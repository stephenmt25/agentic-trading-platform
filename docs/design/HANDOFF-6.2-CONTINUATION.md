# Handoff — Phase 6.2 continuation

> Generated 2026-05-08 at the end of a session that landed 6.1 (settings) and 6.2a (backtests list + new-run modal). Read this before doing anything; it tells you where the foundations are, what's next, and the one open decision that blocks the next chunk.

---

## Branch state

- Branch: `redesign/frontend-v2`
- Worktree: `C:\Users\stevo\DEV\agent_trader_1\aion-trading-redesign`
- Last commit: `1ef6217 redesign(6.2a): backtests run list + new-run modal`
- Tests: 17/17 vitest pass
- `next build`: compiles cleanly through Turbopack; fails on **pre-existing** TS error in `app/design-system/page.tsx` from the `Tag/Pill style` CVA collision (logged HIGH/S in `docs/TECH-DEBT-REGISTRY.md`, line near "frontend (redesign branch)"). Don't fix opportunistically — it's its own ticket.

---

## What shipped in this session

**6.1 — Profiles & Settings (commit `ddbdaaf`)**
- `app/settings/layout.tsx` — CALM-mode shell, 220 nav + max-w-720 content
- `/settings` redirects to `/settings/profiles`
- 8 sub-surfaces: profiles list + detail, exchange keys, risk defaults, notifications, tax, account, sessions, audit log
- Save model per spec §11 implemented on profile detail (dirty banner, ✓ Saved, beforeunload warning)
- Backend gaps surfaced inline as `Pending` tags; logged as one MEDIUM/L entry in TECH-DEBT-REGISTRY

**6.2a — Backtests list (commit `1ef6217`)**
- `app/backtests/page.tsx` — COOL-mode list with filter bar, density toggle, sortable Table, selection action bar (Compare gates on ≥2)
- Live runs poll `api.backtest.result` and merge into the table on completion
- `app/backtests/_components/NewBacktestDialog.tsx` — Profile + Symbol + date range + Timeframe + Slippage% wired to `api.backtest.submit`; richer spec fields surfaced as Pending

---

## What's next, in priority order

### 1. **DECIDE first: chart strategy** (blocks 6.2b/c)

The portfolio doesn't spec a Chart component. Phase 6.2 detail + compare both lean on equity curves, distribution histograms, regime breakdowns. Three viable paths:

| Option | Cost | Trade-off |
|---|---|---|
| **(a)** Spec a `Chart` primitive in `docs/design/04-component-specs/` first | ~1h doc work + impl | Most rigorous; portfolio stays exhaustive |
| **(b)** Compose `recharts` inline within the surface page | low | Pragmatic but invents an out-of-portfolio pattern |
| **(c)** Sparkline-only placeholders + Pending tag (matches 6.2a's chart-deferral) | trivial | Ships structure now; real charts come later when (a) lands |

Recommendation: **(c)** for the first pass of 6.2b — keeps momentum, matches the 6.1/6.2a pattern of "render structure, surface gaps". Spec the Chart primitive after Observatory/Hot Trading reveal what shape it actually needs to be.

### 2. **6.2b — Run detail at `/backtests/[run_id]`**

Surface spec: `docs/design/05-surface-specs/04-backtesting-analytics.md` §2.

Sections needed:
- Headline KeyValue grid (ROI, Sharpe, Sortino, maxDD, trades, win-rate, avgR, profit-factor)
- Equity curve (chart deferred — see decision above)
- Trade distribution histogram (chart deferred)
- Regime breakdown bar chart (chart deferred)
- Trades table — every trade, paginated, link-out to canvas node that fired it
- "View canvas as run" button → snapshot canvas (`/canvas/{profile_id}?snapshot={run_id}`)

Backend wiring:
- `api.backtest.result(jobId)` returns the full result blob (passthrough — schema is loose). Legacy `frontend/app/backtest/page.tsx` reads `equity_curve`, `trades`, etc. from it; same shape applies.
- Sortino isn't in the response shape I saw — Sharpe is. Compute Sortino if upstream has the field; else label it as Pending.
- "View canvas as run" requires the canvas snapshot to be archived with the run (spec §7 critical-path note). Today the backend may not archive it — verify and surface as Pending if absent.

### 3. **6.2c — Compare at `/backtests/compare?runs=a,b,c`**

Surface spec §3. Side-by-side equity curves overlaid, comparison KeyValue grid with Δ columns vs the first run as baseline. Below: trade-by-trade comparison for trades that appear in multiple runs (same time + symbol, different exit).

This is mostly composition + diffing; the heavy lift is the same chart decision from above.

---

## Things to be aware of

- **Live-run polling in /backtests is intentionally naive.** The effect re-creates the interval on every `liveRuns` state change. Fine while the inflight count is small; if it ever pages, replace with a single ref-tracked interval. (`app/backtests/page.tsx` ~line 165.)
- **`api.backtest.result` is `passthrough`** in `lib/api/client.ts:140`. If you read fields off it, you'll need to cast and validate manually — there's no Zod guard. The list page already does this (`as Record<string, unknown>` then `toNumber`).
- **Profile names backfill async.** History loads in parallel with profiles; if profiles arrive after, a useEffect re-maps `profileName` on existing rows. Same pattern works for the detail page.
- **Backend reality drift is the new normal.** Both 6.1 and 6.2a hit the same shape: spec calls for richer features than the API supplies. The pattern that works is: render the spec'd structure, surface unwired bits as `<Tag intent="warn">Pending</Tag>` with one-line reasons, and don't fake. Don't invent.
- **`Tag style="solid"` is forbidden.** Use the default `style="subtle"` (just omit). The CVA collision with `HTMLAttributes.style` breaks `next build`. Existing code in `components/decisions,strategies,backtest,performance` (legacy main-branch UI) still has the issue; not your problem unless you're touching those files.

---

## Suggested next-session prompt

> Continue Phase 6.2. 6.2a (backtests list + new-run modal) is at commit `1ef6217`. Read `docs/design/HANDOFF-6.2-CONTINUATION.md` before anything else.
>
> Today's task: 6.2b — run detail at `/backtests/[run_id]`.
>
> First, decide chart strategy (handoff §1). If you pick (c), proceed; if (a), spec the Chart primitive at `docs/design/04-component-specs/chart.md` first and get signoff.
>
> Compose ONLY existing components. Backend gaps → Pending tags. After landing, commit + push as `redesign(6.2b): backtests run detail`.

---

## Phase 6 progress

- [x] 6.1 Profiles & Settings
- [x] 6.2a Backtests list + new-run modal
- [ ] 6.2b Backtests run detail
- [ ] 6.2c Backtests compare
- [ ] 6.3 Pipeline Canvas
- [ ] 6.4 Agent Observatory
- [ ] 6.5 Hot Trading
- [ ] 6.6 Risk Control

Per `docs/design/11-redesign-execution-plan.md` §6.1, the build order is intentionally inverse to user-time-spent — easiest surfaces first to harden the foundation.
