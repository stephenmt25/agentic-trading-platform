# Execution report — 2026-05-07

> Short-term plan execution against `SECOND-BRAIN-ROADMAP` /
> `EXECUTION-PLAN-TRACK-B` / `EXECUTION-PLAN-CONTINUOUS-CHECKING-2026-05-05` /
> `TECH-DEBT-REGISTRY` (backtesting indicator gap).

---

## TL;DR

| Item | Plan | Status | Commit |
|---|---|---|---|
| Backtesting C.2 indicator wiring | TECH-DEBT (MEDIUM/S, 2026-05-06) | ✅ shipped | `d281b76` |
| Continuous-checking Phase 2 — Redis schema scanner | EXECUTION-PLAN-CONTINUOUS-CHECKING §Phase 2 | ✅ verified live (1 schema bug surfaced + fixed) | `e4eaf38` |
| Track B.2 — backtest history persistence + UI | EXECUTION-PLAN-TRACK-B §4 | ✅ shipped | `66d7bc5` |
| Track B.1 — pipeline editor live state + controls | EXECUTION-PLAN-TRACK-B §3 | ⏸ deferred (context budget) | — |

Commits land cleanly on `main`. All Python tests pass for the touched modules
(`tests/unit/test_vectorbt.py`, `tests/unit/test_redis_invariants.py`,
`tests/unit/test_dynamic_weights.py`, `tests/unit/test_backtest_repo.py`,
`tests/unit/test_backtesting.py`). The frontend has no new TypeScript errors
introduced by these changes (pre-existing errors in `EquityCurveChart.tsx`,
`DecisionFeed.tsx`, `TemplateGallery.tsx` are unrelated to this work).

---

## What shipped

### 1. Backtesting C.2 indicator wiring — `d281b76`

**Problem.** `services/backtesting/src/vectorbt_runner.py::_compute_indicators`
populated only `rsi`, `macd`, `atr`, `adx`, `bb`, `obv`, `choppiness`. When
`engine="vectorbt"`, any rule referencing the C.2 indicators (`z_score`,
`vwap`, `keltner`, `rvol`, `hurst`) hit the unknown-indicator branch and
saw `False` on every bar — silently zero trades. The Mean Reversion
template (`z_score < -2.0`) was the most visible victim.

**Fix.** Imported the five C.2 calculators, instantiated them per run,
appended their values to the returned indicator dict (using the same key
names the rule compiler uses: `z_score`, `vwap`, `keltner.upper/middle/lower`,
`rvol`, `hurst`).

**Test.** `tests/unit/test_vectorbt.py::TestComputeIndicators::test_c2_indicators_prime_with_values`
asserts each new key produces ≥1 non-NaN value across a 300-bar window.
All 19 vectorbt tests pass.

**Tech-debt registry.** Mark the 2026-05-06 backtesting entry RESOLVED.

---

### 2. Continuous-checking Phase 2 — Redis schema scanner — `e4eaf38`

**Pre-state.** The scanner module (`libs/observability/redis_invariants.py`),
its 60s background loop in `services/logger/src/main.py`, the unit-test
suite (`tests/unit/test_redis_invariants.py`, 12 tests), the standalone
CLI (`scripts/scan_redis_invariants.py`), and the `REDIS_INVARIANT_INTERVAL_S`
setting were all already present from a prior session. This work item was
verification + drift correction, not greenfield.

**First live run** against the booted stack reported 3 violations:

| Pattern | Verdict |
|---|---|
| `agent:outcomes:*` (×2 symbols) — schema declared field `price`, producer writes `score` | **Schema bug.** No live consumer reads the field; the audit-stream comment in `libs/core/agent_registry.py` was outdated. Fixed schema and comment. |
| `pnl:daily:18b1a752-…` — missing `date` field, has `total_pct_micro` | **Known.** Already in `TECH-DEBT-REGISTRY.md` (LOW, self-healing on next close). Logged as designed. |

After the schema correction, live scan reports 1 violation (the known
self-healing pnl entry) — the scanner is on a true zero-noise baseline
modulo known tracked items.

