"""EN-W1 B7 — walk-forward (rolling train/test) harness tests.

Covers window arithmetic, OOS-only trade counting, Decimal aggregate
metrics, the param_grid per-window winner selection, and config parsing.
"""

import math
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from libs.core.schemas import WALK_FORWARD_MAX_BARS, BacktestRequest
from services.backtesting.src.simulator import (
    PROFIT_FACTOR_CAP,
    BacktestJob,
    SimulatedTrade,
    parse_bar_time,
)
from services.backtesting.src.walk_forward import (
    WalkForwardConfig,
    WalkForwardResult,
    WalkForwardWindow,
    compute_windows,
    parse_walk_forward_config,
    run_walk_forward,
)

_D = Decimal


def _candles(n=300):
    """Sine oscillation (frequent RSI signals) with hourly timestamps."""
    out = []
    start = datetime(2025, 2, 1)
    for i in range(n):
        price = 100 + 10 * math.sin(i * 0.15)
        out.append(
            {
                "time": (start + timedelta(hours=i)).isoformat(),
                "open": price - 0.3,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": 1000.0,
            }
        )
    return out


def _job(risk_limits=None):
    return BacktestJob(
        job_id="wf-test",
        symbol="BTC/USDT",
        strategy_rules={
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 40}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        },
        slippage_pct=_D("0.001"),
        risk_limits=risk_limits
        or {
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.015,
            "max_holding_hours": 10000,
        },
    )


# ---------------------------------------------------------------------------
# Config parsing + window arithmetic
# ---------------------------------------------------------------------------


class TestConfigParsing:
    def test_step_defaults_to_test_bars(self):
        cfg = parse_walk_forward_config({"train_bars": 100, "test_bars": 50})
        assert cfg.step_bars == 50

    def test_explicit_step(self):
        cfg = parse_walk_forward_config(
            {"train_bars": 100, "test_bars": 50, "step_bars": 25}
        )
        assert cfg.step_bars == 25

    def test_missing_keys_raise(self):
        with pytest.raises(ValueError):
            parse_walk_forward_config({"train_bars": 100})

    def test_non_positive_raises(self):
        with pytest.raises(ValueError):
            parse_walk_forward_config({"train_bars": 0, "test_bars": 50})

    def test_bad_param_grid_raises(self):
        with pytest.raises(ValueError):
            parse_walk_forward_config(
                {"train_bars": 10, "test_bars": 5, "param_grid": [1, 2]}
            )


class TestComputeBudget:
    """DoS guard: a single authenticated job must not starve the serial
    worker via unbounded windows x param-grid combinations."""

    def test_bars_above_cap_rejected(self):
        with pytest.raises(ValueError, match="must not exceed"):
            parse_walk_forward_config(
                {"train_bars": WALK_FORWARD_MAX_BARS + 1, "test_bars": 50}
            )

    def test_step_bars_above_cap_rejected(self):
        with pytest.raises(ValueError, match="must not exceed"):
            parse_walk_forward_config(
                {
                    "train_bars": 100,
                    "test_bars": 50,
                    "step_bars": WALK_FORWARD_MAX_BARS + 1,
                }
            )

    def test_param_grid_combination_cap(self):
        # 11 x 10 = 110 > 100 combinations.
        grid = {"0.value": list(range(11)), "1.value": list(range(10))}
        with pytest.raises(ValueError, match="combinations"):
            parse_walk_forward_config(
                {"train_bars": 100, "test_bars": 50, "param_grid": grid}
            )

    def test_param_grid_empty_list_rejected(self):
        with pytest.raises(ValueError, match="non-empty list"):
            parse_walk_forward_config(
                {"train_bars": 100, "test_bars": 50, "param_grid": {"0.value": []}}
            )

    def test_param_grid_non_list_value_rejected(self):
        with pytest.raises(ValueError, match="non-empty list"):
            parse_walk_forward_config(
                {"train_bars": 100, "test_bars": 50, "param_grid": {"0.value": 30}}
            )

    def test_window_count_cap_at_runtime(self):
        # train_bars=1, step_bars=1 over 300 bars → 299 windows > MAX_WINDOWS.
        cfg = parse_walk_forward_config(
            {"train_bars": 1, "test_bars": 1, "step_bars": 1}
        )
        with pytest.raises(ValueError, match="maximum is"):
            run_walk_forward(_job(), _candles(300), cfg)

    def test_total_run_budget_at_runtime(self):
        # 150 windows x 9 combos = 1350 > MAX_TOTAL_RUNS, while each
        # individual cap (windows ≤ 200, combos ≤ 100) is respected.
        cfg = parse_walk_forward_config(
            {
                "train_bars": 1,
                "test_bars": 1,
                "step_bars": 2,
                "param_grid": {"0.value": [30, 35, 40], "1.value": [1, 2, 3]},
            }
        )
        with pytest.raises(ValueError, match="budget exceeded"):
            run_walk_forward(_job(), _candles(301), cfg)

    def test_request_schema_mirrors_caps(self):
        """The API edge (422) enforces the same caps as the worker parser."""
        base = {
            "symbol": "BTC/USDT",
            "strategy_rules": {
                "direction": "long",
                "match_mode": "all",
                "signals": [
                    {"indicator": "rsi", "comparison": "below", "threshold": 30}
                ],
                "confidence": 0.8,
            },
            "start_date": "2025-01-01T00:00:00",
            "end_date": "2025-02-01T00:00:00",
        }
        with pytest.raises(PydanticValidationError):
            BacktestRequest(
                **base,
                walk_forward={
                    "train_bars": WALK_FORWARD_MAX_BARS + 1,
                    "test_bars": 50,
                },
            )
        with pytest.raises(PydanticValidationError):
            BacktestRequest(
                **base,
                walk_forward={
                    "train_bars": 100,
                    "test_bars": 50,
                    "param_grid": {
                        "0.value": list(range(11)),
                        "1.value": list(range(10)),
                    },
                },
            )
        # Sane config still accepted.
        req = BacktestRequest(
            **base,
            walk_forward={"train_bars": 100, "test_bars": 50},
        )
        assert req.walk_forward["train_bars"] == 100


