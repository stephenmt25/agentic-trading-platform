# Execution plan — Track B (Pipeline editor live state + Backtest history)

> **Purpose:** Self-contained brief for a fresh Claude Code session executing
> Track B (B.1 + B.2) from `docs/AUTONOMOUS-EXECUTION-BRIEF.md`. As of
> `2026-05-04` Tracks A, C, and D.PR2 are shipped; Tracks B remains the
> outstanding gap. Read top-to-bottom before touching code.

---

## 0 · Pre-flight context (≤10 minutes)

Read in this order:

1. `CLAUDE.md` — financial precision, hooks, anti-patterns
2. `docs/AUTONOMOUS-EXECUTION-BRIEF.md` §2 (hard rules), §4 (verification + commit format), §7 items B.1 + B.2 (lines 441-516)
3. `services/api_gateway/src/routes/agent_config.py` — current shape; B.1 extends this
4. `services/api_gateway/src/routes/backtest.py` — current shape; B.2 extends this
5. `services/hot_path/src/processor.py` — gate evaluation; B.1 needs this to read live config
6. `services/backtesting/src/job_runner.py` — backtest completion path; B.2 hooks here
7. `frontend/app/pipeline/page.tsx` — current pipeline editor; B.1 modifies
8. `frontend/app/backtest/page.tsx` — current backtest UI; B.2 modifies
9. `frontend/lib/api/client.ts` — API client; both items extend
10. `libs/messaging/channels.py` — Redis channel/key registry. **B.1 must register any new keys here. Do not invent.**
11. `migrations/versions/008_backtest_results.sql` — current schema, may need extension (see B.2)

After reading, write down on a scratchpad:
- The exact shape of `backtest_results` columns
- The current Redis key conventions in `channels.py`
- The auth scheme used by `agent_config.py` routes (so new endpoints match)
- Whether `frontend/components/pipeline/` contains node renderers or if they're inline in `page.tsx`

---

## 1 · Mission

Ship B.1 and B.2 in a single session. Both are self-contained and don't depend on each other.

**Honesty hooks:**
- If you can't get the live coloring + toggle round-trip working end-to-end (UI click → Redis write → hot_path picks up → block rate changes), **stop and ship the partial**. Don't fake the live indicator.
- If `backtest_results` is missing required columns and migration 019 is already taken, use the next available migration number — do not silently re-use 019.

---

## 2 · Hard rules (from CLAUDE.md)

- Use `bash run_all.sh` always; never start/stop services individually
- Verify Redis channels and keys against `libs/messaging/channels.py`
- All financial values use `Decimal` (not relevant here, but a reminder)
- New SQL goes in `migrations/versions/NNN_*.sql` — find the next free `NNN`
- New endpoints follow the existing auth pattern (Bearer JWT via `deps.py`)
- The `stale-read-guard.sh` hook blocks edits to files not Read in this session — `Read` first

### Commit message format

```
feat(area): one-line subject

[body]

Track-Item: B.1
Session-Tag: track-b-execution-<date>
```

Use `B.1` and `B.2` separately — no comma-list.

---

## 3 · Item B.1 — Pipeline editor live state + controls

### Goal
`/strategies` → Builder tab (which embeds `/pipeline`) shows each gate node colored by live state with live block-rate counters; toggle controls hot-apply via `config_changes`.

### Current state (verified 2026-05-04)
- `/agent-config/gates` endpoint **does not exist**
- `gate_config:*` Redis key pattern **does not exist** in `libs/messaging/channels.py`
- The pipeline editor renders nodes statically; no live state
- `/agent-performance/gate-analytics/{symbol}` endpoint **does exist** (verify by grep) — reuse, don't re-implement

### Files

**Backend:**
- `libs/messaging/channels.py` — register `gate_config:{gate_name}` key pattern
- `services/api_gateway/src/routes/agent_config.py` — add the two new endpoints
- `services/hot_path/src/processor.py` — read gate config from Redis at start of each tick (cache for ~5s to avoid Redis hammering)
- `migrations/versions/NNN_config_changes.sql` — only if `config_changes` table doesn't already exist (verify first; the brief implies it does)

**Frontend:**
- `frontend/lib/api/client.ts` — add `api.gates.list()`, `api.gates.update(name, payload)`
- `frontend/app/pipeline/page.tsx` — add 10s poll loop; pass live state to nodes
- `frontend/components/pipeline/*.tsx` — extend node renderers with color + counter + context menu

### Steps

1. **Verify gate analytics endpoint.** `curl /agent-performance/gate-analytics/BTC%2FUSDT`. If 200 with shape `[{gate_name, block_rate, ...}]` you're good. If not, abort and ask — don't reverse-engineer.
2. **Register Redis key.** Add to `libs/messaging/channels.py`:
   ```python
   GATE_CONFIG_KEY = "gate_config:{gate_name}"  # JSON {enabled: bool, threshold: float}
   ```
