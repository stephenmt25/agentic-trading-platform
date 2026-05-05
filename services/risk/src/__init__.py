"""Risk Service — basic risk limit checking for pre-trade validation.

Provides position size limits, concentration limits, and portfolio-level guards.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Any, Optional
from libs.core.notional import profile_notional
from libs.observability import get_logger

logger = get_logger("risk")


@dataclass
class RiskCheckResult:
    allowed: bool
    reason: Optional[str] = None


class RiskService:
    """Stateless risk limit checker. Designed to be called synchronously
    from the validation service or executor before order placement."""

    # Hard system-wide limits (defence in depth — independent of profile config)
    MAX_SINGLE_ORDER_USD = Decimal("50000")
    MAX_POSITION_CONCENTRATION_PCT = Decimal("0.25")  # 25% of portfolio in one asset
    MAX_OPEN_POSITIONS_PER_PROFILE = 50

    def __init__(self, profile_repo=None, position_repo=None, redis_client=None):
        self._profile_repo = profile_repo
        self._position_repo = position_repo
        self._redis = redis_client

    async def check_order(self, profile_id: str, symbol: str,
                          quantity: Decimal, price: Decimal,
                          side: str = "BUY") -> RiskCheckResult:
        """Run all risk checks against a proposed order. Returns RiskCheckResult."""
        quantity = Decimal(str(quantity))
        price = Decimal(str(price))

        order_value = quantity * price if price > 0 else Decimal("0")

        # 1. Hard cap on single order notional
        if order_value > self.MAX_SINGLE_ORDER_USD:
            return RiskCheckResult(
                allowed=False,
                reason=f"Order value ${order_value:,.2f} exceeds system-wide cap of ${self.MAX_SINGLE_ORDER_USD:,.2f}"
            )

        # 2. Load profile risk limits from DB
        risk_limits = {}
        portfolio_value = Decimal("0")
        if self._profile_repo:
            try:
                profile = await self._profile_repo.get_profile(profile_id)
                if profile:
                    raw = profile.get("risk_limits", "{}")
                    risk_limits = json.loads(raw) if isinstance(raw, str) else (raw or {})
                    portfolio_value = profile_notional(profile)
            except Exception as e:
                logger.error("Failed to load profile for risk check", error=str(e))

        # 3. Profile-specific max allocation per trade
        max_alloc_pct = Decimal(str(risk_limits.get("max_allocation_pct", 1.0)))
        if portfolio_value > 0 and order_value > 0:
            alloc_pct = order_value / portfolio_value
            if alloc_pct > max_alloc_pct:
                return RiskCheckResult(
                    allowed=False,
                    reason=f"Order allocation {alloc_pct*100:.1f}% exceeds profile limit {max_alloc_pct*100:.1f}%"
                )

        # 4. Concentration limit — check existing positions for same symbol
        if self._position_repo:
            try:
                open_positions = await self._position_repo.get_open_positions(profile_id)

                # Total open position count
                if len(open_positions) >= self.MAX_OPEN_POSITIONS_PER_PROFILE:
                    return RiskCheckResult(
                        allowed=False,
                        reason=f"Open position count ({len(open_positions)}) at system limit ({self.MAX_OPEN_POSITIONS_PER_PROFILE})"
                    )

                # Symbol concentration
                if portfolio_value > 0:
                    symbol_exposure = sum(
                        (Decimal(str(p.get("quantity", 0) if isinstance(p, dict) else getattr(p, "quantity", 0)))
                        * Decimal(str(p.get("entry_price", 0) if isinstance(p, dict) else getattr(p, "entry_price", 0))))
                        for p in open_positions
                        if (p.get("symbol") if isinstance(p, dict) else getattr(p, "symbol", "")) == symbol
                    )
                    new_exposure = symbol_exposure + order_value
                    concentration = new_exposure / portfolio_value
                    if concentration > self.MAX_POSITION_CONCENTRATION_PCT:
                        return RiskCheckResult(
                            allowed=False,
                            reason=f"Concentration in {symbol} would be {concentration*100:.1f}%, "
                                   f"exceeding limit of {self.MAX_POSITION_CONCENTRATION_PCT*100:.0f}%"
                        )
            except Exception as e:
                logger.error("Failed to check positions for concentration limit", error=str(e))

        # 5. Circuit breaker — check daily loss from Redis
        if self._redis:
            try:
                halt_key = f"halt:{profile_id}"
                halt_reason = await self._redis.get(halt_key)
                if halt_reason:
                    return RiskCheckResult(
                        allowed=False,
                        reason=f"Trading halted: {halt_reason.decode() if isinstance(halt_reason, bytes) else halt_reason}"
                    )
            except Exception as e:
                logger.error("Failed to check halt status in Redis", error=str(e))

        return RiskCheckResult(allowed=True)
