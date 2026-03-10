from typing import Optional

# 2024 Simplified US Tax Brackets
# Short-term Capital Gains (Ordinary Income)
# 10%, 12%, 22%, 24%, 32%, 35%, 37%
SHORT_TERM_RATES = {
    "10": 0.10,
    "12": 0.12,
    "22": 0.22,
    "24": 0.24,
    "32": 0.32,
    "35": 0.35,
    "37": 0.37
}

# Long-term Capital Gains
# 0%, 15%, 20%
LONG_TERM_RATES = {
    "0": 0.0,
    "15": 0.15,
    "20": 0.20
}

DEFAULT_CONSERVATIVE_SHORT_TERM = 0.37
DEFAULT_CONSERVATIVE_LONG_TERM = 0.20

def get_rate(is_short_term: bool, bracket: Optional[str]) -> float:
    if is_short_term:
        if bracket in SHORT_TERM_RATES:
            return SHORT_TERM_RATES[bracket]
        return DEFAULT_CONSERVATIVE_SHORT_TERM
    else:
        if bracket in LONG_TERM_RATES:
            return LONG_TERM_RATES[bracket]
        return DEFAULT_CONSERVATIVE_LONG_TERM
