"""Predicted-trade oracle (fail-safe Layer 3).

Independent verification that the trade pipeline does what the strategy
*says* it should do. Watches every market tick that hot_path watches,
runs the same StrategyEvaluator in shadow (no gates, no orders), and
publishes a RED alert when the actual pipeline (trade_decisions table +
orders fills) diverges from what the strategy would have produced.

Catches the specific failure mode that bit us 2026-05-26 overnight: 17
APPROVED decisions in the DB, zero corresponding fills, no error trail,
process /health endpoints returning 200 the whole time. Layer 1
(supervisor) prevents the underlying crash; Layer 2 (heartbeat watcher)
detects when a service has gone dark; Layer 3 (this) detects when a
service is alive but not producing the outputs it should be.

Architecture: three supervised loops.

* Loop A — synthetic signal generation
    Subscribe to stream:market_data on a new consumer group
    ('oracle_group'). For every tick, run StrategyEvaluator.evaluate
    against every active profile's compiled rules. Increment per-profile
    per-minute counters in Redis. This is "what hot_path *should*
    approve, before any gate runs."

* Loop B — actual-outcome aggregator
    Every 60 s, poll the `trade_decisions` and `orders` tables for
    rows since the last poll. Sum into per-profile per-minute counters
    in Redis. This is "what the live pipeline actually did."

* Loop C — divergence checker
    Every 60 s, compare synthetic vs approved vs fills over a 5-minute
    rolling window. Publish an AlertEvent(RED) to pubsub:system_alerts
    when divergence exceeds threshold for N consecutive windows.

Out of scope for v1:
    * Bug-in-strategy detection (oracle uses the same StrategyEvaluator
      as hot_path; a bug there is invisible to this oracle). Would
      require a second simpler synthetic check, deferred.
    * Sub-second freshness. Polling, not pubsub on the decisions side.
      Upgrade path is to subscribe to a future pubsub:decision_trace
      channel that hot_path could emit alongside its DB write.
"""

import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from libs.config import settings
from libs.core.enums import EventType, Regime as _Regime
from libs.core.models import NormalisedTick, RiskLimits
from libs.core.notional import profile_notional
from libs.core.schemas import (
    AlertEvent,
    DEFAULT_RISK_LIMITS,
    MarketTickEvent,
)
from libs.indicators import create_indicator_set
from libs.messaging import StreamConsumer, PubSubBroadcaster
from libs.messaging.channels import (
    MARKET_DATA_STREAM,
    PUBSUB_SYSTEM_ALERTS,
)
from libs.observability import get_logger, supervised_task
from libs.storage import RedisClient, TimescaleClient, ProfileRepository
from services.hot_path.src.state import ProfileState
from services.hot_path.src.strategy_eval import StrategyEvaluator
from services.strategy.src.compiler import RuleCompiler

logger = get_logger("oracle")

# ---------- thresholds ----------------------------------------------------
WINDOW_MINUTES = 5             # rolling window for divergence check
POLL_INTERVAL_S = 60.0         # how often Loop B + Loop C run
COUNTER_TTL_S = 60 * 30        # keep per-minute counters in Redis for 30 min
PROFILE_REFRESH_INTERVAL_S = 30
# Stage 1 = strategy → gate-chain dropped signals. Excess synth-vs-approved
# is expected (re-entry guard, regime, validation can legitimately reject).
# Alert only if the gap is *very* sustained and large.
STAGE1_TOLERANCE = 5
STAGE1_CONSECUTIVE_WINDOWS = 3
# Stage 2 = approved decision → fill. Any sustained gap here is a real bug
# (this is precisely the 17-ghost-APPROVALs failure mode). Tight threshold.
STAGE2_TOLERANCE = 0
STAGE2_CONSECUTIVE_WINDOWS = 2

# ---------- redis key helpers --------------------------------------------
def _minute_bucket_now() -> int:
    return int(time.time()) // 60

def _k_synth(pid: str, minute: int) -> str:
    return f"oracle:synth:{pid}:{minute}"

def _k_approved(pid: str, minute: int) -> str:
    return f"oracle:approved:{pid}:{minute}"

