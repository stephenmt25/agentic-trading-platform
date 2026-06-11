from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from libs.core.enums import Regime
from libs.core.exit_policy import (
    decide_exit,
    thresholds_from_risk_limits,
)
from libs.indicators import create_indicator_set
from services.strategy.src.compiler import RuleCompiler

_D = Decimal
_ZERO = _D("0")
_ONE = _D("1")

# Close reason for the forced end-of-data close — not a live exit reason
# (live positions stay open until SL/TP/time fires), only a sim artefact.
CLOSE_END_OF_DATA = "end_of_data"

# Profit factor (gross_profit / gross_loss) is unbounded when there are no
# losing trades. Decimal("Infinity") cannot cross any persistence boundary:
# FastAPI's JSONResponse renders with allow_nan=False (HTTP 500), stdlib
# json.dumps emits the non-standard "Infinity" token into the Redis status
# payload, and Postgres rejects Infinity in the NOT NULL DECIMAL(20,8)
# backtest_results.profit_factor column (failing the job). Walk-forward
# windows with 1-3 all-winning OOS trades hit the no-loss branch routinely,
# so the value is clamped to this finite, obviously-sentinel cap at the
# source — every consumer (engines, walk-forward report, job_runner JSON,
# DB insert) inherits a JSON/NUMERIC-safe value.
PROFIT_FACTOR_CAP = _D("999999999")


def parse_preferred_regimes(strategy_rules: Dict[str, Any]) -> frozenset:
    """Coerce strategy_rules['preferred_regimes'] (a list of regime-name
    strings) to a frozenset of Regime enums. Unknown names are silently
    dropped — mirrors the hot_path loader (_parse_static_config) so a profile
    typo can't change a backtest into a crash. An empty set means the profile
    is regime-agnostic and no regime gating is applied.
    """
    out: set = set()
    for name in strategy_rules.get("preferred_regimes", []) or []:
        try:
            out.add(Regime(name))
        except ValueError:
            pass
    return frozenset(out)


