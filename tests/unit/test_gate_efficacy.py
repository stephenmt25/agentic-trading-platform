"""Unit tests for the Insight Engine gate-efficacy core (Track D.PR2 MVP).

Pure-function tests with synthetic candles + decisions — no DB. Persistence
and the 6-hour orchestrator are covered separately by integration tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest

from services.analyst.src.gate_efficacy import (
    DEFAULT_LOOKAHEAD_BARS,
    MIN_SAMPLE_SIZE,
    _classify_block_gate,
    compute_gate_report,
    discover_gates_in_window,
    simulate_exit,
)


# ---------------------------------------------------------------------------
# simulate_exit
# ---------------------------------------------------------------------------

def _candle(close: float, high: float = None, low: float = None) -> Dict[str, Any]:
    return {"open": close, "close": close, "high": high or close, "low": low or close, "volume": 100.0}


class TestSimulateExit:
    def test_buy_take_profit(self):
        candles = [_candle(100), _candle(101), _candle(103, high=103)]
        sim = simulate_exit("BUY", 100.0, candles, stop_loss_pct=0.05, take_profit_pct=0.02, max_bars=10)
        assert sim.reason == "take_profit"
        assert sim.is_win is True
        assert sim.pnl_pct == pytest.approx(0.02)
        assert sim.bars_held == 3  # 1.03 = 100 * 1.03 → bar 3 with high 103

    def test_buy_stop_loss(self):
        candles = [_candle(99, low=99), _candle(96, low=96), _candle(95, low=94)]
        sim = simulate_exit("BUY", 100.0, candles, stop_loss_pct=0.05, take_profit_pct=0.10, max_bars=10)
        # Stop at 95 — bar 3 low 94 triggers
        assert sim.reason == "stop_loss"
        assert sim.is_win is False
        assert sim.pnl_pct == pytest.approx(-0.05)
        assert sim.bars_held == 3

    def test_buy_time_exit_positive_pnl(self):
        candles = [_candle(101), _candle(101.5), _candle(101.2)]
        sim = simulate_exit("BUY", 100.0, candles, stop_loss_pct=0.05, take_profit_pct=0.05, max_bars=3)
        assert sim.reason == "time_exit"
        assert sim.is_win is True
        assert sim.pnl_pct == pytest.approx(0.012)

    def test_buy_time_exit_negative_pnl(self):
        candles = [_candle(99), _candle(98.5), _candle(98)]
        sim = simulate_exit("BUY", 100.0, candles, stop_loss_pct=0.05, take_profit_pct=0.05, max_bars=3)
        assert sim.reason == "time_exit"
        assert sim.is_win is False
        assert sim.pnl_pct == pytest.approx(-0.02)

    def test_sell_take_profit(self):
        candles = [_candle(99, low=99), _candle(98, low=98), _candle(97.5, low=97.5)]
        sim = simulate_exit("SELL", 100.0, candles, stop_loss_pct=0.05, take_profit_pct=0.02, max_bars=10)
        assert sim.reason == "take_profit"
        assert sim.is_win is True
        assert sim.pnl_pct == pytest.approx(0.02)

    def test_sell_stop_loss(self):
        candles = [_candle(101, high=101), _candle(105, high=106)]
        sim = simulate_exit("SELL", 100.0, candles, stop_loss_pct=0.05, take_profit_pct=0.10, max_bars=10)
        assert sim.reason == "stop_loss"
        assert sim.pnl_pct == pytest.approx(-0.05)

    def test_max_bars_caps_holding(self):
        candles = [_candle(100 + i * 0.001) for i in range(100)]
        sim = simulate_exit("BUY", 100.0, candles, stop_loss_pct=0.05, take_profit_pct=0.10, max_bars=5)
        assert sim.bars_held == 5
        assert sim.reason == "time_exit"

    def test_no_candles_returns_no_data(self):
        sim = simulate_exit("BUY", 100.0, [], stop_loss_pct=0.01, take_profit_pct=0.01, max_bars=1)
        assert sim.reason == "no_data"

    def test_stop_first_when_both_in_one_bar(self):
        # Bar straddles both levels: low=94 (stop), high=103 (target). Conservative
        # convention: stop wins.
        candles = [_candle(98, high=103, low=94)]
        sim = simulate_exit("BUY", 100.0, candles, stop_loss_pct=0.05, take_profit_pct=0.02, max_bars=10)
        assert sim.reason == "stop_loss"


# ---------------------------------------------------------------------------
# _classify_block_gate
# ---------------------------------------------------------------------------

class TestClassifyBlockGate:
    @pytest.mark.parametrize(
        "outcome,expected",
        [
            ("APPROVED", None),
            ("BLOCKED_ABSTENTION", "abstention"),
            ("BLOCKED_REGIME", "regime"),
            ("BLOCKED_REGIME_MISMATCH", "regime_mismatch"),
            ("BLOCKED_HITL", "hitl"),
            ("BLOCKED_RISK", "risk"),
            ("BLOCKED_CIRCUIT_BREAKER", "circuit_breaker"),
            ("BLOCKED_VALIDATION", "validation"),
            (None, None),
            ("UNKNOWN", None),
        ],
    )
    def test_outcome_mapping(self, outcome, expected):
        assert _classify_block_gate({"outcome": outcome}) == expected


# ---------------------------------------------------------------------------
# discover_gates_in_window
# ---------------------------------------------------------------------------

def test_discover_gates_in_window():
    decs = [
        {"outcome": "APPROVED"},
        {"outcome": "BLOCKED_ABSTENTION"},
        {"outcome": "BLOCKED_HITL"},
        {"outcome": "BLOCKED_HITL"},
        {"outcome": "BLOCKED_REGIME_MISMATCH"},
    ]
    assert discover_gates_in_window(decs) == ["abstention", "hitl", "regime_mismatch"]


# ---------------------------------------------------------------------------
# compute_gate_report
# ---------------------------------------------------------------------------

def _decision(
    outcome: str,
    *,
    created_at: datetime,
    price: float = 100.0,
    direction: str = "BUY",
) -> Dict[str, Any]:
    return {
        "outcome": outcome,
        "input_price": price,
        "created_at": created_at,
        "strategy": {"direction": direction},
        "profile_rules": {"direction": direction},
    }


class TestComputeGateReport:
    @staticmethod
    def _winning_future():
        return [_candle(101 + i * 0.5, high=101 + i * 0.5 + 0.5) for i in range(60)]

    @staticmethod
    def _losing_future():
        return [_candle(99 - i * 0.5, low=99 - i * 0.5 - 0.5) for i in range(60)]

    def test_below_min_sample_returns_null_metrics(self):
        # 5 blocked decisions — far below MIN_SAMPLE_SIZE (30) — so the
        # report must surface NULLs to discourage interpretation.
        now = datetime.now(timezone.utc)
        decs = [_decision("BLOCKED_ABSTENTION", created_at=now - timedelta(minutes=i)) for i in range(5)]
        future_winners = self._winning_future()
        report = compute_gate_report(
            profile_id="00000000-0000-0000-0000-000000000001",
            symbol="BTC/USDT",
            gate_name="abstention",
            window_start=now - timedelta(hours=24),
            window_end=now,
            decisions=decs,
            candles_after=lambda _ts: future_winners,
            risk_limits={"stop_loss_pct": 0.05, "take_profit_pct": 0.02},
        )
        assert report.blocked_count == 5
        assert report.passed_count == 0
        assert report.sample_size_blocked == 5
        assert report.blocked_would_be_win_rate is None
        assert report.blocked_would_be_pnl_pct is None
        assert report.passed_realized_win_rate is None
        assert report.confidence_band is None

    def test_full_report_with_winning_blocked_set(self):
        """If every blocked decision would have hit take-profit, the
        gate-efficacy panel should scream — that's the partner-visible
        story this MVP exists to tell."""
        now = datetime.now(timezone.utc)
        n = MIN_SAMPLE_SIZE + 5
        blocked = [_decision("BLOCKED_ABSTENTION", created_at=now - timedelta(minutes=i)) for i in range(n)]
        passed = [_decision("APPROVED", created_at=now - timedelta(minutes=i + 100)) for i in range(n)]
        future = self._winning_future()
        report = compute_gate_report(
            profile_id="00000000-0000-0000-0000-000000000001",
            symbol="BTC/USDT",
            gate_name="abstention",
            window_start=now - timedelta(hours=24),
            window_end=now,
            decisions=blocked + passed,
            candles_after=lambda _ts: future,
            risk_limits={"stop_loss_pct": 0.05, "take_profit_pct": 0.02},
        )
        assert report.blocked_count == n
        assert report.passed_count == n
        # All blocked → take-profit → 100% win rate, +2% PnL
        assert report.blocked_would_be_win_rate == pytest.approx(1.0)
        assert report.blocked_would_be_pnl_pct == pytest.approx(0.02)
        assert report.passed_realized_win_rate == pytest.approx(1.0)
        assert report.passed_realized_pnl_pct == pytest.approx(0.02)
        # Bootstrap CI on equal samples — should be ~0
        assert report.confidence_band is not None
        assert report.confidence_band <= 0.001

    def test_only_target_gate_counted(self):
        """Decisions blocked by gates other than the target gate must not
        influence either count or the metric arrays."""
        now = datetime.now(timezone.utc)
        n = MIN_SAMPLE_SIZE + 2
        target = [_decision("BLOCKED_ABSTENTION", created_at=now - timedelta(minutes=i)) for i in range(n)]
        other_gate = [_decision("BLOCKED_HITL", created_at=now - timedelta(minutes=i + 200)) for i in range(20)]
        passed = [_decision("APPROVED", created_at=now - timedelta(minutes=i + 100)) for i in range(n)]
        future = self._losing_future()
        report = compute_gate_report(
            profile_id="00000000-0000-0000-0000-000000000001",
            symbol="BTC/USDT",
            gate_name="abstention",
            window_start=now - timedelta(hours=24),
            window_end=now,
            decisions=target + other_gate + passed,
            candles_after=lambda _ts: future,
            risk_limits={"stop_loss_pct": 0.05, "take_profit_pct": 0.10},
        )
        assert report.blocked_count == n
        assert report.passed_count == n
        # Losing future for all → expect stop_loss = -5%
        assert report.blocked_would_be_pnl_pct == pytest.approx(-0.05)
        assert report.passed_realized_pnl_pct == pytest.approx(-0.05)

    def test_no_candles_drops_decision(self):
        now = datetime.now(timezone.utc)
        n = MIN_SAMPLE_SIZE + 2
        blocked = [_decision("BLOCKED_ABSTENTION", created_at=now - timedelta(minutes=i)) for i in range(n)]
        report = compute_gate_report(
            profile_id="00000000-0000-0000-0000-000000000001",
            symbol="BTC/USDT",
            gate_name="abstention",
            window_start=now - timedelta(hours=24),
            window_end=now,
            decisions=blocked,
            candles_after=lambda _ts: [],
            risk_limits={"stop_loss_pct": 0.05, "take_profit_pct": 0.02},
        )
        # blocked_count is the raw count; sample_size_blocked drops the rows
        # that had no future data.
        assert report.blocked_count == n
        assert report.sample_size_blocked == 0
        assert report.blocked_would_be_win_rate is None
