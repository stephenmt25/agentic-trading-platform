import json
from dataclasses import dataclass
from typing import Dict, Optional
from libs.observability import get_logger
from .strategy_eval import SignalResult
from libs.core.enums import SignalDirection
from libs.core.agent_registry import AgentPerformanceTracker, AGENT_DEFAULTS


@dataclass(frozen=True)
class AgentModifierTrace:
    """Trace output from apply_traced() capturing per-agent details."""
    signal: SignalResult
    agents: Dict[str, dict]  # {name: {score, weight, adjustment}}
    confidence_before: float
    confidence_after: float

logger = get_logger("hot-path.agent-modifier")


class AgentModifier:
    """Stage 3b: Modifies signal confidence based on ML agent scores from Redis.

    Reads TA alignment, sentiment polarity, and debate scores from Redis keys.
    Uses dynamic weights from agent:weights:{symbol} when available,
    falling back to defaults if missing (graceful degradation).
    """

    # Agent definitions: (redis_key_pattern, agent_name, score_extractor)
    AGENTS = [
        ("agent:ta_score:{symbol}", "ta", "_extract_ta_score"),
        ("agent:sentiment:{symbol}", "sentiment", "_extract_sentiment_score"),
        ("agent:debate:{symbol}", "debate", "_extract_debate_score"),
    ]

    def __init__(self, redis_client):
        self._redis = redis_client

    async def apply(self, symbol: str, signal: SignalResult) -> SignalResult:
        # Pipeline all Redis reads into a single round trip
        pipe = self._redis.pipeline(transaction=False)
        for key_pattern, _, _ in self.AGENTS:
            pipe.get(key_pattern.format(symbol=symbol))
        pipe.hgetall(f"agent:weights:{symbol}")
        results = await pipe.execute()

        # Last result is the weights hash
        agent_results = results[:-1]
        weights_raw = results[-1]

        # Parse dynamic weights (or use defaults)
        weights = self._parse_weights(weights_raw)

        # Compute adjustments from each agent
        total_adj = 0.0
        adjustments = {}

        for i, (_, agent_name, extractor_name) in enumerate(self.AGENTS):
            raw = agent_results[i]
            if not raw:
                continue

            extractor = getattr(self, extractor_name)
            agent_score = extractor(raw, signal)
            if agent_score is None:
                continue

            max_adj = weights.get(agent_name, AGENT_DEFAULTS.get(agent_name, 0.15))
            adj = agent_score * max_adj
            adj = max(-max_adj, min(max_adj, adj))
            total_adj += adj
            adjustments[agent_name] = adj

        # Additive adjustment with clamp
        new_confidence = signal.confidence + total_adj
        new_confidence = max(0.0, min(1.0, new_confidence))

        if adjustments:
            logger.info(
                "Agent modifier applied",
                symbol=symbol,
                adjustments=adjustments,
                weights={k: round(v, 4) for k, v in weights.items()},
                original_confidence=signal.confidence,
                new_confidence=new_confidence,
            )

        return SignalResult(
            direction=signal.direction,
            confidence=new_confidence,
            rule_matched=signal.rule_matched,
        )

    async def apply_traced(self, symbol: str, signal: SignalResult) -> AgentModifierTrace:
        """Same as apply() but returns full per-agent trace for decision logging."""
        pipe = self._redis.pipeline(transaction=False)
        for key_pattern, _, _ in self.AGENTS:
            pipe.get(key_pattern.format(symbol=symbol))
        pipe.hgetall(f"agent:weights:{symbol}")
        results = await pipe.execute()

        agent_results = results[:-1]
        weights_raw = results[-1]
        weights = self._parse_weights(weights_raw)

        confidence_before = signal.confidence
        total_adj = 0.0
        agents_trace: Dict[str, dict] = {}

        for i, (_, agent_name, extractor_name) in enumerate(self.AGENTS):
            raw = agent_results[i]
            score = None
            if raw:
                extractor = getattr(self, extractor_name)
                score = extractor(raw, signal)

            weight = weights.get(agent_name, AGENT_DEFAULTS.get(agent_name, 0.15))

            if score is not None:
                adj = score * weight
                adj = max(-weight, min(weight, adj))
                total_adj += adj
                agents_trace[agent_name] = {
                    "score": round(score, 6),
                    "weight": round(weight, 4),
                    "adjustment": round(adj, 6),
                }
            else:
                agents_trace[agent_name] = {
                    "score": None,
                    "weight": round(weight, 4),
                    "adjustment": 0.0,
                }

        new_confidence = max(0.0, min(1.0, signal.confidence + total_adj))
        new_signal = SignalResult(
            direction=signal.direction,
            confidence=new_confidence,
            rule_matched=signal.rule_matched,
        )

        return AgentModifierTrace(
            signal=new_signal,
            agents=agents_trace,
            confidence_before=confidence_before,
            confidence_after=new_confidence,
        )

    @staticmethod
    def _parse_weights(raw) -> dict:
        """Parse weights Redis hash, falling back to defaults."""
        if not raw:
            return dict(AGENT_DEFAULTS)
        result = {}
        for k, v in raw.items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            try:
                result[key] = float(val)
            except (ValueError, TypeError):
                pass
        # Fill defaults for missing agents
        for name, default in AGENT_DEFAULTS.items():
            if name not in result:
                result[name] = default
        return result

    @staticmethod
    def _extract_ta_score(raw, signal: SignalResult) -> Optional[float]:
        """Extract directional TA score. Returns value in [-1, 1] aligned with signal."""
        try:
            data = json.loads(raw)
            ta_score = float(data["score"])  # -1.0 to 1.0
            if signal.direction == SignalDirection.BUY:
                return ta_score
            elif signal.direction == SignalDirection.SELL:
                return -ta_score
            return None
        except Exception:
            return None

    @staticmethod
    def _extract_sentiment_score(raw, signal: SignalResult) -> Optional[float]:
        """Extract confidence-weighted sentiment score aligned with signal."""
        try:
            data = json.loads(raw)
            sent_score = float(data["score"])  # -1.0 to 1.0
            sent_confidence = float(data.get("confidence", 0.5))
            weighted = sent_score * sent_confidence
            if signal.direction == SignalDirection.BUY:
                return weighted
            elif signal.direction == SignalDirection.SELL:
                return -weighted
            return None
        except Exception:
            return None

    @staticmethod
    def _extract_debate_score(raw, signal: SignalResult) -> Optional[float]:
        """Extract debate consensus score aligned with signal."""
        try:
            data = json.loads(raw)
            debate_score = float(data["score"])  # -1.0 to 1.0
            debate_confidence = float(data.get("confidence", 0.5))
            weighted = debate_score * debate_confidence
            if signal.direction == SignalDirection.BUY:
                return weighted
            elif signal.direction == SignalDirection.SELL:
                return -weighted
            return None
        except Exception:
            return None
