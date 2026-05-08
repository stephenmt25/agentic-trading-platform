# Handoff — Phase 6.3 start (post 6.2c + foundation pass)

> Generated 2026-05-08 at the end of a session that landed 6.2c (compare + Chart primitive), the design-system catalog bug fix, the replication playbook, and a foundation-gap pass (Tag/Pill type collisions, ModeProvider docstring). Read this before doing anything; it tells you where the foundations are, what's next, and the open decision that shapes the next session.

---

## Branch state

- Branch: `redesign/frontend-v2`
- Worktree: `C:\Users\stevo\DEV\agent_trader_1\aion-trading-redesign`
- Last commit: `b464c63 redesign(foundation): fix Tag/Pill type collisions, document ModeProvider`
- Recent commit chain: `7c391dc` (6.2c) → `5aa9b38` (NodeInspector keys fix) → `b4d0d92` (replication playbook) → `b464c63` (foundation pass)
- Tests: 30/30 vitest pass (13 Chart + 17 OrderBook/OrderEntry/etc.)
- `tsc --noEmit`: redesign code is clean. Pre-existing errors only in legacy main-branch components (`components/backtest/EquityCurveChart.tsx` recharts formatter, `components/data-display/List.tsx` onCopy ref-type, `components/decisions/`, `components/performance/`, `components/strategies/`). All logged in `docs/TECH-DEBT-REGISTRY.md` and not used by any redesign route.
- `next build`: legacy `EquityCurveChart.tsx` still blocks. Tag/Pill collision is GONE — that was the one with the redesign blast radius. `next dev` works fine for everything.
- Full stack is currently running (`bash run_all.sh --local-frontend` from the redesign root). Frontend on http://localhost:3001, backend on :8080–8096. Stop with `bash run_all.sh --stop` from the redesign root before next session if you don't want it persisting.

---

## What shipped this session

**6.2c — Backtests compare + Chart primitive (commit `7c391dc`)**
- `components/data-display/Chart.tsx` — line/area/bar XY chart, hand-rolled SVG (no d3/recharts), tokens-only stroke and fill, crosshair tooltip + keyboard nav (←→/Home/End/Esc), ResizeObserver responsive width, min/max bucket downsample, sr-only `tableFallback`. 13 vitest tests.
- `app/backtests/[run_id]/page.tsx` — `EquityCurveSection` retrofitted to use Chart (line+area, baseline=min). "Chart pending" tag dropped; replaced with narrower "Per-tick timestamps pending" tag tied to the actual remaining backend gap.
- `app/backtests/compare/page.tsx` — new surface with breadcrumb + removable run pills + "Add run", underfilled empty state for <2 runs, ComparisonHeadline with Δ vs baseline (pp/raw/int delta modes), EquityComparisonSection overlays runs on a normalized 0–100% relative x-axis, SharedTradesSection keyed on `entry_time + direction` with mixed-timeframes caveat banner.

**Catalog bug fix (commit `5aa9b38`)**
- `app/design-system/page.tsx:1367` — duplicate `regime` output ids in NodeInspector demo data renamed to `regime-to-strategy` and `regime-to-debate`. React duplicate-key warning gone.

**Replication playbook (commit `b4d0d92`)**
- `docs/design/REPLICATION-PLAYBOOK.md` — 13-section, ~500-line how-to for replicating this design-system style in a different repo or for a different aesthetic. Mental model, repo layout, six-phase build (foundation → tokens → specs → components → catalog → surfaces), inline templates (component spec, ADR, surface spec, component scaffold, catalog Section/Row), re-skin protocol, pitfalls, §13 minimum-viable replication checklist.

**Foundation gap pass (commit `b464c63`)**
- `components/primitives/Tag.tsx` — CVA variant `style` → `appearance`. Reserved-attribute-name guidance now lives in the playbook §6.2.
- `app/design-system/page.tsx` — 8 Tag callsites updated; `Record<string, unknown>` cast routed through `unknown` first.
- `components/data-display/Pill.tsx` — `Omit<..., "color" | "children">` on each variant interface to fix the children collision.
- `components/providers/ModeProvider.tsx` — docstring added noting the known SSR-flash limitation (non-HOT routes paint once with HOT tokens before the effect runs); proper fix is route-aware SSR via middleware, deferred until a flash regression is observed.
- `docs/TECH-DEBT-REGISTRY.md` — Tag/Pill row marked RESOLVED; legacy `EquityCurveChart.tsx` recharts formatter logged as separate LOW item.

