"""Fire-and-forget writer for trade decision traces.

Never blocks or crashes the hot path — all errors are logged and swallowed.
"""

import uuid
from libs.observability import get_logger
from libs.storage.repositories.decision_repo import DecisionRepository

logger = get_logger("hot-path.decision-writer")


class DecisionTraceWriter:
    def __init__(self, repo: DecisionRepository):
        self._repo = repo

    async def write(self, trace: dict) -> None:
        """Persist a decision trace. Fails silently on error."""
        try:
            await self._repo.write_decision(
                event_id=trace.get("event_id") or uuid.uuid4(),
                profile_id=uuid.UUID(trace["profile_id"]),
                symbol=trace["symbol"],
                outcome=trace["outcome"],
                input_price=trace["input_price"],
                input_volume=trace.get("input_volume"),
                indicators=trace.get("indicators", {}),
                strategy=trace.get("strategy", {}),
                regime=trace.get("regime"),
                agents=trace.get("agents"),
                gates=trace.get("gates", {}),
                profile_rules=trace.get("profile_rules", {}),
                order_id=uuid.UUID(trace["order_id"]) if trace.get("order_id") else None,
            )
        except Exception:
            logger.exception("Failed to write decision trace", symbol=trace.get("symbol"))
