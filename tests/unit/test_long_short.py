"""C.1 — long+short conditions in one profile.

Covers:
  - Schema acceptance for the new entry_long / entry_short shape
  - Legacy single-direction shape continues to validate
  - Canonical roundtrip preserves both-legs exactly
  - RuleCompiler produces a CompiledRuleSet that evaluates both legs
  - CompiledRuleSet emits BUY when only long matches, SELL when only short
    matches, None when neither matches, and None (with warning) when both
    match in the same tick
"""

import pytest

from libs.core.enums import SignalDirection
from libs.core.schemas import (
    StrategyRulesInput,
    strategy_rules_to_canonical,
    strategy_rules_from_canonical,
)
from services.strategy.src.compiler import RuleCompiler


# ---------------------------------------------------------------------------
# Schema acceptance / validation
# ---------------------------------------------------------------------------

class TestSchema:
    def test_legacy_single_direction_accepted(self):
        rules = StrategyRulesInput.model_validate({
            "direction": "long",
            "match_mode": "all",
            "confidence": 0.7,
            "signals": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
        })
        assert rules.direction == "long"
        assert rules.entry_long is None
        assert rules.entry_short is None

    def test_long_only_accepted(self):
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.7,
            "entry_long": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
            "match_mode_long": "all",
        })
        assert rules.entry_long is not None
        assert rules.entry_short is None

    def test_short_only_accepted(self):
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.7,
            "entry_short": [{"indicator": "rsi", "comparison": "above", "threshold": 70}],
            "match_mode_short": "all",
        })
        assert rules.entry_short is not None

    def test_both_legs_accepted(self):
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.7,
            "entry_long": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
            "match_mode_long": "all",
            "entry_short": [{"indicator": "rsi", "comparison": "above", "threshold": 70}],
            "match_mode_short": "all",
        })
        assert rules.entry_long and rules.entry_short

    def test_no_legs_rejected(self):
        with pytest.raises(Exception):
            StrategyRulesInput.model_validate({"confidence": 0.7})

    def test_entry_long_without_match_mode_rejected(self):
        with pytest.raises(Exception):
            StrategyRulesInput.model_validate({
                "confidence": 0.7,
                "entry_long": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
            })


# ---------------------------------------------------------------------------
# Canonical roundtrip
# ---------------------------------------------------------------------------

class TestCanonicalRoundtrip:
    def test_legacy_roundtrip(self):
        rules = StrategyRulesInput.model_validate({
            "direction": "long",
            "match_mode": "all",
            "confidence": 0.7,
            "signals": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
        })
        canonical = strategy_rules_to_canonical(rules)
        assert "entry_long" not in canonical and "entry_short" not in canonical
        assert canonical["direction"] == "BUY"
        recovered = strategy_rules_from_canonical(canonical)
        assert recovered.direction == "long"
        assert recovered.entry_long is None and recovered.entry_short is None

    def test_both_legs_roundtrip(self):
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.65,
            "entry_long": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
            "match_mode_long": "all",
            "entry_short": [{"indicator": "rsi", "comparison": "above", "threshold": 70}],
            "match_mode_short": "all",
        })
        canonical = strategy_rules_to_canonical(rules)
        # Legacy keys are populated as a fallback (from the long leg here).
        assert canonical["direction"] == "BUY"
        assert canonical["logic"] == "AND"
        # Both legs explicitly present.
        assert canonical["entry_long"]["conditions"][0]["indicator"] == "rsi"
        assert canonical["entry_short"]["conditions"][0]["indicator"] == "rsi"

        recovered = strategy_rules_from_canonical(canonical)
        assert recovered.entry_long is not None
        assert recovered.entry_short is not None
        assert recovered.match_mode_long == "all"
        assert recovered.match_mode_short == "all"
        assert recovered.confidence == pytest.approx(0.65)

    def test_short_only_roundtrip(self):
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.5,
            "entry_short": [{"indicator": "rsi", "comparison": "above", "threshold": 70}],
            "match_mode_short": "any",
        })
        canonical = strategy_rules_to_canonical(rules)
        # Legacy fallback: direction comes from the short leg when long absent.
        assert canonical["direction"] == "SELL"
        assert "entry_short" in canonical and "entry_long" not in canonical

        recovered = strategy_rules_from_canonical(canonical)
        assert recovered.entry_long is None
        assert recovered.entry_short is not None
        assert recovered.match_mode_short == "any"


