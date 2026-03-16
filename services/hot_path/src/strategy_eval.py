from dataclasses import dataclass
from typing import Optional, Dict
from libs.core.enums import SignalDirection
from libs.core.models import NormalisedTick
from .state import ProfileState
from libs.indicators import MACDResult

@dataclass(frozen=True, slots=True)
class EvaluatedIndicators:
    rsi: float
    macd_line: float
    signal_line: float
    histogram: float
    atr: float

@dataclass(frozen=True, slots=True)
class SignalResult:
    direction: SignalDirection
    confidence: float
    rule_matched: bool

class StrategyEvaluator:
    @staticmethod
    def evaluate(state: ProfileState, tick: NormalisedTick) -> Optional[tuple[SignalResult, EvaluatedIndicators]]:
        price = float(tick.price)

        # 1. Update Indicators Incrementally
        # We rely on previous prices matching OHLC structure if full precision is needed, 
        # but here we approximate tick close.
        # Hydration must have been completed.
        rsi_val = state.indicators.rsi.update(price)
        macd_val = state.indicators.macd.update(price)

        # Derive high/low from bid/ask if available, else estimate from prev_close
        if tick.bid is not None and tick.ask is not None:
            tick_high = float(tick.ask)
            tick_low = float(tick.bid)
        else:
            # Use previous close to create a minimal true range
            prev = state.indicators.atr.prev_close if state.indicators.atr.prev_close else price
            tick_high = max(price, prev)
            tick_low = min(price, prev)
        atr_val = state.indicators.atr.update(tick_high, tick_low, price)

        if rsi_val is None or macd_val is None or atr_val is None:
            return None # Indicators still priming

        # Pack into evaluation logic mapping
        eval_dict = {
            'rsi': rsi_val,
            'macd.macd_line': macd_val.macd_line,
            'macd.signal_line': macd_val.signal_line,
            'macd.histogram': macd_val.histogram,
            'atr': atr_val
        }
        
        eval_inds = EvaluatedIndicators(
            rsi=rsi_val,
            macd_line=macd_val.macd_line,
            signal_line=macd_val.signal_line,
            histogram=macd_val.histogram,
            atr=atr_val
        )

        # 2. Compile Rules Evaluator O(1) ops
        res = state.compiled_rules.evaluate(eval_dict)
        if res:
            direction, confidence = res
            return SignalResult(direction=direction, confidence=confidence, rule_matched=True), eval_inds
            
        return None, eval_inds