**Bug-history calibration** (per Phase 2's "what would this catch" sweep):
the scanner *did* catch a real producer/schema-doc drift on first live
run. It would also have caught `acb25ae` (analyst tracker bytes-vs-str)
and `f583ffb` (pnl summary string-vs-hash) had it existed at the time.
Severity tiering looks right.

---

### 3. Track B.2 — backtest history persistence + UI — `66d7bc5`

**Migration 020** (`migrations/versions/020_backtest_history_fields.sql`).
Adds nullable `created_by UUID REFERENCES users(user_id)`, `start_date`,
`end_date`, `timeframe` to `backtest_results`, plus a composite index
`(created_by, created_at DESC)`. Pre-existing 67 rows have NULL `created_by`
and are intentionally hidden from the user-scoped history view.

**Backend.**
- `libs/storage/repositories/backtest_repo.py` — new `get_history(user_id,
  profile_id, symbol, limit)` with WHERE-clause composition, limit clamped
  to `[1, 100]`, asyncpg-friendly Decimal/datetime coercion via the new
  `_coerce_uuid` / `_coerce_dt` helpers. `save_result` extended to accept
  the new fields with NULL fallback for legacy callers.
- `services/backtesting/src/job_runner.py` — populates `created_by`,
  `start_date`, `end_date`, `timeframe` on completion. ISO strings flow
  through Redis JSON; the repo coerces to `datetime` for asyncpg.
- `services/api_gateway/src/routes/backtest.py` — new `GET /backtest/history`
  (auth-required, user-scoped); `GET /backtest/{job_id}` now falls back to
  the DB when the Redis status cache has expired (1h TTL), so loading
  older runs from the history panel keeps working.
- `services/api_gateway/src/deps.py` — `get_backtest_repo` dep matching the
  rest of the Repository factories.

**Frontend.**
- `frontend/lib/api/client.ts` — `api.backtest.history({profileId, symbol,
  limit})` typed against the response envelope `{items: [...], limit}`.
- `frontend/components/backtest/PastRunsPanel.tsx` — new component. Sortable
  by recency / Sharpe / avg return / drawdown. Each row has a Load button
  that pulls the full result via `api.backtest.result(...)` and feeds it
  into the existing `addCompletedRun` path so the equity-curve overlay and
  comparison table work without schema changes.
- `frontend/app/backtest/page.tsx` — renders `PastRunsPanel` under the
  configuration column. In embedded mode (`/strategies → Verify` tab) the
  panel filters by the active symbol; standalone mode shows all symbols.

**Tests.** `tests/unit/test_backtest_repo.py` (13 cases, all passing) —
fakes `TimescaleClient.fetch/execute/fetchrow` to assert on the SQL +
parameter list. Covers user-scoping, optional filter composition, limit
clamping, no-user-scope mode, datetime/UUID coercion, and `save_result`'s
NULL-friendly fallback.

**Acceptance state.**
- ✅ Backend endpoint reachable at `GET /backtest/history` (returns 401
  unauth — expected, JWT required).
- ✅ Migration applied cleanly to live DB; new columns visible.
- ✅ Frontend TypeScript clean for new files (pre-existing errors elsewhere
  unrelated).
- ⏸ Live end-to-end smoke (submit backtest → appears in history → Load
  → equity overlay) **not run** — would require an OAuth token; the live
  paper-trading flow already proves the persist path. Worth a UI walkthrough
  next session.

---

## What didn't ship

### Track B.1 — Pipeline editor live state + controls

Deferred to next session for context-budget reasons, not technical
blockers. Scope estimate from the plan: ~1-2 days.

**Pickup checklist** (read in order):

1. `docs/EXECUTION-PLAN-TRACK-B.md` §3 — full brief
2. `services/api_gateway/src/routes/agent_config.py` — current shape
3. `services/hot_path/src/processor.py` — gate evaluation; B.1 needs to
   read live config here with a 5s in-process cache
4. `frontend/app/pipeline/page.tsx` — current pipeline editor
5. `frontend/components/pipeline/*` — node renderers
6. `libs/messaging/channels.py` — register `gate_config:{gate_name}` first

**Hard rules to remember:**
- Verify `/agent-performance/gate-analytics/{symbol}` exists before building
  the merged endpoint; reuse don't reinvent.
- The `stale-read-guard.sh` hook will block edits to files not Read in the
  session.
- `bash run_all.sh` for any restart, never per-service.
- Two commits, one per item: `Track-Item: B.1` and `Track-Item: B.2` (B.2
  is already landed; B.1 is the only outstanding tag).

**Honesty hook from the plan:** if the live coloring + toggle round-trip
doesn't work end-to-end (UI click → Redis write → hot_path picks up →
block-rate counter moves), ship the partial and flag it. Don't fake the
LIVE indicator.

