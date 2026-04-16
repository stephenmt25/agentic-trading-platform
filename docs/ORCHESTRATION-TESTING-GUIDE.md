# Agent Orchestration Platform — User Flow Testing Guide

Covers all 3 phases of the platform pivot: Analysis, Performance, and Pipeline.

---

## Prerequisites (all phases)

1. **Docker Desktop running** (Redis + TimescaleDB)
2. **Start backend**: `bash run_all.sh`
3. **Start frontend** (separate terminal): `cd frontend && npm run dev`
4. **Sign in** at `http://localhost:3000/login`
5. **Wait 5+ minutes** after first boot for agents to produce scores

---

## Phase 1: Analysis (`/analysis`)

TradingView-style candlestick charting with agent score overlays.

### P1-1: Navigation
- [ ] Sidebar shows "Analysis" after "Agent View"
- [ ] Clicking navigates to `/analysis`
- [ ] No console errors on load

### P1-2: Candlestick Chart
- [ ] Green/red candles render for BTC/USDT
- [ ] Volume histogram (faded bars) at chart bottom
- [ ] Crosshair follows mouse
- [ ] Chart resizes with browser window
- [ ] Right-side price scale shows values
- [ ] Bottom time scale shows timestamps

**If empty**: Ingestion service needs to write candles. Wait 1-2 minutes after boot, refresh.

### P1-3: Timeframe Switching
- [ ] Click 1m — chart reloads with 1-minute candles
- [ ] Click 5m, 15m, 1H — each loads different granularity
- [ ] Active button highlighted blue
- [ ] Brief loading spinner during fetch

### P1-4: Symbol Switching
- [ ] Click "ETH" — chart reloads with ETH/USDT
- [ ] Click "BTC" — back to BTC/USDT
- [ ] Active button highlighted blue

### P1-5: Agent Score Overlay
- [ ] Panel below chart labeled "Agent Scores"
- [ ] TA line (blue) visible, oscillating between -1 and +1
- [ ] Dashed zero reference line
- [ ] Tooltip on hover shows score values per agent

**If empty**: Wait 5+ minutes for agents to accumulate scores. TA writes every 60s, others every 5 minutes.

### P1-6: Overlay Toggles
- [ ] Click "TA" toggle — TA line disappears
- [ ] Click "TA" again — line reappears
- [ ] Each overlay (TA, Sent, Debate, Regime) toggles independently
- [ ] "Trades" and "Regime" toggles exist (visual only for now)

### P1-7: Agent Weights Summary
- [ ] Card below chart shows TA, Sentiment, Debate columns
- [ ] Each shows: current weight, sample count, EWMA bar, delta from default
- [ ] Delta green for positive, red for negative

**If blank**: Confirm the API gateway was restarted with the latest code (field name fix for `ewma_accuracy`).

### P1-8: Auto-Refresh
- [ ] Leave page open 60+ seconds
- [ ] New candle data appears on chart edge
- [ ] No errors or flickering

---

## Phase 2: Performance (`/performance`)

Agent accuracy tracking, gate analytics, weight evolution, trade attribution.

### P2-1: Navigation
- [ ] Sidebar shows "Performance" after "Analysis"
- [ ] Clicking navigates to `/performance`
- [ ] No console errors

### P2-2: Agent Accuracy Table
- [ ] Table with 3 rows: TA, Sentiment, Debate
- [ ] Columns: EWMA Accuracy %, Samples, Current Weight, Default, Delta, accuracy bar
- [ ] Colored dots per agent (blue/violet/amber)
- [ ] Delta green positive, red negative, grey zero
- [ ] Accuracy bar fills proportionally

### P2-3: Symbol Switching
- [ ] Click "ETH" — all panels reload for ETH/USDT
- [ ] Click "BTC" — back to BTC/USDT

### P2-4: Decision Outcomes (Gate Block Analytics)
- [ ] Horizontal bar chart showing APPROVED, BLOCKED_ABSTENTION, etc.
- [ ] Color-coded bars per outcome type
- [ ] Total decisions count in header
- [ ] Gate pass-rate mini-bars below chart

**If empty**: No trade decisions recorded yet. Hot-path needs to process market ticks.

### P2-5: Weight Evolution Chart
- [ ] Line chart with TA (blue), Sentiment (purple), Debate (amber)
- [ ] Legend shows agent names
- [ ] Tooltip shows weight values on hover
- [ ] Lines evolve over time as Analyst recomputes

