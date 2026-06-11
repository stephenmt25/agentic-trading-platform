"""EN-W1 — shared exit policy (libs/core/exit_policy.py).

Covers:
  * thresholds_from_risk_limits parsing (JSON string / dict / partial / None);
  * decide_exit precedence and boundary comparisons (exact live semantics);
  * the HEADLINE live↔sim parity tests: the same price path fed through
    decide_exit the way ExitMonitor.check consumes it (snapshot pct_return
    sequence) and through TradingSimulator.run must close at the same bar
    with the same reason — stop_loss / take_profit / time_exit, never an
    opposing-signal close.
"""

import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from libs.config import settings
from libs.core.enums import OrderSide, PositionStatus
from libs.core.exit_policy import (
    EXIT_STOP_LOSS,
    EXIT_TAKE_PROFIT,
    EXIT_TIME,
    ExitThresholds,
    decide_exit,
    thresholds_from_risk_limits,
)
from libs.core.models import Position
from services.backtesting.src.simulator import BacktestJob, TradingSimulator
from services.pnl.src.exit_monitor import ExitMonitor

_D = Decimal


# ---------------------------------------------------------------------------
# Synthetic price paths (hourly bars, deterministic)
# ---------------------------------------------------------------------------


def _candles_from_closes(closes, start=None):
    """Hourly candles with ISO timestamps; close drives everything."""
    start = start or datetime(2025, 1, 1)
    out = []
    for i, c in enumerate(closes):
        t = (start + timedelta(hours=i)).isoformat()
        out.append(
            {
                "time": t,
                "open": c,
                "high": c * 1.001,
                "low": c * 0.999,
                "close": c,
                "volume": 1000.0,
            }
        )
    return out


def _path_with_dip_then(post_entry: str, n_post: int = 60):
    """60 rising warm-up bars (RSI high → no LT-35 signal), then a decline
    that drives RSI under 35 (deterministic entry), then a post-entry shape:
      'drop'  — keep falling 1%/bar  (stop-loss path)
      'rise'  — rise 1%/bar          (take-profit path)
      'flat'  — hold the dip price   (time-exit path)
    """
    closes = [100.0 + 0.1 * i for i in range(60)]
    p = closes[-1]
    for _ in range(8):  # decline leg — pushes RSI below 35
        p *= 0.99
        closes.append(p)
    if post_entry == "drop":
        for _ in range(n_post):
            p *= 0.99
            closes.append(p)
    elif post_entry == "rise":
        for _ in range(n_post):
            p *= 1.01
            closes.append(p)
    else:  # flat
        closes.extend([p] * n_post)
    return _candles_from_closes(closes)


_RSI_RULES = {
    "conditions": [{"indicator": "rsi", "operator": "LT", "value": 35}],
    "logic": "AND",
    "direction": "BUY",
    "base_confidence": 0.85,
}


def _time_index(candles):
    return {c["time"]: i for i, c in enumerate(candles)}


def _decide_exit_walk(candles, entry_idx, entry_price, thresholds):
    """Feed the price path through decide_exit exactly the way the sim does
    (directional move off the slipped entry, bar close basis, age in hours)
    — which is also the shape ExitMonitor.check consumes via the snapshot.
    Returns (first_trigger_idx, reason) or (None, None).
    """
    entry_dt = datetime.fromisoformat(candles[entry_idx]["time"])
    for i in range(entry_idx + 1, len(candles)):
        close = _D(str(candles[i]["close"]))
        pct_return = (close - entry_price) / entry_price  # BUY direction
        age_hours = (
            datetime.fromisoformat(candles[i]["time"]) - entry_dt
        ).total_seconds() / 3600.0
        reason = decide_exit(pct_return, age_hours, thresholds)
        if reason is not None:
            return i, reason
    return None, None


# ---------------------------------------------------------------------------
# thresholds_from_risk_limits
# ---------------------------------------------------------------------------