def parse_bar_time(value: Any) -> Optional[datetime]:
    """Parse a candle's time field to a datetime.

    The market-data repo returns datetimes (``bucket as "time"``); test
    fixtures and JSON round-trips carry ISO strings. Unparseable/missing
    values return None — the age computation then degrades to 0 hours, which
    can never fire a time exit on its own with positive thresholds.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def bar_age_hours(
    entry_time: Optional[datetime], current_time: Optional[datetime]
) -> float:
    """Position age in hours between two bar timestamps.

    Same float formula as the live ExitMonitor: ``total_seconds() / 3600.0``.
    Missing timestamps → 0.0 (no time-exit information).
    """
    if entry_time is None or current_time is None:
        return 0.0
    return (current_time - entry_time).total_seconds() / 3600.0


@dataclass
class BacktestJob:
    job_id: str
    symbol: str
    strategy_rules: Dict[str, Any]
    slippage_pct: Decimal
    # Profile risk_limits (dict or JSON string) — resolved once per run via
    # libs/core/exit_policy.thresholds_from_risk_limits. None → settings
    # defaults, exactly like a live profile with empty risk_limits.
    risk_limits: Optional[Dict[str, Any]] = None


@dataclass
class SimulatedTrade:
    entry_time: str
    exit_time: Optional[str]
    direction: str
    entry_price: Decimal
    exit_price: Optional[Decimal]
    slippage_cost: Decimal
    pnl_pct: Decimal
    # 'stop_loss' | 'take_profit' | 'time_exit' | 'end_of_data' ('' while open).
    close_reason: str = ""


@dataclass
class BacktestResult:
    job_id: str
    total_trades: int
    win_rate: Decimal
    avg_return: Decimal
    max_drawdown: Decimal
    sharpe: Decimal
    profit_factor: Decimal
    equity_curve: List[Decimal] = field(default_factory=list)
    trades: List[SimulatedTrade] = field(default_factory=list)


def compute_trade_metrics(trades: List[SimulatedTrade]) -> Dict[str, Decimal]:
    """Aggregate win_rate / avg_return / sharpe / profit_factor in Decimal.

    Shared by both engines and the walk-forward OOS aggregation — keep the
    formulas in one place so engine metrics can't drift.
    """
    total_trades = len(trades)
    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]
    win_rate = _D(len(wins)) / _D(total_trades) if total_trades > 0 else _ZERO
    avg_return = (
        sum(t.pnl_pct for t in trades) / _D(total_trades) if total_trades > 0 else _ZERO
    )

    # Sharpe ratio (annualised, assuming daily returns)
    returns = [t.pnl_pct for t in trades]
    if len(returns) >= 2:
        mean_r = sum(returns) / _D(len(returns))
        variance = sum((r - mean_r) ** 2 for r in returns) / _D(len(returns) - 1)
        std_r = variance.sqrt()
        sharpe = (mean_r / std_r) * _D("252").sqrt() if std_r > 0 else _ZERO
    else:
        sharpe = _ZERO

    gross_profit = sum(t.pnl_pct for t in wins) if wins else _ZERO
    gross_loss = abs(sum(t.pnl_pct for t in losses)) if losses else _ZERO
    profit_factor = (
        min(gross_profit / gross_loss, PROFIT_FACTOR_CAP)
        if gross_loss > 0
        else PROFIT_FACTOR_CAP if gross_profit > 0 else _ZERO
    )

    return {
        "win_rate": win_rate,
        "avg_return": avg_return,
        "sharpe": sharpe,
        "profit_factor": profit_factor,
    }


def compute_max_drawdown(equity_curve: List[Decimal]) -> Decimal:
    """Peak-to-trough max drawdown (fraction) over an equity curve."""
    peak = _ZERO
    max_dd = _ZERO
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


class TradingSimulator:
    @staticmethod
    def run(job: BacktestJob, data: List[Dict[str, Any]]) -> BacktestResult:
        if not data:
            return BacktestResult(
                job_id=job.job_id,
                total_trades=0,
                win_rate=_ZERO,
                avg_return=_ZERO,
                max_drawdown=_ZERO,
                sharpe=_ZERO,
                profit_factor=_ZERO,
            )

        compiled = RuleCompiler.compile(job.strategy_rules)
        indicators = create_indicator_set()
        preferred_regimes = parse_preferred_regimes(job.strategy_rules)
        # EN-W1 exit fidelity: same threshold resolution as the live
        # ExitMonitor — risk_limits keys override settings defaults only when
        # explicitly present. Resolved once per run.
        thresholds = thresholds_from_risk_limits(job.risk_limits)

        trades: List[SimulatedTrade] = []
        equity = _ONE
        equity_curve: List[Decimal] = [equity]
        peak_equity = equity
        max_drawdown = _ZERO
        open_trade: Optional[SimulatedTrade] = None
        entry_bar_dt: Optional[datetime] = None

        for candle in data:
            close_f = float(
                candle["close"]
            )  # float-ok: indicator library requires float
            high_f = float(candle["high"])  # float-ok: indicator library requires float
            low_f = float(candle["low"])  # float-ok: indicator library requires float
            close = _D(str(candle["close"]))
            candle_time = str(candle.get("time", ""))
            bar_dt = parse_bar_time(candle.get("time"))

            volume_f = float(
                candle.get("volume", 0)
            )  # float-ok: indicator library requires float

            # Update indicators (these use float internally — that's fine for signal generation)
            rsi_val = indicators.rsi.update(close_f)
            macd_val = indicators.macd.update(close_f)
            atr_val = indicators.atr.update(high_f, low_f, close_f)

            adx_val = (
                indicators.adx.update(high_f, low_f, close_f)
                if indicators.adx
                else None
            )
            bb_val = (
                indicators.bollinger.update(close_f) if indicators.bollinger else None
            )
            obv_val = (
                indicators.obv.update(close_f, volume_f) if indicators.obv else None
            )
            chop_val = (
                indicators.choppiness.update(high_f, low_f, close_f)
                if indicators.choppiness
                else None
            )

            # C.2 indicators — must be populated for templates that reference them
            # (z_score / vwap / keltner / rvol / hurst). Without these, the rule
            # compiler sees `None` for any C.2 condition and treats every candle
            # as "still priming" → zero trades.
            zscore_val = (
                indicators.zscore.update(close_f) if indicators.zscore else None
            )
            vwap_val = (
                indicators.vwap.update(close_f, volume_f) if indicators.vwap else None
            )
            keltner_val = (
                indicators.keltner.update(high_f, low_f, close_f)
                if indicators.keltner
                else None
            )
            rvol_val = indicators.rvol.update(volume_f) if indicators.rvol else None
            hurst_val = indicators.hurst.update(close_f) if indicators.hurst else None

            # ----------------------------------------------------------------
            # EN-W1 exit fidelity: while in position, evaluate the SAME exit
            # policy as the live ExitMonitor (SL/TP/time, same precedence and
            # comparisons) BEFORE any entry evaluation. Runs on every bar —
            # including regime-gated and priming bars — because live exits are
            # checked on every tick regardless of regime/signal state.
            #
            # Price basis: the current bar CLOSE only. This is the honest
            # bar-granularity analog of live's last-trade-price tick basis. We
            # deliberately do NOT use the bar's high/low to fill SL/TP: when a
            # single OHLC bar spans both the SL and TP levels, the intrabar
            # ordering (which level traded first) is unknowable from OHLC, so
            # any intrabar fill model would be guessing. Close-only decisions
            # use information available at decision time (no look-ahead).
            #
            # Basis note: sim pct_return is the directional move off the
            # slipped entry price, gross of exit costs; live pct_return is
            # net-post-tax from PnLCalculator (see libs/core/exit_policy.py).
            # ----------------------------------------------------------------
            if open_trade is not None:
                if open_trade.direction == "BUY":
                    pct_return = (close - open_trade.entry_price) / (
                        open_trade.entry_price
                    )
                else:
                    pct_return = (open_trade.entry_price - close) / (
                        open_trade.entry_price
                    )
                age_hours = bar_age_hours(entry_bar_dt, bar_dt)
                reason = decide_exit(pct_return, age_hours, thresholds)
                if reason is not None:
                    slip = close * job.slippage_pct
                    exit_price = (
                        close - slip if open_trade.direction == "BUY" else close + slip
                    )
                    if open_trade.direction == "BUY":
                        pnl_pct = (
                            exit_price - open_trade.entry_price
                        ) / open_trade.entry_price
                    else:
                        pnl_pct = (
                            open_trade.entry_price - exit_price
                        ) / open_trade.entry_price
                    open_trade.exit_time = candle_time
                    open_trade.exit_price = exit_price
                    open_trade.pnl_pct = pnl_pct
                    open_trade.close_reason = reason
                    trades.append(open_trade)
                    equity *= _ONE + pnl_pct
                    open_trade = None
                    entry_bar_dt = None

            # Signal evaluation — entries only. Opposing/repeat signals while
            # in position are IGNORED (the live hot_path never closes a
            # position on a signal; exits are exclusively SL/TP/time).
            result = None
            if rsi_val is not None and macd_val is not None and atr_val is not None:
                # Row 18: regime gate — mirrors the hot_path regime short-circuit
                # in processor.py. When the profile declares preferred_regimes and
                # the live rule-based regime is known and not among them, skip
                # signal evaluation for this candle (no entry). Empty
                # preferred_regimes = regime-agnostic; regime None during
                # classifier priming = don't gate on missing data. The HMM
                # regime is unavailable offline, so this uses the rule-based
                # SimpleRegimeClassifier alone — exactly how the live dampener
                # degrades when no HMM signal is present.
                gated = False
                if preferred_regimes:
                    regime = indicators.regime.update(close_f, atr_val)
                    if regime is not None and regime not in preferred_regimes:
                        gated = True

                if not gated:
                    eval_dict = {
                        "rsi": rsi_val,
                        "macd.macd_line": macd_val.macd_line,
                        "macd.signal_line": macd_val.signal_line,
                        "macd.histogram": macd_val.histogram,
                        "atr": atr_val,
                    }
                    if adx_val is not None:
                        eval_dict["adx"] = adx_val
                    if bb_val is not None:
                        eval_dict["bb.pct_b"] = bb_val.pct_b
                        eval_dict["bb.bandwidth"] = bb_val.bandwidth
                        eval_dict["bb.upper"] = bb_val.upper
                        eval_dict["bb.lower"] = bb_val.lower
                    if obv_val is not None:
                        eval_dict["obv"] = obv_val
                    if chop_val is not None:
                        eval_dict["choppiness"] = chop_val
                    if zscore_val is not None:
                        eval_dict["z_score"] = zscore_val
                    if vwap_val is not None:
                        eval_dict["vwap"] = vwap_val
                    if keltner_val is not None:
                        eval_dict["keltner.upper"] = keltner_val.upper
                        eval_dict["keltner.middle"] = keltner_val.middle
                        eval_dict["keltner.lower"] = keltner_val.lower
                    if rvol_val is not None:
                        eval_dict["rvol"] = rvol_val
                    if hurst_val is not None:
                        eval_dict["hurst"] = hurst_val

                    result = compiled.evaluate(eval_dict)

            # Open new trade on signal — only when flat. A bar that just
            # closed a position may re-enter on the same bar's signal (live
            # equivalent: a new approved signal right after an exit).
            if open_trade is None and result:
                direction, _confidence = result
                slip = close * job.slippage_pct
                entry_price = close + slip if direction.value == "BUY" else close - slip

                open_trade = SimulatedTrade(
                    entry_time=candle_time,
                    exit_time=None,
                    direction=direction.value,
                    entry_price=entry_price,
                    exit_price=None,
                    slippage_cost=slip,
                    pnl_pct=_ZERO,
                )
                entry_bar_dt = bar_dt

            equity_curve.append(equity)
            peak_equity = max(peak_equity, equity)
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else _ZERO
            max_drawdown = max(max_drawdown, dd)

        # Close any remaining open trade at last candle (sim artefact — live
        # positions would stay open; tagged distinctly for honesty).
        if open_trade and data:
            last_close = _D(str(data[-1]["close"]))
            slip = last_close * job.slippage_pct
            exit_price = (
                last_close - slip
                if open_trade.direction == "BUY"
                else last_close + slip
            )
            if open_trade.direction == "BUY":
                pnl_pct = (exit_price - open_trade.entry_price) / open_trade.entry_price
            else:
                pnl_pct = (open_trade.entry_price - exit_price) / open_trade.entry_price
            open_trade.exit_time = str(data[-1].get("time", ""))
            open_trade.exit_price = exit_price
            open_trade.pnl_pct = pnl_pct
            open_trade.close_reason = CLOSE_END_OF_DATA
            trades.append(open_trade)
            equity *= _ONE + pnl_pct
            equity_curve.append(equity)
            peak_equity = max(peak_equity, equity)
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else _ZERO
            max_drawdown = max(max_drawdown, dd)

        metrics = compute_trade_metrics(trades)

        return BacktestResult(
            job_id=job.job_id,
            total_trades=len(trades),
            win_rate=metrics["win_rate"],
            avg_return=metrics["avg_return"],
            max_drawdown=max_drawdown,
            sharpe=metrics["sharpe"],
            profit_factor=metrics["profit_factor"],
            equity_curve=equity_curve,
            trades=trades,
        )
