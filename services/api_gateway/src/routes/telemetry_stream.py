"""Server-Sent Events endpoint for agent telemetry.

Subscribes to the Redis pubsub:agent_telemetry channel and streams
events to the frontend via SSE. No authentication required — telemetry
is operational data, not user data.
"""

import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from libs.config import settings
from libs.storage import RedisClient
from libs.messaging.channels import PUBSUB_AGENT_TELEMETRY
from libs.observability import get_logger

logger = get_logger("api-gateway.telemetry-stream")

router = APIRouter(tags=["telemetry"])


@router.get("/telemetry/stream")
async def telemetry_stream():
    """SSE endpoint that streams agent telemetry events from Redis pubsub."""

    async def event_generator():
        redis = RedisClient.get_instance(settings.REDIS_URL).get_connection()
        pubsub = redis.pubsub()

        try:
            await pubsub.subscribe(PUBSUB_AGENT_TELEMETRY)
            logger.info("Telemetry SSE client connected")

            # Send initial keepalive
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.1
                )
                if message and message.get("type") == "message":
                    data_raw = message["data"]
                    data_str = (
                        data_raw.decode("utf-8")
                        if isinstance(data_raw, bytes)
                        else data_raw
                    )
                    yield f"data: {data_str}\n\n"
                else:
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Telemetry stream error", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        finally:
            try:
                await pubsub.unsubscribe(PUBSUB_AGENT_TELEMETRY)
                await pubsub.close()
            except Exception:
                pass
            logger.info("Telemetry SSE client disconnected")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "none",
        },
    )
