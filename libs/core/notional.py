"""Profile notional capital — single source of truth.

Historical context (`docs/DECISIONS.md`, 2026-05-05): the system stored
`trading_profiles.allocation_pct` as a Decimal scalar and *five* separate
code paths multiplied it by a hardcoded `$10,000` constant. The constant
agreed by convention only; when a session-bridge bumped two sites to
`$100k` on 2026-05-01, the other three didn't follow, producing a 10x
unit mismatch between gates that said "blocked at concentration" vs gates
that said "still room."

This module is the *only* place the constant lives. Future schema changes
(e.g. renaming `allocation_pct` to `notional_capital_dollars` and storing
the absolute value directly) need only edit this module's body.
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

# Notional capital corresponding to allocation_pct = 1.0. Until the schema
# rename, this is the implicit base of trading_profiles.allocation_pct.
NOTIONAL_PER_ALLOC_UNIT_USD: Decimal = Decimal("10000")

# Default allocation_pct for missing/empty profile data. Profiles created
# via the API default to allocation_pct = 1.0 (= $10k notional).
DEFAULT_ALLOCATION_PCT: Decimal = Decimal("1.0")

# Default notional. Used by callers as a non-zero fallback for division
# guards and as the dataclass default in ProfileState.
DEFAULT_NOTIONAL_USD: Decimal = DEFAULT_ALLOCATION_PCT * NOTIONAL_PER_ALLOC_UNIT_USD

_ZERO: Decimal = Decimal("0")


def profile_notional(profile: Optional[Mapping[str, Any]]) -> Decimal:
    """Compute notional capital for a profile.

    `profile` is typically a dict returned by `ProfileRepository.get_profile`,
    which carries `allocation_pct` as a Decimal-or-string field per the
    schema in `migrations/versions/001_initial_schema.sql:18`.

    Returns `DEFAULT_NOTIONAL_USD` whenever the input is missing, malformed,
    zero, or negative — never returns `0` or a negative value. Callers that
    need division by notional rely on this guarantee.

    Examples:
        >>> profile_notional({"allocation_pct": "1.0"}) == Decimal("10000")
        True
        >>> profile_notional({"allocation_pct": Decimal("2.5")}) == Decimal("25000")
        True
        >>> profile_notional(None) == DEFAULT_NOTIONAL_USD
        True
        >>> profile_notional({}) == DEFAULT_NOTIONAL_USD
        True
        >>> profile_notional({"allocation_pct": 0}) == DEFAULT_NOTIONAL_USD
        True
    """
    if not profile:
        return DEFAULT_NOTIONAL_USD
    raw = profile.get("allocation_pct")
    if raw is None:
        return DEFAULT_NOTIONAL_USD
    try:
        alloc = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return DEFAULT_NOTIONAL_USD
    if alloc <= _ZERO:
        return DEFAULT_NOTIONAL_USD
    notional = alloc * NOTIONAL_PER_ALLOC_UNIT_USD
    if notional <= _ZERO:
        return DEFAULT_NOTIONAL_USD
    return notional
