"""EN-W2 Lane B1 — exit-band sweep dimension (risk_limits_grid).

Covers: combined-grid cardinality math, allowed-key validation, string-valued
merge semantics (Decimal contract via thresholds_from_risk_limits), run_sweep
across both dimensions, walk-forward best-selection across both dimensions,
budget rejection at the API edge and the worker, and the risk-grid-only path.
"""

import json
import math
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from libs.core.exit_policy import thresholds_from_risk_limits
from libs.core.schemas import (
    WALK_FORWARD_MAX_PARAM_COMBOS,
    BacktestRequest,
    risk_limits_grid_combinations,
    walk_forward_grid_combinations,
)
from services.backtesting.src.job_runner import resolve_walk_forward_raw
from services.backtesting.src.simulator import (
    BacktestJob,
    BacktestResult,
    TradingSimulator,
)
from services.backtesting.src.vectorbt_runner import (
    SweepResult,
    VectorBTRunner,
    merge_risk_limits,
    run_sweep,
)
from services.backtesting.src.walk_forward import (
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


_RULES = {
    "conditions": [{"indicator": "rsi", "operator": "LT", "value": 40}],
    "logic": "AND",
    "direction": "BUY",
    "base_confidence": 0.85,
}

_BASE_LIMITS = {
    "stop_loss_pct": 0.05,
    "take_profit_pct": 0.015,
    "max_holding_hours": 10000,
}


def _job(risk_limits=None):
    return BacktestJob(
        job_id="rg-test",
        symbol="BTC/USDT",
        strategy_rules=_RULES,
        slippage_pct=_D("0.001"),
        risk_limits=dict(_BASE_LIMITS) if risk_limits is None else risk_limits,
    )


def _zero_result(job_id="x"):
    return BacktestResult(
        job_id=job_id,
        total_trades=0,
        win_rate=_D("0"),
        avg_return=_D("0"),
        max_drawdown=_D("0"),
        sharpe=_D("0"),
        profit_factor=_D("0"),
    )


# ---------------------------------------------------------------------------
# Cardinality math
# ---------------------------------------------------------------------------


class TestGridCombinations:
    def test_both_grids_multiply(self):
        param = {"0.value": [25, 30, 35], "1.value": [1, 2]}  # 6
        risk = {"stop_loss_pct": [0.02, 0.05], "take_profit_pct": [0.01, 0.03]}  # 4
        assert walk_forward_grid_combinations(param, risk) == 24

    def test_param_grid_only(self):
        param = {"0.value": [25, 30, 35]}
        assert walk_forward_grid_combinations(param) == 3
        assert walk_forward_grid_combinations(param, None) == 3

    def test_risk_grid_only(self):
        risk = {"stop_loss_pct": [0.02, 0.05], "max_holding_hours": [24, 48]}
        assert walk_forward_grid_combinations(None, risk) == 4
        assert walk_forward_grid_combinations({}, risk) == 4

    def test_neither_grid(self):
        assert walk_forward_grid_combinations(None) == 1
        assert walk_forward_grid_combinations(None, None) == 1
        assert walk_forward_grid_combinations({}, {}) == 1

    def test_risk_grid_combinations_standalone(self):
        assert risk_limits_grid_combinations(None) == 1
        assert risk_limits_grid_combinations({}) == 1
        assert risk_limits_grid_combinations({"stop_loss_pct": [0.02, 0.05]}) == 2


class TestRiskGridValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(ValueError, match="not sweepable"):
            risk_limits_grid_combinations({"max_allocation_pct": [0.5, 1.0]})

    def test_unknown_key_rejected_alongside_valid_keys(self):
        grid = {"stop_loss_pct": [0.02], "circuit_breaker_daily_loss_pct": [0.01]}
        with pytest.raises(ValueError, match="not sweepable"):
            risk_limits_grid_combinations(grid)

    def test_empty_list_rejected(self):
        with pytest.raises(ValueError, match="non-empty list"):
            risk_limits_grid_combinations({"stop_loss_pct": []})

    def test_non_list_rejected(self):
        with pytest.raises(ValueError, match="non-empty list"):
            risk_limits_grid_combinations({"stop_loss_pct": 0.02})

    def test_non_positive_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            risk_limits_grid_combinations({"stop_loss_pct": [0.02, 0]})
        with pytest.raises(ValueError, match="positive"):
            risk_limits_grid_combinations({"take_profit_pct": [-0.01]})

    def test_garbage_value_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            risk_limits_grid_combinations({"stop_loss_pct": ["abc"]})
        with pytest.raises(ValueError, match="positive"):
            risk_limits_grid_combinations({"stop_loss_pct": [True]})
        with pytest.raises(ValueError, match="positive"):
            risk_limits_grid_combinations({"stop_loss_pct": [None]})

    def test_non_finite_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            risk_limits_grid_combinations({"max_holding_hours": [float("inf")]})
        with pytest.raises(ValueError, match="positive"):
            risk_limits_grid_combinations({"max_holding_hours": [float("nan")]})

    def test_numeric_strings_accepted(self):
        # DEFAULT_RISK_LIMITS convention: string-encoded Decimals are valid.
        assert risk_limits_grid_combinations({"stop_loss_pct": ["0.02", "0.05"]}) == 2


# ---------------------------------------------------------------------------
# Merge semantics — string values, Decimal-safe threshold resolution
# ---------------------------------------------------------------------------


class TestMergeRiskLimits:
    def test_combo_overrides_base_with_string_values(self):
        merged = merge_risk_limits(dict(_BASE_LIMITS), {"stop_loss_pct": 0.02})
        assert merged["stop_loss_pct"] == "0.02"  # str, not float
        # Untouched keys preserved from base.
        assert merged["take_profit_pct"] == 0.015
        assert merged["max_holding_hours"] == 10000

    def test_all_combo_values_stringified(self):
        combo = {
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.06,
            "max_holding_hours": 24,
        }
        merged = merge_risk_limits({}, combo)
        assert merged == {
            "stop_loss_pct": "0.03",
            "take_profit_pct": "0.06",
            "max_holding_hours": "24",
        }

    def test_empty_combo_returns_base_unchanged(self):
        base = dict(_BASE_LIMITS)
        assert merge_risk_limits(base, {}) is base
        assert merge_risk_limits(None, {}) is None
        # JSON-string base passes through untouched when there is no combo.
        s = json.dumps(_BASE_LIMITS)
        assert merge_risk_limits(s, {}) is s

    def test_json_string_base_is_parsed_then_merged(self):
        s = json.dumps(_BASE_LIMITS)
        merged = merge_risk_limits(s, {"stop_loss_pct": 0.02})
        assert merged["stop_loss_pct"] == "0.02"
        assert merged["take_profit_pct"] == 0.015

    def test_malformed_base_degrades_to_combo_only(self):
        merged = merge_risk_limits("{not json", {"stop_loss_pct": 0.02})
        assert merged == {"stop_loss_pct": "0.02"}

    def test_base_not_mutated(self):
        base = dict(_BASE_LIMITS)
        merge_risk_limits(base, {"stop_loss_pct": 0.02})
        assert base == _BASE_LIMITS

    def test_decimal_thresholds_resolve_from_merged_limits(self):
        """The shared exit policy must see the swept band exactly (Decimal
        from string — no float round-trip)."""
        merged = merge_risk_limits(
            dict(_BASE_LIMITS), {"stop_loss_pct": 0.03, "max_holding_hours": 12}
        )
        thresholds = thresholds_from_risk_limits(merged)
        assert thresholds.stop_loss_pct == Decimal("0.03")
        assert isinstance(thresholds.stop_loss_pct, Decimal)
        # Base (non-swept) key still wins over settings defaults.
        assert thresholds.take_profit_pct == Decimal("0.015")
        assert thresholds.max_holding_hours == 12.0


# ---------------------------------------------------------------------------
# run_sweep across both dimensions
# ---------------------------------------------------------------------------


class TestRunSweepRiskGrid:
    def _capture_runs(self, monkeypatch):
        captured = []

        def fake_run(job, data):
            captured.append(job)
            return _zero_result(job.job_id)

        monkeypatch.setattr(VectorBTRunner, "run", fake_run)
        return captured

    def test_combined_cartesian_product(self, monkeypatch):
        self._capture_runs(monkeypatch)
        result = run_sweep(
            symbol="BTC/USDT",
            base_rules=_RULES,
            param_grid={"0.value": [30, 40]},
            data=_candles(10),
            risk_limits=dict(_BASE_LIMITS),
            risk_limits_grid={"stop_loss_pct": [0.02, 0.05]},
        )
        assert len(result.param_results) == 4
        seen = {
            (r["params"]["0.value"], r["risk_params"]["stop_loss_pct"])
            for r in result.param_results
        }
        assert seen == {(30, 0.02), (30, 0.05), (40, 0.02), (40, 0.05)}

    def test_jobs_carry_merged_string_risk_limits(self, monkeypatch):
        captured = self._capture_runs(monkeypatch)
        run_sweep(
            symbol="BTC/USDT",
            base_rules=_RULES,
            param_grid={"0.value": [30]},
            data=_candles(10),
            risk_limits=dict(_BASE_LIMITS),
            risk_limits_grid={"stop_loss_pct": [0.02, 0.07]},
        )
        assert len(captured) == 2
        swept = sorted(j.risk_limits["stop_loss_pct"] for j in captured)
        assert swept == ["0.02", "0.07"]  # strings, Decimal-safe
        for j in captured:
            assert j.risk_limits["take_profit_pct"] == 0.015  # base preserved

    def test_no_risk_grid_keeps_base_passthrough(self, monkeypatch):
        captured = self._capture_runs(monkeypatch)
        base = dict(_BASE_LIMITS)
        result = run_sweep(
            symbol="BTC/USDT",
            base_rules=_RULES,
            param_grid={"0.value": [30, 40]},
            data=_candles(10),
            risk_limits=base,
        )
        assert all(r["risk_params"] == {} for r in result.param_results)
        assert all(j.risk_limits is base for j in captured)

    def test_risk_grid_only_sweep(self, monkeypatch):
        self._capture_runs(monkeypatch)
        result = run_sweep(
            symbol="BTC/USDT",
            base_rules=_RULES,
            param_grid={},
            data=_candles(10),
            risk_limits=dict(_BASE_LIMITS),
            risk_limits_grid={"take_profit_pct": [0.01, 0.02, 0.03]},
        )
        assert len(result.param_results) == 3
        assert all(r["params"] == {} for r in result.param_results)
        assert {r["risk_params"]["take_profit_pct"] for r in result.param_results} == {
            0.01,
            0.02,
            0.03,
        }

    def test_combined_budget_rejected(self):
        with pytest.raises(ValueError, match="maximum is"):
            run_sweep(
                symbol="BTC/USDT",
                base_rules=_RULES,
                param_grid={"0.value": list(range(1, 52))},  # 51
                data=_candles(10),
                risk_limits_grid={"stop_loss_pct": [0.02, 0.05]},  # x2 = 102
            )

    def test_disallowed_key_rejected(self):
        with pytest.raises(ValueError, match="not sweepable"):
            run_sweep(
                symbol="BTC/USDT",
                base_rules=_RULES,
                param_grid={},
                data=_candles(10),
                risk_limits_grid={"max_allocation_pct": [0.5]},
            )

    def test_real_engine_risk_grid_changes_outcomes(self):
        """End-to-end (no mocks): tighter exit bands must alter results on
        oscillating data — proves the merged thresholds actually reach the
        exit policy."""
        result = run_sweep(
            symbol="BTC/USDT",
            base_rules=_RULES,
            param_grid={},
            data=_candles(300),
            risk_limits=dict(_BASE_LIMITS),
            risk_limits_grid={"take_profit_pct": [0.001, 0.5]},
        )
        assert len(result.param_results) == 2
        tight, wide = result.param_results
        assert tight["risk_params"] == {"take_profit_pct": 0.001}
        # A near-zero TP band exits far more often than a 50% band.
        assert tight["total_trades"] > wide["total_trades"]


# ---------------------------------------------------------------------------
# Walk-forward — config parsing, budgets, best-selection across both dims
# ---------------------------------------------------------------------------


class TestWalkForwardRiskGridConfig:
    def test_parse_carries_risk_grid(self):
        cfg = parse_walk_forward_config(
            {
                "train_bars": 100,
                "test_bars": 50,
                "risk_limits_grid": {"stop_loss_pct": [0.02, 0.05]},
            }
        )
        assert cfg.risk_limits_grid == {"stop_loss_pct": [0.02, 0.05]}
        assert cfg.param_grid is None

    def test_parse_rejects_non_dict_risk_grid(self):
        with pytest.raises(ValueError, match="must be a dict"):
            parse_walk_forward_config(
                {"train_bars": 100, "test_bars": 50, "risk_limits_grid": [0.02]}
            )

    def test_parse_rejects_disallowed_key(self):
        with pytest.raises(ValueError, match="not sweepable"):
            parse_walk_forward_config(
                {
                    "train_bars": 100,
                    "test_bars": 50,
                    "risk_limits_grid": {"max_allocation_pct": [0.5]},
                }
            )

    def test_parse_combined_cardinality_cap(self):
        # 20 rule combos x 6 risk combos = 120 > 100.
        with pytest.raises(ValueError, match="combinations"):
            parse_walk_forward_config(
                {
                    "train_bars": 100,
                    "test_bars": 50,
                    "param_grid": {"0.value": list(range(20))},
                    "risk_limits_grid": {
                        "stop_loss_pct": [0.02, 0.05],
                        "take_profit_pct": [0.01, 0.02, 0.03],
                    },
                }
            )

    def test_runtime_total_budget_uses_combined_cardinality(self):
        # 150 windows x (3 rule x 3 risk) = 1350 > MAX_TOTAL_RUNS while each
        # individual cap (windows <= 200, combos <= 100) is respected.
        cfg = parse_walk_forward_config(
            {
                "train_bars": 1,
                "test_bars": 1,
                "step_bars": 2,
                "param_grid": {"0.value": [30, 35, 40]},
                "risk_limits_grid": {"stop_loss_pct": [0.02, 0.03, 0.05]},
            }
        )
        with pytest.raises(ValueError, match="budget exceeded"):
            run_walk_forward(_job(), _candles(301), cfg)


class TestWalkForwardRiskGridSelection:
    def test_best_selection_across_both_dims(self, monkeypatch):
        """The window winner is the (params, risk_params) PAIR with the best
        in-sample sharpe; its exit bands are merged (stringified) into the
        OOS evaluation job's risk_limits."""
        fake_results = [
            {
                "params": {"0.value": 30},
                "risk_params": {"stop_loss_pct": 0.02},
                "sharpe": _D("0.5"),
            },
            {
                "params": {"0.value": 45},
                "risk_params": {"stop_loss_pct": 0.07},
                "sharpe": _D("2.5"),
            },
            {
                "params": {"0.value": 45},
                "risk_params": {"stop_loss_pct": 0.02},
                "sharpe": _D("1.0"),
            },
        ]

        def fake_sweep(**kwargs):
            return SweepResult(
                job_id="fake", symbol="BTC/USDT", param_results=list(fake_results)
            )

        monkeypatch.setattr(
            "services.backtesting.src.walk_forward.run_sweep", fake_sweep
        )

        oos_jobs = []
        real_run = TradingSimulator.run

        def capture_run(job, data):
            oos_jobs.append(job)
            return real_run(job, data)

        monkeypatch.setattr(TradingSimulator, "run", capture_run)

        cfg = parse_walk_forward_config(
            {
                "train_bars": 100,
                "test_bars": 100,
                "param_grid": {"0.value": [30, 45]},
                "risk_limits_grid": {"stop_loss_pct": [0.02, 0.07]},
            }
        )
        result = run_walk_forward(_job(), _candles(300), cfg)

        assert len(result.windows) == 2
        for w in result.windows:
            assert w.chosen_params == {"0.value": 45}
            assert w.chosen_risk_params == {"stop_loss_pct": 0.07}
            assert w.in_sample_sharpe == _D("2.5")
        for j in oos_jobs:
            assert j.risk_limits["stop_loss_pct"] == "0.07"  # string-merged
            assert j.risk_limits["take_profit_pct"] == 0.015  # base preserved
            assert j.strategy_rules["conditions"][0]["value"] == 45

    def test_risk_grid_only_walk_forward(self):
        """No param_grid, risk grid present: the sweep runs on exit bands
        alone and every window reports a chosen band."""
        cfg = parse_walk_forward_config(
            {
                "train_bars": 100,
                "test_bars": 50,
                "risk_limits_grid": {"take_profit_pct": [0.005, 0.05]},
            }
        )
        result = run_walk_forward(_job(), _candles(300), cfg)
        assert len(result.windows) == 4
        for w in result.windows:
            assert w.chosen_params == {}  # no rule overrides swept
            assert w.chosen_risk_params is not None
            assert w.chosen_risk_params["take_profit_pct"] in (0.005, 0.05)
            assert isinstance(w.in_sample_sharpe, Decimal)

    def test_report_carries_risk_grid_and_chosen_bands(self):
        cfg = parse_walk_forward_config(
            {
                "train_bars": 100,
                "test_bars": 100,
                "risk_limits_grid": {"stop_loss_pct": [0.02, 0.05]},
            }
        )
        result = run_walk_forward(_job(), _candles(300), cfg)
        # Must round-trip through json (Redis status payload contract).
        decoded = json.loads(json.dumps(result.report()))
        assert decoded["config"]["risk_limits_grid"] == {"stop_loss_pct": [0.02, 0.05]}
        for w in decoded["windows"]:
            assert w["chosen_risk_params"]["stop_loss_pct"] in (0.02, 0.05)

    def test_static_walk_forward_reports_none_risk_params(self):
        cfg = parse_walk_forward_config({"train_bars": 100, "test_bars": 100})
        result = run_walk_forward(_job(), _candles(300), cfg)
        for w in result.windows:
            assert w.chosen_risk_params is None


# ---------------------------------------------------------------------------
# API edge — BacktestRequest shape (mirrors the worker caps)
# ---------------------------------------------------------------------------

_API_BASE = {
    "symbol": "BTC/USDT",
    "strategy_rules": {
        "direction": "long",
        "match_mode": "all",
        "signals": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
        "confidence": 0.8,
    },
    "start_date": "2025-01-01T00:00:00",
    "end_date": "2025-02-01T00:00:00",
}


class TestBacktestRequestRiskGrid:
    def test_top_level_grid_with_walk_forward_accepted(self):
        req = BacktestRequest(
            **_API_BASE,
            walk_forward={"train_bars": 100, "test_bars": 50},
            risk_limits_grid={"stop_loss_pct": [0.02, 0.05]},
        )
        assert req.risk_limits_grid == {"stop_loss_pct": [0.02, 0.05]}

    def test_top_level_grid_without_walk_forward_rejected(self):
        with pytest.raises(PydanticValidationError, match="walk_forward"):
            BacktestRequest(
                **_API_BASE, risk_limits_grid={"stop_loss_pct": [0.02, 0.05]}
            )

    def test_disallowed_key_rejected(self):
        with pytest.raises(PydanticValidationError, match="not sweepable"):
            BacktestRequest(
                **_API_BASE,
                walk_forward={"train_bars": 100, "test_bars": 50},
                risk_limits_grid={"max_allocation_pct": [0.5]},
            )

    def test_combined_budget_rejected_at_edge(self):
        # 51 rule combos x 2 risk combos = 102 > 100.
        with pytest.raises(PydanticValidationError, match="combinations"):
            BacktestRequest(
                **_API_BASE,
                walk_forward={
                    "train_bars": 100,
                    "test_bars": 50,
                    "param_grid": {"0.value": list(range(1, 52))},
                },
                risk_limits_grid={"stop_loss_pct": [0.02, 0.05]},
            )

    def test_embedded_grid_wins_over_top_level_for_budget(self):
        # Same 51x2=102 top-level combination, but the walk_forward dict
        # embeds a 1-value grid — the embedded grid is the effective one
        # (51x1=51), so the request passes.
        req = BacktestRequest(
            **_API_BASE,
            walk_forward={
                "train_bars": 100,
                "test_bars": 50,
                "param_grid": {"0.value": list(range(1, 52))},
                "risk_limits_grid": {"stop_loss_pct": [0.02]},
            },
            risk_limits_grid={"stop_loss_pct": [0.02, 0.05]},
        )
        assert req.walk_forward["risk_limits_grid"] == {"stop_loss_pct": [0.02]}

    def test_embedded_grid_budget_enforced(self):
        with pytest.raises(PydanticValidationError, match="combinations"):
            BacktestRequest(
                **_API_BASE,
                walk_forward={
                    "train_bars": 100,
                    "test_bars": 50,
                    "param_grid": {"0.value": list(range(1, 52))},
                    "risk_limits_grid": {"stop_loss_pct": [0.02, 0.05]},
                },
            )

    def test_cap_constant_unchanged(self):
        assert WALK_FORWARD_MAX_PARAM_COMBOS == 100


# ---------------------------------------------------------------------------
# Worker payload threading (job_runner)
# ---------------------------------------------------------------------------


class TestResolveWalkForwardRaw:
    def test_top_level_grid_threaded_into_walk_forward(self):
        wf = {"train_bars": 100, "test_bars": 50}
        payload = {
            "walk_forward": wf,
            "risk_limits_grid": {"stop_loss_pct": [0.02]},
        }
        out = resolve_walk_forward_raw(payload)
        assert out["risk_limits_grid"] == {"stop_loss_pct": [0.02]}
        # Original dict is not mutated (payload may be re-serialized).
        assert "risk_limits_grid" not in wf

    def test_embedded_grid_wins(self):
        payload = {
            "walk_forward": {
                "train_bars": 100,
                "test_bars": 50,
                "risk_limits_grid": {"stop_loss_pct": [0.03]},
            },
            "risk_limits_grid": {"stop_loss_pct": [0.02]},
        }
        out = resolve_walk_forward_raw(payload)
        assert out["risk_limits_grid"] == {"stop_loss_pct": [0.03]}

    def test_grid_without_walk_forward_fails_loudly(self):
        with pytest.raises(ValueError, match="walk_forward"):
            resolve_walk_forward_raw({"risk_limits_grid": {"stop_loss_pct": [0.02]}})

    def test_no_walk_forward_no_grid_returns_none(self):
        assert resolve_walk_forward_raw({}) is None
        assert resolve_walk_forward_raw({"walk_forward": None}) is None

    def test_walk_forward_without_grid_passes_through(self):
        wf = {"train_bars": 100, "test_bars": 50}
        assert resolve_walk_forward_raw({"walk_forward": wf}) == wf

    def test_threaded_output_parses(self):
        out = resolve_walk_forward_raw(
            {
                "walk_forward": {"train_bars": 100, "test_bars": 50},
                "risk_limits_grid": {"stop_loss_pct": [0.02, 0.05]},
            }
        )
        cfg = parse_walk_forward_config(out)
        assert cfg.risk_limits_grid == {"stop_loss_pct": [0.02, 0.05]}


# ---------------------------------------------------------------------------
# Gateway route — payload threading + 422 budget shape
# ---------------------------------------------------------------------------

from services.api_gateway.src.deps import (  # noqa: E402
    get_current_user,
    get_profile_repo,
    get_redis,
)
from services.api_gateway.src.routes.backtest import (  # noqa: E402
    router as backtest_router,
)

_USER_ID = str(uuid.uuid4())


def _redis_mock():
    redis = AsyncMock()
    redis.xlen = AsyncMock(return_value=0)
    redis.xadd = AsyncMock()
    redis.set = AsyncMock()
    return redis


def _client(redis) -> TestClient:
    app = FastAPI()
    app.include_router(backtest_router, prefix="/backtest")
    app.dependency_overrides[get_current_user] = lambda: _USER_ID
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_profile_repo] = lambda: AsyncMock()
    return TestClient(app)


