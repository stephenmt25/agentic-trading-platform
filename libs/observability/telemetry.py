"""Lightweight telemetry publisher for the Agent View dashboard.

Each service creates a TelemetryPublisher instance and calls publish()
at key points in its processing loop. Events are broadcast via Redis
Pub/Sub to the WebSocket gateway, which forwards them to the frontend.

Usage:
    telemetry = TelemetryPublisher(redis_client, "ta_agent", "scoring")
    await telemetry.start_health_loop()

    # In your main loop:
    await telemetry.emit("output_emitted", {"score": 0.73, "symbol": "BTC/USDT"}, target_agent="hot_path")
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from libs.messaging.channels import PUBSUB_AGENT_TELEMETRY
from ._logger import get_logger

logger = get_logger("telemetry")


class TelemetryPublisher:
    def __init__(self, redis_client, agent_id: str, agent_type: str):
        self._redis = redis_client
        self._agent_id = agent_id
        self._agent_type = agent_type
        self._start_time = time.monotonic()
        self._message_count = 0
        self._health_task: Optional[asyncio.Task] = None
        self._channel = PUBSUB_AGENT_TELEMETRY

    async def emit(
        self,
        event_type: str,
        payload: dict,
        source_agent: Optional[str] = None,
        target_agent: Optional[str] = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        """Publish a telemetry event to the agent telemetry channel."""
        self._message_count += 1
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": self._agent_id,
            "agent_type": self._agent_type,
            "event_type": event_type,
            "payload": payload,
        }
        if source_agent:
            event["source_agent"] = source_agent
        if target_agent:
            event["target_agent"] = target_agent
        if latency_ms is not None:
            event["latency_ms"] = latency_ms

        try:
            await self._redis.publish(self._channel, json.dumps(event))
        except Exception:
            pass  # Telemetry is best-effort, never block the service

    async def emit_health(self) -> None:
        """Publish a health check event."""
        import psutil
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / (1024 * 1024)
        cpu_pct = process.cpu_percent(interval=None)

        await self.emit("health_check", {
            "status": "healthy",
            "uptime_s": int(time.monotonic() - self._start_time),
            "memory_mb": round(mem_mb, 1),
            "cpu_pct": round(cpu_pct, 1),
            "messages_processed": self._message_count,
            "error_count_1h": 0,
        })

    async def start_health_loop(self, interval_s: float = 5.0) -> None:
        """Start a background task that publishes health checks periodically."""
        async def _loop():
            while True:
                try:
                    await self.emit_health()
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass
                await asyncio.sleep(interval_s)

        self._health_task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        """Cancel the health loop."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
