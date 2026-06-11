# Phase 2 Handoff — Next Claude Session

### Risk-Truth UI Surfacing (FE-W1) + Backtest Truth-Pass (EN-W1)

**Date:** 2026-06-11  ·  **Author:** Claude Code (handler)  ·  **Supersedes:** `NEXT-SESSION-PLAN-2026-06-10.md` §3–§5 sequencing (Phase 1 rows are DONE; that doc remains the master plan for Phases 3–5)
**Status:** ready to execute — no new decisions needed; the 7 locked decisions of the master plan stand.

---

## 1 · Where we are (git truth, verified 2026-06-11)

**Phase 1 (FE-W0 + EN-W0) is COMPLETE and the Risk-Truth Hardening slice is MERGED TO MAIN.**

- `main` = `ddf9db1` — merge of `feat/risk-truth-hardening` (PR0–PR7 + EN-W0), via gated **PR #2** with the **full CI pipeline green**. This formally satisfies Viability Plan Phase 3 and the DECISIONS.md branch-model exit bar (CI green + soak-verified).
- **Active integration branch: `feat/snappy-honest-edge`** (pushed, contains post-merge main at `3026c33`). ALL new work this session goes here; small PRs squash into it; it merges to main at slice end via a gated PR.
- `feat/risk-truth-hardening` still exists on origin (merged; safe to delete whenever).
- Local leftover for the user, not the agent: `git worktree remove --force ..\aion-trading-redesign; git branch -D redesign/frontend-v2` (remote already deleted; unique handoff file preserved in `docs/design/`).

### What FE-W0 delivered (commits `d1cfa41` + review fixes `cede61a`)

- **Token cache**: `apiRequest` reads the JWT synchronously from `authStore`; `/api/auth/session` survives only as a 30s-memoized cold-start fallback **and a 401-recovery path** (NextAuth re-mints the 1h backend token server-side inside the session endpoint — the old per-request fetch was doing rotation implicitly; the recovery blacklists the stale store JWT and retries exactly once).
- **React Query**: `QueryProvider` wraps `AppShell` in `app/layout.tsx`; **`frontend/lib/api/hooks.ts`** has `useProfiles / usePositions / useKillSwitch / useCandles / useRisk / useAllRisk / useClosedTrades` + `queryKeys`. Defaults: staleTime 5s, gcTime 5m, no focus refetch, retry 1.
- **WS warm-start**: lifecycle lives in `AuthProvider`'s `SessionSync` (same effect that writes the JWT); `ws/client.ts` `connect()` guards `CONNECTING` and clears pending backoff reconnects.
- **Streaming shell**: `ShellSkeleton` (inert, React 19 `inert` prop) replaces the bare auth spinner; root `<Suspense>` in `RedesignShell` (forward-scaffolding — see §4 landmines).
- **Verified live**: 19 API calls share 2 session fetches cold (dev StrictMode doubles; 1 in prod), **0 on warm nav**; `next build` green; 639 unit tests green.

### What EN-W0 delivered

