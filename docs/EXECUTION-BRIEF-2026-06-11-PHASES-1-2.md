# Execution Brief — 2026-06-11 (two sessions)

### Risk-Truth slice merged · Phase 1 (FE-W0 + EN-W0) · Phase 2 (FE-W1 + EN-W1)

**Audience:** architect sign-off · **Author:** Claude Code (handler: Stevo) · **Branch state:** `main` = `ddf9db1`, `feat/snappy-honest-edge` = `d39f810`, CI green on both.

---

## TL;DR

In one day the platform went from "risk-truth slice awaiting merge" to: slice **on main** behind a green gated PR, the frontend's data layer rebuilt (FE-W0), the engine's safety surface **operable from the UI** with a four-verb tiered halt (FE-W1), and the **backtest truth-pass complete** (EN-W1) — the mandatory blocker for the Phase-6 live-decision gate is cleared. Test suite 639 → 709 backend + 79 frontend, all lint/guard gates green, everything live-verified against the running stack. **Three items below need your sign-off**, one of them a security-posture change to the kill switch.

---

## Session 1 — Phase 1 (morning)

**Risk-Truth Hardening slice (PR0–PR7) merged to `main`** via gated PR #2 with the full CI pipeline green — formally satisfies Viability Plan Phase 3 and the DECISIONS branch-model exit bar. Four pre-existing CI defects were fixed to get an honest green: unpinned lint tool versions, the 298-problem ESLint baseline (made advisory + registry row; `tsc` stays blocking), and the empty `tests/integration` job (exit-5 tolerated with a warning + registry row).

**EN-W0 — policy and gates:**

