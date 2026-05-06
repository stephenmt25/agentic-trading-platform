"""Vectorized backtesting engine using numpy.

Converts strategy rules into vectorized signal arrays for 100-1000x
faster parameter sweeps compared to the sequential TradingSimulator.
Same BacktestJob input / BacktestResult output interface.
"""

import math
import numpy as np
from decimal import Decimal
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from services.strategy.src.compiler import RuleCompiler
from libs.indicators import (
    RSICalculator, MACDCalculator, ATRCalculator,
    ADXCalculator, BollingerCalculator, OBVCalculator, ChoppinessCalculator,
    VWAPCalculator, KeltnerCalculator, RVOLCalculator, ZScoreCalculator, HurstCalculator,
)
from .simulator import BacktestJob, BacktestResult, SimulatedTrade

_D = Decimal


def _compute_indicators(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                         volumes: np.ndarray) -> Dict[str, np.ndarray]:
    """Compute all indicators incrementally and return aligned arrays.

    Each array has the same length as the input, with NaN during priming.
    """
    n = len(closes)
    rsi_arr = np.full(n, np.nan)
    macd_line_arr = np.full(n, np.nan)
    signal_line_arr = np.full(n, np.nan)
    histogram_arr = np.full(n, np.nan)
    atr_arr = np.full(n, np.nan)
    adx_arr = np.full(n, np.nan)
    bb_pct_b_arr = np.full(n, np.nan)
    bb_bandwidth_arr = np.full(n, np.nan)
    bb_upper_arr = np.full(n, np.nan)
    bb_lower_arr = np.full(n, np.nan)
    obv_arr = np.full(n, np.nan)
    chop_arr = np.full(n, np.nan)
    zscore_arr = np.full(n, np.nan)
    vwap_arr = np.full(n, np.nan)
    keltner_upper_arr = np.full(n, np.nan)
    keltner_middle_arr = np.full(n, np.nan)
    keltner_lower_arr = np.full(n, np.nan)
    rvol_arr = np.full(n, np.nan)
    hurst_arr = np.full(n, np.nan)

    rsi_calc = RSICalculator()
    macd_calc = MACDCalculator()
    atr_calc = ATRCalculator()
    adx_calc = ADXCalculator()
    bb_calc = BollingerCalculator()
    obv_calc = OBVCalculator()
    chop_calc = ChoppinessCalculator()
    zscore_calc = ZScoreCalculator()
    vwap_calc = VWAPCalculator()
    keltner_calc = KeltnerCalculator()
    rvol_calc = RVOLCalculator()
    hurst_calc = HurstCalculator()

    for i in range(n):
        c, h, l, v = closes[i], highs[i], lows[i], volumes[i]

        rv = rsi_calc.update(c)
        if rv is not None:
            rsi_arr[i] = rv

        mv = macd_calc.update(c)
        if mv is not None:
            macd_line_arr[i] = mv.macd_line
            signal_line_arr[i] = mv.signal_line
            histogram_arr[i] = mv.histogram

        av = atr_calc.update(h, l, c)
        if av is not None:
            atr_arr[i] = av

        dv = adx_calc.update(h, l, c)
        if dv is not None:
            adx_arr[i] = dv

        bv = bb_calc.update(c)
        if bv is not None:
            bb_pct_b_arr[i] = bv.pct_b
            bb_bandwidth_arr[i] = bv.bandwidth
            bb_upper_arr[i] = bv.upper
            bb_lower_arr[i] = bv.lower

        ov = obv_calc.update(c, v)
        if ov is not None:
            obv_arr[i] = ov

        cv = chop_calc.update(h, l, c)
        if cv is not None:
            chop_arr[i] = cv

        zv = zscore_calc.update(c)
        if zv is not None:
            zscore_arr[i] = zv

        wv = vwap_calc.update(c, v)
        if wv is not None:
            vwap_arr[i] = wv

        kv = keltner_calc.update(h, l, c)
        if kv is not None:
            keltner_upper_arr[i] = kv.upper
            keltner_middle_arr[i] = kv.middle
            keltner_lower_arr[i] = kv.lower

        rv2 = rvol_calc.update(v)
        if rv2 is not None:
            rvol_arr[i] = rv2

        hv = hurst_calc.update(c)
        if hv is not None:
            hurst_arr[i] = hv

    return {
        "rsi": rsi_arr,
        "macd.macd_line": macd_line_arr,
        "macd.signal_line": signal_line_arr,
        "macd.histogram": histogram_arr,
        "atr": atr_arr,
        "adx": adx_arr,
        "bb.pct_b": bb_pct_b_arr,
        "bb.bandwidth": bb_bandwidth_arr,
        "bb.upper": bb_upper_arr,
        "bb.lower": bb_lower_arr,
        "obv": obv_arr,
        "choppiness": chop_arr,
        "z_score": zscore_arr,
        "vwap": vwap_arr,
        "keltner.upper": keltner_upper_arr,
        "keltner.middle": keltner_middle_arr,
        "keltner.lower": keltner_lower_arr,
        "rvol": rvol_arr,
        "hurst": hurst_arr,
    }


