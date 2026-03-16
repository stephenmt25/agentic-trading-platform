from typing import List, Optional
from uuid import UUID
from libs.core.models import TradingProfile, RiskLimits
from ._repository_base import BaseRepository
import json

class ProfileRepository(BaseRepository):
    async def get_active_profiles_for_user(self, user_id: str) -> list:
        query = """
        SELECT * FROM trading_profiles
        WHERE user_id = $1 AND is_active = true AND deleted_at IS NULL
        ORDER BY created_at DESC
        """
        records = await self._fetch(query, UUID(user_id))
        return [dict(r) for r in records]

    async def get_all_profiles_for_user(self, user_id: str) -> list:
        query = """
        SELECT * FROM trading_profiles
        WHERE user_id = $1
        ORDER BY created_at DESC
        """
        records = await self._fetch(query, UUID(user_id))
        return [dict(r) for r in records]

    async def get_profile(self, profile_id: str) -> Optional[dict]:
        query = "SELECT * FROM trading_profiles WHERE profile_id = $1"
        record = await self._fetchrow(query, UUID(profile_id))
        if record:
            return dict(record)
        return None

    async def get_profile_for_user(self, profile_id: str, user_id: str) -> Optional[dict]:
        query = "SELECT * FROM trading_profiles WHERE profile_id = $1 AND user_id = $2"
        record = await self._fetchrow(query, UUID(profile_id), UUID(user_id))
        if record:
            return dict(record)
        return None

    async def create_profile(self, user_id: str, name: str, strategy_rules: dict,
                             risk_limits: dict, allocation_pct: float,
                             exchange_key_ref: str = "paper") -> dict:
        query = """
        INSERT INTO trading_profiles (user_id, name, strategy_rules, risk_limits, allocation_pct, exchange_key_ref, is_active)
        VALUES ($1, $2, $3, $4, $5, $6, true)
        RETURNING *
        """
        record = await self._fetchrow(
            query,
            UUID(user_id),
            name,
            json.dumps(strategy_rules),
            json.dumps(risk_limits),
            allocation_pct,
            exchange_key_ref
        )
        return dict(record) if record else {}

    async def update_profile(self, profile_id: str, user_id: str, strategy_rules: dict, is_active: bool = True) -> dict:
        query = """
        UPDATE trading_profiles
        SET strategy_rules = $1, is_active = $2, updated_at = NOW()
        WHERE profile_id = $3 AND user_id = $4
        RETURNING *
        """
        record = await self._fetchrow(
            query,
            json.dumps(strategy_rules),
            is_active,
            UUID(profile_id),
            UUID(user_id)
        )
        return dict(record) if record else {}

    async def toggle_active(self, profile_id: str, user_id: str, is_active: bool) -> dict:
        query = """
        UPDATE trading_profiles SET is_active = $1, updated_at = NOW()
        WHERE profile_id = $2 AND user_id = $3
        RETURNING *
        """
        record = await self._fetchrow(query, is_active, UUID(profile_id), UUID(user_id))
        return dict(record) if record else {}

    async def soft_delete(self, profile_id: str, user_id: str) -> dict:
        query = """
        UPDATE trading_profiles
        SET is_active = false, deleted_at = NOW(), updated_at = NOW()
        WHERE profile_id = $1 AND user_id = $2
        RETURNING *
        """
        record = await self._fetchrow(query, UUID(profile_id), UUID(user_id))
        return dict(record) if record else {}

    async def get_profiles_for_symbol(self, symbol: str) -> list:
        query = "SELECT * FROM trading_profiles WHERE is_active = true AND deleted_at IS NULL"
        records = await self._fetch(query)
        return [dict(r) for r in records]

    # Legacy methods kept for inter-service use (not user-facing)
    async def get_active_profiles(self) -> list:
        query = "SELECT * FROM trading_profiles WHERE is_active = true ORDER BY created_at DESC"
        records = await self._fetch(query)
        return [dict(r) for r in records]

    async def get_all_profiles(self) -> list:
        query = "SELECT * FROM trading_profiles ORDER BY created_at DESC"
        records = await self._fetch(query)
        return [dict(r) for r in records]
