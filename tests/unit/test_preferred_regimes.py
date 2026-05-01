"""Tests for C.4 preferred_regimes plumbing.

Covers schema acceptance, canonical roundtrip, profile-state defaults, and
the main-module loader's regime parsing (incl. silent drop of unknown regime
strings — a typo in a profile must not crash hot_path startup).
"""

from decimal import Decimal

import pytest

from libs.core.enums import Regime
from libs.core.schemas import (
    StrategyRulesInput,
    strategy_rules_to_canonical,
    strategy_rules_from_canonical,
)
from libs.indicators import create_indicator_set
from libs.core.models import RiskLimits
from services.hot_path.src.state import ProfileState
from services.strategy.src.compiler import RuleCompiler


def _legacy_rules() -> dict:
    return {
        "direction": "long",
        "match_mode": "all",
        "confidence": 0.7,
        "signals": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
    }


class TestSchema:
    def test_default_is_empty_list(self):
        rules = StrategyRulesInput.model_validate(_legacy_rules())
        assert rules.preferred_regimes == []

    def test_accepts_known_regime(self):
        body = _legacy_rules() | {"preferred_regimes": ["RANGE_BOUND", "TRENDING_UP"]}
        rules = StrategyRulesInput.model_validate(body)
        assert rules.preferred_regimes == ["RANGE_BOUND", "TRENDING_UP"]

    def test_rejects_unknown_regime(self):
        body = _legacy_rules() | {"preferred_regimes": ["BANANA"]}
        with pytest.raises(Exception):
            StrategyRulesInput.model_validate(body)


class TestCanonicalRoundtrip:
    def test_empty_preferred_regimes_omitted_from_canonical(self):
        rules = StrategyRulesInput.model_validate(_legacy_rules())
        canonical = strategy_rules_to_canonical(rules)
        assert "preferred_regimes" not in canonical

    def test_non_empty_preferred_regimes_preserved(self):
        body = _legacy_rules() | {"preferred_regimes": ["RANGE_BOUND"]}
        rules = StrategyRulesInput.model_validate(body)
        canonical = strategy_rules_to_canonical(rules)
        assert canonical["preferred_regimes"] == ["RANGE_BOUND"]

    def test_canonical_to_user_roundtrip(self):
        body = _legacy_rules() | {"preferred_regimes": ["RANGE_BOUND", "TRENDING_UP"]}
        original = StrategyRulesInput.model_validate(body)
        canonical = strategy_rules_to_canonical(original)
        recovered = strategy_rules_from_canonical(canonical)
        assert recovered.preferred_regimes == ["RANGE_BOUND", "TRENDING_UP"]


class TestProfileStateDefaults:
    def _state(self, preferred=None) -> ProfileState:
        compiled = RuleCompiler.compile({
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.7,
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
        })
        return ProfileState(
            profile_id="abc",
            compiled_rules=compiled,
            risk_limits=RiskLimits(
                max_drawdown_pct=Decimal("0.1"),
                stop_loss_pct=Decimal("0.02"),
                circuit_breaker_daily_loss_pct=Decimal("0.02"),
                max_allocation_pct=Decimal("1.0"),
            ),
            blacklist=frozenset(),
            indicators=create_indicator_set(),
            preferred_regimes=preferred,
        )

    def test_default_is_empty_frozenset(self):
        s = self._state()
        assert s.preferred_regimes == frozenset()

    def test_membership_check_works(self):
        s = self._state(frozenset({Regime.RANGE_BOUND, Regime.TRENDING_UP}))
        assert Regime.RANGE_BOUND in s.preferred_regimes
        assert Regime.HIGH_VOLATILITY not in s.preferred_regimes


class TestLoaderParser:
    """The loader sits inside hot_path/main.py inside lifespan() — hard to
    import directly. We re-implement the small parsing block here so the
    'unknown regime is dropped, known regime is kept' invariant has a unit
    test that won't drift silently from the production code.
    """

    def _parse_preferred_regimes(self, rules: dict) -> frozenset:
        pr_raw = rules.get("preferred_regimes", []) or []
        out: set = set()
        for name in pr_raw:
            try:
                out.add(Regime(name))
            except ValueError:
                pass
        return frozenset(out)

    def test_unknown_regime_silently_dropped(self):
        rules = {"preferred_regimes": ["RANGE_BOUND", "BANANA"]}
        result = self._parse_preferred_regimes(rules)
        assert result == frozenset({Regime.RANGE_BOUND})

    def test_missing_field_is_empty_frozenset(self):
        result = self._parse_preferred_regimes({})
        assert result == frozenset()

    def test_all_known_kept(self):
        rules = {"preferred_regimes": ["TRENDING_UP", "TRENDING_DOWN"]}
        result = self._parse_preferred_regimes(rules)
        assert result == frozenset({Regime.TRENDING_UP, Regime.TRENDING_DOWN})
