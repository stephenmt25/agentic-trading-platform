from typing import Any, Dict, Optional, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict

from .enums import EventType, OrderSide, OrderStatus, ValidationCheck, ValidationMode, ValidationVerdict
from .types import Price, ProfileId, Quantity, SymbolPair, Timestamp

class BaseEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
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
