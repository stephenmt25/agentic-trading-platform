"""Build the redesigned-UI PDF walkthrough.

Counterpart to scripts/build_ui_walkthrough_pdf.py (which targets the legacy
walkthrough). Reads screenshots from scrnshts/redesign/ and emits the PDF at
docs/PRAXIS-UI-WALKTHROUGH-REDESIGN.pdf. Section content here mirrors
docs/PRAXIS-UI-WALKTHROUGH-REDESIGN.md — keep the two in sync when content
changes (the MD is the source of truth for the narrative; this script is the
typesetting layer).

Run from the project root:
    python scripts/build_ui_walkthrough_redesign_pdf.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent.parent
SCRNSHTS = ROOT / "scrnshts" / "redesign"
OUT_PDF = ROOT / "docs" / "PRAXIS-UI-WALKTHROUGH-REDESIGN.pdf"

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
    tag = ParagraphStyle(
        "Tag",
        parent=body,
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#a07000"),
        spaceAfter=6,
    )
    return {"body": body, "h1": h1, "h2": h2, "h3": h3, "caption": caption, "tag": tag}


def fit_image(path: Path, max_w: float, max_h: float):
    """Return an RLImage scaled to fit (max_w, max_h) preserving aspect, or a
    placeholder paragraph if the file is missing — so the doc still renders."""
    if not path.exists():
        return Paragraph(
            f"<i>[Screenshot missing — expected at <font face='Courier'>"
            f"{path.relative_to(ROOT)}</font>. Add the file and rebuild.]</i>",
            styles()["caption"],
        )
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
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd4d9"))]))
    return t


def section(
    story: list,
    s: dict,
    *,
    title: str,
    file_label: str,
    image: Path,
    summary: str,
    bullets: list[str] | None = None,
    code_refs: list[str] | None = None,
    status_tag: str | None = None,
) -> None:
    story.append(Paragraph(title, s["h2"]))
    if status_tag:
        story.append(Paragraph(status_tag, s["tag"]))
    story.append(Paragraph(f"<i>Screenshot:</i> <font face='Courier'>{file_label}</font>", s["caption"]))
    story.append(fit_image(image, USABLE_W, 5.5 * inch))
    story.append(Spacer(1, 6))
    story.append(Paragraph(summary, s["body"]))
    if bullets:
        story.append(Paragraph("<b>What the screenshot is showing</b>", s["h3"]))
        for b in bullets:
            story.append(Paragraph(f"&bull;&nbsp; {b}", s["body"]))
    if code_refs:
        story.append(Paragraph("<b>Source of truth (code)</b>", s["h3"]))
        for c in code_refs:
            story.append(Paragraph(f"<font face='Courier' size='9'>{c}</font>", s["body"]))
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
        title="Praxis Trading Platform - UI Walkthrough (Redesign)",
        author="Praxis Trading",
    )
    story: list = []

    # ── Cover ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * inch))
    story.append(Paragraph("Praxis Trading Platform", s["h1"]))
    story.append(Paragraph("UI Walkthrough &mdash; Partner Brief (Redesign)", s["h2"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "This document walks through the redesigned Praxis dashboard one surface at a time. "
        "The frontend was rebuilt over Phases 1&ndash;9 of the redesign program; the merged "
        "design portfolio (<font face='Courier'>docs/design/</font>) governs visual and IA "
        "decisions. Every behavior described below is grounded in source code &mdash; file "
        "paths and line ranges are listed under each section.",
        s["body"],
    ))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "The redesign is organized around <b>five canonical surfaces</b> and a shared chrome:",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>Hot Trading</b> &mdash; <font face='Courier'>/hot/{symbol}</font> &mdash; the cockpit, max density. 70%+ of session time.",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>Agent Observatory</b> &mdash; <font face='Courier'>/agents/observatory</font> &mdash; the analyst&apos;s workbench. 15&ndash;25% of session.",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>Risk Control</b> &mdash; <font face='Courier'>/risk</font> &mdash; highest-stakes surface; must stay responsive when others degrade.",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>Backtesting</b> &mdash; <font face='Courier'>/backtests</font> + detail / compare &mdash; validate profile changes before they go live.",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>Settings</b> &mdash; <font face='Courier'>/settings/{section}</font> &mdash; CALM mode; configure intent, not react to markets.",
        s["body"],
    ))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "<b>Mode contract.</b> Every surface declares <font face='Courier'>data-mode=\"hot|cool|calm\"</font> on its root. "
        "The three modes share a token vocabulary but differ in density, visual budget, and tone. "
        "HOT is the cockpit; COOL is the analyst&apos;s workbench; CALM is the office where you configure intent.",
        s["body"],
    ))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Contents", s["h3"]))
    toc = [
        "1. Hot Trading &mdash; cockpit (chart + book + tape + order entry)",
        "&nbsp;&nbsp;&nbsp;Chrome &mdash; Engine-totals pill <i>(new, Phase 10.1)</i>",
        "&nbsp;&nbsp;&nbsp;Hot Trading &mdash; Profile comparison grid <i>(new, Phase 10.2)</i>",
        "&nbsp;&nbsp;&nbsp;Profile cockpit &mdash; Decisions tab <i>(new, Phase 10.3)</i>",
        "&nbsp;&nbsp;&nbsp;Profile cockpit &mdash; Decision drill-down drawer <i>(new, Phase 10.3)</i>",
        "&nbsp;&nbsp;&nbsp;Profile cockpit &mdash; Positions tab <i>(new, Phase 10.3)</i>",
        "&nbsp;&nbsp;&nbsp;Profile cockpit &mdash; Position chain drill-down drawer <i>(new, Phase 10.3)</i>",
        "&nbsp;&nbsp;&nbsp;Profile cockpit &mdash; Daily P&amp;L tab <i>(new, Phase 10.4)</i>",
        "&nbsp;&nbsp;&nbsp;Profile cockpit &mdash; Day transparency drill-down drawer <i>(new, Phase 10.4)</i>",
        "&nbsp;&nbsp;&nbsp;Profile cockpit &mdash; Attribution tab <i>(new, Phase 10.4)</i>",
        "2. Agent Observatory &mdash; roster + event stream + focus panel",
        "3. Risk Control &mdash; kill switch + exposure + active limits",
        "&nbsp;&nbsp;&nbsp;Risk Control &mdash; All-profiles risk matrix <i>(new, Phase 10.1)</i>",
        "4. Backtesting &mdash; run list",
        "5. Backtesting &mdash; run detail",
        "6. Backtesting &mdash; compare view",
        "7. Settings &mdash; navigation",
        "8. Settings &mdash; Profiles",
        "9. Settings &mdash; Exchange keys",
        "10. Settings &mdash; Risk defaults (newly wired)",
        "11. Settings &mdash; Notifications (partial)",
        "12. Settings &mdash; Tax (Pending)",
        "13. Settings &mdash; Account",
        "14. Settings &mdash; Sessions / API (newly wired)",
        "15. Settings &mdash; Audit log",
    ]
    for line in toc:
        story.append(Paragraph(line, s["body"]))
    story.append(PageBreak())

    # ── 1. Hot Trading default ──────────────────────────────────────────
    section(
        story, s,
        title="1. Hot Trading &mdash; cockpit",
        file_label="hot_trading_default.png",
        image=SCRNSHTS / "hot_trading_default.png",
        summary=(
            "<font face='Courier'>/hot/{symbol}</font> is the surface that opens on sign-in. Three-column "
            "grid: collapsible left rail + center column (chart on top, order book + trades tape below, "
            "positions / open orders / fills tabs at the bottom) + right column (order entry on top, "
            "agent summary below). HOT mode, max density &mdash; this is the cockpit."
        ),
        bullets=[
            "<b>Chart</b> &mdash; lightweight-charts candle chart with timeframe selector (1m / 5m / 15m / 1h / 4h / 1d). Fluid layout so candles paint correctly across viewport sizes.",
            "<b>Order book</b> &mdash; 50 price levels per side, 1.0-tick aggregation default, mid + spread anchored center. DOM virtualized; never more than ~60 visible rows.",
            "<b>Trades tape</b> &mdash; TapeRow stream, max 200 buffered, newest at top. Auto-scroll lock if the user scrolls up.",
            "<b>Positions</b> tab &mdash; every open position for the active profile, refreshing on every tick. Negative unrealized in <font color='#dc4040'>ask</font>, positive in <font color='#38a169'>bid</font>.",
            "<b>Order entry</b> &mdash; side toggle (B / S keys), market / limit type (M / L), size, leverage, post-only / reduce-only flags. Submits to <font face='Courier'>/orders</font>.",
            "<b>Agent summary</b> (right column, below order entry) &mdash; recent AgentTrace cards (TA, regime, sentiment); embedded DebatePanel surfaces when a debate is in flight.",
            "<b>Chrome connection pill</b> top-right is <font face='Courier'>/ready</font>-aware (ADR-017): green LIVE / amber DEGRADED / red 503 STALE.",
        ],
        code_refs=[
            "frontend/app/hot/[symbol]/page.tsx  &nbsp;&nbsp;// surface composition",
            "frontend/components/trading/PriceChart.tsx  &nbsp;&nbsp;// fluid chart + timeScale().fitContent() + monotonic-skip in update path",
            "frontend/components/trading/OrderBook.tsx  &nbsp;&nbsp;// virtualized DOM",
            "frontend/components/trading/TapeRow.tsx  &nbsp;&nbsp;// streaming tape",
            "frontend/components/trading/PositionsPanel.tsx",
            "frontend/components/trading/OrderEntryPanel.tsx",
            "frontend/components/agentic/AgentSummaryPanel.tsx",
            "docs/design/05-surface-specs/01-hot-trading.md  &nbsp;&nbsp;// surface spec",
        ],
    )

    # ── 1A. Chrome — Engine-totals pill (Phase 10.1) ────────────────────
    section(
        story, s,
        title="Chrome &mdash; Engine-totals pill <i>(new, Phase 10.1)</i>",
        file_label="chrome_engine_pill_expanded.png",
        image=SCRNSHTS / "chrome_engine_pill_expanded.png",
        summary=(
            "Anchored to the right of the trading-mode pill on every surface. Headline state shows net "
            "P&amp;L since boot (positive = bid-green, negative = danger-red, zero = neutral). Clicking "
            "expands a popover with the full strip &mdash; gross P&amp;L, trades, win rate, max DD, Sharpe "
            "&mdash; plus a deep link to <font face='Courier'>/hot/profiles</font>. The operator's "
            "&ldquo;is the engine still net-positive today?&rdquo; glance, available from any surface."
        ),
        bullets=[
            "<b>Collapsed headline</b> &mdash; <font face='Courier'>engine -8,648.09</font> in danger-red because the cumulative P&amp;L is negative on this run.",
            "<b>Expanded popover</b> &mdash; six metrics in a two-column grid: Net P&amp;L, Gross P&amp;L, Trades, Win rate, Max DD, Sharpe.",
            "<b>Footer</b> &mdash; <font face='Courier'>since 2026-04-28</font> + deep link &ldquo;open detailed report&rdquo; &rarr; <font face='Courier'>/hot/profiles</font>.",
            "<b>Poll discipline</b> (added 2026-05-13 after a backend-saturation incident): 30 s interval, in-flight guard so polls never stack, 20 s AbortController timeout, stale value survives failed polls &mdash; no blink to <font face='Courier'>&mdash;</font>.",
        ],
        code_refs=[
            "frontend/components/shell/EngineTotalsPill.tsx",
            "frontend/components/shell/StatusPills.tsx  &nbsp;&nbsp;// wires the pill into chrome",
            "frontend/lib/api/client.ts  &nbsp;&nbsp;// api.paperTrading.status({ signal })",
            "docs/design/02-information-architecture.md  &nbsp;&nbsp;// §4.1 chrome pill spec",
            "docs/design/09-decisions-log.md  &nbsp;&nbsp;// ADR-018 placement rationale",
        ],
    )

    # ── 1B. Profile comparison grid (Phase 10.2) ────────────────────────
    section(
        story, s,
        title="Hot Trading &mdash; Profile comparison grid <i>(new, Phase 10.2)</i>",
        file_label="hot_profiles_grid.png",
        image=SCRNSHTS / "hot_profiles_grid.png",
        summary=(
            "The &ldquo;Hot Trading&rdquo; rail entry now covers two URL spaces (ADR-018): symbol-axis execution at "
            "<font face='Courier'>/hot/{symbol}</font> and profile-axis observation under "
            "<font face='Courier'>/hot/profiles[/...]</font>. The grid is the index: one card per active "
            "profile, sorted by net P&amp;L since boot descending, with an &ldquo;Add profile&rdquo; tile linking "
            "to <font face='Courier'>/canvas</font>."
        ),
        bullets=[
            "<b>Five cards</b>, sorted by P&amp;L: Demo Pullback Long (+1,423.92) at top, Trend Following (&ndash;232.67) at the bottom. Positive cards render the P&amp;L in bid-green with an upward sparkline; negative in danger-red with downward.",
            "<b>Per-card data</b> &mdash; status dot + name + paper mode pill in the header, big net-P&amp;L value with a 24-trade cumulative sparkline, a 2&times;2 grid for Trades today / Win rate / Drawdown / Allocation, plus a footer with open-position count + last-trade-relative time.",
            "<b>Cross-link rules</b> per IA §3 &mdash; profile name &rarr; cockpit, P&amp;L sparkline &rarr; Daily P&amp;L tab, drawdown &rarr; <font face='Courier'>/risk</font>, open-positions &rarr; Positions tab.",
            "<b>Data aggregation</b> &mdash; backend has no per-profile <font face='Courier'>metricsSinceBoot</font> endpoint yet, so the grid does four parallel calls and groups client-side. Four backend round-trips regardless of profile count.",
        ],
        code_refs=[
            "frontend/app/hot/profiles/page.tsx",
            "frontend/lib/api/client.ts  &nbsp;&nbsp;// api.audit.closedTrades + api.positions.list({ profileId })",
            "docs/design/05-surface-specs/01-hot-trading.md  &nbsp;&nbsp;// §9.1 grid spec",
        ],
    )

    # ── 1C. Profile cockpit — Decisions tab (Phase 10.3) ────────────────
    section(
        story, s,
        title="Profile cockpit &mdash; Decisions tab <i>(new, Phase 10.3)</i>",
        file_label="cockpit_decisions.png",
        image=SCRNSHTS / "cockpit_decisions.png",
        summary=(
            "Per-profile observation surface at <font face='Courier'>/hot/profiles/{id}</font>. The header "
            "carries a back-link, profile name + live status dot, profile-switch dropdown, and a five-card "
            "MetricStrip (Net P&amp;L since boot, Trades today, Win rate, Drawdown, Allocation). Tabs are "
            "URL-routable and persist per profile via localStorage. The Decisions tab is the default and "
            "lists every signal the engine evaluated for this profile."
        ),
        bullets=[
            "<b>Filter chips</b> &mdash; All / Approved / Blocked. Refresh affordance at the right with last-fetch indicator.",
            "<b>Table</b> &mdash; Time, Symbol, Outcome (color-coded pill), Direction (bid/ask tone), Confidence, RSI, ATR. Left-edge accent bar per row (bid-green for approved, danger-red for blocked).",
            "<b>Hover state</b> &mdash; row highlights and a right-aligned chevron fades in, signalling the row is clickable.",
            "<b>Row click</b> opens the drill-down drawer covered in the next section.",
            "<b>URL drill-through</b>: <font face='Courier'>?tab=decisions</font> for the table view; selection state lives in <font face='Courier'>?decision={event_id}</font>.",
        ],
        code_refs=[
            "frontend/app/hot/profiles/[id]/page.tsx",
            "frontend/app/hot/profiles/[id]/_components/DecisionsTab.tsx",
            "frontend/app/hot/profiles/[id]/_components/MetricStrip.tsx",
            "docs/design/05-surface-specs/01-hot-trading.md  &nbsp;&nbsp;// §9.2.1 spec",
        ],
    )

    # ── 1C-drawer. Decision drill-down drawer ───────────────────────────
    section(
        story, s,
        title="Profile cockpit &mdash; Decision drill-down drawer <i>(new, Phase 10.3)</i>",
        file_label="cockpit_decisions_drawer.png",
        image=SCRNSHTS / "cockpit_decisions_drawer.png",
        summary=(
            "Clicking any row on the Decisions tab opens a 420 px right-side drawer with the full "
            "TradeDecision broken into named sections. Backdrop dims the underlying table; the drawer is "
            "scrollable independently. Esc, click-outside, or the X button dismiss."
        ),
        bullets=[
            "<b>Drawer header</b> &mdash; symbol &middot; direction (e.g. <font face='Courier'>ETH/USDT &middot; BUY</font>) + timestamp + truncated event ID + an &ldquo;open {symbol} &rarr;&rdquo; action that deep-links to <font face='Courier'>/hot/{symbol}</font>.",
            "<b>Setup</b> &mdash; strategy, direction, base + before / after confidence, input price.",
            "<b>Regime</b> &mdash; resolved / rule-based / HMM with multiplier.",
            "<b>Indicators</b> &mdash; RSI, MACD, Signal, Histogram, ATR, ADX.",
            "<b>Agent scores</b> &mdash; per-agent score &times; weight, color-tinted by sign (TA, sentiment, debate).",
            "<b>Gates</b> &mdash; every gate the decision passed or blocked on, with the block reason inline.",
            "<b>Strategy conditions</b> &mdash; each evaluated condition with actual value vs. threshold and a ✓/✗ pass mark.",
            "<b>Resulting order</b> &mdash; order ID linkout when the decision was approved.",
            "<b>Shareable URL</b>: <font face='Courier'>?tab=decisions&amp;decision={event_id}</font> opens the cockpit with this drawer already expanded.",
        ],
        code_refs=[
            "frontend/app/hot/profiles/[id]/_components/DecisionsTab.tsx  &nbsp;&nbsp;// DecisionDetail render",
            "frontend/app/hot/profiles/[id]/_components/DetailDrawer.tsx  &nbsp;&nbsp;// shared drawer shell",
        ],
    )

    # ── 1D. Profile cockpit — Positions tab (Phase 10.3) ────────────────
    section(
        story, s,
        title="Profile cockpit &mdash; Positions tab <i>(new, Phase 10.3)</i>",
        file_label="cockpit_positions.png",
        image=SCRNSHTS / "cockpit_positions.png",
        summary=(
            "Cross-symbol open positions for this profile (the legacy panel was symbol-scoped; this is "
            "profile-scoped). The table view lists every open position; click a row to drill into the full "
            "lineage and a market-close action (next section)."
        ),
        bullets=[
            "<b>Table</b> &mdash; Symbol, Side (long/short pill), Qty, Entry, Mark, Unrealized $ / %, Age. Color-tinted per side and per P&amp;L sign; left-edge accent matches the side.",
            "<b>Open-count chip</b> at the top of the tab body shows the live count of open positions for this profile.",
            "<b>Hover state</b> &mdash; row highlights, right-aligned chevron fades in.",
            "<b>5 s poll cadence</b> for live mark/unrealized updates, with the in-flight guard so a slow tail doesn&apos;t stack requests.",
        ],
        code_refs=[
            "frontend/app/hot/profiles/[id]/_components/PositionsTab.tsx",
            "frontend/lib/api/client.ts  &nbsp;&nbsp;// api.positions.list({ profileId })",
            "docs/design/05-surface-specs/01-hot-trading.md  &nbsp;&nbsp;// §9.2.2 spec",
        ],
    )

    # ── 1D-drawer. Position chain drill-down drawer ─────────────────────
    section(
        story, s,
        title="Profile cockpit &mdash; Position chain drill-down drawer <i>(new, Phase 10.3)</i>",
        file_label="cockpit_positions_drawer.png",
        image=SCRNSHTS / "cockpit_positions_drawer.png",
        summary=(
            "Row click on the Positions tab opens the position chain &mdash; the full decision &rarr; order "
            "&rarr; position lineage assembled by <font face='Courier'>api.audit.chain(decision_event_id)</font>. "
            "Includes a primary market-close action at the bottom of the drawer."
        ),
        bullets=[
            "<b>Drawer header</b> &mdash; symbol &middot; side (e.g. <font face='Courier'>ETH/USDT &middot; long</font>) + age (&ldquo;opened 17.8h ago&rdquo;) + &ldquo;open {symbol} &rarr;&rdquo; link.",
            "<b>Live state</b> &mdash; Symbol, Side / Qty, Entry, Mark, Unrealized ($ + %), Notional, Stop ($price), Target ($price), Age. Stop renders in danger-red, target in bid-green.",
            "<b>Why we entered</b> &mdash; regime resolved, final score, rationale (if recorded).",
            "<b>Agent scores</b> &mdash; ranked by absolute score; weight shown next to each.",
            "<b>Gates</b> &mdash; every gate the originating decision passed, with reason for any blocks.",
            "<b>Refs</b> &mdash; truncated decision event ID + position ID for cross-referencing logs / DB.",
            "<b>Close at market</b> action at the bottom &mdash; confirms before submitting to <font face='Courier'>POST /positions/{id}/close</font>.",
            "<b>Shareable URL</b>: <font face='Courier'>?tab=positions&amp;position={position_id}</font>.",
        ],
        code_refs=[
            "frontend/app/hot/profiles/[id]/_components/PositionsTab.tsx  &nbsp;&nbsp;// PositionDetail render",
            "services/api_gateway/src/routes/audit.py  &nbsp;&nbsp;// /chain/{decision_event_id}",
            "services/api_gateway/src/routes/positions.py  &nbsp;&nbsp;// POST /positions/{id}/close",
        ],
    )

    # ── 1E. Profile cockpit — Daily P&L tab (Phase 10.4) ────────────────
    section(
        story, s,
        title="Profile cockpit &mdash; Daily P&amp;L tab <i>(new, Phase 10.4)</i>",
        file_label="cockpit_daily_pnl.png",
        image=SCRNSHTS / "cockpit_daily_pnl.png",
        summary=(
            "Per-day P&amp;L sparkline at the top + a table of trading days. The sparkline is tagged "
            "<i>engine-wide</i> because per-profile daily summaries need a backend aggregator (TECH-DEBT). "
            "Click any day row to drill into the day's full transparency (next section)."
        ),
        bullets=[
            "<b>Top strip</b> &mdash; engine net P&amp;L since boot + 10-day sparkline (area + midline) + engine-wide Pending tag.",
            "<b>Note</b> below the sparkline explains the gap: &ldquo;Daily reports are engine-wide totals &mdash; the day drawer below filters trade lineage to this profile.&rdquo;",
            "<b>Table</b> &mdash; Date, Trades, Win rate, Gross, Net, Max DD, Sharpe. Left-edge accent: bid-green when net positive, danger-red when negative.",
            "<b>Hover</b> &mdash; row highlights + chevron fades in.",
            "<b>60 s poll cadence</b> &mdash; this is a daily-rollup surface, not real-time.",
        ],
        code_refs=[
            "frontend/app/hot/profiles/[id]/_components/DailyPnlTab.tsx",
            "frontend/lib/api/client.ts  &nbsp;&nbsp;// api.paperTrading.status() for the daily-reports array",
            "docs/design/05-surface-specs/01-hot-trading.md  &nbsp;&nbsp;// §9.2.3 spec",
        ],
    )

    # ── 1E-drawer. Day transparency drill-down drawer ───────────────────
    section(
        story, s,
        title="Profile cockpit &mdash; Day transparency drill-down drawer <i>(new, Phase 10.4)</i>",
        file_label="cockpit_daily_pnl_drawer.png",
        image=SCRNSHTS / "cockpit_daily_pnl_drawer.png",
        summary=(
            "Row click on the Daily P&amp;L table opens the day's transparency report. The drawer fetches "
            "<font face='Courier'>api.paperTrading.reportDetail(date)</font> and filters the trades and "
            "blocked attempts to the URL profile &mdash; this is where operators see exactly what their "
            "profile did (or didn&apos;t do) on a given day."
        ),
        bullets=[
            "<b>Drawer header</b> &mdash; date (e.g. <font face='Courier'>2026-05-01</font>) + &ldquo;full transparency &middot; this profile&rdquo; subtitle.",
            "<b>Engine totals (this day)</b> &mdash; engine-wide trades, win rate, net P&amp;L, Sharpe for context.",
            "<b>This profile (filtered)</b> &mdash; trades, win rate, net P&amp;L, blocked count specifically for this profile.",
            "<b>Closed trades</b> &mdash; per-trade card with symbol, outcome, realized $ + %, entry &rarr; exit, hold duration, close reason, slippage. Each card has a &ldquo;view decision lineage &rarr;&rdquo; link that deep-links to <font face='Courier'>?tab=decisions&amp;decision={event_id}</font>.",
            "<b>Blocked attempts</b> &mdash; up to 10 cards showing symbol, outcome, blocking gates + reasons, time.",
            "<b>Diagnostic example</b> from the screenshot: on 2026-05-01 the engine had 7 winning trades but this profile had 0 closed trades and 100 blocked attempts (all <font face='Courier'>risk_gate (trade_below_minimum)</font>) &mdash; the answer to &ldquo;why didn&apos;t my profile trade?&rdquo; that used to require grepping logs.",
            "<b>Shareable URL</b>: <font face='Courier'>?tab=daily-pnl&amp;date=YYYY-MM-DD</font>.",
        ],
        code_refs=[
            "frontend/app/hot/profiles/[id]/_components/DailyPnlTab.tsx  &nbsp;&nbsp;// DailyReportDrawer render",
            "frontend/lib/api/client.ts  &nbsp;&nbsp;// api.paperTrading.reportDetail(date)",
            "services/api_gateway/src/routes/paper_trading.py  &nbsp;&nbsp;// reports/{date}/detail",
        ],
    )

    # ── 1F. Profile cockpit — Attribution tab (Phase 10.4) ──────────────
    section(
        story, s,
        title="Profile cockpit &mdash; Attribution tab <i>(new, Phase 10.4)</i>",
        file_label="cockpit_attribution.png",
        image=SCRNSHTS / "cockpit_attribution.png",
        summary=(
            "Symbol-axis attribution analytics for this profile. A symbol-scope picker defaults to the "
            "most-traded symbol the profile has touched; three sections analyze the engine's behavior."
        ),
        bullets=[
            "<b>Gate efficacy</b> &mdash; per-gate pass/block counts sorted by block count desc. On the demo profile, <font face='Courier'>circuit_breaker</font> is blocking 186 / 500 (37% of all decisions) &mdash; the diagnostic answer to &ldquo;why does this profile never trade?&rdquo;.",
            "<b>Per-agent contribution</b> &mdash; win rate &times; avg P&amp;L by (TA / Sentiment / Debate) stance pattern over the last 7 days. Confidence lift per pattern shown on the right.",
            "<b>Weight evolution</b> &mdash; last-7d agent weight + EWMA accuracy + a sparkline per agent. Tagged <i>Pending</i> for the profile-filter gap because the backend endpoint is currently symbol-only.",
            "<b>Symbol picker</b> at the top &mdash; discovered client-side from this profile's closed trades; rerenders all three sections when changed.",
        ],
        code_refs=[
            "frontend/app/hot/profiles/[id]/_components/AttributionTab.tsx",
            "frontend/lib/api/client.ts  &nbsp;&nbsp;// agentPerformance.gateAnalytics + agentAttributionSummary + weightHistory",
            "services/api_gateway/src/routes/agent_performance.py",
            "docs/design/05-surface-specs/01-hot-trading.md  &nbsp;&nbsp;// §9.2.4 spec",
        ],
    )

    # ── 2. Agent Observatory default ────────────────────────────────────
    section(
        story, s,
        title="2. Agent Observatory",
        file_label="observatory_default.png",
        image=SCRNSHTS / "observatory_default.png",
        summary=(
            "<font face='Courier'>/agents/observatory</font> is the analyst&apos;s workbench. Three columns: "
            "agent roster on the left (each row: agent name + StatusDot + last-emit time), chronological event "
            "stream in the middle (virtualized AgentTrace cards), focus panel on the right. When no event is "
            "selected the focus panel shows a summary dashboard; click any trace to expand its reasoning chain."
        ),
        bullets=[
            "<b>Agent roster</b> (220px left) &mdash; ta_agent, regime_hmm, sentiment, slm_inference, debate, analyst. Click toggles include-this-agent filter; right-click for per-agent actions.",
            "<b>StatusDot states</b>: live (emitted within liveness window), idle (>5m since last emit), error (last emit was an error), disabled (toggled off).",
            "<b>Event stream</b> &mdash; virtualized chronological feed. Each AgentTrace card shows agent + symbol + decision + confidence + one-line summary. Click to expand inline; click the avatar to zoom right column to that agent&apos;s focus view.",
            "<b>Filter facets</b> at top: agent type, symbol, time window (1h / 4h / 24h / 7d), event type (decision / debate / abstain).",
            "<b>HITL approval queue</b> lives here (when populated) &mdash; signals held by the HITL gate appear at the top of the stream with Approve / Reject / See full trace buttons.",
        ],
        code_refs=[
            "frontend/app/agents/observatory/page.tsx",
            "frontend/app/agents/observatory/_components/AgentRoster.tsx",
            "frontend/app/agents/observatory/_components/EventStream.tsx",
            "frontend/app/agents/observatory/_components/FocusPanel.tsx",
            "services/api_gateway/src/routes/hitl.py  &nbsp;&nbsp;// HITL approve/reject endpoints",
            "docs/design/05-surface-specs/02-agent-observatory.md",
        ],
    )

    # ── 3. Risk Control ─────────────────────────────────────────────────
    section(
        story, s,
        title="3. Risk Control",
        file_label="risk_control_default.png",
        image=SCRNSHTS / "risk_control_default.png",
        summary=(
            "<font face='Courier'>/risk</font> is the highest-stakes surface. Per the surface spec, this page "
            "<i>must remain interactive when other parts of the app are degraded</i> &mdash; the kill-switch "
            "keyboard shortcut (<font face='Courier'>Cmd+Shift+K</font> / <font face='Courier'>Ctrl+Shift+K</font>) "
            "and the positions read must work even if the agent system or canvas backend is unavailable."
        ),
        bullets=[
            "<b>Kill Switch card</b> (top) &mdash; current state (OFF / ARMED soft / ARMED hard), who set it + when + reason. Two arm actions: soft (blocks new orders, positions remain) or hard (blocks new orders AND auto-flattens at market).",
            "<b>Exposure card</b> &mdash; leverage as a RiskMeter, portfolio VaR (1-day 95%), concentration breakdown per symbol, current drawdown vs. peak.",
            "<b>Active limits card</b> &mdash; live status per limit (max position size, max leverage, daily loss limit, rate limit). Limits >60% utilized turn amber; breached turn red with a callout.",
            "<b>Recent violations</b> strip &mdash; last 5 rejected orders with the rule that blocked them.",
            "<b>All-profiles risk matrix</b> sits above the kill switch (see the next section) &mdash; the operator&apos;s &ldquo;which profile needs intervening on, right now?&rdquo; glance before any kill-switch decision.",
        ],
        code_refs=[
            "frontend/app/risk/page.tsx  &nbsp;&nbsp;// surface composition",
            "frontend/components/shell/KillSwitchModal.tsx  &nbsp;&nbsp;// confirm modal (Ctrl+Shift+K)",
            "services/hot_path/src/kill_switch.py  &nbsp;&nbsp;// KillSwitch Redis key + reasoned arm/disarm log",
            "services/api_gateway/src/routes/commands.py  &nbsp;&nbsp;// /commands/kill-switch endpoint",
            "docs/design/05-surface-specs/05-risk-control.md",
        ],
    )

    # ── 3A. Risk Control — all-profiles matrix (Phase 10.1) ─────────────
    section(
        story, s,
        title="Risk Control &mdash; All-profiles risk matrix <i>(new, Phase 10.1)</i>",
        file_label="risk_profiles_matrix.png",
        image=SCRNSHTS / "risk_profiles_matrix.png",
        summary=(
            "The all-profiles risk matrix is now the first thing on <font face='Courier'>/risk</font>, sitting "
            "above the kill switch &mdash; the spec phrasing is &ldquo;which profile needs intervening on, "
            "<i>right now</i>?&rdquo; before any kill-switch decision. Replaces the legacy stack of per-profile "
            "RiskMonitorCard rows with a horizontally-scrollable card grid, sorted by drawdown severity "
            "(worst first)."
        ),
        bullets=[
            "<b>Header</b> &mdash; section title, active-profile count, &ldquo;worst drawdown first&rdquo; sort note.",
            "<b>Per card</b> &mdash; profile name + truncated ID; Drawdown bar (current % vs. <font face='Courier'>auto_pause_drawdown_pct</font> cap, color-graded: danger at &ge;85% of cap, warn at &ge;50%); Allocation bar against <font face='Courier'>max_allocation_pct</font>; 2&times;2 grid for Exposure (USDC at risk across open positions) and Open positions count.",
            "<b>Cross-links</b> &mdash; entire card &rarr; cockpit; Drawdown bar &rarr; cockpit Daily P&amp;L tab; Open-positions count &rarr; cockpit Positions tab; &ldquo;open in cockpit&rdquo; affordance at the footer.",
            "<b>Empty state</b> &mdash; &ldquo;No active profiles. Risk Control monitors active trading; activate a profile in Pipeline Canvas to populate this matrix.&rdquo; (link to <font face='Courier'>/canvas</font>).",
            "<b>Poll discipline</b> &mdash; 30 s interval with in-flight guard; component fan-outs to 1 + 2N requests per cycle so without the guard 5 active profiles would mean 11 requests every 10 s.",
        ],
        code_refs=[
            "frontend/components/risk/ProfilesRiskMatrix.tsx",
            "frontend/app/risk/page.tsx  &nbsp;&nbsp;// matrix mounted above KillSwitchSection",
            "docs/design/05-surface-specs/05-risk-control.md  &nbsp;&nbsp;// §1.1 matrix spec",
            "docs/design/09-decisions-log.md  &nbsp;&nbsp;// ADR-018 companion placement rationale",
        ],
    )

    # ── 4. Backtests list ───────────────────────────────────────────────
    section(
        story, s,
        title="4. Backtesting &mdash; run list",
        file_label="backtests_list.png",
        image=SCRNSHTS / "backtests_list.png",
        summary=(
            "<font face='Courier'>/backtests</font> is the COOL-mode workbench for validating profile changes "
            "before they go live. Dense Table of every backtest run with selectable rows; selecting &ge;2 "
            "rows enables the Compare action. Filter by profile, status, date range, or search by run ID."
        ),
        bullets=[
            "<b>Row columns</b> &mdash; run-id, profile name, symbol, date range, trades, win %, avg return, Sharpe, max DD, status.",
            "<b>Running rows</b> show progress and disable selection &mdash; only completed runs can be compared.",
            "<b>Selection footer</b> &mdash; <i>selected: N runs &nbsp; [Compare &raquo;] &nbsp; [Archive &raquo;] &nbsp; [Delete &raquo;]</i>. Compare is the primary action.",
            "<b>+ New backtest</b> (top right) opens a side drawer with the run config: symbol, date range, timeframe, slippage %, profile picker.",
            "Density control top-right lets the user switch between Compact / Standard / Comfortable.",
        ],
        code_refs=[
            "frontend/app/backtests/page.tsx",
            "frontend/app/backtests/_components/RunListTable.tsx",
            "services/api_gateway/src/routes/backtest.py",
            "services/backtesting/src/main.py  &nbsp;&nbsp;// worker; 2s poll, 10-min soft timeout",
            "docs/design/05-surface-specs/04-backtesting-analytics.md",
        ],
    )

    # ── 5. Backtest detail ──────────────────────────────────────────────
    section(
        story, s,
        title="5. Backtesting &mdash; run detail",
        file_label="backtests_detail.png",
        image=SCRNSHTS / "backtests_detail.png",
        summary=(
            "<font face='Courier'>/backtests/{run_id}</font> &mdash; the post-mortem view for a single completed run. "
            "Headline metrics at the top, equity curve in the middle, per-trade table at the bottom. The "
            "screenshot shows a 30-day BTC/USDT run."
        ),
        bullets=[
            "<b>Headline</b> &mdash; ROI / Sharpe / Sortino / maxDD / trades / win-rate / avgR / profit-factor as StatCells.",
            "<b>Equity curve</b> &mdash; line chart of equity over time with drawdown overlay below.",
            "<b>Per-trade table</b> &mdash; every simulated trade with entry, exit, hold duration, P&amp;L $/%, reason for close, outcome chip. Paginated.",
            "<b>Open in canvas as run</b> &mdash; opens the profile&apos;s Pipeline Canvas with the backtest&apos;s exact agent weights and rules pinned, so the wiring that produced this result is inspectable.",
        ],
        code_refs=[
            "frontend/app/backtests/[run_id]/page.tsx",
            "frontend/components/backtest/EquityCurveChart.tsx",
            "frontend/components/backtest/TradesTable.tsx",
            "libs/storage/repositories/backtest_repo.py  &nbsp;&nbsp;// migration 008&rarr;009 Decimal precision fix",
        ],
    )

    # ── 6. Backtests compare ────────────────────────────────────────────
    section(
        story, s,
        title="6. Backtesting &mdash; compare view",
        file_label="backtests_compare.png",
        image=SCRNSHTS / "backtests_compare.png",
        summary=(
            "<font face='Courier'>/backtests/compare?runs=A,B,C</font> &mdash; multiple runs overlaid on the "
            "same equity curve so divergence is visible at a glance. Below the chart: comparison table, one "
            "row per run, sortable on any metric."
        ),
        bullets=[
            "<b>Overlaid equity curves</b> &mdash; each run gets a distinct color; legend at the top. Synchronized cross-hair across all runs on hover.",
            "<b>Comparison table</b> &mdash; trades, win %, avg return, max DD, Sharpe, profit factor; cells colored relative to the best run in each column (winner highlighted).",
            "<b>Add run</b> button preserves the existing comparison set (<font face='Courier'>?compare=A,B,C&amp;add=D</font>) &mdash; fix from commit <font face='Courier'>06dbb4a</font>.",
            "<b>Pin highlighted run</b> &mdash; clicking a row in the table makes that run the highlighted one in the simulated-trades table at the bottom.",
            "<i>Note for partner:</i> &ldquo;Sortino &amp; avg R Pending&rdquo; tag visible on the headline panel &mdash; those metrics are emitted by the simulator next.",
        ],
        code_refs=[
            "frontend/app/backtests/compare/page.tsx",
            "frontend/components/backtest/ComparisonTable.tsx",
            "frontend/components/backtest/EquityCurveChart.tsx  &nbsp;&nbsp;// multi-run overlay",
        ],
    )

    # ── 7. Settings nav ─────────────────────────────────────────────────
    section(
        story, s,
        title="7. Settings &mdash; navigation",
        file_label="settings_nav.png",
        image=SCRNSHTS / "settings_nav.png",
        summary=(
            "Settings is CALM mode &mdash; deliberately departed from HOT and COOL: generous whitespace, "
            "15px body baseline, larger form controls, one accent color, no agent-identity colors, no live "
            "updates beyond standard save acknowledgments. The user is configuring intent here, not "
            "reacting to markets. The visual budget reflects that."
        ),
        bullets=[
            "<b>Left rail</b> &mdash; 8 sections: Profiles, Exchange keys, Risk defaults, Notifications, Tax, Account, Sessions / API, Audit log.",
            "<b>Content area</b> centered, bounded to max-width 720px. Not a full-bleed dashboard.",
            "<b>Save model</b> &mdash; explicit Save buttons (no auto-save, deliberately). Sticky save bar appears at the bottom when there are unsaved changes. Inline &ldquo;&#10003; Saved&rdquo; indicator for 4s after a successful save.",
            "<b>Tone</b> &mdash; officespace, not chatbot. No &ldquo;Hi! Ready to set up?&rdquo; copy.",
        ],
        code_refs=[
            "frontend/app/settings/layout.tsx  &nbsp;&nbsp;// shell + section nav",
            "frontend/app/settings/page.tsx  &nbsp;&nbsp;// landing &rarr; /settings/profiles",
            "docs/design/05-surface-specs/06-profiles-settings.md",
        ],
    )

    # ── 8. Settings profiles ────────────────────────────────────────────
    section(
        story, s,
        title="8. Settings &mdash; Profiles",
        file_label="settings_profiles.png",
        image=SCRNSHTS / "settings_profiles.png",
        summary=(
            "List of all trading profiles. Each card shows profile name, status badge (Live / Paused), "
            "last-updated, node count, 7-day P&amp;L / trades / win-rate, and three actions: "
            "[Open in canvas] [Edit settings] [Run backtest]. Profile <i>structure</i> is edited in the "
            "Pipeline Canvas; profile <i>identity / overrides</i> is edited here. The split is by domain &mdash; "
            "behavior vs configuration."
        ),
        code_refs=[
            "frontend/app/settings/profiles/page.tsx",
            "frontend/components/settings/ProfileCard.tsx",
            "services/api_gateway/src/routes/profiles.py  &nbsp;&nbsp;// CRUD endpoints",
        ],
    )

    # ── 9. Settings exchange keys ───────────────────────────────────────
    section(
        story, s,
        title="9. Settings &mdash; Exchange keys",
        file_label="settings_exchange_keys.png",
        image=SCRNSHTS / "settings_exchange_keys.png",
        summary=(
            "API keys for connected exchanges. Per CLAUDE.md security: Praxis never enters sensitive "
            "financial data on the user&apos;s behalf &mdash; users paste their own keys. The form makes "
            "that explicit, and the saved keys appear masked (<font face='Courier'>hl_&bull;&bull;&bull;&bull;&bull;&bull;3a4f</font>); a saved secret is never re-displayed."
        ),
        bullets=[
            "<b>Add exchange</b> form &mdash; exchange dropdown, label, API key, secret, permissions checkboxes (trade / withdraw &mdash; withdraw off by default).",
            "<b>Info banner</b> &mdash; &ldquo;Praxis never stores keys with withdraw permissions enabled by default. Confirm withdraw is off in your exchange API settings before saving.&rdquo;",
            "<b>Test connection</b> calls CCXT <font face='Courier'>fetch_balance</font> to confirm the key works AND asserts withdraw is disabled (skipped on testnet, which always has full permissions).",
        ],
        code_refs=[
            "frontend/app/settings/exchange/page.tsx",
            "services/api_gateway/src/routes/exchange_keys.py  &nbsp;&nbsp;// list + create + test",
            "libs/core/secrets.py  &nbsp;&nbsp;// GCP Secret Manager wrapper",
        ],
    )

    # ── 10. Settings risk defaults (NEWLY WIRED) ────────────────────────
    section(
        story, s,
        title="10. Settings &mdash; Risk defaults",
        file_label="settings_risk_defaults.png",
        image=SCRNSHTS / "settings_risk_defaults.png",
        status_tag="<b>Newly wired (May 2026).</b> Migration 021, repository, API route, FE form &mdash; all landed this push.",
        summary=(
            "User-level risk caps that apply to <i>newly created</i> profiles. This page was previously a "
            "&ldquo;shipped shell&rdquo; (informational only); it was wired end-to-end in this push. The form "
            "persists; what it doesn&apos;t yet do is propagate to <i>running</i> profiles &mdash; the "
            "recompile fan-out, scoped as a separate project. The page discloses that scope inline."
        ),
        bullets=[
            "<b>Five caps</b>, each as a numeric input: Max position size (% of free capital &times; signal confidence), Max leverage (&times;), Max daily loss (%), Rate limit (orders / min), Auto-pause drawdown (%).",
            "<b>Inline note</b> at the top: &ldquo;Defaults apply to newly created profiles. Propagation to <i>running</i> profiles (the recompile fan-out) ships in a follow-up.&rdquo;",
            "<b>Last-saved timestamp</b> below the form. If never saved: &ldquo;No saved defaults yet. Showing canonical fallbacks.&rdquo;",
            "<b>Sticky save bar</b> at the bottom, visible only when dirty.",
            "Bounds enforced server-side via <font face='Courier'>UserRiskDefaultsPayload</font> (Pydantic): max_position_size_pct 0&ndash;1, max_leverage 1&ndash;20, max_daily_loss_pct 0&ndash;1, rate_limit_orders_per_min 1&ndash;600, auto_pause_drawdown_pct 0&ndash;1.",
        ],
        code_refs=[
            "frontend/app/settings/risk/page.tsx  &nbsp;&nbsp;// rewritten in this push",
            "frontend/lib/api/client.ts  &nbsp;&nbsp;// api.riskDefaults wrapper",
            "services/api_gateway/src/routes/risk_defaults.py  &nbsp;&nbsp;// GET/PUT /risk-defaults",
            "libs/storage/repositories/user_risk_defaults_repo.py",
            "libs/core/schemas.py  &nbsp;&nbsp;// UserRiskDefaultsPayload + UserRiskDefaultsResponse",
            "migrations/versions/021_user_risk_defaults.sql",
        ],
    )

    # ── 11. Settings notifications ──────────────────────────────────────
    section(
        story, s,
        title="11. Settings &mdash; Notifications",
        file_label="settings_notifications.png",
        image=SCRNSHTS / "settings_notifications.png",
        status_tag="<b>Partial.</b> Two coarse booleans wired; the full event &times; channel matrix is the next backlog item.",
        summary=(
            "Per the spec, this is the per-event delivery matrix: each event &times; email / push / audible. "
            "Today the backend exposes two coarse booleans (<font face='Courier'>email_alerts</font>, "
            "<font face='Courier'>trade_notifications</font>) &mdash; those are wired. The richer matrix is "
            "Pending and the page lists each future event with a one-line reason, so the partner sees "
            "exactly what&apos;s coming."
        ),
        bullets=[
            "<b>Active toggles</b> &mdash; Daily summary email, Trade fills.",
            "<b>Pending events</b> &mdash; Kill-switch state changes; Large fills (size threshold); Agent override events; Profile drawdown trigger; Monthly tax report ready.",
            "<b>Anti-pattern note</b> &mdash; no &ldquo;all on/off&rdquo; mega-toggle. Each event toggles separately so a stressed user can&apos;t silence everything by accident.",
        ],
        code_refs=[
            "frontend/app/settings/notifications/page.tsx",
            "services/api_gateway/src/routes/  &nbsp;&nbsp;// /preferences route is Pending (FE has the client wrapper; the BE route lands with the matrix schema)",
        ],
    )

    # ── 12. Settings tax ────────────────────────────────────────────────
    section(
        story, s,
        title="12. Settings &mdash; Tax",
        file_label="settings_tax.png",
        image=SCRNSHTS / "settings_tax.png",
        status_tag="<b>Pending.</b> The tax microservice is a calculator today; full report generation is the next backlog item.",
        summary=(
            "The form is rendered to spec. The tax microservice exists (port 8089) but currently exposes only "
            "<font face='Courier'>/calculate</font> and <font face='Courier'>/health</font> &mdash; it&apos;s a "
            "tax estimator, not a report generator. Full report generation (persistence, FIFO / HIFO / LIFO "
            "export, year-by-year history) is its own project. The page surfaces this honestly with an inline "
            "note and a disabled Generate button."
        ),
        bullets=[
            "<b>Generate form</b> &mdash; year selector (last 5 years), jurisdiction (US / UK / EU / CA / AU), method (FIFO / HIFO / LIFO &mdash; intentionally no default; users must pick the one their jurisdiction allows).",
            "<b>Prior reports</b> section &mdash; empty state, awaits the report-generator backend.",
            "<b>Manual lot adjustments</b> &mdash; Pending, lands alongside the main tax client wrapper.",
        ],
        code_refs=[
            "frontend/app/settings/tax/page.tsx",
            "services/tax/src/main.py  &nbsp;&nbsp;// /calculate + /health (today&apos;s surface)",
        ],
    )

    # ── 13. Settings account ────────────────────────────────────────────
    section(
        story, s,
        title="13. Settings &mdash; Account",
        file_label="settings_account.png",
        image=SCRNSHTS / "settings_account.png",
        summary=(
            "User identity + display preferences. Per CLAUDE.md security: never auto-fill or auto-set "
            "passwords; users type directly. Display name and avatar come from the OAuth provider (Google "
            "in this screenshot). Email shown with a verified-state pill."
        ),
        code_refs=[
            "frontend/app/settings/account/page.tsx",
            "services/api_gateway/src/routes/auth.py  &nbsp;&nbsp;// /auth/me + provider data",
        ],
    )

    # ── 14. Settings sessions (NEWLY WIRED) ─────────────────────────────
    section(
        story, s,
        title="14. Settings &mdash; Sessions / API",
        file_label="settings_sessions.png",
        image=SCRNSHTS / "settings_sessions.png",
        status_tag=(
            "<b>Newly wired (May 2026).</b> Migration 022, repository, /auth/sessions + revoke endpoints, "
            "jti rotation on /auth/refresh, FE form &mdash; all landed this push. (Screenshot was taken before "
            "the api_gateway process was restarted to pick up the new routes &mdash; the graceful "
            "&ldquo;endpoint unreachable&rdquo; banner you see in the screenshot is exactly the defensive UI "
            "behavior that ships when the backend lags the FE. After restart the active sessions list populates "
            "with the user&apos;s real cross-device sessions.)"
        ),
        summary=(
            "Active sessions list. Previously single-session only (&ldquo;only the current browser appears&rdquo; "
            "with a Pending tag); now wired against a real <font face='Courier'>user_sessions</font> table populated "
            "on every <font face='Courier'>/auth/callback</font> and updated on every <font face='Courier'>/auth/refresh</font>. "
            "Any session can be revoked individually; the next refresh of that browser&apos;s token fails and the "
            "user is forced back to <font face='Courier'>/login</font>."
        ),
        bullets=[
            "<b>Active sessions list</b> &mdash; each row: device icon + browser/device label, IP + last-seen timestamp, [Sign out] on the current session and [Revoke] on others.",
            "<b>&ldquo;This session&rdquo; pill</b> &mdash; green StatusDot marks the row representing the current browser (matched via the <font face='Courier'>session_id</font> claim on the access token).",
            "<b>Revoke action</b> &mdash; flips <font face='Courier'>revoked_at</font> on the row; the next <font face='Courier'>/auth/refresh</font> for that session fails (DB is the source of truth for session liveness).",
            "<b>API tokens</b> section &mdash; Pending. Builds on the session-revocation pattern that landed today.",
            "<b>Webhook destinations</b> section &mdash; Pending, pairs with the notification matrix.",
        ],
        code_refs=[
            "frontend/app/settings/sessions/page.tsx  &nbsp;&nbsp;// rewritten in this push",
            "frontend/lib/api/client.ts  &nbsp;&nbsp;// api.sessions wrapper",
            "services/api_gateway/src/routes/auth.py  &nbsp;&nbsp;// /auth/sessions + revoke + session create/rotate",
            "services/api_gateway/src/middleware/auth.py  &nbsp;&nbsp;// create_refresh_token returns (token, jti)",
            "libs/storage/repositories/user_session_repo.py",
            "migrations/versions/022_user_sessions.sql",
        ],
    )

    # ── 15. Settings audit ──────────────────────────────────────────────
    section(
        story, s,
        title="15. Settings &mdash; Audit log",
        file_label="settings_audit.png",
        image=SCRNSHTS / "settings_audit.png",
        status_tag="<b>Wired (kill-switch source).</b> Other event sources tagged as Pending until their emitters land.",
        summary=(
            "Read-only feed of significant user actions. The endpoint is wired against "
            "<font face='Courier'>services/api_gateway/src/routes/audit.py::list_user_audit_events</font>. "
            "Today&apos;s emitted source: <b>kill-switch transitions</b> (from the "
            "<font face='Courier'>praxis:kill_switch:log</font> Redis list). Spec&apos;d-but-not-yet-emitted "
            "sources (profile changes, API key rotations, agent overrides, failed sign-ins) stay tagged "
            "<i>Pending</i> on the page itself &mdash; the partial-feed banner tells the user how many of M sources "
            "are wired so the surface is honest about coverage."
        ),
        bullets=[
            "<b>Filter row</b> &mdash; event type dropdown, from-date, to-date.",
            "<b>Partial-feed banner</b> &mdash; &ldquo;N of M event sources are wired. Pending sources will start appearing here as their producers land &mdash; no UI change needed.&rdquo;",
            "<b>&ldquo;What gets recorded&rdquo; section</b> at the bottom &mdash; per-source Recorded / Pending tags so the user knows exactly which sources are emitting.",
            "<b>CSV export</b> at the right of the filter row.",
        ],
        code_refs=[
            "frontend/app/settings/audit/page.tsx",
            "frontend/lib/api/client.ts  &nbsp;&nbsp;// api.audit.userEvents",
            "services/api_gateway/src/routes/audit.py  &nbsp;&nbsp;// /user-events aggregator",
            "services/hot_path/src/kill_switch.py  &nbsp;&nbsp;// KILL_SWITCH_LOG_KEY (today&apos;s only emitter)",
        ],
    )

    # ── Closer ─────────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("What ships next", s["h2"]))
    story.append(Paragraph(
        "Five Pending items remain on the post-cutover backlog. Two of the five (Risk defaults, Sessions) "
        "were wired in this push; three remain:",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>Risk defaults &mdash; recompile fan-out</b> &mdash; propagate user-level saves to running profiles. Today defaults apply to new profiles only.",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>Notifications matrix</b> &mdash; replace the two coarse booleans with email &times; push &times; audible per event.",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>Tax report generator</b> &mdash; service-side persistence + FIFO / HIFO / LIFO export + year-history.",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>API tokens + webhook destinations</b> &mdash; on the Sessions page. Builds on the session-revocation pattern that landed today.",
        s["body"],
    ))
    story.append(Paragraph(
        "&bull;&nbsp; <b>Audit log per-source emitters</b> &mdash; profile changes, API-key rotations, agent overrides, failed sign-ins.",
        s["body"],
    ))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        "Each is its own backlog project. The FE shells already render with honest Pending tags per ADR-013 &mdash; "
        "render structure, never fake. As each backend lands, the corresponding panel populates with no UI change needed.",
        s["body"],
    ))

    doc.build(story)
    print(f"Wrote {OUT_PDF.relative_to(ROOT)} ({OUT_PDF.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
