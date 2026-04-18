# Praxis Agent Orchestration Platform — User Flow Testing Guide

Comprehensive testing guide for the consolidated 5-page application.

---

## Prerequisites

1. **Docker Desktop running** (Redis + TimescaleDB)
2. **Start backend**: `bash run_all.sh`
3. **Start frontend** (separate terminal): `cd frontend && npm run dev`
4. **Sign in** at `http://localhost:3000/login`
5. **Wait 5+ minutes** after first boot for agents to produce scores

---

## 1. Dashboard (`/`)

### 1.1 Page Load
- [ ] Page renders with title "Dashboard"
- [ ] Sidebar shows 6 items: Dashboard, Monitor, Analytics, Configure, Simulate, Docs
- [ ] Settings link at bottom of sidebar

### 1.2 Total Portfolio P&L
- [ ] Section header with (i) tooltip icon visible
- [ ] Hover (i) → tooltip shows "Aggregate post-tax P&L across all active profiles..."
- [ ] Tooltip renders above the section, not clipped by sidebar
- [ ] P&L value displays ($0.00 if no trades)
- [ ] Invested, Gross P&L, Trading Fees, Tax Est. metrics below

### 1.3 Active Agent Bounds
- [ ] Section header with (i) tooltip icon
- [ ] Profile cards show name + RUNNING/DORMANT badge
- [ ] Click a profile card → navigates to Configure > Profiles

### 1.4 ML Agent Scores
- [ ] Section header with (i) tooltip icon
- [ ] BTC/USDT and ETH/USDT rows with TA Score, Sentiment, Source
- [ ] Regime badge (CRISIS/TRENDING_UP/etc.)
- [ ] Auto-refresh indicator with timestamp

### 1.5 Risk Monitor
- [ ] Section header with (i) tooltip icon
- [ ] Per-profile risk cards: Daily P&L vs Breaker, Drawdown, Allocation
- [ ] Circuit Breaker badge if triggered (red border)

---

## 2. Monitor (`/monitor`)

### 2.1 Welcome Guide (no agent selected)
- [ ] Center panel shows "Agent Monitor" heading
- [ ] 4 guide cards with colored icons:
  - ← Agent Registry (green arrow)
  - Agent Detail (blue, highlighted border)
  - → Message Flow (amber arrow)
  - ↓ Quick Stats (violet arrow)
- [ ] Each card has description text

### 2.2 Agent Registry (left panel)
- [ ] "AGENTS" header with (i) tooltip icon
- [ ] Agents grouped: Orchestration, Data, Scoring, Risk, Execution, Portfolio, Intelligence
- [ ] Green dots = healthy, message counts and timestamps shown
- [ ] Click an agent → center panel shows detail

### 2.3 Agent Detail (center panel)
- [ ] Shows agent name, type badge, data source indicator
- [ ] Three sections: Input Stream, Decision State, Output Stream
- [ ] Real-time event data flowing

### 2.4 Message Flow (right panel)
- [ ] "Message Flow" header with (i) tooltip icon and count badge
- [ ] Filter dropdowns: All agents, All event types
- [ ] Search box for messages
- [ ] Real-time message entries with timestamps

### 2.5 Quick Stats Bar (bottom)
- [ ] Orders, Fills, Win Rate, Net PnL, Drawdown, Positions, Pending
- [ ] Values update in real-time

### 2.6 System Status Bar (top)
- [ ] Mode badge (PAPER/LIVE)
- [ ] Agent count "11 / 11 healthy"
- [ ] UTC + Local timestamps
- [ ] Throughput (msgs/sec)
- [ ] Slow Mode toggle

---

## 3. Analytics (`/analytics`)

### 3.1 Tab Navigation
- [ ] Two tabs: "Charts" and "Performance"
- [ ] Active tab has blue underline
- [ ] URL updates: `?tab=charts` or `?tab=performance`
- [ ] Switching tabs preserves sidebar active state

### 3.2 Charts Tab
- [ ] Candlestick chart with green/red candles
- [ ] Volume histogram at chart bottom
- [ ] Crosshair on mouse hover
- [ ] BTC/ETH symbol selector — switches chart data
- [ ] 1m/5m/15m/1H timeframe selector — chart reloads
- [ ] Overlay toggles: TA, Sent, Debate, Regime, Trades, Regime
- [ ] Agent Scores panel with (i) tooltip
- [ ] TA line (blue) visible in score overlay
- [ ] Current Agent Weights card with (i) tooltip
- [ ] Weight values, samples, EWMA %, delta from default

### 3.3 Performance Tab
- [ ] Agent Accuracy & Weights table with (i) tooltip
- [ ] 3 agent rows: TA, Sentiment, Debate
- [ ] EWMA Accuracy, Samples, Current/Default Weight, Delta, accuracy bar
- [ ] Decision Outcomes chart with (i) tooltip — horizontal bar
- [ ] Weight Evolution chart with (i) tooltip — line chart over time
- [ ] Trade Attribution table with (i) tooltip — per-trade agent adjustments
- [ ] BTC/ETH symbol switcher

