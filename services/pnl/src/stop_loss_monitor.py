"""Stop-loss enforcement for open positions.

Monitors unrealized PnL on every price tick and triggers a position close
when the loss exceeds the profile's stop_loss_pct threshold.

Defect D-9 fix: risk_limits.stop_loss_pct was defined in the schema and
validated at order time, but never enforced against open positions.
"""

import json
from decimal import Decimal
from typing import Optional

from libs.core.models import Position
from libs.core.schemas import RiskLimitsPayload
from libs.storage.repositories import ProfileRepository
from libs.observability import get_logger

from .calculator import PnLSnapshot
from .closer import PositionCloser

logger = get_logger("pnl.stop-loss")

_ZERO = Decimal("0")
_DEFAULT_STOP_LOSS = Decimal("0.05")  # 5% default if not set


class StopLossMonitor:
    """Checks each PnL snapshot against the profile's stop-loss threshold.

    Usage:
        monitor = StopLossMonitor(closer, profile_repo)
        # On each tick after computing snapshot:
        closed = await monitor.check(position, snapshot, current_price, taker_rate)
    """

    def __init__(self, closer: PositionCloser, profile_repo: ProfileRepository):
        self._closer = closer
        self._profile_repo = profile_repo
        # Cache stop-loss thresholds per profile to avoid DB lookups on every tick
        self._stop_loss_cache: dict[str, Decimal] = {}

    async def _get_stop_loss_pct(self, profile_id: str) -> Decimal:
        """Load and cache the stop-loss percentage for a profile."""
        if profile_id in self._stop_loss_cache:
            return self._stop_loss_cache[profile_id]

        stop_loss = _DEFAULT_STOP_LOSS
        try:
            profile = await self._profile_repo.get_profile(profile_id)
            if profile:
                raw_limits = profile.get("risk_limits", "{}")
                if isinstance(raw_limits, str):
                    risk_limits = RiskLimitsPayload.model_validate_json(raw_limits)
                elif isinstance(raw_limits, dict):
                    risk_limits = RiskLimitsPayload.model_validate(raw_limits)
                else:
                    risk_limits = RiskLimitsPayload()
                stop_loss = Decimal(str(risk_limits.stop_loss_pct))
        except Exception as e:
            logger.error("Failed to load stop-loss for profile", profile_id=profile_id, error=str(e))

        self._stop_loss_cache[profile_id] = stop_loss
        return stop_loss

    def invalidate_cache(self, profile_id: str):
        """Call when a profile's risk_limits are updated."""
        self._stop_loss_cache.pop(profile_id, None)

    async def check(
        self,
        position: Position,
        snapshot: PnLSnapshot,
        current_price: Decimal,
        taker_rate: Decimal,
    ) -> bool:
        """Check if the position has breached its stop-loss.

        Returns True if the position was closed, False otherwise.
        """
        # Only trigger on losses (negative pct_return)
        if snapshot.pct_return >= _ZERO:
            return False

        stop_loss_pct = await self._get_stop_loss_pct(str(position.profile_id))
        loss_pct = abs(snapshot.pct_return)

        if loss_pct < stop_loss_pct:
            return False

        # Stop-loss triggered — close the position
        logger.warning(
            "STOP-LOSS TRIGGERED",
            position_id=str(position.position_id),
            profile_id=str(position.profile_id),
            symbol=position.symbol,
            loss_pct=str(loss_pct),  # float-ok: structlog serialization
            stop_loss_pct=str(stop_loss_pct),  # float-ok: structlog serialization
            current_price=str(current_price),  # float-ok: structlog serialization
            entry_price=str(position.entry_price),  # float-ok: structlog serialization
        )

        try:
            await self._closer.close(
                position=position,
                exit_price=current_price,
                taker_rate=taker_rate,
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to close position on stop-loss trigger",
                position_id=str(position.position_id),
                error=str(e),
            )
            return False
