# Execution Report — Phase 3 (`routes/pnl.py` WRONGTYPE)

**Date:** 2026-05-05
**Plan:** `docs/EXECUTION-PLAN-TECH-DEBT-2026-05-05.md` Phase 3

## TL;DR

| Entry | Commit | Files changed |
|-------|--------|---------------|
| `api_gateway/pnl-routes-wrongtype` (HIGH) | `f583ffb` | `services/api_gateway/src/routes/pnl.py`, `tests/unit/test_pnl_routes.py` (new) |

## Plan accuracy

The plan correctly identified the bug (`redis.get` + `json.loads` on a hash → WRONGTYPE) but **incorrectly described the frontend impact**:

- Plan claimed fixing the shape "breaks `frontend/app/paper-trading/page.tsx:110` and `frontend/lib/api/client.ts:204`."
- Reality: zero callers of `/pnl/summary` or `/pnl/{profile_id}` exist anywhere in `frontend/`. Verified by `grep` for `getPnlSummary`, `/pnl/`, and similar variants — only match was a docs manifest entry (`pnl service` description).
- The `total_net_pnl` reads at `paper-trading/page.tsx:110` and `trade/page.tsx:248` come from `status.metrics.total_net_pnl`, where `status` is a `PaperTradingStatus` object returned by a different endpoint (the paper-trading status route, not the pnl route).
- The interface at `frontend/lib/api/client.ts:198-220` is `PaperTradingStatus`, NOT a `PnlSummary` interface. There is no `PnlSummary` type and no client function calling these routes.

So this was backend-only — no frontend code or types needed changes.

## Implementation

`services/api_gateway/src/routes/pnl.py`:

- Removed `import json`; added `Decimal` and `Tuple`.
- New helper `_read_daily_loss(redis, profile_id)` that uses `redis.hget` against the hash, decodes bytes-or-str values, computes `pct = Decimal(total_pct_micro) / 1_000_000`, returns `(float_pct, date_or_None)`. Defaults to `(0.0, None)` on absent/malformed data — never raises.
- New helper `_snapshot_to_dict(row)` that converts an asyncpg Record into a JSON-friendly dict, narrowing Decimal→float at the wire boundary.
- `/summary` rewritten: iterates the user's active profiles, calls `PnlRepository.get_latest(pid)` for dollar P&L, calls `_read_daily_loss` for the percentage. Sums `Decimal` totals; converts to `float` only at the response.
- `/{profile_id}` rewritten: calls `get_latest` + `_read_daily_loss`, returns `{profile_id, snapshot, daily_loss_pct, daily_date}`.
- `/history` unchanged (already used `PnlRepository`).

The plan asked for a new `get_latest_snapshot` method on the repo. `PnlRepository.get_latest(profile_id)` already existed and returned exactly what was needed, so I reused it.

## Acceptance evidence

```
$ poetry run pytest tests/unit/test_pnl_routes.py -v
…
tests/unit/test_pnl_routes.py::TestPnlSummaryWrongTypeSafety::test_summary_with_hash_present_returns_200_and_dollar_value PASSED [ 25%]
tests/unit/test_pnl_routes.py::TestPnlSummaryWrongTypeSafety::test_summary_with_hash_absent_returns_200_and_zero_pct PASSED [ 50%]
tests/unit/test_pnl_routes.py::TestProfilePnlWrongTypeSafety::test_profile_endpoint_with_hash_returns_200 PASSED [ 75%]
tests/unit/test_pnl_routes.py::TestProfilePnlWrongTypeSafety::test_profile_endpoint_404_for_foreign_profile PASSED [100%]
========================= 4 passed, 5 warnings in 1.66s =========================

$ poetry run pytest tests/unit/ -q --ignore=…  (excluding 4 pre-existing-fail files)
410 passed, 11 warnings in 18.28s
```

The first test simulates the previously-broken state: `pnl_snapshots` has data and the daily hash exists with `total_pct_micro = -25000`. Old code would have raised WRONGTYPE on the second call. New code returns 200 with `total_net_pnl = 85.50` (from snapshots) and `daily_loss_pct = -0.025` (from the hash).

The third test additionally seeds the hash field as raw `bytes` to mirror the default `decode_responses=False` shape returned by the live RedisClient.

The live API gateway is running with the pre-fix code. Live verification will require a system restart (out of scope for this session per CLAUDE.md). The unit tests cover the failure mode the registry described.

## Registry diff

```
- | api_gateway | …routes/pnl.py … 500 with WRONGTYPE … breaks frontend… | HIGH | M | 2026-04-15 | OPEN |
+ | api_gateway | …routes/pnl.py … 500 with WRONGTYPE … breaks frontend… | HIGH | M | 2026-04-15 | **RESOLVED** (2026-05-05) — Plan's frontend-impact claim was incorrect. Verified zero callers … Backend-only fix: rewrote both routes to source dollar P&L from pnl_snapshots and expose the hash's total_pct_micro as daily_loss_pct. Regression test added. |
```

## Tangential findings

- `PnlRepository.get_latest(profile_id)` returns the most recent snapshot across **all** symbols for a profile, not a per-symbol aggregate. For a multi-symbol profile this is just "whatever symbol most recently crossed the 0.5% snapshot threshold," which under-reports total cumulative P&L. Out of scope for this fix (the prior route shape didn't aggregate either), but worth a future task if the dashboard ever needs accurate per-profile totals.
- The `pnl:daily:{pid}` hash is a circuit-breaker counter, NOT a dollar P&L cache. The original route's name (`get_pnl_summary` returning a `net_pnl` field from this hash) was misleading even before it broke. Now explicit: dollar fields come from snapshots; percentage from the hash.
