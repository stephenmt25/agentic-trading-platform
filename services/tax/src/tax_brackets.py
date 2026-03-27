from decimal import Decimal
from typing import Optional

# 2024 Simplified US Tax Brackets
# Short-term Capital Gains (Ordinary Income)
# 10%, 12%, 22%, 24%, 32%, 35%, 37%
SHORT_TERM_RATES = {
    "10": Decimal("0.10"),
    "12": Decimal("0.12"),
    "22": Decimal("0.22"),
    "24": Decimal("0.24"),
    "32": Decimal("0.32"),
    "35": Decimal("0.35"),
    "37": Decimal("0.37"),
}

# Long-term Capital Gains
# 0%, 15%, 20%
LONG_TERM_RATES = {
    "0": Decimal("0"),
    "15": Decimal("0.15"),
    "20": Decimal("0.20"),
}

DEFAULT_CONSERVATIVE_SHORT_TERM = Decimal("0.37")
DEFAULT_CONSERVATIVE_LONG_TERM = Decimal("0.20")

def get_rate(is_short_term: bool, bracket: Optional[str]) -> Decimal:
    if is_short_term:
        if bracket in SHORT_TERM_RATES:
            return SHORT_TERM_RATES[bracket]
        return DEFAULT_CONSERVATIVE_SHORT_TERM
    else:
        if bracket in LONG_TERM_RATES:
            return LONG_TERM_RATES[bracket]
        return DEFAULT_CONSERVATIVE_LONG_TERM
