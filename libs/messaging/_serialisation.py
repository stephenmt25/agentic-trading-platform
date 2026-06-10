from typing import Any, Dict

import msgpack

from libs.core.exceptions import SchemaVersionMismatchError
from libs.core.schemas import (
    AlertEvent,
    BaseEvent,
    CircuitBreakerEvent,
    MarketTickEvent,
    OrderApprovedEvent,
    OrderBookSnapshotEvent,
    OrderExecutedEvent,
    OrderRejectedEvent,
    PnlUpdateEvent,
    SignalEvent,
    ThresholdProximityEvent,
    TradeTickEvent,
    ValidationRequestEvent,
    ValidationResponseEvent,
)

EVENT_MAP = {
    "MARKET_TICK": MarketTickEvent,
    "SIGNAL_GENERATED": SignalEvent,
    "ORDER_APPROVED": OrderApprovedEvent,
    "ORDER_REJECTED": OrderRejectedEvent,
    "ORDER_EXECUTED": OrderExecutedEvent,
    "VALIDATION_PROCEED": ValidationRequestEvent,  # Fallback, same type structure roughly, handled manually
    "VALIDATION_BLOCK": ValidationRequestEvent,  # But validation response differs
    "PNL_UPDATE": PnlUpdateEvent,
    "CIRCUIT_BREAKER_TRIGGERED": CircuitBreakerEvent,
    "ALERT_AMBER": AlertEvent,
    "ALERT_RED": AlertEvent,
    "SYSTEM_ALERT": AlertEvent,
    "THRESHOLD_PROXIMITY": ThresholdProximityEvent,
    "ORDERBOOK_SNAPSHOT": OrderBookSnapshotEvent,
    "TRADE_TICK": TradeTickEvent,
}

# Add explicitly validation event schemas that share same enum name but different types
# We will use class type for serialization


def encode_event(event: BaseEvent) -> bytes:
    # Fast path: use __dict__ directly for internal events, avoiding Pydantic overhead
    try:
        raw = {}
        for k, v in event.__dict__.items():
            # Convert non-serializable types for msgpack
            if hasattr(v, "value"):  # Enum
                raw[k] = v.value
            elif hasattr(v, "hex"):  # UUID
                raw[k] = str(v)
            else:
                raw[k] = v
        raw["__type__"] = event.__class__.__name__
        return msgpack.packb(raw, use_bin_type=True, default=str)
    except Exception:
        # Fallback to Pydantic model_dump for complex cases
        data = event.model_dump(mode="json")
        return msgpack.packb(
            {"__type__": event.__class__.__name__, **data}, use_bin_type=True
        )


def decode_event(data: bytes) -> BaseEvent:
    raw: Dict[str, Any] = msgpack.unpackb(data, raw=False)
    if not isinstance(raw, dict) or "__type__" not in raw:
        raise ValueError("Invalid packed event format")

    event_type_str = raw.pop("__type__")
    schema_version = raw.get("schema_version", 1)

    if schema_version != 1:
        raise SchemaVersionMismatchError(
            f"Unsupported schema version: {schema_version}"
        )

    models = {
        "BaseEvent": BaseEvent,
        "MarketTickEvent": MarketTickEvent,
        "SignalEvent": SignalEvent,
        "OrderApprovedEvent": OrderApprovedEvent,
        "OrderRejectedEvent": OrderRejectedEvent,
        "OrderExecutedEvent": OrderExecutedEvent,
        "ValidationRequestEvent": ValidationRequestEvent,
        "ValidationResponseEvent": ValidationResponseEvent,
        "PnlUpdateEvent": PnlUpdateEvent,
        "CircuitBreakerEvent": CircuitBreakerEvent,
        "AlertEvent": AlertEvent,
        "ThresholdProximityEvent": ThresholdProximityEvent,
        "OrderBookSnapshotEvent": OrderBookSnapshotEvent,
        "TradeTickEvent": TradeTickEvent,
    }

    if event_type_str not in models:
        raise ValueError(f"Unknown event type: {event_type_str}")

    return models[event_type_str].model_validate(raw)
