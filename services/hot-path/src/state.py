from __future__ import annotations
import numpy as np
from typing import Dict, Optional
from libs.indicators import IndicatorSet
from services.strategy.src.compiler import CompiledRuleSet
from libs.core.enums import Regime
from libs.core.models import RiskLimits

class ProfileState:
    __slots__ = (
        'profile_id',
        'compiled_rules',
        'risk_limits',
        'blacklist',
        'indicators',
        'regime',
        'daily_realised_pnl_pct',
        'current_drawdown_pct',
        'current_allocation_pct',
        'is_active'
    )

    def __init__(
        self,
        profile_id: str,
        compiled_rules: CompiledRuleSet,
        risk_limits: RiskLimits,
        blacklist: frozenset,
        indicators: IndicatorSet,
    ):
        self.profile_id = profile_id
        self.compiled_rules = compiled_rules
        self.risk_limits = risk_limits
        self.blacklist = blacklist
        self.indicators = indicators
        self.regime: Optional[Regime] = None
        self.daily_realised_pnl_pct: float = 0.0
        self.current_drawdown_pct: float = 0.0
        self.current_allocation_pct: float = 0.0
        self.is_active = True

class ProfileStateCache:
    __slots__ = ('_profiles',)
    
    def __init__(self):
        self._profiles: Dict[str, ProfileState] = {}

    def add(self, state: ProfileState):
        self._profiles[state.profile_id] = state

    def get(self, profile_id: str) -> Optional[ProfileState]:
        return self._profiles.get(profile_id)

    def itervalues(self):
        return self._profiles.values()