def _k_blocked(pid: str, minute: int) -> str:
    """All gate-rejected outcomes (BLOCKED_REENTRY, BLOCKED_ABSTENTION,
    BLOCKED_REGIME, BLOCKED_VALIDATION, BLOCKED_RISK, BLOCKED_HITL,
    BLOCKED_CIRCUIT_BREAKER, BLOCKED_BLACKLIST, BLOCKED_REGIME_MISMATCH).
    Stage 1 subtracts this from synth — a signal blocked by ANY gate
    is correctly accounted for, not a silent fail."""
    return f"oracle:blocked:{pid}:{minute}"

def _k_fills(pid: str, minute: int) -> str:
    return f"oracle:fills:{pid}:{minute}"

def _k_last_decision_poll() -> str:
    return "oracle:state:last_decision_poll"

def _k_last_order_poll() -> str:
    return "oracle:state:last_order_poll"

def _k_consecutive(pid: str, stage: int) -> str:
    return f"oracle:state:consecutive_alert:{pid}:{stage}"


# ---------- profile cache -------------------------------------------------
class _ProfileEntry:
    __slots__ = ("profile_id", "state", "compiled_rules")

    def __init__(self, profile_id: str, state: ProfileState, compiled_rules):
        self.profile_id = profile_id
        self.state = state
        self.compiled_rules = compiled_rules


class ProfileCache:
    """Lightweight refresh-from-DB cache. Reuses hot_path's parsing
    semantics in spirit but simplified (oracle doesn't need risk limits
    or blacklist — those are gate concerns)."""

    def __init__(self, profile_repo: ProfileRepository):
        self._repo = profile_repo
        self._entries: dict[str, _ProfileEntry] = {}

    def get_all(self) -> list[_ProfileEntry]:
        return list(self._entries.values())

    async def refresh(self) -> None:
        try:
            profiles = await self._repo.get_active_profiles()
        except Exception as exc:
            logger.warning("profile_refresh_failed", error=str(exc))
            return

        fresh_ids = set()
        for prof in profiles:
            pid = str(prof["profile_id"])
            fresh_ids.add(pid)
            entry = self._build_entry(pid, prof)
            if entry is None:
                continue
            self._entries[pid] = entry

        # Drop deactivated profiles
        for stale in [p for p in self._entries if p not in fresh_ids]:
            del self._entries[stale]

    def _build_entry(self, pid: str, prof: dict) -> Optional[_ProfileEntry]:
        rules_raw = prof.get("strategy_rules", {})
        rules = json.loads(rules_raw) if isinstance(rules_raw, str) else rules_raw
        required = {"logic", "direction", "base_confidence", "conditions"}
        if not rules or not required.issubset(rules.keys()):
            return None

        try:
            compiled = RuleCompiler.compile(rules)
        except Exception as exc:
            logger.warning("rule_compile_failed", profile_id=pid, error=str(exc))
            return None

        # Minimal RiskLimits — ProfileState requires it; oracle doesn't use it
        risk_limits = RiskLimits(
            max_drawdown_pct=Decimal(str(DEFAULT_RISK_LIMITS["max_drawdown_pct"])),
            stop_loss_pct=Decimal(str(DEFAULT_RISK_LIMITS["stop_loss_pct"])),
            circuit_breaker_daily_loss_pct=Decimal(str(DEFAULT_RISK_LIMITS["circuit_breaker_daily_loss_pct"])),
            max_allocation_pct=Decimal(str(DEFAULT_RISK_LIMITS["max_allocation_pct"])),
        )

        # Preserve an entry's existing indicator state across refreshes so
        # priming history isn't lost when the cache reloads.
        existing = self._entries.get(pid)
        indicators = existing.state.indicators if existing else create_indicator_set()

        state = ProfileState(
            profile_id=pid,
            compiled_rules=compiled,
            risk_limits=risk_limits,
            blacklist=frozenset(),
            indicators=indicators,
            notional=profile_notional(prof),
            preferred_regimes=frozenset(),  # oracle ignores regime gating
        )
        return _ProfileEntry(profile_id=pid, state=state, compiled_rules=compiled)


