"""Agent Performance Tracker — dynamic weight computation via EWMA accuracy.

Stores rolling (prediction_direction, actual_outcome) per agent per symbol.
Computes EWMA accuracy score, clamped to [MIN_WEIGHT, MAX_WEIGHT].
Weights are stored in Redis hash `agent:weights:{symbol}` for hot-path consumption.
"""

import json
import time
from dataclasses import dataclass
from typing import Optional, Dict, List

# Default weight constants
DEFAULT_WEIGHT_TA = 0.20
DEFAULT_WEIGHT_SENTIMENT = 0.15
DEFAULT_WEIGHT_DEBATE = 0.25
MIN_WEIGHT = 0.05
MAX_WEIGHT = 1.0
EWMA_ALPHA = 0.1  # Lower = slower adaptation, more stable weights
MIN_SAMPLES = 10   # Minimum outcome samples before overriding defaults

AGENT_DEFAULTS = {
    "ta": DEFAULT_WEIGHT_TA,
    "sentiment": DEFAULT_WEIGHT_SENTIMENT,
    "debate": DEFAULT_WEIGHT_DEBATE,
}

# Redis key patterns
WEIGHTS_KEY = "agent:weights:{symbol}"          # Hash: agent_name -> weight (float)
OUTCOMES_KEY = "agent:outcomes:{symbol}"         # Stream: {agent, direction, price, timestamp}
CLOSED_KEY = "agent:closed:{symbol}"             # Stream: {position_id, outcome, pnl_pct, agents_json}
TRACKER_KEY = "agent:tracker:{symbol}:{agent}"   # Hash: ewma_accuracy, sample_count, last_updated


def _decode_hash(d):
    """Decode bytes keys/values from a redis hgetall result.

    The shared RedisClient does not set decode_responses=True, so hgetall
    returns {bytes: bytes}. Any code that does ``hash.get("field")`` against
    that dict silently falls through to the default — masking real state.
    Use this helper before reading fields by string name.
    """
    if not d:
        return {}
    return {
        (k.decode() if isinstance(k, (bytes, bytearray)) else k):
        (v.decode() if isinstance(v, (bytes, bytearray)) else v)
        for k, v in d.items()
    }


@dataclass
class AgentOutcome:
    agent_name: str
    predicted_direction: str   # "BUY" or "SELL"
    score_at_signal: float     # agent's score at time of signal
    entry_price: float
    timestamp: float


@dataclass
class ClosedPositionOutcome:
    position_id: str
    symbol: str
    outcome: str       # "win" or "loss"
    pnl_pct: float
    agents: Dict[str, AgentOutcome]


