# Messaging and Streams

## Purpose and Responsibility

The Messaging library provides the platform's inter-service communication backbone. It wraps Redis Streams for durable, ordered, consumer-group-based message delivery; Redis Pub/Sub for low-latency broadcast notifications; a dead-letter queue for failed messages; and a msgpack-based serialisation layer that maps between Python event objects and wire format. Every service in the Aion Trading Platform uses this library to publish and consume events.

## Public Interface

### Stream Operations

```python
class StreamPublisher:
    def __init__(self, redis_client: redis.Redis)
    async def publish(self, channel: str, event: BaseEvent) -> str

class StreamConsumer:
    def __init__(self, redis_client: redis.Redis)
    async def consume(self, channel: str, group: str, consumer: str,
                      count: int = 10, block_ms: int = 100) -> List[tuple[str, BaseEvent]]
    async def ack(self, channel: str, group: str, message_ids: List[str]) -> None
```

### Pub/Sub Operations

```python
class PubSubBroadcaster:
    def __init__(self, redis_client: redis.Redis)
    async def publish(self, channel: str, event: BaseEvent) -> None

class PubSubSubscriber:
    def __init__(self, redis_client: redis.Redis)
    async def subscribe(self, channel: str, callback: Callable[[str], Awaitable[None]]) -> None
```

### Dead Letter Queue

```python
class DeadLetterQueue:
    def __init__(self, redis_client: redis.Redis, dlq_channel: str = "stream:dlq")
    async def send_to_dlq(self, original_channel: str, event_data: bytes, error: str) -> None
    async def replay_from_dlq(self, target_channel: str, count: int = 10) -> None
```

### Serialisation

```python
def encode_event(event: BaseEvent) -> bytes
def decode_event(data: bytes) -> BaseEvent
```

### Channel Constants

```python
# Streams (durable, ordered)
MARKET_DATA_STREAM       = "stream:market_data"
ORDERS_STREAM            = "stream:orders"
VALIDATION_STREAM        = "stream:validation"
VALIDATION_RESPONSE_STREAM = "stream:validation_response"
DLQ_STREAM               = "stream:dlq"

# Pub/Sub (fire-and-forget broadcast)
PUBSUB_PNL_UPDATES       = "pubsub:pnl_updates"
PUBSUB_PRICE_TICKS       = "pubsub:price_ticks"
PUBSUB_ALERTS            = "pubsub:alerts"
PUBSUB_SYSTEM_ALERTS     = "pubsub:system_alerts"
PUBSUB_THRESHOLD_PROXIMITY = "pubsub:threshold_proximity"
```

## Internal Architecture

### Stream Consumer Groups

`StreamConsumer` uses Redis consumer groups (`XREADGROUP`) for durable, at-least-once delivery. On first consume from a new channel/group pair, it auto-creates the consumer group via `XGROUP CREATE` with `mkstream=True`. The `BUSYGROUP` error (group already exists) is caught and ignored, making the operation idempotent.

Known group names are cached in a `_known_groups` set to avoid redundant `XGROUP CREATE` calls on subsequent consume iterations.

Messages are read with the `>` ID (new messages only) and returned as a list of `(message_id, BaseEvent)` tuples. If a message fails to decode, it is included as `(message_id, None)` -- the caller is responsible for handling this case.

### Pub/Sub

`PubSubBroadcaster` wraps `redis.publish()` with event serialisation. Messages are fire-and-forget with no delivery guarantee.

`PubSubSubscriber` wraps `redis.pubsub()` and provides a callback-based subscription loop. It polls for messages with a 100ms timeout and sleeps for 10ms between empty polls to yield the event loop.

### Serialisation (msgpack)

All events are serialised using msgpack for compact binary encoding. The serialisation layer handles two concerns:

**Encoding** (`encode_event`):
1. Fast path: Iterates `event.__dict__` directly, converting enums to `.value`, UUIDs to strings, and everything else as-is. Injects a `__type__` field with the class name.
2. Fallback: If the fast path fails, uses Pydantic's `model_dump(mode="json")` for complex cases.
3. Packs the result with `msgpack.packb(use_bin_type=True, default=str)`.