class TestThresholdsFromRiskLimits:
    def test_none_returns_settings_defaults(self):
        th = thresholds_from_risk_limits(None)
        assert th.stop_loss_pct == _D(str(settings.DEFAULT_STOP_LOSS_PCT))
        assert th.take_profit_pct == _D(str(settings.DEFAULT_TAKE_PROFIT_PCT))
        assert th.max_holding_hours == settings.DEFAULT_MAX_HOLDING_HOURS
        assert isinstance(th.stop_loss_pct, Decimal)
        assert isinstance(th.take_profit_pct, Decimal)

    def test_dict_input_full_override(self):
        th = thresholds_from_risk_limits(
            {"stop_loss_pct": 0.07, "take_profit_pct": 0.03, "max_holding_hours": 12}
        )
        assert th.stop_loss_pct == _D("0.07")
        assert th.take_profit_pct == _D("0.03")
        assert th.max_holding_hours == 12.0

    def test_json_string_input(self):
        th = thresholds_from_risk_limits(
            '{"stop_loss_pct": 0.04, "max_holding_hours": 6}'
        )
        assert th.stop_loss_pct == _D("0.04")
        assert th.take_profit_pct == _D(str(settings.DEFAULT_TAKE_PROFIT_PCT))
        assert th.max_holding_hours == 6.0

    def test_partial_keys_only_explicit_override(self):
        """Pydantic defaults on RiskLimitsPayload must NOT override settings —
        only keys explicitly present in the payload do."""
        th = thresholds_from_risk_limits({"take_profit_pct": 0.10})
        assert th.take_profit_pct == _D("0.1")
        assert th.stop_loss_pct == _D(str(settings.DEFAULT_STOP_LOSS_PCT))
        assert th.max_holding_hours == settings.DEFAULT_MAX_HOLDING_HOURS

    def test_unrelated_keys_do_not_override(self):
        th = thresholds_from_risk_limits({"max_drawdown_pct": 0.5})
        assert th.stop_loss_pct == _D(str(settings.DEFAULT_STOP_LOSS_PCT))
        assert th.take_profit_pct == _D(str(settings.DEFAULT_TAKE_PROFIT_PCT))
        assert th.max_holding_hours == settings.DEFAULT_MAX_HOLDING_HOURS

    def test_empty_string_returns_defaults(self):
        th = thresholds_from_risk_limits("")
        assert th.stop_loss_pct == _D(str(settings.DEFAULT_STOP_LOSS_PCT))

    def test_malformed_json_falls_back_to_defaults(self):
        th = thresholds_from_risk_limits("{not json")
        assert th.stop_loss_pct == _D(str(settings.DEFAULT_STOP_LOSS_PCT))
        assert th.max_holding_hours == settings.DEFAULT_MAX_HOLDING_HOURS


# ---------------------------------------------------------------------------
# decide_exit precedence + comparisons
# ---------------------------------------------------------------------------

_TH = ExitThresholds(
    stop_loss_pct=_D("0.05"), take_profit_pct=_D("0.03"), max_holding_hours=48.0
)


class TestDecideExitPrecedence:
    def test_stop_loss_fires_on_threshold_loss(self):
        assert decide_exit(_D("-0.05"), 0.0, _TH) == EXIT_STOP_LOSS  # >= boundary
        assert decide_exit(_D("-0.10"), 0.0, _TH) == EXIT_STOP_LOSS

    def test_take_profit_fires_on_threshold_gain(self):
        assert decide_exit(_D("0.03"), 0.0, _TH) == EXIT_TAKE_PROFIT  # >= boundary
        assert decide_exit(_D("0.08"), 0.0, _TH) == EXIT_TAKE_PROFIT

    def test_time_exit_fires_on_age(self):
        assert decide_exit(_D("0.001"), 48.0, _TH) == EXIT_TIME  # >= boundary
        assert decide_exit(_D("-0.001"), 100.0, _TH) == EXIT_TIME

    def test_none_when_nothing_triggers(self):
        assert decide_exit(_D("-0.01"), 1.0, _TH) is None
        assert decide_exit(_D("0.01"), 1.0, _TH) is None
        assert decide_exit(_D("0"), 1.0, _TH) is None

    def test_stop_loss_wins_over_simultaneous_time_expiry(self):
        assert decide_exit(_D("-0.10"), 500.0, _TH) == EXIT_STOP_LOSS

    def test_take_profit_wins_over_simultaneous_time_expiry(self):
        assert decide_exit(_D("0.10"), 500.0, _TH) == EXIT_TAKE_PROFIT

    def test_sl_tp_are_sign_exclusive_zero_falls_through_to_time(self):
        """On the 'weird bar' (pct_return == 0 with zero thresholds) neither
        SL (strictly < 0) nor TP (strictly > 0) can fire — SL/TP are
        sign-exclusive by construction, so the only simultaneity that exists
        is against the time exit (covered above)."""
        th0 = ExitThresholds(_D("0"), _D("0"), 1.0)
        assert decide_exit(_D("0"), 0.5, th0) is None
        assert decide_exit(_D("0"), 1.0, th0) == EXIT_TIME

    def test_minus_inf_age_never_time_exits(self):
        assert decide_exit(_D("0"), -math.inf, _TH) is None