class TestWindowArithmetic:
    def test_exact_tiling(self):
        cfg = WalkForwardConfig(train_bars=100, test_bars=50, step_bars=50)
        assert compute_windows(300, cfg) == [
            (0, 100, 150),
            (50, 150, 200),
            (100, 200, 250),
            (150, 250, 300),
        ]

    def test_partial_final_test_segment(self):
        cfg = WalkForwardConfig(train_bars=100, test_bars=50, step_bars=100)
        assert compute_windows(320, cfg) == [
            (0, 100, 150),
            (100, 200, 250),
            (200, 300, 320),  # final test segment shortened to the data end
        ]

    def test_no_window_when_data_too_short(self):
        cfg = WalkForwardConfig(train_bars=100, test_bars=50, step_bars=50)
        assert compute_windows(100, cfg) == []
        assert compute_windows(101, cfg) == [(0, 100, 101)]


# ---------------------------------------------------------------------------
# Static-rules walk-forward
# ---------------------------------------------------------------------------


class TestWalkForwardStatic:
    def _result(self):
        cfg = parse_walk_forward_config({"train_bars": 100, "test_bars": 50})
        return run_walk_forward(_job(), _candles(300), cfg)

    def test_window_count(self):
        result = self._result()
        assert len(result.windows) == 4

    def test_oos_trades_only_from_test_segments(self):
        result = self._result()
        candles = _candles(300)
        time_to_idx = {c["time"]: i for i, c in enumerate(candles)}
        windows = compute_windows(300, result.config)
        assert result.oos_trades, "synthetic data must produce OOS trades"
        # all_oos_trades is built by extending in window order, so cumulative
        # oos_trade_count slices recover each window's own trades. Assert each
        # entered within ITS OWN window's [test_start, test_end) — a global
        # earliest-boundary check would mask train leakage in later windows
        # whose train segments overlap earlier windows' test segments.
        offset = 0
        for w_res, (_, test_start, test_end) in zip(result.windows, windows):
            window_trades = result.oos_trades[offset : offset + w_res.oos_trade_count]
            offset += w_res.oos_trade_count
            for t in window_trades:
                idx = time_to_idx[t.entry_time]
                assert test_start <= idx < test_end, (
                    f"trade entered at bar {idx} outside its window's test "
                    f"segment [{test_start}, {test_end})"
                )
        assert offset == len(result.oos_trades)

    def test_window_oos_counts_sum_to_aggregate(self):
        result = self._result()
        assert sum(w.oos_trade_count for w in result.windows) == len(result.oos_trades)

    def test_aggregate_metrics_are_decimal(self):
        result = self._result()
        for key in ("win_rate", "avg_return", "sharpe", "profit_factor"):
            assert isinstance(result.oos_metrics[key], Decimal), key
        assert isinstance(result.oos_max_drawdown, Decimal)
        assert all(isinstance(e, Decimal) for e in result.oos_equity_curve)

    def test_in_sample_and_oos_reported_separately(self):
        result = self._result()
        report = result.report()
        assert report["total_windows"] == 4
        for w in report["windows"]:
            assert "in_sample_sharpe" in w
            assert "oos_sharpe" in w
            assert "oos_trades" in w
        assert "oos_total_trades" in report
        assert "oos_max_drawdown" in report

    def test_parent_backtest_result_carries_oos_aggregates(self):
        result = self._result()
        parent = result.to_backtest_result()
        assert parent.job_id == "wf-test"
        assert parent.total_trades == len(result.oos_trades)
        assert parent.trades == result.oos_trades
        assert parent.win_rate == result.oos_metrics["win_rate"]

    def test_raises_when_data_shorter_than_train(self):
        cfg = parse_walk_forward_config({"train_bars": 500, "test_bars": 50})
        with pytest.raises(ValueError):
            run_walk_forward(_job(), _candles(300), cfg)


