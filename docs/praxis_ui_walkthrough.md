# Praxis Trading Platform UI Walkthrough
**Partner Brief**

This document walks through the current state of the Praxis dashboard, section by section, using screenshots from `scrnshts/` and the React components that render them. Every behavior described below is grounded in source code file paths and line ranges are listed under each section.

**Scope tags used throughout the dashboard:**
* **PROFILE** - the panel reflects the active profile selected in the picker.
* **SYSTEM** - the panel reflects the engine as a whole, ignoring the profile picker.
* **SYMBOL** - the panel reflects whichever chart symbol (BTC/USDT, ETH/USDT) is selected.

## Contents
1. Landing page (root redirect)
2. Trade dashboard - top section (Engine totals, Risk monitor, Approvals, Daily P&L)
3. Trade dashboard - Live Activity (Decision feed + Price/agent overlays)
4. Decision Feed - expanded row (full decision trace + chart pinning)
5. Trade dashboard - Open positions
6. Daily transparency report (drawer, summary view)
7. Daily transparency report (drawer, expanded trade lineage)
8. Performance review drawer (gate analytics, weight evolution, closed trades)
9. Strategies - Templates tab
10. Strategies - Verify tab (backtest)

---

## 1. Landing page
**Screenshot file:** `landing_page.png`

There is no standalone landing page; the root route redirects straight to `/trade`. The screenshot shows the Trade dashboard as it appears on first load, with the left-rail nav (Trade, Strategies, Agents, Docs) and the Praxis logo in the top-left. Trade is highlighted because that is the default destination.

**What the screenshot is showing:**
* Praxis branding and global nav are rendered by the root layout. The page user lands on is always Trade.
* Top-right shows a connection indicator (LIVE), notification bell, and avatar - identical chrome on every page.
* Below the header you can see panels that are detailed in sections 2-4: Engine totals strip, Risk monitor / Approvals row, Daily P&L card on the right, Live activity strip beneath.

**Source of truth (code):**
* `frontend/app/page.tsx:1-5` // redirect('/trade')
* `frontend/app/layout.tsx` // global chrome (logo, side nav, LIVE badge)
* `frontend/app/trade/page.tsx:343-394` // Trade page header that the user lands on

---

## 2. Trade dashboard - top section
**Screenshot file:** `trade_dashboard_top_section.png`

This is the top half of the Trade dashboard. It is composed of four panels: Engine totals, Risk monitor, Approvals, and Daily P&L. Each panel is tagged with a scope chip (PROFILE/SYSTEM/SYMBOL) so the operator always knows whether they are looking at one profile or the engine as a whole. The header shows a PAPER mode badge, an updated-Ns-ago timestamp with a refresh button, and a Kill Switch control.

**What the screenshot is showing:**
* **Mode badge:** PAPER/TESTNET/LIVE, color-coded amber/blue/emerald. Driven by `api.paperTrading.mode()`.
* **Kill Switch:** toggles the global KillSwitch Redis key. When ACTIVE the button turns red and a system-state warning chip appears under the header.
* **Engine totals (SYSTEM):** Net P&L, Gross P&L, Trades, Win rate, Max DD, Sharpe - aggregate across all profiles since boot. In the screenshot: +$535.86 net, 52 trades, 57.0% win, 1.7% MaxDD.
* **Risk monitor (SYSTEM):** per active profile, shows Daily P&L vs the circuit-breaker limit, current drawdown, and allocation used. Two profiles are visible: Demo Pullback Long with 2.01% drawdown and Oversold Uptrend at 0%.
* **Approvals (SYSTEM):** trades held by the HITL gate awaiting human decision. Empty state shown ("No pending approvals").
* **Daily P&L (SYSTEM):** right-side card with a date picker and a Create Report button. Below is a sparkline of net P&L by day and a scrollable list of past reports. Clicking a row opens the Daily Transparency Report drawer (section 5).
* **Live status** auto-refreshes every 30s (POLL_INTERVAL = 30_000) and can be force-refreshed via the round-arrow button.