3. **Add `GET /agent-config/gates`** in `agent_config.py`:
   - Returns list of `{gate_name, enabled, threshold, block_rate_1h}` for every known gate
   - Reads `gate_config:*` keys (use `SCAN`, not `KEYS`)
   - Joins with the gate-analytics endpoint's data for `block_rate_1h`
   - Returns sane defaults if no Redis entry exists yet
4. **Add `PATCH /agent-config/gates/{gate_name}`** in `agent_config.py`:
   - Accepts `{enabled?: bool, threshold?: number}`
   - Writes the new config to Redis under `gate_config:{gate_name}`
   - Logs to `config_changes` table (if it exists; check first)
   - Returns the new state
5. **Hot-path consumer.** In `services/hot_path/src/processor.py`, before each gate evaluation:
   - Look up `gate_config:{gate_name}` from Redis (cache 5s in-process to avoid hammering)
   - If `enabled=false`, skip the gate entirely (record nothing — gate is "off")
   - If `threshold` is set, use it instead of the hardcoded threshold
   - Default behavior preserved when no Redis entry exists (for back-compat)
6. **Frontend client.** Add to `frontend/lib/api/client.ts`:
   ```typescript
   gates: {
     list: () => api.get<GateState[]>("/agent-config/gates"),
     update: (name: string, payload: GateUpdate) =>
       api.patch(`/agent-config/gates/${name}`, payload),
   }
   ```
7. **Pipeline page poll loop.** In `frontend/app/pipeline/page.tsx`, `useEffect` polling every 10s. Pass `gateStates` map down to node renderers.
8. **Node rendering.** In each gate node component:
   - Color: `enabled && block_rate < 50%` → green, `enabled && >= 50%` → amber, `!enabled` → grey
   - Annotation: `"blocked X% of last hour"` text overlay
   - Right-click → context menu with "Enable / Disable" toggle and threshold slider, calling `api.gates.update(...)`
9. **"Live" badge.** Add a small green dot with "LIVE" text near the canvas header so users know it's reflecting reality.

### Acceptance
- `curl -s http://localhost:8000/agent-config/gates -H "Authorization: Bearer $TOKEN" | python -m json.tool` returns at least the abstention, hitl, and regime_mismatch gates
- Open `/strategies` → Builder tab. Every gate has a color reflecting current live state (regime gate likely grey if disabled per current demo).
- Toggle the regime gate via the UI; within 10s the block rate counter starts moving.
- A new row in `config_changes` records the toggle.

### Test commands
```bash
# Backend smoke
TOKEN="<paste from frontend session>"
curl -s http://localhost:8000/agent-config/gates -H "Authorization: Bearer $TOKEN" | python -m json.tool
curl -s -X PATCH "http://localhost:8000/agent-config/gates/regime_mismatch" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"enabled": false}' | python -m json.tool

# Hot_path consumes within next tick — verify a fresh trade decision logs gate_disabled rather than evaluating regime_mismatch
docker exec deploy-timescaledb-1 psql -U postgres -d praxis_trading -c \
  "SELECT outcome, COUNT(*) FROM trade_decisions WHERE created_at > NOW() - INTERVAL '5 minutes' GROUP BY outcome;"

# UI: visual inspection at http://localhost:3000/strategies (Builder tab)
```

### Out of scope (B.1)
- Editing gate logic itself — only enabled/disabled + threshold
- Per-profile gate overrides — global only
- Undo/redo — `config_changes` is the audit trail; revert via a follow-up PATCH

---

## 4 · Item B.2 — Backtest history persistence + UI

### Goal
Completed backtest runs persist to `backtest_results`; `/backtest` shows a "Run history" panel with sortable past runs and a "load" button that overlays the equity curve into the comparison table.

### Current state (verified 2026-05-04)
- `backtest_results` table exists (migration 008, made `Decimal` in 009). **Verify columns** — may need extension migration if `created_by`, `profile_id`, `equity_curve` (JSONB) are missing.
- `services/backtesting/src/job_runner.py` runs backtests but does NOT write the final result row.
- `GET /backtest/history` endpoint **does not exist**.
- `RunHistoryPanel` component **does not exist**.

### Files

**Backend:**
- `services/backtesting/src/job_runner.py` — write result row on completion
- `migrations/versions/NNN_backtest_results_extra_fields.sql` — only if columns are missing (check first)
- `services/api_gateway/src/routes/backtest.py` — add `GET /backtest/history`
- `libs/storage/repositories/backtest_repo.py` (or wherever the existing query-by-id lives) — add `get_history(profile_id, user_id, limit)`