---

## What's next, in priority order

### 1. **DECIDE first: PriceChart timing** (shapes 6.3 vs 6.5)

PriceChart is deferred per `chart.md`'s explicit out-of-scope note ("OHLC needs gap rules, wicks, live-tick flash; abstractions diverge from Chart"). It blocks 6.5 (Hot Trading) but not 6.3 (Pipeline Canvas) or 6.4 (Agent Observatory).

| Option | Cost | Trade-off |
|---|---|---|
| **(A)** Skip PriceChart entirely until 6.5; do 6.3 → 6.4 first | low | Maintains the inverse-time-spent build order. PriceChart can be its own focused session right before 6.5, informed by what 6.5 actually needs. **Recommended.** |
| **(B)** Spec PriceChart now (no implementation); 6.3 next | medium | Forces a design conversation about candles/wicks/flash without a forcing surface yet. Risk: spec drifts before 6.5 reality forces the question. |
| **(C)** Spec + implement PriceChart before 6.3 | high | Backend Hot Trading would have its primary visual ready when its session lands, but the primitive's API gets stress-tested by its first integration — the pattern that worked for Chart suggests "primitive in its own session, validated by retrofit." |

**Recommendation: (A).** The Chart precedent is "spec the primitive when a real surface forces it; one session for the primitive; one session for retrofit." 6.3 doesn't need PriceChart, so just go.

### 2. **6.3 — Pipeline Canvas at `/canvas` (and `/canvas/{profile_id}`)**

Surface spec: `docs/design/05-surface-specs/03-pipeline-canvas.md`.

Components already exist per Phase 5:
- `components/canvas/Node.tsx`, `Edge.tsx`, `MiniMap.tsx`, `NodeInspector.tsx`, `NodePalette.tsx`, `RunControlBar.tsx`
- `@xyflow/react` is in dependencies — wire it up