**Source of truth (code):**
* `frontend/app/trade/page.tsx:35-50` // ModeBadge
* `frontend/app/trade/page.tsx:52-78` // KillSwitchControl toggle handler at 314-328
* `frontend/app/trade/page.tsx:402-438` // Engine totals strip (StatCells)
* `frontend/app/trade/page.tsx:444-456` // Risk monitor section wrapper
* `frontend/components/risk/RiskMonitorCard.tsx:26-72` // Risk Monitor data fetch 10s polling
* `frontend/app/trade/page.tsx:458-468` // Approvals panel (ApprovalQueue dynamic import)
* `frontend/app/trade/page.tsx:472-536` // Daily P&L card: sparkline, date picker, Create Report
* `frontend/app/trade/page.tsx:279-312` // handleGenerateReport opens drawer on success

---

## 3. Trade dashboard - Live Activity
**Screenshot file:** `trade_dashboard_middle_live_activity_section.png`

The middle band of the Trade dashboard, titled Live activity. Two side-by-side panels show what the engine is doing right now: a Decision Feed on the left (PROFILE-scoped) and a Price Agent overlays chart on the right (SYMBOL-scoped). Above them is the profile picker (currently set to Demo Pullback Long) and a button that opens the Performance review drawer.

**What the screenshot is showing:**
* **Profile picker:** scopes per-profile panels. Risk monitor and Engine totals deliberately ignore it - both are system views.
* **Decision Feed:** a live, polling list of trade decisions for the selected profile. Refreshes every 15s. Each row can be expanded to show the full agent/gate / regime trace. The screenshot shows a stream of recent rows.
* **Price Agent overlays:** candlestick chart (TradingView-style) for the selected symbol with agent score overlays toggleable along the top. Below the price chart is a panel of agent contribution scores, with the current agent weights visible in the strip at the bottom.
* **Performance review button** opens a right-side drawer scoped to the active profile (section 7).

**Source of truth (code):**
* `frontend/app/trade/page.tsx:540-577` // Live activity header + profile picker + Performance review button
* `frontend/app/trade/page.tsx:580-589` // Decision Feed panel wrapper
* `frontend/components/decisions/DecisionFeed.tsx:1-40` // 15s polling, filter chips (all/approved/blocked), expandable rows
* `frontend/app/trade/page.tsx:591-604` // Price Agent overlays panel wrapper
* `frontend/app/analytics/AnalysisContent.tsx:34-80` // Candles agent scores weights, refreshes every 60s

---

## 4. Decision Feed - expanded row
**Screenshot file:** `trade_dashboard_live_activity_decision_feed_expanded.png`

Drilling into the Decision Feed: any row can be clicked to expand the full decision trace in place. The screenshot shows an APPROVED ETH/USDT BUY at 08:27 PM with confidence 0.71. Notice the same decision is also marked on the right-side price chart with a green APPROVED arrow - that's the pin-to-chart feature: clicking the pin icon next to a decision row anchors that exact moment on the candle chart and the agent-score chart, so price action and the trace can be read together.

**What the screenshot is showing:**
* **Row header:** status dot (emerald = APPROVED, slate = BLOCKED), symbol, direction (BUY/SELL color-coded), timestamp (HH:MM:SS for today, MMM d HH:MM otherwise), live confidence, outcome chip, pin icon, expand chevron.
* **One-line summary** (under the header, when collapsed): for APPROVED rows this is TA: adj Sent:±adj Dbt:±adj; for BLOCKED rows it is the failing gate name + reason.
* **Market context - 1m:** a lightweight-charts mini candle chart spanning ±15 minutes around the decision, with an APPROVED/BLOCKED arrow marker placed at the exact decision second (above-bar for SELL, below-bar for BUY). Falls back to a graceful "no candles for this window" state if the API has no data.
* **Indicators:** RSI (color-graded green <30/ red >70), MACD histogram, ATR, ADX, BB%B, OBV, Choppiness - the snapshot the strategy evaluated against.
* **Strategy (AND/OR) - BUY/SELL conf 0.65:** every condition rendered as a row with the operator (LT/GT), threshold, actual value, and a pass/fail check. The screenshot shows two AND-conditions: rsi LT 50 | 47.6121 and macd_histogram GT 0 | 166.9246.
* **Regime:** rule-based regime, HMM regime, and the resolved confidence multiplier (Mult: 1x).
* **Agent Influence:** header summarises confidence-before confidence-after with a percentage delta colored green/red. Per-agent rows show name, score, weight, signed adjustment, and a horizontal bar whose width is min(adjustment *500, 100)%. In the screenshot: confidence moved 0.650 → 0.707 (+8.8%).
* **Gates:** pass/fail row per gate (regime, blacklist, abstention, circuit_breaker, validation, hitl, risk) with reason text. Risk gate rows additionally show qty and alloc when the gate computed them.
* **Filter pills** at the top-right of the panel (ALL/APPROVED/ BLOCKED) scope the feed without re-fetching profile state.

