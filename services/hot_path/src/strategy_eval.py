from dataclasses import dataclass
from typing import Optional, Dict
from libs.core.enums import SignalDirection
from libs.core.models import NormalisedTick
from .state import ProfileState
from libs.indicators import MACDResult, BollingerResult

@dataclass(frozen=True, slots=True)
class EvaluatedIndicators:
    rsi: float
    macd_line: float
    signal_line: float
    histogram: float
    atr: float
    adx: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_pct_b: Optional[float] = None
    bb_bandwidth: Optional[float] = None
    obv: Optional[float] = None
    choppiness: Optional[float] = None

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
        rsi_val = state.indicators.rsi.update(price)
        macd_val = state.indicators.macd.update(price)

        # Derive high/low from bid/ask if available, else estimate from prev_close
        if tick.bid is not None and tick.ask is not None:
            tick_high = float(tick.ask)
            tick_low = float(tick.bid)
        else:
            prev = state.indicators.atr.prev_close if state.indicators.atr.prev_close else price
            tick_high = max(price, prev)
            tick_low = min(price, prev)
        atr_val = state.indicators.atr.update(tick_high, tick_low, price)

        # New indicators (optional — None means still priming or not configured)
        adx_val = state.indicators.adx.update(tick_high, tick_low, price) if state.indicators.adx else None
        bb_val = state.indicators.bollinger.update(price) if state.indicators.bollinger else None
        obv_val = state.indicators.obv.update(price, float(tick.volume)) if state.indicators.obv else None
        chop_val = state.indicators.choppiness.update(tick_high, tick_low, price) if state.indicators.choppiness else None

        if rsi_val is None or macd_val is None or atr_val is None:
            return None # Core indicators still priming

        # Pack into evaluation logic mapping
        eval_dict = {
            'rsi': rsi_val,
            'macd.macd_line': macd_val.macd_line,
            'macd.signal_line': macd_val.signal_line,
            'macd.histogram': macd_val.histogram,
            'atr': atr_val,
        }
        # Add new indicators to eval_dict only when primed
        if adx_val is not None:
            eval_dict['adx'] = adx_val
        if bb_val is not None:
            eval_dict['bb.pct_b'] = bb_val.pct_b
            eval_dict['bb.bandwidth'] = bb_val.bandwidth
            eval_dict['bb.upper'] = bb_val.upper
            eval_dict['bb.lower'] = bb_val.lower
        if obv_val is not None:
            eval_dict['obv'] = obv_val
        if chop_val is not None:
            eval_dict['choppiness'] = chop_val

        eval_inds = EvaluatedIndicators(
            rsi=rsi_val,
            macd_line=macd_val.macd_line,
            signal_line=macd_val.signal_line,
            histogram=macd_val.histogram,
            atr=atr_val,
            adx=adx_val,
            bb_upper=bb_val.upper if bb_val else None,
            bb_lower=bb_val.lower if bb_val else None,
            bb_pct_b=bb_val.pct_b if bb_val else None,
            bb_bandwidth=bb_val.bandwidth if bb_val else None,
            obv=obv_val,
            choppiness=chop_val,
        )

        # 2. Compile Rules Evaluator O(1) ops
        res = state.compiled_rules.evaluate(eval_dict)
        if res:
            direction, confidence = res
            return SignalResult(direction=direction, confidence=confidence, rule_matched=True), eval_inds

        return None, eval_inds
