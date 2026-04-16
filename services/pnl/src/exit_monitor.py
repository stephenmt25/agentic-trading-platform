"""Unified position exit monitor — stop-loss, take-profit, and time-based exits.

Supersedes the single-policy StopLossMonitor with a combined check that
evaluates all three exit conditions on every price tick.

Thresholds are read from the profile's risk_limits JSONB, falling back to
global defaults in settings.py.  All financial math uses Decimal.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from libs.core.models import Position
from libs.core.schemas import RiskLimitsPayload
from libs.config import settings
from libs.storage.repositories import ProfileRepository
from libs.observability import get_logger

from .calculator import PnLSnapshot
from .closer import PositionCloser

logger = get_logger("pnl.exit-monitor")

_ZERO = Decimal("0")


class _ProfileExitThresholds:
    """Cached exit thresholds for a single profile."""
    __slots__ = ("stop_loss_pct", "take_profit_pct", "max_holding_hours")

    def __init__(
        self,
        stop_loss_pct: Decimal,
        take_profit_pct: Decimal,
        max_holding_hours: float,
    ):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_holding_hours = max_holding_hours


class ExitMonitor:
    """Checks each PnL snapshot against stop-loss, take-profit, and max-hold.

    Usage:
        monitor = ExitMonitor(closer, profile_repo)
        # On each tick after computing snapshot:
        closed, reason = await monitor.check(position, snapshot, current_price, taker_rate)
    """

    def __init__(self, closer: PositionCloser, profile_repo: ProfileRepository):
        self._closer = closer
        self._profile_repo = profile_repo
        self._cache: dict[str, _ProfileExitThresholds] = {}

    # ------------------------------------------------------------------
    # Threshold loading
    # ------------------------------------------------------------------

    async def _get_thresholds(self, profile_id: str) -> _ProfileExitThresholds:
        if profile_id in self._cache:
            return self._cache[profile_id]

        # Defaults from settings.py
        stop_loss = Decimal(str(settings.DEFAULT_STOP_LOSS_PCT))
        take_profit = Decimal(str(settings.DEFAULT_TAKE_PROFIT_PCT))
        max_hours = settings.DEFAULT_MAX_HOLDING_HOURS

        try:
            profile = await self._profile_repo.get_profile(profile_id)
            if profile:
                raw_limits = profile.get("risk_limits", "{}")
                if isinstance(raw_limits, str):
                    import json as _json
                    raw_dict = _json.loads(raw_limits) if raw_limits else {}
                    rl = RiskLimitsPayload.model_validate(raw_dict)
                elif isinstance(raw_limits, dict):
                    raw_dict = raw_limits
                    rl = RiskLimitsPayload.model_validate(raw_limits)
                else:
                    raw_dict = {}
                    rl = RiskLimitsPayload()

                # Only override settings defaults for keys explicitly stored
                # in the profile JSONB — Pydantic defaults must NOT override.
                if "stop_loss_pct" in raw_dict and rl.stop_loss_pct is not None:
                    stop_loss = Decimal(str(rl.stop_loss_pct))
                if "take_profit_pct" in raw_dict and rl.take_profit_pct is not None:
                    take_profit = Decimal(str(rl.take_profit_pct))
                if "max_holding_hours" in raw_dict and rl.max_holding_hours is not None:
                    max_hours = rl.max_holding_hours
        except Exception as e:
            logger.error("Failed to load exit thresholds", profile_id=profile_id, error=str(e))

        thresholds = _ProfileExitThresholds(stop_loss, take_profit, max_hours)
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

        # --- 1. Stop-loss (negative return exceeds threshold) ---
        if snapshot.pct_return < _ZERO:
            loss_pct = abs(snapshot.pct_return)
            if loss_pct >= thresholds.stop_loss_pct:
                return await self._close(
                    position, current_price, taker_rate,
                    reason="stop_loss",
                    detail={"loss_pct": str(loss_pct), "threshold": str(thresholds.stop_loss_pct)},
                )

        # --- 2. Take-profit (positive return exceeds threshold) ---
        if snapshot.pct_return > _ZERO:
            if snapshot.pct_return >= thresholds.take_profit_pct:
                return await self._close(
                    position, current_price, taker_rate,
                    reason="take_profit",
                    detail={"gain_pct": str(snapshot.pct_return), "threshold": str(thresholds.take_profit_pct)},
                )

        # --- 3. Time-based exit (position held too long) ---
        if position.opened_at:
            age_hours = (datetime.now(timezone.utc) - position.opened_at).total_seconds() / 3600.0
            if age_hours >= thresholds.max_holding_hours:
                return await self._close(
                    position, current_price, taker_rate,
                    reason="time_exit",
                    detail={"age_hours": f"{age_hours:.1f}", "threshold_hours": str(thresholds.max_holding_hours)},
                )

        return False, None

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
