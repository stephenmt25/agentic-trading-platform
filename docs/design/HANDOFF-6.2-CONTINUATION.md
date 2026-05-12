# Handoff — Phase 6.2 continuation (post-6.2b)

> Generated 2026-05-08 at the end of a session that landed 6.2b (run detail) and the Chart primitive spec. Supersedes the earlier post-6.2a handoff at this same path. Read this before doing anything; it tells you where the foundations are, what's next, and the one open decision that shapes the rest of 6.2.

---

## Branch state

- Branch: `redesign/frontend-v2`
- Worktree: `C:\Users\stevo\DEV\agent_trader_1\aion-trading-redesign`
- Last commit: `7861aa1 redesign(6.2b): backtests run detail`
- Tests: 17/17 vitest pass
- `tsc --noEmit`: zero new TS errors. Pre-existing errors in `app/design-system/page.tsx` (Tag/Pill `style` CVA collision), `components/data-display/{List,Pill}.tsx`, `components/primitives/Tag.tsx`, `components/{decisions,strategies,performance,backtest}/...` (legacy main-branch UI), and `components/backtest/EquityCurveChart.tsx` (recharts formatter signature) — all logged in `docs/TECH-DEBT-REGISTRY.md`. Don't fix opportunistically.
- `next build`: still fails on the same pre-existing CVA collision in design-system page; route compiles fine via `next dev`.

---

## What shipped in this session

**Chart primitive spec (commit `7861aa1`)**
- `docs/design/04-component-specs/chart.md` — line / area / bar XY chart, COOL-mode focused. OHLC explicitly out-of-scope and routed to a future `PriceChart` in `trading-specific.md`. Heatmaps + brush-range deferred with named follow-up homes. SVG-first, `d3-shape` line/area generators allowed if math complexity demands.
- `docs/design/04-component-specs/README.md` index updated.

**6.2b — Run detail (commit `7861aa1`)**
- `app/backtests/[run_id]/page.tsx` — composes `KeyValue`, `PnLBadge`, `Sparkline`, `Table`, `Tag`, `Pill`, `Button`, `StatusDot`. Headline KeyValue grid (ROI, Sharpe, maxDD, trades, win-rate, profit-factor, avg-return), Sortino + avgR Pending. Equity-curve section uses `Sparkline` + "Chart pending" tag. Distribution + regime panels are full Pending placeholders. Paginated trades table (50/page). "View canvas as run" button with snapshot-pending tag. Loading / error / not-completed / failed states all handled.
- Backend gaps surfaced inline as Pending tags (matches 6.1 / 6.2a pattern): Sortino, avg-R / R-multiples, regime breakdown, per-agent attribution, canvas snapshot archived with run, per-trade exit reason + decision-event link.

---

## What's next, in priority order

### 1. **DECIDE first: Chart implementation timing** (shapes 6.2c and the rest of Phase 6)

The Chart spec is now binding (signed off this session). Three viable paths from here:

| Option | Cost | Trade-off |
|---|---|---|
| **(A)** Ship 6.2c with the same Sparkline + Pending placeholder pattern, implement Chart as its own piece later | low | Keeps momentum on surface coverage; 6.2b/c stay placeholder-shaped until Chart lands and then upgrade transparently |
| **(B)** Implement Chart first, then 6.2c with the real component | high | Backtesting gets full fidelity in one shot; Chart implementation is sizeable enough to warrant its own focused session |
| **(C)** 6.2c + Chart in the same session | very high | Risky — Chart is the kind of primitive whose API gets stress-tested by its first integration. Shipping the integration and the primitive together makes the iteration loop slow. |

**Recommendation: (A).** Chart is foundational — when it lands it should be its own commit, with its first integration being the `EquityCurveSection` in 6.2b retrofitted as the validation case. 6.2c is mostly composition + diffing on top of structure that already exists; doing it placeholder-shaped first is fine and matches what 6.2b does. After 6.2c, Chart is the natural next focused piece (~1-2 sessions on its own).

### 2. **6.2c — Compare at `/backtests/compare?runs=a,b,c`**

Surface spec: `docs/design/05-surface-specs/04-backtesting-analytics.md` §3.

