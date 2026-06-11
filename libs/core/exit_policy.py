"""Shared position exit-decision policy — SINGLE SOURCE OF TRUTH.

This module is consumed by BOTH:

  * the live ``ExitMonitor`` (``services/pnl/src/exit_monitor.py``) — evaluated
    on every price tick against the PnL snapshot; and
  * the backtest engines (``services/backtesting/src/simulator.py`` and
    ``services/backtesting/src/vectorbt_runner.py``) — evaluated once per bar
    at the bar close.

Do NOT copy this logic anywhere else: live/sim drift in exit semantics is the
exact failure mode this module exists to prevent (TECH-DEBT-REGISTRY row 43,
locked decision #4 — backtest truth-pass).

Basis difference (deliberate, documented):
  * **Live** ``pct_return`` is the net-post-tax return computed by
    ``PnLCalculator`` (``services/pnl/src/calculator.py``) — it already
    includes entry/exit fees and the tax estimate.
  * **Sim** ``pct_return`` is the directional move of the current bar close
    off the *slipped* entry price (entry slippage included), gross of exit
    costs — exit slippage/fees are applied to the fill price after the
    decision, mirroring how the live monitor decides on the tick price before
    the close order's costs are known.

Threshold precedence (identical to live):
  1. keys explicitly present in the profile's ``risk_limits`` JSONB;
  2. otherwise the settings defaults (``DEFAULT_STOP_LOSS_PCT``,
     ``DEFAULT_TAKE_PROFIT_PCT``, ``DEFAULT_MAX_HOLDING_HOURS``).

Note the known discrepancy between ``DEFAULT_RISK_LIMITS['stop_loss_pct']``
(0.05) and ``settings.DEFAULT_STOP_LOSS_PCT`` (0.02): live behaviour is that
the settings defaults win when the profile does not explicitly set a key, and
this module preserves that exactly. Do not "fix" it here.

All financial comparisons use Decimal. Hours-as-time stays float to match the
live formula (``total_seconds() / 3600.0``) bit-for-bit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Union

from libs.config import settings
from libs.core.schemas import RiskLimitsPayload
from libs.observability import get_logger

logger = get_logger("core.exit_policy")

# Canonical close-reason strings — shared by live closes (closed_trades rows,
# OrderApprovedEvent.close_reason) and simulated trades (close_reason field).
EXIT_STOP_LOSS = "stop_loss"
EXIT_TAKE_PROFIT = "take_profit"
EXIT_TIME = "time_exit"

_ZERO = Decimal("0")


@dataclass(frozen=True)
class ExitThresholds:
    """Resolved exit thresholds for one profile (or one backtest job)."""

    stop_loss_pct: Decimal
    take_profit_pct: Decimal
    max_holding_hours: float


def thresholds_from_risk_limits(
    risk_limits: Union[dict, str, None],
) -> ExitThresholds:
    """Resolve ``ExitThresholds`` from a profile's ``risk_limits`` JSONB.

    Replicates ``ExitMonitor._get_thresholds`` parsing exactly:

      * tolerates a JSON string, a dict, or None;
      * starts from the settings defaults and overrides them ONLY for keys
        explicitly present in the raw risk_limits payload — Pydantic defaults
        on ``RiskLimitsPayload`` must NOT override the settings defaults;
      * any parse error falls back to the settings defaults (the live monitor
        catches and logs, then uses defaults — same net behaviour).
    """
    stop_loss = Decimal(str(settings.DEFAULT_STOP_LOSS_PCT))
    take_profit = Decimal(str(settings.DEFAULT_TAKE_PROFIT_PCT))
    max_hours = settings.DEFAULT_MAX_HOLDING_HOURS

    try:
        if isinstance(risk_limits, str):
            raw_dict = json.loads(risk_limits) if risk_limits else {}
            rl = RiskLimitsPayload.model_validate(raw_dict)
        elif isinstance(risk_limits, dict):
            raw_dict = risk_limits
            rl = RiskLimitsPayload.model_validate(risk_limits)
        else:
            raw_dict = {}
            rl = RiskLimitsPayload()

        if "stop_loss_pct" in raw_dict and rl.stop_loss_pct is not None:
            stop_loss = Decimal(str(rl.stop_loss_pct))
        if "take_profit_pct" in raw_dict and rl.take_profit_pct is not None:
            take_profit = Decimal(str(rl.take_profit_pct))
        if "max_holding_hours" in raw_dict and rl.max_holding_hours is not None:
            max_hours = rl.max_holding_hours
    except Exception as exc:
        # Malformed payload → settings defaults, exactly like the live path.
        # A profile silently trading on default thresholds instead of its
        # configured stop is a risk-control gap — make it visible.
        logger.warning(
            "risk_limits parse failed — falling back to settings defaults",
            error=str(exc),
        )
        return ExitThresholds(
            stop_loss_pct=Decimal(str(settings.DEFAULT_STOP_LOSS_PCT)),
            take_profit_pct=Decimal(str(settings.DEFAULT_TAKE_PROFIT_PCT)),
            max_holding_hours=settings.DEFAULT_MAX_HOLDING_HOURS,
        )

    return ExitThresholds(
        stop_loss_pct=stop_loss,
        take_profit_pct=take_profit,
        max_holding_hours=max_hours,
    )


def decide_exit(
    pct_return: Decimal,
    age_hours: float,
    thresholds: ExitThresholds,
) -> Optional[str]:
    """Evaluate the three exit conditions in live precedence order.

    Returns ``EXIT_STOP_LOSS`` / ``EXIT_TAKE_PROFIT`` / ``EXIT_TIME`` or None.

    Exact live comparisons (``ExitMonitor.check``):
      1. stop-loss:  ``pct_return < 0 and abs(pct_return) >= stop_loss_pct``
      2. take-profit: ``pct_return > 0 and pct_return >= take_profit_pct``
      3. time:        ``age_hours >= max_holding_hours``

    Callers that have no valid position age must pass ``-math.inf`` (the live
    monitor only evaluates the time condition when ``opened_at`` is set).
    """
    if pct_return < _ZERO and abs(pct_return) >= thresholds.stop_loss_pct:
        return EXIT_STOP_LOSS
    if pct_return > _ZERO and pct_return >= thresholds.take_profit_pct:
        return EXIT_TAKE_PROFIT
    if age_hours >= thresholds.max_holding_hours:
        return EXIT_TIME
    return None
