from typing import List, Optional
from uuid import UUID
from libs.core.models import TradingProfile, RiskLimits
from ._repository_base import BaseRepository
import json

class ProfileRepository(BaseRepository):
    async def get_active_profiles(self) -> List[TradingProfile]:
        query = "SELECT * FROM trading_profiles WHERE is_active = true"
        records = await self._fetch(query)
        # Type conversions omitted
        return []

    async def get_profile(self, profile_id: str) -> Optional[TradingProfile]:
        query = "SELECT * FROM trading_profiles WHERE profile_id = $1"
        record = await self._fetchrow(query, UUID(profile_id))
        if record:
            pass
        return None

    async def update_profile(self, profile: TradingProfile):
        query = """
        UPDATE trading_profiles 
        SET name = $1, strategy_rules_json = $2, risk_limits = $3, blacklist = $4, allocation_pct = $5, is_active = $6
        WHERE profile_id = $7
        """
        await self._execute(
            query,
            profile.name,
            profile.strategy_rules_json,
            json.dumps(profile.risk_limits.__dict__), # simplified
            profile.blacklist,
            profile.allocation_pct,
            profile.is_active,
            UUID(profile.profile_id)
        )

    async def get_profiles_for_symbol(self, symbol: str) -> List[TradingProfile]:
        query = "SELECT * FROM trading_profiles WHERE is_active = true"
        # We assume later parsing or actual join depending on setup
        return []