# ---------------------------------------------------------------------------
# param_grid walk-forward — per-window winner selection
# ---------------------------------------------------------------------------


class TestWalkForwardParamGrid:
    def test_param_grid_picks_per_window_winner(self):
        cfg = parse_walk_forward_config(
            {
                "train_bars": 100,
                "test_bars": 50,
                "param_grid": {"0.value": [30, 45]},
            }
        )
        result = run_walk_forward(_job(), _candles(300), cfg)
        assert len(result.windows) == 4
        for w in result.windows:
            assert w.chosen_params is not None
            assert w.chosen_params["0.value"] in (30, 45)
            assert isinstance(w.in_sample_sharpe, Decimal)

    def test_param_grid_report_serializes(self):
        import json

        cfg = parse_walk_forward_config(
            {
                "train_bars": 100,
                "test_bars": 100,
                "param_grid": {"0.value": [35, 45]},
            }
        )
        result = run_walk_forward(_job(), _candles(300), cfg)
        # Must round-trip through json (Redis status payload contract).
        encoded = json.dumps(result.report())
        decoded = json.loads(encoded)
        assert decoded["config"]["param_grid"] == {"0.value": [35, 45]}
        assert decoded["windows"][0]["chosen_params"] is not None


# ---------------------------------------------------------------------------
# Sanity: parse_bar_time accepts both datetimes and ISO strings
# ---------------------------------------------------------------------------


class TestAllWinningWindowReportIsJsonCompliant:
    """Regression for the Infinity profit factor: a window whose 1-3 OOS
    trades are all winners used to put float('inf') into the report, which
    json.dumps round-tripped as the non-standard 'Infinity' token and
    FastAPI's JSONResponse (allow_nan=False) turned into an HTTP 500."""

    def _all_win_result(self):
        from services.backtesting.src.simulator import compute_trade_metrics

        win = SimulatedTrade(
            entry_time="2025-02-05T00:00:00",
            exit_time="2025-02-05T03:00:00",
            direction="BUY",
            entry_price=Decimal("100"),
            exit_price=Decimal("102"),
            slippage_cost=Decimal("0.1"),
            pnl_pct=Decimal("0.02"),
            close_reason="take_profit",
        )
        metrics = compute_trade_metrics([win])
        window = WalkForwardWindow(
            index=0,
            train_start="2025-02-01T00:00:00",
            test_start="2025-02-05T00:00:00",
            test_end="2025-02-07T00:00:00",
            chosen_params=None,
            in_sample_sharpe=Decimal("1.2"),
            oos_trade_count=1,
            oos_metrics=metrics,
        )
        return WalkForwardResult(
            job_id="wf-inf",
            config=WalkForwardConfig(train_bars=100, test_bars=50, step_bars=50),
            windows=[window],
            oos_trades=[win],
            oos_equity_curve=[Decimal("1"), Decimal("1.02")],
            oos_metrics=metrics,
            oos_max_drawdown=Decimal("0"),
        )

    def test_report_survives_strict_json(self):
        import json

        report = self._all_win_result().report()
        # allow_nan=False mirrors FastAPI's JSONResponse renderer.
        decoded = json.loads(json.dumps(report, allow_nan=False))
        assert decoded["oos_profit_factor"] == float(PROFIT_FACTOR_CAP)
        assert decoded["windows"][0]["oos_profit_factor"] == float(PROFIT_FACTOR_CAP)

    def test_parent_row_profit_factor_finite(self):
        parent = self._all_win_result().to_backtest_result()
        assert parent.profit_factor.is_finite()
        assert parent.profit_factor == PROFIT_FACTOR_CAP


class TestParseBarTime:
    def test_datetime_passthrough(self):
        dt = datetime(2025, 1, 1, 12)
        assert parse_bar_time(dt) is dt

    def test_iso_string(self):
        assert parse_bar_time("2025-01-01T12:00:00") == datetime(2025, 1, 1, 12)

    def test_garbage_returns_none(self):
        assert parse_bar_time("not-a-time") is None
        assert parse_bar_time("") is None
        assert parse_bar_time(None) is None
