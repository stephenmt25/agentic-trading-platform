# Execution Brief — 2026-06-13

### Debt burn-down session · whole deferred list cleared · every CI gate now blocking

**Audience:** architect sign-off · **Author:** Claude Code (handler: Stevo) · **Branch state:** `feat/snappy-honest-edge` = `7b8361d`, CI **green** (run 27441306368); `main` = `ddf9db1` (35 commits behind, 16 from this session).

---

## TL;DR

A single ultracode session cleared the entire deferred-debt backlog except the items that are genuinely yours to decide. Work ran as 10 parallel ownership-scoped lanes (Wave 1) then 9 parallel cleanup agents (Wave 2), 16 commits, every change live-verified against the running stack. The headline outcome is that **every CI quality gate is now blocking and green for the first time**: mypy went 104 errors → **0 across 275 files**, ESLint 300 problems → **0/0**, and the integration job went from an empty exit-5 tolerance to **24 real tests** against live-shaped Redis + TimescaleDB. Test suite 770 → **887 unit + 24 integration + 115 frontend**.

The single HIGH-risk item shipped fully (the HITL gate no longer blocks the trade loop — the bug that once froze a soak for ~13 hours). The work also surfaced a live trading-safety event you should see (§ State changes), and there are **five decisions plus one merge-timing call** that need your sign-off. None of the five is new in kind — they are the standing partner inputs, now more timely because the engineering blockers around them are cleared.

---

## What landed

**Safety & correctness (Wave 1):**

- **HITL gate de-blocked (HIGH, registry row 44).** The human-approval gate's blocking `blpop(timeout=60)` ran *inside* the per-tick loop — one triggered signal stalled the whole engine (it froze the Phase-0 soak for ~13h once). Reworked to park-and-sweep: signals park PENDING (in-memory + Redis with a deadline), each loop iteration does a non-blocking sweep, approve resumes the gate sequence, timeout/deny fail-safe-rejects. Fail-safe semantics, audit logging, and the `PRAXIS_HITL_ENABLED=false` bypass are all preserved. The tick loop never awaits a human again.
- **Direction-aware agent scoring (ruling D-A).** Meta-learning now credits each agent on whether *its own* call was right, not just whether the trade won. Required a clean-baseline reset of the EWMA Redis state (archived, not destroyed) — executed with your live approval during the relaunch.
- **Real `cost_basis`** persisted (was a fabricated `2·gross − fees`); **tenant-scoped decay baselines** (a foreign user's backtest can no longer poison a victim's baseline); **Decimal at every repo boundary**; the unauthenticated service-local `/backtest/sweep` endpoint **retired** in favor of the auth'd gateway path (ruling D-B); **one risk-limit default authority** (settings, ruling D-D).
- **Logger crash-loop root-caused and fixed** — it had been restarting every ~30 min on a malformed alert; proven fixed live (a synthetic alert now lands real text in `audit_log`). **Real chunk-aware hypertable archiving** (the old path silently never pruned; first live run moved 106,755 `audit_log` rows). **WS pnl per-user filtering**, **kill-switch hardening**, **pyramid burst tripwire**.

**Quality gates (Wave 2):**

- **mypy 0/275, blocking** in CI + pre-commit (7 parallel typing-only agents; behavior unchanged; the few `# type: ignore` markers carry inline rationale and several point at real defects now logged as rows).
- **ESLint 0/0, blocking** (all 20 `no-explicit-any` fixed with real types, not rule-weakening; two React-Compiler-era hook rules config-disabled with justification, logged as a row).
- **24 integration tests** against real Redis + TimescaleDB (order-flow contract, kill-switch round-trip, repository CRUD incl. the tenant-scoped baseline, learning-loop→job-runner enqueue); exit-5 tolerance removed.
- **Skill-drift CI guard** wired so per-service prompt bundles can't drift from canonical.

**Docs:** 8 new ops docs (`docs/ops/`, every unmeasured number marked PROPOSED dev-box with method), 4 architecture-doc corrections, a WS-fan-out benchmark, registry + DECISIONS fully reconciled.

---

## State changes you should know about

