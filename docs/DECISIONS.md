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

### Long-term fix (open)

The hardcoded `$10,000` constant itself is the real defect. Notional should
derive from a single source — most naturally from `trading_profiles.allocation_pct`
(currently 0..N where 1.0 = 100% of some implicit base). When that lands,
all four call sites collapse to a single helper and this DECISIONS.md
entry can be marked as superseded.

### Why not preserve the bump (keep $100k everywhere)?

- The bump was explicitly marked session-bridge with revert instructions
- The closer's daily-loss counter and the binding RiskGate were never bumped — 3,689 closed BTC trades have already accrued under effective $10k notional; preserving $10k keeps that history coherent
- Honest paper-trading (the user's stated goal) requires the system's numbers to reflect a single, real portfolio size; $10k is the value the binding gate has always used