**Source of truth (code):**
* `frontend/components/decisions/DecisionFeed.tsx:69-92` // Decision Trace header filter pills (all/approved/blocked)
* `frontend/components/decisions/DecisionFeed.tsx:113-200` // row rendering, summary builder, pin-to-chart icon
* `frontend/components/decisions/DecisionFeed.tsx:54-67` // togglePin() writes pinnedDecision into the analysis store
* `frontend/components/decisions/DecisionFeed.tsx:202-207` // in-place expansion (DecisionDetail mount)
* `frontend/components/decisions/DecisionDetail.tsx:200-298` // expanded trace: chart, indicators, strategy, regime, agents, gates
* `frontend/components/decisions/DecisionDetail.tsx:84-192` // DecisionContext Chart 1m candles + APPROVED/BLOCKED marker
* `frontend/components/decisions/DecisionDetail.tsx:44-59` // ConditionRow threshold vs actual_value with pass/fail
* `frontend/components/decisions/DecisionDetail.tsx:61-80` // AgentRow score / weight / adjustment + bar
* `frontend/components/decisions/DecisionDetail.tsx:19-42` // GateRow reason suggested_qty / alloc

---

## 5. Trade dashboard - Open positions
**Screenshot file:** `trade_dashboard_open_positions_panel.png`

The lower-third Open positions panel (PROFILE-scoped). It tabulates all currently open positions for the selected profile, refreshing every 15 seconds. The screenshot shows three open ETH/USDT longs, all approximately 4.8 hours old, with a combined unrealized P&L of -$180.53.

**What the screenshot is showing:**
* **Columns:** Symbol, Side (long/short with up/down arrow), Qty, Entry, Unrealized $, Unrealized %, Age. Negative unrealized values render in red, positive in emerald.
* **Polling interval** is 15_000ms positions are kept fresh without flooding the API.
* When the list is empty, the panel shows operator guidance: positions only appear when an APPROVED signal becomes a fill, and most signals are filtered upstream by abstention / circuit-breaker gates.
* **Total unrealized footer** aggregates the visible rows. Shown in red here because all three positions are slightly underwater.

**Source of truth (code):**
* `frontend/app/trade/page.tsx:607-616` // PanelHeader + PositionsPanel mount
* `frontend/components/trade/PositionsPanel.tsx:28-49` // load() + 15s setInterval
* `frontend/components/trade/PositionsPanel.tsx:80-152` // table layout, row coloring, total unrealized footer

---

## 6. Daily transparency report (drawer)
**Screenshot file:** `daily_transparency_report.png`

Right-side drawer that opens when the operator clicks a row in the Daily P&L card or hits Create Report. It pulls the full `/paper-trading/reports/{date}/detail` payload and renders a Summary block, the closed-trade table, and a list of blocked decisions.

**What the screenshot is showing:**
* **Summary cells (six metrics):** Trades, Win Rate, Sharpe, Gross, Net, Max DD - with green/red accents based on sign / threshold (e.g. win rate >= 0.5 turns green, drawdown is always red).
* **Closed trades table:** every closed trade for the day, one row each. Columns include Closed time, Symbol, Side, Entry, Exit, Hold duration, P&L $, P&L %, Reason, Outcome. Each row is clickable to expand the full decision lineage (section 6).
* **Blocked decisions section** (further down): counts by outcome (e.g. ABSTENTION, REGIME, RISK), then a recent list. Each blocked row can be expanded to show the gate trace of which gate failed and why.
* Drawer is dismissible by Escape, the X button, or clicking the backdrop. Body scroll is locked while open.

