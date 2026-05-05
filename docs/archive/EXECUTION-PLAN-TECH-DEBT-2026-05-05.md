# Execution plan — open HIGH/MEDIUM tech debt (snapshot 2026-05-05)

> **Purpose:** Self-contained brief for fresh Claude Code sessions to clear the
> three remaining open HIGH/MEDIUM entries in `docs/TECH-DEBT-REGISTRY.md`.
> Each phase is independent and can be executed in a separate session — no
> phase requires the others to land first. Recommended order is by ascending
> blast radius (test-only fix → backend wiring → coordinated FE+BE change).

---

## 0 · Pre-flight context (≤15 min, shared by all phases)

Read in this order:

1. `CLAUDE.md` — financial precision, hooks, anti-patterns
2. `docs/TECH-DEBT-REGISTRY.md` — full table; the three OPEN HIGH/MEDIUM rows we are clearing are:
   - `hot_path` — AbstentionChecker CRISIS check disabled (MEDIUM, S, 2026-05-01)
   - `analyst` — weights stuck at 0.05/0.05/0.05, sample_count=0 (HIGH, M, 2026-05-05)
   - `api_gateway` — `routes/pnl.py` reads a Redis hash with `redis.get`+`json.loads` (HIGH, M, 2026-04-15)
3. `libs/messaging/channels.py` — verify any new keys/streams against the registry
4. `libs/core/enums.py` — for `Regime` (phase 1) and `Outcome` shape (phase 2 — note: there is **no** `Outcome` enum; closed_trades.outcome is TEXT 'win'/'loss'/'breakeven')

**Hard rules (from CLAUDE.md, apply to every phase):**

- `bash run_all.sh` only — never start/stop services individually
- All financial values use `Decimal`; never `float()` in financial paths
- New Redis keys/streams must be added to `libs/messaging/channels.py` first
- The `stale-read-guard.sh` hook blocks edits to files not Read in this session
- Don't fix unrelated tech debt opportunistically — append to the registry

**Commit message convention:**
```
fix(<service>): <subject>

[body — what changed and why]

Tech-Debt-Item: <service>/<short-tag>
```

---

## Phase 1 — Re-enable the AbstentionChecker CRISIS short-circuit

**Severity:** MEDIUM · **Effort:** S (≤30 min) · **Blast radius:** test-only

### Problem

`services/hot_path/src/abstention.py` has the CRISIS regime gate commented out at lines 21-23 and 40-42, with a comment that explicitly says "Re-enable before any paper or live run that should be trusted." `tests/unit/test_hot_path_signals.py::TestAbstentionChecker::test_abstain_on_crisis_regime` already encodes the production behaviour and fails on `main`.

### Files to read

- `services/hot_path/src/abstention.py` (47 lines, full file)
- `tests/unit/test_hot_path_signals.py` (find `TestAbstentionChecker` class — confirm the exact assertion and any other CRISIS-related cases in the same file)
- `services/hot_path/src/regime_dampener.py` lines 70-75 — note that `RegimeDampener.check` already short-circuits CRISIS to no-trade with a confidence multiplier of 0. Confirm we're not double-blocking; the abstention check is the cheaper/earlier gate, dampener is the deeper one. Both should agree.

### Files to change

| File | Change |
|------|--------|
| `services/hot_path/src/abstention.py` | Uncomment the two CRISIS branches (lines 21-23 in `check` and 40-42 in `check_with_reason`). Replace the leading "TEST-ONLY" docstring/comment with a one-liner explaining the gate's intent — or delete it entirely. The comment is now wrong. |

### Acceptance

- `poetry run pytest tests/unit/test_hot_path_signals.py -v` passes
- Both `check` and `check_with_reason` return `True` / `(True, "crisis_regime")` when `state.regime == Regime.CRISIS`
- No other test newly fails (`poetry run pytest tests/unit/ -q`)

### Commit

