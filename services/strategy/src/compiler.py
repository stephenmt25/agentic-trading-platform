from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from libs.core.enums import SignalDirection

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
