# Handoff — Post-cutover (Phase 9 merged)

> Generated 2026-05-12. **Phase 9 cutover is complete end-to-end.** `redesign/frontend-v2` has been merged into `main` via `--no-ff`. This handoff supersedes `HANDOFF-PHASE-9-START.md` (leave that file in place as audit trail). Estimated work remaining: **1 short cleanup session (~30 min)** + open backlog projects each with their own scope.

---

## Branch state

- Active branch: `main`
- Worktree: `C:/Users/stevo/DEV/agent_trader_1/aion-trading`
- Main HEAD: `6112767 Merge redesign/frontend-v2 into main — Phase 9 cutover`
- Rollback anchor: `pre-redesign-cutover` tag @ `5e1155e` (main's HEAD immediately before the merge)
- Redesign branch: still exists as `redesign/frontend-v2`, last commit `06dbb4a`. Now an ancestor of main; safe to delete locally, recommend keeping the remote ref for audit.
- Working tree state: clean modulo `.claude/settings.local.json` (local harness state, do not commit) and a couple of untracked local utility files (`frontend/public/html2canvas.min.js`, `scripts/build_ui_walkthrough_pdf.py`) that pre-date the cutover.

Two worktrees still exist:
- `C:/Users/stevo/DEV/agent_trader_1/aion-trading` — main (active)
- `C:/Users/stevo/DEV/agent_trader_1/aion-trading-redesign` — `redesign/frontend-v2`, now redundant. See **Cleanup** below.

---

## What shipped today

Eight commits between Phase 8 close and the merge, all on `redesign/frontend-v2`, all now in main:

| SHA | Commit |
|---|---|
| `196048a` | `fix(libs/storage): socket_timeout + dedicated long-blocking client` — closes HIGH-1 (KillSwitch fail-safe gap) and HIGH-2 (WS code-1006 cycling, incidentally via `health_check_interval=15`) |
| `682955e` | `fix(api_gateway): rate-limit middleware fails open on Redis errors` — surfaced during HIGH-1 validation; without this, every protected endpoint 500s during a Redis outage and the kill-switch fail-safe is invisible |
| `ebd05f2` | `redesign(chrome): /ready-aware connection pill (ADR-017)` — frontend pill now reflects downstream degradation. `/health` left static for k8s liveness |
| `c219cac` | `fix(api_gateway): normalize URL-safe symbol shape on /market-data/candles` — caught during smoke test; without this the price chart on `/hot/BTC-USDT` shows "no candles" against a healthy DB |
| `86b81c9` | `fix(/hot): PriceChart fluid layout + color + visible-range so candles paint` — three bugs in one component: fixed-pixel chart overflowing flex slot, `color-mix()` unparseable by lightweight-charts, missing `timeScale().fitContent()` after setData |
| `06dbb4a` | `fix(/backtests): preserve comparison set when adding more runs` — caught during smoke test; "Add run" now carries the existing comparison set forward via `?compare=A,B` query param |
| `6112767` | `Merge redesign/frontend-v2 into main — Phase 9 cutover` — the actual cutover commit, 165 files changed, +30,059 / −1,285 lines, no conflicts |

ADRs added:
- **ADR-017** — chrome connection pill polls `/ready`, not `/health`; 503 is a third "degraded" tone

---

## Smoke-test results (all five canonical surfaces verified on prod build before merge)

| Surface | Result |
|---|---|
| `/hot/BTC-USDT` | Pass after 3 fixes (`c219cac`, `86b81c9`). Orderbook + tape streaming, candles render, paper-order submission works, all chrome pills correct |
| `/agents/observatory` | Pass. HITL approval section renders empty (correct), DebatePanel + 3-column layout intact |
| `/risk` | Pass. Cmd+Shift+K opens kill-switch modal, arm/disarm flips the chrome pill correctly |
| `/backtests` | Pass after 1 fix (`06dbb4a`). List loads, comparison-extend flow works |
| `/settings/*` | Pass. All 9 sub-pages render structure; Pending tags inline on `/settings/{risk,notifications,tax,sessions,audit}` as expected per ADR-013 |

vitest 65/65 green, tsc --noEmit clean.

---

## Validation evidence

- **HIGH-1**: `docker stop deploy-redis-1` followed by `GET /commands/kill-switch` returns `{active:true}` in **288 ms** (target ≤ 5 s). Restored cleanly.
- **HIGH-2**: 12.5-min instrumented WS soak against `/ws`: **1 connection opened, 0 closes, 46,603 frames received**. Pre-patch baseline was 43 closes/hr. P(0 closes | λ ≈ 9) ≈ 0.01%.
- **ADR-017**: `/ready` returns 200 (Redis up) / 503 (Redis down) / 200 (after restore) — the three states the new pill renders.
- **Merge boot**: From the main worktree, all five redesign routes (`/hot/BTC-USDT`, `/agents/observatory`, `/risk`, `/backtests`, `/settings`) returned HTTP 200 on dev :3001 with backend healthy on :8000.

---

## Pending backend gaps (NOT post-cutover blockers — each is its own project)

These surfaces ship as UI shells with inline "Pending" tags per ADR-013 ("render structure, never fake"). Each becomes a separate post-cutover project. The UI is already wired and ready to render data the moment the backend lands.

| Surface | Pending area | What's needed | Source spec |
|---|---|---|---|
| `/settings/risk` | User-level risk defaults with profile-recompile fan-out | User-level risk store + recompile mechanism to propagate to active profiles | `05-surface-specs/06-profiles-settings.md` §5 |
| `/settings/notifications` | Per-event notification matrix | Replace coarse booleans on `api.preferences` with email × push × audible × event-type matrix | §6 |
| `/settings/tax` | Tax client wrapper | `lib/api/client.ts` client for the existing tax service (port 8089, backend already exists) | §7 |
| `/settings/sessions` | API tokens / sessions / webhooks | Token issuance + device listing endpoints on api_gateway | §9 |
| `/settings/audit` | User-action audit feed | Backend feed of profile edits, kill-switch transitions, key rotations | §10 |
| `/backtests` | Sortino, avg-R, per-tick equity timestamps, regime breakdown, per-agent attribution | Various backend metric emissions | Various |

Tracked in `docs/TECH-DEBT-REGISTRY.md` row 22 (MEDIUM, OPEN, effort L per backend).

---

## Open registry rows that survive cutover (LOW/MEDIUM)

None block production use. Each lands as a separate small commit when prioritized.

| Severity | What |
|---|---|
| MEDIUM | Orderbook WS gap — selective channel dropouts on `/hot/BTC-USDT` (tape unaffected). Investigate alongside any WS work. |
| MEDIUM | Backtesting simulator doesn't honor `preferred_regimes`. Affects backtest fidelity for regime-gated profiles. |
| MEDIUM | WS auth: expired JWT in URL accepted for ~50 min after expiry. Security hygiene + WS reliability. ~5 LOC in `routes/ws.py`. |
| LOW | Coinbase adapter not wired into ingestion `main.py`. Uncomment + verify sandbox creds; 1 commit. |
| LOW | `pnl:daily:...` malformed hash, self-healing on next close. Operational. |
| LOW | OrderBook "stale Xs" badge tracks wrong timestamp source. ~10 LOC. |
| LOW | §8.4-A CLS spinner `animate-spin` non-composited. One-line `will-change-transform`. Project-wide audit warranted. |
| LOW | Phase 8.3 playbook S2/S3 architectural inaccuracies. Docs hygiene. |

Full detail in `docs/TECH-DEBT-REGISTRY.md`.

---

## Rollback procedure (still valid)

If anything regresses in normal use over the next few sessions:

**Preferred — revert merge:**
```bash
cd C:/Users/stevo/DEV/agent_trader_1/aion-trading
git revert --no-ff 6112767
```
Restart the stack. Clean history, audit-friendly.

**Nuclear — reset to tag:**
```bash
cd C:/Users/stevo/DEV/agent_trader_1/aion-trading
git reset --hard pre-redesign-cutover
```
Erases the merge entirely. Safe in this repo because it's solo + local — never use `reset --hard` on shared branches.

Either path restores the legacy frontend exactly as it was at `5e1155e`. The redesign branch and all its commits remain intact.

---

## Session N+3 — Post-cutover cleanup (~30 min)

The handoff before this one specified this as the final cleanup pass. Do this when comfortable that nothing's regressing.

1. **Remove the redesign worktree:**
   ```bash
   cd C:/Users/stevo/DEV/agent_trader_1/aion-trading
   git worktree remove ../aion-trading-redesign
   ```
   This frees the disk and removes the duplicate working copy. The `redesign/frontend-v2` branch survives as a git ref.

2. **Archive the legacy design-system doc:**
   ```bash
   git mv frontend/DESIGN-SYSTEM.legacy.md docs/historical/
   ```
   Or delete outright if you confirm nothing references it. (At the time of the merge `frontend/DESIGN-SYSTEM.legacy.md` had no inbound references in the source tree; `DESIGN.md` is the load-bearing one.)

3. **Sync portfolio with shipped reality.** Read `docs/design/05-surface-specs/*.md` and update places where shipped behavior diverged from spec. Per ADR-013 §Consequences — the redesign portfolio is meant to track reality, not freeze a snapshot.

4. **Registry cleanup.** Mark all Phase 8.1 GAP rows and `frontend (redesign branch)` rows as historical. Promote surviving deferred items (Settings backend gaps, vectorbt regimes, etc.) into clean post-cutover backlog rows with explicit owners.

5. **Branch policy decision.** Delete `redesign/frontend-v2` locally (`git branch -D redesign/frontend-v2`)? The merge commit references it forever; the branch ref itself stops mattering. Recommendation: keep remote (audit trail), delete local once you're done with cleanup-related operations on it.

---

## Things to be aware of (carrying forward + new)

Still valid from earlier handoffs:
- `PRAXIS_PAPER_TRADING_MODE` defaults to `false` on main now; **do not toggle to live without explicit user direction.**
- `set-state-in-effect` warning at `OrderBook.tsx:275` is pre-existing; not a regression.
- `PriceChart` canvas is `aria-hidden` intentionally — `lightweight-charts` doesn't expose a meaningful tree.
- Test profile: `9c94da6c-8d20-42f3-b086-9170e3ba8f2c` (Mean Reversion).

New since cutover:
- **The `pre-redesign-cutover` tag is the load-bearing rollback ref.** Do not delete it until weeks have passed without rollback being needed. The tag costs nothing to keep.
- **`docs/design/HANDOFF-PHASE-9-START.md` lives in the old redesign worktree only.** It was never committed — it's a working note. When you remove the worktree, that file disappears. This handoff replaces it; the audit trail of phase work is in commit history + `docs/design/09-decisions-log.md` + the per-phase HANDOFF-*.md files that WERE committed (Phase 6.2, 6.3, 7, 8 start/continue/final).
- **`.next/` build artifacts in both worktrees are now stale.** Run `npm run build` fresh from main if you want to test prod-build behavior.
- **The PriceChart `fluid` prop is new.** Use it in any future composition where the chart shares vertical space proportionally with siblings. Default (fluid=false) preserves fixed-pixel density behavior for standalone usage.

---

## Suggested next-session prompt

> Continue post-cutover cleanup on `main`. The redesign is live; the cutover landed at `6112767`. Read `docs/design/HANDOFF-POST-CUTOVER.md` before anything else.
>
> Plan for this session (Session N+3, ~30 min):
> 1. Remove the redesign worktree: `git worktree remove ../aion-trading-redesign`
> 2. Decide on `frontend/DESIGN-SYSTEM.legacy.md` (archive to `docs/historical/` or delete)
> 3. Walk `docs/design/05-surface-specs/*.md` and reconcile spec vs shipped reality (light edits only; deep updates are separate work)
> 4. Promote surviving Phase 8 / Phase 9 registry rows into clean post-cutover backlog items
> 5. Decide whether to delete `redesign/frontend-v2` locally
>
> Stop and ask before deleting the `pre-redesign-cutover` tag — it's the load-bearing rollback anchor.

---

## Other artifacts to know about

- **`HANDOFF-PHASE-9-START.md`** — superseded by this file. Lives only in the old redesign worktree (was never committed).
- **`HANDOFF-PHASE-8-FINAL.md`** — committed, frozen. Last handoff before cutover work began.
- **Earlier HANDOFF-PHASE-*.md files** — committed, frozen audit trail.
- **`docs/design/PHASE-8-PERF-PLAYBOOK.md`** — perf gate procedures. Still applicable post-cutover for any future regression work.
- **`docs/design/PHASE-8-RESILIENCE-PLAYBOOK.md`** — S1/S2/S3 scenarios. Note: 2 minor architectural inaccuracies logged in the registry — fix during next playbook pass.
- **`docs/design/PHASE-8-PARITY-AUDIT.md`** — legacy parity coverage matrix. Reference when scheduling post-cutover backend work.
- **`docs/design/perf-traces/2026-05-11-results.md`** — §8.4 perf gate results. Frozen reference.
- **`docs/design/perf-traces/2026-05-11-resilience-results.md`** — Phase 8.3 resilience results. Frozen.
- **`docs/TECH-DEBT-REGISTRY.md`** — open backlog items.
- **`docs/design/09-decisions-log.md`** — ADRs through ADR-017. The narrative of why the design is what it is.
- **`docs/design/11-redesign-execution-plan.md`** — canonical phase-by-phase plan. Phases 1–9 now historical; can be marked accordingly during the portfolio-sync step.