**Source of truth (code):**
* `frontend/app/trade/page.tsx:637-713` // DailyReportDrawer (animated aside, escape handler)
* `frontend/components/performance/DailyReportDetail.tsx:80-98` // data fetch via `api.paperTrading.reportDetail(date)`
* `frontend/components/performance/DailyReportDetail.tsx:117-260` // Summary, Closed trades, Blocked decisions sections

---

## 7. Daily transparency report - expanded trade lineage
**Screenshot file:** `daily_transparency_report_expanded.png`

Same drawer, with one trade row expanded. The expansion exposes full decision lineage: order timeline, agent attribution, gate trace + regime, indicator snapshot, and the profile rules in effect at decision time. This is the 'why did the engine do this?' view.

**What the screenshot is showing:**
* **Order timeline column:** status, exchange, qty, intended price, fill price, slippage %, fill latency ms, placed/filled timestamps.
* **Agent attribution column:** per-agent (TA / Sentiment / Debate) direction, weight, and adjustment to confidence; plus the confidence-before confidence-after value used at the gate.
* **Gate trace:** chip per gate (regime, blacklist, abstention, circuit_breaker, validation, hitl, risk) showing pass/fail with the reason on hover. Below it: rule-based regime, HMM regime, resolved regime + confidence multiplier.
* **Indicators:** rsi, macd_line, signal_line, histogram, atr, adx, bb_pct_b, obv, choppiness - the snapshot the strategy evaluated against.
* **Profile rules at decision time:** direction, logic, base_confidence, the actual condition list (e.g. macd_histogram > 0), and risk_limits as captured at decision time.

**Source of truth (code):**
* `frontend/components/performance/DailyReportDetail.tsx:327-372` // ExpandableTradeRow
* `frontend/components/performance/DailyReportDetail.tsx:375-491` // DecisionPanel: order, agents, gates, regime, indicators
* `frontend/components/performance/DailyReportDetail.tsx:494-537` // ProfileRules Panel
* `frontend/components/performance/DailyReportDetail.tsx:304-325` // GateChips

---

## 8. Performance review drawer
**Screenshot file:** `performance_review_drawer.png`

Right-side drawer triggered from the Live activity header (PROFILE-scoped). Where the Daily transparency report is per-day, this drawer is per-profile and aggregated over the recent history. Three panels stacked top to bottom: Decision Outcomes, Weight Evolution, and Closed Trades.

**What the screenshot is showing:**
* **Symbol toggle** in the top-right (BTC/ETH) re-fetches the data for the chosen pair. The screenshot is on ETH.
* **Decision Outcomes (left):** horizontal bar chart of how many signals were APPROVED vs. blocked by each gate. Below the chart is a row of pass-rate bars per gate (Regime 100%, Blacklist 100%, Risk Gate 7%, Abstention 100%, Circuit Breaker 100%, HITL 100%, Validation 81%). The 7% Risk Gate pass rate is the headline finding here - that is what is killing most signals.
* **Weight Evolution (right):** line chart of agent weights (Debate, Sentiment, TA) over time. The X axis is recorded_at; the Y axis is the agent weight. Forward-filled so the tooltip always shows every agent.
* **Closed Trades (bottom):** a paginated table of recent closed trades for this profile/symbol pair. Columns: Date, Closed, Side, Entry, Exit, Hold, P&L $, P&L %, Reason. The header strip shows aggregate counts (25W, 8L, +$1821.64). Reason is 'manual' in this run because the trades were closed by the operator, not by stop-loss/take-profit.
* Data refreshes every 60 seconds.

**Source of truth (code):**
* `frontend/app/trade/page.tsx:715-794` // PerformanceReviewDrawer (animated aside)
* `frontend/app/analytics/PerformanceContent.tsx:25-91` // data fetch + 60s refresh, three sub-components
* `frontend/components/performance/GateBlockAnalytics.tsx:35-100` // Decision outcomes bar chart + gate detail
* `frontend/components/performance/WeightEvolutionChart.tsx:34-100` // weight forward-fill + line chart
* `frontend/components/performance/ClosedTradesPanel.tsx:31-60` // closed trades table

---

## 9. Strategies - Templates tab
**Screenshot file:** `strategies_page_templates_tab.png`