# ---------- Loop A: synthetic signal generation ---------------------------
async def synthetic_signal_loop(
    consumer: StreamConsumer,
    redis_client,
    profile_cache: ProfileCache,
):
    """Consume stream:market_data and run StrategyEvaluator in shadow.

    Note: this uses its OWN consumer group ('oracle_group'), so it doesn't
    interfere with hot_path's stream consumption. Both read the same tick
    stream; trim is bounded by ingestion's maxlen cap."""
    group_name = "oracle_group"
    consumer_name = "oracle_1"
    logger.info("synthetic_signal_loop starting", group=group_name)

    while True:
        try:
            events = await consumer.consume(
                MARKET_DATA_STREAM, group_name, consumer_name, count=100, block_ms=50
            )
        except Exception as exc:
            logger.error("oracle consume failed — retrying", error=str(exc))
            await asyncio.sleep(1)
            continue

        ack_ids = []
        for msg_id, event in events:
            if not event or not isinstance(event, MarketTickEvent):
                ack_ids.append(msg_id)
                continue

            tick = NormalisedTick(
                symbol=event.symbol,
                exchange=event.exchange,
                timestamp=event.timestamp_us,
                price=event.price,
                volume=event.volume,
            )

            for entry in profile_cache.get_all():
                try:
                    result = StrategyEvaluator.evaluate(entry.state, tick)
                except Exception as exc:
                    logger.warning(
                        "synthetic_eval_failed",
                        profile_id=entry.profile_id,
                        error=str(exc),
                    )
                    continue

                if result is None:
                    continue  # indicators still priming
                sig_res, _ = result
                if sig_res is None or not sig_res.rule_matched:
                    continue

                bucket = _minute_bucket_now()
                key = _k_synth(entry.profile_id, bucket)
                try:
                    await redis_client.incr(key)
                    await redis_client.expire(key, COUNTER_TTL_S)
                except Exception as exc:
                    logger.warning("synth_counter_write_failed", error=str(exc))

            ack_ids.append(msg_id)

        if ack_ids:
            try:
                await consumer.ack(MARKET_DATA_STREAM, group_name, ack_ids)
            except Exception as exc:
                logger.warning("oracle_ack_failed", error=str(exc))


# ---------- Loop B: actual-outcome aggregator -----------------------------
def _read_cursor(raw, default_dt):
    """Decode a Redis-stored ISO timestamp; fall back to default on miss."""
    if not raw:
        return default_dt
    s = raw.decode() if isinstance(raw, bytes) else raw
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return default_dt


async def actual_outcome_loop(redis_client, timescale: TimescaleClient):
    """Poll trade_decisions + orders since last cursor and tally per
    profile per minute-bucket."""
    logger.info("actual_outcome_loop starting", poll_s=POLL_INTERVAL_S)
    while True:
        try:
            now = datetime.now(timezone.utc)
            # First-poll fallback: cap the lookback to one window + a
            # margin so we don't tally arbitrary history on cold start.
            initial_lookback = now - timedelta(minutes=WINDOW_MINUTES + 1)

            # --- decisions ---
            last_decision_raw = await redis_client.get(_k_last_decision_poll())
            last_decision = _read_cursor(last_decision_raw, initial_lookback)

            rows = await timescale.fetch(
                """
                SELECT profile_id, outcome, created_at
                FROM trade_decisions
                WHERE created_at > $1
                  AND created_at <= $2
                """,
                last_decision,
                now,
            )

            for row in rows:
                pid = str(row["profile_id"])
                outcome = row["outcome"]
                bucket = int(row["created_at"].timestamp()) // 60
                if outcome == "APPROVED":
                    key = _k_approved(pid, bucket)
                    await redis_client.incr(key)
                    await redis_client.expire(key, COUNTER_TTL_S)
                elif outcome and outcome.startswith("BLOCKED_"):
                    # Every gate-rejection counts as legitimate accounting.
                    # The original implementation only tracked BLOCKED_REENTRY,
                    # which produced Stage 1 false positives whenever any
                    # other gate (regime, abstention, validation, risk, etc.)
                    # rejected a signal.
                    key = _k_blocked(pid, bucket)
                    await redis_client.incr(key)
                    await redis_client.expire(key, COUNTER_TTL_S)

            await redis_client.set(_k_last_decision_poll(), now.isoformat())

            # --- fills (CONFIRMED orders) ---
            last_order_raw = await redis_client.get(_k_last_order_poll())
            last_order = _read_cursor(last_order_raw, initial_lookback)

            order_rows = await timescale.fetch(
                """
                SELECT profile_id, created_at
                FROM orders
                WHERE status = 'CONFIRMED'
                  AND created_at > $1
                  AND created_at <= $2
                """,
                last_order,
                now,
            )

            for row in order_rows:
                pid = str(row["profile_id"])
                bucket = int(row["created_at"].timestamp()) // 60
                key = _k_fills(pid, bucket)
                await redis_client.incr(key)
                await redis_client.expire(key, COUNTER_TTL_S)

            await redis_client.set(_k_last_order_poll(), now.isoformat())
        except Exception:
            logger.exception("actual_outcome_loop pass failed")

        await asyncio.sleep(POLL_INTERVAL_S)


