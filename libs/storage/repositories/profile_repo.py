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

    async def update_profile(
        self,
        profile_id: str,
        user_id: str,
        strategy_rules: dict,
        is_active: bool = True,
        risk_limits: Optional[dict] = None,
        allocation_pct: Optional[float] = None,
    ) -> dict:
        """Update strategy rules + active flag, and optionally risk_limits / allocation_pct.

        risk_limits is merged with existing JSONB rather than overwritten — callers
        only need to send the keys they want to change. allocation_pct is a scalar
        update (None = leave unchanged).
        """
        # Build the SET clause dynamically so unspecified fields aren't touched.
        sets = ["strategy_rules = $1", "is_active = $2", "updated_at = NOW()"]
        args: list = [json.dumps(strategy_rules), is_active]
        idx = 3

        if risk_limits is not None:
            # JSONB merge keeps existing keys (max_drawdown_pct etc.) when only
            # one knob like max_allocation_pct changes.
            sets.append(f"risk_limits = COALESCE(risk_limits, '{{}}'::jsonb) || ${idx}::jsonb")
            args.append(json.dumps(risk_limits))
            idx += 1

        if allocation_pct is not None:
            sets.append(f"allocation_pct = ${idx}")
            args.append(allocation_pct)
            idx += 1

        args.append(UUID(profile_id))
        args.append(UUID(user_id))
        query = f"""
        UPDATE trading_profiles
        SET {', '.join(sets)}
        WHERE profile_id = ${idx} AND user_id = ${idx + 1}
        RETURNING *
        """
        record = await self._fetchrow(query, *args)
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

    async def update_pipeline_config(self, profile_id: str, config) -> None:
        query = """
        UPDATE trading_profiles SET pipeline_config = $1, updated_at = NOW()
        WHERE profile_id = $2
        """
        config_json = json.dumps(config) if config is not None else None
        await self._execute(query, config_json, UUID(profile_id))

    async def update_pipeline_and_rules(
        self, profile_id: str, pipeline_config: dict, strategy_rules: dict
    ) -> None:
        """Atomic save of both canvas state and the rules compiled from it.

        Used by the pipeline editor save path: pipeline_config is the canvas; strategy_rules
        is the compile output that hot_path consumes.
        """
        query = """
        UPDATE trading_profiles
        SET pipeline_config = $1, strategy_rules = $2, updated_at = NOW()
        WHERE profile_id = $3
        """
        await self._execute(
            query,
            json.dumps(pipeline_config),
            json.dumps(strategy_rules),
            UUID(profile_id),
        )

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