**Decoding** (`decode_event`):
1. Unpacks with `msgpack.unpackb(raw=False)`.
2. Extracts the `__type__` field and looks up the corresponding Pydantic model class in a hardcoded registry.
3. Validates schema version (must be 1, raises `SchemaVersionMismatchError` otherwise).
4. Calls `model.model_validate(raw)` to construct the event object.

Supported event types: `MarketTickEvent`, `SignalEvent`, `OrderApprovedEvent`, `OrderRejectedEvent`, `OrderExecutedEvent`, `ValidationRequestEvent`, `ValidationResponseEvent`, `PnlUpdateEvent`, `CircuitBreakerEvent`, `AlertEvent`, `ThresholdProximityEvent`.

### Dead Letter Queue

`DeadLetterQueue` writes failed messages to `stream:dlq` with the original channel name, error description, and raw payload. The `replay_from_dlq` method is defined but not yet implemented.

## Dependencies

### Infrastructure Dependencies

- **Redis** -- Streams (XADD, XREADGROUP, XACK, XGROUP CREATE), Pub/Sub (PUBLISH, SUBSCRIBE), and the DLQ stream

### Library Dependencies

- `msgpack` -- Binary serialisation
- `redis.asyncio` -- Async Redis client
- `libs.core.schemas` -- All event Pydantic models
- `libs.core.exceptions` -- `SchemaVersionMismatchError`

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Consumer group already exists | `BUSYGROUP` error caught and ignored |
| Message decode failure in consumer | Event returned as `None` in the tuple; no error raised |
| Unknown event type during decode | `ValueError` raised |
| Unsupported schema version | `SchemaVersionMismatchError` raised |
| Encode fast path failure | Falls back to Pydantic `model_dump` |

## Configuration

| Setting | Source | Default | Description |
|---------|--------|---------|-------------|
| Channel names | `libs.messaging.channels` | See constants above | Hardcoded stream and pubsub channel names |
| DLQ channel | `DeadLetterQueue` constructor | `"stream:dlq"` | Dead letter queue stream name |
| Consumer block time | Caller-specified | `100ms` | Default XREADGROUP block duration |
| Consumer batch size | Caller-specified | `10` | Default messages per consume call |
| PubSub poll timeout | Hardcoded | `100ms` | `get_message` timeout in subscriber |
| PubSub sleep interval | Hardcoded | `10ms` | Yield between empty polls |

## Known Issues and Technical Debt

1. **DLQ replay not implemented** -- `DeadLetterQueue.replay_from_dlq()` is a stub (`pass`). Failed messages can be written to the DLQ but cannot be replayed.

2. **No DLQ routing in consumers** -- When `StreamConsumer.consume()` encounters a decode failure, it returns `None` but does not route the raw message to the DLQ. The caller must handle this (and currently no caller does).

3. **Hardcoded event type registry** -- Both `encode_event` and `decode_event` maintain separate hardcoded mappings of event type names to classes. Adding a new event type requires updating both the `EVENT_MAP` dict and the `models` dict in `decode_event`.

4. **PubSubSubscriber is a blocking loop** -- `subscribe()` runs an infinite loop with no cancellation mechanism. The caller must cancel the task externally.

5. **No stream trimming** -- Streams grow unbounded. There is no `MAXLEN` parameter on `XADD` and no separate trimming job.

6. **Missing consumer logging** -- Decode failures in `StreamConsumer.consume()` are caught with a bare `except Exception` and produce no log output. The comment acknowledges this: "Logging missing here."

7. **Schema version locked to 1** -- The schema version check rejects anything other than version 1 with no migration path. Future schema evolution will require updating every deployed consumer simultaneously or implementing version-aware decoding.

8. **PubSub serialisation uses encode_event** -- Pub/Sub messages go through the same msgpack encoding as stream messages, even though the comment in `PubSubBroadcaster` mentions "faster internal pubsub serialization." There is no performance differentiation.
