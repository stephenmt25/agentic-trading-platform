from typing import Dict, Any, List
from pydantic import BaseModel, root_validator, ValidationError
from libs.core.enums import SignalDirection

SUPPORTED_INDICATORS = {'rsi', 'macd.macd_line', 'macd.signal_line', 'macd.histogram', 'atr'}
SUPPORTED_OPERATORS = {'LT', 'GT', 'LTE', 'GTE', 'EQ'}

class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []

class RuleCondition(BaseModel):
    indicator: str
    operator: str
    value: float

    @root_validator(pre=True)
    def check_support(cls, values):
        errors = []
        if values.get('indicator') not in SUPPORTED_INDICATORS:
            errors.append(f"Unsupported indicator: {values.get('indicator')}")
        if values.get('operator') not in SUPPORTED_OPERATORS:
            errors.append(f"Unsupported operator: {values.get('operator')}")
        if errors:
            raise ValueError(" | ".join(errors))
        return values
        
class RuleSchema(BaseModel):
    conditions: List[RuleCondition]
    logic: str
    direction: SignalDirection
    base_confidence: float
    
    @root_validator(pre=True)
    def check_logic(cls, values):
        if values.get('logic') not in {'AND', 'OR'}:
            raise ValueError("Logic must be AND or OR")
        if not (0.0 <= values.get('base_confidence', -1) <= 1.0):
            raise ValueError("base_confidence must be between 0 and 1")
        if not values.get('conditions'):
            raise ValueError("At least one condition required")
        return values

class RuleValidator:
    @staticmethod
    def validate(rules_json: Dict[str, Any]) -> ValidationResult:
        try:
            RuleSchema(**rules_json)
            return ValidationResult(is_valid=True)
        except ValidationError as e:
            errors = [str(err['msg']) for err in e.errors()]
            return ValidationResult(is_valid=False, errors=errors)