class AgentPerformanceTracker:
    """Tracks agent prediction accuracy and computes dynamic weights.

    Used by the analyst service (weight engine) to:
    1. Record agent scores at signal time (called by execution service)
    2. Record position outcomes (called by PnL close logic)
    3. Recompute EWMA weights and write to Redis (periodic task)
    """

    def __init__(self, redis_client):
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    async def record_agent_scores(self, symbol: str, agents: Dict[str, dict]):
        """Record agent scores at time of order execution.

        agents: {"ta": {"direction": "BUY", "score": 0.65}, "sentiment": {...}}
        """
        for agent_name, data in agents.items():
            entry = {
                "agent": agent_name,
                "direction": data.get("direction", ""),
                "score": str(data.get("score", 0.0)),
                "timestamp": str(time.time()),
            }
            await self._redis.xadd(
                OUTCOMES_KEY.format(symbol=symbol), entry, maxlen=1000
            )

    async def record_position_close(self, symbol: str, position_id: str,
                                     outcome: str, pnl_pct: float,
                                     agent_scores: Dict[str, dict]):
        """Record a closed position outcome for weight feedback."""
        entry = {
            "position_id": position_id,
            "outcome": outcome,
            "pnl_pct": str(pnl_pct),
            "agents_json": json.dumps(agent_scores),
            "timestamp": str(time.time()),
        }
        await self._redis.xadd(
            CLOSED_KEY.format(symbol=symbol), entry, maxlen=5000
        )

    # ------------------------------------------------------------------
    # Weight computation
    # ------------------------------------------------------------------

    async def recompute_weights(self, symbol: str, agent_names: List[str] = None):
        """Read closed position outcomes, update EWMA accuracy, write weights.

        Called periodically by the analyst weight engine (~every 5 min).
        """
        if agent_names is None:
            agent_names = list(AGENT_DEFAULTS.keys())

        # Read recent closed outcomes (last 500)
        closed_key = CLOSED_KEY.format(symbol=symbol)
        entries = await self._redis.xrevrange(closed_key, count=500)

        if not entries:
            return  # No outcomes yet — keep defaults

        weights = {}
        for agent_name in agent_names:
            tracker_key = TRACKER_KEY.format(symbol=symbol, agent=agent_name)
            tracker_raw = _decode_hash(await self._redis.hgetall(tracker_key))

            ewma = float(tracker_raw.get("ewma_accuracy", "0.5"))
            sample_count = int(tracker_raw.get("sample_count", "0"))
            last_ts = float(tracker_raw.get("last_updated", "0"))

            # Process new outcomes since last update
            new_outcomes = 0
            for _msg_id, data in entries:
                ts = float(data.get(b"timestamp", data.get("timestamp", 0)))
                if ts <= last_ts:
                    continue

                agents_json = data.get(b"agents_json", data.get("agents_json", "{}"))
                if isinstance(agents_json, bytes):
                    agents_json = agents_json.decode()
                agents = json.loads(agents_json)

                if agent_name not in agents:
                    continue

                outcome = data.get(b"outcome", data.get("outcome", ""))
                if isinstance(outcome, bytes):
                    outcome = outcome.decode()

                agent_data = agents[agent_name]
                direction = agent_data.get("direction", "")

                # Score: did the agent's direction align with the outcome?
                if outcome == "win":
                    hit = 1.0
                else:
                    hit = 0.0

                ewma = EWMA_ALPHA * hit + (1 - EWMA_ALPHA) * ewma
                sample_count += 1
                new_outcomes += 1

            if new_outcomes > 0:
                # Update tracker state
                await self._redis.hset(tracker_key, mapping={
                    "ewma_accuracy": str(ewma),
                    "sample_count": str(sample_count),
                    "last_updated": str(time.time()),
                })

            # Compute weight from EWMA accuracy
            if sample_count >= MIN_SAMPLES:
                # Map EWMA accuracy [0, 1] to weight range
                # accuracy=0.5 (random) -> default weight, >0.5 -> higher, <0.5 -> lower
                default = AGENT_DEFAULTS.get(agent_name, 0.15)
                weight = default * (ewma / 0.5)  # 2x at perfect accuracy, 0x at zero
                weight = max(MIN_WEIGHT, min(MAX_WEIGHT, weight))
            else:
                weight = AGENT_DEFAULTS.get(agent_name, 0.15)

            weights[agent_name] = weight

        # Write computed weights to Redis hash for hot-path consumption
        weights_key = WEIGHTS_KEY.format(symbol=symbol)
        if weights:
            mapping = {k: str(v) for k, v in weights.items()}
            await self._redis.hset(weights_key, mapping=mapping)
            # Expire in 15 min — stale weights revert to defaults via graceful degradation
            await self._redis.expire(weights_key, 900)

    # ------------------------------------------------------------------
    # Reading (used by hot-path agent_modifier)
    # ------------------------------------------------------------------

    @staticmethod
    async def get_weights(redis_client, symbol: str) -> Dict[str, float]:
        """Read current agent weights from Redis. Returns defaults if missing."""
        weights_key = WEIGHTS_KEY.format(symbol=symbol)
        raw = await redis_client.hgetall(weights_key)
        if not raw:
            return dict(AGENT_DEFAULTS)

        result = {}
        for k, v in raw.items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            try:
                result[key] = max(MIN_WEIGHT, min(MAX_WEIGHT, float(val)))
            except (ValueError, TypeError):
                result[key] = AGENT_DEFAULTS.get(key, 0.15)

        # Fill in defaults for any missing agents
        for agent_name, default in AGENT_DEFAULTS.items():
            if agent_name not in result:
                result[agent_name] = default

        return result
