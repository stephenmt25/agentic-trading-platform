"""Well-known Redis channel/stream/key names. Single source of truth.

Schema for hashes/streams (required fields, expected types) lives in
``libs/observability/redis_invariants.py``. When you add a new key here,
also add a SCHEMAS entry there if you want the periodic scanner to enforce
its shape.
"""

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

# Live market microstructure for the /hot surface. Both are global (not
# per-symbol): payload carries `symbol` and frontends filter — keeps the
# WebSocket subscription list bounded and avoids per-symbol fan-out logic
# in services/ingestion. Throughput is capped by CCXT's debounce inside
# watch_order_book / watch_trades (~10Hz on Binance Spot).
PUBSUB_ORDERBOOK = "pubsub:orderbook"
PUBSUB_TRADES = "pubsub:trades"

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