Backend wiring per CLAUDE.md §2C "Profile config model":
- `trading_profiles.pipeline_config` (the canvas) is authoritative
- Save the canvas via `PUT /agent-config/{profile_id}/pipeline` — atomic with `strategy_rules` (compiled from canvas's `strategy_eval` node config via `libs/core/pipeline_compiler.py`)
- Load: `GET /agent-config/{profile_id}/pipeline` (or whatever the GET pair is — verify in `services/api_gateway/`)

Surface spec sections to render:
- Header: profile name, mode (`data-mode="cool"` per ModeProvider), run-status pill, `[run]` `[stop]` `[deploy]` chrome
- Canvas (xyflow viewport): nodes + edges, drag-to-reposition, drag-to-connect
- Left rail: NodePalette (categorized by node-kind: agent / data-source / strategy_eval / sink)
- Right drawer: NodeInspector (open on node-click; collapsible sections; primitive form controls)
- Bottom dock: RunControlBar (live progress + log tail)
- MiniMap: bottom-right floating

Backend gaps likely (verify per service):
- Per-node live activity (token counter, latency, error rate) — if `services/{agent}` doesn't emit it, surface as Pending tags
- Canvas snapshot per backtest run — already known gap (see 6.2b note); leave Pending until backend lands
- Real-time `/canvas` WebSocket for live node states — verify what `services/api_gateway/` exposes

Compose ONLY existing components. If a canvas-tier component is missing or short, STOP and update the component spec first (don't extend inline).

### 3. **6.4 — Agent Observatory at `/agents` (and `/agents/{run_id}`)**

After 6.3. First surface where `components/agentic/` (AgentTrace, ReasoningStream, DebatePanel, AgentSummaryPanel) meets real WebSocket data. Streaming reliability is the new variable here.

Surface spec: `docs/design/05-surface-specs/02-agent-observatory.md`.

### 4. **PriceChart primitive** (if option A — defer until 6.5)

Spec then implement, in that order. Spec lives at `docs/design/04-component-specs/price-chart.md` (extend `04-component-specs/README.md` index when written). Per `trading-specific.md`, this is its own component because OHLC has gap rules, wicks, live-tick flash, volume sub-pane, range selection at the millisecond grain — abstractions diverge from Chart. Phase 6.5 will reveal whether to build on top of TradingView Lightweight Charts (already in dependencies as `lightweight-charts`) or hand-roll like Chart.

---

## Things to be aware of

- **Per-page `data-mode` overrides remain valid.** ModeProvider sets `<html data-mode="..."/>` from the route. The redesign pages still set `data-mode="cool"` on their root divs. That's intentional — the spec calls for sectional overrides (e.g., a CALM modal inside a COOL surface). Don't strip them opportunistically.
- **The SSR mode flash is real but deferred.** Non-HOT routes paint once with HOT tokens before the client effect runs and swaps. The fix is middleware-based route-aware SSR. Defer until a user actually flags the flicker; if 6.3/6.4/6.5 all build cleanly under it, leave alone.
- **Backend reality drift is the steady state.** Continue the "render the spec'd structure, surface unwired bits as Pending tags with one-line reasons, never fake" pattern. It's worked for 6.1, 6.2a, 6.2b, 6.2c — four surfaces in a row.
- **Full stack is currently running.** If you're picking up cold, either reuse it (browser at http://localhost:3001) or stop with `bash run_all.sh --stop` from the redesign root. Backend Poetry env was installed this session, so `run_all.sh --local-frontend` works without re-prep.
- **Legacy main-branch UI errors don't block redesign work.** They're tracked in `TECH-DEBT-REGISTRY.md` and will be deleted at Phase 9 cutover. Don't fix opportunistically.
- **Catalog page works again.** http://localhost:3001/design-system renders; Tag rendering uses the new `appearance` prop. Add a Section for `Chart` next time the catalog gets touched (it's currently uncatalogued — `Sparkline` and `DepthChart` are there but Chart isn't).
- **The `TECH-DEBT-REGISTRY.md` file is open in the IDE** as of session end. The user reviewed it on wrap-up.

---

## Suggested next-session prompt

> Continue Phase 6 of the redesign. 6.2c (compare + Chart) and the foundation pass are at commit `b464c63`. Read `docs/design/HANDOFF-6.3-START.md` before anything else.
>
> Today's task: 6.3 — Pipeline Canvas at `/canvas` and `/canvas/{profile_id}`.
>
> Decide PriceChart timing (handoff §1) before starting. If you pick (A), proceed with 6.3 as planned — PriceChart isn't needed. If (B) or (C), confirm scope first.
>
> Compose ONLY existing canvas-tier components. Wire `@xyflow/react` into the viewport. Backend gaps → Pending tags. After landing, commit + push as `redesign(6.3): pipeline canvas`.

---

## Phase 6 progress

- [x] 6.1 Profiles & Settings
- [x] 6.2a Backtests list + new-run modal
- [x] 6.2b Backtests run detail
- [x] 6.2c Backtests compare + Chart primitive
- [x] Foundation pass — Tag/Pill type collisions resolved, ModeProvider documented
- [ ] 6.3 Pipeline Canvas
- [ ] 6.4 Agent Observatory
- [ ] PriceChart primitive (deferred until 6.5 forces it)
- [ ] 6.5 Hot Trading
- [ ] 6.6 Risk Control

Per `docs/design/11-redesign-execution-plan.md` §6.1, build order is intentionally inverse to user-time-spent — easiest surfaces first to harden the foundation.

---

## Other artifacts to know about

- **REPLICATION-PLAYBOOK.md** (`docs/design/`) — how to rebuild this design-system style for a different repo / aesthetic. §13 has the weekend-scoped minimum-viable checklist. Reference for any future re-skin work.
- **TECH-DEBT-REGISTRY.md** (`docs/`) — append-only log. Tag/Pill row marked RESOLVED this session; legacy EquityCurveChart logged as separate LOW item.
- **This handoff** supersedes `HANDOFF-6.2-CONTINUATION.md` (which described 6.2c as the next task, now done).