---

## 4. Configure (`/configure`)

### 4.1 Tab Navigation
- [ ] Two tabs: "Profiles" and "Pipeline"
- [ ] URL updates with `?tab=profiles` or `?tab=pipeline`

### 4.2 Profiles Tab
- [ ] Left panel: searchable profile list
- [ ] Profile status badges (Running/Dormant/Deleted)
- [ ] "2 active" count + "New Profile" button
- [ ] Right panel: JSON rule editor for selected profile
- [ ] Delete, Deactivate, Save buttons
- [ ] Create new profile → modal with name + allocation %

### 4.3 Pipeline Tab
- [ ] React Flow canvas with dark background + dot grid
- [ ] 16 nodes: Market Tick → 9 gates → Order Approved + 4 agents + Exit Monitor
- [ ] Animated dashed edges connecting nodes
- [ ] Minimap in bottom-right
- [ ] Zoom controls in bottom-left
- [ ] Profile selector dropdown in toolbar
- [ ] "Unsaved" badge when changes made
- [ ] Click a node → config drawer opens on right
- [ ] TA Agent: timeframe_weights array, candle_limit slider, score_ttl_s slider
- [ ] Sentiment: score_interval_s, llm_backend, score_ttl_s
- [ ] Drag nodes → they move, edges follow
- [ ] Save button → persists config
- [ ] Reset button → reverts to default layout

---

## 5. Simulate (`/simulate`)

### 5.1 Tab Navigation
- [ ] Three tabs: "Backtest", "Paper Trading", "Approval"
- [ ] URL updates with `?tab=backtest`, `?tab=paper-trading`, `?tab=approval`

### 5.2 Backtest Tab
- [ ] Configuration form: Symbol, Start/End Date, Slippage %, Strategy Rules (JSON)
- [ ] "Run Backtest" button
- [ ] Right side: "Configure and run a backtest to see results"
- [ ] After running: Metrics cards (Trades, Win Rate, Sharpe, etc.)
- [ ] Equity curve chart
- [ ] Trades table with entry/exit details

### 5.3 Paper Trading Tab
- [ ] Status bar: PAPER badge, ENABLED status, Operational indicator, Stop button
- [ ] Net P&L hero number (large, red if negative)
- [ ] Metrics: Gross P&L, Total Trades, Win Rate, Max Drawdown
- [ ] 30-Day Safety Period progress bar (X / 30 days)
- [ ] Metric cards: Trades, Win Rate, Drawdown, Sharpe
- [ ] Daily P&L sparkline chart
- [ ] Expandable daily reports
- [ ] Decision feed with (i) tooltip (scrolled into view below)

### 5.4 Approval Tab
- [ ] "Trade Approvals" heading
- [ ] Empty state: "No pending approvals" with description
- [ ] When HITL triggers: request cards with Approve/Reject buttons

---

## 6. InfoTooltip System

### 6.1 Rendering
- [ ] (i) icons visible next to all section headers (14 total across app)
- [ ] Tooltips render via portal (not clipped by any container)
- [ ] z-index 9999 — always above all other elements

### 6.2 Positioning
- [ ] Near left edge → tooltip aligns left (not behind sidebar)
- [ ] Near right edge → tooltip aligns right
- [ ] Center of page → tooltip centered on icon
- [ ] Near top → tooltip renders below
- [ ] Near bottom → tooltip renders above

### 6.3 Interaction
- [ ] Hover icon → 200ms delay → tooltip appears
- [ ] Move mouse away → 100ms delay → tooltip disappears
- [ ] Hover onto tooltip content → stays visible (prevents flicker)
- [ ] Focus via keyboard (Tab) → tooltip appears
- [ ] Blur → tooltip disappears

### 6.4 Content
- [ ] All tooltips use text-xs, IBM Plex Sans, design system popover colors
- [ ] Width: 360px (or 90vw on mobile)
- [ ] Text is contextual and actionable (not generic)

---

## 7. Cross-Page Checks

### 7.1 Navigation
- [ ] Sidebar: Dashboard → Monitor → Analytics → Configure → Simulate → Docs
- [ ] Active page highlighted with blue left border
- [ ] Settings at bottom of sidebar
- [ ] All tab URLs are bookmarkable (`/analytics?tab=performance`)

### 7.2 Connection Status
- [ ] "LIVE" indicator (green dot) when backend connected
- [ ] "BACKEND OFFLINE" banner when backend unreachable
- [ ] Auto-reconnect on backend restart

### 7.3 Responsive
- [ ] Resize browser to mobile → sidebar collapses, hamburger appears
- [ ] Tab bars remain functional on narrow screens
- [ ] Charts resize responsively

### 7.4 Error States
- [ ] Stop backend → pages show error/loading states (not blank crashes)
- [ ] No unhandled JavaScript errors in console across all pages
