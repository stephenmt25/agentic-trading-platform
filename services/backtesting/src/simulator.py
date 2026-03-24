from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import math

from services.strategy.src.compiler import RuleCompiler, CompiledRuleSet
from libs.indicators import create_indicator_set


@dataclass
class BacktestJob:
    job_id: str
    symbol: str
    strategy_rules: Dict[str, Any]
    slippage_pct: float


@dataclass
class SimulatedTrade:
    entry_time: str
    exit_time: Optional[str]
    direction: str
    entry_price: float
    exit_price: Optional[float]
    slippage_cost: float
    pnl_pct: float


@dataclass
class BacktestResult:
    job_id: str
    total_trades: int
    win_rate: float
    avg_return: float
    max_drawdown: float
    sharpe: float
    profit_factor: float
    equity_curve: List[float] = field(default_factory=list)
    trades: List[SimulatedTrade] = field(default_factory=list)


class TradingSimulator:
    @staticmethod
    def run(job: BacktestJob, data: List[Dict[str, Any]]) -> BacktestResult:
        if not data:
            return BacktestResult(
                job_id=job.job_id, total_trades=0, win_rate=0.0,
                avg_return=0.0, max_drawdown=0.0, sharpe=0.0, profit_factor=0.0,
            )

        compiled = RuleCompiler.compile(job.strategy_rules)
        indicators = create_indicator_set()

        trades: List[SimulatedTrade] = []
        equity = 1.0
        equity_curve = [equity]
        peak_equity = equity
        max_drawdown = 0.0
        open_trade: Optional[SimulatedTrade] = None

        for candle in data:
            close = float(candle["close"])
            high = float(candle["high"])
            low = float(candle["low"])
            candle_time = str(candle.get("time", ""))

            # Update indicators
            rsi_val = indicators.rsi.update(close)
            macd_val = indicators.macd.update(close)
            atr_val = indicators.atr.update(high, low, close)

            # New indicators (None-safe — still priming returns None)
            adx_val = indicators.adx.update(high, low, close) if indicators.adx else None
            bb_val = indicators.bollinger.update(close) if indicators.bollinger else None
            volume = float(candle.get("volume", 0))
            obv_val = indicators.obv.update(close, volume) if indicators.obv else None
            chop_val = indicators.choppiness.update(high, low, close) if indicators.choppiness else None

            # Skip burn-in period
            if rsi_val is None or macd_val is None or atr_val is None:
                equity_curve.append(equity)
                continue

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

            result = compiled.evaluate(eval_dict)

            # Close open trade on opposing signal or any signal when in position
            if open_trade and result:
                direction, _confidence = result
                slip = close * job.slippage_pct
                exit_price = close - slip if open_trade.direction == "BUY" else close + slip

                if open_trade.direction == "BUY":
                    pnl_pct = (exit_price - open_trade.entry_price) / open_trade.entry_price
                else:
                    pnl_pct = (open_trade.entry_price - exit_price) / open_trade.entry_price

                open_trade.exit_time = candle_time
                open_trade.exit_price = exit_price
                open_trade.pnl_pct = pnl_pct
                trades.append(open_trade)

                equity *= (1 + pnl_pct)
                open_trade = None

            # Open new trade on signal
            if not open_trade and result:
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
                    pnl_pct=0.0,
                )

            equity_curve.append(equity)
            peak_equity = max(peak_equity, equity)
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
            max_drawdown = max(max_drawdown, dd)

        # Close any remaining open trade at last candle
        if open_trade and data:
            last_close = float(data[-1]["close"])
            slip = last_close * job.slippage_pct
            exit_price = last_close - slip if open_trade.direction == "BUY" else last_close + slip
            if open_trade.direction == "BUY":
                pnl_pct = (exit_price - open_trade.entry_price) / open_trade.entry_price
            else:
                pnl_pct = (open_trade.entry_price - exit_price) / open_trade.entry_price
            open_trade.exit_time = str(data[-1].get("time", ""))
            open_trade.exit_price = exit_price
            open_trade.pnl_pct = pnl_pct
            trades.append(open_trade)
            equity *= (1 + pnl_pct)
            equity_curve.append(equity)

        # Compute aggregate metrics
        total_trades = len(trades)
        wins = [t for t in trades if t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct <= 0]
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
        avg_return = sum(t.pnl_pct for t in trades) / total_trades if total_trades > 0 else 0.0

        # Sharpe ratio (annualised, assuming 1-min candles ~ 525600/yr)
        returns = [t.pnl_pct for t in trades]
        if len(returns) >= 2:
            mean_r = sum(returns) / len(returns)
            std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1))
            sharpe = (mean_r / std_r) * math.sqrt(252) if std_r > 0 else 0.0
        else:
            sharpe = 0.0

        gross_profit = sum(t.pnl_pct for t in wins)
        gross_loss = abs(sum(t.pnl_pct for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

        return BacktestResult(
            job_id=job.job_id,
            total_trades=total_trades,
            win_rate=win_rate,
            avg_return=avg_return,
            max_drawdown=max_drawdown,
            sharpe=sharpe,
            profit_factor=profit_factor,
            equity_curve=equity_curve,
            trades=trades,
        )
