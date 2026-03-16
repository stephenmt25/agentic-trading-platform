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
        # Pipeline both Redis reads into a single round trip
        pipe = self._redis.pipeline(transaction=False)
        pipe.get(f"agent:ta_score:{symbol}")
        pipe.get(f"agent:sentiment:{symbol}")
        ta_raw, sent_raw = await pipe.execute()

        ta_adj = self._calc_ta_adjustment(ta_raw, signal)
        sentiment_adj = self._calc_sentiment_adjustment(sent_raw, signal)

        # Additive adjustment with clamp avoids multiplicative compounding
        # that can drive confidence toward zero when multiple agents disagree.
        new_confidence = signal.confidence + ta_adj + sentiment_adj
        new_confidence = max(0.0, min(1.0, new_confidence))

        if ta_adj != 0.0 or sentiment_adj != 0.0:
            logger.info(
                "Agent modifier applied",
                symbol=symbol,
                ta_adjustment=ta_adj,
                sentiment_adjustment=sentiment_adj,
                original_confidence=signal.confidence,
                new_confidence=new_confidence,
            )

        return SignalResult(
            direction=signal.direction,
            confidence=new_confidence,
            rule_matched=signal.rule_matched,
        )

    @staticmethod
    def _calc_ta_adjustment(raw, signal: SignalResult) -> float:
        """TA alignment adjustment: positive when TA agrees, negative when opposing.

        Returns an additive adjustment in [-0.20, +0.20].
        """
        try:
            if not raw:
                return 0.0
            data = json.loads(raw)
            ta_score = float(data["score"])  # -1.0 to 1.0

            if signal.direction == SignalDirection.BUY:
                adj = ta_score * 0.20  # +/-20 pct-points
            elif signal.direction == SignalDirection.SELL:
                adj = -ta_score * 0.20
            else:
                adj = 0.0

            return max(-0.20, min(0.20, adj))
        except Exception:
            return 0.0

    @staticmethod
    def _calc_sentiment_adjustment(raw, signal: SignalResult) -> float:
        """Sentiment adjustment: positive when sentiment aligns, negative when opposing.

        Returns an additive adjustment in [-0.15, +0.15].
        """
        try:
            if not raw:
                return 0.0
            data = json.loads(raw)
            sent_score = float(data["score"])  # -1.0 to 1.0
            sent_confidence = float(data.get("confidence", 0.5))

            weighted_score = sent_score * sent_confidence

            if signal.direction == SignalDirection.BUY:
                adj = weighted_score * 0.15  # +/-15 pct-points
            elif signal.direction == SignalDirection.SELL:
                adj = -weighted_score * 0.15
            else:
                adj = 0.0

            return max(-0.15, min(0.15, adj))
        except Exception:
            return 0.0
