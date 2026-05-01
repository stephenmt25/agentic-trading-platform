"""HITL (Human-in-the-Loop) execution gate.

Inserted between risk_gate and validation in the hot-path pipeline.
Triggers on configurable conditions (trade size, low confidence, high volatility).
When triggered: publishes approval request, waits for response with timeout.
When not triggered: pass-through with zero latency impact.
Fail-safe: timeout or error → reject (block trade).
"""

import json
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID

from libs.config import settings
from libs.core.enums import Regime, HITLStatus, SignalDirection
from libs.core.schemas import HITLApprovalRequest, HITLApprovalResponse
from libs.core.models import NormalisedTick
from libs.messaging.channels import PUBSUB_HITL_PENDING, HITL_RESPONSE_STREAM
from libs.observability import get_logger
from .state import ProfileState
from .strategy_eval import SignalResult, EvaluatedIndicators
from .risk_gate import RiskGateResult

logger = get_logger("hot-path.hitl-gate")


@dataclass(frozen=True, slots=True)
class HITLGateResult:
    blocked: bool
    reason: Optional[str] = None
    hitl_triggered: bool = False


class HITLGate:
    """Human-in-the-loop gate for high-risk trades.

    Conditions that trigger HITL approval:
    1. Trade size exceeds configured percentage of allocation
    2. Signal confidence below configured threshold
    3. Market regime is HIGH_VOLATILITY
    """

    def __init__(self, redis_client, pubsub_broadcaster):
        self._redis = redis_client
        self._pubsub = pubsub_broadcaster

    async def check(
        self,
        state: ProfileState,
        signal: SignalResult,
        tick: NormalisedTick,
        indicators: EvaluatedIndicators,
        risk_result: RiskGateResult,
    ) -> HITLGateResult:
        """Check if HITL approval is required. Returns immediately if not triggered."""
        if not settings.HITL_ENABLED:
            return HITLGateResult(blocked=False)

        trigger_reason = self._should_trigger(state, signal, tick, risk_result)
        if trigger_reason is None:
            return HITLGateResult(blocked=False)

        # Build approval request
        request = HITLApprovalRequest(
            profile_id=state.profile_id,
            symbol=tick.symbol,
            side=SignalDirection(signal.direction),
            quantity=risk_result.suggested_quantity,
            price=tick.price,
            confidence=signal.confidence,
            trigger_reason=trigger_reason,
            agent_scores=await self._get_agent_scores(tick.symbol),
            risk_metrics={
                "allocation_pct": state.current_allocation_pct,
                "drawdown_pct": state.current_drawdown_pct,
                "regime": state.regime.value if state.regime else "UNKNOWN",
                "rsi": indicators.rsi,
                "atr": indicators.atr,
            },
            timestamp_us=tick.timestamp,
            source_service="hot-path",
        )

        logger.info(
            "HITL gate triggered",
            symbol=tick.symbol,
            profile_id=state.profile_id,
            reason=trigger_reason,
            confidence=signal.confidence,
        )

        # Publish request for human review
        await self._pubsub.publish(PUBSUB_HITL_PENDING, request)

        # Store request in Redis for frontend retrieval
        request_key = f"hitl:pending:{request.event_id}"
        await self._redis.set(
            request_key,
            request.model_dump_json(),
            ex=settings.HITL_TIMEOUT_S + 30,  # TTL slightly longer than timeout
        )

        # Wait for response via Redis list (BLPOP pattern, same as validation)
        response_key = f"hitl:response:{request.event_id}"
        result = await self._redis.blpop(response_key, timeout=settings.HITL_TIMEOUT_S)

        # Clean up pending key
        await self._redis.delete(request_key)

        if result is None:
            # Timeout → fail-safe: reject
            logger.warning(
                "HITL timeout — trade rejected (fail-safe)",
                request_id=str(request.event_id),
                timeout_s=settings.HITL_TIMEOUT_S,
            )
            return HITLGateResult(
                blocked=True,
                reason=f"hitl_timeout_{settings.HITL_TIMEOUT_S}s",
                hitl_triggered=True,
            )

        # Parse response
        try:
            _, response_data = result
            if isinstance(response_data, bytes):
                response_data = response_data.decode()
            data = json.loads(response_data)
            status = HITLStatus(data.get("status", "REJECTED"))
        except Exception as e:
            logger.error("Failed to parse HITL response", error=str(e))
            return HITLGateResult(blocked=True, reason="hitl_parse_error", hitl_triggered=True)

        if status == HITLStatus.APPROVED:
            logger.info("HITL approved", request_id=str(request.event_id))
            return HITLGateResult(blocked=False, hitl_triggered=True)
        else:
            logger.info(
                "HITL rejected",
                request_id=str(request.event_id),
                status=status.value,
                reason=data.get("reason", ""),
            )
            return HITLGateResult(
                blocked=True,
                reason=f"hitl_{status.value.lower()}",
                hitl_triggered=True,
            )

    def _should_trigger(
        self,
        state: ProfileState,
        signal: SignalResult,
        tick: NormalisedTick,
        risk_result: RiskGateResult,
    ) -> Optional[str]:
        """Determine if HITL approval is needed. Returns trigger reason or None."""
        # 1. Low confidence
        if signal.confidence < settings.HITL_CONFIDENCE_THRESHOLD:
            return f"low_confidence_{signal.confidence:.2f}"

        # 2. High volatility regime
        if state.regime == Regime.HIGH_VOLATILITY:
            return "high_volatility_regime"

        # 3. Large trade size relative to the profile's allocation cap.
        #
        # Units recap (the previous version mixed these and produced
        # nonsense percentages like 285%):
        #   suggested_quantity   asset units (e.g. ETH)
        #   tick.price           dollars per asset unit
        #   notional             dollars (profile capital)
        #   max_allocation_pct   fraction of notional, 0..1
        #
        # The right question is "what fraction of the allocation cap does
        # this single trade consume?" — i.e. trade_dollars / allocation_dollars.
        max_alloc = Decimal(str(state.risk_limits.max_allocation_pct))
        notional = Decimal(str(state.notional))
        price = Decimal(str(tick.price))
        qty = Decimal(str(risk_result.suggested_quantity))

        if max_alloc > 0 and notional > 0 and price > 0:
            trade_dollars = qty * price
            allocation_dollars = notional * max_alloc
            if allocation_dollars > 0:
                size_pct = trade_dollars / allocation_dollars * Decimal("100")
                if float(size_pct) > settings.HITL_SIZE_THRESHOLD_PCT:  # float-ok: comparison with float setting
                    return f"large_trade_{size_pct:.1f}pct"

        return None

    async def _get_agent_scores(self, symbol: str) -> Dict[str, Any]:
        """Fetch current agent scores from Redis for display in approval UI."""
        scores = {}
        try:
            pipe = self._redis.pipeline(transaction=False)
            pipe.get(f"agent:ta_score:{symbol}")
            pipe.get(f"agent:sentiment:{symbol}")
            pipe.get(f"agent:debate:{symbol}")
            results = await pipe.execute()

            for name, raw in zip(["ta", "sentiment", "debate"], results):
                if raw:
                    scores[name] = json.loads(raw)
        except Exception:
            pass
        return scores
