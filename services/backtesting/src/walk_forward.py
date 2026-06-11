"""Walk-forward (rolling train/test) harness — EN-W1 B7.

A single in-sample fit can masquerade as edge; walk-forward splits the candle
series into rolling windows, (optionally) selects parameters on each train
slice, then evaluates ONLY the out-of-sample test segment. In-sample and
out-of-sample results are reported separately (``oos_`` prefix / ``windows``).

Window arithmetic (bar indices over the loaded candles):

    window k:  train = data[s : s+train_bars]
               test  = data[s+train_bars : s+train_bars+test_bars]
               s     = k * step_bars            (step_bars defaults to test_bars)

A window is emitted while the full train slice fits and at least one test bar
remains; the final test segment may be shorter than ``test_bars`` (honest use
of the remaining data). With the default ``step_bars == test_bars`` the test
segments tile the series without overlap; a smaller step overlaps test
segments and may double-count trades in the OOS aggregate — callers choosing
that trade-off own it.

Evaluation runs the sequential ``TradingSimulator`` (Decimal-exact) over
train+test so the train slice serves as indicator warm-up, then counts ONLY
trades ENTERED within the test segment. Parameter selection (when
``param_grid`` is given) reuses the vectorized ``run_sweep`` on the train
slice and picks the best in-sample sharpe.

All aggregate OOS metrics are Decimal via the shared
``simulator.compute_trade_metrics`` / ``compute_max_drawdown`` helpers.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from libs.core.schemas import (
    WALK_FORWARD_MAX_BARS,
    WALK_FORWARD_MAX_PARAM_COMBOS,
    walk_forward_grid_combinations,
)

from .simulator import (
    BacktestJob,
    BacktestResult,
    SimulatedTrade,
    TradingSimulator,
    compute_max_drawdown,
    compute_trade_metrics,
    parse_bar_time,
)
from .vectorbt_runner import _deep_copy_rules, _set_nested, run_sweep

_D = Decimal
_ZERO = _D("0")
_ONE = _D("1")

# Compute budget (DoS guard) — the backtesting worker is a SINGLE serial
# consumer; one pathological job (tiny step over a long series, dense grid)
# would starve every queued backtest. WALK_FORWARD_MAX_BARS /
# WALK_FORWARD_MAX_PARAM_COMBOS are shared with the API-edge validator in
# libs/core/schemas.py; the window/total-run caps below depend on the loaded
# series length, so they are enforced here at run time.
MAX_WINDOWS = 200
# windows x param-grid combinations — each unit is a full engine pass.
MAX_TOTAL_RUNS = 1_000


@dataclass(frozen=True)
class WalkForwardConfig:
    train_bars: int
    test_bars: int
    step_bars: int
    # Same shape as vectorbt run_sweep's param_grid, e.g. {"0.value": [25, 30]}.
    param_grid: Optional[Dict[str, List[Any]]] = None


def parse_walk_forward_config(raw: Dict[str, Any]) -> WalkForwardConfig:
    """Parse/validate the request's walk_forward dict."""
    try:
        train_bars = int(raw["train_bars"])
        test_bars = int(raw["test_bars"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "walk_forward requires integer train_bars and test_bars"
        ) from exc
    step_raw = raw.get("step_bars")
    step_bars = int(step_raw) if step_raw else test_bars
    if train_bars <= 0 or test_bars <= 0 or step_bars <= 0:
        raise ValueError("walk_forward bars must all be positive")
    if max(train_bars, test_bars, step_bars) > WALK_FORWARD_MAX_BARS:
        raise ValueError(
            f"walk_forward bars must not exceed {WALK_FORWARD_MAX_BARS}"
        )
    param_grid = raw.get("param_grid") or None
    if param_grid is not None and not isinstance(param_grid, dict):
        raise ValueError("walk_forward param_grid must be a dict")
    # Raises on non-list/empty values; bounds the sweep cardinality.
    combos = walk_forward_grid_combinations(param_grid)
    if combos > WALK_FORWARD_MAX_PARAM_COMBOS:
        raise ValueError(
            f"walk_forward param_grid expands to {combos} combinations; "
            f"maximum is {WALK_FORWARD_MAX_PARAM_COMBOS}"
        )
    return WalkForwardConfig(
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        param_grid=param_grid,
    )


def compute_windows(
    n_bars: int, config: WalkForwardConfig
) -> List[Tuple[int, int, int]]:
    """Return (train_start, test_start, test_end_exclusive) index triples."""
    windows: List[Tuple[int, int, int]] = []
    s = 0
    while s + config.train_bars < n_bars:
        test_start = s + config.train_bars
        test_end = min(test_start + config.test_bars, n_bars)
        windows.append((s, test_start, test_end))
        s += config.step_bars
    return windows


@dataclass
class WalkForwardWindow:
    index: int
    train_start: str
    test_start: str
    test_end: str
    chosen_params: Optional[Dict[str, Any]]
    in_sample_sharpe: Decimal
    oos_trade_count: int
    oos_metrics: Dict[str, Decimal]


@dataclass
class WalkForwardResult:
    job_id: str
    config: WalkForwardConfig
    windows: List[WalkForwardWindow]
    oos_trades: List[SimulatedTrade]
    oos_equity_curve: List[Decimal]
    oos_metrics: Dict[str, Decimal]
    oos_max_drawdown: Decimal

    def to_backtest_result(self) -> BacktestResult:
        """Parent backtest_results row: OOS aggregates only (the honest
        decay-tracker baseline). The per-window report is Redis/API-only."""
        return BacktestResult(
            job_id=self.job_id,
            total_trades=len(self.oos_trades),
            win_rate=self.oos_metrics["win_rate"],
            avg_return=self.oos_metrics["avg_return"],
            max_drawdown=self.oos_max_drawdown,
            sharpe=self.oos_metrics["sharpe"],
            profit_factor=self.oos_metrics["profit_factor"],
            equity_curve=self.oos_equity_curve,
            trades=self.oos_trades,
        )

    def report(self) -> Dict[str, Any]:
        """JSON-serializable per-window + aggregate report (Redis status /
        GET response). Decimal→float at this display boundary only — the DB
        row keeps Decimal precision."""

        def _f(v: Decimal) -> float:
            return float(v)  # float-ok: JSON display boundary, DB row stays Decimal

        return {
            "config": {
                "train_bars": self.config.train_bars,
                "test_bars": self.config.test_bars,
                "step_bars": self.config.step_bars,
                "param_grid": self.config.param_grid,
            },
            "total_windows": len(self.windows),
            "windows": [
                {
                    "index": w.index,
                    "train_start": w.train_start,
                    "test_start": w.test_start,
                    "test_end": w.test_end,
                    "chosen_params": w.chosen_params,
                    "in_sample_sharpe": _f(w.in_sample_sharpe),
                    "oos_trades": w.oos_trade_count,
                    "oos_win_rate": _f(w.oos_metrics["win_rate"]),
                    "oos_avg_return": _f(w.oos_metrics["avg_return"]),
                    "oos_sharpe": _f(w.oos_metrics["sharpe"]),
                    "oos_profit_factor": _f(w.oos_metrics["profit_factor"]),
                }
                for w in self.windows
            ],
            "oos_total_trades": len(self.oos_trades),
            "oos_win_rate": _f(self.oos_metrics["win_rate"]),
            "oos_avg_return": _f(self.oos_metrics["avg_return"]),
            "oos_max_drawdown": _f(self.oos_max_drawdown),
            "oos_sharpe": _f(self.oos_metrics["sharpe"]),
            "oos_profit_factor": _f(self.oos_metrics["profit_factor"]),
        }


def _entered_in_test(trade: SimulatedTrade, test_start_raw: Any) -> bool:
    """True when the trade's ENTRY falls inside the test segment."""
    test_dt = parse_bar_time(test_start_raw)
    entry_dt = parse_bar_time(trade.entry_time)
    if test_dt is not None and entry_dt is not None:
        return entry_dt >= test_dt
    # Fallback: ISO strings of a homogeneous series compare lexicographically.
    return str(trade.entry_time) >= str(test_start_raw)


def run_walk_forward(
    job: BacktestJob,
    data: List[Dict[str, Any]],
    config: WalkForwardConfig,
) -> WalkForwardResult:
    n = len(data)
    windows = compute_windows(n, config)
    if not windows:
        raise ValueError(
            f"walk_forward needs more than train_bars={config.train_bars} bars; "
            f"got {n}"
        )
    # Run-time compute budget: window count depends on the loaded series, so
    # it can only be enforced here. Each window costs (combos + 1) engine
    # passes with a param_grid (sweep + winner evaluation), 2 without.
    if len(windows) > MAX_WINDOWS:
        raise ValueError(
            f"walk_forward produces {len(windows)} windows over {n} bars; "
            f"maximum is {MAX_WINDOWS} (increase step_bars/test_bars)"
        )
    combos = walk_forward_grid_combinations(config.param_grid)
    if len(windows) * combos > MAX_TOTAL_RUNS:
        raise ValueError(
            f"walk_forward budget exceeded: {len(windows)} windows x "
            f"{combos} param combinations > {MAX_TOTAL_RUNS} engine runs"
        )

    window_reports: List[WalkForwardWindow] = []
    all_oos_trades: List[SimulatedTrade] = []

    for w_idx, (train_start, test_start, test_end) in enumerate(windows):
        train_data = data[train_start:test_start]
        eval_data = data[train_start:test_end]
        rules = job.strategy_rules
        chosen_params: Optional[Dict[str, Any]] = None

        if config.param_grid:
            sweep = run_sweep(
                symbol=job.symbol,
                base_rules=job.strategy_rules,
                param_grid=config.param_grid,
                data=train_data,
                slippage_pct=job.slippage_pct,
                risk_limits=job.risk_limits,
            )
            best = max(sweep.param_results, key=lambda r: r["sharpe"])
            chosen_params = best["params"]
            in_sample_sharpe = best["sharpe"]
            rules = _deep_copy_rules(job.strategy_rules)
            for key, val in chosen_params.items():
                _set_nested(rules, key, val)
        else:
            # Static rules: report the train-slice sharpe as the in-sample
            # reference so IS vs OOS decay is visible per window.
            is_job = BacktestJob(
                job_id=f"{job.job_id}-w{w_idx}-is",
                symbol=job.symbol,
                strategy_rules=rules,
                slippage_pct=job.slippage_pct,
                risk_limits=job.risk_limits,
            )
            in_sample_sharpe = TradingSimulator.run(is_job, train_data).sharpe

        # Evaluate over train+test (train = indicator warm-up), then keep
        # only trades ENTERED inside the test segment.
        w_job = BacktestJob(
            job_id=f"{job.job_id}-w{w_idx}",
            symbol=job.symbol,
            strategy_rules=rules,
            slippage_pct=job.slippage_pct,
            risk_limits=job.risk_limits,
        )
        res = TradingSimulator.run(w_job, eval_data)
        test_start_raw = data[test_start].get("time")
        oos_trades = [t for t in res.trades if _entered_in_test(t, test_start_raw)]
        all_oos_trades.extend(oos_trades)

        window_reports.append(
            WalkForwardWindow(
                index=w_idx,
                train_start=str(data[train_start].get("time", "")),
                test_start=str(data[test_start].get("time", "")),
                test_end=str(data[test_end - 1].get("time", "")),
                chosen_params=chosen_params,
                in_sample_sharpe=in_sample_sharpe,
                oos_trade_count=len(oos_trades),
                oos_metrics=compute_trade_metrics(oos_trades),
            )
        )

    # Aggregate OOS metrics over the concatenated OOS trades (Decimal).
    oos_metrics = compute_trade_metrics(all_oos_trades)
    equity = _ONE
    oos_equity_curve: List[Decimal] = [equity]
    for t in all_oos_trades:
        equity *= _ONE + t.pnl_pct
        oos_equity_curve.append(equity)
    oos_max_drawdown = compute_max_drawdown(oos_equity_curve)

    return WalkForwardResult(
        job_id=job.job_id,
        config=config,
        windows=window_reports,
        oos_trades=all_oos_trades,
        oos_equity_curve=oos_equity_curve,
        oos_metrics=oos_metrics,
        oos_max_drawdown=oos_max_drawdown,
    )
