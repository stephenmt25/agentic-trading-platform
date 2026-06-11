"""Sprint 8.6: Backtest engine verification tests.

EN-W1 additions: opposing-signal close removal, look-ahead prefix
invariance, and the survivorship/coverage guard.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from services.backtesting.src.job_runner import compute_coverage
from services.backtesting.src.simulator import (
    CLOSE_END_OF_DATA,
    PROFIT_FACTOR_CAP,
    BacktestJob,
    SimulatedTrade,
    TradingSimulator,
    compute_trade_metrics,
    parse_preferred_regimes,
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
        candles.append(
            {
                "time": f"2025-01-01T00:{i // 60:02d}:{i % 60:02d}",
                "open": close - 0.5,
                "high": high,
                "low": low,
                "close": close,
                "volume": 100.0,
            }
        )
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

_ALL_REGIMES = {
    "RANGE_BOUND",
    "TRENDING_UP",
    "TRENDING_DOWN",
    "HIGH_VOLATILITY",
    "CRISIS",
}


def _observed_regimes(candles: list) -> set:
    """Replay the candles through the same rule-based regime classifier the
    backtester uses (fed only once ATR has primed) and collect every regime it
    actually emits. Lets the gating tests self-calibrate to whatever the
    synthetic data classifies as, instead of hard-coding a regime."""
    from libs.indicators import ATRCalculator, SimpleRegimeClassifier

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
            job = BacktestJob(
                "rg-seq", "BTC/USDT", self._rules(preferred), Decimal("0.001")
            )
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
            job = BacktestJob(
                "rg-vbt", "BTC/USDT", self._rules(preferred), Decimal("0.001")
            )
            return VectorBTRunner.run(job, candles).total_trades

        ungated = run(None)
        assert ungated > 0
        assert run(matched) == ungated
        assert run(excluded) < ungated


# ---------------------------------------------------------------------------
# EN-W1 — exit fidelity on the sequential engine
# ---------------------------------------------------------------------------

_WIDE_LIMITS = {
    # Thresholds no synthetic path can hit — isolates signal behaviour.
    "stop_loss_pct": 0.99,
    "take_profit_pct": 99.0,
    "max_holding_hours": 1e9,
}

_LIVE_LIKE_LIMITS = {
    # Explicit (env-independent) live-default-shaped thresholds.
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.015,
    "max_holding_hours": 10000,
}


def _rsi_job(value=45, risk_limits=None, job_id="en-w1"):
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


class TestOpposingSignalCloseRemoved:
    """The series keeps firing the entry signal while in position; with
    unreachable SL/TP/time thresholds the position must stay open until the
    forced end-of-data close — the pre-EN-W1 engine would have closed (and
    re-opened) on every repeat signal."""

    def test_sequential_engine_ignores_in_position_signals(self):
        candles = _make_candles(300)
        result = TradingSimulator.run(_rsi_job(45, _WIDE_LIMITS), candles)
        assert result.total_trades == 1
        assert result.trades[0].close_reason == CLOSE_END_OF_DATA

    def test_signal_rich_data_sanity(self):
        """Same data with live-like thresholds produces MULTIPLE trades —
        proves the single-trade result above comes from ignoring in-position
        signals, not from a signal-starved series."""
        candles = _make_candles(300)
        result = TradingSimulator.run(_rsi_job(45, _LIVE_LIKE_LIMITS), candles)
        assert result.total_trades > 1


class TestLookAheadPrefixInvariance:
    """B6: decisions may only use data through the current bar. Running on a
    truncated prefix must reproduce the full run's trades inside the common
    prefix exactly (entry/exit times, prices, reasons), excluding only the
    truncated run's forced end-of-data close."""

    PREFIX = 300

    def _run(self, candles):
        return TradingSimulator.run(_rsi_job(35, _LIVE_LIKE_LIMITS), candles)

    def test_sequential_engine_prefix_invariant(self):
        candles = _make_candles(450)
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

        # The truncated run's forced close (if any) corresponds to a trade
        # the full run also entered at the same bar.
        eod = [t for t in trunc.trades if t.close_reason == CLOSE_END_OF_DATA]
        if eod:
            assert eod[0].entry_time in {t.entry_time for t in full.trades}


