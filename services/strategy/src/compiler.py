from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from libs.core.enums import SignalDirection


@dataclass(frozen=True)
class ConditionTrace:
    indicator: str
    operator: str
    threshold: float
    actual_value: float
    passed: bool


@dataclass(frozen=True)
class StrategyTrace:
    direction: str
    logic: str
    base_confidence: float
    matched: bool
    conditions: List[ConditionTrace]


@dataclass
class CompiledRuleSet:
    logic: str
    direction: SignalDirection
    base_confidence: float
    conditions: List[Dict[str, Any]]

    def evaluate(self, indicators: Dict[str, float]) -> Optional[tuple[SignalDirection, float]]:
        results = []
        for cond in self.conditions:
            ind_val = indicators.get(cond['indicator'])
            if ind_val is None:
                return None
            
            op = cond['operator']
            val = cond['value']
            
            if op == 'LT': res = ind_val < val
            elif op == 'GT': res = ind_val > val
            elif op == 'LTE': res = ind_val <= val
            elif op == 'GTE': res = ind_val >= val
            elif op == 'EQ': res = ind_val == val
            else: return None
            
            results.append(res)
            
        if not results:
            return None
            
        if self.logic == 'AND':
            matched = all(results)
        elif self.logic == 'OR':
            matched = any(results)
        else:
            return None
            
        if matched:
            return (self.direction, self.base_confidence)
        return None

    def evaluate_with_trace(
        self, indicators: Dict[str, float]
    ) -> tuple[Optional[tuple[SignalDirection, float]], StrategyTrace]:
        """Same as evaluate() but returns a StrategyTrace with per-condition results."""
        cond_traces: List[ConditionTrace] = []
        results: List[bool] = []

        for cond in self.conditions:
            ind_val = indicators.get(cond["indicator"])
            if ind_val is None:
                # Indicator still priming — record as not passed, return no signal
                cond_traces.append(
                    ConditionTrace(
                        indicator=cond["indicator"],
                        operator=cond["operator"],
                        threshold=float(cond["value"]),
                        actual_value=0.0,
                        passed=False,
                    )
                )
                trace = StrategyTrace(
                    direction=self.direction.value,
                    logic=self.logic,
                    base_confidence=self.base_confidence,
                    matched=False,
                    conditions=cond_traces,
                )
                return None, trace

            op = cond["operator"]
            val = cond["value"]

            if op == "LT":
                res = ind_val < val
            elif op == "GT":
                res = ind_val > val
            elif op == "LTE":
                res = ind_val <= val
            elif op == "GTE":
                res = ind_val >= val
            elif op == "EQ":
                res = ind_val == val
            else:
                res = False

            results.append(res)
            cond_traces.append(
                ConditionTrace(
                    indicator=cond["indicator"],
                    operator=op,
                    threshold=float(val),
                    actual_value=float(ind_val),
                    passed=res,
                )
            )

        if not results:
            matched = False
        elif self.logic == "AND":
            matched = all(results)
        elif self.logic == "OR":
            matched = any(results)
        else:
            matched = False

        trace = StrategyTrace(
            direction=self.direction.value,
            logic=self.logic,
            base_confidence=self.base_confidence,
            matched=matched,
            conditions=cond_traces,
        )
        signal = (self.direction, self.base_confidence) if matched else None
        return signal, trace


class RuleCompiler:
    @staticmethod
    def compile(rules_json: Dict[str, Any]) -> CompiledRuleSet:
        # Expected format:
        # {'conditions': [{'indicator': 'rsi', 'operator': 'LT', 'value': 30}], 'logic': 'AND', 'direction': 'BUY', 'base_confidence': 0.85}
        try:
            return CompiledRuleSet(
                logic=rules_json['logic'],
                direction=SignalDirection(rules_json['direction']),
                base_confidence=float(rules_json['base_confidence']),
                conditions=rules_json['conditions']
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Failed to compile rules: {e}")