# ---------------------------------------------------------------------------
# CompiledRuleSet evaluation with both legs
# ---------------------------------------------------------------------------

class TestEvaluation:
    def _compile_both_legs(self):
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.65,
            "entry_long": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
            "match_mode_long": "all",
            "entry_short": [{"indicator": "rsi", "comparison": "above", "threshold": 70}],
            "match_mode_short": "all",
        })
        canonical = strategy_rules_to_canonical(rules)
        return RuleCompiler.compile(canonical)

    def test_long_only_match(self):
        compiled = self._compile_both_legs()
        result = compiled.evaluate({"rsi": 25.0})
        assert result == (SignalDirection.BUY, 0.65)

    def test_short_only_match(self):
        compiled = self._compile_both_legs()
        result = compiled.evaluate({"rsi": 75.0})
        assert result == (SignalDirection.SELL, 0.65)

    def test_neither_match(self):
        compiled = self._compile_both_legs()
        assert compiled.evaluate({"rsi": 50.0}) is None

    def test_both_match_returns_none(self):
        # Construct a profile where the same indicator value satisfies both legs:
        # entry_long: rsi < 80, entry_short: rsi > 20.
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.5,
            "entry_long": [{"indicator": "rsi", "comparison": "below", "threshold": 80}],
            "match_mode_long": "all",
            "entry_short": [{"indicator": "rsi", "comparison": "above", "threshold": 20}],
            "match_mode_short": "all",
        })
        compiled = RuleCompiler.compile(strategy_rules_to_canonical(rules))
        # rsi=50 satisfies both legs. Evaluator must return None (with warning).
        assert compiled.evaluate({"rsi": 50.0}) is None

    def test_long_only_profile_never_emits_sell(self):
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.7,
            "entry_long": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
            "match_mode_long": "all",
        })
        compiled = RuleCompiler.compile(strategy_rules_to_canonical(rules))
        # Only long leg defined → high RSI shouldn't produce anything.
        assert compiled.evaluate({"rsi": 90.0}) is None
        # Low RSI fires the long leg.
        assert compiled.evaluate({"rsi": 20.0}) == (SignalDirection.BUY, 0.7)

    def test_legacy_path_unchanged(self):
        rules = StrategyRulesInput.model_validate({
            "direction": "long",
            "match_mode": "all",
            "confidence": 0.85,
            "signals": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
        })
        compiled = RuleCompiler.compile(strategy_rules_to_canonical(rules))
        assert compiled.long_leg is None and compiled.short_leg is None
        assert compiled.evaluate({"rsi": 25.0}) == (SignalDirection.BUY, 0.85)
        assert compiled.evaluate({"rsi": 50.0}) is None


# ---------------------------------------------------------------------------
# evaluate_with_trace
# ---------------------------------------------------------------------------

class TestTrace:
    def test_trace_present_on_long_match(self):
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.5,
            "entry_long": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
            "match_mode_long": "all",
            "entry_short": [{"indicator": "rsi", "comparison": "above", "threshold": 70}],
            "match_mode_short": "all",
        })
        compiled = RuleCompiler.compile(strategy_rules_to_canonical(rules))
        signal, trace = compiled.evaluate_with_trace({"rsi": 25.0})
        assert signal == (SignalDirection.BUY, 0.5)
        assert trace.matched is True
        assert trace.direction == "BUY"

    def test_trace_present_on_neither_match(self):
        rules = StrategyRulesInput.model_validate({
            "confidence": 0.5,
            "entry_long": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
            "match_mode_long": "all",
            "entry_short": [{"indicator": "rsi", "comparison": "above", "threshold": 70}],
            "match_mode_short": "all",
        })
        compiled = RuleCompiler.compile(strategy_rules_to_canonical(rules))
        signal, trace = compiled.evaluate_with_trace({"rsi": 50.0})
        assert signal is None
        assert trace.matched is False