**Frontend:**
- `frontend/lib/api/client.ts` — add `api.backtest.history(...)`
- `frontend/components/backtest/RunHistoryPanel.tsx` (new) — list of past runs with load button
- `frontend/app/backtest/page.tsx` — render `RunHistoryPanel` alongside the new-run form

### Steps

1. **Verify schema.** `\d backtest_results` in psql. If `profile_id` is `TEXT NOT NULL DEFAULT ''` (per migration 008), tighten to `UUID REFERENCES trading_profiles(profile_id)` via a new migration **only if the existing data is empty or all-uuid**. Otherwise, leave it text and document the limitation.
2. **Add missing columns** if needed via `migrations/versions/NNN_backtest_history_fields.sql`:
   ```sql
   ALTER TABLE backtest_results
       ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(user_id),
       ADD COLUMN IF NOT EXISTS equity_curve JSONB;
   CREATE INDEX IF NOT EXISTS idx_backtest_results_user_created
       ON backtest_results (created_by, created_at DESC);
   ```
3. **Patch `job_runner.py`** to insert one row into `backtest_results` on `BacktestStatus.COMPLETED`. Use the existing repo or add a `write_result()` helper. Include all metric columns + the `equity_curve` JSONB.
4. **Add `GET /backtest/history`** in `routes/backtest.py`:
   ```
   GET /backtest/history?profile_id=&user_id=&limit=20&order=desc
   ```
   - User-scoped by default (filter on `created_by = current_user.user_id`)
   - Returns rows newest-first
   - Default `limit=20`, max 100
5. **Frontend `RunHistoryPanel`:**
   - Fetches via `api.backtest.history(...)` on mount
   - Renders a list with date, symbol, period, headline metrics (total return %, sharpe, max DD)
   - Each row has a "Load" button that calls `GET /backtest/{job_id}` and pushes the result into the comparison table state
   - Sort by date (default), total return, sharpe
6. **Pin/unpin** in localStorage (no schema change). Pinned runs show first.
7. **Page integration.** `frontend/app/backtest/page.tsx` renders `RunHistoryPanel` in a left rail or above the new-run form.

### Acceptance
- Run a backtest via UI. Refresh. The run appears in Run history with correct metrics.
- Click "Load" on a past run → its equity curve overlays the comparison table.
- API: `GET /backtest/history` returns the run, scoped to the current user.
- Pinned runs persist across page refreshes.

### Test commands
```bash
# 1. Submit a backtest via UI (or curl). Note the job_id.
TOKEN="<paste from frontend session>"
JOB_ID="<from response>"

# 2. Wait for completion
while true; do
  STATUS=$(curl -s "http://localhost:8000/backtest/$JOB_ID" -H "Authorization: Bearer $TOKEN" | jq -r .status)
  [ "$STATUS" = "completed" ] && break
  sleep 5
done

# 3. Verify history shows it
curl -s "http://localhost:8000/backtest/history?limit=5" -H "Authorization: Bearer $TOKEN" | python -m json.tool

# 4. Verify UI: visual inspection at http://localhost:3000/backtest
```

### Out of scope (B.2)
- Cross-user run sharing (user-scoped only)
- Run replay against fresh data (a separate feature)
- Bulk delete / archive (defer)

---

## 5 · Sequencing within the session

Both items are independent. Recommended order:

1. **B.2 first** (smaller blast radius — backend write + new endpoint + UI panel)
2. **B.1 second** (touches `hot_path/processor.py` which is in the live trading path; do it after B.2 is committed so a regression is easy to bisect)

Stop after each item is committed and verified end-to-end. Do not bundle both into one commit.

---

## 6 · Final acceptance for the session

```bash
# All unit tests still green (no regressions)
poetry run pytest tests/unit/ -q

# Stack runs clean
bash run_all.sh --stop && bash run_all.sh --local-frontend
# All services on /health → 200

# Manual verifications above passed for both B.1 and B.2

# Git log shows two commits with proper Track-Item tags
git log --grep "Track-Item: B" --oneline
```

---

## 7 · Reporting

End-of-session: write `docs/EXECUTION-REPORT-TRACK-B-<YYYY-MM-DD>.md` following the structure of `docs/EXECUTION-REPORT-2026-05-04.md`. Include:
- TL;DR table (B.1 / B.2 status, commit hashes, blockers)
- What shipped per item (commit hash + bullets)
- What didn't ship (be specific — "B.1 hot_path consumer didn't pick up live config" is more useful than "B.1 partial")
- Verification state (what passed, what wasn't tested)
- Honesty hooks (untested code paths, assumptions made)

---

*Estimated effort: B.1 ~1-2 days, B.2 ~1 day. Total ~2-3 days for one engineer.*