# ---------- Loop C: divergence checker ------------------------------------
async def _sum_window(redis_client, key_fn, pid: str, end_minute: int) -> int:
    total = 0
    for offset in range(WINDOW_MINUTES):
        bucket = end_minute - offset
        val = await redis_client.get(key_fn(pid, bucket))
        if val is not None:
            try:
                total += int(val)
            except (TypeError, ValueError):
                pass
    return total


async def divergence_loop(
    redis_client,
    pubsub: PubSubBroadcaster,
    profile_cache: ProfileCache,
):
    """Compare synthetic / approved / fills over rolling 5-minute window."""
    logger.info("divergence_loop starting", window_m=WINDOW_MINUTES)

    # Sleep one window before first check so loop B has data to compare.
    await asyncio.sleep(POLL_INTERVAL_S * 2)

    while True:
        try:
            end_minute = _minute_bucket_now()
            for entry in profile_cache.get_all():
                pid = entry.profile_id

                synth = await _sum_window(redis_client, _k_synth, pid, end_minute)
                approved = await _sum_window(redis_client, _k_approved, pid, end_minute)
                blocked = await _sum_window(redis_client, _k_blocked, pid, end_minute)
                fills = await _sum_window(redis_client, _k_fills, pid, end_minute)

                # Stage 1: hot_path's strategy fired but no decision was
                # recorded at all (silent fail in the strategy → gate chain).
                # Any BLOCKED_* outcome counts as a legitimate accounting,
                # so the gap is synth − (approved + blocked). Sustained
                # positive gap means hot_path's evaluate() saw the same tick
                # the oracle did but didn't write any decision row.
                accounted = approved + blocked
                stage1_gap = synth - accounted
                if stage1_gap > STAGE1_TOLERANCE:
                    n = await redis_client.incr(_k_consecutive(pid, 1))
                    await redis_client.expire(_k_consecutive(pid, 1), COUNTER_TTL_S)
                    if n >= STAGE1_CONSECUTIVE_WINDOWS:
                        await _publish_divergence_alert(
                            pubsub,
                            pid,
                            stage=1,
                            synth=synth, blocked=blocked, approved=approved, fills=fills,
                            gap=stage1_gap,
                            consecutive=n,
                        )
                else:
                    await redis_client.delete(_k_consecutive(pid, 1))

                # Stage 2: approvals not turning into fills. Tight tolerance.
                stage2_gap = approved - fills
                if stage2_gap > STAGE2_TOLERANCE:
                    n = await redis_client.incr(_k_consecutive(pid, 2))
                    await redis_client.expire(_k_consecutive(pid, 2), COUNTER_TTL_S)
                    if n >= STAGE2_CONSECUTIVE_WINDOWS:
                        await _publish_divergence_alert(
                            pubsub,
                            pid,
                            stage=2,
                            synth=synth, blocked=blocked, approved=approved, fills=fills,
                            gap=stage2_gap,
                            consecutive=n,
                        )
                else:
                    await redis_client.delete(_k_consecutive(pid, 2))

                logger.info(
                    "oracle_window",
                    profile_id=pid,
                    window_m=WINDOW_MINUTES,
                    synth=synth, blocked=blocked, approved=approved, fills=fills,
                    stage1_gap=stage1_gap, stage2_gap=stage2_gap,
                )
        except Exception:
            logger.exception("divergence_loop pass failed")

        await asyncio.sleep(POLL_INTERVAL_S)