def _api_body(**overrides):
    body = dict(_API_BASE)
    body.update(overrides)
    return body


class TestGatewayRiskGrid:
    def test_grid_rides_the_enqueued_payload(self):
        redis = _redis_mock()
        client = _client(redis)
        resp = client.post(
            "/backtest/",
            json=_api_body(
                walk_forward={"train_bars": 100, "test_bars": 50},
                risk_limits_grid={"stop_loss_pct": [0.02, 0.05]},
            ),
        )
        assert resp.status_code == 200
        args, _ = redis.xadd.await_args
        payload = json.loads(args[1]["data"])
        assert payload["risk_limits_grid"] == {"stop_loss_pct": [0.02, 0.05]}
        assert payload["walk_forward"] == {"train_bars": 100, "test_bars": 50}

    def test_over_budget_combined_grid_is_422_and_not_enqueued(self):
        redis = _redis_mock()
        client = _client(redis)
        resp = client.post(
            "/backtest/",
            json=_api_body(
                walk_forward={
                    "train_bars": 100,
                    "test_bars": 50,
                    "param_grid": {"0.value": list(range(1, 52))},
                },
                risk_limits_grid={"stop_loss_pct": [0.02, 0.05]},
            ),
        )
        assert resp.status_code == 422
        redis.xadd.assert_not_awaited()

    def test_disallowed_key_is_422_and_not_enqueued(self):
        redis = _redis_mock()
        client = _client(redis)
        resp = client.post(
            "/backtest/",
            json=_api_body(
                walk_forward={"train_bars": 100, "test_bars": 50},
                risk_limits_grid={"max_allocation_pct": [0.5]},
            ),
        )
        assert resp.status_code == 422
        redis.xadd.assert_not_awaited()

    def test_grid_without_walk_forward_is_422(self):
        redis = _redis_mock()
        client = _client(redis)
        resp = client.post(
            "/backtest/",
            json=_api_body(risk_limits_grid={"stop_loss_pct": [0.02]}),
        )
        assert resp.status_code == 422
        redis.xadd.assert_not_awaited()

    def test_request_without_grid_omits_nothing(self):
        """Backward compatibility: a no-grid request still enqueues with
        risk_limits_grid=None in the payload."""
        redis = _redis_mock()
        client = _client(redis)
        resp = client.post("/backtest/", json=_api_body())
        assert resp.status_code == 200
        args, _ = redis.xadd.await_args
        payload = json.loads(args[1]["data"])
        assert payload["risk_limits_grid"] is None
