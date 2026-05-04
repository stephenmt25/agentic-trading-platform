"""Gate efficacy computation (Track D.PR2 — MVP).

Pure-function core: given a list of decisions and a candle lookup, compute
"of the decisions blocked by gate G, what fraction would have been
profitable had they passed?" This is the highest-leverage Insight Engine
metric and the one the partner dialogue specifically calls out.

The worker (services/analyst/src/insight_engine.py) handles persistence
and scheduling; the math lives here so it stays unit-testable without a
running database.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence

from libs.observability import get_logger

logger = get_logger("analyst.gate_efficacy")

WINNING_OUTCOMES = ("APPROVED",)
DEFAULT_LOOKAHEAD_BARS = 60
DEFAULT_TIMEFRAME = "1m"
MIN_SAMPLE_SIZE = 30


@dataclass
class SimulatedExit:
    """Result of replaying a decision through future candles using a
    profile's stop-loss / take-profit / max-holding rules."""

    pnl_pct: float
    is_win: bool
    bars_held: int
    reason: str  # "take_profit" | "stop_loss" | "time_exit" | "no_data"


@dataclass
class GateEfficacyReport:
    profile_id: str
    symbol: str
    gate_name: str
    window_start: datetime
    window_end: datetime
    blocked_count: int
    passed_count: int
    sample_size_blocked: int
    sample_size_passed: int
    blocked_would_be_win_rate: Optional[float]
    blocked_would_be_pnl_pct: Optional[float]
    passed_realized_win_rate: Optional[float]
    passed_realized_pnl_pct: Optional[float]
    confidence_band: Optional[float]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _decision_side(decision: Dict[str, Any]) -> str:
    """Best-effort extraction of BUY/SELL from a trade_decisions row.

    The decision shape varies (long-only legacy → both-legs profiles, C.1).
    We look at strategy.direction first, then profile_rules.direction,
    defaulting to BUY when nothing matches — gate efficacy of an
    accidentally-flipped decision is still informative on the demo profile,
    which is long-only. Replace with the explicit signal when later
    iterations populate ``strategy.signal_direction``.
    """
    strat = decision.get("strategy") or {}
    if isinstance(strat, str):
        try:
            import json
            strat = json.loads(strat)
        except Exception:
            strat = {}
    direction = (strat.get("direction") or "").upper()
    if direction in ("BUY", "SELL"):
        return direction
    rules = decision.get("profile_rules") or {}
    if isinstance(rules, str):
        try:
            import json
            rules = json.loads(rules)
        except Exception:
            rules = {}
    return (rules.get("direction") or "BUY").upper()


def simulate_exit(
    side: str,
    entry_price: float,
    candles: Sequence[Dict[str, Any]],
    stop_loss_pct: float,
    take_profit_pct: float,
    max_bars: int,
) -> SimulatedExit:
    """Walk forward through ``candles`` and return the simulated outcome.

    Convention:
      - BUY: stop hits when low <= entry * (1 - stop_loss_pct);
             target hits when high >= entry * (1 + take_profit_pct).
      - SELL: mirror.
      - When both stop and target straddle a single bar, we conservatively
        assume the stop was hit first (worst-case PnL). This matches the
        backtesting service's defensive default.
      - max_bars cap → "time_exit" at the close of bar ``max_bars``.

    All math is float — historical OHLCV is float64 in the candles dict;
    the report column itself is NUMERIC(10,4) and conversion happens at
    persistence time. (Reports are descriptive metrics, not order
    quantities, so the Decimal contract from CLAUDE.md §2A doesn't apply.)
    """
    if not candles or entry_price <= 0:
        return SimulatedExit(pnl_pct=0.0, is_win=False, bars_held=0, reason="no_data")

    side = side.upper()
    capped = list(candles[:max_bars])

    if side == "BUY":
        stop_price = entry_price * (1.0 - stop_loss_pct)
        target_price = entry_price * (1.0 + take_profit_pct)
        for i, c in enumerate(capped, start=1):
            high = _to_float(c.get("high"))
            low = _to_float(c.get("low"))
            if low <= stop_price:
                return SimulatedExit(pnl_pct=-stop_loss_pct, is_win=False, bars_held=i, reason="stop_loss")
            if high >= target_price:
                return SimulatedExit(pnl_pct=take_profit_pct, is_win=True, bars_held=i, reason="take_profit")
        last_close = _to_float(capped[-1].get("close")) if capped else entry_price
        pnl = (last_close - entry_price) / entry_price if entry_price else 0.0
        return SimulatedExit(
            pnl_pct=pnl,
            is_win=pnl > 0.0,
            bars_held=len(capped),
            reason="time_exit",
        )
    else:  # SELL
        stop_price = entry_price * (1.0 + stop_loss_pct)
        target_price = entry_price * (1.0 - take_profit_pct)
        for i, c in enumerate(capped, start=1):
            high = _to_float(c.get("high"))
            low = _to_float(c.get("low"))
            if high >= stop_price:
                return SimulatedExit(pnl_pct=-stop_loss_pct, is_win=False, bars_held=i, reason="stop_loss")
            if low <= target_price:
                return SimulatedExit(pnl_pct=take_profit_pct, is_win=True, bars_held=i, reason="take_profit")
        last_close = _to_float(capped[-1].get("close")) if capped else entry_price
        pnl = (entry_price - last_close) / entry_price if entry_price else 0.0
        return SimulatedExit(
            pnl_pct=pnl,
            is_win=pnl > 0.0,
            bars_held=len(capped),
            reason="time_exit",
        )


