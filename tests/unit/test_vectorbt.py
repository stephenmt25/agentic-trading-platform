"""Tests for Phase 6: VectorBT Backtesting Engine.

Tests the vectorized runner produces valid results, matches sequential
simulator on basic cases, and parameter sweep works correctly.
"""

import pytest
import math
from decimal import Decimal
from services.backtesting.src.simulator import TradingSimulator, BacktestJob, BacktestResult
from services.backtesting.src.vectorbt_runner import (
    VectorBTRunner, run_sweep, _compute_indicators, _evaluate_conditions_vectorized,
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
        candles.append({
            "time": f"2024-01-01T00:{i // 60:02d}:{i % 60:02d}",
            "open": price - 0.5,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price,
            "volume": 1000.0 + i * 10,
        })
    return candles


def _make_job(rules=None, slippage=Decimal("0.001")):
    if rules is None:
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
    return BacktestJob(job_id="test-job", symbol="BTC/USDT", strategy_rules=rules, slippage_pct=slippage)


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
            "rsi", "macd.macd_line", "atr", "adx", "bb.pct_b", "obv", "choppiness",
            "z_score", "vwap", "keltner.upper", "keltner.middle", "keltner.lower",
            "rvol", "hurst",
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
            "logic": "AND", "direction": "BUY", "base_confidence": 0.85,
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
            "logic": "AND", "direction": "BUY", "base_confidence": 0.85,
        }
        candles = _make_candles(200)

        result_no_slip = VectorBTRunner.run(_make_job(rules, slippage=Decimal("0")), candles)
        result_with_slip = VectorBTRunner.run(_make_job(rules, slippage=Decimal("0.01")), candles)

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
            candles.append({
                "time": f"2024-01-01T00:{i // 60:02d}:{i % 60:02d}",
                "open": price - 0.3, "high": price + 1.0,
                "low": price - 1.0, "close": price, "volume": 1000.0,
            })

        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 35}],
            "logic": "AND", "direction": "BUY", "base_confidence": 0.85,
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
            "logic": "AND", "direction": "BUY", "base_confidence": 0.85,
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
            "logic": "AND", "direction": "BUY", "base_confidence": 0.85,
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
            "logic": "AND", "direction": "BUY", "base_confidence": 0.85,
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
            "logic": "AND", "direction": "BUY", "base_confidence": 0.85,
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