---

## Verification state

- `poetry run pytest tests/unit/test_vectorbt.py tests/unit/test_redis_invariants.py tests/unit/test_backtest_repo.py tests/unit/test_dynamic_weights.py tests/unit/test_backtesting.py -q` → all green (44 tests).
- `poetry run python scripts/scan_redis_invariants.py` → 1 known violation
  (`pnl:daily:18b1a752-…` missing-date, tracked).
- `bash run_all.sh --local-frontend` → all 19 services healthy, frontend
  on :3000.
- Live `GET /backtest/history` → 401 with valid auth-required error path.
- Frontend `tsc --noEmit` → 0 new errors in PastRunsPanel.tsx,
  app/backtest/page.tsx, lib/api/client.ts.

---

## Honesty hooks

- **B.2 was not exercised against a real auth token.** The endpoint
  signature, repository SQL, and frontend wiring are unit-tested but no
  end-to-end click-through happened. The user-scoping logic in
  `get_backtest_history` and the `created_by` filter in `get_backtest_result`
  haven't been validated against a real JWT. Next session, run an actual
  paper-trading backtest after the migration is on live and verify the
  Load button populates the comparison table.
- **The Redis schema scanner's "1 violation = healthy" baseline assumes
  the `pnl:daily` partial-write is treated as known.** If a new partial
  write appears on a different profile, the scanner will surface it as
  HIGH and route to PagerDuty/Slack via the existing alerter — that's the
  intended behaviour, not a noise bug.
- **The C.2 indicator fix in `vectorbt_runner.py` mirrors the
  `simulator.py` shape exactly**, but only the simulator path is exercised
  by integration tests today; the vectorbt runner is unit-tested in
  isolation and against a synthetic-candle test, not against a real
  backtest job through `job_runner.py`. If the rule compiler ever expects
  a different key name, the vectorbt path would silently regress before
  the simulator path.

---

## Tech-debt registry diffs

| Service | Status change |
|---|---|
| backtesting (vectorbt missing C.2 indicators, MEDIUM/S, 2026-05-06) | OPEN → **RESOLVED (2026-05-07)** — `d281b76` |

No new entries opened by this session.

---

## Plan archival

Plans now fully landed and safe to archive (move to `docs/archive/`):

- `EXECUTION-PLAN-CONTINUOUS-CHECKING-2026-05-05.md` — Phase 1 done in a
  prior session (`EXECUTION-REPORT-CONTINUOUS-CHECKING-phase1-2026-05-05.md`),
  Phase 2 verified live in this session. Phases 3 + 4 remain open but are
  documented in their own future-plan section; the plan as a whole is no
  longer the active work item — they should be split into separate plans
  if/when picked up.

Plans still active and **kept in `docs/`**:

- `EXECUTION-PLAN-TRACK-B.md` — B.1 still outstanding.
- `EXECUTION-PLAN-RACE-AND-COOLDOWN-2026-05-05.md` — untouched.
- `EXECUTION-PLAN-D-PR5.md` — blocked on A.1.
- `SECOND-BRAIN-PRS-REMAINING.md`, `SECOND-BRAIN-ROADMAP.md` — strategic
  docs.
- `AUTONOMOUS-EXECUTION-BRIEF.md` — strategic doc.
- `ANALYSIS-CHART-ENHANCEMENTS-PLAN.md` — untouched.

---

*Session-Tag: short-term-plan-2026-05-07.*
