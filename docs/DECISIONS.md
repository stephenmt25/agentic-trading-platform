# Decisions log

> Architectural and trade-off decisions that diverge from a default, a plan, or
> a prior decision. Append-only — preserve history.

---

## 2026-05-05 — Notional-per-allocation reverted to $10k across all four call sites

### Context

Four call sites in financial code multiply `allocation_pct` by a hardcoded
notional constant:

| File | Constant | Effect |
|------|----------|--------|
| `services/hot_path/src/main.py:132` | `Decimal("10000")` | Sets `state.notional` per profile load (binding for RiskGate's exposure-at-notional check) |
| `services/hot_path/src/state.py:33` | `Decimal("10000")` | `ProfileState` default — only fires if no profile loaded; dead code in production |
| `services/risk/src/__init__.py:60` | `Decimal("10000")` | RiskService.check_order's `portfolio_value` (concentration check, allocation cap) |
| `services/pnl/src/closer.py:35` | `Decimal("10000")` | Daily realised-PnL counter denominator (CircuitBreaker compares against this) |

Commit `ddb68e5` (2026-05-01) bumped `state.py:33` and `risk/__init__.py:60`
from `$10k → $100k` as a session-bridge to unfreeze decision flow during a
demo session where 7 open positions had saturated the $10k notional.
`main.py:132` and `closer.py:35` were missed by the bump, so the running
system used **$10k for the binding RiskGate and the daily-loss counter**
but **$100k for the validation service's pre-trade concentration check** —
a 10× unit mismatch.

### Decision

Reverted `state.py:33` and `risk/__init__.py:60` to `$10k` to match the
other two call sites. All four constants now agree.

### Trade-off

If a profile's open exposure saturates $10k (the original demo's failure
mode), RiskGate's exposure-at-notional check will again freeze new decision
flow. This is **correct rails behaviour** under the documented contract —
the gate exists to enforce capital discipline. Workarounds for an active
demo session: close positions, lower `allocation_pct`, or land the
long-term fix.

### Long-term fix (LANDED 2026-05-05)

The hardcoded `$10,000` constant has been collapsed into a single helper at
`libs/core/notional.py`:

- `NOTIONAL_PER_ALLOC_UNIT_USD = Decimal("10000")` — the only place the
  constant lives.
- `DEFAULT_ALLOCATION_PCT = Decimal("1.0")`
- `DEFAULT_NOTIONAL_USD = DEFAULT_ALLOCATION_PCT * NOTIONAL_PER_ALLOC_UNIT_USD`
- `profile_notional(profile)` — accepts the dict returned by
  `ProfileRepository.get_profile`, returns the computed Decimal. Strictly
  positive — invalid/missing/zero/negative inputs all return
  `DEFAULT_NOTIONAL_USD` so callers can divide without guards.

While auditing, a **fifth** call site was discovered that the original
DECISIONS entry missed: `services/validation/src/check_6_risk_level.py:48`
used a Python `int` literal `10_000` (not even a `Decimal`). It would have
been the next site to silently drift on any future bump.

All five sites now read from the helper:

| File (was) | Now |
|------------|-----|
| `services/hot_path/src/main.py:132` `alloc_pct * Decimal("10000")` | `profile_notional(prof)` |
| `services/hot_path/src/state.py:33` default `Decimal("10000")` | default `DEFAULT_NOTIONAL_USD` |
| `services/risk/src/__init__.py:60` `Decimal(...) * Decimal("10000")` | `profile_notional(profile)` |
| `services/pnl/src/closer.py:_profile_notional` `alloc * _NOTIONAL_PER_ALLOC_UNIT` | wraps `profile_notional(row)` with caching |
| `services/validation/src/check_6_risk_level.py:48` `profile_allocation * 10_000` | `profile_notional(profile)` |

Tests: `tests/unit/test_notional.py` (16 cases) covers the helper's
contract — string/Decimal/int/float inputs, missing/None/empty profile,
zero/negative/garbage values, the strictly-positive-output property.

### Future work (still open)

- Schema rename `trading_profiles.allocation_pct` → `notional_capital_dollars`
  (storing absolute dollars, not a multiplier). Single helper edit when it
  lands. DB migration + frontend form update needed.
- `notional` becomes profile-scoped from a config setting
  (`PRAXIS_NOTIONAL_BASE_USD`) so operators can change the base without a
  code edit. Would live entirely inside `libs/core/notional.py`.

### Why not preserve the bump (keep $100k everywhere)?

- The bump was explicitly marked session-bridge with revert instructions
- The closer's daily-loss counter and the binding RiskGate were never bumped — 3,689 closed BTC trades have already accrued under effective $10k notional; preserving $10k keeps that history coherent
- Honest paper-trading (the user's stated goal) requires the system's numbers to reflect a single, real portfolio size; $10k is the value the binding gate has always used
