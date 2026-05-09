# Handoff — Phase 7 start (Phase 6 complete)

> Generated 2026-05-09 at the end of a session that landed the remaining four Phase 6 milestones (6.3 Pipeline Canvas, 6.4 Agent Observatory, 6.6 Risk Control, 6.5 Hot Trading) plus the deferred PriceChart primitive. **All six surfaces in `05-surface-specs/` now exist.** Read this before doing anything; it tells you where the surfaces stand, what each one's "Pending" tags translate to as concrete work for Phase 7, and the validation gates that block merge.

---

## Branch state

- Branch: `redesign/frontend-v2`
- Worktree: `C:\Users\stevo\DEV\agent_trader_1\aion-trading-redesign`
- Last commit: `41f7a3b redesign(6.5): hot trading at /hot/[symbol]`
- Recent commit chain (this session):
  - `c2b0999` (6.3 Pipeline Canvas)
  - `e30a172` (6.4 Agent Observatory)
  - `431fea7` (6.6 Risk Control)
  - `f66858e` (PriceChart primitive + spec)
  - `41f7a3b` (6.5 Hot Trading)
- Tests: **44/44 vitest pass** (was 30/30 — added 14 PriceChart tests this session).
- `tsc --noEmit`: redesign code is clean. Pre-existing legacy errors only — same 20 lines, same files, none touched (`components/backtest/EquityCurveChart.tsx`, `components/data-display/List.tsx`, `components/decisions/`, `components/performance/`, `components/strategies/`).
- `next build`: still blocked by the legacy `EquityCurveChart.tsx` recharts formatter. `next dev` works fine. Tracked LOW in `docs/TECH-DEBT-REGISTRY.md`; will be deleted at Phase 9 cutover when legacy components retire (do not fix opportunistically).
- `eslint`: clean across all redesign files.
- The full stack may or may not be running depending on session-of-the-day. To check: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3001/canvas`. To start: `bash run_all.sh --local-frontend` from the redesign root. To stop: `bash run_all.sh --stop`.

---

## What shipped this session

Five commits, all on the redesign branch, in build order.

**6.3 — Pipeline Canvas** (commit `c2b0999`)
- `app/canvas/page.tsx` — profile picker / auto-redirect when one profile.
- `app/canvas/[profile_id]/page.tsx` — three-column COOL surface composing the existing `components/canvas/` (Node, Edge, NodePalette, NodeInspector, RunControlBar) against `@xyflow/react`.
- `_components/CanvasNode.tsx` + `CanvasEdge.tsx` — xyflow adapters wrapping the redesign Node/Edge so connection routing works without breaking the spec's visual contract. Backend node-types (`input | gate | agent_input | meta | output`) map to redesign Node `kind`s (`data-source | decision | agent | sink`).
- `_components/InspectorContent.tsx` — config form generator from `api.agentConfig.catalog()` (`AGENT_CATALOG`).
- Wired: `GET /agent-config/{id}/pipeline`, `PUT` on save (atomic `strategy_rules` recompile per CLAUDE.md §2C), reset endpoint, profile selector switches routes, `Cmd+S` saves.
- Pending: per-node live activity, run paper/live launch, drag-from-palette node creation (backend ids are compile-significant — `strategy_eval` etc.), templates / compare / comments / auto-layout (spec §6/§7/§8), strategy_eval rule editor (points users to `/profiles` for now).

**6.4 — Agent Observatory** (commit `e30a172`)
- `app/agents/page.tsx` — redirects to `/agents/observatory`.
- `app/agents/observatory/page.tsx` — three-column COOL surface: roster (220px) | filter bar + virtualized event stream (`react-virtuoso`) | focus panel (460px).
- `_components/Roster.tsx` — six agentic AgentKinds (`ta`, `regime`, `sentiment`, `slm`, `debate`, `analyst`) with live status from `agentViewStore`.
- `_components/FocusPanel.tsx` — selected event renders full `AgentTrace`; default falls back to spec §5 summary dashboard (regime `ConfidenceBar`, sentiment `Sparkline`, TA, debate Pending, agent health rollup).
- `_components/eventHelpers.ts` — `backendIdToKind` mapping (also reused by 6.5).
- Keyboard map per spec §7: J/K, Enter, F (focus search), Cmd+1..6 (toggle agents), Esc.
- Pending: reasoning-body search (events aren't indexed), symbol filter (events lack a normalized symbol), debate event type (no telemetry shape), override / silence / replay actions (no intervention API).

**6.6 — Risk Control** (commit `431fea7`)
- `app/risk/page.tsx` — single-column HOT surface in fixed spec order: kill switch → exposure → active limits → recent violations.
- Wired: `api.commands.killSwitchStatus` polled every 10s; modal requires reason text and refuses empty submissions; `api.agents.risk(profile_id)` polled; concentration % derived from `api.positions.list`; active limits from profile `risk_limits` jsonb with utilization-colored `StatusDot` at the spec's 60%/85% thresholds.
- `Cmd+Shift+K` toggles the modal locally on this surface.
- Pending: hard-arm vs soft-arm distinction (backend kill switch is binary), global `Cmd+Shift+K` (works only here for now), portfolio VaR, leverage × (backend exposes allocation %), live values for stop-loss / take-profit / max-hold, order-rejection / warning violation log.

**PriceChart primitive** (commit `f66858e`)
- `docs/design/04-component-specs/price-chart.md` — full spec (anatomy, states, tokens, variants, accessibility, don'ts, references) with an explicit "deferred to v2" list.
- `docs/design/04-component-specs/trading-specific.md` — §Chart shrunk to a one-paragraph pointer at `price-chart.md` to avoid spec duplication.
- `docs/design/04-component-specs/README.md` — index updated.
- `components/trading/PriceChart.tsx` — `lightweight-charts` v5 wrapper. Theme tokens via `getComputedStyle` reapplied on a 1.5s tick so mode swaps repaint without rebuilding the chart. `setData()` on shape changes, `update()` on the trailing two bars for tick-only updates. Custom timeframe tab strip + symbol/status slots. ResizeObserver for responsive width.
- `app/design-system/page.tsx` — `PriceChart` Section with three demos backed by a deterministic synthetic candle generator (no `Math.random` — keeps SSR stable).
- `components/trading/PriceChart.test.tsx` — 14 vitest tests covering tablist, tabs, summary, mode pill, loading/error/empty, slot composition.
- Pending (per spec): drawing tools strip (pencil/line/fib/eraser), inline DepthChart strip composition, multi-pane indicators, replay-playback control strip, range-selection brush, keyboard candle nav.

**6.5 — Hot Trading** (commit `41f7a3b`)
- `app/hot/page.tsx` — redirects to `/hot/BTC-PERP` per surface spec §1 default landing.
- `app/hot/[symbol]/page.tsx` — three-column HOT cockpit: chrome (breadcrumb + symbol Select + status pills row + chrome `PnLBadge`) → center column (`PriceChart` 60% + `OrderBook` | `TapeRow` split + Positions / Orders / Fills tabs) | right column 360px (`OrderEntryPanel` + `AgentSummaryPanel`).
- Wired: candles via `api.marketData.candles`, positions polled every 5s and scoped to surface symbol, chrome `PnLBadge` from `usePortfolioStore().pnlData`, kill switch polled every 10s with `Cmd+Shift+K` modal (same shape as `/risk`), agent feed from `agentViewStore.globalFeed` filtered to the surface symbol → up to 3 compact `AgentTrace` cards + "see all in Observatory ▸" link.
- Per ADR-006 / IA §7: ≤1024px the right column is hidden entirely (monitor-only mode). A warn-toned banner explains the absence.
- Pending: order submission endpoint (no `api.orders.submit`; submit toasts the intent), orderbook WS channel (rendered with synthesized levels around last close), trades WS channel (one frozen example row), Open Orders / Fills endpoints (tabs render Pending panels), hard-arm kill switch (same as `/risk`), regime / latency / agent-count chrome pills.

---

## Phase 6 outcome (the scoreboard)

```
[x] 6.1   Profiles & Settings           /settings
[x] 6.2a  Backtests list + new-run      /backtests
[x] 6.2b  Backtests run detail          /backtests/[run_id]
[x] 6.2c  Backtests compare + Chart     /backtests/compare
[x] Foundation pass — Tag/Pill type collisions, ModeProvider docs
[x] 6.3   Pipeline Canvas               /canvas, /canvas/[profile_id]
[x] 6.4   Agent Observatory             /agents/observatory
[x] 6.6   Risk Control                  /risk
[x] PriceChart primitive                components/trading/PriceChart.tsx
[x] 6.5   Hot Trading                   /hot, /hot/[symbol]
```

**Every surface in `05-surface-specs/` is implemented.** Every component in `04-component-specs/` is implemented and consumed by at least one surface (no zombies). The `data-mode` per surface matches `02-information-architecture.md`.

---

## What's next, in priority order

### 1. **Phase 7 — Data wiring & polish** (the natural next phase)

Phase 7 in `11-redesign-execution-plan.md` §"Phase 7" calls for:

- Real-time WebSocket reliability (reconnection, exponential backoff, stale-data indicators)
- Optimistic updates on order placement (with rollback on validation reject)
- Mid-render layout stability — no CLS on price ticks
- Performance budgets — `OrderBook` should never block scroll for >16ms
- Audit log surface — the lowest-priority Settings sub-surface, do it last

**The accumulated Pending tag inventory tells you what backend wiring needs to land first.** Each tag is intentionally specific so closing it is mechanical:

| Surface | Pending tag | What's actually needed |
|---|---|---|
| `/hot` | order submission | New `api.orders.submit` endpoint backed by `services/execution`; adapter to `OrderEntryPanel.onSubmit`. |
| `/hot` | orderbook live data | New `pubsub:orderbook:{symbol}` (or Redis stream) + `wsClient` subscription → store; replace synthesized levels in `OrderBookPanel`. |
| `/hot` | tape live data | Same pattern — `pubsub:trades:{symbol}` channel + `wsClient` route → `TapePanel` state. |
| `/hot` | Open Orders / Fills tabs | `api.orders.list({ status })` + either `api.orders.fills` or a `pubsub:fills` channel. |
| `/hot` | regime / latency / agent count chrome pills | Three thin reads — surface-side rollups from existing stores once wired. |
| `/risk`, `/hot` | hard-arm vs soft-arm kill switch | Backend `services/risk` (or wherever `KillSwitch` lives) needs a tri-state model — current is binary. The frontend will pick this up automatically when `KillSwitchStatus.active` becomes a state enum. |
| `/risk` | global Cmd+Shift+K | Move the kill-switch modal mounting from each surface (`/risk`, `/hot`) into `RedesignShell`; both surfaces' local modals become redundant. ~50 LOC. |
| `/risk` | portfolio VaR | New `services/risk` endpoint; surfaces in the existing Exposure section. |
| `/risk` | violation log | New `services/risk` endpoint or `pubsub:violations` channel; the section already has the empty-state copy ready. |
| `/risk` | live values for stop-loss / take-profit / max-hold | Per-position metrics from `pnl` / `risk` services — drop the row's `pending` flag in `app/risk/page.tsx:activeLimits`. |
| `/agents/observatory` | reasoning-body search | Either index `agent_telemetry` events server-side (Postgres FTS) or accept client-side filtering on the in-memory ring buffer. The client-side path is ~10 LOC. |
| `/agents/observatory` | symbol filter | `AgentTelemetryEvent.payload` needs a normalized `symbol` field across all six agentic agents; right now only some carry it. |
| `/agents/observatory` | debate event type | New `event_type === "debate_round"` (with rounds + contributions per `DebatePanel` shape) emitted by `services/debate`. |
| `/agents/observatory` | override / silence / replay | Backend intervention API (writes a `user_override` event onto the analyst archive per spec §8). |
| `/canvas` | drag-from-palette | Backend node-id reservation rules (spec §6 templates lean on this); current compile chain looks for `strategy_eval` / `agent_modifier` / etc. by literal id. |
| `/canvas` | per-node live activity | Per-node telemetry pipeline (`pubsub:canvas_node_activity` or similar) → adornments on each `Node`. |
| `/canvas` | run paper / live launch | A `POST /canvas/{id}/run?mode=paper|live` endpoint, or wire to the existing strategy launcher. |
| `/canvas` | strategy_eval rule editor | Port the legacy `StrategyEvalForm` to redesign tokens; v2 of `InspectorContent`. |
| `/canvas` | templates / compare / comments / auto-layout | Spec §6/§7/§8 features — each is its own session. |
| `PriceChart` | drawing tools | Pencil / line / fib / eraser; spec the actual tool affordances when Hot Trading proves the demand. |
| `PriceChart` | replay playback strip | Lands when Backtesting replay (post-6.5) needs it. |
| `PriceChart` | range-selection brush | When a surface needs to scrub a time window. |
| `PriceChart` | keyboard candle nav | Deferred until `lightweight-charts` ships first-class keyboard support. |
| `/settings/{risk,notifications,tax,sessions,audit}` | various | See the open tech-debt entry under `api_gateway, frontend (redesign branch)` for the full list. |

**Recommended Phase 7 order:**

1. **Move kill-switch modal global** (low-hanging — closes a Pending tag on two surfaces in one move).
2. **Wire `OrderBook` + `TapeRow` live data** on `/hot` — needs a backend channel; the frontend side is ~30 LOC each once the channel exists. This is the highest-stakes UX gap.
3. **Wire order submission** on `/hot` — pair with optimistic-update + rollback per Phase 7 brief.
4. **Performance budget audit** on `/hot` — profile `OrderBook` under live load; the spec calls for ≤16ms scroll-block.
5. **Audit log surface** — the Settings sub-surface left over from 6.1.

Items 1–3 are the most user-visible. Item 4 is the highest-stakes ahead of merge. Item 5 closes the last Pending in Settings.

### 2. **Phase 8 — Validation gates**

`11-redesign-execution-plan.md` §8.1–8.5 lists the gates. Most are satisfiable by inspection now; a few will block merge until Phase 7 closes Pending tags.

| Gate | Status |
|---|---|
| 8.1 Functional parity with main | Partial — order submit + kill-switch hard-arm + several legacy endpoints are still Pending. |
| 8.2 Design fidelity (no hex literals, mode-correct, tabular, every component used) | **Probably green.** Spot-check with `grep -r "#[0-9a-fA-F]\{6\}" frontend/components/`. Every component in `04-component-specs/` has at least one surface usage. |
| 8.3 Critical-path resilience (Risk Control works when other services down, kill switch works when API gateway degraded, Hot Trading degrades gracefully) | Untested; needs a session of failure-injection. |
| 8.4 Performance budget (FCP <1.5s on Hot Trading, no frame drop on `OrderBook` at 100 updates/s, no >50MB memory growth in 1h) | Untested; needs Item 4 above. |
| 8.5 Accessibility minimum (Hot Trading keyboard-only, kill switch ≤2 keystrokes from any surface, focus rings, accessible names) | Mostly green by composition (all primitives ship with focus rings); kill-switch ≤2 keystrokes needs the global `Cmd+Shift+K` from Item 1. |

### 3. **Phase 9 — Cutover**

Per `11-redesign-execution-plan.md` §9. Don't start until Phase 8 is fully green. The branch carries 25+ commits; the merge will be substantial. Tag `pre-redesign-cutover` before merging. Document a rollback. Remove the worktree after.

---

## Things to be aware of

- **The SSR mode-flash is still real and still deferred.** Non-HOT routes paint once with HOT tokens before the client effect runs and swaps. Documented in `components/providers/ModeProvider.tsx`. The fix is route-aware SSR via middleware; defer until a user actually flags the flicker.
- **`next build` still fails** because of the legacy `EquityCurveChart.tsx` recharts type error. `next dev` works fine. Don't fix opportunistically — Phase 9 deletes legacy. Logged LOW in `TECH-DEBT-REGISTRY.md`.
- **`react-hooks/purity` lint rule is strict.** Don't call `Date.now()` in `useMemo` / render — store a `nowTick` state and bump it on a timer (the pattern is in `app/agents/observatory/page.tsx:nowTick`). Don't call `setState` synchronously inside `useEffect` — derive instead (see `app/agents/observatory/page.tsx:safeActiveIndex`). This came up twice this session.
- **The Pending-tag pattern works.** Four surfaces in a row shipped using "render the spec'd structure, surface unwired bits as Pending tags with one-line reasons, never fake." Continue it for any post-6.5 work.
- **PriceChart theming via `getComputedStyle` polls every 1.5s.** Cheap, and necessary because `lightweight-charts` doesn't subscribe to CSS-var changes. If a future user complains about the poll cost, the alternative is a `MutationObserver` on `<html data-mode>` — slightly more code, less wall-clock work. Not worth the swap unless flagged.
- **The `lightweight-charts` v5 API uses `chart.addSeries(CandlestickSeries, options)`** rather than the legacy `addCandlestickSeries()`. If you see online examples using the old form, they're for v4.
- **Order submission is intentionally not wired** in `/hot`. The `OrderEntryPanel.onSubmit` callback toasts the intended order. When you wire `api.orders.submit`, the surface change is one function — see the comment in `handleSubmit`.
- **The Roster's six AgentKinds (ta/regime/sentiment/slm/debate/analyst) don't fully map to the backend's 11-agent registry.** Only 5 of the 6 are in `AGENT_REGISTRY` (slm_inference is missing). The Observatory hides events from agents not in the agentic kinds — by design per the surface spec, but worth knowing.
- **Status pills in the `/hot` chrome (regime / latency / agent count) are Pending placeholders.** These are easy reads off existing stores once wired; deliberately not faked.
- **The full PriceChart component canvas is `aria-hidden`** because `lightweight-charts` is canvas-based and doesn't expose a meaningful tree. The wrapping `role="region"` carries the accessible label. Keyboard candle navigation is in the v2 deferred list — surface a follow-up if accessibility audit pushes it forward.
- **Tests are in good shape (44/44).** PriceChart's tests mock `lightweight-charts` to skip the canvas; that pattern is reusable for any future tests of the wrapper.

---

## Suggested next-session prompt

> Continue the Praxis frontend redesign on `redesign/frontend-v2`. Phase 6 is complete (all six surfaces + PriceChart shipped); commit `41f7a3b` is the head. Read `docs/design/HANDOFF-PHASE-7-START.md` before anything else.
>
> Today's task: Phase 7. Pick one of the four ranked items in the handoff §1 ("Recommended Phase 7 order") — recommend starting with **moving the kill-switch modal global** since it closes a Pending tag on two surfaces in one ~50 LOC move and unblocks the §8.5 accessibility gate.
>
> Compose only existing components. Wire concrete backend endpoints; surface remaining gaps as `Pending` tags with one-line reasons. After landing, commit + push as `redesign(7.x): <what you did>`.

---

## Other artifacts to know about

- **`REPLICATION-PLAYBOOK.md`** (`docs/design/`) — the how-to for replicating this design-system style for a different repo or aesthetic. Stable through this session.
- **`TECH-DEBT-REGISTRY.md`** (`docs/`) — append-only log. The Tag/Pill row is RESOLVED; the legacy `EquityCurveChart` row stays OPEN until Phase 9. The Settings backend gaps row from 6.1 is OPEN and tracks the Phase 7 wiring backlog for Settings sub-surfaces specifically.
- **`HANDOFF-6.3-START.md` and `HANDOFF-6.2-CONTINUATION.md`** are now superseded by this file. Leave them in place as audit trail.
- **`11-redesign-execution-plan.md`** is the authoritative phase plan. Phases 7–9 are described there in the same level of detail as 4–6 were when this began.
- **Phase 6 commit count**: 11 commits (`ddbdaaf` through `41f7a3b`), spanning 2026-05-04 through 2026-05-09. No rebases, no force-pushes.
