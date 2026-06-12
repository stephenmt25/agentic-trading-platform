"""Repository for user-level risk defaults.

Backed by migration 021_user_risk_defaults.sql. Returns dicts that the
route layer feeds into UserRiskDefaultsPayload for validation/defaulting.
"""

import json
import uuid
from typing import Any, Dict, Optional

from ._repository_base import BaseRepository


class UserRiskDefaultsRepository(BaseRepository):
    async def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return persisted defaults + updated_at, or None if the user has never saved."""
        row = await self._fetchrow(
            "SELECT defaults, updated_at FROM user_risk_defaults WHERE user_id = $1",
            uuid.UUID(user_id),
        )
        if row is None:
            return None
        defaults = row["defaults"]
        if isinstance(defaults, str):
            defaults = json.loads(defaults)
        return {"defaults": defaults, "updated_at": row["updated_at"]}

    async def upsert(self, user_id: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update defaults for the given user; returns the upserted row."""
        # Annotated Any: INSERT ... RETURNING always yields a row, so the
        # Optional from _fetchrow never materialises here.
        row: Any = await self._fetchrow(
            """
            INSERT INTO user_risk_defaults (user_id, defaults, updated_at)
            VALUES ($1, $2::jsonb, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET defaults = EXCLUDED.defaults,
                updated_at = NOW()
            RETURNING defaults, updated_at
            """,
            uuid.UUID(user_id),
            json.dumps(defaults),
        )
        out_defaults = row["defaults"]
        if isinstance(out_defaults, str):
            out_defaults = json.loads(out_defaults)
        return {"defaults": out_defaults, "updated_at": row["updated_at"]}
