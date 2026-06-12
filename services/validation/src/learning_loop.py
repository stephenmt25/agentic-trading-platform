"""Hourly learning loop: RED/AMBER validation events trigger auto-backtests.

Publishing contract (registry row 57): the backtesting JobRunner reads ONLY
the gateway wire shape — a raw ``{"data": json.dumps(payload)}`` stream field
on ``auto_backtest_queue`` (services/api_gateway/src/routes/backtest.py).
The previous implementation published msgpack via StreamPublisher (a
``payload`` field), which the runner cannot read — every auto-backtest job
was silently dropped — and carried no symbol/strategy_rules/risk_limits.

DECAY-BASELINE GUARD (latest-wins landmine): backtest_repo.latest_for_profile
treats the NEWEST backtest_results row carrying a profile_id as that
profile's decay baseline. Auto-runs are exploratory diagnostics, so they are
ALWAYS enqueued with profile_id="" and must never overwrite an operator's
baseline. The originating profile rides along as ``source_profile_id``
(ignored by the runner; kept for traceability).
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

from libs.config import settings
from libs.core.enums import ValidationCheck
from libs.messaging import StreamPublisher
from libs.observability import get_logger
from libs.storage.repositories import ProfileRepository, ValidationRepository

logger = get_logger("validation.learning_loop")

# Same stream the gateway POST /backtest writes and the backtesting
# JobRunner consumes (services/backtesting/src/job_runner.py).
AUTO_BACKTEST_QUEUE = "auto_backtest_queue"
AUTO_BACKTEST_LOOKBACK_DAYS = 30
AUTO_BACKTEST_TIMEFRAME = "1m"  # live signal evaluation runs on 1m candles
AUTO_BACKTEST_SLIPPAGE_PCT = "0.001"  # gateway default; str preserves Decimal


def _as_dict(value) -> dict:
    """JSONB columns arrive as dict or JSON string depending on codec."""
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}
    return dict(value)


class LearningLoop:
    def __init__(
        self,
        validation_repo: ValidationRepository,
        publisher: StreamPublisher,
        profile_repo: ProfileRepository | None = None,
        redis_client=None,
    ):
        self._validation_repo = validation_repo
        self._publisher = publisher
        # services/validation/src/main.py wires only (validation_repo,
        # publisher); derive the profile repo + raw Redis handle from them so
        # the queue payload can carry the profile's strategy_rules/risk_limits
        # without changing the service wiring. Explicit injection wins.
        self._profile_repo = profile_repo or ProfileRepository(validation_repo._db)
        self._redis = redis_client if redis_client is not None else publisher._redis

    async def run_hourly_scan(self, interval_seconds: int = 3600):
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await self.scan_once()
            except Exception as exc:
                logger.error(
                    "learning-loop scan failed",
                    error_type=type(exc).__name__,
                    error=repr(exc),
                )

    async def scan_once(self) -> int:
        """One scan pass. Returns the number of jobs enqueued."""
        # Fetch recent red/amber events from the last hour across all checks.
        events = []
        for check_type in ValidationCheck:
            try:
                records = await self._validation_repo.get_recent_events(
                    check_type, hours=1
                )
                for r in records:
                    row = dict(r) if not isinstance(r, dict) else r
                    if row.get("verdict", "") in ("RED", "AMBER"):
                        events.append(row)
            except Exception:
                continue

        enqueued = 0
        seen: set[tuple[str, str]] = set()
        for ev in events:
            reason = ev.get("reason") or ""
            job_type = ""
            # If drift RED -> "what if we halted"
            if "Drift RED" in reason:
                job_type = "what_if_halted"
            # If hallucination -> "backtest with sentiment zeroed"
            elif "Hallucination" in reason:
                job_type = "zero_sentiment_backtest"
            # If bias -> "backtest bias neutralised"
            elif "Bias" in reason:
                job_type = "neutral_bias_backtest"

            profile_id = ev.get("profile_id")
            if not job_type or not profile_id:
                continue

            # One job set per (profile, diagnosis) per scan — a burst of
            # identical RED events must not flood the queue.
            key = (str(profile_id), job_type)
            if key in seen:
                continue
            seen.add(key)

            enqueued += await self._enqueue_jobs(
                str(profile_id), job_type, ev.get("event_id")
            )
        return enqueued

    async def _enqueue_jobs(
        self, profile_id: str, job_type: str, source_event_id
    ) -> int:
        """Enqueue one gateway-shaped job per tracked symbol for a profile."""
        try:
            profile = await self._profile_repo.get_profile(profile_id)
        except Exception as exc:
            logger.error(
                "auto-backtest profile lookup failed",
                profile_id=profile_id,
                error=repr(exc),
            )
            return 0
        if not profile:
            logger.warning(
                "auto-backtest skipped: profile not found", profile_id=profile_id
            )
            return 0

        strategy_rules = _as_dict(profile.get("strategy_rules"))
        risk_limits = _as_dict(profile.get("risk_limits"))
        user_id = str(profile.get("user_id", ""))

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=AUTO_BACKTEST_LOOKBACK_DAYS)

        published = 0
        for symbol in settings.TRADING_SYMBOLS:
            # Backpressure — mirror the gateway's queue-depth gate.
            queue_len = await self._redis.xlen(AUTO_BACKTEST_QUEUE)
            if queue_len >= settings.BACKTEST_MAX_QUEUE_DEPTH:
                logger.warning(
                    "auto-backtest queue full; skipping remaining jobs",
                    queue_len=queue_len,
                )
                break

            job_id = f"auto-{job_type}-{uuid.uuid4().hex[:12]}"
            # Mirror of the gateway enqueue payload (routes/backtest.py) /
            # scripts/en_w2_edge_triage.py build_payload — the shape the
            # JobRunner's parse path reads.
            payload = {
                "job_id": job_id,
                "user_id": user_id,
                "symbol": symbol,
                "strategy_rules": strategy_rules,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "timeframe": AUTO_BACKTEST_TIMEFRAME,
                "slippage_pct": AUTO_BACKTEST_SLIPPAGE_PCT,
                # ALWAYS "" — see module docstring (decay-baseline guard).
                "profile_id": "",
                "risk_limits": risk_limits,
                "walk_forward": None,
                "risk_limits_grid": None,
                # Traceability extras (ignored by the JobRunner):
                "job_type": job_type,
                "source_event_id": (
                    str(source_event_id) if source_event_id is not None else None
                ),
                "source_profile_id": profile_id,
            }
            await self._redis.xadd(AUTO_BACKTEST_QUEUE, {"data": json.dumps(payload)})
            await self._redis.set(
                f"backtest:status:{job_id}",
                json.dumps({"status": "queued", "job_id": job_id, "user_id": user_id}),
                ex=3600,
            )
            logger.info(
                "auto-backtest enqueued (profile_id deliberately empty so the "
                "run can never become a decay baseline)",
                job_id=job_id,
                job_type=job_type,
                symbol=symbol,
                source_profile_id=profile_id,
            )
            published += 1
        return published