# ---------------------------------------------------------------------------
# EN-W1 B8 — survivorship/coverage guard
# ---------------------------------------------------------------------------


def _hourly_candles(start: datetime, hours: int):
    return [
        {
            "time": (start + timedelta(hours=i)).isoformat(),
            "open": 100.0,
            "high": 100.5,
            "low": 99.5,
            "close": 100.0,
            "volume": 10.0,
        }
        for i in range(hours + 1)
    ]


class TestCoverageGuard:
    START = datetime(2025, 1, 1)

    def test_full_coverage_no_warning(self):
        end = self.START + timedelta(hours=240)
        cov = compute_coverage(self.START, end, _hourly_candles(self.START, 240))
        assert cov["coverage_pct"] == 1.0
        assert cov["coverage_warning"] is False
        assert cov["data_start"] == self.START.isoformat()
        assert cov["data_end"] == end.isoformat()

    def test_partial_coverage_warns(self):
        """Symbol listed mid-range: candles cover only half the request."""
        end = self.START + timedelta(hours=240)
        cov = compute_coverage(self.START, end, _hourly_candles(self.START, 120))
        assert abs(cov["coverage_pct"] - 0.5) < 0.01
        assert cov["coverage_warning"] is True

    def test_just_above_threshold_no_warning(self):
        end = self.START + timedelta(hours=100)
        cov = compute_coverage(self.START, end, _hourly_candles(self.START, 96))
        assert cov["coverage_pct"] >= 0.95
        assert cov["coverage_warning"] is False

    def test_unparseable_times_zero_coverage(self):
        end = self.START + timedelta(hours=10)
        candles = [{"time": "", "close": 100.0}]
        cov = compute_coverage(self.START, end, candles)
        assert cov["coverage_pct"] == 0.0
        assert cov["coverage_warning"] is True
        assert cov["data_start"] is None


def _winning_trade(pnl="0.02"):
    return SimulatedTrade(
        entry_time="2025-01-01T00:00:00",
        exit_time="2025-01-01T01:00:00",
        direction="BUY",
        entry_price=Decimal("100"),
        exit_price=Decimal("102"),
        slippage_cost=Decimal("0.1"),
        pnl_pct=Decimal(pnl),
        close_reason="take_profit",
    )


class TestProfitFactorIsAlwaysFinite:
    """Regression: profit_factor used to be Decimal('Infinity') when there
    were no losing trades. That value 500s the GET /backtest/{job_id} route
    (FastAPI JSONResponse uses allow_nan=False), writes the non-standard
    'Infinity' token into the Redis status payload, and is rejected by the
    NOT NULL DECIMAL(20,8) backtest_results.profit_factor column. Small
    all-winning walk-forward OOS windows hit the no-loss branch routinely,
    so the shared metrics helper clamps to a finite cap at the source."""

    def test_all_wins_clamped_to_finite_cap(self):
        metrics = compute_trade_metrics([_winning_trade(), _winning_trade("0.01")])
        assert metrics["profit_factor"] == PROFIT_FACTOR_CAP
        assert metrics["profit_factor"].is_finite()

    def test_all_wins_survives_strict_json(self):
        import json

        metrics = compute_trade_metrics([_winning_trade()])
        # allow_nan=False mirrors FastAPI's JSONResponse renderer — the exact
        # boundary that raised ValueError on Infinity before the clamp.
        encoded = json.dumps({k: float(v) for k, v in metrics.items()}, allow_nan=False)
        assert json.loads(encoded)["profit_factor"] == float(PROFIT_FACTOR_CAP)

    def test_huge_finite_ratio_also_capped(self):
        """A dust-sized loss must not produce a ratio that overflows the
        DECIMAL(20,8) column either — the cap bounds the finite branch too."""
        dust_loss = _winning_trade("-1E-20")
        metrics = compute_trade_metrics([_winning_trade(), dust_loss])
        assert metrics["profit_factor"] == PROFIT_FACTOR_CAP

    def test_mixed_trades_unaffected(self):
        loss = _winning_trade("-0.01")
        metrics = compute_trade_metrics([_winning_trade("0.02"), loss])
        assert metrics["profit_factor"] == Decimal("2")

    def test_no_trades_zero(self):
        assert compute_trade_metrics([])["profit_factor"] == Decimal("0")