def _classify_block_gate(decision: Dict[str, Any]) -> Optional[str]:
    """Map a decision row to the gate that blocked it (or None for APPROVED).

    BLOCKED_<X> outcomes encode the gate directly. We strip the prefix and
    lowercase so the gate names match the keys used in the gates JSONB blob
    (abstention, regime, regime_mismatch, circuit_breaker, hitl, risk,
    blacklist, validation).
    """
    outcome = (decision.get("outcome") or "").upper()
    if not outcome.startswith("BLOCKED_"):
        return None
    return outcome[len("BLOCKED_"):].lower() or None


def _bootstrap_ci(values: Sequence[float], n_iter: int = 200, seed: int = 42) -> Optional[float]:
    """Return the half-width of a 95% bootstrap confidence interval on the mean.

    Returns None when the sample is too small for a meaningful estimate;
    that NULL surfaces in the dashboard and tells the partner not to
    over-interpret the signal. n_iter=200 keeps the per-report cost
    bounded — the reports are 6-hourly, not real-time.
    """
    if not values or len(values) < 5:
        return None
    import random

    rng = random.Random(seed)
    n = len(values)
    means: List[float] = []
    for _ in range(n_iter):
        sample = [values[rng.randrange(0, n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * n_iter)]
    hi = means[int(0.975 * n_iter) - 1]
    return (hi - lo) / 2.0


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def compute_gate_report(
    profile_id: str,
    symbol: str,
    gate_name: str,
    window_start: datetime,
    window_end: datetime,
    decisions: Iterable[Dict[str, Any]],
    candles_after,
    risk_limits: Dict[str, Any],
    *,
    lookahead_bars: int = DEFAULT_LOOKAHEAD_BARS,
    min_sample: int = MIN_SAMPLE_SIZE,
) -> GateEfficacyReport:
    """Build one report row from raw decisions + a candle-lookup callable.

    ``candles_after(decision_created_at) -> List[candle]`` should return up to
    ``lookahead_bars`` future OHLCV bars. The caller is responsible for
    fetching them via the MarketDataRepository — we keep this function pure
    so it can be unit-tested with synthetic data.

    Sample-size handling: when fewer than ``min_sample`` blocked or passed
    rows are available, the corresponding win-rate / PnL fields return
    None (not 0.0). NULL is the honest signal that the metric is
    untrustworthy at this volume.
    """
    stop_loss_pct = _to_float(risk_limits.get("stop_loss_pct"))
    take_profit_pct = _to_float(risk_limits.get("take_profit_pct"))
    if stop_loss_pct <= 0 or take_profit_pct <= 0:
        # Degenerate risk_limits — make the report visible but don't simulate.
        logger.warning(
            "risk_limits missing stop_loss / take_profit",
            profile_id=profile_id,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )

    blocked_pnls: List[float] = []
    blocked_wins = 0
    passed_pnls: List[float] = []
    passed_wins = 0
    blocked_count = 0
    passed_count = 0

    for d in decisions:
        outcome = (d.get("outcome") or "").upper()
        if outcome == "APPROVED":
            passed_count += 1
        elif _classify_block_gate(d) == gate_name.lower():
            blocked_count += 1
        else:
            continue

        entry = _to_float(d.get("input_price"))
        if entry <= 0 or stop_loss_pct <= 0 or take_profit_pct <= 0:
            continue
        future = candles_after(d.get("created_at"))
        if not future:
            continue
        sim = simulate_exit(
            side=_decision_side(d),
            entry_price=entry,
            candles=future,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_bars=lookahead_bars,
        )
        if sim.reason == "no_data":
            continue
        if outcome == "APPROVED":
            passed_pnls.append(sim.pnl_pct)
            if sim.is_win:
                passed_wins += 1
        else:
            blocked_pnls.append(sim.pnl_pct)
            if sim.is_win:
                blocked_wins += 1

    def _summary(samples: List[float], wins: int) -> tuple[Optional[float], Optional[float]]:
        n = len(samples)
        if n < min_sample:
            return None, None
        return wins / n, sum(samples) / n

    blocked_wr, blocked_pnl_pct = _summary(blocked_pnls, blocked_wins)
    passed_wr, passed_pnl_pct = _summary(passed_pnls, passed_wins)

    if blocked_pnl_pct is not None and passed_pnl_pct is not None:
        diffs = [b - p for b, p in zip(blocked_pnls[: min(len(blocked_pnls), len(passed_pnls))],
                                        passed_pnls[: min(len(blocked_pnls), len(passed_pnls))])]
        confidence_band = _bootstrap_ci(diffs)
    else:
        confidence_band = None

    return GateEfficacyReport(
        profile_id=str(profile_id),
        symbol=symbol,
        gate_name=gate_name,
        window_start=window_start if window_start.tzinfo else window_start.replace(tzinfo=timezone.utc),
        window_end=window_end if window_end.tzinfo else window_end.replace(tzinfo=timezone.utc),
        blocked_count=blocked_count,
        passed_count=passed_count,
        sample_size_blocked=len(blocked_pnls),
        sample_size_passed=len(passed_pnls),
        blocked_would_be_win_rate=blocked_wr,
        blocked_would_be_pnl_pct=blocked_pnl_pct,
        passed_realized_win_rate=passed_wr,
        passed_realized_pnl_pct=passed_pnl_pct,
        confidence_band=confidence_band,
    )


def discover_gates_in_window(decisions: Iterable[Dict[str, Any]]) -> List[str]:
    """Return the distinct gate names present in a decision window.

    Used by the orchestrator to avoid producing zero-row reports for gates
    that had no activity. APPROVED rows are excluded (they don't identify
    a gate).
    """
    names: set[str] = set()
    for d in decisions:
        gate = _classify_block_gate(d)
        if gate:
            names.add(gate)
    return sorted(names)