# ---------------------------------------------------------------------------
# HEADLINE: live ↔ sim exit parity on identical bars
# ---------------------------------------------------------------------------


class TestLiveSimExitParity:
    """A position that hits SL live hits SL — not opposing-signal — in the
    sim on identical bars (and the TP / time-exit equivalents)."""

    def _run_sim(self, candles, risk_limits):
        job = BacktestJob(
            job_id="parity",
            symbol="BTC/USDT",
            strategy_rules=_RSI_RULES,
            slippage_pct=_D("0.001"),
            risk_limits=risk_limits,
        )
        return TradingSimulator.run(job, candles)

    def _parity(self, candles, risk_limits, expected_reason):
        result = self._run_sim(candles, risk_limits)
        assert result.total_trades >= 1
        trade = result.trades[0]
        assert trade.close_reason == expected_reason

        idx = _time_index(candles)
        entry_idx = idx[trade.entry_time]
        exit_idx = idx[trade.exit_time]
        assert exit_idx > entry_idx

        # Same price path through the shared decision function, the way the
        # live ExitMonitor consumes it (pct_return sequence + age).
        thresholds = thresholds_from_risk_limits(risk_limits)
        live_idx, live_reason = _decide_exit_walk(
            candles, entry_idx, trade.entry_price, thresholds
        )
        assert live_idx == exit_idx, "live and sim must close on the same bar"
        assert live_reason == expected_reason
        return result, trade

    def test_stop_loss_parity_sim_closes_on_sl_not_opposing_signal(self):
        """THE headline test (registry row 43): on a declining path the sim
        closes via stop_loss at the exact bar the live policy fires — even
        though the entry signal keeps firing (which the removed
        opposing-signal close would have acted on first)."""
        candles = _path_with_dip_then("drop")
        risk_limits = {
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.5,
            "max_holding_hours": 10000,
        }
        self._parity(candles, risk_limits, EXIT_STOP_LOSS)

    def test_take_profit_parity(self):
        candles = _path_with_dip_then("rise")
        risk_limits = {
            "stop_loss_pct": 0.5,
            "take_profit_pct": 0.02,
            "max_holding_hours": 10000,
        }
        self._parity(candles, risk_limits, EXIT_TAKE_PROFIT)

    def test_time_exit_parity(self):
        candles = _path_with_dip_then("flat", n_post=20)
        risk_limits = {
            "stop_loss_pct": 0.5,
            "take_profit_pct": 0.5,
            "max_holding_hours": 5,
        }
        result, trade = self._parity(candles, risk_limits, EXIT_TIME)
        idx = _time_index(candles)
        # Hourly bars: a 5h max hold closes exactly 5 bars after entry.
        assert idx[trade.exit_time] - idx[trade.entry_time] == 5

    @pytest.mark.asyncio
    async def test_exit_monitor_fires_same_bar_as_sim(self):
        """Drive the real ExitMonitor.check over the sim's own pct_return
        sequence — it must return (True, 'stop_loss') exactly on the sim's
        exit bar and (False, None) on every prior bar."""
        candles = _path_with_dip_then("drop")
        risk_limits = {
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.5,
            "max_holding_hours": 10000,
        }
        result = self._run_sim(candles, risk_limits)
        trade = result.trades[0]
        idx = _time_index(candles)
        entry_idx, exit_idx = idx[trade.entry_time], idx[trade.exit_time]

        profile_repo = AsyncMock()
        profile_repo.get_profile = AsyncMock(
            return_value={"risk_limits": json.dumps(risk_limits)}
        )
        closer = AsyncMock()
        monitor = ExitMonitor(closer, profile_repo)  # legacy DB-only close path

        position = Position(
            position_id=uuid.uuid4(),
            profile_id=str(uuid.uuid4()),
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_price=trade.entry_price,
            quantity=_D("1"),
            entry_fee=_D("0"),
            opened_at=datetime.now(timezone.utc),  # age ≈ 0 → no time exit
            status=PositionStatus.OPEN,
        )

        for i in range(entry_idx + 1, exit_idx + 1):
            close = _D(str(candles[i]["close"]))
            pct = (close - trade.entry_price) / trade.entry_price
            snapshot = SimpleNamespace(pct_return=pct)
            closed, reason = await monitor.check(
                position, snapshot, close, _D("0.001")
            )
            if i < exit_idx:
                assert (closed, reason) == (False, None)
            else:
                assert (closed, reason) == (True, EXIT_STOP_LOSS)
        closer.close.assert_awaited_once()
