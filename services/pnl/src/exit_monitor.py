"""Unified position exit monitor — stop-loss, take-profit, and time-based exits.

Supersedes the single-policy StopLossMonitor with a combined check that
evaluates all three exit conditions on every price tick.

The exit DECISION logic (threshold resolution + precedence/comparisons) lives
in the shared ``libs/core/exit_policy.py`` so the live monitor and the
backtest engines cannot drift (EN-W1 backtest truth-pass). This module owns
what is live-only: the per-profile threshold cache, snapshot/tick plumbing,
logging detail, and the close routing (reduce-only requester vs legacy
DB-only closer).

Thresholds are read from the profile's risk_limits JSONB, falling back to
global defaults in settings.py.  All financial math uses Decimal.
"""

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from libs.config import settings
from libs.core.exit_policy import (
    EXIT_STOP_LOSS,
    EXIT_TAKE_PROFIT,
    ExitThresholds,
    decide_exit,
    thresholds_from_risk_limits,
)
from libs.core.models import Position
from libs.observability import get_logger
from libs.storage.repositories import ProfileRepository

from .calculator import PnLSnapshot
from .closer import PositionCloser

logger = get_logger("pnl.exit-monitor")


class ExitMonitor:
    """Checks each PnL snapshot against stop-loss, take-profit, and max-hold.

    Usage:
        monitor = ExitMonitor(closer, profile_repo)
        # On each tick after computing snapshot:
        closed, reason = await monitor.check(position, snapshot, current_price, taker_rate)
    """

    def __init__(
        self,
        closer: PositionCloser,
        profile_repo: ProfileRepository,
        close_requester=None,
    ):
        self._closer = closer
        self._profile_repo = profile_repo
        # When set (and PRAXIS_EXCHANGE_CLOSE_ENABLED), exits route through the
        # execution OMS as a reduce-only order instead of the legacy DB-only
        # close. Optional so older call sites / tests keep working.
        self._close_requester = close_requester
        self._cache: dict[str, ExitThresholds] = {}

    # ------------------------------------------------------------------
    # Threshold loading
    # ------------------------------------------------------------------

    async def _get_thresholds(self, profile_id: str) -> ExitThresholds:
        if profile_id in self._cache:
            return self._cache[profile_id]

        raw_limits = None
        try:
            profile = await self._profile_repo.get_profile(profile_id)
            if profile:
                raw_limits = profile.get("risk_limits", "{}")
        except Exception as e:
            logger.error(
                "Failed to load exit thresholds", profile_id=profile_id, error=str(e)
            )

        # Shared parsing/override semantics — see libs/core/exit_policy.py.
        # Repo failure or malformed payload → settings defaults, as before.
        thresholds = thresholds_from_risk_limits(raw_limits)
        self._cache[profile_id] = thresholds
        return thresholds

    def invalidate_cache(self, profile_id: str):
        """Call when a profile's risk_limits are updated."""
        self._cache.pop(profile_id, None)

    # ------------------------------------------------------------------
    # Core check
    # ------------------------------------------------------------------

    async def check(
        self,
        position: Position,
        snapshot: PnLSnapshot,
        current_price: Decimal,
        taker_rate: Decimal,
    ) -> tuple[bool, Optional[str]]:
        """Evaluate all exit conditions for one position.

        Returns (closed: bool, reason: str | None).
        Reason is one of: 'stop_loss', 'take_profit', 'time_exit', or None.
        """
        thresholds = await self._get_thresholds(str(position.profile_id))

        # First pass: SL/TP only (age = -inf disables the time condition).
        # The position age is computed lazily afterwards — preserves the live
        # semantics where opened_at is only touched when SL/TP didn't fire.
        age_hours = -math.inf
        reason = decide_exit(snapshot.pct_return, age_hours, thresholds)

        if reason is None and position.opened_at:
            age_hours = (
                datetime.now(timezone.utc) - position.opened_at
            ).total_seconds() / 3600.0
            reason = decide_exit(snapshot.pct_return, age_hours, thresholds)

        if reason is None:
            return False, None

        if reason == EXIT_STOP_LOSS:
            detail = {
                "loss_pct": str(abs(snapshot.pct_return)),
                "threshold": str(thresholds.stop_loss_pct),
            }
        elif reason == EXIT_TAKE_PROFIT:
            detail = {
                "gain_pct": str(snapshot.pct_return),
                "threshold": str(thresholds.take_profit_pct),
            }
        else:  # EXIT_TIME
            detail = {
                "age_hours": f"{age_hours:.1f}",
                "threshold_hours": str(thresholds.max_holding_hours),
            }

        return await self._close(
            position, current_price, taker_rate, reason=reason, detail=detail
        )

    # ------------------------------------------------------------------
    # Internal close helper
    # ------------------------------------------------------------------

    async def _close(
        self,
        position: Position,
        current_price: Decimal,
        taker_rate: Decimal,
        reason: str,
        detail: dict,
    ) -> tuple[bool, Optional[str]]:
        logger.warning(
            f"EXIT TRIGGERED: {reason.upper()}",
            position_id=str(position.position_id),
            profile_id=str(position.profile_id),
            symbol=position.symbol,
            current_price=str(current_price),
            entry_price=str(position.entry_price),
            **{k: v for k, v in detail.items()},
        )
        try:
            if self._close_requester is not None and settings.EXCHANGE_CLOSE_ENABLED:
                # Real exchange close: publish a reduce-only order and mark the
                # position PENDING_CLOSE. Whether we won the CAS or another path
                # already owns the close, this position is leaving OPEN — return
                # closed=True so the tick handler stops monitoring it. The DB
                # close is finalised later on fill confirmation.
                await self._close_requester.request_close(
                    position, current_price, close_reason=reason
                )
                return True, reason

            # Legacy synchronous DB-only fallback (PRAXIS_EXCHANGE_CLOSE_ENABLED off).
            await self._closer.close(
                position=position,
                exit_price=current_price,
                taker_rate=taker_rate,
                close_reason=reason,
            )
            return True, reason
        except Exception as e:
            logger.error(
                f"Failed to close position on {reason}",
                position_id=str(position.position_id),
                error=str(e),
            )
            return False, None