- DECISIONS entries written: **cloud region AWS Tokyo `ap-northeast-1`** (decision #1) and the **netting/margin policy** (decision #5 — horizon partitioning, never hard-veto, no cross-horizon netting, perp legs ISOLATED; binding for migration 025).
- **Blocking CI `guards` job** (`scripts/ci/guards.py`): AST-based float-gate over the four financial services honoring span-aware `# float-ok` markers, plus a Redis-channel contract gate (every channel literal must match `libs/messaging/channels.py`). Pre-commit mirrors it.

**FE-W0 — frontend data layer:**

- JWT read synchronously from the auth store; `/api/auth/session` survives only as a 30s-memoized cold-start fallback and a 401-recovery path (rotation preserved, stale-token blacklist + single retry).
- React Query infrastructure (`lib/api/hooks.ts`) with strict query-key discipline; WS warm-start; inert shell skeleton.
- Adversarially reviewed (76 agents: 3 confirmed findings fixed, 11 refuted). Runtime-verified: 19 API calls share 2 session fetches cold, **0 on warm navigation**.

## Session 2 — Phase 2 (afternoon/evening)

### EN-W1 · Backtest truth-pass *(locked decision #4 — Phase-6 gate blocker, now CLEARED)*

The defect (registry row 43): the backtester closed positions **only on opposing signals** and modeled no SL/TP/time exits, while the live engine closes **only** on SL/TP/time — backtests had no structural relationship to live behavior.

- **`libs/core/exit_policy.py`** — exit decisions extracted to a single shared lib consumed by BOTH the live `ExitMonitor` and both backtest engines. The live refactor is behavior-identical (every pre-existing test passes unchanged). Copy-paste drift is now structurally impossible.
- **Opposing-signal closes removed** from both engines; sim exits evaluate the live precedence (SL → TP → time) at bar close. No intrabar SL/TP fills — the intrabar ordering of SL vs TP is unknowable from OHLC, so any intrabar model would fabricate fills (judgment call recorded in DECISIONS, flagged for your review).
- **Walk-forward** (`walk_forward.py`): rolling train/test windows, optional per-window param-grid fit on train, evaluation strictly out-of-sample. The OOS aggregate persists as the parent `backtest_results` row — **the decay-tracker baseline is now out-of-sample by construction**. Compute budgets cap windows/combinations/job-runtime (600s) so one job can't starve the serial worker.
- **Coverage guard**: requested-vs-actual data span reported (`coverage_pct`, warning flag) — a backtest can no longer silently pretend it traded a period with no data.
- `risk_limits` threaded end-to-end (API → queue → job), with profile-ownership validation closing a cross-user decay-baseline poisoning hole the security review found.

**Live evidence (real BTC/USDT 1h, Apr 1 – Jun 1):** 62 trades closing as `time_exit: 50 / take_profit: 8 / stop_loss: 3 / end_of_data: 1` — the 100%-time-exit pathology is now *visible and measurable*, which is exactly the input EN-W2's exit-band triage needs. The 6-window walk-forward run: window-0 in-sample sharpe **5.79** vs out-of-sample **−0.60** — the honest-baseline argument in one number.

### FE-W1 · Risk-truth UI *(locked decision #6)*

- **Tiered halt control**: the modal is now a graduated four-verb control (`STOP_OPENING / DE_RISK / NEUTRALIZE / FLATTEN`) with DECISIONS-verbatim descriptions; reason mandatory; **FLATTEN behind a two-stage gate that states the locked auto-FLATTEN policy and requires typing `FLATTEN`**. Optimistic update with a tested rollback path. Chrome severity: NEUTRALIZE+ fires the danger overlay (matches the backend CRITICAL-log threshold).
- **Truth panels on `/risk`** (one click-to-reveal card, three tabs): **Portfolio** (gross vs budget, per-cluster cap utilization, per-symbol concentration from the PR4 snapshot), **Costs** (PR5 per-strategy gross→net waterfall; slippage/funding as attribution chips, never double-subtracted), **Decay** (PR7 per-profile status, AMBER + reasons verbatim — the human companion to EN-W4 auto-deprecation).
- **Three new gateway read endpoints** (`/risk/portfolio`, `/risk/decay`, `/pnl/net-of-cost`) — the engine data existed but had no API. Also fixed: the kill-switch status schema was silently stripping `level` and the activity log from responses.
- **Live-verified end-to-end**: STOP_OPENING and DE_RISK fired from the UI → `redis-cli` confirms level + audit rows → resumed clean. FLATTEN's gate proven impassable without the typed confirmation. Synthetic `decayed:true` rendered AMBER with reasons; restored afterward. NEUTRALIZE/FLATTEN deliberately **not** live-fired — 4 open paper-soak positions would have been trimmed/closed; the backend path is the same `set_level` call proven twice.

---

## Decisions requiring your sign-off

1. **Kill-switch operator authorization** *(DECISIONS 2026-06-11)*. The security review found the kill switch had authentication but **no authorization** — any logged-in account could FLATTEN all positions (cross-user destructive) or silently clear a halt someone else set. Shipped: `PRAXIS_KILL_SWITCH_OPERATORS` allowlist — NEUTRALIZE/FLATTEN and halt-clearing are operator-gated (403 otherwise); STOP_OPENING/DE_RISK stay open to any authenticated user (anyone may pull the brake; only operators may floor or release it). **Unconfigured = single-operator mode** (today's deployment unchanged; an un-clearable halt was judged worse than a tierless one). Must be configured before any multi-user deployment. The activity log (actor IDs + reasons) and the portfolio per-symbol breakdown are operator-only when configured.
2. **EN-W1 exit-semantics judgment calls** *(DECISIONS 2026-06-11)*: bar-close-only fills (no intrabar SL/TP — conservative, no look-ahead, prefix-invariance tested); sim pct-return basis is directional-off-slipped-entry vs live net-post-tax (decision logic shared, basis documented); walk-forward OOS persisted as the decay baseline; **convergence checks must filter `close_reason="end_of_data"`**.
3. **Standing inputs (unchanged, now more timely)**: (a) your GitHub handle for the `@praxis-architect` CODEOWNERS placeholder + enabling branch protection on `main`; (b) capital/fees confirmation — **$10k @ Binance VIP0 is still a FLAGGED assumption** (decision #7), needed before EN-W4 EV math.

## New findings you should know about (registry rows, not fixed — per process)

- **HIGH — live risk enforcement wrong today**: `cluster_for()` misclassifies dash-format symbols — the live portfolio snapshot shows `BTC-USDT` counted in the **ALT** cluster (ETH/USDT correctly in MAJORS), so the hot-path correlation-cluster cap enforces the wrong budget on exactly the most-correlated asset. Small fix; needs a look at how dash symbols enter `positions.symbol` at all.
- **HIGH — `/hot` total PnL has been summing zeros**: the WS pnl handler reads fields (`net_post_tax`, `roi_pct`, `position_id`) that the published event never carried — every read is silently `undefined`. Fix needs a coordinated publisher schema change; paired with the FE-W2 migration.
- 11 further rows: dead learning-loop backtest producer, non-tenant-scoped decay baseline query, repo-boundary float conversions, kill-switch hardening follow-ups, FE-W2 poller retirement, et al. Rows 43 and 55 marked RESOLVED / MOSTLY RESOLVED.

## State of the tree

| Item | State |
|---|---|
| `main` | `ddf9db1` — risk-truth slice + EN-W0, gated PR #2, CI green |
| `feat/snappy-honest-edge` | `d39f810` — FE-W0/W1 + EN-W1, pushed, **CI green** |
| Backend tests | 639 → **709** (+70, incl. SL/TP/time parity, look-ahead prefix-invariance, walk-forward, ownership) |
| Frontend tests | 66 → **79**; `tsc` clean; `next build` green |
| Lint/guards | black · isort · ruff · float/channel guards — all green and blocking |
| Paper soak | undisturbed — 4 open positions preserved, kill switch restored to NONE |

## Next (master plan Phase 3)

**FE-W2** snappy-fetch + render-jank kill (React Query migration retires the leaked page-local pollers; pairs with the WS pnl fix) · **EN-W2** per-profile edge triage — MACD kill/rebuild and A/B exit bands, now measurable because close reasons are finally honest. Then EN-W3 Tokyo substrate + migration 025 (your netting/margin entry is binding), EN-W4 Yield Harvester + auto-deprecation + 60-day soak.

---

*Full audit trail: DECISIONS.md (two new 2026-06-11 entries), TECH-DEBT-REGISTRY.md (rows 43/55 updated, 13 new), commit messages `d25a449` / `30da70e` / `9a8326b` / `d39f810`.*
