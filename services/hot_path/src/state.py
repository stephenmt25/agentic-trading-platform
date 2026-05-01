from __future__ import annotations
from decimal import Decimal
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
        'notional',
        'open_exposure_dollars',
        'is_active'
    )

    def __init__(
        self,
        profile_id: str,
        compiled_rules: CompiledRuleSet,
        risk_limits: RiskLimits,
        blacklist: frozenset,
        indicators: IndicatorSet,
        notional: Decimal = Decimal("100000"),
    ):
        self.profile_id = profile_id
        self.compiled_rules = compiled_rules
        self.risk_limits = risk_limits
        self.blacklist = blacklist
        self.indicators = indicators
        self.regime: Optional[Regime] = None
        self.daily_realised_pnl_pct: Decimal = Decimal("0")
        self.current_drawdown_pct: Decimal = Decimal("0")
        self.current_allocation_pct: Decimal = Decimal("0")
        # Profile's nominal trading capital (allocation_pct × $100,000).
        # Session-bridge bump from $10k → $100k on 2026-05-01: with the demo
        # profile's 7 open positions consuming the full $10k allocation, the
        # risk gate's exposure_at_notional check froze all new decisions and
        # the autonomous execution session had no flow to learn from. Revert
        # alongside services/risk/src/__init__.py:60 once the session ends
        # and either positions close or notional becomes profile-scaled.
        self.notional: Decimal = notional
        # Sum of cost_basis over currently-open positions for this profile.
        # Updated by PnlSync poll loop from the positions table. Drives the
        # aggregate-exposure cap in RiskGate so we don't keep stacking trades
        # past the profile's notional capital.
        self.open_exposure_dollars: Decimal = Decimal("0")
        self.is_active = True

class ProfileStateCache:
    __slots__ = ('_profiles',)
    
    def __init__(self):
        self._profiles: Dict[str, ProfileState] = {}

    def add(self, state: ProfileState):
        self._profiles[state.profile_id] = state

    def get(self, profile_id: str) -> Optional[ProfileState]:
        return self._profiles.get(profile_id)

    def remove(self, profile_id: str) -> None:
        self._profiles.pop(profile_id, None)

    def itervalues(self):
        return self._profiles.values()
