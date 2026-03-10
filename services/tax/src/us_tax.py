from dataclasses import dataclass
from typing import Optional
from .tax_brackets import get_rate

@dataclass
class TaxEstimate:
    estimated_tax: float
    effective_rate: float
    classification: str

class USTaxCalculator:
    @staticmethod
    def calculate(holding_duration_days: int, net_pnl: float, tax_bracket: Optional[str] = None) -> TaxEstimate:
        if net_pnl <= 0:
            return TaxEstimate(0.0, 0.0, "none")
            
        is_short_term = holding_duration_days < 365
        classification = "short-term" if is_short_term else "long-term"
        
        effective_rate = get_rate(is_short_term, tax_bracket)
        estimated_tax = net_pnl * effective_rate
        
        return TaxEstimate(
            estimated_tax=estimated_tax,
            effective_rate=effective_rate,
            classification=classification
        )
