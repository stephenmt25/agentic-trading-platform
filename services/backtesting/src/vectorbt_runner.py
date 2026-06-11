"""Vectorized backtesting engine using numpy.

Converts strategy rules into vectorized signal arrays for 100-1000x
faster parameter sweeps compared to the sequential TradingSimulator.
Same BacktestJob input / BacktestResult output interface.
"""

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

import numpy as np

from libs.core.exit_policy import decide_exit, thresholds_from_risk_limits

from libs.indicators import (
    ADXCalculator,
    ATRCalculator,
    BollingerCalculator,
    ChoppinessCalculator,
    HurstCalculator,
    KeltnerCalculator,
    MACDCalculator,
    OBVCalculator,
    RSICalculator,
    RVOLCalculator,
    SimpleRegimeClassifier,
    VWAPCalculator,
    ZScoreCalculator,
)
from services.strategy.src.compiler import RuleCompiler

from .simulator import (
    CLOSE_END_OF_DATA,
    BacktestJob,
    BacktestResult,
    SimulatedTrade,
    bar_age_hours,
    compute_trade_metrics,
    parse_bar_time,
    parse_preferred_regimes,
)

_D = Decimal
_ZERO = _D("0")
_ONE = _D("1")


def _compute_indicators(
    closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, volumes: np.ndarray
) -> Dict[str, np.ndarray]:
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
                job_id=job.job_id,
                total_trades=0,
                win_rate=_ZERO,
                avg_return=_ZERO,
                max_drawdown=_ZERO,
                sharpe=_ZERO,
                profit_factor=_ZERO,
            )

        # Extract OHLCV arrays
        n = len(data)
        closes = np.array([float(c["close"]) for c in data])  # float-ok: numpy interop
        highs = np.array([float(c["high"]) for c in data])  # float-ok: numpy interop
        lows = np.array([float(c["low"]) for c in data])  # float-ok: numpy interop
        volumes = np.array(
            [float(c.get("volume", 0)) for c in data]  # float-ok: numpy interop
        )
        times = [str(c.get("time", "")) for c in data]

        # Compute indicators
        indicators = _compute_indicators(closes, highs, lows, volumes)

        # Compile and evaluate rules vectorized
        compiled = RuleCompiler.compile(job.strategy_rules)
        signals = _evaluate_conditions_vectorized(
            indicators,
            compiled.conditions,
            compiled.logic,
        )

        # Row 18: regime gate. Mask the signal array to False on every bar
        # whose live rule-based regime is not in the profile's
        # preferred_regimes — same semantics as the sequential engine and
        # hot_path. Empty preferred_regimes = regime-agnostic (no masking).
        # The SimpleRegimeClassifier is fed only once ATR has primed (NaN ATR
        # bars are skipped); a None regime during its own priming leaves the
        # bar un-masked, so we never gate on missing data.
        preferred_regimes = parse_preferred_regimes(job.strategy_rules)
        if preferred_regimes:
            atr_arr = indicators["atr"]
            regime_clf = SimpleRegimeClassifier()
            for i in range(n):
                a = atr_arr[i]
                if math.isnan(a):
                    continue
                reg = regime_clf.update(float(closes[i]), float(a))  # float-ok: indicator library requires float
                if reg is not None and reg not in preferred_regimes:
                    signals[i] = False

        direction = compiled.direction.value  # "BUY" or "SELL"

        # EN-W1 exit fidelity: identical shared exit policy as the live
        # ExitMonitor and the sequential simulator. Thresholds resolved once
        # per run from the job's risk_limits (None → settings defaults).
        thresholds = thresholds_from_risk_limits(job.risk_limits)
        bar_dts = [parse_bar_time(c.get("time")) for c in data]

        # Simulate trades from the signal array. Trade mechanics (prices,
        # slippage, PnL, equity) are Decimal-exact — same as the sequential
        # engine; numpy/float stays confined to indicators and signals.
        trades: List[SimulatedTrade] = []
        equity = _ONE
        equity_curve: List[Decimal] = []
        peak_equity = _ONE
        max_drawdown = _ZERO
        in_position = False
        entry_idx = 0
        entry_price: Optional[Decimal] = None
        entry_slip = _ZERO

        for i in range(n):
            close_d = _D(str(closes[i]))

            # ------------------------------------------------------------
            # Exit check while in position — BEFORE any entry evaluation.
            # Same close-only price basis as the sequential engine: the bar
            # close is the honest bar-granularity analog of live's
            # last-trade-price tick basis. High/low are deliberately NOT
            # used for SL/TP fills (intrabar ordering of SL vs TP is
            # unknowable from OHLC). Signals while in position are IGNORED
            # — the live engine never closes a position on a signal.
            # ------------------------------------------------------------
            if in_position:
                if direction == "BUY":
                    pct_return = (close_d - entry_price) / entry_price
                else:
                    pct_return = (entry_price - close_d) / entry_price
                age_hours = bar_age_hours(bar_dts[entry_idx], bar_dts[i])
                reason = decide_exit(pct_return, age_hours, thresholds)
                if reason is not None:
                    slip = close_d * job.slippage_pct
                    exit_price = (
                        close_d - slip if direction == "BUY" else close_d + slip
                    )
                    if direction == "BUY":
                        pnl_pct = (exit_price - entry_price) / entry_price
                    else:
                        pnl_pct = (entry_price - exit_price) / entry_price
                    trades.append(
                        SimulatedTrade(
                            entry_time=times[entry_idx],
                            exit_time=times[i],
                            direction=direction,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            # Entry-side slippage in quote terms — matches the
                            # sequential engine; exit slippage is embedded in
                            # exit_price (the old slip*2 double-count belonged
                            # to the removed close+re-open semantics).
                            slippage_cost=entry_slip,
                            pnl_pct=pnl_pct,
                            close_reason=reason,
                        )
                    )
                    equity *= _ONE + pnl_pct
                    in_position = False
                    entry_price = None

            # Open on signal — only when flat (same-bar re-entry after an
            # exit is allowed, mirroring the sequential engine).
            if signals[i] and not in_position:
                entry_idx = i
                entry_slip = close_d * job.slippage_pct
                entry_price = (
                    close_d + entry_slip if direction == "BUY" else close_d - entry_slip
                )
                in_position = True

            equity_curve.append(equity)
            peak_equity = max(peak_equity, equity)
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else _ZERO
            max_drawdown = max(max_drawdown, dd)

        # Close remaining position (sim artefact — tagged distinctly).
        if in_position:
            i = n - 1
            close_d = _D(str(closes[i]))
            slip = close_d * job.slippage_pct
            exit_price = close_d - slip if direction == "BUY" else close_d + slip

            if direction == "BUY":
                pnl_pct = (exit_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - exit_price) / entry_price

            trades.append(
                SimulatedTrade(
                    entry_time=times[entry_idx],
                    exit_time=times[i],
                    direction=direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    slippage_cost=entry_slip,
                    pnl_pct=pnl_pct,
                    close_reason=CLOSE_END_OF_DATA,
                )
            )
            equity *= _ONE + pnl_pct
            equity_curve.append(equity)
            peak_equity = max(peak_equity, equity)
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else _ZERO
            max_drawdown = max(max_drawdown, dd)

        # Aggregate metrics — shared Decimal helper (same formulas as the
        # sequential engine; do not duplicate).
        metrics = compute_trade_metrics(trades)

        return BacktestResult(
            job_id=job.job_id,
            total_trades=len(trades),
            win_rate=metrics["win_rate"],
            avg_return=metrics["avg_return"],
            max_drawdown=max_drawdown,
            sharpe=metrics["sharpe"],
            profit_factor=metrics["profit_factor"],
            equity_curve=equity_curve,
            trades=trades,
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
    risk_limits: Optional[Dict[str, Any]] = None,
) -> SweepResult:
    """Run a parameter grid sweep using the vectorized engine.

    param_grid maps condition index + field to values, e.g.:
    {"0.value": [25, 30, 35]} sweeps the first condition's threshold.
    risk_limits (profile JSONB shape) applies the same exit policy to every
    combination — None → settings defaults.
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
            risk_limits=risk_limits,
        )
        result = VectorBTRunner.run(job, data)
        results.append(
            {
                "params": params,
                "total_trades": result.total_trades,
                "win_rate": result.win_rate,
                "sharpe": result.sharpe,
                "max_drawdown": result.max_drawdown,
                "profit_factor": result.profit_factor,
                "avg_return": result.avg_return,
            }
        )

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