async def _publish_divergence_alert(
    pubsub: PubSubBroadcaster,
    profile_id: str,
    stage: int,
    synth: int, blocked: int, approved: int, fills: int,
    gap: int, consecutive: int,
):
    """Push a RED alert. Frontend chrome's alertStore picks it up via
    api_gateway's WS fan-out of pubsub:system_alerts."""
    stage_name = "strategy→gates" if stage == 1 else "gates→execution"
    msg = (
        f"Oracle divergence (stage {stage}: {stage_name}) for profile {profile_id} — "
        f"gap={gap} over last {WINDOW_MINUTES}m, sustained {consecutive} windows. "
        f"synth={synth} blocked={blocked} approved={approved} fills={fills}. "
        f"Indicates the live pipeline is dropping work the strategy says should happen."
    )
    logger.error(
        "oracle_divergence_detected",
        stage=stage,
        profile_id=profile_id,
        synth=synth, blocked=blocked, approved=approved, fills=fills,
        gap=gap, consecutive=consecutive,
    )
    event = AlertEvent(
        event_type=EventType.ALERT_RED,
        timestamp_us=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
        source_service="oracle",
        message=msg,
        level="RED",
        profile_id=profile_id,
    )
    try:
        await pubsub.publish(PUBSUB_SYSTEM_ALERTS, event)
    except Exception:
        logger.exception(
            "oracle alert publish failed",
            profile_id=profile_id,
            stage=stage,
        )


# ---------- FastAPI lifespan ---------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale = TimescaleClient(settings.DATABASE_URL)
    await timescale.init_pool()

    profile_repo = ProfileRepository(timescale)
    profile_cache = ProfileCache(profile_repo)
    await profile_cache.refresh()
    logger.info(
        "Oracle started with profiles",
        count=len(profile_cache.get_all()),
        ids=[e.profile_id for e in profile_cache.get_all()],
    )

    consumer = StreamConsumer(redis_client)
    pubsub = PubSubBroadcaster(redis_client)

    async def _refresh_loop():
        while True:
            await asyncio.sleep(PROFILE_REFRESH_INTERVAL_S)
            await profile_cache.refresh()

    refresh_task = supervised_task(_refresh_loop, name="oracle.profile_refresh")
    synth_task = supervised_task(
        lambda: synthetic_signal_loop(consumer, redis_client, profile_cache),
        name="oracle.synthetic_signal",
    )
    actual_task = supervised_task(
        lambda: actual_outcome_loop(redis_client, timescale),
        name="oracle.actual_outcome",
    )
    diverge_task = supervised_task(
        lambda: divergence_loop(redis_client, pubsub, profile_cache),
        name="oracle.divergence",
    )

    # Expose for /diagnostics endpoint
    app.state.profile_cache = profile_cache
    app.state.redis = redis_client

    yield

    for t in (refresh_task, synth_task, actual_task, diverge_task):
        t.cancel()
    await asyncio.gather(refresh_task, synth_task, actual_task, diverge_task,
                        return_exceptions=True)
    await timescale.close()
    logger.info("Oracle shutdown gracefully")


app = FastAPI(title="Predicted-Trade Oracle", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/diagnostics")
async def diagnostics():
    """Show the live state of the rolling counters per profile. Useful
    for debugging divergence alerts and verifying the oracle is seeing
    what hot_path is seeing."""
    cache: ProfileCache = app.state.profile_cache
    redis_client = app.state.redis
    end_minute = _minute_bucket_now()
    out = {"window_minutes": WINDOW_MINUTES, "profiles": {}}
    for entry in cache.get_all():
        pid = entry.profile_id
        synth = await _sum_window(redis_client, _k_synth, pid, end_minute)
        approved = await _sum_window(redis_client, _k_approved, pid, end_minute)
        blocked = await _sum_window(redis_client, _k_blocked, pid, end_minute)
        fills = await _sum_window(redis_client, _k_fills, pid, end_minute)
        out["profiles"][pid] = {
            "synth": synth, "blocked": blocked,
            "approved": approved, "fills": fills,
            "stage1_gap": synth - (approved + blocked),
            "stage2_gap": approved - fills,
        }
    return out


if __name__ == "__main__":
    uvicorn.run("services.oracle.src.main:app", host="0.0.0.0", port=8097)