def _evaluate_conditions_vectorized(
    indicators: Dict[str, np.ndarray],
    conditions: List[Dict[str, Any]],
    logic: str,
) -> np.ndarray:
    """Evaluate strategy conditions across all bars, returning a boolean signal array."""
    n = len(next(iter(indicators.values())))
    if not conditions:
        return np.zeros(n, dtype=bool)

    cond_results = []
    for cond in conditions:
        ind_key = cond["indicator"]
        op = cond["operator"]
        val = float(cond["value"])  # float-ok: numpy array comparison

        arr = indicators.get(ind_key)
        if arr is None:
            # Unknown indicator → condition is False everywhere
            cond_results.append(np.zeros(n, dtype=bool))
            continue

        # NaN positions are always False
        valid = ~np.isnan(arr)

        if op == "LT":
            result = valid & (arr < val)
        elif op == "GT":
            result = valid & (arr > val)
        elif op == "LTE":
            result = valid & (arr <= val)
        elif op == "GTE":
            result = valid & (arr >= val)
        elif op == "EQ":
            result = valid & (arr == val)
        else:
            result = np.zeros(n, dtype=bool)

        cond_results.append(result)

    if logic == "AND":
        return np.all(cond_results, axis=0)
    elif logic == "OR":
        return np.any(cond_results, axis=0)
    return np.zeros(n, dtype=bool)


