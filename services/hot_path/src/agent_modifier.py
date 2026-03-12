import json
from typing import Optional
from libs.observability import get_logger
from .strategy_eval import SignalResult
from libs.core.enums import SignalDirection

logger = get_logger("hot-path.agent-modifier")


class AgentModifier:
    """Stage 3b: Modifies signal confidence based on ML agent scores from Redis.

    Reads TA alignment and sentiment polarity from Redis keys.
    If keys are missing/expired, returns signal unchanged (graceful degradation).
    """

    def __init__(self, redis_client):
        self._redis = redis_client

    async def apply(self, symbol: str, signal: SignalResult) -> SignalResult:
        ta_factor = await self._get_ta_factor(symbol, signal)
        sentiment_factor = await self._get_sentiment_factor(symbol, signal)

        new_confidence = signal.confidence * ta_factor * sentiment_factor
        new_confidence = max(0.0, min(1.0, new_confidence))

        if ta_factor != 1.0 or sentiment_factor != 1.0:
            logger.info(
                "Agent modifier applied",
                symbol=symbol,
                ta_factor=ta_factor,
                sentiment_factor=sentiment_factor,
                original_confidence=signal.confidence,
                new_confidence=new_confidence,
            )

        return SignalResult(
            direction=signal.direction,
            confidence=new_confidence,
            rule_matched=signal.rule_matched,
        )

    async def _get_ta_factor(self, symbol: str, signal: SignalResult) -> float:
        """TA alignment factor: boosts confidence when TA agrees, dampens when opposing."""
        try:
            raw = await self._redis.get(f"agent:ta_score:{symbol}")
            if not raw:
                return 1.0
            data = json.loads(raw)
            ta_score = float(data["score"])  # -1.0 to 1.0

            # Align with signal direction
            if signal.direction == SignalDirection.BUY:
                # Positive TA score = bullish alignment → boost
                factor = 1.0 + (ta_score * 0.2)  # ±20%
            elif signal.direction == SignalDirection.SELL:
                # Negative TA score = bearish alignment → boost
                factor = 1.0 + (-ta_score * 0.2)
            else:
                factor = 1.0

            return max(0.5, min(1.5, factor))
        except Exception:
            return 1.0

    async def _get_sentiment_factor(self, symbol: str, signal: SignalResult) -> float:
        """Sentiment polarity factor: adjusts confidence based on market sentiment."""
        try:
            raw = await self._redis.get(f"agent:sentiment:{symbol}")
            if not raw:
                return 1.0
            data = json.loads(raw)
            sent_score = float(data["score"])  # -1.0 to 1.0
            sent_confidence = float(data.get("confidence", 0.5))

            # Weight by sentiment confidence
            weighted_score = sent_score * sent_confidence

            if signal.direction == SignalDirection.BUY:
                factor = 1.0 + (weighted_score * 0.15)  # ±15%
            elif signal.direction == SignalDirection.SELL:
                factor = 1.0 + (-weighted_score * 0.15)
            else:
                factor = 1.0

            return max(0.5, min(1.5, factor))
        except Exception:
            return 1.0
