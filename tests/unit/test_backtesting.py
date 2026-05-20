"""Sprint 8.6: Backtest engine verification tests."""
import pytest
from decimal import Decimal
from services.backtesting.src.simulator import (
    TradingSimulator, BacktestJob, parse_preferred_regimes,
)
from services.backtesting.src.vectorbt_runner import VectorBTRunner


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
            slippage_pct=Decimal("0.001"),
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
            slippage_pct=Decimal("0.001"),
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
            slippage_pct=Decimal("0.001"),
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
            slippage_pct=Decimal("0.01"),  # 1% slippage to make effect visible
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
            slippage_pct=Decimal("0.001"),
        )
        candles = _make_candles(200)
        result = TradingSimulator.run(job, candles)
        assert result.equity_curve[0] == 1.0


# ---------------------------------------------------------------------------
# Row 18 — backtester honours preferred_regimes
# ---------------------------------------------------------------------------

_ALL_REGIMES = {"RANGE_BOUND", "TRENDING_UP", "TRENDING_DOWN", "HIGH_VOLATILITY", "CRISIS"}


def _observed_regimes(candles: list) -> set:
    """Replay the candles through the same rule-based regime classifier the
    backtester uses (fed only once ATR has primed) and collect every regime it
    actually emits. Lets the gating tests self-calibrate to whatever the
    synthetic data classifies as, instead of hard-coding a regime."""
    from libs.indicators import SimpleRegimeClassifier, ATRCalculator
    clf = SimpleRegimeClassifier()
    atr = ATRCalculator()
    seen: set = set()
    for c in candles:
        a = atr.update(float(c["high"]), float(c["low"]), float(c["close"]))
        if a is None:
            continue
        r = clf.update(float(c["close"]), a)
        if r is not None:
            seen.add(r)
    return seen


class TestParsePreferredRegimes:
    def test_empty_when_absent(self):
        assert parse_preferred_regimes({}) == frozenset()

    def test_empty_when_none(self):
        assert parse_preferred_regimes({"preferred_regimes": None}) == frozenset()

    def test_known_regimes_parsed(self):
        from libs.core.enums import Regime
        result = parse_preferred_regimes(
            {"preferred_regimes": ["RANGE_BOUND", "TRENDING_UP"]}
        )
        assert result == frozenset({Regime.RANGE_BOUND, Regime.TRENDING_UP})

    def test_unknown_regime_silently_dropped(self):
        from libs.core.enums import Regime
        result = parse_preferred_regimes(
            {"preferred_regimes": ["RANGE_BOUND", "BANANA"]}
        )
        assert result == frozenset({Regime.RANGE_BOUND})


class TestRegimeGating:
    """A regime-gated profile must fire strictly fewer trades than the same
    profile with no allowlist — and an allowlist that covers every regime the
    data visits must change nothing. Without this, regime-gated backtests
    overstate trade frequency (the Row 18 defect)."""

    def _rules(self, preferred=None) -> dict:
        r = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 45}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        if preferred is not None:
            r["preferred_regimes"] = preferred
        return r

    def _setup(self):
        candles = _make_candles(500)
        observed = _observed_regimes(candles)
        assert observed, "classifier should prime over 500 candles"
        excluded = sorted(_ALL_REGIMES - {r.value for r in observed})
        assert excluded, "synthetic data must not span every regime"
        matched = sorted(r.value for r in observed)
        return candles, matched, excluded

    def test_sequential_engine_honours_preferred_regimes(self):
        candles, matched, excluded = self._setup()

        def run(preferred):
            job = BacktestJob("rg-seq", "BTC/USDT", self._rules(preferred), Decimal("0.001"))
            return TradingSimulator.run(job, candles).total_trades

        ungated = run(None)
        assert ungated > 0
        # Allowlist covering every visited regime must not gate anything.
        assert run(matched) == ungated
        # Allowlist of regimes the data never visits suppresses post-priming
        # signals → strictly fewer trades.
        assert run(excluded) < ungated

    def test_vectorbt_engine_honours_preferred_regimes(self):
        candles, matched, excluded = self._setup()

        def run(preferred):
            job = BacktestJob("rg-vbt", "BTC/USDT", self._rules(preferred), Decimal("0.001"))
            return VectorBTRunner.run(job, candles).total_trades

        ungated = run(None)
        assert ungated > 0
        assert run(matched) == ungated
        assert run(excluded) < ungated
