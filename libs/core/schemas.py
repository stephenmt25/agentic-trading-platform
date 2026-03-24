from typing import Any, Dict, Optional, Literal
from uuid import UUID, uuid4
import os
import threading
from pydantic import BaseModel, Field, ConfigDict

from .enums import EventType, OrderSide, OrderStatus, ValidationCheck, ValidationMode, ValidationVerdict, HITLStatus
from .types import Price, ProfileId, Quantity, SymbolPair, Timestamp


def _make_monotonic_id_factory():
    """Create a fast monotonic ID generator using process ID + counter.

    Produces valid UUID-shaped strings without syscalls.
    Format: 00000000-0000-4pid-8cnt-cntcntcntcnt
    """
    _pid = os.getpid() & 0xFFF
    _counter = 0
    _lock = threading.Lock()

    def _next_id() -> UUID:
        nonlocal _counter
        with _lock:
            _counter += 1
            c = _counter
        # Build a UUID from pid + counter deterministically
        high = (c >> 48) & 0xFFFFFFFF
        mid = (c >> 32) & 0xFFFF
        low = c & 0xFFFFFFFFFFFF
        hex_str = f"{high:08x}-{mid:04x}-4{_pid:03x}-8000-{low:012x}"
        return UUID(hex_str)

    return _next_id


_monotonic_id = _make_monotonic_id_factory()


class BaseEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=_monotonic_id)
    event_type: EventType
    timestamp_us: Timestamp
    source_service: str
    schema_version: int = 1

class MarketTickEvent(BaseEvent):
    event_type: Literal[EventType.MARKET_TICK] = EventType.MARKET_TICK
    symbol: SymbolPair
    exchange: str
    price: Price
    volume: Quantity

class SignalEvent(BaseEvent):
    event_type: Literal[EventType.SIGNAL_GENERATED] = EventType.SIGNAL_GENERATED
    profile_id: ProfileId
    symbol: SymbolPair
    direction: Literal["BUY", "SELL", "ABSTAIN"]
    confidence: float

class OrderApprovedEvent(BaseEvent):
    event_type: Literal[EventType.ORDER_APPROVED] = EventType.ORDER_APPROVED
    profile_id: ProfileId
    symbol: SymbolPair
    side: OrderSide
    quantity: Quantity
    price: Price

class OrderRejectedEvent(BaseEvent):
    event_type: Literal[EventType.ORDER_REJECTED] = EventType.ORDER_REJECTED
    profile_id: ProfileId
    symbol: SymbolPair
    reason: str

class OrderExecutedEvent(BaseEvent):
    event_type: Literal[EventType.ORDER_EXECUTED] = EventType.ORDER_EXECUTED
    order_id: UUID
    profile_id: ProfileId
    symbol: SymbolPair
    side: OrderSide
    fill_price: Price
    quantity: Quantity

class ValidationRequestEvent(BaseEvent):
    event_type: Literal[EventType.VALIDATION_PROCEED, EventType.VALIDATION_BLOCK] = EventType.VALIDATION_PROCEED
    profile_id: ProfileId
    symbol: SymbolPair
    check_type: ValidationCheck
    payload: Dict[str, Any]

class ValidationResponseEvent(BaseEvent):
    event_type: Literal[EventType.VALIDATION_PROCEED, EventType.VALIDATION_BLOCK] = EventType.VALIDATION_PROCEED
    verdict: ValidationVerdict
    check_type: ValidationCheck
    mode: ValidationMode
    reason: Optional[str] = None
    response_time_ms: float

class PnlUpdateEvent(BaseEvent):
    event_type: Literal[EventType.PNL_UPDATE] = EventType.PNL_UPDATE
    profile_id: ProfileId
    symbol: SymbolPair
    gross_pnl: Price
    net_pnl: Price
    pct_return: float

class CircuitBreakerEvent(BaseEvent):
    event_type: Literal[EventType.CIRCUIT_BREAKER_TRIGGERED] = EventType.CIRCUIT_BREAKER_TRIGGERED
    profile_id: ProfileId
    reason: str

class AlertEvent(BaseEvent):
    event_type: Literal[EventType.ALERT_AMBER, EventType.ALERT_RED, EventType.SYSTEM_ALERT, EventType.REGIME_DISAGREEMENT]
    message: str
    level: str
    profile_id: Optional[ProfileId] = None

class ThresholdProximityEvent(BaseEvent):
    event_type: Literal[EventType.THRESHOLD_PROXIMITY] = EventType.THRESHOLD_PROXIMITY
    profile_id: ProfileId
    symbol: SymbolPair
    indicator_name: str
    current_value: float
    trigger_threshold: float
    proximity_pct: float


class HITLApprovalRequest(BaseEvent):
    event_type: Literal[EventType.HITL_PENDING] = EventType.HITL_PENDING
    profile_id: ProfileId
    symbol: SymbolPair
    side: OrderSide
    quantity: Quantity
    price: Price
    confidence: float
    trigger_reason: str
    agent_scores: Dict[str, Any] = Field(default_factory=dict)
    risk_metrics: Dict[str, Any] = Field(default_factory=dict)


class HITLApprovalResponse(BaseEvent):
    event_type: Literal[EventType.HITL_RESPONSE] = EventType.HITL_RESPONSE
    request_id: UUID
    status: HITLStatus
    reviewer: Optional[str] = None
    reason: Optional[str] = None
