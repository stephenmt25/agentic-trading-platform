"""Build a PDF walkthrough of the Praxis UI for partner review.

Reads screenshots from ../scrnshts and emits a PDF in the same folder.
Each section pairs the screenshot with a code-grounded explanation of what
the UI is showing — citations point to the React component and line range
that produces the rendered behavior.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
SCRNSHTS = ROOT / "scrnshts"
OUT_PDF = SCRNSHTS / "PRAXIS-UI-WALKTHROUGH.pdf"

PAGE_W, PAGE_H = LETTER
MARGIN = 0.6 * inch
USABLE_W = PAGE_W - 2 * MARGIN


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a1a"),
    )
    h1 = ParagraphStyle(
        "H1",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        spaceAfter=10,
        textColor=colors.HexColor("#0b3d2e"),
    )
    h2 = ParagraphStyle(
        "H2",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        spaceBefore=4,
        spaceAfter=6,
        textColor=colors.HexColor("#0b3d2e"),
    )
    h3 = ParagraphStyle(
        "H3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        spaceBefore=6,
        spaceAfter=3,
        textColor=colors.HexColor("#222"),
    )
    caption = ParagraphStyle(
        "Caption",
        parent=body,
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#555"),
        alignment=TA_LEFT,
        spaceAfter=8,
    )
    code = ParagraphStyle(
        "Code",
        parent=body,
        fontName="Courier",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#333"),
        backColor=colors.HexColor("#f1f3f5"),
        borderPadding=4,
        spaceAfter=8,
    )
    return {
        "body": body,
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "caption": caption,
        "code": code,
    }


def fit_image(path: Path, max_w: float, max_h: float) -> RLImage:
    """Return an RLImage scaled to fit (max_w, max_h) while preserving aspect."""
    with Image.open(path) as im:
        w, h = im.size
    aspect = w / h
    target_w = max_w
    target_h = target_w / aspect
    if target_h > max_h:
        target_h = max_h
        target_w = target_h * aspect
    img = RLImage(str(path), width=target_w, height=target_h)
    img.hAlign = "CENTER"
    return img


def hr() -> Table:
    t = Table([[""]], colWidths=[USABLE_W], rowHeights=[1])
    t.setStyle(
        TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd4d9"))])
    )
    return t


def section(
    story: list,
    s: dict,
    *,
    title: str,
    file_label: str,
    image: Path,
    summary: str,
    bullets: list[str],
    code_refs: list[str],
) -> None:
    story.append(Paragraph(title, s["h2"]))
    story.append(
        Paragraph(
            f"<i>Screenshot file:</i> <font face='Courier'>{file_label}</font>",
            s["caption"],
        )
    )
    story.append(fit_image(image, USABLE_W, 4.6 * inch))
    story.append(Spacer(1, 6))
    story.append(Paragraph(summary, s["body"]))
    if bullets:
        story.append(Paragraph("<b>What the screenshot is showing</b>", s["h3"]))
        for b in bullets:
            story.append(Paragraph(f"&bull;&nbsp; {b}", s["body"]))
    if code_refs:
        story.append(Paragraph("<b>Source of truth (code)</b>", s["h3"]))
        for c in code_refs:
            story.append(
                Paragraph(f"<font face='Courier' size='9'>{c}</font>", s["body"])
            )
    story.append(Spacer(1, 8))
    story.append(hr())
    story.append(Spacer(1, 8))


def build() -> None:
    s = styles()
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=LETTER,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title="Praxis Trading Platform - UI Walkthrough",
        author="Praxis Trading",
    )
    story: list = []

    # ── Cover ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * inch))
    story.append(Paragraph("Praxis Trading Platform", s["h1"]))
    story.append(Paragraph("UI Walkthrough &mdash; Partner Brief", s["h2"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        Paragraph(
            "This document walks through the current state of the Praxis dashboard, "
            "section by section, using screenshots from <font face='Courier'>scrnshts/</font> "
            "and the React components that render them. Every behavior described below is "
            "grounded in source code &mdash; file paths and line ranges are listed under each section.",
            s["body"],
        )
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        Paragraph(
            "Scope tags used throughout the dashboard:",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "&bull;&nbsp; <b>PROFILE</b> &mdash; the panel reflects the active profile selected in the picker.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "&bull;&nbsp; <b>SYSTEM</b> &mdash; the panel reflects the engine as a whole, ignoring the profile picker.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "&bull;&nbsp; <b>SYMBOL</b> &mdash; the panel reflects whichever chart symbol (BTC/USDT, ETH/USDT) is selected.",
            s["body"],
        )
    )
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Contents", s["h3"]))
    toc = [
        "1. Landing page (root redirect)",
        "2. Trade dashboard &mdash; top section (Engine totals, Risk monitor, Approvals, Daily P&L)",
        "3. Trade dashboard &mdash; Live Activity (Decision feed + Price/agent overlays)",
        "4. Decision Feed &mdash; expanded row (full decision trace + chart pinning)",
        "5. Trade dashboard &mdash; Open positions",
        "6. Daily transparency report (drawer, summary view)",
        "7. Daily transparency report (drawer, expanded trade lineage)",
        "8. Performance review drawer (gate analytics, weight evolution, closed trades)",
        "9. Strategies &mdash; Templates tab",
        "10. Strategies &mdash; Verify tab (backtest)",
    ]
    for line in toc:
        story.append(Paragraph(line, s["body"]))
    story.append(PageBreak())

    # ── 1. Landing page ────────────────────────────────────────────────
    section(
        story,
        s,
        title="1. Landing page",
        file_label="landing_page.png",
        image=SCRNSHTS / "landing_page.png",
        summary=(
            "There is no standalone landing page &mdash; the root route redirects "
            "straight to <font face='Courier'>/trade</font>. The screenshot shows the "
            "Trade dashboard as it appears on first load, with the left-rail nav "
            "(Trade, Strategies, Agents, Docs) and the Praxis logo in the top-left. "
            "Trade is highlighted because that is the default destination."
        ),
        bullets=[
            "Praxis branding and global nav are rendered by the root layout. The page user lands on is always Trade.",
            "Top-right shows a connection indicator (LIVE), notification bell, and avatar &mdash; identical chrome on every page.",
            "Below the header you can see panels that are detailed in sections 2-4: Engine totals strip, Risk monitor / Approvals row, Daily P&amp;L card on the right, Live activity strip beneath.",
        ],
        code_refs=[
            "frontend/app/page.tsx:1-5  &nbsp;&nbsp;// redirect('/trade')",
            "frontend/app/layout.tsx  &nbsp;&nbsp;// global chrome (logo, side nav, LIVE badge)",
            "frontend/app/trade/page.tsx:343-394  &nbsp;&nbsp;// Trade page header that the user lands on",
        ],
    )

    # ── 2. Trade dashboard top section ─────────────────────────────────
    section(
        story,
        s,
        title="2. Trade dashboard &mdash; top section",
        file_label="trade_dashboard_top_section.png",
        image=SCRNSHTS / "trade_dashboard_top_section.png",
        summary=(
            "This is the top half of the Trade dashboard. It is composed of four panels: "
            "<b>Engine totals</b>, <b>Risk monitor</b>, <b>Approvals</b>, and <b>Daily P&amp;L</b>. "
            "Each panel is tagged with a scope chip (PROFILE / SYSTEM / SYMBOL) so the "
            "operator always knows whether they are looking at one profile or the engine "
            "as a whole. The header shows a PAPER mode badge, an updated-Ns-ago timestamp "
            "with a refresh button, and a Kill Switch control."
        ),
        bullets=[
            "<b>Mode badge</b>: PAPER / TESTNET / LIVE, color-coded amber/blue/emerald. Driven by <font face='Courier'>api.paperTrading.mode()</font>.",
            "<b>Kill Switch</b>: toggles the global <font face='Courier'>KillSwitch</font> Redis key. When ACTIVE the button turns red and a system-state warning chip appears under the header.",
            "<b>Engine totals</b> (SYSTEM): Net P&amp;L, Gross P&amp;L, Trades, Win rate, Max DD, Sharpe &mdash; aggregate across all profiles since boot. In the screenshot: +$535.86 net, 52 trades, 57.0% win, 1.7% MaxDD.",
            "<b>Risk monitor</b> (SYSTEM): per active profile, shows Daily P&amp;L vs the circuit-breaker limit, current drawdown, and allocation used. Two profiles are visible: <i>Demo &middot; Pullback Long</i> with 2.01% drawdown and <i>Oversold Uptrend</i> at 0%.",
            "<b>Approvals</b> (SYSTEM): trades held by the HITL gate awaiting human decision. Empty state shown (&ldquo;No pending approvals&rdquo;).",
            "<b>Daily P&amp;L</b> (SYSTEM): right-side card with a date picker and a <font face='Courier'>Create Report</font> button. Below is a sparkline of net P&amp;L by day and a scrollable list of past reports. Clicking a row opens the Daily Transparency Report drawer (section 5).",
            "Live status auto-refreshes every 30s (<font face='Courier'>POLL_INTERVAL = 30_000</font>) and can be force-refreshed via the round-arrow button.",
        ],
        code_refs=[
            "frontend/app/trade/page.tsx:35-50  &nbsp;&nbsp;// ModeBadge",
            "frontend/app/trade/page.tsx:52-78  &nbsp;&nbsp;// KillSwitchControl + toggle handler at 314-328",
            "frontend/app/trade/page.tsx:402-438  &nbsp;&nbsp;// Engine totals strip (StatCells)",
            "frontend/app/trade/page.tsx:444-456  &nbsp;&nbsp;// Risk monitor section wrapper",
            "frontend/components/risk/RiskMonitorCard.tsx:26-72  &nbsp;&nbsp;// Risk Monitor data fetch + 10s polling",
            "frontend/app/trade/page.tsx:458-468  &nbsp;&nbsp;// Approvals panel (ApprovalQueue dynamic import)",
            "frontend/app/trade/page.tsx:472-536  &nbsp;&nbsp;// Daily P&amp;L card: sparkline, date picker, Create Report",
            "frontend/app/trade/page.tsx:279-312  &nbsp;&nbsp;// handleGenerateReport &mdash; opens drawer on success",
        ],
    )

    # ── 3. Trade dashboard live activity ───────────────────────────────
    section(
        story,
        s,
        title="3. Trade dashboard &mdash; Live Activity",
        file_label="trade_dashboard_middle_live_activity_section.png",
        image=SCRNSHTS / "trade_dashboard_middle_live_activity_section.png",
        summary=(
            "The middle band of the Trade dashboard, titled <b>Live activity</b>. "
            "Two side-by-side panels show what the engine is doing right now: a "
            "<b>Decision Feed</b> on the left (PROFILE-scoped) and a <b>Price &middot; Agent overlays</b> "
            "chart on the right (SYMBOL-scoped). Above them is the profile picker "
            "(currently set to <i>Demo &middot; Pullback Long</i>) and a button that opens "
            "the Performance review drawer."
        ),
        bullets=[
            "<b>Profile picker</b>: scopes per-profile panels. Risk monitor and Engine totals deliberately ignore it &mdash; both are system views.",
            "<b>Decision Feed</b>: a live, polling list of trade decisions for the selected profile. Refreshes every 15s. Each row can be expanded to show the full agent / gate / regime trace. The screenshot shows a stream of recent rows.",
            "<b>Price &middot; Agent overlays</b>: candlestick chart (TradingView-style) for the selected symbol with agent score overlays toggleable along the top. Below the price chart is a panel of agent contribution scores, with the current agent weights visible in the strip at the bottom.",
            "<b>Performance review</b> button opens a right-side drawer scoped to the active profile (section 7).",
        ],
        code_refs=[
            "frontend/app/trade/page.tsx:540-577  &nbsp;&nbsp;// Live activity header + profile picker + Performance review button",
            "frontend/app/trade/page.tsx:580-589  &nbsp;&nbsp;// Decision Feed panel wrapper",
            "frontend/components/decisions/DecisionFeed.tsx:1-40  &nbsp;&nbsp;// 15s polling, filter chips (all/approved/blocked), expandable rows",
            "frontend/app/trade/page.tsx:591-604  &nbsp;&nbsp;// Price &middot; Agent overlays panel wrapper",
            "frontend/app/analytics/AnalysisContent.tsx:34-80  &nbsp;&nbsp;// Candles + agent scores + weights, refreshes every 60s",
        ],
    )

    # ── 4. Decision Feed expanded row ──────────────────────────────────
    section(
        story,
        s,
        title="4. Decision Feed &mdash; expanded row",
        file_label="trade_dashboard_live_activity_decision_feed_expanded.png",
        image=SCRNSHTS / "trade_dashboard_live_activity_decision_feed_expanded.png",
        summary=(
            "Drilling into the Decision Feed: any row can be clicked to expand the "
            "<b>full decision trace</b> in place. The screenshot shows an APPROVED "
            "ETH/USDT BUY at 08:27 PM with confidence 0.71. Notice the same decision "
            "is also marked on the right-side price chart with a green APPROVED arrow "
            "&mdash; that&apos;s the <b>pin-to-chart</b> feature: clicking the pin icon "
            "next to a decision row anchors that exact moment on the candle chart and "
            "the agent-score chart, so price action and the trace can be read together."
        ),
        bullets=[
            "<b>Row header</b>: status dot (emerald = APPROVED, slate = BLOCKED), symbol, direction (BUY/SELL color-coded), timestamp (HH:MM:SS for today, MMM&nbsp;d HH:MM otherwise), live confidence, outcome chip, pin icon, expand chevron.",
            "<b>One-line summary</b> (under the header, when collapsed): for APPROVED rows this is <i>TA:&plusmn;adj &nbsp; Sent:&plusmn;adj &nbsp; Dbt:&plusmn;adj</i>; for BLOCKED rows it is the failing gate name + reason.",
            "<b>Market context &mdash; 1m</b>: a lightweight-charts mini candle chart spanning &plusmn;15 minutes around the decision, with an APPROVED/BLOCKED arrow marker placed at the exact decision second (above-bar for SELL, below-bar for BUY). Falls back to a graceful &ldquo;no candles for this window&rdquo; state if the API has no data.",
            "<b>Indicators</b>: RSI (color-graded green &lt;30 / red &gt;70), MACD histogram, ATR, ADX, BB%B, OBV, Choppiness &mdash; the snapshot the strategy evaluated against.",
            "<b>Strategy (AND/OR) &mdash; BUY/SELL &mdash; conf 0.65</b>: every condition rendered as a row with the operator (LT/GT), threshold, actual value, and a pass/fail check. The screenshot shows two AND-conditions: <font face='Courier'>rsi LT 50 | 47.6121</font> and <font face='Courier'>macd_histogram GT 0 | 166.9246</font>.",
            "<b>Regime</b>: rule-based regime, HMM regime, and the resolved confidence multiplier (Mult: 1x).",
            "<b>Agent Influence</b>: header summarises confidence-before &rarr; confidence-after with a percentage delta colored green/red. Per-agent rows show name, score, weight, signed adjustment, and a horizontal bar whose width is <font face='Courier'>min(|adjustment|*500, 100)%</font>. In the screenshot: confidence moved 0.650 &rarr; 0.707 (+8.8%).",
            "<b>Gates</b> (cut off at the bottom of the screenshot): pass/fail row per gate (regime, blacklist, abstention, circuit_breaker, validation, hitl, risk) with reason text. Risk gate rows additionally show <i>qty</i> and <i>alloc</i> when the gate computed them.",
            "<b>Filter pills</b> at the top-right of the panel (ALL / APPROVED / BLOCKED) scope the feed without re-fetching profile state.",
        ],
        code_refs=[
            "frontend/components/decisions/DecisionFeed.tsx:69-92  &nbsp;&nbsp;// Decision Trace header + filter pills (all/approved/blocked)",
            "frontend/components/decisions/DecisionFeed.tsx:113-200  &nbsp;&nbsp;// row rendering, summary builder, pin-to-chart icon",
            "frontend/components/decisions/DecisionFeed.tsx:54-67  &nbsp;&nbsp;// togglePin() &mdash; writes pinnedDecision into the analysis store",
            "frontend/components/decisions/DecisionFeed.tsx:202-207  &nbsp;&nbsp;// in-place expansion (DecisionDetail mount)",
            "frontend/components/decisions/DecisionDetail.tsx:200-298  &nbsp;&nbsp;// expanded trace: chart, indicators, strategy, regime, agents, gates",
            "frontend/components/decisions/DecisionDetail.tsx:84-192  &nbsp;&nbsp;// DecisionContextChart &mdash; 1m candles + APPROVED/BLOCKED marker",
            "frontend/components/decisions/DecisionDetail.tsx:44-59  &nbsp;&nbsp;// ConditionRow &mdash; threshold vs actual_value with pass/fail",
            "frontend/components/decisions/DecisionDetail.tsx:61-80  &nbsp;&nbsp;// AgentRow &mdash; score / weight / adjustment + bar",
            "frontend/components/decisions/DecisionDetail.tsx:19-42  &nbsp;&nbsp;// GateRow &mdash; reason / suggested_qty / alloc",
        ],
    )

    # ── 5. Trade dashboard open positions ──────────────────────────────
    section(
        story,
        s,
        title="5. Trade dashboard &mdash; Open positions",
        file_label="trade_dashboard_open_positions_panel.png",
        image=SCRNSHTS / "trade_dashboard_open_positions_panel.png",
        summary=(
            "The lower-third <b>Open positions</b> panel (PROFILE-scoped). It tabulates "
            "all currently open positions for the selected profile, refreshing every 15 "
            "seconds. The screenshot shows three open ETH/USDT longs, all approximately "
            "4.8 hours old, with a combined unrealized P&amp;L of -$180.53."
        ),
        bullets=[
            "<b>Columns</b>: Symbol, Side (long/short with up/down arrow), Qty, Entry, Unrealized $, Unrealized %, Age. Negative unrealized values render in red, positive in emerald.",
            "Polling interval is <font face='Courier'>15_000ms</font> &mdash; positions are kept fresh without flooding the API.",
            "When the list is empty, the panel shows operator guidance: positions only appear when an APPROVED signal becomes a fill, and most signals are filtered upstream by abstention / circuit-breaker gates.",
            "<b>Total unrealized</b> footer aggregates the visible rows. Shown in red here because all three positions are slightly underwater.",
        ],
        code_refs=[
            "frontend/app/trade/page.tsx:607-616  &nbsp;&nbsp;// PanelHeader + PositionsPanel mount",
            "frontend/components/trade/PositionsPanel.tsx:28-49  &nbsp;&nbsp;// load() + 15s setInterval",
            "frontend/components/trade/PositionsPanel.tsx:80-152  &nbsp;&nbsp;// table layout, row coloring, total unrealized footer",
        ],
    )

    # ── 6. Daily transparency report ───────────────────────────────────
    section(
        story,
        s,
        title="6. Daily transparency report (drawer)",
        file_label="daily_transparency_report.png",
        image=SCRNSHTS / "daily_transparency_report.png",
        summary=(
            "Right-side drawer that opens when the operator clicks a row in the Daily "
            "P&amp;L card or hits <b>Create Report</b>. It pulls the full "
            "<font face='Courier'>/paper-trading/reports/{date}/detail</font> payload and "
            "renders a Summary block, the closed-trade table, and a list of blocked "
            "decisions."
        ),
        bullets=[
            "<b>Summary cells</b> (six metrics): Trades, Win Rate, Sharpe, Gross, Net, Max DD &mdash; with green/red accents based on sign / threshold (e.g. win rate &ge; 0.5 turns green, drawdown is always red).",
            "<b>Closed trades table</b>: every closed trade for the day, one row each. Columns include Closed time, Symbol, Side, Entry, Exit, Hold duration, P&amp;L $, P&amp;L %, Reason, Outcome. Each row is clickable to expand the full decision lineage (section 6).",
            "<b>Blocked decisions</b> section (further down): counts by outcome (e.g. ABSTENTION, REGIME, RISK), then a recent list. Each blocked row can be expanded to show the gate trace of which gate failed and why.",
            "Drawer is dismissible by Escape, the X button, or clicking the backdrop. Body scroll is locked while open.",
        ],
        code_refs=[
            "frontend/app/trade/page.tsx:637-713  &nbsp;&nbsp;// DailyReportDrawer (animated aside, escape handler)",
            "frontend/components/performance/DailyReportDetail.tsx:80-98  &nbsp;&nbsp;// data fetch via api.paperTrading.reportDetail(date)",
            "frontend/components/performance/DailyReportDetail.tsx:117-260  &nbsp;&nbsp;// Summary, Closed trades, Blocked decisions sections",
        ],
    )

    section(
        story,
        s,
        title="7. Daily transparency report &mdash; expanded trade lineage",
        file_label="daily_transparency_report_expanded.png",
        image=SCRNSHTS / "daily_transparency_report_expanded.png",
        summary=(
            "Same drawer, with one trade row expanded. The expansion exposes <b>full decision "
            "lineage</b>: order timeline, agent attribution, gate trace + regime, indicator snapshot, "
            "and the profile rules in effect at decision time. This is the &lsquo;why did the engine "
            "do this?&rsquo; view."
        ),
        bullets=[
            "<b>Order timeline</b> column: status, exchange, qty, intended price, fill price, slippage %, fill latency ms, placed/filled timestamps.",
            "<b>Agent attribution</b> column: per-agent (TA / Sentiment / Debate) direction, weight, and adjustment to confidence; plus the confidence-before &rarr; confidence-after value used at the gate.",
            "<b>Gate trace</b>: chip per gate (regime, blacklist, abstention, circuit_breaker, validation, hitl, risk) showing pass/fail with the reason on hover. Below it: rule-based regime, HMM regime, resolved regime + confidence multiplier.",
            "<b>Indicators</b>: rsi, macd_line, signal_line, histogram, atr, adx, bb_pct_b, obv, choppiness &mdash; the snapshot the strategy evaluated against.",
            "<b>Profile rules at decision time</b>: direction, logic, base_confidence, the actual condition list (<i>e.g. macd_histogram &gt; 0</i>), and risk_limits as captured at decision time.",
        ],
        code_refs=[
            "frontend/components/performance/DailyReportDetail.tsx:327-372  &nbsp;&nbsp;// ExpandableTradeRow",
            "frontend/components/performance/DailyReportDetail.tsx:375-491  &nbsp;&nbsp;// DecisionPanel: order, agents, gates, regime, indicators",
            "frontend/components/performance/DailyReportDetail.tsx:494-537  &nbsp;&nbsp;// ProfileRulesPanel",
            "frontend/components/performance/DailyReportDetail.tsx:304-325  &nbsp;&nbsp;// GateChips",
        ],
    )

    # ── 8. Performance review drawer ───────────────────────────────────
    section(
        story,
        s,
        title="8. Performance review drawer",
        file_label="performance_review_drawer.png",
        image=SCRNSHTS / "performance_review_drawer.png",
        summary=(
            "Right-side drawer triggered from the Live activity header (PROFILE-scoped). "
            "Where the Daily transparency report is per-day, this drawer is per-profile "
            "and aggregated over the recent history. Three panels stacked top to bottom: "
            "<b>Decision Outcomes</b>, <b>Weight Evolution</b>, and <b>Closed Trades</b>."
        ),
        bullets=[
            "<b>Symbol toggle</b> in the top-right (BTC / ETH) re-fetches the data for the chosen pair. The screenshot is on ETH.",
            "<b>Decision Outcomes</b> (left): horizontal bar chart of how many signals were APPROVED vs. blocked by each gate. Below the chart is a row of pass-rate bars per gate (Regime 100%, Blacklist 100%, Risk Gate 7%, Abstention 100%, Circuit Breaker 100%, HITL 100%, Validation 81%). The 7% Risk Gate pass rate is the headline finding here &mdash; that is what is killing most signals.",
            "<b>Weight Evolution</b> (right): line chart of agent weights (Debate, Sentiment, TA) over time. The X axis is recorded_at; the Y axis is the agent weight. Forward-filled so the tooltip always shows every agent.",
            "<b>Closed Trades</b> (bottom): a paginated table of recent closed trades for this profile/symbol pair. Columns: Date, Closed, Side, Entry, Exit, Hold, P&amp;L $, P&amp;L %, Reason. The header strip shows aggregate counts (25W, 8L, +$1821.64). Reason is &lsquo;manual&rsquo; in this run because the trades were closed by the operator, not by stop-loss / take-profit.",
            "Data refreshes every 60 seconds.",
        ],
        code_refs=[
            "frontend/app/trade/page.tsx:715-794  &nbsp;&nbsp;// PerformanceReviewDrawer (animated aside)",
            "frontend/app/analytics/PerformanceContent.tsx:25-91  &nbsp;&nbsp;// data fetch + 60s refresh, three sub-components",
            "frontend/components/performance/GateBlockAnalytics.tsx:35-100  &nbsp;&nbsp;// Decision outcomes bar chart + gate detail",
            "frontend/components/performance/WeightEvolutionChart.tsx:34-100  &nbsp;&nbsp;// weight forward-fill + line chart",
            "frontend/components/performance/ClosedTradesPanel.tsx:31-60  &nbsp;&nbsp;// closed trades table",
        ],
    )

    # ── 9. Strategies templates ────────────────────────────────────────
    section(
        story,
        s,
        title="9. Strategies &mdash; Templates tab",
        file_label="strategies_page_templates_tab.png",
        image=SCRNSHTS / "strategies_page_templates_tab.png",
        summary=(
            "The Strategies page is tabbed: <b>Profiles | Templates | Builder | Verify | Raw</b>. "
            "The screenshot is on <b>Templates</b>: a 2&times;2 grid of one-click profile starters. "
            "Each card shows the strategy name, a plain-English description, the rule summary "
            "(direction, condition list, confidence, regimes), and a <i>Create profile</i> button "
            "that POSTs to <font face='Courier'>api.profiles.create</font>."
        ),
        bullets=[
            "<b>Mean Reversion (RSI + Z-Score)</b>: long when RSI&lt;30 AND z_score&lt;-2; short when RSI&gt;70 AND z_score&gt;2. Confidence 0.65, regime RANGE_BOUND.",
            "<b>Trend Following (MACD)</b>: long-only when macd_line&gt;0. Confidence 0.6, regime TRENDING_UP. The doc note explains this is a coarse stand-in for a real MA crossover &mdash; the indicator DSL doesn't yet ship MA50/MA200.",
            "<b>Bollinger Mean Reversion (&plusmn; 2&sigma;)</b>: long RSI&lt;35, short RSI&gt;65. Confidence 0.6, regimes RANGE_BOUND / TRENDING_UP / TRENDING_DOWN.",
            "<b>High Volume Breakout</b>: long when rvol&gt;2 AND RSI&gt;50. Confidence 0.6, regime TRENDING_UP. The doc note flags that &ldquo;close above VWAP&rdquo; semantics need a price-vs-indicator DSL extension that is not yet shipped.",
            "Templates are static JSON in <font face='Courier'>app/strategies/templates.json</font> &mdash; adding a new template is a one-file change.",
        ],
        code_refs=[
            "frontend/app/strategies/page.tsx:25-63  &nbsp;&nbsp;// Tab definitions and lazy-loaded contents",
            "frontend/components/strategies/TemplateGallery.tsx:43-130  &nbsp;&nbsp;// gallery render + Create profile handler",
            "frontend/app/strategies/templates.json  &nbsp;&nbsp;// the four template definitions plus _notes on DSL gaps",
        ],
    )

    # ── 10. Strategies verify ──────────────────────────────────────────
    section(
        story,
        s,
        title="10. Strategies &mdash; Verify tab (backtest)",
        file_label="strategies_page_verify_tab.png",
        image=SCRNSHTS / "strategies_page_verify_tab.png",
        summary=(
            "The <b>Verify</b> tab embeds the backtest UI inside Strategies. When opened "
            "from /strategies the rule editor is hidden &mdash; backtests run against the "
            "selected profile&apos;s saved canonical rules. The screenshot shows two completed "
            "runs being compared on the same equity curve."
        ),
        bullets=[
            "<b>Run history</b> (top): saved runs as small cards with Sharpe / Win / Avg Return summaries. Two runs pinned: <i>BTC-1m-rsi&lt;80-long</i> and <i>BTC-1m-rsi&lt;50-long</i>.",
            "<b>Configuration</b> (left column): symbol, start/end dates, timeframe (1m / 5m / 15m / 1h / 1d), slippage %, profile picker, and a <b>Run Backtest</b> button. Below the button is the live job ID once the run is queued.",
            "<b>Equity Curve</b> (right): overlaid lines per run so divergence is visible immediately. The red line (rsi&lt;80) collapses to ~10% by step ~250; the green line (rsi&lt;50) is gentler.",
            "<b>Comparison table</b>: trades, win %, avg return, max DD, Sharpe, profit factor &mdash; one row per run. The rsi&lt;80 run logged 7,091 trades at 0.2% win, the rsi&lt;50 run logged 854 at 2.5% win. (Both lose money in this window &mdash; that's the point of running Verify before going live.)",
            "<b>Simulated trades</b> table (bottom): every trade for the highlighted run with entry / exit / P&amp;L % / entry time. Pagination controls at the bottom-right (43 pages here).",
            "Backend polling cadence is 2s, with a 10-minute soft timeout so multi-month 1m runs aren't cut off (sequential simulator with Decimal math).",
        ],
        code_refs=[
            "frontend/app/strategies/page.tsx:16-19  &nbsp;&nbsp;// VerifyContent dynamic-imports app/backtest/page.tsx",
            "frontend/app/backtest/page.tsx:83-150  &nbsp;&nbsp;// embedded-mode detection (rule editor hidden in /strategies)",
            "frontend/app/backtest/page.tsx:71-79  &nbsp;&nbsp;// 2s poll, 10-minute timeout, elapsed formatter",
            "frontend/components/backtest/EquityCurveChart.tsx  &nbsp;&nbsp;// multi-run overlay rendering",
            "frontend/components/backtest/ComparisonTable.tsx  &nbsp;&nbsp;// per-run sortable metrics table",
            "frontend/components/backtest/TradesTable.tsx  &nbsp;&nbsp;// paginated simulated-trade list",
        ],
    )

    # ── Closing notes ──────────────────────────────────────────────────
    story.append(Paragraph("Notes", s["h2"]))
    story.append(
        Paragraph(
            "Every screenshot above is taken from a single, currently-deployed branch &mdash; the "
            "components named are the actual files that render the visible UI. Where panels poll "
            "the backend, the polling cadence is shown in the bullets so latency expectations are "
            "explicit. Refresh / drawer behavior (Escape closes, body scroll locks while open, "
            "backdrop is click-dismissable) is consistent across the app and is implemented inline "
            "in <font face='Courier'>app/trade/page.tsx</font>.",
            s["body"],
        )
    )

    doc.build(story)
    print(f"Wrote {OUT_PDF}")


if __name__ == "__main__":
    build()
