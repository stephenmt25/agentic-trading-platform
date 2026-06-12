# Phase 4 Handoff — Next Claude Session

### EN-W3 Tokyo Substrate + Phase-A Primitives (priority raised) · FE-W3 Perceived-Perf Polish (demoted to cleanup)

**Date:** 2026-06-13  ·  **Author:** Claude Code (handler)  ·  **Supersedes:** `NEXT-SESSION-PLAN-2026-06-12.md` (EXECUTED — both lanes shipped, live-verified in a prod build, baselines seeded, MACD killed). `NEXT-SESSION-PLAN-2026-06-10.md` remains the master plan for Phase 5.

---

## 1 · Where we are (verified 2026-06-12)

**Phase 3 (FE-W2 + EN-W2) is COMPLETE.**

- Branch `feat/snappy-honest-edge`, commits `067b9ac` (cluster_for), `c1c7aae` (risk_limits_grid), `01447e3` (FE-W2), + docs commit. Baselines: **770 backend · 91 frontend · tsc/build/guards/black/isort/ruff green**.
- **FE-W2 live-verified (prod build, :3000)**: /hot total-PnL non-zero from the new WS pipeline (+0.32 observed live); zero residual polling after nav-away (25s observation); zero DOM mutations across 2 /risk poll cycles; **/hot LCP 675ms, CLS 0.00**. The 25–35s slowness memory is closed.
- **cluster_for live-verified**: `risk:portfolio:snapshot` shows BTC-USDT in MAJORS (was ALT); gateway `submit_order` now normalizes dash symbols (entry vector stopped).
- **EN-W2 verdicts (DECISIONS 2026-06-12, numbers in `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md`)**:
  - **MACD ×3 KILLED** — every run negative OOS sharpe (−2.7..−8.2); 21/24 windows negative even in-sample. No rebuild.
  - **Exit re-banding rejected** — 18-combo sweep OOS (−5.41) WORSE than current bands (−4.00); unstable per-window winners.
  - **Convergence PASSES** — live 93/7 time/SL vs sim-OOS 90/5/5: the EN-W1 exit unification is validated on real soak data.
  - **Soak decay baseline seeded** (`en-w2-soak-baseline`, honest OOS) — `no_baseline` resolved.

### ⚠ THE HEADLINE (read first, tell the architect)

**Every current signal family has negative out-of-sample edge.** The
instrument is honest now; what it measures is not profitable. EN-W3/EN-W4 is
not polish — it is the path to the first defensible edge. This session's
brief asks the architect to confirm the re-prioritization below.

---

## 2 · This session's lanes

### Lane A (PRIORITY) — EN-W3 · Tokyo substrate + Phase-A primitives + migration 025

