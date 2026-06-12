# Debt Burn-Down Handoff — Next Claude Session (ultracode)

**Date:** 2026-06-13 · **Author:** Claude Code (handler) · **Mission:** clear EVERY deferred item except those awaiting partner input, in one session, via multi-agent orchestration.
**This document supersedes `NEXT-SESSION-PLAN-2026-06-13.md` as the next session's directive** (EN-W3 Tokyo substrate shifts one session later; its handoff stays valid).
**Status:** ready to execute. Branch `feat/snappy-honest-edge` @ `ead3b85`, CI green.

---

## 0 · How to run this session

You are an ultracode orchestrator. The work below is pre-decomposed into **lanes with strict file ownership** (the proven pattern from the 06-11/06-12 sessions — disjoint files, shared files split by named region, stale-read-guard tolerated via re-Read + re-apply). Run lanes within a wave in parallel; waves are barriers. Every lane agent must:

- Read `CLAUDE.md` first. Decimal contract is ZERO TOLERANCE; hooks are active (Read-before-Edit; float-gate; channel-name gate).
- Run `poetry run black <touched .py files>` + `isort` after edits, keep `# float-ok` markers on the call's own line.
- Add/extend tests in its OWN test modules; run its targeted tests; report honestly via structured output (files_changed / decisions / tests_run / open_issues / registry_updates).
- NOT commit (orchestrator commits per-lane), NOT start/stop services, NOT touch another lane's files.

**Definition of done per item** — one of:
- **FIXED**: code landed + tests + registry row updated to RESOLVED with evidence.
- **VERIFIED**: evidence gathered, row closed or re-opened with new facts (for verify-class items).
- **TRIAGED-CLOSED**: row status updated to a terminal disposition (wontfix / deferred-by-design / blocked-on-credentials) with rationale. No silent skips.

**Session gates (all blocking):** full `pytest tests/unit` green · `python scripts/ci/guards.py` (AFTER `git add` — guards only sees tracked files) · black/isort/ruff · **mypy green & flipped to blocking (item W2-2)** · **ESLint green & flipped to blocking (item W2-1)** · `tsc --noEmit` · vitest · `next build` · stack relaunch via `bash run_all.sh --local-frontend` + zero `loop crashed` + soak intact (4 OPEN positions) · prod-build live verification on **:3000 only** · push + CI green.

---

## 1 · Verified environment facts (saves you the exploration)

- **Stack**: 19 services via `run_all.sh` (ports: gateway 8000, ingestion 8080 … debate 8096; strategy = portless worker; dev frontend :3001). Infra: docker `deploy-redis-1` / `deploy-timescaledb-1`.
- **Redis is DB 1**: `docker exec deploy-redis-1 redis-cli -a changeme_redis_dev --no-auth-warning -n 1 …` (db0 is a decoy). TimescaleDB: `docker exec deploy-timescaledb-1 psql -U postgres -d praxis_trading`.
- **positions.status is UPPERCASE** (`'OPEN'`).
- **Soak**: profile `a05adba2-5128-4bef-bb92-a3cb429b55e1` (ACTIVE, RSI<35 ETH/USDT). 4 OPEN positions total — 3 carry dash symbol `BTC-USDT` (2 synthetic-looking: High Volume Breakout `fbb3e0f3…`/`e077690d…` entries 1.0005/100.05; 1 real: Mean Reversion `f5603599…` BTC @75037.50). NEVER fire NEUTRALIZE/FLATTEN; restarts are fine.
- **Owner user UUID** (for any direct queue enqueue / DB writes needing created_by): `6322b6fa-d425-51d7-a818-088c19275228`.
- **Baselines @ ead3b85**: 770 pytest · 91 vitest · tsc/build/guards/black/isort/ruff green · mypy ADVISORY (~99 real errors) · ESLint ADVISORY (62 errors/236 warnings).
- **Decay baselines are latest-wins** — any backtest carrying `profile_id` becomes that profile's baseline. Worked example incl. direct-enqueue payload shape: `scripts/en_w2_edge_triage.py`.
- **Wire decimals on pnl channels are str-encoded** (FE parses via `parsePnlMessage`); `portfolioStore` is position-keyed (`PnLPositionSnapshot`, `applyPnlSnapshots`).
- **CORS** (`.env` `PRAXIS_CORS_ORIGINS`) allows :3000/:3001 only — prod verification on :3000.
- **gh CLI**: `C:\Program Files\GitHub CLI\gh.exe`; token via `git credential fill` cmd-redirect (`cmd /c "git credential fill < %TEMP%\cred.txt"`); multiline commits via `git commit -F` + `[System.IO.File]::WriteAllText` (no BOM).
- **307 note**: every gateway GET from the FE currently pays a trailing-slash redirect — do not misread doubled requests as a leak (item F1-6 fixes it).

