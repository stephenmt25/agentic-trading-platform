"""DecayTracker (PR7) — surfaces live-vs-backtest strategy decay and consumes the
shadow-decision flag.

For each active profile it gathers:
  - LIVE performance from closed_trades (net-of-cost, PR5): win rate, avg return.
  - BACKTEST baseline from the profile's latest backtest_results.
  - SHADOW signal: how many decisions passed the rules but were gate-blocked
    (the would-have-traded count the shadow flag records).

It feeds live + baseline to libs.core.decay.assess_decay, writes a per-profile
report to Redis, and raises an AMBER alert when a strategy has decayed. This is
the comparison/surfacing the brief scopes to PR7 — the walk-forward / survivorship
/ out-of-sample backtest overhaul (the larger 3.14 gap) is tracked separately.
"""

import asyncio
import json
from datetime import datetime, timezone

from libs.config import settings
from libs.core.decay import assess_decay
from libs.core.enums import EventType
from libs.core.schemas import AlertEvent
from libs.messaging.channels import PUBSUB_SYSTEM_ALERTS
from libs.observability import get_logger

logger = get_logger("analyst.decay")

SNAPSHOT_KEY = "analyst:decay:snapshot"


def _f(v):
    return float(v) if v is not None else None


class DecayTracker:
    def __init__(
        self,
        closed_trade_repo,
        decision_repo,
        backtest_repo,
        profile_repo,
        redis_client=None,
        pubsub=None,
    ):
        self._closed_trade_repo = closed_trade_repo
        self._decision_repo = decision_repo
        self._backtest_repo = backtest_repo
        self._profile_repo = profile_repo
        self._redis = redis_client
        self._pubsub = pubsub

    async def assess_all(self) -> list:
        window = int(settings.DECAY_WINDOW_HOURS)
        live = {
            r["profile_id"]: r
            for r in await self._closed_trade_repo.net_of_cost_by_profile(
                window_hours=window
            )
        }
        shadow = {
            r["profile_id"]: r
            for r in await self._decision_repo.shadow_summary_by_profile(
                window_hours=window
            )
        }
        profiles = await self._profile_repo.get_active_profiles()

        reports = []
        for p in profiles:
            pid = str(p.get("profile_id", ""))
            if not pid:
                continue
            lv = live.get(pid, {})
            bt = await self._backtest_repo.latest_for_profile(pid)
            assessment = assess_decay(
                live_trades=lv.get("trade_count", 0) or 0,
                live_win_rate=lv.get("win_rate"),
                live_avg_pct=lv.get("avg_pnl_pct"),
                backtest_win_rate=_f(bt.get("win_rate")) if bt else None,
                backtest_avg_return=_f(bt.get("avg_return")) if bt else None,
                min_live_trades=int(settings.DECAY_MIN_LIVE_TRADES),
                win_rate_drop=float(settings.DECAY_WIN_RATE_DROP),
                avg_factor=float(settings.DECAY_AVG_FACTOR),
            )
            sh = shadow.get(pid, {})
            report = {
                "profile_id": pid,
                "status": assessment.status,
                "decayed": assessment.decayed,
                "reasons": assessment.reasons,
                "live_win_rate": assessment.live_win_rate,
                "backtest_win_rate": assessment.backtest_win_rate,
                "live_avg_pct": assessment.live_avg_pct,
                "backtest_avg_return": assessment.backtest_avg_return,
                "live_trades": lv.get("trade_count", 0) or 0,
                "shadow_count": sh.get("shadow_count", 0) or 0,
                "shadow_share": sh.get("shadow_share"),
            }
            reports.append(report)
            if assessment.decayed:
                logger.warning(
                    "strategy_decay_detected",
                    profile_id=pid,
                    reasons=assessment.reasons,
                )
                await self._alert(pid, assessment.reasons)

        if self._redis is not None:
            try:
                await self._redis.set(SNAPSHOT_KEY, json.dumps(reports), ex=86400)
            except Exception:
                logger.warning("failed to write decay snapshot")
        return reports

    async def _alert(self, profile_id: str, reasons: list):
        if self._pubsub is None:
            return
        try:
            await self._pubsub.publish(
                PUBSUB_SYSTEM_ALERTS,
                AlertEvent(
                    event_type=EventType.ALERT_AMBER,
                    message=(
                        f"Strategy decay on profile {profile_id} — "
                        f"live underperforming backtest: {'; '.join(reasons)}"
                    ),
                    level="AMBER",
                    profile_id=profile_id,
                    timestamp_us=int(
                        datetime.now(timezone.utc).timestamp() * 1_000_000
                    ),
                    source_service="analyst.decay",
                ),
            )
        except Exception:
            logger.exception("failed to publish decay alert")

    async def run_loop(self, interval: float = None):
        interval = interval or float(settings.DECAY_TRACKER_INTERVAL_S)
        logger.info("DecayTracker loop starting", interval_s=interval)
        while True:
            try:
                reports = await self.assess_all()
                decayed = sum(1 for r in reports if r["decayed"])
                logger.info("decay_assessed", profiles=len(reports), decayed=decayed)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("decay assessment failed")
            await asyncio.sleep(interval)
