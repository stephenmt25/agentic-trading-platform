from typing import Dict, Any
import structlog
import time

logger = structlog.get_logger("system.metrics")

class MetricsCollector:
    @staticmethod
    def track_latency(op: str, duration_ms: float, tags: Dict[str, Any] = None):
        t = tags or {}
        # Structured log emitted which can be parsed by Datadog or Prometheus log bridge
        logger.info(
            "metrics.latency",
            operation=op,
            duration_ms=duration_ms,
            **t
        )

    @staticmethod
    def increment_counter(metric: str, tags: Dict[str, Any] = None):
        t = tags or {}
        logger.info(
            "metrics.counter",
            metric=metric,
            count=1,
            **t
        )

    @staticmethod
    def set_gauge(metric: str, value: float, tags: Dict[str, Any] = None):
        t = tags or {}
        logger.info(
            "metrics.gauge",
            metric=metric,
            value=value,
            **t
        )

class timer:
    """Context manager to easily track latency of a block."""
    def __init__(self, op_name: str, **tags):
        self.op_name = op_name
        self.tags = tags
        self.start = 0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start) * 1000
        MetricsCollector.track_latency(self.op_name, duration_ms, self.tags)