---

## 2 · Pre-made engineering decisions (do NOT stall on these; log each in DECISIONS.md where marked ⚖)

| # | Decision | Ruling |
|---|---|---|
| D-A ⚖ | Row 50 direction-aware EWMA scoring design | Score each agent on whether ITS call was right: `hit = 1.0` iff (agent direction == executed direction AND outcome == win) OR (agent direction == opposite AND outcome == loss); direction missing/ABSTAIN → skip that agent for that trade (no update). Then **reset the EWMA Redis state** (`agent:tracker:*`, `agent:weights:*`) per the 2026-05-05 clean-baseline precedent — the interpretation of every prior sample changed. |
| D-B ⚖ | Service-local `POST /backtest/sweep` | **RETIRE** it: delete the route + `SweepRequest` (schemas.py ~487) + its tests; the gateway `POST /backtest` (auth'd, Decimal, grids) is the sole entry. Grep FE for callers first (none expected — the backtest page uses the gateway). |
| D-C | Dead pnl components | **DELETE** `components/pnl/PnLDisplay.tsx`, `components/pnl/PortfolioSummaryCard.tsx`, `lib/hooks/useRealtimePnl.ts`, orphaned `PnLSnapshot` type in `lib/types/index.ts` + their tests. Mounting them serves no surface. |
| D-D ⚖ | Row 67 risk-limit default authority | **settings wins** (live ExitMonitor + exit_policy already resolve from settings). Delete/repoint `DEFAULT_RISK_LIMITS` in schemas.py so there is one authority; keep RiskLimitsPayload defaults sourced from settings or removed. Verify no behavior change via exit_policy tests. |
| D-E | Row 66 bounds | Add `ge`/`le` bounds (pcts in (0,1], hours > 0, drop `extra="allow"`) ONLY after `SELECT` confirms every existing `trading_profiles.risk_limits` row is in-bounds; if any row violates, normalize that row first (log it), then tighten. |
| D-F | D-12 LLM intent classification (501) | **TRIAGED-CLOSED (wontfix)**: the command palette shipped without it; delete the 501 stub branch or leave with a comment, update DOCUMENTATION-GAPS. |
| D-G | D-18 llama-cpp optional / D-21 archiver GCS export | **TRIAGED-CLOSED (by design / blocked-on-cloud)**: D-18 is documented-by-design; D-21 stays deferred until a GCS bucket exists (local-only deployment). Update statuses with rationale. |
| D-H | Row 38 managed-agent cookbook | **TRIAGED-CLOSED (deferred-by-design)**: registry explicitly says do not pursue until a concrete external-surface ask exists. Reword status so it stops counting as actionable debt. |
| D-I | Row 12 Coinbase adapter | Wire it (uncomment `get_adapter("COINBASE", …)`) ONLY if sandbox creds exist in `.env`; else **TRIAGED-CLOSED (blocked-on-credentials)** with the exact env keys needed listed in the row. |
| D-J | Dash-symbol DB rows | **Normalize symbols only** (`UPDATE positions SET symbol='BTC/USDT' WHERE symbol='BTC-USDT'` — 3 rows; record before/after in the report). Do NOT close/delete any position (the 2 synthetic ones are the operator's call — listed in §6 partner items as a courtesy flag, non-blocking). |
| D-K | Row 41 pyramid race | Root cause needs a live recurrence — ship the **tripwire** instead: a burst detector at the hot_path order-publish site (count per profile per rolling 60s; WARN at >10, CRITICAL log + `pubsub:system_alerts` at >25; NO auto-halt — that wiring is EN-W4's auto-deprecation territory). Row status → "tripwire armed, root-cause on next recurrence". |
| D-L | G-1/G-2/G-5/G-11 need real load data | Publish **v1 PROPOSED** docs: derive what code/config already pins (fast-gate 50ms, rate limits, poll cadences), run a bounded local benchmark for WS connections (script: open N=200 WS clients against :8000/ws, record ceiling/latency) and symbol-scaling estimate, and mark every number `PROPOSED (dev-box)` pending ops review. A PROPOSED doc with method beats no doc. |
| D-M | Rows 22/39 (missing backend stores) | Implement the **S/M-sized subset** end-to-end (see B7) and TRIAGE the rest into precise per-endpoint rows with schemas sketched — the original rows are too coarse to burn down honestly in one lane; replace them with implementable rows + land the quick ones. |

---

## 3 · WAVE 0 — orchestrator inline (before fan-out)

1. Session checklist: `git fetch --all --prune`; verify branch/CI; boot state (stack likely already up — keep it); `loop crashed` grep; 770/91 baselines; soak = 4 OPEN.
2. Apply D-J (dash-row symbol normalization) + verify `risk:portfolio:snapshot` still all-MAJORS afterward.
3. `.env`: append `http://localhost:3002` to `PRAXIS_CORS_ORIGINS` (takes effect at the Wave-2 relaunch).
4. Verify-class quick items: **row 16** (`HGETALL pnl:daily:18b1a752-…` — confirm self-healed or absent → close); **row 27 follow-up** (orderbook staleness badge on /hot against the healthy stack for ~10 min — expected honest/quiet → close with evidence); telemetry mock guard (confirm `lib/mocks/telemetry-generator.ts` is gated behind `NEXT_PUBLIC_AGENT_VIEW_MOCK` and absent from the prod bundle — note result).
5. Then fan out Wave 1.

---

## 4 · WAVE 1 — parallel lanes (strict file ownership)

### Lane B1 — pnl service truth
**Owns:** `services/pnl/src/publisher.py`, `services/pnl/src/calculator.py` (if needed), `tests/unit/test_pnl.py`.
1. **cost_basis fabrication (registry 2026-06-12, MEDIUM)**: `publisher.py:67-69` writes `gross_pnl + net_pre_tax` (=2·gross−fees) as `cost_basis`. Fix: persist the real `entry_price × quantity` — the calculator/snapshot path has both (thread a field through `PnLSnapshot` if absent). Decimal end-to-end; test asserts cost_basis == entry value on a synthetic snapshot.
2. **Pydantic v1-isms (pnl half)**: `publisher.py:62` `ev.dict()` → `model_dump()`; kill the deprecation warning in the test run.

### Lane B2 — gateway hardening + symbol coherence
**Owns:** `services/api_gateway/src/routes/{orders,positions,commands,risk}.py`, `services/api_gateway/src/middleware/rate_limit.py`, `libs/config/settings.py`, `libs/core/schemas.py` (ONLY the RiskLimitsPayload/DEFAULT_RISK_LIMITS region), `services/hot_path/src/kill_switch.py` (reason truncation only), gateway tests.
1. **WS pnl per-user filter no-op (MEDIUM)**: `routes/ws.py`… — **correction**: ws.py belongs here too; add it to ownership. Fix server-side: at WS connect, load the user's profile_id set (profile repo), filter `pubsub:pnl_updates` messages by `profile_id ∈ set` (refresh the set lazily on a miss). Do NOT add user_id to the event (keeps producers clean). Test with two fake users' profiles.
2. **Read-side dash normalization (MEDIUM)**: `GET /orders?symbol=` + `GET /positions?symbol=` normalize via the `market_data.py:35` pattern before repo filter. Tests: dash filter returns slash rows.
3. **submit_order symbol-universe validation (LOW)**: reject symbols not in `settings.TRADING_SYMBOLS` (after normalization) with 422 — defense in depth on a financial route (§5A pass required).
4. **Row 64 trio (LOW)**: (a) `PRAXIS_KILL_SWITCH_OPERATORS` as a typed Setting consumed by `routes/commands.py` (drop raw `os.environ`); (b) `KillSwitch.set_level` truncates `reason` to 256 server-side; (c) post-auth per-user rate bucket for `POST /commands/kill-switch` (route-level dependency — middleware runs pre-auth, keep it).
5. **Rows 66+67 per D-D/D-E** (this lane owns the schemas region + settings + profile-write validation).
6. **D-F**: close the 501 intent-classification stub per ruling.
7. **Row 65 (its half)**: swap `routes/risk.py`'s duplicated `analyst:decay:snapshot` literal to the new shared constant — **contract**: `DECAY_SNAPSHOT_KEY` defined beside the existing portfolio snapshot key in libs (B4 creates it; grep for the portfolio key's home and import from there).

### Lane B3 — hot_path: HITL async + tripwire  ⚠ riskiest lane, §5A/§5B mandatory
**Owns:** `services/hot_path/src/{hitl_gate.py,processor.py,state.py}`, hot_path tests.
1. **Row 44 (HIGH)**: the blocking `blpop(timeout=60)` runs INSIDE the per-tick loop — one triggered signal stalls the engine (froze a soak for ~13h once). Rework to non-blocking: emit the approval request and park the signal as PENDING (in-memory + Redis with deadline); each loop iteration does a non-blocking `LPOP` sweep of pending response keys; APPROVE → resume the remaining gate sequence and publish; timeout/deny → fail-safe reject + audit log (preserve EXACT fail-safe semantics and the `PRAXIS_HITL_ENABLED=false` bypass). The tick loop must never await a human.
   **Verify:** unit tests (pending-park, approve-resume, timeout-reject, disabled-bypass); live: synthetic `pubsub:hitl_pending` injection (2026-05-11 precedent) while watching hot_path log cadence — tick processing must continue during a pending approval. Soak keeps `PRAXIS_HITL_ENABLED=false` afterward.
   **Escape hatch:** if mid-session this proves unsafe to land, ship the design + failing-edge tests + a precise registry update — the ONLY item allowed to exit unfixed, and say so loudly.
2. **D-K tripwire (row 41)**: burst detector at the order-publish site per ruling.

### Lane B4 — storage/backtesting precision + scoping
**Owns:** `libs/storage/repositories/{backtest_repo.py,closed_trade_repo.py}`, `services/analyst/src/decay_tracker.py`, `services/backtesting/src/job_runner.py`, the new shared-key constant in libs, their tests. Per **D-B** also: delete `services/backtesting/src/main.py`'s `/backtest/sweep` route + `SweepRequest` region of schemas.py (coordinate: B2 owns a different schemas region — re-Read on stale-block).
1. **Row 59 (MEDIUM)**: tenant-scope `latest_for_profile` (join `trading_profiles.user_id` / accept a `created_by` param threaded from decay_tracker) so a foreign row can never become a victim's baseline.
2. **Row 61 (MEDIUM)**: `net_of_cost_by_profile` returns Decimal (drop `float(v)`); audit/fix its callers.
3. **Row 68 (LOW)**: job_runner res_payload uses `str(Decimal)` before save into DECIMAL columns.
4. **Row 65 (its half)**: hoist `DECAY_SNAPSHOT_KEY` to libs beside the portfolio key; decay_tracker consumes it.
5. **D-B**: retire the sweep endpoint per ruling.

### Lane B5 — service reliability cluster
**Owns:** `services/validation/src/learning_loop.py`, `services/logger/src/event_subscriber.py`, `scripts/daily_report.py` + `libs/reports/daily.py`, `services/archiver/src/migrator.py`, `services/ingestion/src/main.py` (Coinbase line only), their tests.
1. **Row 57 (MEDIUM)**: learning_loop publishes the gateway `{"data": json}` shape with the full job payload incl. the profile's `risk_limits` (mirror `scripts/en_w2_edge_triage.py`'s payload; jobs MUST NOT carry `profile_id` unless they're meant to become the decay baseline — they are auto-runs, so per the latest-wins landmine: include `profile_id` ONLY if the architect's auto-baseline intent is documented; default **profile_id=""** + log). Contract test: enqueue → job_runner parses.
2. **Row 42 (MEDIUM)**: daily_report daemon — retry-with-backoff around initial backfill + survive-and-continue into the 00:05 loop.
3. **Row 47 (MEDIUM)**: archiver — first log `repr(e)`/type (the blank-error bug), then make hypertable archiving real: for TimescaleDB hypertables use chunk-aware retention (`drop_chunks` older than policy after a verified copy to the `_archive` table, or `move_chunks`) instead of `CREATE TABLE … (LIKE …)` + CTE-delete. **Verify against a throwaway copy of `audit_log` first**; prove old rows actually move/prune locally.
4. **Row 46 (LOW)**: `_on_alert` reads the real `AlertEvent` fields (`message`, `source_service`) — ~3 LOC.
5. **Row 12 / D-I**: Coinbase wiring per ruling.

### Lane B6 — libs: meta-learning + exchange contract
**Owns:** `libs/core/agent_registry.py`, `libs/exchange/{_base.py,_binance.py,_coinbase.py,_paper.py}`, their tests, the DECISIONS entry for D-A.
1. **Row 50 (MEDIUM)**: direction-aware scoring per **D-A** (incl. the operational EWMA state reset — coordinate the reset with the orchestrator at Wave-2 relaunch; document keys flushed).
2. **Row 51 (MEDIUM)**: add `symbol` to base `cancel_order`/`get_order_status` signatures + paper adapter, killing the LSP mismatch (mypy `[override]`); audit callers.

### Lane P — prompts/LLM surfaces
**Owns:** `prompts/**`, `scripts/` (new sync/check scripts), the 4 LLM services' prompt-loading sites (`services/{analyst,debate,sentiment,slm_inference}` prompt assets only), promptfoo configs.
1. **Row 37 (LOW/S)**: add the advisory-framing lines (emits signal only / does not decide trades / downstream gates own the decision) to each LLM-surface system prompt (~10 LOC total).
2. **Row 36 (LOW/M)**: skill-bundle pipeline — carve `prompts/skills/*.md` as canonical, `scripts/sync_agent_skills.py` copies into per-service assets, `scripts/ci/check_skill_drift.py` fails on divergence; wire the check into guards or ci.yml (coordinate ci.yml edit through the orchestrator).
3. **Row 38**: TRIAGED-CLOSED per **D-H**.

### Lane F1 — frontend: finish the React Query migration + WS/token hygiene
**Owns:** `frontend/lib/api/hooks.ts`, `frontend/lib/ws/client.ts`, `frontend/lib/types/index.ts`, `frontend/components/shell/EngineTotalsPill.tsx`, `frontend/components/agents/AgentStatusPanel.tsx`, `frontend/components/pnl/**` (deletion per D-C), `frontend/app/hot/**`, `frontend/app/risk/**`, `frontend/app/settings/{sessions,audit}/**`, `frontend/app/backtests/**`, `frontend/app/analysis/**`, `frontend/app/agents/**`, hooks/store tests. (NOT `app/performance/**` — that's F2's.)
1. **Migrate every remaining setInterval API poller** to React Query hooks (FE-W2 pattern; full verified inventory): `app/hot/profiles/page.tsx:~197`, `app/hot/profiles/[id]/page.tsx:~240`, the four tab components `_components/{DecisionsTab:~60,PositionsTab:~72,DailyPnlTab:~45,AttributionTab:~161}.tsx`, `EngineTotalsPill.tsx:~99`, `settings/sessions/page.tsx:~53`, `settings/audit/page.tsx:~91`, `AgentStatusPanel.tsx:~37`, `app/backtests/page.tsx:~300`, `app/analysis/page.tsx:~84`. New hooks get query keys registered in `queryKeys` + key-discipline tests (`["risk"]` umbrella stays invalidation-only). UI-tick timers (clocks/staleness) stay. `connectionStore`'s visibility-aware health poll stays.
2. **One-shot fetches onto shared hooks (registry row)**: /hot + /risk profiles → `useProfiles`; /hot candles → `useCandles`.
3. **D-C deletions** (dead pnl components + orphaned type).
4. **WS URL token refresh (row 31 remainder)**: `ws/client.ts:29` — refresh the token from the session on each (re)connect instead of reusing the construction-time token.
5. **Row 28**: `will-change-transform` on `animate-spin` spinners (PriceChart:~360 +the order-submitting Pill + project-wide grep).
6. **307 redirects (registry row)**: align api-client paths with route trailing-slash reality (verify per-route; kill the redirect on the polled endpoints at minimum) — confirm in the network tab afterward.
7. **chosen_risk_params rendering (registry row)**: backtest results panel shows per-window `chosen_risk_params` when present.

### Lane F2 — frontend: legacy token-contract rewrites
**Owns:** `frontend/app/performance/**`, `frontend/components/decisions/DecisionFeed.tsx`, `frontend/components/risk/RiskMonitorCard.tsx`, `frontend/components/trade/PositionsPanel.tsx`, `frontend/components/performance/DailyReportDetail.tsx`, `frontend/app/analytics/PerformanceContent*` (locate exactly), their tests.
1. **Rows 40 + 62 (MEDIUM)**: rewrite to the Praxis token surface (`bg-bg-canvas`, `text-fg`, `bg-bid-500`, `border-border-subtle`, …) — NO hex literals, NO shadcn tokens; `data-mode` on surface roots; zero functional change (snapshot the rendered data before/after). Also migrate `/performance`'s own 60s setInterval poller (`page.tsx:~71`) while in the file (F1 stays out).

### Lane D — docs truth
**Owns:** `docs/**` (except TECH-DEBT-REGISTRY.md and DECISIONS.md — orchestrator owns those at Wave 2), the WS benchmark script under `scripts/`.
1. **A-2** (WALKTHROUGH.md `/auth/login` → real OAuth `/auth/callback` flow), **A-3** (35ms → 50ms fast-gate), **A-4** (SHUTDOWN.md: all 19 services with per-service shutdown notes — derive from run_all.sh + service mains), **A-6** (migrate.py applies 001–024+ — state the real current range).
2. **Row 35**: resilience playbook S2/S3 corrected (WS endpoint IS the gateway; Redis death hangs the subscription, doesn't drop the socket).
3. **G-rows v1 (per D-L)**: `docs/ops/` — `SLA-TARGETS.md` (G-1, PROPOSED), `CAPACITY.md` (G-2, method + dev-box numbers), `DR-PLAYBOOK.md` (G-3 — fold the S1–S3 resilience evidence), `DATA-RETENTION.md` (G-4 — from `HOT_DATA_RETENTION_DAYS`, archiver policies, audit needs), `ALERTING.md` (G-5, PROPOSED thresholds incl. the new B3 tripwire), `ROLLBACK.md` (G-6 — git revert + migration-rollback reality + run_all relaunch), `KEY-ROTATION.md` (G-7 — manual steps today, automation TBD), `WS-LIMITS.md` (G-11 — run the N-connection benchmark, publish numbers as dev-box). Update DOCUMENTATION-GAPS.md statuses (PROPOSED-doc = gap closed at v1).
4. **D-F/D-G/D-H** status updates in DOCUMENTATION-GAPS.md per rulings.

---

## 5 · WAVE 2 — barriers (sequential after Wave 1 lands + per-lane tests green)

1. **W2-1 ESLint baseline (row 53, MEDIUM)**: `npx eslint . --fix`, then triage the ~62 errors per-rule (fix, or rule-level justify in config with a comment); remove the stale disable at `KillSwitchModal.tsx:159`; flip `frontend-lint` to blocking in ci.yml. MUST run after F1/F2 (they churn the files).
2. **W2-2 mypy cleanup (row 49 remainder, the big one)**: fan out per-module agents over the ~99 errors (None-indexing of DB rows, strategy-DSL Literal mismatches, the row-51 override errors B6 already killed); NO behavior changes — typing only, `# type: ignore[code]` with justification where a fix would change runtime behavior; flip mypy to blocking in ci.yml + re-enable in `.pre-commit-config.yaml`. Orchestrator owns the ci.yml/pre-commit edits.
3. **W2-3 integration tests (row 52, MEDIUM)**: populate `tests/integration/` against the REAL local Redis+Timescale (CI job already has service containers): (a) `stream:orders` → validation → execution contract (port from `scripts/verify_*`), (b) KillSwitch level round-trip incl. operator gating, (c) repository CRUD (positions/closed_trades/backtest_results) incl. the new tenant-scoped baseline query, (d) the learning_loop→job_runner enqueue contract (B5's fix). Remove the exit-5 tolerance + `::warning` from ci.yml once tests exist.
4. **W2-4 relaunch + live verification**: `bash run_all.sh --local-frontend` (picks up every backend change + CORS); EWMA reset per D-A; `loop crashed` grep; soak 4 OPEN; kill-switch round-trip; `/hot` total-PnL still live in prod build (:3000 or now-allowed :3002); HITL synthetic-injection check (B3); archiver one-shot run evidence (B5); burst-tripwire smoke (publish N synthetic orders to a test profile? — only if safely below real execution, else unit-level only).
5. **W2-5 paper trail (orchestrator)**: TECH-DEBT-REGISTRY — every touched row → RESOLVED/TRIAGED with evidence; DOCUMENTATION-GAPS summary table refreshed; DECISIONS.md entries (D-A, D-B, D-D at minimum); per-lane commits (same discipline as 06-12: lane commits + one docs commit); push; CI green; rewrite `NEXT-SESSION-PLAN-2026-06-14.md` pointing back to the EN-W3 handoff (`NEXT-SESSION-PLAN-2026-06-13.md` content carries forward); update memory `project_next_session_plan` + `project_ci_lint_red_on_main` (mypy/ESLint now blocking = that memory closes).

**Priority ladder if time pressure hits** (land in this order, cut from the bottom): B3 → B2 → B4 → B5 → B1/B6 → F1 → W2-2/W2-1 flips → F2 → W2-3 → Lane D G-rows → Lane P row 36. Anything cut gets an honest registry note, not silence.

---

## 6 · Explicitly OUT of scope (do not touch)

- **Partner-input items**: EN-W3/EN-W4 re-prioritization; EN-W2 verdicts sign-off; kill-switch operator model sign-off; `@praxis-architect` CODEOWNERS handle; $10k VIP0 capital/fees confirmation. (Courtesy flag for the architect: whether to close/delete the 2 synthetic High-Volume-Breakout positions.)
- **Decision-gated by existing DECISIONS**: tick-level sim (gated on decay divergence); durable per-window WF storage (migration 026+ — sequenced AFTER EN-W3's reserved 025); soak exit bands (stay as-is per 2026-06-12).
- **Master-plan deferrals**: federation, capital allocator, sub-accounts beyond ISOLATED perp legs, signal families E/F/H/I/J.
- **Phase-2 readiness P-1…P-6** (K8s/Terraform/HPA/secrets-rotation/blue-green): deployment-phase work, meaningless before a cloud target exists.
- **Migration 025**: RESERVED for EN-W3 netting/margin — no migrations this session at all.

---

*Written 2026-06-12 on user direction: clear the whole deferred list next session. The lanes/rulings above are the alignment artifact — if reality contradicts a file:line pointer, trust reality, fix the doc in the same commit, and keep going.*
