"""Tests for Phase 6: VectorBT Backtesting Engine.

Tests the vectorized runner produces valid results, matches sequential
simulator on basic cases, and parameter sweep works correctly.
"""

import math
from datetime import datetime, timedelta
from decimal import Decimal

from services.backtesting.src.simulator import (
    CLOSE_END_OF_DATA,
    BacktestJob,
    BacktestResult,
    TradingSimulator,
)
from services.backtesting.src.vectorbt_runner import (
    VectorBTRunner,
    _compute_indicators,
    _evaluate_conditions_vectorized,
    run_sweep,
)

# ---------------------------------------------------------------------------
# Test data generation
# ---------------------------------------------------------------------------


def _make_candles(n=100, base_price=100.0, trend=0.1):
    """Generate synthetic candle data with a slight uptrend."""
    candles = []
    price = base_price
    for i in range(n):
        price += trend * (1 if i % 3 != 0 else -0.5)
        candles.append(
            {
                "time": f"2024-01-01T00:{i // 60:02d}:{i % 60:02d}",
                "open": price - 0.5,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": 1000.0 + i * 10,
            }
        )
    return candles


def _make_job(rules=None, slippage=Decimal("0.001")):
    if rules is None:
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
    return BacktestJob(
        job_id="test-job",
        symbol="BTC/USDT",
        strategy_rules=rules,
        slippage_pct=slippage,
    )


# ---------------------------------------------------------------------------
# Indicator computation
# ---------------------------------------------------------------------------


class TestComputeIndicators:
    def test_returns_all_indicator_arrays(self):
        candles = _make_candles(50)
        import numpy as np

        closes = np.array([c["close"] for c in candles])
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])
        volumes = np.array([c["volume"] for c in candles])

        inds = _compute_indicators(closes, highs, lows, volumes)

        expected_keys = [
            "rsi",
            "macd.macd_line",
            "atr",
            "adx",
            "bb.pct_b",
            "obv",
            "choppiness",
            "z_score",
            "vwap",
            "keltner.upper",
            "keltner.middle",
            "keltner.lower",
            "rvol",
            "hurst",
        ]
        for key in expected_keys:
            assert key in inds
            assert len(inds[key]) == 50

    def test_c2_indicators_prime_with_values(self):
        """C.2 indicators (z_score, vwap, keltner, rvol, hurst) must populate values
        after their priming windows — otherwise the Mean Reversion template silently
        produces zero trades on the vectorbt engine."""
        import numpy as np

        candles = _make_candles(300)
        closes = np.array([c["close"] for c in candles])
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])
        volumes = np.array([c["volume"] for c in candles])

        inds = _compute_indicators(closes, highs, lows, volumes)

        for key in ("z_score", "vwap", "keltner.upper", "rvol", "hurst"):
            non_nan = [v for v in inds[key] if not math.isnan(v)]
            assert len(non_nan) > 0, f"{key} produced no values across 300 bars"

    def test_rsi_primes_after_period(self):
        import numpy as np

        candles = _make_candles(30)
        closes = np.array([c["close"] for c in candles])
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])
        volumes = np.array([c["volume"] for c in candles])

        inds = _compute_indicators(closes, highs, lows, volumes)
        rsi = inds["rsi"]

        # First 14 bars should be NaN (priming)
        assert all(math.isnan(rsi[i]) for i in range(14))
        # After priming, should have values
        non_nan = [v for v in rsi[14:] if not math.isnan(v)]
        assert len(non_nan) > 0


# ---------------------------------------------------------------------------
# Vectorized condition evaluation
# ---------------------------------------------------------------------------


