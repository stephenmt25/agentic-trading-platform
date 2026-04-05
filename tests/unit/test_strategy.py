"""Tests for Strategy service: rule compilation, validation, and hydration."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.core.enums import SignalDirection
from services.strategy.src.compiler import RuleCompiler, CompiledRuleSet
from services.strategy.src.rule_validator import RuleValidator


# ---------------------------------------------------------------------------
# RuleCompiler tests
# ---------------------------------------------------------------------------

class TestRuleCompiler:
    def _valid_rules(self, **overrides):
        base = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        base.update(overrides)
        return base

    def test_compile_valid_buy_rule(self):
        rules = self._valid_rules()
        compiled = RuleCompiler.compile(rules)
        assert isinstance(compiled, CompiledRuleSet)
        assert compiled.direction == SignalDirection.BUY
        assert compiled.logic == "AND"
        assert compiled.base_confidence == 0.85

    def test_compile_sell_direction(self):
        compiled = RuleCompiler.compile(self._valid_rules(direction="SELL"))
        assert compiled.direction == SignalDirection.SELL

    def test_compile_missing_key_raises(self):
        with pytest.raises(ValueError, match="Failed to compile"):
            RuleCompiler.compile({"logic": "AND"})

    def test_compile_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="Failed to compile"):
            RuleCompiler.compile(self._valid_rules(direction="INVALID"))


# ---------------------------------------------------------------------------
# CompiledRuleSet.evaluate tests
# ---------------------------------------------------------------------------

class TestCompiledRuleSetEvaluate:
    def _make(self, conditions, logic="AND", direction=SignalDirection.BUY, confidence=0.9):
        return CompiledRuleSet(
            logic=logic, direction=direction,
            base_confidence=confidence, conditions=conditions,
        )

    def test_and_all_true(self):
        rs = self._make([
            {"indicator": "rsi", "operator": "LT", "value": 30},
            {"indicator": "macd", "operator": "GT", "value": 0},
        ])
        result = rs.evaluate({"rsi": 25.0, "macd": 0.5})
        assert result == (SignalDirection.BUY, 0.9)

    def test_and_one_false(self):
        rs = self._make([
            {"indicator": "rsi", "operator": "LT", "value": 30},
            {"indicator": "macd", "operator": "GT", "value": 0},
        ])
        assert rs.evaluate({"rsi": 35.0, "macd": 0.5}) is None

    def test_or_one_true(self):
        rs = self._make(
            [
                {"indicator": "rsi", "operator": "LT", "value": 30},
                {"indicator": "macd", "operator": "GT", "value": 0},
            ],
            logic="OR",
        )
        result = rs.evaluate({"rsi": 35.0, "macd": 0.5})
        assert result == (SignalDirection.BUY, 0.9)

    def test_or_none_true(self):
        rs = self._make(
            [
                {"indicator": "rsi", "operator": "LT", "value": 30},
                {"indicator": "macd", "operator": "GT", "value": 0},
            ],
            logic="OR",
        )
        assert rs.evaluate({"rsi": 35.0, "macd": -1.0}) is None

    def test_missing_indicator_returns_none(self):
        rs = self._make([{"indicator": "rsi", "operator": "LT", "value": 30}])
        assert rs.evaluate({"macd": 0.5}) is None

    def test_lte_operator(self):
        rs = self._make([{"indicator": "rsi", "operator": "LTE", "value": 30}])
        assert rs.evaluate({"rsi": 30.0}) is not None

    def test_gte_operator(self):
        rs = self._make([{"indicator": "rsi", "operator": "GTE", "value": 30}])
        assert rs.evaluate({"rsi": 30.0}) is not None

    def test_eq_operator(self):
        rs = self._make([{"indicator": "rsi", "operator": "EQ", "value": 50}])
        assert rs.evaluate({"rsi": 50.0}) is not None
        assert rs.evaluate({"rsi": 49.0}) is None

    def test_unsupported_operator_returns_none(self):
        rs = self._make([{"indicator": "rsi", "operator": "NEQ", "value": 30}])
        assert rs.evaluate({"rsi": 25.0}) is None

    def test_unsupported_logic_returns_none(self):
        rs = CompiledRuleSet(
            logic="XOR", direction=SignalDirection.BUY,
            base_confidence=0.5, conditions=[{"indicator": "rsi", "operator": "LT", "value": 30}],
        )
        assert rs.evaluate({"rsi": 25.0}) is None

    def test_empty_conditions_returns_none(self):
        rs = self._make([])
        assert rs.evaluate({"rsi": 25.0}) is None


# ---------------------------------------------------------------------------
# RuleValidator tests
# ---------------------------------------------------------------------------

class TestRuleValidator:
    def test_valid_rule_passes(self):
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        result = RuleValidator.validate(rules)
        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_indicator_fails(self):
        rules = {
            "conditions": [{"indicator": "unknown_ind", "operator": "LT", "value": 30}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        result = RuleValidator.validate(rules)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_invalid_logic_fails(self):
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
            "logic": "XOR",
            "direction": "BUY",
            "base_confidence": 0.85,
        }
        result = RuleValidator.validate(rules)
        assert result.is_valid is False

    def test_confidence_out_of_range_fails(self):
        rules = {
            "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 1.5,
        }
        result = RuleValidator.validate(rules)
        assert result.is_valid is False

    def test_empty_conditions_fails(self):
        rules = {
            "conditions": [],
            "logic": "AND",
            "direction": "BUY",
            "base_confidence": 0.5,
        }
        result = RuleValidator.validate(rules)
        assert result.is_valid is False
