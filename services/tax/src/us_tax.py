from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from .tax_brackets import get_rate

_ZERO = Decimal("0")

@dataclass
class TaxEstimate:
    estimated_tax: Decimal
    effective_rate: Decimal
    classification: str

class USTaxCalculator:
    @staticmethod
    def calculate(holding_duration_days: int, net_pnl: Decimal, tax_bracket: Optional[str] = None) -> TaxEstimate:
        if net_pnl <= _ZERO:
            return TaxEstimate(_ZERO, _ZERO, "none")

        is_short_term = holding_duration_days < 365
        classification = "short-term" if is_short_term else "long-term"

        effective_rate = get_rate(is_short_term, tax_bracket)
        estimated_tax = net_pnl * effective_rate

        return TaxEstimate(
            estimated_tax=estimated_tax,
            effective_rate=effective_rate,
            classification=classification
        )