Sections needed:
- Header — breadcrumb, run-id chips with remove (Pill `as="removable"`), "Add another run" affordance (route back to list with selection persisted? or modal?). The list page already navigates here with comma-joined ids in `?runs=`.
- Comparison KeyValue grid — same headline metrics as 6.2b, plus a `Δ` column per run vs the first selected run as baseline. Use existing `KeyValue` + diffing logic; surface up/down arrows colored by sign.
- Side-by-side equity curves — overlaid using accent + neutral palette (per spec §3, since these aren't agents). Multi-series line is exactly the case the Chart spec was written for; for now, render N separate `Sparkline`s vertically stacked OR overlaid in a flexbox with `Tag` legend, plus the same "Chart pending" tag as 6.2b.
- Trade-by-trade comparison (below) — for trades that appear in multiple runs (same time + symbol, different exit). Backend doesn't currently emit a "shared trade key" so this likely has to be derived client-side: `entry_time + symbol + side` is the natural fingerprint. If two runs use different timeframes that'll never match — surface as Pending with a one-line caveat.

Backend wiring:
- `api.backtest.result(jobId)` per-run, in parallel — mirror the loadHistory flow on the list page. Each blob is `passthrough`-typed; reuse the `as Record<string, unknown>` + `toNumber` pattern from 6.2b.
- "Empty when only one run" empty state per spec §6 — render a friendly "Select 2 or more runs to compare" with a back-to-list link.

### 3. **Chart primitive implementation** (per `chart.md`)

The first integration should be 6.2b's `EquityCurveSection`. Recommended path:
- `frontend/components/data-display/Chart.tsx` — the main component. Use `d3-shape` for `line()` and `area()` generators (already small, ESM-friendly); everything else hand-rolled SVG matching the `Sparkline` pattern.
- Props per the spec (`series`, `xKey`, `xType`, `yScale`, `axes`, `gridLines`, `barLayout`, `tooltip`, `legend`, `downsample`, `dimmed`, `tableFallback`).
- Add to `components/data-display/index.ts`.
- Retrofit `app/backtests/[run_id]/page.tsx`: replace `<Sparkline>` in `EquityCurveSection` with `<Chart>` configured for line + area (drawdown overlay), drop the "Chart pending" tag.
- Add a Storybook-equivalent demo on `app/design-system/page.tsx` once the design-system Tag/Pill collision is resolved (logged separately).

The handoff will not pre-decide the runtime tooling further than that — the spec covers the contract; the implementation should match what `Sparkline` does. If the line/area math feels heavy enough to warrant `d3-shape`, pull it; otherwise hand-roll.

---

## Things to be aware of

- **The `view canvas as run` button is currently a soft-link to the live canvas, not a snapshot.** It's tagged "Snapshot pending" and the title attribute warns the user. When the backend starts archiving the canvas snapshot with the run (per surface spec §7 critical-path note + ADR P4), drop the warning tag and update the URL semantics — `/canvas/{profile_id}?snapshot={run_id}` is the agreed shape.
- **Trades table has no "exit reason" column yet.** The simulator's `SimulatedTrade` shape doesn't carry one. Spec §2 calls for `reason` after `R`. Either add to the backend payload or document it as Pending in the column header (currently surfaced as a header-level Pending tag).
- **`equity_curve` is a flat `number[]` with no timestamps.** This matters for the Chart implementation — when it lands, the equity curve will need synthetic x positions (index → relative timestamp) until the backend emits paired (t, equity) tuples. Avoid baking a "timestamps required" assumption into the Chart API; the spec deliberately allows numeric/categorical xType.
- **Live-run polling on `/backtests` re-creates the interval on every state change.** Carryover note from 6.2a: fine while inflight count is small; replace with a single ref-tracked interval if it ever pages.
- **`Tag style="solid"` is still forbidden.** Default style="subtle" everywhere. The CVA/HTMLAttributes `style` collision in `components/primitives/Tag.tsx` is the same bug that breaks `next build`; it's its own ticket.
- **Backend reality drift is the steady state.** Continue the "render the spec'd structure, surface unwired bits as Pending tags with one-line reasons, never fake" pattern. It's worked for 6.1, 6.2a, and 6.2b — three surfaces in a row.
- **Browser smoke-test wasn't run for 6.2b.** Port 3001 was bound to the user's existing dev server. The page is TS-clean and lint-clean and composes only existing components, so risk is low — but confirm visually before declaring 6.2 done.

---

## Suggested next-session prompt

> Continue Phase 6.2. 6.2b (run detail + Chart spec) is at commit `7861aa1`. Read `docs/design/HANDOFF-6.2-CONTINUATION.md` before anything else.
>
> Today's task: 6.2c — compare at `/backtests/compare?runs=a,b,c`.
>
> Decide Chart implementation timing (handoff §1) before starting. If you pick (A), proceed with the same Sparkline + Pending placeholder pattern as 6.2b. If (B) or (C), confirm scope first — Chart is its own meaningful piece of work.
>
> Compose ONLY existing components (modulo Chart if you go (B)/(C)). Backend gaps → Pending tags. After landing, commit + push as `redesign(6.2c): backtests compare`.

---

## Phase 6 progress

- [x] 6.1 Profiles & Settings
- [x] 6.2a Backtests list + new-run modal
- [x] 6.2b Backtests run detail (Chart slots Pending)
- [ ] 6.2c Backtests compare
- [ ] Chart primitive implementation (binding spec at `04-component-specs/chart.md`)
- [ ] 6.3 Pipeline Canvas
- [ ] 6.4 Agent Observatory
- [ ] 6.5 Hot Trading
- [ ] 6.6 Risk Control

Per `docs/design/11-redesign-execution-plan.md` §6.1, the build order is intentionally inverse to user-time-spent — easiest surfaces first to harden the foundation. Chart is a primitive, so it slots in whenever Backtesting completion forces the question; Hot Trading's `PriceChart` is a separate animal entirely (deferred per `chart.md`'s out-of-scope note).
