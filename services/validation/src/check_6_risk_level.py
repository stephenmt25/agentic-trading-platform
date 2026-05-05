import json
from decimal import Decimal
from .check_1_strategy import CheckResult
from libs.core.notional import profile_notional
from libs.observability import get_logger

logger = get_logger("validation.risk_level")

_ZERO = Decimal("0")


class RiskLevelRecheck:
    def __init__(self, profile_repo):
        self._profile_repo = profile_repo

    async def check(self, request) -> CheckResult:
        """
        Validates the pre-execution order against portfolio-level risk limits
        loaded from the trading profile in the database.
        """
        quantity = Decimal(str(request.payload.get("quantity", 0)))
        price = Decimal(str(request.payload.get("price", 0)))
        order_value = quantity * price if price > 0 else quantity

        # Load the profile and its risk_limits from DB
        try:
            profile = await self._profile_repo.get_profile(str(request.profile_id))
        except Exception as e:
            logger.error("Failed to load profile for risk check", error=str(e))
            profile = None

        if not profile:
            return CheckResult(passed=False, reason="Profile not found — cannot verify risk limits")

        # Parse risk_limits from the profile record
        raw_limits = profile.get("risk_limits", "{}")
        if isinstance(raw_limits, str):
            try:
                risk_limits = json.loads(raw_limits)
            except (json.JSONDecodeError, TypeError):
                risk_limits = {}
        else:
            risk_limits = raw_limits if isinstance(raw_limits, dict) else {}

        # (a) Max allocation percentage check — notional from libs.core.notional
        max_allocation_pct = Decimal(str(risk_limits.get("max_allocation_pct", 1)))
        notional = profile_notional(profile)
        if notional > 0 and order_value > 0:
            alloc_fraction = order_value / notional
            if alloc_fraction > max_allocation_pct:
                return CheckResult(
                    passed=False,
                    reason=f"Order value ${float(order_value):.2f} exceeds max allocation "
                           f"({float(max_allocation_pct)*100:.0f}% of profile budget)"
                )

        # (b) Stop-loss tolerance check
        stop_loss_pct = Decimal(str(risk_limits.get("stop_loss_pct", "0.05")))
        order_stop_loss = Decimal(str(request.payload.get("stop_loss_pct", 0)))
        if order_stop_loss > 0 and order_stop_loss > stop_loss_pct:
            return CheckResult(
                passed=False,
                reason=f"Stop-loss {float(order_stop_loss)*100:.1f}% exceeds profile limit of {float(stop_loss_pct)*100:.1f}%"
            )

        # (c) Max drawdown circuit breaker
        max_drawdown_pct = Decimal(str(risk_limits.get("max_drawdown_pct", "0.10")))
        current_drawdown = Decimal(str(request.payload.get("current_drawdown_pct", 0)))
        if current_drawdown >= max_drawdown_pct:
            return CheckResult(
                passed=False,
                reason=f"Current drawdown {float(current_drawdown)*100:.1f}% at/above max allowed {float(max_drawdown_pct)*100:.1f}%"
            )

        # (d) Hard safety cap — absolute quantity guard
        if quantity > 10_000:
            return CheckResult(
                passed=False,
                reason="Absolute quantity guard: order qty exceeds 10,000 unit hard cap"
            )

        return CheckResult(passed=True)