class TestEvaluateConditions:
    def test_simple_lt_condition(self):
        import numpy as np

        indicators = {"rsi": np.array([25.0, 35.0, 28.0, 50.0, 29.0])}
        conditions = [{"indicator": "rsi", "operator": "LT", "value": 30}]

        result = _evaluate_conditions_vectorized(indicators, conditions, "AND")
        assert list(result) == [True, False, True, False, True]

    def test_and_logic(self):
        import numpy as np

        indicators = {
            "rsi": np.array([25.0, 35.0, 28.0]),
            "atr": np.array([10.0, 5.0, 8.0]),
        }
        conditions = [
            {"indicator": "rsi", "operator": "LT", "value": 30},
            {"indicator": "atr", "operator": "GT", "value": 7},
        ]
        result = _evaluate_conditions_vectorized(indicators, conditions, "AND")
        # rsi<30: [T, F, T], atr>7: [T, F, T] → AND: [T, F, T]
        assert list(result) == [True, False, True]

    def test_or_logic(self):
        import numpy as np

        indicators = {
            "rsi": np.array([25.0, 35.0, 28.0]),
            "atr": np.array([10.0, 5.0, 3.0]),
        }
        conditions = [
            {"indicator": "rsi", "operator": "LT", "value": 30},
            {"indicator": "atr", "operator": "GT", "value": 7},
        ]
        result = _evaluate_conditions_vectorized(indicators, conditions, "OR")
        # rsi<30: [T, F, T], atr>7: [T, F, F] → OR: [T, F, T]
        assert list(result) == [True, False, True]

    def test_nan_treated_as_false(self):
        import numpy as np

        indicators = {"rsi": np.array([float("nan"), 25.0, float("nan")])}
        conditions = [{"indicator": "rsi", "operator": "LT", "value": 30}]
        result = _evaluate_conditions_vectorized(indicators, conditions, "AND")
        assert list(result) == [False, True, False]

    def test_unknown_indicator_all_false(self):
        import numpy as np

        indicators = {"rsi": np.array([25.0, 35.0])}
        conditions = [{"indicator": "nonexistent", "operator": "LT", "value": 30}]
        result = _evaluate_conditions_vectorized(indicators, conditions, "AND")
        assert list(result) == [False, False]


# ---------------------------------------------------------------------------
# VectorBT Runner
# ---------------------------------------------------------------------------


class TestVectorBTRunner:
    def test_empty_data(self):
        result = VectorBTRunner.run(_make_job(), [])
        assert result.total_trades == 0
        assert result.job_id == "test-job"

    def test_produces_valid_result(self):
        candles = _make_candles(200)
        result = VectorBTRunner.run(_make_job(), candles)

        assert isinstance(result, BacktestResult)
        assert result.job_id == "test-job"
        assert 0.0 <= result.win_rate <= 1.0
        assert 0.0 <= result.max_drawdown <= 1.0
        assert len(result.equity_curve) > 0

    def test_equity_curve_starts_at_one(self):
        candles = _make_candles(200)
        result = VectorBTRunner.run(_make_job(), candles)
        assert result.equity_curve[0] == 1.0

    def test_trades_have_valid_structure(self):
        # Use a strategy that will trigger (RSI < 40 is easy to hit)
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 40}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        candles = _make_candles(200)
        result = VectorBTRunner.run(_make_job(rules), candles)

        for t in result.trades:
            assert t.direction in ("BUY", "SELL")
            assert t.entry_price > 0
            assert t.exit_price is not None

    def test_slippage_applied(self):
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 40}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        candles = _make_candles(200)

        result_no_slip = VectorBTRunner.run(
            _make_job(rules, slippage=Decimal("0")), candles
        )
        result_with_slip = VectorBTRunner.run(
            _make_job(rules, slippage=Decimal("0.01")), candles
        )

        if result_no_slip.total_trades > 0 and result_with_slip.total_trades > 0:
            # Slippage should reduce returns
            assert result_with_slip.avg_return <= result_no_slip.avg_return


# ---------------------------------------------------------------------------
# Cross-engine consistency
# ---------------------------------------------------------------------------


