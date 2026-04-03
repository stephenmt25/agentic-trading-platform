from typing import Dict, Optional, Tuple
from libs.indicators import create_indicator_set, IndicatorSet, MACDResult, BollingerResult


class TAConfluenceScorer:
    """Scores cross-timeframe technical alignment using independent indicator sets."""

    TIMEFRAMES = ("1m", "5m", "15m", "1h")

    def __init__(self):
        self._indicator_sets: Dict[str, IndicatorSet] = {
            tf: create_indicator_set() for tf in self.TIMEFRAMES
        }
        # Track last computed values since indicators don't expose .current
        self._last_rsi: Dict[str, Optional[float]] = {tf: None for tf in self.TIMEFRAMES}
        self._last_macd: Dict[str, Optional[MACDResult]] = {tf: None for tf in self.TIMEFRAMES}
        self._last_adx: Dict[str, Optional[float]] = {tf: None for tf in self.TIMEFRAMES}
        self._last_bb: Dict[str, Optional[BollingerResult]] = {tf: None for tf in self.TIMEFRAMES}
        self._last_chop: Dict[str, Optional[float]] = {tf: None for tf in self.TIMEFRAMES}

    def update_timeframe(self, timeframe: str, high: float, low: float, close: float,
                         volume: float = 0.0):
        """Feed a candle to the indicator set for a specific timeframe."""
        iset = self._indicator_sets.get(timeframe)
        if not iset:
            return
        rsi_val = iset.rsi.update(close)
        macd_val = iset.macd.update(close)
        iset.atr.update(high, low, close)

        if rsi_val is not None:
            self._last_rsi[timeframe] = rsi_val
        if macd_val is not None:
            self._last_macd[timeframe] = macd_val

        # New indicators
        if iset.adx:
            adx_val = iset.adx.update(high, low, close)
            if adx_val is not None:
                self._last_adx[timeframe] = adx_val
        if iset.bollinger:
            bb_val = iset.bollinger.update(close)
            if bb_val is not None:
                self._last_bb[timeframe] = bb_val
        if iset.choppiness:
            chop_val = iset.choppiness.update(high, low, close)
            if chop_val is not None:
                self._last_chop[timeframe] = chop_val
        if iset.obv:
            iset.obv.update(close, volume)

    def score(self) -> Optional[float]:
        """
        Compute confluence score from -1.0 (strong bearish) to 1.0 (strong bullish).
        Returns None if any timeframe's core indicators are still priming.
        """
        rsi_signals = []
        macd_signals = []
        bb_signals = []

        for tf in self.TIMEFRAMES:
            rsi_val = self._last_rsi[tf]
            macd_result = self._last_macd[tf]

            if rsi_val is None or macd_result is None:
                return None

            # RSI signal: continuous value based on distance from neutral (50).
            rsi_signal = (50.0 - rsi_val) / 50.0
            rsi_signals.append(max(-1.0, min(1.0, rsi_signal)))

            # MACD signal: continuous value from histogram magnitude.
            macd_line_abs = abs(macd_result.macd_line) if macd_result.macd_line else 0.0
            if macd_line_abs > 1e-10:
                macd_signal = macd_result.histogram / macd_line_abs
                macd_signal = max(-1.0, min(1.0, macd_signal))
            else:
                macd_signal = max(-1.0, min(1.0, macd_result.histogram * 1000.0)) if macd_result.histogram else 0.0
            macd_signals.append(macd_signal)

            # Bollinger %B signal: %B < 0.2 -> bullish (oversold), %B > 0.8 -> bearish (overbought)
            bb_result = self._last_bb[tf]
            if bb_result is not None:
                # Map %B to [-1, 1]: pct_b=0 -> +1 (bullish), pct_b=1 -> -1 (bearish)
                bb_signal = 1.0 - 2.0 * bb_result.pct_b
                bb_signals.append(max(-1.0, min(1.0, bb_signal)))

        # Weighted average: longer timeframes carry more weight
        weights = [0.1, 0.2, 0.3, 0.4]  # 1m, 5m, 15m, 1h
        rsi_score = sum(w * s for w, s in zip(weights, rsi_signals))
        macd_score = sum(w * s for w, s in zip(weights, macd_signals))

        # If Bollinger is available for all timeframes, include as 3rd dimension
        if len(bb_signals) == len(self.TIMEFRAMES):
            bb_score = sum(w * s for w, s in zip(weights, bb_signals))
            raw_score = (rsi_score + macd_score + bb_score) / 3.0
        else:
            raw_score = (rsi_score + macd_score) / 2.0

        # ADX trend-strength multiplier: strong trend (ADX>25) amplifies score,
        # weak trend (ADX<20) dampens it. Use 1h timeframe as primary.
        adx_1h = self._last_adx.get("1h")
        if adx_1h is not None:
            if adx_1h >= 25:
                # Scale up to 1.3x for very strong trends (ADX=50+)
                adx_mult = 1.0 + min(0.3, (adx_1h - 25) / 83.0)
            elif adx_1h < 20:
                # Dampen to 0.7x for very weak trends (ADX~0)
                adx_mult = 0.7 + 0.3 * (adx_1h / 20.0)
            else:
                adx_mult = 1.0
            raw_score *= adx_mult

        # Choppiness regime filter: high choppiness (>61.8) dampens conviction
        chop_1h = self._last_chop.get("1h")
        if chop_1h is not None and chop_1h > 61.8:
            # Linear dampen: chop=61.8 -> 1.0x, chop=100 -> 0.5x
            chop_mult = 1.0 - 0.5 * min(1.0, (chop_1h - 61.8) / 38.2)
            raw_score *= chop_mult

        return round(max(-1.0, min(1.0, raw_score)), 4)