```
fix(hot_path): re-enable AbstentionChecker CRISIS short-circuit

The CRISIS regime gate was commented out for dashboard testing and never
restored. Test_abstain_on_crisis_regime has been failing on main since at
least 2026-05-01. Production behaviour is to abstain on CRISIS — restore it.

Tech-Debt-Item: hot_path/abstention-crisis
```

---

## Phase 2 — Wire closed-trade outcomes to the analyst weight engine

**Severity:** HIGH · **Effort:** M (~½ day) · **Blast radius:** backend only

### Problem

`agent_weight_history` shows every (symbol, agent) pair stuck at `weight=0.05, sample_count=0` despite 41 closed trades having occurred. Two compounding issues:

1. **No producer for `agent:closed:{symbol}`.** A grep of all `services/**` and `libs/**` for `agent:closed`, `CLOSED_KEY`, or `record_position_outcome` returns **zero matches**. The consumer in `libs/core/agent_registry.py:104-117` (`AgentPerformanceTracker.recompute_weights`) reads from this stream and early-returns when empty — so the EWMA learning path has never run.
2. **Stored weights are 0.05, not the AGENT_DEFAULTS.** `AGENT_DEFAULTS = {ta: 0.20, sentiment: 0.15, debate: 0.25}` (`libs/core/agent_registry.py:22-26`), but every persisted snapshot reads back 0.05 (= `MIN_WEIGHT`). Some path is writing 0.05 directly. The 5-min recompute loop in `services/analyst/src/main.py:35-71` falls back to `AGENT_DEFAULTS[agent_name]` only when Redis returns empty — so something is *populating* Redis with 0.05.

### Files to read (in order)