- `docs/DECISIONS.md` 2026-06-11 entries: **cloud region AWS Tokyo `ap-northeast-1`** (#1) and the **netting/margin policy** (#5 — horizon partitioning, never hard-veto, no cross-horizon netting, perp legs ISOLATED; schema implications binding for migration 025).
- Viability plan reconciled (Phase 3 SATISFIED; scheduler item moved to EN-W3).
- **Blocking CI `guards` job** — `scripts/ci/guards.py` (AST-based): float-gate over `services/{execution,pnl,risk,strategy}` honoring span-aware `# float-ok: <reason>` markers, + Redis-channel contract gate (every `stream:`/`pubsub:` literal must exactly match a constant in `libs/messaging/channels.py`; docstrings skipped). Pre-commit mirrors it (`praxis-guards`). Acceptance-tested both ways.

---

## 2 · This session's two lanes (Phase 2 of the master plan)

### Lane A — FE-W1 · Risk-Truth UI surfacing *(LOCKED decision #6 — highest-priority FE feature work)*

Make the engine's safety surface operable from the UI (today: CLI/Redis only). Build on the FE-W0 hooks; work on `feat/snappy-honest-edge`.

1. **Tiered halt control.** `killSwitchStore.ts` is binary (`'off'|'soft'|'hard'`) — extend to the four backend verbs (`HaltLevel` in `libs/core/enums.py`: `STOP_OPENING / DE_RISK / NEUTRALIZE / FLATTEN`). Extend `api.commands.killSwitchToggle` to send `{level, reason}` (backend `services/api_gateway/src/routes/commands.py` already accepts `level`, validates ~line 75). Rebuild `KillSwitchModal.tsx` into a graduated control: first three verbs single-click; **FLATTEN behind an explicit confirm gate that states the locked policy** (auto-FLATTEN only on ≥2 concurrent severe triggers held ≥30s, else human auth — decision #2 / DECISIONS.md 2026-06-10). Optimistic toggle with reconcile-on-poll — **test the rollback path; a mis-reconcile on a safety control is worse than a spinner.**
2. **Portfolio-risk + correlation panel on `/risk`** — surface PR4 (portfolio snapshot is written by `services/risk/src/portfolio.py` to its `SNAPSHOT_KEY`; stress-correlation concentration shipped in PR4). Concentration grid + correlation heatmap; `RiskPageSkeleton` instead of empty-state pop.
3. **Net-of-cost dashboard** — PR5 per-strategy gross→net waterfall (fees / funding / slippage attribution) on `/performance` or a `/risk` sub-tab.
4. **Decay dashboard** — PR7 live-vs-backtest decay. `services/analyst/src/decay_tracker.py` writes a snapshot to Redis; add a thin api_gateway read endpoint if none exists. Render per-profile decay status, AMBER + `reasons[]`.
5. **Polling discipline**: build all new reads on the FE-W0 hooks. Note `useKillSwitch` already polls @10s and React Query pauses intervals while the tab is hidden (`refetchIntervalInBackground` defaults false) — the plan's page-visibility guard is largely free.

**Verify:** trigger each tier from the UI → `redis-cli` confirms the level and entries are blocked at the right tiers; FLATTEN cannot fire without the gate; synthetic `decayed=true` renders AMBER + reasons; React Profiler shows <5 component updates per `/risk` poll.

**Security:** this touches `api_gateway` commands + financial display — run the CLAUDE.md §5A/§5B checklist (rate-limited command endpoints, Decimal end-to-end, kill-switch integration).

### Lane B — EN-W1 · Backtest truth-pass *(LOCKED decision #4 — mandatory BLOCKER for the Phase-6 live gate)*

Registry rows 43 + 52 are the spec. The backtester closes only on opposing-signal; live `ExitMonitor` closes only on SL/TP/time. Make the sim honest:

1. **Exit fidelity via a shared lib.** Extract the exit-decision logic (`stop_loss_pct` / `take_profit_pct` / `max_holding_hours`, same precedence and price basis) from `services/pnl/src/exit_monitor.py` into a shared lib (suggest `libs/core/exit_policy.py`) consumed by BOTH `exit_monitor.py` and `services/backtesting/src/simulator.py` + `vectorbt_runner.py` — **do not copy-paste; drift is the failure mode.** Drop the opposing-signal close. Unit test: a position that hits SL live hits SL (not opposing-signal) in the sim on identical bars.
2. **Look-ahead guard** — audit for bar-close/future data in intrabar decisions; decision-time-only information.
3. **Walk-forward** — rolling train/test windows; out-of-sample metrics reported separately.
4. **Survivorship guard** — symbol universe as-of-date.
5. **All-Decimal** — every new calc in `Decimal`. Note: `services/backtesting/` and `libs/` are NOT in the CI float-guard's scope dirs (it covers execution/pnl/risk/strategy) — **consider extending `FLOAT_GUARD_DIRS` in `scripts/ci/guards.py` to the new shared exit lib** so sim/live parity is gate-protected; regardless, CLAUDE.md §2A applies.

**Verify:** close-reason distributions converge between backtest and paper-soak on the same profile (PR7 decay tracker is the cross-check). **No Phase-6 live gate until exit-fidelity tests are green.**

**Cross-lane:** EN-W2 (edge triage) wants FE-W1's dashboards; otherwise the lanes are independent — fan out in parallel.

---

## 3 · Session-start checklist

1. `git fetch --all --prune` → confirm on `feat/snappy-honest-edge`, in sync with origin; `main` should be `ddf9db1`.
2. Boot: `bash run_all.sh --local-frontend` (never start services individually). Post-boot: grep `.praxis_logs/*.log` for `loop crashed`.
3. Frontend dev at `localhost:3001`; login is OAuth-only — the user's existing Chrome session authenticates; chrome-devtools MCP rides it.
4. GitHub ops: `gh` is at `C:\Program Files\GitHub CLI\gh.exe` (not on PATH); auth per call via the `git credential fill` cmd-redirect pattern (see memory `reference_gh_cli_auth`); multiline commit messages via `git commit -F <file>` (PS5.1 quoting).
5. Tests: `poetry run pytest tests/unit -q` (639 green baseline). Guards: `python scripts/ci/guards.py` (green baseline).

---

## 4 · Landmines & nuances discovered 2026-06-11 (read before touching)

- **CI is green but opinionated**: lint tools are version-pinned in ci.yml (black 24.2.0 / isort 5.13.2 / ruff 0.2.2 / mypy 1.8.0) — never unpin. ESLint is ADVISORY (298-problem pre-existing baseline, registry row; `tsc --noEmit` is the blocking FE gate). mypy advisory. `tests/integration/` is EMPTY — pytest exit 5 tolerated with a warning (registry row; first real integration tests are a welcome side-quest, candidates listed in the registry).
- **hooks.ts key discipline** (review-confirmed bug class): never alias an umbrella invalidation key (`["risk"]`) as a live data key — per-profile queries use `queryKeys.riskFor(id)` with a `"__pending__"` sentinel when undefined; `enabled` guards merge with `opts.enabled`, never overridable. Follow this pattern for every new hook.
- **Manual position close may still be phantom**: `frontend/lib/api/client.ts` `api.positions.close` comment claims the manual `POST /positions/{id}/close` is DB-only. Verify whether that route was rewired through the PR1 reduce-only close path **before** surfacing any close button in FE-W1; fix route or comment accordingly.
- **`pubsub:pnl_updates` carries floats** (`services/pnl/src/publisher.py` `_DecimalEncoder`) — display-only today, registry row exists. If FE-W1/FE-W2 touches that consumer (`ws/client.ts` pnl handler), consider doing the str-encoding fix in the same change.
- **Interval leak evidence for FE-W2**: `/hot`'s positions/orders/kill-switch `setInterval` pollers keep firing after navigating away (observed live). Don't patch ad hoc — the FE-W2 React Query migration kills the class. Likely related to the long-open `/hot` slowness memory.
- **Root Suspense in `RedesignShell` is scaffolding**: nothing suspends into it yet, and future `loading.tsx` files create segment boundaries below it. Don't claim streaming behavior from it; FE-W3 makes it real.
- **Auth rotation contract**: `authStore.jwt` is single-writer (`SessionSync`). The 401-recovery in `client.ts` blacklists a stale store JWT locally (`staleStoreJwt`) — if you touch auth, preserve single-writer and the logout `clearSessionTokenCache()` call.
- **Dev-mode measurement**: StrictMode double-fires mount effects and `next dev` disables prefetch — perf numbers only count from a prod build (`next build && next start`).

---

## 5 · Open partner inputs (unchanged, do not block Phase 2)

1. **GitHub handle** for the `@praxis-architect` CODEOWNERS placeholder + enabling branch protection (require Code Owners review + status checks) on `main` and integration branches — now timely since main has its first gated merge.
2. **Capital/fees confirmation** — $10k @ Binance VIP0 is a FLAGGED working assumption (decision #7); needed before EN-W4 capital/EV math. Surface it in any EV calculations; never hardcode as confirmed.

## 6 · After this session (master plan Phases 3–5)

FE-W2 snappy-fetch + render-jank kill (the polling inventory is in the 2026-06-11 recon, preserved in the FE-W0 review workflow transcripts) → FE-W3 polish · EN-W2 edge triage (MACD kill/rebuild, A/B exit bands) → EN-W3 Tokyo substrate + migration 025 (schema FIRST; the netting/margin DECISIONS entry is binding) → EN-W4 Yield Harvester + auto-deprecation (`decay_tracker.py` → `KillSwitch.set_level(NEUTRALIZE)`, never FLATTEN) + 60-day soak. **DEFER:** federation, capital allocator, sub-accounts beyond ISOLATED perp legs, signal families E/F/H/I/J.

---

*Handoff written at the close of the 2026-06-11 ultracode session (Phase 1 execution). Memory files updated in parallel: `project_next_session_plan`, `project_phantom_close_finding` (RESOLVED), `project_hot_browser_slowness` (new leak evidence), `reference_gh_cli_auth` (new).*
