"""HITL (Human-in-the-Loop) execution gate — non-blocking park/sweep model.

Inserted between risk_gate and validation in the hot-path pipeline.
Triggers on configurable conditions (trade size, low confidence, high
volatility). When not triggered: pass-through with zero latency impact.

Registry row 44 rework: the original gate did a blocking
``blpop(timeout=HITL_TIMEOUT_S)`` INSIDE the per-tick loop, so one triggered
signal stalled the whole engine (and a silently-degraded no-socket-timeout
Redis connection once froze a soak for ~13 hours). The gate now NEVER awaits
a human:

* ``check()`` emits the approval request exactly as before, then PARKS the
  signal as PENDING — in-memory (`ParkedSignal`) plus a Redis record
  (``hitl:parked:{event_id}``) carrying the deadline — and returns
  immediately with ``parked=True``.
* ``sweep()`` is called once per processor loop iteration. It does a
  NON-blocking LPOP over each pending response key, resolves
  approve/deny/parse-error responses, and applies the fail-safe timeout
  against a monotonic deadline (so a degraded Redis connection can only
  delay resolution, never hang the engine).

Fail-safe semantics are preserved exactly: timeout, deny, or a malformed
response → reject (block trade), with the same audit log lines and reason
strings as the blocking implementation. The ``PRAXIS_HITL_ENABLED=false``
bypass is unchanged.
"""

import json
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from libs.config import settings
from libs.core.enums import HITLStatus, Regime, SignalDirection
from libs.core.models import NormalisedTick
from libs.core.schemas import HITLApprovalRequest
from libs.messaging.channels import PUBSUB_HITL_PENDING
from libs.observability import get_logger

from .risk_gate import RiskGateResult
from .state import ProfileState
from .strategy_eval import EvaluatedIndicators, SignalResult

logger = get_logger("hot-path.hitl-gate")

# Operator-visible Redis record for a parked signal (deadline + context).
# Distinct from hitl:pending:{id} (the frontend approval-queue payload) so a
# crash-restarted hot_path is diagnosable: pending keys without a live parked
# record mean the in-memory park was lost and the request will TTL-expire.
PARKED_KEY_PREFIX = "hitl:parked:"


@dataclass(frozen=True, slots=True)
class HITLGateResult:
    blocked: bool
    reason: Optional[str] = None
    hitl_triggered: bool = False
    # True → the signal was parked PENDING a human response. ``blocked`` is
    # False in that case, but the caller must NOT continue the gate sequence
    # for this signal now — resolution arrives later via sweep().
    parked: bool = False


@dataclass(slots=True)
class ParkedSignal:
    """Everything needed to resume the remaining gate sequence on APPROVE."""

    request_id: str
    profile_id: str
    symbol: str
    signal: SignalResult
    tick: NormalisedTick
    indicators: EvaluatedIndicators
    risk_result: RiskGateResult
    trace: Dict[str, Any]
    parked_at_mono: float
    deadline_mono: float
    request_key: str
    response_key: str
    parked_key: str