1. `libs/core/agent_registry.py` — full file. Note `CLOSED_KEY = "agent:closed:{symbol}"` (line 31), `MIN_SAMPLES = 10`, `MIN_WEIGHT = 0.05`, and the recompute formula in `recompute_weights` lines 104-186.
2. `services/analyst/src/main.py` lines 35-71 — the loop that calls `recompute_weights` and persists to TimescaleDB
3. `services/pnl/src/closer.py` — find the close-position pathway. Look for where realized P&L is computed and a `closed_trades` row is written. **This is the hook point** for emitting outcomes onto the stream (the writer doesn't exist yet — you are adding it).
4. `services/execution/src/executor.py` — find where `agent:position_scores:{position_id}` is written (mentioned in `services/pnl/src/closer.py:_get_position_snapshot`, around line 197-209). This is the entry-time score capture; the producer in pnl/closer just needs to read this back at close.
5. `libs/messaging/channels.py` — confirm `agent:closed:{symbol}` is NOT in the registered channels list. Add it as a documented stream key alongside the other `agent:` keys.

### Files to change

| File | Change |
|------|--------|
| `libs/messaging/channels.py` | Register `AGENT_CLOSED_OUTCOMES = "agent:closed:{symbol}"` constant for parity with the existing `agent:weights:{symbol}` etc. (Verify the existing convention — there may already be an `agent:` block to extend.) |
| `services/pnl/src/closer.py` | After a position closes and the `closed_trades` row is written: read back the entry-time score snapshot from `agent:position_scores:{position_id}`, build the payload `{position_id, outcome: "win"\|"loss"\|"breakeven", pnl_pct, agents_json: <jsonified per-agent {direction, score_at_signal, entry_price, timestamp}>, timestamp}`, and `XADD` to `agent:closed:{symbol}` with `MAXLEN ~ 1000` to bound the stream. Use `Decimal` for pnl_pct internally; serialise to string for JSON. |
| `tests/unit/test_pnl_closer.py` (or whatever covers closer; create if missing) | Test: closing a winning position emits exactly one stream entry on `agent:closed:{symbol}` with the expected payload. |
| `libs/core/agent_registry.py` | Investigate the 0.05 mystery. Likely candidates: (a) `recompute_weights` writes `weights = {}` → empty dict, then later `hset(weights_key, mapping=mapping)` is a no-op when empty — but expiry at line 186 (`expire(weights_key, 900)`) still runs, so something else must populate the hash. (b) Look for any test or seed script that writes `MIN_WEIGHT` directly. (c) Check if hot_path's `agent_modifier` ever writes back to `agent:weights:` — it shouldn't but verify. Once found, document or fix. |

### Acceptance

- After running `bash run_all.sh --local-frontend` and forcing one paper-trade close (via `POST /paper-trading/positions/{id}/close`):
  ```
  redis-cli XLEN agent:closed:BTC/USDT
  → ≥ 1
  ```
- Within 5 min (one recompute interval), `agent_weight_history` shows `sample_count > 0` for at least the symbol you closed
- Existing tests pass: `poetry run pytest tests/unit/ -q`
- New test in `test_pnl_closer.py` passes
- The 0.05 mystery has a documented root cause — either fix it, or if it turns out to be benign (e.g. the EWMA path correctly clamps a fresh outcome's weight to MIN_WEIGHT and that's fine), append a 1-line note to the registry explaining

### Commit

```
fix(pnl,analyst): emit closed-trade outcomes to weight engine

services/pnl/src/closer.py now XADDs onto agent:closed:{symbol} after every
position close, restoring the missing producer for AgentPerformanceTracker.
recompute_weights. Without this, sample_count never advanced past 0 and the
hot path read flat MIN_WEIGHT for every agent — meta-learning was dead.

Tech-Debt-Item: analyst/weights-stuck-at-min
```

---

## Phase 3 — Fix `routes/pnl.py` WRONGTYPE on hash + frontend display

**Severity:** HIGH · **Effort:** M (~1 day, includes UI verification) · **Blast radius:** API contract + frontend

### Problem

`services/api_gateway/src/routes/pnl.py:26-32` and `:67-69` call `redis.get(f"pnl:daily:{pid}")` followed by `json.loads(raw)`. The producer in `services/pnl/src/closer.py:179-189` writes a **hash**, not a string — fields are `date` (ISO date) and `total_pct_micro` (integer micro-percentage of profile equity, since UTC midnight, used by CircuitBreaker). Every call to these endpoints will raise `WRONGTYPE` when the hash exists, returning 500 to the frontend.

The hash schema does **not** contain dollar P&L at all. The previous string schema apparently had `net_pnl` (dollars). To restore the old API contract you need a new source for dollar P&L; the natural one is the `pnl_snapshots` table via `PnlRepository.get_snapshots`.

### Files to read

1. `services/api_gateway/src/routes/pnl.py` — full file (70 lines). Note the three endpoints: `/summary`, `/history`, `/{profile_id}`. Only `/summary` and `/{profile_id}` are broken; `/history` already uses `PnlRepository`.
2. `services/pnl/src/closer.py` lines 165-195 — confirms the hash schema (`date` + `total_pct_micro`)
3. `libs/storage/repositories/pnl_repo.py` — see `get_snapshots` and any "latest" helper. If a "latest snapshot" method doesn't exist, add one.
4. `frontend/lib/api/client.ts` lines 200-230 — TypeScript types for `total_net_pnl` and per-position `net_pnl`
5. `frontend/app/paper-trading/page.tsx` line 110, `frontend/app/trade/page.tsx` line 248 — consumers of the `total_net_pnl` field
6. `frontend/components/trade/PositionsPanel.tsx` lines 15-133 — uses `unrealized_net_pnl` (per-position, separate concern but same naming family)
7. `frontend/lib/types/telemetry.ts` line 151 — `net_pnl_session` is a separate telemetry-driven field, **not** the same as REST `total_net_pnl`. Don't conflate.

### Decision: API contract

Two viable shapes; pick one and document in the PR description.

**Option A (preserve frontend, requires new backend query):**
- `/summary` returns `{ total_net_pnl: number, positions: [{profile_id, net_pnl, ...}] }` — same as today
- Compute by querying `pnl_snapshots` for the latest row per active profile and summing `net_pnl_dollars`
- Keep the hash read for `circuit_pct` (a new field) so the FE can display the daily-loss circuit-breaker progress

**Option B (expose what the hash actually has):**
- `/summary` returns `{ daily_loss_pct_by_profile: {pid: float}, ... }`
- Frontend renames its field from `total_net_pnl` → `total_daily_loss_pct` and changes display from `$X` to `Y%`

Recommend **A**: less frontend churn, and the dollar value is what the user actually wants to see. The hash was always a private circuit-breaker counter; the route shouldn't have been reading it as if it held dollars.

### Files to change (Option A path)

| File | Change |
|------|--------|
| `libs/storage/repositories/pnl_repo.py` | Add `get_latest_snapshot(profile_id) -> Optional[dict]` that returns the most recent row from `pnl_snapshots`. Use `Decimal` for `net_pnl_dollars`. |
| `services/api_gateway/src/routes/pnl.py` | Rewrite `/summary` and `/{profile_id}` to use `PnlRepository.get_latest_snapshot`. For `/summary`, sum `net_pnl_dollars` across the user's active profiles. Add a helper to read the daily-loss-pct from the hash with `redis.hget(key, "total_pct_micro")` returning `Decimal(stored) / Decimal("1000000")`, expose as `daily_loss_pct` per profile. Drop `json.loads`. |
| `frontend/lib/api/client.ts` | Update the response type for `getPnlSummary` to match the new shape. Add `daily_loss_pct?: number` to per-position. |
| `frontend/app/paper-trading/page.tsx`, `frontend/app/trade/page.tsx` | Already read `total_net_pnl` — no change if the field name is preserved. If the new shape adds `daily_loss_pct`, optionally surface it. |
| `tests/unit/test_pnl_routes.py` (or extend existing) | Test the WRONGTYPE-safety: hash exists for a profile → endpoint returns 200 with dollar value from snapshots, not a 500. Test missing snapshot → returns 0 / null gracefully. |

### Acceptance

- `curl http://localhost:8000/pnl/summary -H "Authorization: Bearer <token>"` returns 200 with `total_net_pnl: <number>` even when `pnl:daily:{pid}` hash exists in Redis
- Same for `GET /pnl/{profile_id}`
- Frontend `paper-trading` and `trade` pages render the net P&L number with no console errors and no 500s in API logs
- `poetry run pytest tests/unit/ -q` clean
- Manually verify in browser: open `/paper-trading`, see the net P&L tile populated; force-close a position, see the value update on the next snapshot tick

### Commit

```
fix(api_gateway,frontend): pnl summary reads from snapshots, not the daily hash

routes/pnl.py /summary and /{profile_id} were json.loads-ing a Redis hash
written by services/pnl/src/closer.py, returning 500 WRONGTYPE for any
profile that had ever closed a trade. The hash holds total_pct_micro for the
circuit breaker — never dollar P&L. New code reads dollars from
pnl_snapshots and exposes the hash's percentage as a separate, named field.

Tech-Debt-Item: api_gateway/pnl-routes-wrongtype
```

---

## Reporting

After **each phase** (not at the end of all three), write a short
`docs/EXECUTION-REPORT-TECH-DEBT-<phase>-<YYYY-MM-DD>.md` with:

- TL;DR table — entry resolved, commit SHA, lines changed
- The exact diff against `docs/TECH-DEBT-REGISTRY.md` — flip the row from OPEN to RESOLVED with a one-line root-cause summary (don't rewrite the description; preserve it for history)
- Any tangential findings logged as new registry entries (don't fix them)
- Test command output proving the acceptance criteria

If a phase reveals the entry is wrong/no-longer-applicable (e.g. someone fixed
it in a separate change), note that and just flip the row to RESOLVED with
the explanation — don't manufacture work to justify the session.

---

## Out of scope for this plan

- The LOW-severity `ingestion / Coinbase adapter not wired in` entry — leave it
- Documentation gaps (G-* items in `docs/DOCUMENTATION-GAPS.md`)
- The deferred D.PR5 (LLM post-mortems) — separate plan in `EXECUTION-PLAN-D-PR5.md`
- Resetting `agent_weight_history` to AGENT_DEFAULTS — phase 2 fixes the producer; the existing 0.05 rows are accurate audit history of what the system actually computed and should remain