**If empty**: Analyst writes weight history every 5 minutes. Wait 5+ minutes.

### P2-6: Trade Attribution Table
- [ ] Table shows: Time, Price, Conf Before, Conf After, TA/Sent/Debate adjustments
- [ ] Adjustments green (positive) or red (negative)
- [ ] "Showing 20 of N" footer if >20 trades

**If empty**: No trades approved yet.

### P2-7: Auto-Refresh
- [ ] Data refreshes every 60 seconds without errors

---

## Phase 3: Pipeline (`/pipeline`)

n8n-style DAG editor for the 9-gate pipeline with agent nodes.

### P3-1: Navigation
- [ ] Sidebar shows "Pipeline" after "Performance"
- [ ] Clicking navigates to `/pipeline`
- [ ] No console errors

### P3-2: Pipeline Canvas
- [ ] React Flow canvas renders with dark background and dot grid
- [ ] Default pipeline loads: 16 nodes connected by edges
- [ ] Animated edges (flowing particles on connections)
- [ ] Minimap in bottom-right corner
- [ ] Zoom/pan controls in bottom-left

### P3-3: Node Types
- [ ] **Green "Market Tick"** node on the left (input)
- [ ] **Blue gate nodes** in a horizontal chain: Strategy Eval → Abstention → Regime Dampener → Agent Modifier → Circuit Breaker → Blacklist → Risk Gate → HITL → Validation
- [ ] **Purple/amber agent nodes** above the chain: TA Agent, Sentiment, Debate, Regime HMM
- [ ] **Green "Order Approved"** node on the right (output)
- [ ] **Exit Monitor** node connected from Risk Gate

### P3-4: Node Interaction
- [ ] Click a node — it highlights with blue border
- [ ] Config drawer slides in from the right
- [ ] Drawer shows node name, type, and configurable parameters
- [ ] For agent nodes (TA, Sentiment, etc.): sliders for interval, threshold, TTL
- [ ] For gate nodes: shows config keys if applicable
- [ ] Click canvas background — drawer closes

### P3-5: Parameter Tuning
- [ ] Select TA Agent node → drawer shows timeframe_weights, candle_limit, score_ttl_s
- [ ] Drag the `candle_limit` slider — value updates in real-time
- [ ] "Unsaved" badge appears in toolbar
- [ ] Select Regime HMM → confidence_threshold slider (0.1–1.0)
- [ ] Select Sentiment → llm_backend dropdown (cloud/local/auto)

### P3-6: Drag & Drop
- [ ] Drag any node — it moves on the canvas
- [ ] Connected edges follow the node
- [ ] "Unsaved" badge appears after moving

### P3-7: Profile Selector
- [ ] Dropdown in toolbar shows available profiles
- [ ] Switching profiles reloads the pipeline config
- [ ] Each profile can have its own custom pipeline

### P3-8: Save & Reset
- [ ] Click "Save" — pipeline config persists to database
- [ ] Success toast appears
- [ ] "Unsaved" badge disappears
- [ ] Click "Reset" — pipeline reverts to default layout
- [ ] Success toast: "Pipeline reset to default"

### P3-9: Edge Connections
- [ ] Drag from a node's output handle to another node's input handle
- [ ] New edge appears connecting them
- [ ] "Unsaved" badge appears

### P3-10: Fit View
- [ ] Pipeline auto-fits to canvas on load
- [ ] Use scroll wheel to zoom in/out
- [ ] Use Controls panel (bottom-left) for zoom reset

---

## Cross-Phase Checks

### Sidebar Order
- [ ] Dashboard → Agent View → Analysis → Performance → Pipeline → Profiles → Backtest → Paper Trading → Docs

### Auto-Refresh
- [ ] All 3 new pages auto-refresh every 60 seconds
- [ ] No memory leaks (check browser DevTools → Performance → Memory)

### Error Recovery
- [ ] Stop backend → pages show error states (not blank crashes)
- [ ] Restart backend → pages recover on next refresh cycle

### Mobile Responsive
- [ ] Resize browser to mobile width
- [ ] Analysis: chart shrinks, controls wrap
- [ ] Performance: cards stack vertically
- [ ] Pipeline: canvas still functional (pinch-zoom on touch)
