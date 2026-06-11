# Phase 3 Handoff — Next Claude Session

### Snappy-Fetch + Render-Jank Kill (FE-W2) + Per-Profile Edge Triage (EN-W2)

**Date:** 2026-06-12  ·  **Author:** Claude Code (handler)  ·  **Supersedes:** `NEXT-SESSION-PLAN-2026-06-11.md` (EXECUTED — both lanes shipped, live-verified, CI green). `NEXT-SESSION-PLAN-2026-06-10.md` remains the master plan for Phases 4–5.
**Status:** ready to execute. The 7 locked decisions stand; 2 new DECISIONS entries (2026-06-11) await architect sign-off but do not block this phase.

---

## 1 · Where we are (git truth, verified 2026-06-12)

**Phase 2 (FE-W1 + EN-W1) is COMPLETE. The Phase-6 live-gate backtest blocker is CLEARED.**

- `main` = `ddf9db1` (risk-truth slice + EN-W0, gated PR #2, CI green).
- **Active integration branch: `feat/snappy-honest-edge` = `9965dd1`** (pushed, **CI green** at `d39f810`; `9965dd1` adds the architect brief). ALL new work goes here; gated PR to main at slice end.
- Baselines: **709 backend tests · 79 frontend tests · black/isort/ruff/guards/tsc/build all green and blocking** (mypy + ESLint advisory).
- Architect brief covering both 2026-06-11 sessions: `docs/EXECUTION-BRIEF-2026-06-11-PHASES-1-2.md` (+ PDF, untracked).

### What EN-W1 delivered (commit `d25a449`)

- **`libs/core/exit_policy.py`** — single source of truth for exit decisions (SL → TP → time, exact live comparisons), consumed by the live `ExitMonitor` (refactor behavior-identical) AND both backtest engines. Opposing-signal closes removed; entries only open when flat; per-trade `close_reason` + `slippage_cost` persisted in the trades JSONB.
- **Walk-forward** (`services/backtesting/src/walk_forward.py`): rolling train/test windows; optional per-window `param_grid` fit on train via `run_sweep` (best in-sample sharpe) evaluated out-of-sample; **OOS aggregate persisted as the parent `backtest_results` row** (honest decay baseline); per-window report only on the Redis `backtest:status:{job_id}` payload (1h TTL). Budget caps: 500k bars / 100 combos / 200 windows / 1,000 runs / 600s per job (`asyncio.wait_for` + engines in `to_thread`).
- **Coverage guard**: `data_start` / `data_end` / `coverage_pct` / `coverage_warning` (<0.95) on the status payload.
- `risk_limits` threaded API → queue → `BacktestJob`; profile ownership validated whenever `profile_id` is present (closed a cross-user decay-baseline poisoning hole); `BacktestRequest` gained `profile_id` / `risk_limits` / `walk_forward`.
- `FLOAT_GUARD_DIRS` now covers `libs/core/exit_policy.py` + `services/backtesting/`.
- **Live evidence** (real BTC/USDT 1h, Apr–Jun): plain run closes `time_exit:50 / take_profit:8 / stop_loss:3 / end_of_data:1`; WF window-0 IS sharpe 5.79 → OOS −0.60.

### What FE-W1 delivered (commit `30da70e`)

- **Tiered halt control**: `killSwitchStore` holds the five `HaltLevel` verbs + `severity()` (NEUTRALIZE+ = danger, matching the backend CRITICAL-log threshold); graduated `KillSwitchModal` with DECISIONS-verbatim verb descriptions; **FLATTEN behind a two-stage gate** (policy text verbatim + typed `FLATTEN`); optimistic mutation with tested cache+store rollback; canonical 10s `useKillSwitch` poll mounted in `RedesignShell`.
- **Truth panels on `/risk`** — one click-to-reveal card, tabs Portfolio / Costs / Decay (`frontend/components/risk/RiskTruthPanel.tsx`), `RiskPageSkeleton`, memoized ActiveLimits rows.
- **New gateway endpoints**: `GET /risk/portfolio`, `GET /risk/decay`, `GET /pnl/net-of-cost` (Decimal-string serialization; logged failure paths; stale-honest empty states). `KillSwitchStatusResponse` now actually exposes `level` + typed `recent_log` (response_model was stripping them).
- **Operator authorization** on the kill switch: `PRAXIS_KILL_SWITCH_OPERATORS` allowlist — NEUTRALIZE/FLATTEN and halt-clearing (incl. legacy `active=false`) are operator-gated; STOP_OPENING/DE_RISK open to all authenticated users; **unconfigured = single-operator mode**. Activity log + portfolio breakdown operator-only when configured.
- **Live-verified**: STOP_OPENING + DE_RISK round-trip UI → Redis → audit log; FLATTEN gate impassable without typed confirm; synthetic decay rendered AMBER + reasons. NEUTRALIZE/FLATTEN deliberately not live-fired (open paper-soak positions).

---

## 2 · This session's two lanes (Phase 3 of the master plan)

### Lane A — FE-W2 · Snappy fetch + render-jank kill

The class-level fix for the long-standing /hot slowness (memory: 25–35s page fetches vs 220ms curl) and the leaked-poller bug observed live 2026-06-11. Build on the FE-W0 hooks; the FE-W1 hooks (`useRiskPortfolio`/`useDecay`/`useNetOfCost`) are the pattern.

1. **React Query migration of the page-local pollers** (registry row). Known inventory:
   - `app/hot/[symbol]/page.tsx`: kill-switch `setInterval` @10s (now redundant — RedesignShell owns the canonical poll), positions @~5s, orders-list reconcile polling, plus the leaked-after-nav-away intervals.
   - `app/risk/page.tsx`: metrics @10s + kill-switch @10s `setInterval`s.
   - `components/risk/ProfilesRiskMatrix.tsx`: @30s making 1+2N requests per cycle — collapse onto `useProfiles`/`useAllRisk`/`usePositions`.
   - Retire the page-local kill-switch pollers entirely; everything reads the store (synced by RedesignShell) or `useKillSwitch`.
2. **WS pnl pipeline fix** (HIGH registry row + row 54, coordinated change): `PnlUpdateEvent` lacks `position_id`/`net_post_tax`/`roi_pct` that `ws/client.ts` reads — `/hot` total-PnL sums zeros today. Extend the publisher event (str-encoded Decimals per row 54), rewrite the handler, fix the `/hot` total memo. Touching `services/pnl/` → §5A/§5B checklist + Decimal contract; the float-gate covers it.
3. **Render-jank**: portfolio-store update throttling (row 54 notes pairing); `/hot` chrome to tiered severity (`HotChrome` label + `OrderEntryPanel` still binary — registry row); verify <5 component updates per poll on /risk **in a prod build** (`next build && next start` — dev StrictMode doubles effects; the FE-W1 memoization was never profiled in prod).
4. **Re-measure /hot end-to-end after migration** (prod build) and update the `project_hot_browser_slowness` memory with numbers.

**Verify:** navigate away from /hot → network tab shows zero residual polling; /hot total-PnL renders non-zero against live ticks; prod-build profiler numbers recorded.

### Lane B — EN-W2 · Per-profile edge triage *(locked decision #3, first half)*

EN-W1 made close reasons honest — now use them. Goal: kill or rebuild what has no edge, fix the exit-band pathology, and seed honest decay baselines.

1. **Seed decay baselines**: run walk-forward backtests for each ACTIVE profile with its real `risk_limits` (the soak profile is `status: no_baseline` today — its decay tracking is blind). Enqueue via `POST /backtest` with `profile_id` (ownership-checked, limits auto-loaded). The OOS parent row becomes the baseline automatically.
2. **A/B exit bands**: the 12h-max-hold plain run closed 50/62 trades on time_exit — sweep `stop_loss_pct` / `take_profit_pct` / `max_holding_hours` bands per profile and compare OOS metrics + close-reason mix. NOTE: `run_sweep`'s `param_grid` currently sweeps strategy-rule condition values (`"0.value"` keys), NOT risk_limits — extending the sweep dimension to exit bands is the first engineering task of this lane (small: thread a `risk_limits_grid` through `run_sweep`/`walk_forward` respecting the existing combo budget).
3. **MACD kill/rebuild**: backtest the MACD-based signals/profiles honestly (walk-forward, real exit bands); kill what shows no OOS edge, rebuild or re-band what does. Decisions logged to DECISIONS.md.
4. **Close-reason convergence check** (PR7 cross-check): compare backtest vs paper-soak close-reason distributions for the soak profile — **filter `close_reason="end_of_data"`** (DECISIONS 2026-06-11; each WF window contributes one synthetic boundary close).
5. **Candidate quick win (small, separate commit, needs no new decision):** the HIGH `cluster_for()` dash-symbol bug — `BTC-USDT` is counted in the ALT cluster TODAY, so the live correlation cap enforces the wrong budget on BTC. Fix = separator-agnostic matching + audit how dash symbols enter `positions.symbol`. Touches `libs/core/correlation.py` (risk path → §5A/§5B).

**Cross-lane:** independent; fan out in parallel. Lane A owns `frontend/**` + `services/pnl/src/publisher.py` + `libs/core/schemas.py` (PnlUpdateEvent region); Lane B owns `services/backtesting/**` + `libs/core/correlation.py` + analysis scripts. Disjoint except schemas.py (different regions — same drill as last session).

---

## 3 · Session-start checklist

1. `git fetch --all --prune` → on `feat/snappy-honest-edge`, in sync with origin (`9965dd1`); `main` = `ddf9db1`.
2. Boot: `bash run_all.sh --local-frontend` (never individually). Post-boot: grep `.praxis_logs/*.log` for `loop crashed`. The api_gateway health check in the boot script may print a false WARNING (it probes before uvicorn finishes) — curl `:8000/health` to confirm.
3. Frontend dev at `localhost:3001`; OAuth-only login — chrome-devtools MCP rides the user's Chrome session.
4. **Redis is DB 1**: `redis-cli -a <pw from .env> --no-auth-warning -n 1 ...` — db0 is a near-empty decoy that mimics a broken system (memory `reference_redis_db1`). TimescaleDB: `psql -U postgres -d praxis_trading`.
5. Baselines: `poetry run pytest tests/unit -q` (709 green) · `python scripts/ci/guards.py` · `poetry run black --check . && poetry run isort --check-only . && poetry run ruff check .` (all green — these are BLOCKING in CI now; run them before every push) · frontend: `npx tsc --noEmit`, `npm run test` (79), `npm run build`.
6. GitHub ops: `gh` at `C:\Program Files\GitHub CLI\gh.exe`; auth via the `git credential fill` cmd-redirect pattern (memory `reference_gh_cli_auth`); multiline commit messages via `git commit -F` — write the file with `[System.IO.File]::WriteAllText` (PS5.1 `Out-File -Encoding utf8` writes a BOM that lands in the commit subject).

---

## 4 · Landmines & nuances discovered 2026-06-11 (read before touching)

- **black vs `# float-ok` markers**: black's line rewrapping can move a marker off the float-call's line span, flipping guards red AFTER a clean run — keep markers on the call's own line (extract a temp var if needed) and run black BEFORE guards locally. This bit us once (commit `d39f810` fixed two sites).
- **guards.py scans `git ls-files` only** — brand-new untracked files are invisible to it until `git add`. Don't trust a green guards run on uncommitted new files.
- **Direct queue enqueues need the COMPILED rules shape**: `{"conditions": [{indicator, operator, value}], "logic", "direction", "base_confidence"}` — the gateway compiles `StrategyRulesInput` before enqueueing; `job_runner` does not. Also `user_id` must be a real UUID (DB `created_by`). Two harmless verification rows exist in `backtest_results` (`en-w1-verify-plain3` / `en-w1-verify-wf3`, `profile_id=""`).
- **Operator allowlist semantics**: `PRAXIS_KILL_SWITCH_OPERATORS` unset = everyone is an operator (single-user deployment unchanged). If the architect signs off, consider setting it; until then don't be surprised that NEUTRALIZE/FLATTEN/NONE work for any token locally. Read via raw `os.environ` in `routes/commands.py` (registry row: promote to a typed Setting).
- **Page-local kill-switch pollers still run** on /hot + /risk alongside RedesignShell's canonical `useKillSwitch` — duplicated on purpose (FE-W2 retires them); don't "fix" one without doing the migration.
- **`/risk` truth-panel hooks**: `useRiskPortfolio` (10s), `useDecay` (60s), `useNetOfCost` (60s) — keys `["risk","portfolio"]` / `["risk","decay"]` / `["netOfCost", h]`; the umbrella `["risk"]` is invalidation-only, never a data key. Portfolio money values are STRING Decimals end-to-end — keep them strings.
- **Walk-forward window detail is Redis-only** (1h TTL on `backtest:status:{job_id}`); the DB row carries only the OOS aggregate + OOS trades. If EN-W2 wants durable per-window reports, that's a conscious schema addition (migration 025 is RESERVED for netting/margin — use 026+).
- **`run_sweep` param_grid ≠ exit bands** (see Lane B item 2) — budget caps (`WALK_FORWARD_MAX_*` in `libs/core/schemas.py`) apply to whatever new dimension is added.
- **Dev-mode measurement**: StrictMode double-fires effects; perf numbers only count from `next build && next start`.
- **Paper soak continuity**: 4 OPEN positions (1 profile) — avoid firing NEUTRALIZE/FLATTEN live and avoid anything that mass-closes positions; the soak PnL distribution is a Phase-0 exit criterion.

---

## 5 · Open partner inputs (surface, do not block)

1. **Sign-off pending (new, 2026-06-11)**: kill-switch operator-authorization model + EN-W1 exit-semantics judgment calls — both in DECISIONS.md and the architect brief (`docs/EXECUTION-BRIEF-2026-06-11-PHASES-1-2.md`).
2. **GitHub handle** for `@praxis-architect` CODEOWNERS + branch protection on `main`/integration branches.
3. **Capital/fees confirmation** — $10k @ Binance VIP0 stays a FLAGGED assumption (decision #7); blocks EN-W4 EV math only.

## 6 · After this session (master plan Phases 4–5)

FE-W3 perceived-perf polish → EN-W3 Tokyo substrate + Phase-A primitives + migration 025 (netting/margin DECISIONS entry is binding; schema FIRST) → EN-W4 Yield Harvester + auto-deprecation (`decay_tracker` → `KillSwitch.set_level(NEUTRALIZE)`, never FLATTEN — now both the engine verbs AND the FE decay surface exist) + 60-day soak. **DEFER:** federation, capital allocator, sub-accounts beyond ISOLATED perp legs, signal families E/F/H/I/J.

---

*Handoff written 2026-06-12 at the close of the Phase-2 ultracode session. Memory updated in parallel: `project_next_session_plan` (Phase 2 DONE), `project_phantom_close_finding` (nuance closed), `reference_redis_db1` (new). Registry: rows 43/55 resolved, 13 new rows — the two HIGH ones (`cluster_for` dash symbols, WS pnl field mismatch) are both scheduled into this phase's lanes.*
