MARKET_DATA_STREAM = "stream:market_data"
ORDERS_STREAM = "stream:orders"
VALIDATION_STREAM = "stream:validation"
VALIDATION_RESPONSE_STREAM = "stream:validation_response"
DLQ_STREAM = "stream:dlq"

PUBSUB_PNL_UPDATES = "pubsub:pnl_updates"
PUBSUB_PRICE_TICKS = "pubsub:price_ticks"
PUBSUB_ALERTS = "pubsub:alerts"
PUBSUB_SYSTEM_ALERTS = "pubsub:system_alerts"
PUBSUB_THRESHOLD_PROXIMITY = "pubsub:threshold_proximity"

# Agent telemetry (real-time dashboard)
PUBSUB_AGENT_TELEMETRY = "pubsub:agent_telemetry"

# HITL (Human-in-the-Loop) channels
PUBSUB_HITL_PENDING = "pubsub:hitl_pending"
HITL_RESPONSE_STREAM = "stream:hitl_response"

# Agent registry keys (per-symbol). The format-string source of truth is
# libs/core/agent_registry.py; these aliases exist so channels.py stays the
# single discoverable index of every well-known Redis key/stream.
from libs.core.agent_registry import (  # noqa: E402
    WEIGHTS_KEY as AGENT_WEIGHTS,
    OUTCOMES_KEY as AGENT_OUTCOMES,
    CLOSED_KEY as AGENT_CLOSED_OUTCOMES,
    TRACKER_KEY as AGENT_TRACKER,
)