class TestCrossEngineConsistency:
    def test_both_engines_produce_trades_on_same_data(self):
        """Both engines should produce trades from the same strategy and data."""
        import math

        # Create oscillating data that will trigger RSI dips below 35
        candles = []
        for i in range(200):
            price = 100 + 10 * math.sin(i * 0.15)
            candles.append(
                {
                    "time": f"2024-01-01T00:{i // 60:02d}:{i % 60:02d}",
                    "open": price - 0.3,
                    "high": price + 1.0,
                    "low": price - 1.0,
                    "close": price,
                    "volume": 1000.0,
                }
            )

        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 35}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        job = _make_job(rules)

        seq_result = TradingSimulator.run(job, candles)
        vec_result = VectorBTRunner.run(job, candles)

        # Both should produce at least some trades on oscillating data
        assert seq_result.total_trades > 0
        assert vec_result.total_trades > 0

    def test_empty_data_matches(self):
        seq = TradingSimulator.run(_make_job(), [])
        vec = VectorBTRunner.run(_make_job(), [])
        assert seq.total_trades == vec.total_trades == 0


# ---------------------------------------------------------------------------
# Parameter sweep
# ---------------------------------------------------------------------------


class TestParameterSweep:
    def test_sweep_produces_results(self):
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        candles = _make_candles(200)

        result = run_sweep(
            symbol="BTC/USDT",
            base_rules=rules,
            param_grid={"0.value": [25, 30, 35, 40]},
            data=candles,
        )

        assert len(result.param_results) == 4
        assert result.symbol == "BTC/USDT"

    def test_sweep_varies_results(self):
        """Different threshold values should produce different trade counts."""
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        candles = _make_candles(200)

        result = run_sweep(
            symbol="BTC/USDT",
            base_rules=rules,
            param_grid={"0.value": [10, 50]},  # Very tight vs very loose threshold
            data=candles,
        )

        trades_10 = result.param_results[0]["total_trades"]
        trades_50 = result.param_results[1]["total_trades"]
        # Looser threshold should produce >= trades
        assert trades_50 >= trades_10

    def test_sweep_result_structure(self):
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        candles = _make_candles(100)

        result = run_sweep(
            symbol="ETH/USDT",
            base_rules=rules,
            param_grid={"0.value": [30]},
            data=candles,
        )

        entry = result.param_results[0]
        assert "params" in entry
        assert "total_trades" in entry
        assert "win_rate" in entry
        assert "sharpe" in entry
        assert "max_drawdown" in entry
        assert "profit_factor" in entry

    def test_multi_param_sweep(self):
        """Sweep over two parameters produces cartesian product."""
        rules = {
            "conditions": [
                {"indicator": "rsi", "operator": "LT", "value": 30},
                {"indicator": "atr", "operator": "GT", "value": 1.0},
            ],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        candles = _make_candles(200)

        result = run_sweep(
            symbol="BTC/USDT",
            base_rules=rules,
            param_grid={"0.value": [25, 30, 35], "1.value": [0.5, 1.0]},
            data=candles,
        )

        # 3 x 2 = 6 combinations
        assert len(result.param_results) == 6


# ---------------------------------------------------------------------------
# EN-W1 — exit fidelity on the vectorized engine
# ---------------------------------------------------------------------------

_WIDE_LIMITS = {
    "stop_loss_pct": 0.99,
    # take_profit_pct=1.0 (+100%) is the RiskLimitsPayload le=1 boundary and is
    # still unreachable for these fixtures (mirrors test_backtesting.py).
    "take_profit_pct": 1.0,
    "max_holding_hours": 1e9,
}

_LIVE_LIKE_LIMITS = {
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.015,
    "max_holding_hours": 10000,
}


def _oscillating_candles(n=300):
    """Sine-driven closes that repeatedly push RSI below 35 (many signals)."""
    candles = []
    start = datetime(2025, 1, 1)
    for i in range(n):
        price = 100 + 10 * math.sin(i * 0.15)
        candles.append(
            {
                "time": (start + timedelta(hours=i)).isoformat(),
                "open": price - 0.3,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": 1000.0,
            }
        )
    return candles


def _rsi_job(value=35, risk_limits=None, job_id="en-w1-vbt"):
    return BacktestJob(
        job_id=job_id,
        symbol="BTC/USDT",
        strategy_rules={
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": value}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        },
        slippage_pct=Decimal("0.001"),
        risk_limits=risk_limits,
    )


def _trade_sig(t):
    return (
        t.entry_time,
        t.exit_time,
        t.direction,
        str(t.entry_price),
        str(t.exit_price),
        str(t.pnl_pct),
        t.close_reason,
    )


class TestOpposingSignalCloseRemovedVectorbt:
    def test_vectorbt_engine_ignores_in_position_signals(self):
        """Repeat signals while in position must NOT close (the old engine
        closed + re-opened); with unreachable thresholds exactly one trade
        survives to the forced end-of-data close."""
        candles = _oscillating_candles(300)
        result = VectorBTRunner.run(_rsi_job(35, _WIDE_LIMITS), candles)
        assert result.total_trades == 1
        assert result.trades[0].close_reason == CLOSE_END_OF_DATA

    def test_signal_rich_data_sanity(self):
        candles = _oscillating_candles(300)
        result = VectorBTRunner.run(_rsi_job(35, _LIVE_LIKE_LIMITS), candles)
        assert result.total_trades > 1


class TestLookAheadPrefixInvarianceVectorbt:
    """B6 prefix invariance for the vectorized engine."""

    PREFIX = 300

    def _run(self, candles):
        return VectorBTRunner.run(_rsi_job(35, _LIVE_LIKE_LIMITS), candles)

    def test_vectorbt_engine_prefix_invariant(self):
        candles = _oscillating_candles(450)
        full = self._run(candles)
        trunc = self._run(candles[: self.PREFIX])

        prefix_times = {c["time"] for c in candles[: self.PREFIX]}
        trunc_core = [t for t in trunc.trades if t.close_reason != CLOSE_END_OF_DATA]
        full_core = [
            t
            for t in full.trades
            if t.close_reason != CLOSE_END_OF_DATA and t.exit_time in prefix_times
        ]
        assert len(trunc_core) > 0, "test needs closed trades inside the prefix"
        assert [_trade_sig(t) for t in trunc_core] == [_trade_sig(t) for t in full_core]

        eod = [t for t in trunc.trades if t.close_reason == CLOSE_END_OF_DATA]
        if eod:
            assert eod[0].entry_time in {t.entry_time for t in full.trades}


class TestCrossEngineExitConsistency:
    """B10 #9: same data + same risk_limits → both engines close at the same
    bars with the same reasons and Decimal-identical prices."""

    def _dip_recover_candles(self):
        """Rising warm-up (no signal until both engines are past indicator
        priming), then two dip/recover cycles → two deterministic entries."""
        closes = [100.0 + 0.1 * i for i in range(50)]
        p = closes[-1]
        for _ in range(2):
            for _ in range(6):
                p *= 0.99
                closes.append(p)
            for _ in range(50):
                p *= 1.005
                closes.append(p)
        start = datetime(2025, 3, 1)
        return [
            {
                "time": (start + timedelta(hours=i)).isoformat(),
                "open": c,
                "high": c * 1.001,
                "low": c * 0.999,
                "close": c,
                "volume": 500.0,
            }
            for i, c in enumerate(closes)
        ]

    def test_same_close_reasons_at_same_bars(self):
        candles = self._dip_recover_candles()
        job = _rsi_job(35, _LIVE_LIKE_LIMITS, job_id="xengine")

        seq = TradingSimulator.run(job, candles)
        vec = VectorBTRunner.run(job, candles)

        assert seq.total_trades > 0
        assert [_trade_sig(t) for t in seq.trades] == [
            _trade_sig(t) for t in vec.trades
        ]
        # Both engines surface a real exit-policy reason (not signal-close).
        for t in seq.trades:
            assert t.close_reason in (
                "stop_loss",
                "take_profit",
                "time_exit",
                CLOSE_END_OF_DATA,
            )
