"""EN-W2 per-profile edge triage — operational runner (2026-06-12).

Enqueues honest walk-forward backtests for the active soak profile and the
three MACD profiles, plus an exit-band A/B sweep for the soak profile, then
polls results and prints OOS metrics + close-reason mixes + the live
convergence comparison (PR7 cross-check).

Mechanics
---------
- Direct queue enqueue (no HTTP auth): the payload mirrors the gateway's
  POST /backtest shape exactly (services/api_gateway/src/routes/backtest.py).
  trading_profiles.strategy_rules is already the COMPILED canonical shape the
  worker expects, so no recompilation is needed.
- Runs use the profile owner's real user UUID (DB created_by is a UUID FK).
- Live signal evaluation is on 1m candles (services/strategy/src/hydrator.py),
  so honest baselines run on 1m data.
- BASELINE-POISONING GUARD: backtest_repo.latest_for_profile() takes the MOST
  RECENT row per profile as the decay baseline. Exploratory runs (the exit-band
  A/B sweep) therefore carry profile_id="" and the canonical per-profile
  baseline runs are enqueued LAST.
- Convergence check filters close_reason="end_of_data" per DECISIONS 2026-06-11
  (each walk-forward window contributes one synthetic boundary close).

Usage:  poetry run python scripts/en_w2_edge_triage.py [--enqueue-only]
"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from libs.config import settings  # noqa: E402
from libs.storage import RedisClient  # noqa: E402

OWNER_USER_ID = "6322b6fa-d425-51d7-a818-088c19275228"  # stevo.do.ob@gmail.com
SOAK_PROFILE_ID = "a05adba2-5128-4bef-bb92-a3cb429b55e1"  # Phase 0 Soak
MACD_PROFILES = {
    "macd-trend": "5d55f08e-69d7-4160-a53b-7d364aa3b136",  # Trend Following (MACD)
    "macd-pullback": "c557fcdc-2bc2-4ef3-8004-102cd71859c0",  # Demo · Pullback Long
    "macd-oversold": "8d284f48-32e5-446b-8feb-7a72014108dd",  # Oversold Uptrend
}

# 1m coverage starts 2026-04-18 (memory/registry: earlier data refetched then).
START = "2026-04-18T00:00:00"
END = "2026-06-12T12:00:00"
TIMEFRAME = "1m"
SLIPPAGE = "0.001"

# 14d train / 7d test / 7d step on 1m bars → ~3 windows over the range.
WF = {"train_bars": 20160, "test_bars": 10080, "step_bars": 10080}

# Exit-band A/B around the soak profile's current bands (SL 4% / TP 3% / 6h):
# live mix is 28/30 time_exit, so the sweep widens TP down and hold up.
# 2 x 3 x 3 = 18 combos <= 100; 18 x ~3 windows = ~54 runs <= 1,000.
RISK_GRID = {
    "stop_loss_pct": [0.02, 0.04],
    "take_profit_pct": [0.01, 0.02, 0.03],
    "max_holding_hours": [6.0, 12.0, 24.0],
}

POLL_S = 5
JOB_TIMEOUT_S = 700  # worker-side cap is 600s; small cushion


async def load_profiles(conn) -> dict:
    rows = await conn.fetch(
        """SELECT profile_id, name, strategy_rules, risk_limits
           FROM trading_profiles WHERE profile_id = ANY($1::uuid[])""",
        [SOAK_PROFILE_ID, *MACD_PROFILES.values()],
    )
    out = {}
    for r in rows:
        rules = r["strategy_rules"]
        limits = r["risk_limits"]
        out[str(r["profile_id"])] = {
            "name": r["name"],
            "rules": json.loads(rules) if isinstance(rules, str) else dict(rules),
            "limits": json.loads(limits) if isinstance(limits, str) else dict(limits),
        }
    return out


def build_payload(
    job_id: str,
    symbol: str,
    rules: dict,
    limits: dict | None,
    profile_id: str,
    walk_forward: dict,
    risk_limits_grid: dict | None = None,
) -> dict:
    """Mirror of the gateway enqueue payload (routes/backtest.py)."""
    return {
        "job_id": job_id,
        "user_id": OWNER_USER_ID,
        "symbol": symbol,
        "strategy_rules": rules,
        "start_date": START,
        "end_date": END,
        "timeframe": TIMEFRAME,
        "slippage_pct": SLIPPAGE,
        "profile_id": profile_id,
        "risk_limits": limits,
        "walk_forward": walk_forward,
        "risk_limits_grid": risk_limits_grid,
    }


def close_mix(trades: list) -> tuple[Counter, Counter]:
    """(raw mix, mix with end_of_data filtered) over a trades list."""
    raw = Counter(t.get("close_reason", "?") for t in trades)
    filtered = Counter({k: v for k, v in raw.items() if k != "end_of_data"})
    return raw, filtered


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enqueue-only", action="store_true")
    args = parser.parse_args()

    conn = await asyncpg.connect(settings.DATABASE_URL)
    profiles = await load_profiles(conn)
    redis = RedisClient.get_instance(settings.REDIS_URL).get_connection()

    jobs: list[dict] = []

    # 1) MACD triage — honest plain walk-forward per profile per symbol.
    #    profile_id SET: these become each (inactive) profile's honest
    #    baseline; latest-wins is fine because nothing later overwrites them.
    for label, pid in MACD_PROFILES.items():
        p = profiles[pid]
        for sym, sym_tag in (("BTC/USDT", "btc"), ("ETH/USDT", "eth")):
            jobs.append(
                build_payload(
                    f"en-w2-{label}-{sym_tag}", sym, p["rules"], p["limits"], pid, WF
                )
            )

    # 2) Soak exit-band A/B — EXPLORATORY, so profile_id="" (must not become
    #    the decay baseline).
    soak = profiles[SOAK_PROFILE_ID]
    jobs.append(
        build_payload(
            "en-w2-soak-exit-ab",
            "ETH/USDT",
            soak["rules"],
            soak["limits"],
            "",
            WF,
            risk_limits_grid=RISK_GRID,
        )
    )

    # 3) Soak canonical baseline — LAST, with profile_id, real limits.
    jobs.append(
        build_payload(
            "en-w2-soak-baseline",
            "ETH/USDT",
            soak["rules"],
            soak["limits"],
            SOAK_PROFILE_ID,
            WF,
        )
    )

    for payload in jobs:
        await redis.xadd("auto_backtest_queue", {"data": json.dumps(payload)})
        print(f"enqueued {payload['job_id']}")

    if args.enqueue_only:
        await conn.close()
        return

    # Poll serially in enqueue order (the worker is serial anyway).
    results: dict[str, dict] = {}
    for payload in jobs:
        job_id = payload["job_id"]
        waited = 0
        while waited <= JOB_TIMEOUT_S:
            raw = await redis.get(f"backtest:status:{job_id}")
            data = json.loads(raw) if raw else {}
            status = data.get("status", "missing")
            if status in ("completed", "failed"):
                results[job_id] = data
                break
            await asyncio.sleep(POLL_S)
            waited += POLL_S
        else:
            results[job_id] = {"status": f"timeout after {JOB_TIMEOUT_S}s"}
        print(f"{job_id}: {results[job_id].get('status')}")

    # ----- Report ---------------------------------------------------------
    print("\n" + "=" * 72)
    print("EN-W2 EDGE TRIAGE REPORT")
    print("=" * 72)
    for job_id, data in results.items():
        print(f"\n--- {job_id} [{data.get('status')}] ---")
        if data.get("status") != "completed":
            print(json.dumps(data, indent=2, default=str)[:2000])
            continue
        for k in (
            "total_trades",
            "win_rate",
            "avg_return",
            "sharpe",
            "max_drawdown",
            "profit_factor",
            "coverage_pct",
        ):
            if k in data:
                print(f"  {k}: {data[k]}")
        raw, filtered = close_mix(data.get("trades", []))
        print(f"  close_mix(raw): {dict(raw)}")
        print(f"  close_mix(no end_of_data): {dict(filtered)}")
        wf = data.get("walk_forward") or {}
        for w in wf.get("windows", []):
            print(
                "  window"
                f" is_sharpe={w.get('in_sample_sharpe')}"
                f" oos_trades={w.get('oos_trades')}"
                f" params={w.get('chosen_params')}"
                f" bands={w.get('chosen_risk_params')}"
            )

    # ----- Convergence check (soak baseline vs live closed_trades) --------
    live_rows = await conn.fetch(
        "SELECT close_reason, count(*) AS n FROM closed_trades"
        " WHERE profile_id=$1 GROUP BY close_reason",
        SOAK_PROFILE_ID,
    )
    live = Counter({r["close_reason"]: r["n"] for r in live_rows})
    base = results.get("en-w2-soak-baseline", {})
    _, sim = close_mix(base.get("trades", []))
    print("\n--- CONVERGENCE (soak profile, end_of_data filtered) ---")
    for name, mix in (("live", live), ("backtest-OOS", sim)):
        total = sum(mix.values()) or 1
        pct = {k: f"{100 * v / total:.0f}%" for k, v in sorted(mix.items())}
        print(f"  {name}: n={sum(mix.values())} {pct}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
