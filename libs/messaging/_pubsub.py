import asyncio
import json
import redis.asyncio as redis
from libs.core.schemas import BaseEvent
from typing import Callable, Awaitable

class PubSubBroadcaster:
    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def publish(self, channel: str, event: BaseEvent):
        # PubSub uses JSON format for websocket ease
        data = event.model_dump_json()
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