class VectorBTRunner:
    """Vectorized backtesting engine — same interface as TradingSimulator."""

    @staticmethod
    def run(job: BacktestJob, data: List[Dict[str, Any]]) -> BacktestResult:
        if not data:
            return BacktestResult(
                job_id=job.job_id, total_trades=0, win_rate=0.0,
                avg_return=0.0, max_drawdown=0.0, sharpe=0.0, profit_factor=0.0,
            )

        # Extract OHLCV arrays
        n = len(data)
        closes = np.array([float(c["close"]) for c in data])  # float-ok: numpy interop
        highs = np.array([float(c["high"]) for c in data])  # float-ok: numpy interop
        lows = np.array([float(c["low"]) for c in data])  # float-ok: numpy interop
        volumes = np.array([float(c.get("volume", 0)) for c in data])  # float-ok: numpy interop
        times = [str(c.get("time", "")) for c in data]

        # Compute indicators
        indicators = _compute_indicators(closes, highs, lows, volumes)

        # Compile and evaluate rules vectorized
        compiled = RuleCompiler.compile(job.strategy_rules)
        signals = _evaluate_conditions_vectorized(
            indicators, compiled.conditions, compiled.logic,
        )
        direction = compiled.direction.value  # "BUY" or "SELL"
        slippage_f = float(job.slippage_pct)  # float-ok: numpy vectorized engine requires float

        # Simulate trades from signal array
        trades: List[SimulatedTrade] = []
        equity = 1.0
        equity_curve = []
        peak_equity = 1.0
        max_drawdown = 0.0
        in_position = False
        entry_idx = 0

        for i in range(n):
            if signals[i] and not in_position:
                # Open position
                entry_idx = i
                in_position = True
            elif signals[i] and in_position:
                # Close + re-open on signal while in position
                slip = closes[i] * slippage_f
                entry_price = closes[entry_idx] + (slip if direction == "BUY" else -slip)
                exit_price = closes[i] - (slip if direction == "BUY" else -slip)

                if direction == "BUY":
                    pnl_pct = (exit_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - exit_price) / entry_price

                trades.append(SimulatedTrade(
                    entry_time=times[entry_idx], exit_time=times[i],
                    direction=direction, entry_price=entry_price,
                    exit_price=exit_price, slippage_cost=slip * 2, pnl_pct=pnl_pct,
                ))
                equity *= (1 + pnl_pct)
                entry_idx = i  # Re-open

            equity_curve.append(equity)
            peak_equity = max(peak_equity, equity)
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
            max_drawdown = max(max_drawdown, dd)

        # Close remaining position
        if in_position:
            i = n - 1
            slip = closes[i] * slippage_f
            entry_price = closes[entry_idx] + (slip if direction == "BUY" else -slip)
            exit_price = closes[i] - (slip if direction == "BUY" else -slip)

            if direction == "BUY":
                pnl_pct = (exit_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - exit_price) / entry_price

            trades.append(SimulatedTrade(
                entry_time=times[entry_idx], exit_time=times[i],
                direction=direction, entry_price=entry_price,
                exit_price=exit_price, slippage_cost=slip * 2, pnl_pct=pnl_pct,
            ))
            equity *= (1 + pnl_pct)
            equity_curve.append(equity)

        # Aggregate metrics — compute in float (numpy context), convert to Decimal at output
        total_trades = len(trades)
        wins = [t for t in trades if t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct <= 0]
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
        avg_return = sum(t.pnl_pct for t in trades) / total_trades if total_trades > 0 else 0.0

        returns = [t.pnl_pct for t in trades]
        if len(returns) >= 2:
            mean_r = sum(returns) / len(returns)
            std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1))
            sharpe = (mean_r / std_r) * math.sqrt(252) if std_r > 0 else 0.0
        else:
            sharpe = 0.0

        gross_profit = sum(t.pnl_pct for t in wins)
        gross_loss = abs(sum(t.pnl_pct for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

        return BacktestResult(
            job_id=job.job_id,
            total_trades=total_trades,
            win_rate=_D(str(win_rate)),
            avg_return=_D(str(avg_return)),
            max_drawdown=_D(str(max_drawdown)),
            sharpe=_D(str(sharpe)),
            profit_factor=_D(str(profit_factor)) if math.isfinite(profit_factor) else _D("Infinity"),
            equity_curve=[_D(str(e)) for e in equity_curve],
            trades=[
                SimulatedTrade(
                    entry_time=t.entry_time, exit_time=t.exit_time,
                    direction=t.direction,
                    entry_price=_D(str(t.entry_price)),
                    exit_price=_D(str(t.exit_price)) if t.exit_price is not None else None,
                    slippage_cost=_D(str(t.slippage_cost)),
                    pnl_pct=_D(str(t.pnl_pct)),
                ) for t in trades
            ],
        )


@dataclass
class SweepResult:
    """Result of a parameter sweep — one BacktestResult per parameter combination."""
    job_id: str
    symbol: str
    param_results: List[Dict[str, Any]] = field(default_factory=list)


def run_sweep(
    symbol: str,
    base_rules: Dict[str, Any],
    param_grid: Dict[str, List[Any]],
    data: List[Dict[str, Any]],
    slippage_pct: Decimal = Decimal("0.001"),
) -> SweepResult:
    """Run a parameter grid sweep using the vectorized engine.

    param_grid maps condition index + field to values, e.g.:
    {"0.value": [25, 30, 35]} sweeps the first condition's threshold.
    """
    import itertools
    import uuid

    sweep_id = str(uuid.uuid4())[:8]
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = list(itertools.product(*values))

    results = []
    for combo in combos:
        # Deep-copy rules and apply parameter overrides
        rules = _deep_copy_rules(base_rules)
        params = dict(zip(keys, combo))
        for key, val in params.items():
            _set_nested(rules, key, val)

        job = BacktestJob(
            job_id=f"{sweep_id}-{len(results)}",
            symbol=symbol,
            strategy_rules=rules,
            slippage_pct=slippage_pct,
        )
        result = VectorBTRunner.run(job, data)
        results.append({
            "params": params,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "sharpe": result.sharpe,
            "max_drawdown": result.max_drawdown,
            "profit_factor": result.profit_factor,
            "avg_return": result.avg_return,
        })

    return SweepResult(job_id=sweep_id, symbol=symbol, param_results=results)


def _deep_copy_rules(rules: Dict[str, Any]) -> Dict[str, Any]:
    import json
    return json.loads(json.dumps(rules))


def _set_nested(rules: Dict[str, Any], key: str, value: Any):
    """Set a nested value in rules. Key format: 'conditions.0.value' or '0.value'."""
    parts = key.split(".")
    # Handle "0.value" as "conditions.0.value"
    if parts[0].isdigit():
        parts = ["conditions"] + parts

    obj = rules
    for part in parts[:-1]:
        if part.isdigit():
            obj = obj[int(part)]
        else:
            obj = obj[part]
    final = parts[-1]
    if final.isdigit():
        obj[int(final)] = value
    else:
        obj[final] = value
