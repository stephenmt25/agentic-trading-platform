import asyncio
import msgpack
import redis.asyncio as redis
from libs.core.schemas import BaseEvent
from libs.messaging._serialisation import encode_event
from typing import Callable, Awaitable

class PubSubBroadcaster:
    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def publish(self, channel: str, event: BaseEvent):
        # Use msgpack for faster internal pubsub serialization
        data = encode_event(event)
        await self._redis.publish(channel, data)

class PubSubSubscriber:
    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client
        self._pubsub = redis_client.pubsub()

    async def subscribe(self, channel: str, callback: Callable[[str], Awaitable[None]]):
        await self._pubsub.subscribe(channel)
        while True:
            message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message:
                await callback(message['data'])
            else:
                await asyncio.sleep(0.01)