Per master plan Phase 4, now carrying the urgency of the headline:
1. **Migration 025 (RESERVED — netting/margin DECISIONS entry is BINDING, schema FIRST)**: `accounts` + `position_groups`, `market_type` + `margin_mode` on accounts/positions, horizon partition key, all money columns NUMERIC. No dependent code before the schema is verified.
2. Phase-A primitives per the master plan / Strategy Gap Analysis (funding-rate ingestion, perp-leg plumbing on ISOLATED margin — the Yield Harvester's substrate).
3. Carry-over quick wins if blocked: registry rows for `learning_loop` payload mismatch (row 57) and repo tenant-scoping (row 59).

### Lane B (small) — FE-W3 · perceived-perf polish + UI catch-ups

The perf class problems are gone (675ms LCP); what remains is polish:
1. Render `chosen_risk_params` per window in the backtest results panel (registry row 2026-06-12).
2. Skeleton/optimistic polish per master plan FE-W3 (much smaller than originally scoped — re-scope at session start against the live UI).
3. Candidate: migrate the remaining one-shot page-local fetches (profiles/candles) onto shared hooks (registry row 2026-06-12).

---

## 3 · Session-start checklist

1. `git fetch --all --prune` → `feat/snappy-honest-edge` in sync with origin; CI green on the pushed head.
2. Boot: `bash run_all.sh --local-frontend`; post-boot grep `.praxis_logs/*.log` for `loop crashed`; `curl :8000/health`.
3. **Perf/live FE verification: prod build on :3000 ONLY** (`.env` CORS excludes :3002; dev compiles lie about everything).
4. Redis DB 1 (`-n 1` + password from `.env`); TimescaleDB `psql -U postgres -d praxis_trading`; positions.status is UPPERCASE.
5. Baselines: `poetry run pytest tests/unit -q` (770) · `python scripts/ci/guards.py` (AFTER black; new files invisible until `git add`) · black/isort/ruff · frontend `npx tsc --noEmit`, `npm run test` (91), `npm run build`.
6. Soak: 4 OPEN positions; avoid NEUTRALIZE/FLATTEN and mass-closes. Soak PnL distribution remains a Phase-0 exit criterion (instrument fidelity — the edge verdict doesn't change that).

---

## 4 · Landmines & nuances added 2026-06-12

- **Decay baselines are latest-wins**: any backtest with a `profile_id` becomes that profile's decay baseline. Exploratory runs must use `profile_id=""`; canonical baselines go LAST. `scripts/en_w2_edge_triage.py` is the worked example.
- **Direct queue enqueues**: payload mirrors `routes/backtest.py` exactly; `trading_profiles.strategy_rules` is already the compiled shape; `user_id` must be the owner's real UUID (`6322b6fa-…`, stevo.do.ob@gmail.com).
- **risk_limits_grid contract** (DECISIONS 2026-06-12): keys exactly {stop_loss_pct, take_profit_pct, max_holding_hours}; requires walk_forward; embedded grid beats top-level; combined cardinality ≤100; windows × combos ≤1,000.
- **Wire decimals are str-encoded now** on `pubsub:pnl_updates` + the `pnl:*:latest` cache; new consumers parse `Decimal(str(x))` / `Number(x)`-null-safe. `parsePnlMessage` in `ws/client.ts` is the FE reference.
- **portfolioStore is position-keyed** (`PnLPositionSnapshot`, `applyPnlSnapshots` batch setter). Anything reading the old per-profile `pnlData` shape is dead code (three dead pnl components are registry-logged).
- **Gateway GETs pay a 307 trailing-slash redirect** (registry row) — don't misread doubled requests as a poller leak in network audits.
- **3 legacy dash-symbol position rows remain** (2 look synthetic — High Volume Breakout entries at 1.0005/100.05; 1 real Mean Reversion BTC). Read-side handles them; whether to clean/normalize the rows is an open operator call (B2 open issue).

---

## 5 · Open partner inputs (surface, do not block)

1. **NEW: EN-W3/EN-W4 re-prioritization** given the no-edge headline + the three EN-W2 verdicts (DECISIONS 2026-06-12) — in this session's brief.
2. Kill-switch operator-authorization model + EN-W1 exit-semantics judgment calls (2026-06-11, still pending).
3. GitHub handle for `@praxis-architect` CODEOWNERS + branch protection.
4. Capital/fees confirmation ($10k @ Binance VIP0, FLAGGED assumption #7) — blocks EN-W4 EV math.

## 6 · After this session (master plan Phase 5)

EN-W4 Yield Harvester + auto-deprecation (`decay_tracker` → `KillSwitch.set_level(NEUTRALIZE)`, never FLATTEN) + 60-day soak. **DEFER:** federation, capital allocator, sub-accounts beyond ISOLATED perp legs, signal families E/F/H/I/J.

---

*Handoff written 2026-06-12 at the close of the Phase-3 ultracode session. Memory updated: `project_hot_browser_slowness` (RESOLVED with prod numbers), `project_next_session_plan` (Phase 3 DONE + headline). Registry: rows 54/56/60/63 resolved, 10 new rows.*
