import asyncio
import json
import uuid
import httpx
from decimal import Decimal
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage._redis_client import RedisClient
from libs.storage import TimescaleClient, ProfileRepository
from libs.storage.repositories.position_repo import PositionRepository
from libs.messaging import StreamConsumer, StreamPublisher, PubSubBroadcaster
from libs.messaging._pubsub import PubSubSubscriber
from libs.messaging.channels import (
    MARKET_DATA_STREAM,
    ORDERS_STREAM,
    VALIDATION_STREAM,
    VALIDATION_RESPONSE_STREAM,
    PUBSUB_THRESHOLD_PROXIMITY
)
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher
from libs.core.models import RiskLimits
from libs.core.notional import profile_notional
from libs.core.schemas import DEFAULT_RISK_LIMITS
from libs.indicators import create_indicator_set
from services.strategy.src.compiler import RuleCompiler

from .state import ProfileState, ProfileStateCache
from .validation_client import ValidationClient
from .processor import HotPathProcessor
from .pnl_sync import PnlSync
from .decision_writer import DecisionTraceWriter
from libs.storage.repositories.decision_repo import DecisionRepository

logger = get_logger("hot-path.main")

async def verify_validation_agent_health():
    """Wait and verify validation agent is completely online before starting."""
    url = "http://validation:8080/health"
    backoff = 1.0

    logger.info("Waiting for Validation Agent health check...")

    async with httpx.AsyncClient() as client:
        while True:
            try:
                res = await client.get(url, timeout=2.0)
                if res.status_code == 200:
                    logger.info("Validation Agent is HEALTHY.")
                    break
            except httpx.ConnectError:
                pass

            logger.info(f"Validation Agent unavailable. Retrying in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

async def wait_for_hydration_complete(redis_client, state_cache: ProfileStateCache):
    """Wait for strategy agent to hydrate cache elements to start safely"""
    while True:
        all_ready = True
        for prof in state_cache.itervalues():
            key = f"hydration:{prof.profile_id}:status"
            status = await redis_client.get(key)
            if status != b"complete":
                all_ready = False
                break

        if all_ready and len(list(state_cache.itervalues())) > 0:
             break

        # If no profiles, skip wait for dummy boots
        if len(list(state_cache.itervalues())) == 0:
             break

        await asyncio.sleep(1.0)
    logger.info("Profile states successfully hydrated.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Core Setup
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    consumer = StreamConsumer(redis_instance)
    publisher = StreamPublisher(redis_instance)
    pubsub = PubSubBroadcaster(redis_instance)
    pubsub_subscriber = PubSubSubscriber(redis_instance)

    val_client = ValidationClient(
        publisher=publisher,
        consumer=consumer,
        req_channel=VALIDATION_STREAM,
        resp_channel=VALIDATION_RESPONSE_STREAM,
        timeout_ms=settings.FAST_GATE_TIMEOUT_MS
    )

    state_cache = ProfileStateCache()

    # 0. Load active profiles from database into state cache
    ts_client = TimescaleClient(settings.DATABASE_URL)
    await ts_client.init_pool()
    profile_repo = ProfileRepository(ts_client)

    def _parse_static_config(prof):
        """Parse rules / risk / blacklist from a DB row.
        Returns (compiled, risk_limits, bl, notional, preferred_regimes) or None."""
        rules_raw = prof.get("strategy_rules", {})
        rules = json.loads(rules_raw) if isinstance(rules_raw, str) else rules_raw
        required_keys = {"logic", "direction", "base_confidence", "conditions"}
        if not rules or not required_keys.issubset(rules.keys()):
            return None
        compiled = RuleCompiler.compile(rules)

        limits_raw = prof.get("risk_limits", {})
        limits = json.loads(limits_raw) if isinstance(limits_raw, str) else limits_raw
        risk_limits = RiskLimits(
            max_drawdown_pct=Decimal(str(limits.get("max_drawdown_pct", DEFAULT_RISK_LIMITS["max_drawdown_pct"]))),
            stop_loss_pct=Decimal(str(limits.get("stop_loss_pct", DEFAULT_RISK_LIMITS["stop_loss_pct"]))),
            circuit_breaker_daily_loss_pct=Decimal(str(limits.get("circuit_breaker_daily_loss_pct", DEFAULT_RISK_LIMITS["circuit_breaker_daily_loss_pct"]))),
            max_allocation_pct=Decimal(str(limits.get("max_allocation_pct", DEFAULT_RISK_LIMITS["max_allocation_pct"]))),
        )

        blacklist_raw = prof.get("blacklist", [])
        if isinstance(blacklist_raw, str):
            bl = json.loads(blacklist_raw)
        else:
            bl = blacklist_raw if isinstance(blacklist_raw, list) else []

        # Notional capital — single source of truth in libs/core/notional.py
        notional = profile_notional(prof)

        # C.4: preferred_regimes lives inside strategy_rules JSONB. Coerce each
        # entry to the Regime enum; silently drop unknown values rather than
        # crashing the loader (a typo in a profile shouldn't take hot_path down).
        from libs.core.enums import Regime as _Regime
        pr_raw = rules.get("preferred_regimes", []) or []
        pr_set: set = set()
        for name in pr_raw:
            try:
                pr_set.add(_Regime(name))
            except ValueError:
                logger.warning(
                    "Unknown regime in profile preferred_regimes; ignoring",
                    profile_id=str(prof.get("profile_id")),
                    regime=name,
                )
        preferred_regimes = frozenset(pr_set)

        return compiled, risk_limits, frozenset(bl), notional, preferred_regimes

    profiles = await profile_repo.get_active_profiles()
    for prof in profiles:
        parsed = _parse_static_config(prof)
        if parsed is None:
            logger.warning("Profile %s has incomplete strategy_rules, skipping", prof.get("profile_id"))
            continue
        compiled, risk_limits, bl, notional, preferred_regimes = parsed
        state = ProfileState(
            profile_id=str(prof["profile_id"]),
            compiled_rules=compiled,
            risk_limits=risk_limits,
            blacklist=bl,
            indicators=create_indicator_set(),
            notional=notional,
            preferred_regimes=preferred_regimes,
        )
        state_cache.add(state)

    logger.info(f"Loaded {len(profiles)} profiles into state cache")

    async def _profile_refresh_loop():
        """Refresh profile rules/risk/blacklist from DB every 30s without resetting indicators.
        Adds new profiles, updates existing ones, removes deactivated/deleted ones."""
        REFRESH_INTERVAL_S = 30
        try:
            while True:
                await asyncio.sleep(REFRESH_INTERVAL_S)
                try:
                    fresh = await profile_repo.get_active_profiles()
                    fresh_by_id = {str(p["profile_id"]): p for p in fresh}

                    # Update or add
                    for pid, prof in fresh_by_id.items():
                        parsed = _parse_static_config(prof)
                        if parsed is None:
                            continue
                        compiled, risk_limits, bl, notional, preferred_regimes = parsed
                        existing = state_cache.get(pid)
                        if existing:
                            existing.compiled_rules = compiled
                            existing.risk_limits = risk_limits
                            existing.blacklist = bl
                            existing.notional = notional
                            existing.preferred_regimes = preferred_regimes
                        else:
                            new_state = ProfileState(
                                profile_id=pid,
                                compiled_rules=compiled,
                                risk_limits=risk_limits,
                                blacklist=bl,
                                indicators=create_indicator_set(),
                                notional=notional,
                                preferred_regimes=preferred_regimes,
                            )
                            state_cache.add(new_state)
                            logger.info("Profile %s added to state cache via refresh", pid)

                    # Remove profiles no longer active
                    cached_ids = [s.profile_id for s in list(state_cache.itervalues())]
                    for pid in cached_ids:
                        if pid not in fresh_by_id:
                            state_cache.remove(pid)
                            logger.info("Profile %s removed from state cache via refresh", pid)
                except Exception as e:
                    logger.error("Profile refresh loop error", error=str(e))
        except asyncio.CancelledError:
            pass

    # 1. Hydrate cache loop Wait
    await wait_for_hydration_complete(redis_instance, state_cache)

    # 2. Start PnL sync background task (Sprint 10.1)
    pnl_sync = PnlSync(
        redis_instance,
        pubsub_subscriber,
        state_cache,
        position_repo=PositionRepository(ts_client),
    )
    pnl_sync_task = asyncio.create_task(pnl_sync.run())

    # 2b. Start profile refresh loop — picks up canvas saves without service restart
    profile_refresh_task = asyncio.create_task(_profile_refresh_loop())

    # Telemetry publisher
    telemetry = TelemetryPublisher(redis_instance, "hot_path", "orchestrator")
    await telemetry.start_health_loop()

    # Decision trace writer
    decision_repo = DecisionRepository(ts_client)
    decision_writer = DecisionTraceWriter(decision_repo)

    processor = HotPathProcessor(
        state_cache=state_cache,
        consumer=consumer,
        publisher=publisher,
        pubsub=pubsub,
        validation_client=val_client,
        tick_channel=MARKET_DATA_STREAM,
        orders_channel=ORDERS_STREAM,
        proximity_pubsub_channel=PUBSUB_THRESHOLD_PROXIMITY,
        redis_client=redis_instance,
        telemetry=telemetry,
        decision_writer=decision_writer,
    )

    logger.info("Injecting Hot-Path background loop.")
    task = asyncio.create_task(processor.run())

    yield

    # Teardown
    task.cancel()
    pnl_sync_task.cancel()
    profile_refresh_task.cancel()
    await asyncio.gather(task, pnl_sync_task, profile_refresh_task, return_exceptions=True)
    await telemetry.stop()
    await ts_client.close()
    logger.info("Hot-Path shutdown gracefully.")

app = FastAPI(title="HotPath Processor", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.hot_path.src.main:app", host="0.0.0.0", port=8082)
