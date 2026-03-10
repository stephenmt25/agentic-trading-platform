import json
from typing import List, Any, Dict
from libs.core.schemas import ValidationResponseEvent
from libs.core.enums import ValidationCheck, ValidationMode
from ._repository_base import BaseRepository

class ValidationRepository(BaseRepository):
    async def write_validation_event(self, profile_id: str, event: ValidationResponseEvent, signal_data: Dict[str, Any]):
        query = """
        INSERT INTO validation_events (
            event_id, profile_id, check_type, signal_data, verdict, 
            reason, check_mode, response_time_ms, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, to_timestamp($9))
        """
        await self._execute(
            query,
            event.event_id,
            profile_id,
            event.check_type.value,
            json.dumps(signal_data),
            event.verdict.value,
            event.reason,
            event.mode.value,
            event.response_time_ms,
            event.timestamp_us / 1000000.0
        )

    async def get_events_by_profile(self, profile_id: str, limit: int = 100) -> List[Any]:
        query = "SELECT * FROM validation_events WHERE profile_id = $1 ORDER BY created_at DESC LIMIT $2"
        return await self._fetch(query, profile_id, limit)

    async def get_recent_events(self, check_type: ValidationCheck, hours: int) -> List[Any]:
        query = """
        SELECT * FROM validation_events 
        WHERE check_type = $1 AND created_at >= NOW() - INTERVAL '1 hour' * $2
        """
        return await self._fetch(query, check_type.value, hours)
