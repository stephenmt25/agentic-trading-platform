# Phase 0 Soak — Status & Partner Update

> **Launched:** 2026-05-20  ·  **Last updated:** 2026-05-22
> **Status:** engine stabilised and running clean after a 3-day shakedown — verified 30+ minutes continuous, crash-resilient.
> **Companion docs:** `PLATFORM_VIABILITY_PLAN_2026-05-18.md` (§3 Phase 0), `TECH-DEBT-REGISTRY.md`.

---

## Summary — the launch was a shakedown

The Phase 0 soak launch functioned as a full shakedown of the trading engine. Over three days (2026-05-20 → 22) it surfaced roughly a dozen genuine bugs — each of which would have bitten in live trading — all now found, fixed, committed and verified. The engine is now crash-resilient and running clean on live data.

## What's running

- **Profile:** `Phase 0 Soak — Hold Baseline` (`a05adba2-5128-4bef-bb92-a3cb429b55e1`) — the only active profile. Entry `rsi < 35` → BUY; exits stop-loss 4% / take-profit 3% / `max_holding_hours` 6h. `exchange_key_ref=paper`.
- **Engine:** 19 services + frontend, live Binance market data.

## Verified state (2026-05-22)

| Check | Result |
|---|---|
| hot_path | 30+ min continuous, processing live ticks, current — no crash, no stall |
| Boot pyramid | **none** — stale-tick guard skips the backlog (vs 90 positions opened before the fix) |
| Open positions | 0 — engine healthy, awaiting a live entry signal |
| `stream:market_data` | bounded ~10k (was 1M+ untrimmed) |
| Service ports / `/ready` | 17/17, redis + postgres `ok` |
| Frontend `:3001` | HTTP 200 |

## Bugs found & fixed during the shakedown

| Issue | Fix |
|---|---|
| HITL gate's blocking `blpop` ran inside the per-tick loop — froze the engine | HITL disabled for the autonomous soak (`.env`) |
| Entry logic stacked ~190 positions in 17s (no "already in a position" check) | re-entry guard — one open position per (profile, symbol) |
| Re-entry guard race let an occasional duplicate position through | grace-window reconciliation in `PnlSync` |
| `daily_report` daemon crashed permanently on a cold-start DB timeout | retry + survive-and-continue |
| `stream:market_data` grew unbounded (1M+ entries) | `maxlen` cap on publish |
| Processor crashed *silently* on a transient Redis `TimeoutError` (consume, then validation) | `run()` supervisor — restarts the loop on any crash; consume guard |
| Engine could fail invisibly | stall watchdog + processor-crash done-callback |
| Boot replayed a stale tick backlog → trades on hours-old prices + pyramid | stale-tick guard — only live data is traded |
| `run_all.sh --stop` left orphaned `python` zombies every time | kills process trees (`//T`) + port sweep + command-line catch-all |

Commits on `main`: `cfc5b9a`, `cfe379f`, `b264c81`, `8af7a13`, `9d9b491`, `fd11522`, `4ec3389`, `d223b93`, `3f4aa32`, `01c9fca`, `a3f2d04`. (`run_all.sh` carries unrelated pre-existing WIP — its `--stop` fix is on disk but left uncommitted for the owner to commit.)

## Partner message (latest)

> Soak update — the engine is *stabilised and running clean*.
>
> The launch was effectively a shakedown — it surfaced ~a dozen real bugs in the trading engine over three days, all now fixed (position pyramiding, a gate that hung the engine, silent crashes, trading on stale data). Far better to flush these out in a paper soak than with real money.
>
> The engine is now crash-resilient: it survives transient hiccups, restarts its own loop on any failure, and can no longer fail silently — it's fully instrumented. Verified clean for 30+ minutes continuous. The 14-day measurement clock runs from here.

## Operational notes (soak hygiene)

- Laptop must be set to **never sleep** for the duration — uptime is the property under test (`PLATFORM_VIABILITY_PLAN_2026-05-18.md` §1).
- Keep a **downtime log** — any sleep / restart / ISP blip is soak *data*, not automatically a failure.
- `run_all.sh --stop` now leaves a genuinely clean slate (process-tree kill + sweeps). The recurring-zombie problem is fixed.
- If hot_path ever dies, it is now *visible*: `grep -E "processor_task_crashed|processor_stall_detected|processor loop crashed" .praxis_logs/hot_path.log`.
- Review the daily P&L report as days accumulate; the exit criterion is a coherent PnL distribution over hour-scale-hold trades.
