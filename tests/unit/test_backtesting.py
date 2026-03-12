"""Sprint 8.6: Backtest engine verification tests."""
import pytest
from services.backtesting.src.simulator import TradingSimulator, BacktestJob


def _make_candles(n: int, base_price: float = 100.0) -> list:
    """Generate synthetic candles with an oscillating pattern to trigger RSI signals."""
    candles = []
    import math
    for i in range(n):
        # Create oscillating pattern: price swings to trigger RSI oversold/overbought
        phase = math.sin(i * 0.15) * 20  # Oscillation
        trend = i * 0.05  # Slight uptrend
        close = base_price + phase + trend
        high = close + abs(math.sin(i * 0.3)) * 2
        low = close - abs(math.cos(i * 0.3)) * 2
        candles.append({
            "time": f"2025-01-01T00:{i // 60:02d}:{i % 60:02d}",
            "open": close - 0.5,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100.0,
        })
    return candles


class TestTradingSimulator:
    def test_run_with_synthetic_data_produces_real_trades(self):
        """Feed 200 synthetic candles with RSI rule, verify real trades and metrics."""
        job = BacktestJob(
            job_id="test-001",
            symbol="BTC/USDT",
            strategy_rules={
                "conditions": [{"indicator": "rsi", "operator": "LT", "value": 35}],
                "logic": "AND",
                "direction": "BUY",
                "base_confidence": 0.85,
            },
            slippage_pct=0.001,
        )
        candles = _make_candles(200)
        result = TradingSimulator.run(job, candles)

        # Must produce actual trades (not hardcoded 50)
        assert result.total_trades > 0
        assert result.total_trades != 50, "Result should not be hardcoded mock"
        assert 0.0 <= result.win_rate <= 1.0
        assert result.max_drawdown >= 0.0
        assert result.job_id == "test-001"
        assert len(result.equity_curve) > 0
        assert len(result.trades) == result.total_trades

    def test_run_with_empty_data(self):
        """Empty data should produce zero-trade result."""
        job = BacktestJob(
            job_id="test-002",
            symbol="BTC/USDT",
            strategy_rules={
                "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
                "logic": "AND",
                "direction": "BUY",
                "base_confidence": 0.85,
            },
            slippage_pct=0.001,
        )
        result = TradingSimulator.run(job, [])
        assert result.total_trades == 0
        assert result.win_rate == 0.0
        assert result.sharpe == 0.0

    def test_trades_have_valid_structure(self):
        """Each simulated trade should have entry/exit prices and PnL."""
        job = BacktestJob(
            job_id="test-003",
            symbol="ETH/USDT",
            strategy_rules={
                "conditions": [{"indicator": "rsi", "operator": "LT", "value": 40}],
                "logic": "AND",
                "direction": "BUY",
                "base_confidence": 0.9,
            },
            slippage_pct=0.001,
        )
        candles = _make_candles(200, base_price=3000.0)
        result = TradingSimulator.run(job, candles)

        for trade in result.trades:
            assert trade.entry_price > 0
            assert trade.exit_price is not None
            assert trade.exit_price > 0
            assert trade.entry_time != ""
            assert trade.direction in ("BUY", "SELL")

    def test_slippage_is_applied(self):
        """Slippage should make entry prices worse than the candle close."""
        job = BacktestJob(
            job_id="test-004",
            symbol="BTC/USDT",
            strategy_rules={
                "conditions": [{"indicator": "rsi", "operator": "LT", "value": 40}],
                "logic": "AND",
                "direction": "BUY",
                "base_confidence": 0.85,
            },
            slippage_pct=0.01,  # 1% slippage to make effect visible
        )
        candles = _make_candles(200)
        result = TradingSimulator.run(job, candles)

        if result.trades:
            # BUY trades: entry price should be higher than the raw close
            for trade in result.trades:
                if trade.direction == "BUY":
                    assert trade.slippage_cost > 0

    def test_equity_curve_starts_at_one(self):
        """Equity curve should start at 1.0 (100%)."""
        job = BacktestJob(
            job_id="test-005",
            symbol="BTC/USDT",
            strategy_rules={
                "conditions": [{"indicator": "rsi", "operator": "LT", "value": 35}],
                "logic": "AND",
                "direction": "BUY",
                "base_confidence": 0.85,
            },
            slippage_pct=0.001,
        )
        candles = _make_candles(200)
        result = TradingSimulator.run(job, candles)
        assert result.equity_curve[0] == 1.0
