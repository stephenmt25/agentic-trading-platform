import asyncio
from typing import Optional
from libs.messaging import StreamPublisher, StreamConsumer
from libs.messaging._serialisation import decode_event
from libs.core.schemas import ValidationRequestEvent, ValidationResponseEvent
from libs.core.enums import ValidationVerdict
import time
from libs.observability import get_logger, timer

logger = get_logger("hot-path.validation")

class ValidationClient:
    __slots__ = ('_publisher', '_redis', '_req_channel', '_resp_channel', '_timeout_ms')

    def __init__(self, publisher: StreamPublisher, consumer: StreamConsumer, req_channel: str, resp_channel: str, timeout_ms: int = 50):
        self._publisher = publisher
        self._redis = consumer._redis  # Access underlying Redis for BLPOP
        self._req_channel = req_channel
        self._resp_channel = resp_channel
        self._timeout_ms = timeout_ms

    async def fast_gate(self, request: ValidationRequestEvent) -> Optional[ValidationResponseEvent]:
        # Use per-request Redis list key for 1:1 RPC via BLPOP
        resp_key = f"validation:resp:{request.event_id}"

        # Publish request to validation stream
        await self._publisher.publish(self._req_channel, request)

        # BLPOP blocks until the validation service LPUSHes a response
        timeout_s = self._timeout_ms / 1000.0
        result = await self._redis.blpop(resp_key, timeout=timeout_s)

        if result is None:
            logger.warning(f"Validation fast_gate timeout for {request.event_id}")
            return None

        # result is (key, value) tuple
        _, raw_data = result
        try:
            event = decode_event(raw_data)
            if isinstance(event, ValidationResponseEvent):
                return event
            logger.warning(f"Unexpected event type in validation response: {type(event)}")
            return None
        except Exception as e:
            logger.error(f"Failed to decode validation response: {e}")
            return None
