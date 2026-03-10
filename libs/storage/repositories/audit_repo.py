import json
from libs.core.schemas import BaseEvent
from ._repository_base import BaseRepository

class AuditRepository(BaseRepository):
    async def write_audit_event(self, event: BaseEvent, payload: dict):
        query = """
        INSERT INTO audit_log (event_id, event_type, source_service, profile_id, payload, created_at)
        VALUES ($1, $2, $3, $4, $5, to_timestamp($6))
        """
        await self._execute(
            query,
            event.event_id,
            event.event_type.value,
            event.source_service,
            # Handle optionals internally if base event provides
            payload.get("profile_id", None),
            json.dumps(payload),
            event.timestamp_us / 1000000.0
        )
