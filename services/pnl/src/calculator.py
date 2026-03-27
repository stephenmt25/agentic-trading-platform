from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from libs.core.models import Position
from libs.core.enums import SignalDirection
from services.tax.src.us_tax import TaxEstimate

_ZERO = Decimal("0")

@dataclass
class PnLSnapshot:
    position_id: str
    symbol: str
    gross_pnl: Decimal
    fees: Decimal
    net_pre_tax: Decimal
    net_post_tax: Decimal
    pct_return: Decimal
    tax_estimate: Decimal

class PnLCalculator:
    @staticmethod
    def calculate(position: Position, current_price: Decimal, taker_rate: Decimal, tax_result: Optional[TaxEstimate] = None) -> PnLSnapshot:
        qty = position.quantity
        entry = position.entry_price
        cp = current_price

        if position.side == SignalDirection.BUY:
            gross = (cp - entry) * qty
        else:  # SHORT
            gross = (entry - cp) * qty

        fees_exit = cp * qty * taker_rate
        total_fees = position.entry_fee + fees_exit

        net_pre_tax = gross - total_fees

        tax_est = tax_result.estimated_tax if tax_result else _ZERO
        net_post_tax = net_pre_tax - tax_est

        cost_basis = entry * qty
        pct_return = net_post_tax / cost_basis if cost_basis > 0 else _ZERO

        return PnLSnapshot(
            position_id=str(position.position_id),
            symbol=position.symbol,
            gross_pnl=gross,
            fees=total_fees,
            net_pre_tax=net_pre_tax,
            net_post_tax=net_post_tax,
            pct_return=pct_return,
            tax_estimate=tax_est
        )