1. **The 4-open-position soak baseline is obsolete — and a live safety mechanism proved itself doing it.** A Wave-0 fix (normalizing dash-format symbols to `BTC/USDT`) made three legacy dash-symbol BTC positions priceable for the first time. The live ExitMonitor immediately did its job: take-profit on the two synthetic High-Volume-Breakout positions (+635% / +63,649%), stop-loss on the one real Mean-Reversion position (−15.2%). The ETH soak position then time-exited and re-entered on schedule. **Soak health is now "profile ACTIVE and cycling," not a position count.** Your courtesy flag about whether to close those two synthetic positions is therefore moot — the system closed them itself, correctly.
2. **A precision defect surfaced from that event:** the +63,649% return overflowed `closed_trades.pnl_pct NUMERIC(10,6)` and that one audit row was lost (the position closed fine). Logged as a row; the fix is a column-widen migration, sequenced after the reserved 025.
3. **The first blocking CI run failed — and that was the gate working.** It exposed that CI's mypy ran without project deps on a different version than local (redis stub noise, degraded inference → 22 phantom errors a clean local tree never produces). Fixed by running mypy through poetry in CI for exact local/pre-commit parity. The re-run is fully green.

---

## Decisions requiring your sign-off

These are the standing partner inputs. The engineering work that depended on or pointed at each is now done, so they're the critical path.

1. **EN-W3 / EN-W4 re-prioritization.** The headline from the prior session stands: **every current signal family has negative out-of-sample edge** (soak RSI OOS sharpe −4.0; MACD ×3 killed, −2.7..−8.2). The instrument is now honest and the safety surface is hardened — the debt that was blocking a clean run at *finding* edge is cleared. The strategic call on what to build next (EN-W3 Tokyo substrate + Phase-A primitives is the current plan of record) is yours.
2. **EN-W2 verdicts sign-off** (carried over): MACD ×3 killed, exit re-banding rejected, close-reason convergence passes, soak decay baseline seeded. Numbers in `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md`.
3. **Kill-switch operator model.** `PRAXIS_KILL_SWITCH_OPERATORS` is now a typed setting (hardened this session). Unconfigured = single-operator mode (today's deployment unchanged). **It must be configured before any multi-user deployment** — NEUTRALIZE/FLATTEN and halt-clearing are operator-gated, STOP_OPENING/DE_RISK stay open to any authenticated user. Your call on the operator allowlist.
4. **`@praxis-architect` CODEOWNERS handle + branch protection on `main`.** Needed to enable the gated-merge model — and now materially valuable, because the branch finally has every CI gate green and blocking, so branch protection would actually hold the line.
5. **Capital/fees confirmation** — **$10k @ Binance VIP0 is still a flagged assumption**, needed before EN-W4 EV math.

**Plus one merge-timing call:** `feat/snappy-honest-edge` is 35 commits ahead of `main` and carries the entire risk-truth slice, FE-W0/W1/W2, EN-W1/W2, and this whole debt burn-down — with all CI gates green and blocking. Merging it flips `main` itself green and makes the blocking gates real for the whole repo. It's tied to decision #4 (branch protection wants the CODEOWNERS handle first). Your call on when to merge.

---

## State of the tree

| Item | State |
|---|---|
| `feat/snappy-honest-edge` | `7b8361d` — debt burn-down complete, **CI green, every gate blocking** |
| `main` | `ddf9db1` — 35 commits behind; goes green at merge (decision #4/merge call) |
| Unit / integration / frontend tests | 887 / 24 / 115 — all green |
| mypy | **0 errors / 275 files — blocking** (CI + pre-commit) |
| ESLint | **0 errors / 0 warnings — blocking** |
| Deferred registry backlog | cleared except partner-input items; **24 new honest rows** opened for what the work surfaced |
| Paper soak | profile `a05adba2` ACTIVE and cycling; HITL stays disabled for autonomy |

## New findings logged (registry rows, not fixed — per process)

- **`closed_trades.pnl_pct` overflow** on extreme returns (above) — audit row lost, position close unaffected.
- **`positions.close_reason` never populated** (0/658 CLOSED rows) — the reason lives only on `closed_trades`.
- **WS fan-out is pool-bound** at ~50 fully-served concurrent clients on the dev box (one pubsub subscription per connection from a shared 100-conn pool) — relevant if EN-W3 adds WS consumers; benchmark + numbers in `docs/ops/WS-LIMITS.md`.
- **Agents never emit their own vote direction** — so the new direction-aware scoring's contrarian-credit path can't fire on live data until producers stamp per-agent direction (MEDIUM).
- A `next dev` (:3001) Turbopack panic — environment-level, prod build (:3000) unaffected — plus ~19 smaller rows (tax float/Decimal crash, dead SentimentCache, HITL response-key TTL, et al.).

---

*Next session of record: EN-W3 Tokyo substrate (`docs/NEXT-SESSION-PLAN-2026-06-13.md`, with the burn-down deltas in `docs/NEXT-SESSION-PLAN-2026-06-14.md`).*
