import asyncio
from typing import Optional
from libs.messaging import StreamPublisher, StreamConsumer
from libs.core.schemas import ValidationRequestEvent, ValidationResponseEvent
from libs.core.enums import ValidationVerdict
import time
from libs.observability import get_logger, timer

logger = get_logger("hot-path.validation")

class ValidationClient:
    __slots__ = ('_publisher', '_consumer', '_req_channel', '_resp_channel', '_timeout_ms')

    def __init__(self, publisher: StreamPublisher, consumer: StreamConsumer, req_channel: str, resp_channel: str, timeout_ms: int = 50):
        self._publisher = publisher
        self._consumer = consumer
        self._req_channel = req_channel
        self._resp_channel = resp_channel
        self._timeout_ms = timeout_ms

    async def fast_gate(self, request: ValidationRequestEvent) -> Optional[ValidationResponseEvent]:
        start = time.perf_counter()
        
        # Publish
        await self._publisher.publish(self._req_channel, request)
        
        # We need a dedicated group/consumer or use Pub/Sub ideally for RPC pattern
        # For simplicity in Phase 1 stream based: loop reading specific event id (Inefficient if high volume,
        # better to use a dedicated Redis Pub/Sub response topic per gateway request, or Redis List blocking pop)
        
        # Optimized trick for Phase 1: Wait on list LPUSH for our specific request
        # Redis BLPOP is much faster and more isolated here.
        # But per design doc: wait on VALIDATION_RESPONSE_STREAM matching event_id
        
        deadline = time.time() + (self._timeout_ms / 1000.0)
        
        while time.time() < deadline:
            remaining = int((deadline - time.time()) * 1000)
            if remaining <= 0:
                break
                
            events = await self._consumer.consume(
                self._resp_channel, 
                group="hotpath_validator", 
                consumer=f"consumer_{request.event_id}", # Hacky consumer isolation for demo
                count=1,
                block_ms=remaining
            )
            
            for msg_id, ev in events:
                if ev and isinstance(ev, ValidationResponseEvent) and ev.event_id == request.event_id:
                    # Found it
                    await self._consumer.ack(self._resp_channel, "hotpath_validator", [msg_id])
                    return ev
                
                # if not matching, ideally don't ack or send back to queue, implies design contention
                # In robust versions, we use Redis Lists for 1:1 RPC or separate response channels
                
            await asyncio.sleep(0.001)

        logger.warning(f"Validation fast_gate timeout for {request.event_id}")
        return None