The Strategies page is tabbed: Profiles | Templates | Builder | Verify | Raw. The screenshot is on Templates: a 2x2 grid of one-click profile starters. Each card shows the strategy name, a plain-English description, the rule summary (direction, condition list, confidence, regimes), and a Create profile button that POSTS to `api.profiles.create`.

**What the screenshot is showing:**
* **Mean Reversion (RSI + Z-Score):** long when RSI<30 AND z_score<-2; short when RSI>70 AND z_score>2. Confidence 0.65, regime RANGE_BOUND.
* **Trend Following (MACD):** long-only when macd_line>0. Confidence 0.6, regime TRENDING_UP. The doc note explains this is a coarse stand-in for a real MA crossover - the indicator DSL doesn't yet ship MA50/MA200.
* **Bollinger Mean Reversion (± 2b):** long RSI<35, short RSI>65. Confidence 0.6, regimes RANGE_BOUND / TRENDING_UP / TRENDING_DOWN.
* **High Volume Breakout:** long when rvol>2 AND RSI>50. Confidence 0.6, regime TRENDING_UP. The doc note flags that "close above VWAP" semantics need a price-vs-indicator DSL extension that is not yet shipped.
* Templates are static JSON in `app/strategies/templates.json` - adding a new template is a one-file change.

**Source of truth (code):**
* `frontend/app/strategies/page.tsx:25-63` // Tab definitions and lazy-loaded contents
* `frontend/components/strategies/TemplateGallery.tsx:43-130` // gallery render + Create profile handler
* `frontend/app/strategies/templates.json` // the four template definitions plus notes on DSL gaps

---

## 10. Strategies - Verify tab (backtest)
**Screenshot file:** `strategies_page_verify_tab.png`

The Verify tab embeds the backtest UI inside Strategies. When opened from `/strategies` the rule editor is hidden - backtests run against the selected profile's saved canonical rules. The screenshot shows two completed runs being compared on the same equity curve.

**What the screenshot is showing:**
* **Run history (top):** saved runs as small cards with Sharpe / Win / Avg Return summaries. Two runs pinned: BTC-1m-rsi<80-long and BTC-1m-rsi<50-long.
* **Configuration (left column):** symbol, start/end dates, timeframe (1m/5m/15m/1h/1d) slippage %, profile picker, and a Run Backtest button. Below the button is the live job ID once the run is queued.
* **Equity Curve (right):** overlaid lines per run so divergence is visible immediately. The red line (rsi<80) collapses to ~10% by step 250; the green line (rsi<50) is gentler.
* **Comparison table:** trades, win %, avg return, max DD, Sharpe, profit factor - one row per run. The rsi<80 run logged 7,091 trades at 0.2% win, the rsi<50 run logged 854 at 2.5% win. (Both lose money in this window - that's the point of running Verify before going live.)
* **Simulated trades table (bottom):** every trade for the highlighted run with entry / exit / P&L % / entry time. Pagination controls at the bottom-right (43 pages here).
* Backend polling cadence is 2s, with a 10-minute soft timeout so multi-month 1m runs aren't cut off (sequential simulator with Decimal math).

**Source of truth (code):**
* `frontend/app/strategies/page.tsx:16-19` // VerifyContent dynamic-imports app/backtest/page.tsx
* `frontend/app/backtest/page.tsx:83-150` // embedded-mode detection (rule editor hidden in /strategies)
* `frontend/app/backtest/page.tsx:71-79` // 2s poll, 10-minute timeout, elapsed formatter
* `frontend/components/backtest/EquityCurveChart.tsx` // multi-run overlay rendering
* `frontend/components/backtest/ComparisonTable.tsx` // per-run sortable metrics table
* `frontend/components/backtest/TradesTable.tsx` // paginated simulated-trade list

---

## Notes
Every screenshot above is taken from a single, currently-deployed branch - the components named are the actual files that render the visible UI. Where panels poll the backend, the polling cadence is shown in the bullets so latency expectations are explicit. Refresh / drawer behavior (Escape closes, body scroll locks while open, backdrop is click-dismissable) is consistent across the app and is implemented inline in `app/trade/page.tsx`.
