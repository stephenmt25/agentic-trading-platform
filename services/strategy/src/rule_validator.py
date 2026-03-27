from typing import Dict, Any, List
from pydantic import ValidationError
from libs.core.schemas import RuleCondition, RuleSchema


class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []


class RuleValidator:
    @staticmethod
    def validate(rules_json: Dict[str, Any]) -> ValidationResult:
        try:
            RuleSchema(**rules_json)
            return ValidationResult(is_valid=True)
        except ValidationError as e:
            errors = [str(err['msg']) for err in e.errors()]
            return ValidationResult(is_valid=False, errors=errors)
