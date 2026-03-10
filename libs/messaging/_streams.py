from typing import List
import redis.asyncio as redis
from libs.core.schemas import BaseEvent
from ._serialisation import encode_event, decode_event

class StreamPublisher:
    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def publish(self, channel: str, event: BaseEvent) -> str:
        data = encode_event(event)
        message_id = await self._redis.xadd(channel, {"payload": data})
        return message_id

class StreamConsumer:
    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def _ensure_group(self, channel: str, group: str):
        try:
            await self._redis.xgroup_create(channel, group, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def consume(self, channel: str, group: str, consumer: str, count: int = 10, block_ms: int = 100) -> List[tuple[str, BaseEvent]]:
        await self._ensure_group(channel, group)
        streams = {channel: ">"}
        results = await self._redis.xreadgroup(group, consumer, streams, count=count, block=block_ms)
        
        events = []
        for stream_name, messages in results:
            for message_id, data in messages:
                try:
                    event = decode_event(data[b"payload"])
                    events.append((message_id, event))
                except Exception:
                    # Logging missing here but schema errors can be sent to DLQ
                    events.append((message_id, None)) 
        return events

    async def ack(self, channel: str, group: str, message_ids: List[str]):
        if message_ids:
            await self._redis.xack(channel, group, *message_ids)
