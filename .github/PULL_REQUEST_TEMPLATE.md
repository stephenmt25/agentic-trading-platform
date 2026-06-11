<!--
Praxis PR template. Keep it short but answer every section.
Delete a section only if it is genuinely N/A (and say why).
-->

## What & why

<!-- One paragraph: what this PR changes and the problem it solves. Link the issue / brief / DECISIONS entry. -->

Closes / relates to:

## Risk tier

<!-- Pick one. Drives the depth of review required. -->

- [ ] **Critical** — touches order execution, position closing, kill switch, or money-at-risk paths
- [ ] **High** — risk/PnL/strategy logic, exchange adapters, schema/migrations
- [ ] **Medium** — supporting services, observability, non-financial logic
- [ ] **Low** — docs, tests, scaffolding, frontend-only

## Financial-precision checklist (CLAUDE.md §2A / §5B)

<!-- Required for any change under services/{execution,pnl,risk,strategy} or libs/core. Check or mark N/A. -->

- [ ] All financial values use `Decimal` / `NUMERIC` — no new `float(`/`double`
- [ ] Type aliases from `libs/core/types.py` used where applicable
- [ ] Redis channel names verified against `libs/messaging/channels.py` (none invented)
- [ ] Enum values sourced from `libs/core/enums.py`
- [ ] Kill switch / stop-loss / position-size limits respected where relevant
- [ ] Order-submission paths are rate-limited

## Test evidence

<!-- Paste command + result. Unit/integration as relevant. Note paper vs testnet. -->

```
# e.g. poetry run pytest tests/unit/... -v
```

## Rollback

<!-- How to undo this safely. "Revert the commit" only if there's no migration/state change; otherwise spell out the steps. -->
