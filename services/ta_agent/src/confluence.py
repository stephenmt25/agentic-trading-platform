from typing import Dict, Optional, Tuple
from libs.indicators import create_indicator_set, IndicatorSet, MACDResult


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

    def update_timeframe(self, timeframe: str, high: float, low: float, close: float):
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

    def score(self) -> Optional[float]:
        """
        Compute confluence score from -1.0 (strong bearish) to 1.0 (strong bullish).
        Returns None if any timeframe indicators are still priming.
        """
        rsi_signals = []
        macd_signals = []

        for tf in self.TIMEFRAMES:
            rsi_val = self._last_rsi[tf]
            macd_result = self._last_macd[tf]

            if rsi_val is None or macd_result is None:
                return None

            # RSI signal: bullish < 40, bearish > 60, neutral otherwise
            if rsi_val < 40:
                rsi_signals.append(1.0)
            elif rsi_val > 60:
                rsi_signals.append(-1.0)
            else:
                rsi_signals.append(0.0)

            # MACD signal: bullish if histogram > 0, bearish if < 0
            if macd_result.histogram > 0:
                macd_signals.append(1.0)
            elif macd_result.histogram < 0:
                macd_signals.append(-1.0)
            else:
                macd_signals.append(0.0)

        # Weighted average: longer timeframes carry more weight
        weights = [0.1, 0.2, 0.3, 0.4]  # 1m, 5m, 15m, 1h
        rsi_score = sum(w * s for w, s in zip(weights, rsi_signals))
        macd_score = sum(w * s for w, s in zip(weights, macd_signals))

        # Combined: 50% RSI alignment + 50% MACD alignment
        return round((rsi_score + macd_score) / 2, 4)