@dataclass(frozen=True, slots=True)
class HITLResolution:
    """Outcome of a parked signal, produced by sweep()."""

    parked: ParkedSignal
    approved: bool
    reason: Optional[str] = None  # populated on deny / timeout / parse error


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
        # request_id -> ParkedSignal. In-memory source of truth for the sweep.
        self._parked: Dict[str, ParkedSignal] = {}
        # (profile_id, symbol) pairs with a park in flight. A sustained signal
        # re-fires every tick; without this dedup the async gate would emit a
        # fresh approval request per tick (and a multi-click human could
        # approve several) — the blocking gate implicitly serialised this by
        # stalling the engine.
        self._parked_pairs: set = set()

    @property
    def pending_count(self) -> int:
        return len(self._parked)

    async def check(
        self,
        state: ProfileState,
        signal: SignalResult,
        tick: NormalisedTick,
        indicators: EvaluatedIndicators,
        risk_result: RiskGateResult,
        trace: Optional[Dict[str, Any]] = None,
    ) -> HITLGateResult:
        """Check if HITL approval is required.

        Returns immediately in every case: pass-through when not triggered,
        ``parked=True`` when an approval request was emitted. Never blocks
        on a human response — that is sweep()'s job.
        """
        if not settings.HITL_ENABLED:
            return HITLGateResult(blocked=False)

        trigger_reason = self._should_trigger(state, signal, tick, risk_result)
        if trigger_reason is None:
            return HITLGateResult(blocked=False)

        pair = (state.profile_id, tick.symbol)
        if pair in self._parked_pairs:
            # An approval for this (profile, symbol) is already pending —
            # fail-safe block the duplicate rather than spamming the human
            # with one request per tick of a sustained signal.
            return HITLGateResult(
                blocked=True,
                reason="hitl_pending_existing",
                hitl_triggered=True,
            )

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
        request_id = str(request.event_id)
        request_key = f"hitl:pending:{request_id}"
        await self._redis.set(
            request_key,
            request.model_dump_json(),
            ex=settings.HITL_TIMEOUT_S + 30,  # TTL slightly longer than timeout
        )

        # Park the signal: Redis record (operator visibility + deadline) ...
        now_mono = time.monotonic()
        deadline_mono = now_mono + settings.HITL_TIMEOUT_S
        parked_key = f"{PARKED_KEY_PREFIX}{request_id}"
        await self._redis.set(
            parked_key,
            json.dumps(
                {
                    "request_id": request_id,
                    "profile_id": state.profile_id,
                    "symbol": tick.symbol,
                    "side": signal.direction.value,
                    "quantity": str(risk_result.suggested_quantity),
                    "price": str(tick.price),
                    "trigger_reason": trigger_reason,
                    "deadline_epoch": time.time() + settings.HITL_TIMEOUT_S,
                }
            ),
            ex=settings.HITL_TIMEOUT_S + 30,
        )

        # ... and in-memory (last, after every await has succeeded, so a
        # Redis failure above can't leave a half-parked entry behind).
        response_key = f"hitl:response:{request_id}"
        self._parked[request_id] = ParkedSignal(
            request_id=request_id,
            profile_id=state.profile_id,
            symbol=tick.symbol,
            signal=signal,
            tick=tick,
            indicators=indicators,
            risk_result=risk_result,
            trace=trace if trace is not None else {},
            parked_at_mono=now_mono,
            deadline_mono=deadline_mono,
            request_key=request_key,
            response_key=response_key,
            parked_key=parked_key,
        )
        self._parked_pairs.add(pair)

        return HITLGateResult(blocked=False, hitl_triggered=True, parked=True)

    async def sweep(self) -> List[HITLResolution]:
        """Resolve parked signals without blocking. Called once per processor
        loop iteration.

        Non-blocking LPOP per pending response key (never BLPOP — the tick
        loop must never await a human). No response by the monotonic deadline
        → fail-safe reject, exactly like the old blocking timeout.
        """
        if not self._parked:
            return []

        resolutions: List[HITLResolution] = []
        now = time.monotonic()
        for request_id in list(self._parked.keys()):
            parked = self._parked[request_id]
            raw = None
            try:
                raw = await self._redis.lpop(parked.response_key)
            except Exception as e:
                # Redis hiccup — leave the signal parked. The monotonic
                # deadline below still applies, so a degraded connection can
                # only delay resolution toward the fail-safe reject, never
                # hang the engine (row 44 failure mode 2).
                logger.warning(
                    "HITL response sweep read failed",
                    error=str(e),
                    request_id=request_id,
                )

            if raw is not None:
                resolutions.append(self._resolve_response(parked, raw))
            elif now >= parked.deadline_mono:
                # Timeout → fail-safe: reject
                logger.warning(
                    "HITL timeout — trade rejected (fail-safe)",
                    request_id=request_id,
                    timeout_s=settings.HITL_TIMEOUT_S,
                )
                resolutions.append(
                    HITLResolution(
                        parked=parked,
                        approved=False,
                        reason=f"hitl_timeout_{settings.HITL_TIMEOUT_S}s",
                    )
                )
            else:
                continue  # still pending — keep parked

            await self._unpark(parked)

        return resolutions

    def _resolve_response(self, parked: ParkedSignal, raw) -> HITLResolution:
        """Parse a human response. Same semantics as the blocking gate:
        malformed → fail-safe reject; APPROVED → approve; anything else →
        reject with the status in the reason."""
        try:
            if isinstance(raw, bytes):
                raw = raw.decode()
            data = json.loads(raw)
            status = HITLStatus(data.get("status", "REJECTED"))
        except Exception as e:
            logger.error("Failed to parse HITL response", error=str(e))
            return HITLResolution(
                parked=parked, approved=False, reason="hitl_parse_error"
            )

        if status == HITLStatus.APPROVED:
            logger.info("HITL approved", request_id=parked.request_id)
            return HITLResolution(parked=parked, approved=True)

        logger.info(
            "HITL rejected",
            request_id=parked.request_id,
            status=status.value,
            reason=data.get("reason", ""),
        )
        return HITLResolution(
            parked=parked,
            approved=False,
            reason=f"hitl_{status.value.lower()}",
        )

    async def _unpark(self, parked: ParkedSignal) -> None:
        self._parked.pop(parked.request_id, None)
        self._parked_pairs.discard((parked.profile_id, parked.symbol))
        try:
            await self._redis.delete(parked.request_key)
            await self._redis.delete(parked.parked_key)
        except Exception as e:
            # Both keys carry TTLs — Redis reaps them if this delete fails.
            logger.warning(
                "HITL key cleanup failed",
                error=str(e),
                request_id=parked.request_id,
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
                if (
                    float(size_pct) > settings.HITL_SIZE_THRESHOLD_PCT
                ):  # float-ok: comparison with float setting
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
