"""Generic Markdown → PDF builder.

Reads a markdown file and emits a PDF next to it using reportlab. Supports
the constructs used across Praxis docs: ATX headings (h1–h4), paragraphs
with inline bold / italic / code / links, bulleted and numbered lists,
GFM-style tables, fenced code blocks, blockquotes, horizontal rules.

Usage:
    python scripts/build_md_pdf.py docs/STRATEGY_GAP_ANALYSIS.md
    python scripts/build_md_pdf.py docs/foo.md -o docs/foo.pdf

Counterpart-by-convention to scripts/build_ui_walkthrough_redesign_pdf.py
(which is bespoke per-doc). This one is content-agnostic — drop any MD
file in and get a PDF.

Dependencies (system Python — the existing walkthrough builders use the
same): `pip install reportlab markdown`.
"""
from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

import markdown as md_lib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PAGE_W, PAGE_H = LETTER
MARGIN = 0.6 * inch
USABLE_W = PAGE_W - 2 * MARGIN


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=13.5,
        alignment=TA_LEFT,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a1a"),
    )
    h1 = ParagraphStyle(
        "H1",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        spaceBefore=4,
        spaceAfter=10,
        textColor=colors.HexColor("#0b3d2e"),
    )
    h2 = ParagraphStyle(
        "H2",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14.5,
        leading=18,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.HexColor("#0b3d2e"),
    )
    h3 = ParagraphStyle(
        "H3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#222"),
    )
    h4 = ParagraphStyle(
        "H4",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        spaceBefore=6,
        spaceAfter=3,
        textColor=colors.HexColor("#444"),
    )
    bullet = ParagraphStyle(
        "Bullet",
        parent=body,
        leftIndent=14,
        bulletIndent=2,
        spaceAfter=3,
    )
    ordered = ParagraphStyle(
        "Ordered",
        parent=body,
        leftIndent=18,
        bulletIndent=2,
        spaceAfter=3,
    )
    code = ParagraphStyle(
        "Code",
        parent=body,
        fontName="Courier",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#222"),
        backColor=colors.HexColor("#f4f4f4"),
        borderColor=colors.HexColor("#e0e0e0"),
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=8,
        leftIndent=4,
        rightIndent=4,
    )
    quote = ParagraphStyle(
        "Quote",
        parent=body,
        leftIndent=14,
        textColor=colors.HexColor("#555"),
        borderColor=colors.HexColor("#cfd4d9"),
        spaceAfter=8,
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=body,
        fontSize=8.5,
        leading=10.5,
        spaceAfter=0,
    )
    table_header = ParagraphStyle(
        "TableHeader",
        parent=table_cell,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0b3d2e"),
    )
    return {
        "body": body, "h1": h1, "h2": h2, "h3": h3, "h4": h4,
        "bullet": bullet, "ordered": ordered, "code": code, "quote": quote,
        "table_cell": table_cell, "table_header": table_header,
    }


# ---------------------------------------------------------------------------
# Inline HTML → reportlab markup
# ---------------------------------------------------------------------------

class _InlineConverter(HTMLParser):
    """Convert the inline HTML that python-markdown emits (<strong>, <em>,
    <code>, <a href>, <br>) into reportlab Paragraph markup (<b>, <i>,
    <font face='Courier'>, <link>, <br/>).

    Block-level tags (<p>, <li>, <h1>, etc.) are stripped — the block walker
    handles them. Anything we don't recognise is dropped silently rather
    than crashing on a quirk of a downstream markdown extension.
    """

    _INLINE_OPEN = {
        "strong": "<b>",
        "b": "<b>",
        "em": "<i>",
        "i": "<i>",
        "code": "<font face='Courier' size='9' color='#a02020'>",
        "br": "<br/>",
    }
    _INLINE_CLOSE = {
        "strong": "</b>",
        "b": "</b>",
        "em": "</i>",
        "i": "</i>",
        "code": "</font>",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = next((v for k, v in attrs if k == "href"), "")
            self._out.append(f"<link href='{_esc_attr(href)}' color='#0a66c2'>")
        elif tag in self._INLINE_OPEN:
            self._out.append(self._INLINE_OPEN[tag])
        # block-level / unknown — drop

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._out.append("</link>")
        elif tag in self._INLINE_CLOSE:
            self._out.append(self._INLINE_CLOSE[tag])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self._out.append("<br/>")

    def handle_data(self, data: str) -> None:
        self._out.append(_esc_text(data))

    def result(self) -> str:
        return "".join(self._out)


def _esc_text(s: str) -> str:
    """Escape characters with special meaning to reportlab's mini-markup."""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def _esc_attr(s: str) -> str:
    return _esc_text(s).replace("'", "&#39;").replace('"', "&quot;")


def _inline_to_rl(html_fragment: str) -> str:
    conv = _InlineConverter()
    conv.feed(html_fragment)
    return conv.result()


# ---------------------------------------------------------------------------
# Block-level parser
# ---------------------------------------------------------------------------
#
# We parse the markdown source line-by-line rather than walking python-markdown's
# HTML tree because the line-oriented approach gives clean handling of tables,
# code blocks, lists, and HR — and the inline content of each block is the only
# place we need python-markdown (via the inline converter above).

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_HR_RE = re.compile(r"^\s*(---+|\*\*\*+|___+)\s*$")
_FENCE_RE = re.compile(r"^\s*```(.*)$")
_UL_RE = re.compile(r"^(\s*)([-*+])\s+(.+)$")
_OL_RE = re.compile(r"^(\s*)(\d+)\.\s+(.+)$")
_BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _render_inline(text: str) -> str:
    """Convert a single line of markdown inline content to reportlab markup."""
    html = md_lib.markdown(text, extensions=[])
    # Strip the wrapping <p>...</p> python-markdown adds for single lines.
    html = re.sub(r"^\s*<p>", "", html)
    html = re.sub(r"</p>\s*$", "", html)
    return _inline_to_rl(html)


def _split_table_row(line: str) -> list[str]:
    raw = line.strip()
    if raw.startswith("|"):
        raw = raw[1:]
    if raw.endswith("|"):
        raw = raw[:-1]
    # Honour \| as a literal pipe inside a cell. Replace, split, restore.
    raw = raw.replace(r"\|", "\x00")
    cells = [c.strip().replace("\x00", "|") for c in raw.split("|")]
    return cells


def _build_table(header: list[str], rows: list[list[str]], styles: dict) -> Table:
    """Render a parsed markdown table as a reportlab Table that fits USABLE_W."""
    ncols = max(len(header), max((len(r) for r in rows), default=0))
    header = header + [""] * (ncols - len(header))
    rows = [r + [""] * (ncols - len(r)) for r in rows]

    # Column widths: equal share. Tables in this codebase tend to be matrix-
    # like (gap matrix) and look fine with equal columns; the alternative is
    # a content-length heuristic which is fiddly and rarely better.
    col_w = USABLE_W / ncols

    def _cell(text: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(_render_inline(text), style)

    data = [[_cell(h, styles["table_header"]) for h in header]]
    for r in rows:
        data.append([_cell(c, styles["table_cell"]) for c in r])

    tbl = Table(data, colWidths=[col_w] * ncols, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3ef")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#0b3d2e")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#dcdfe3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _hr_flowable() -> Table:
    t = Table([[""]], colWidths=[USABLE_W], rowHeights=[1])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd4d9"))]))
    return t


def _flush_list(story: list, items: list[tuple[int, str, bool]], styles: dict) -> None:
    """Flush a buffered list. Each item is (indent, content, ordered)."""
    if not items:
        return
    ordered = items[0][2]
    style_key = "ordered" if ordered else "bullet"
    for idx, (_indent, content, _o) in enumerate(items, start=1):
        bullet = f"{idx}." if ordered else "&bull;"
        story.append(Paragraph(
            f"{bullet}&nbsp;&nbsp;{_render_inline(content)}",
            styles[style_key],
        ))
    items.clear()


def parse_markdown_to_flowables(md_text: str, styles: dict) -> list:
    lines = md_text.replace("\r\n", "\n").split("\n")
    story: list = []
    i = 0
    list_buf: list[tuple[int, str, bool]] = []
    paragraph_buf: list[str] = []
    blockquote_buf: list[str] = []

    def flush_paragraph():
        if paragraph_buf:
            text = " ".join(paragraph_buf).strip()
            paragraph_buf.clear()
            if text:
                story.append(Paragraph(_render_inline(text), styles["body"]))

    def flush_blockquote():
        if blockquote_buf:
            text = " ".join(blockquote_buf).strip()
            blockquote_buf.clear()
            if text:
                story.append(Paragraph(_render_inline(text), styles["quote"]))

    def flush_all():
        flush_paragraph()
        flush_blockquote()
        _flush_list(story, list_buf, styles)

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        m = _FENCE_RE.match(line)
        if m:
            flush_all()
            buf: list[str] = []
            i += 1
            while i < len(lines) and not _FENCE_RE.match(lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1  # consume closing fence (if present)
            code_text = _esc_text("\n".join(buf)).replace("\n", "<br/>").replace(" ", "&nbsp;")
            story.append(Paragraph(code_text, styles["code"]))
            continue

        # Horizontal rule
        if _HR_RE.match(line):
            flush_all()
            story.append(Spacer(1, 4))
            story.append(_hr_flowable())
            story.append(Spacer(1, 6))
            i += 1
            continue

        # Heading
        m = _HEADING_RE.match(line)
        if m:
            flush_all()
            level = len(m.group(1))
            text = m.group(2)
            key = f"h{min(level, 4)}"
            story.append(Paragraph(_render_inline(text), styles[key]))
            i += 1
            continue

        # Table — look ahead for separator row
        if "|" in line and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1]):
            flush_all()
            header = _split_table_row(line)
            i += 2  # skip separator
            rows: list[list[str]] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_split_table_row(lines[i]))
                i += 1
            story.append(Spacer(1, 4))
            story.append(_build_table(header, rows, styles))
            story.append(Spacer(1, 6))
            continue

        # Blockquote
        m = _BLOCKQUOTE_RE.match(line)
        if m:
            flush_paragraph()
            _flush_list(story, list_buf, styles)
            blockquote_buf.append(m.group(1))
            i += 1
            continue
        else:
            flush_blockquote()

        # Unordered list
        m = _UL_RE.match(line)
        if m:
            flush_paragraph()
            if list_buf and list_buf[0][2]:  # ordered → switching
                _flush_list(story, list_buf, styles)
            indent = len(m.group(1))
            list_buf.append((indent, m.group(3), False))
            i += 1
            continue

        # Ordered list
        m = _OL_RE.match(line)
        if m:
            flush_paragraph()
            if list_buf and not list_buf[0][2]:  # unordered → switching
                _flush_list(story, list_buf, styles)
            indent = len(m.group(1))
            list_buf.append((indent, m.group(3), True))
            i += 1
            continue

        # Blank line — paragraph / list separator
        if not line.strip():
            flush_all()
            i += 1
            continue

        # Default: accumulate into paragraph
        _flush_list(story, list_buf, styles)
        paragraph_buf.append(line.strip())
        i += 1

    flush_all()
    return story


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build(md_path: Path, pdf_path: Optional[Path] = None) -> Path:
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")
    if pdf_path is None:
        pdf_path = md_path.with_suffix(".pdf")

    md_text = md_path.read_text(encoding="utf-8")
    styles = _build_styles()
    story = parse_markdown_to_flowables(md_text, styles)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=md_path.stem.replace("_", " ").replace("-", " "),
        author="Praxis Trading",
    )
    doc.build(story)
    return pdf_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert a markdown file to PDF.")
    ap.add_argument("md_path", type=Path, help="Path to the .md file")
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="Output PDF path (default: same stem, .pdf)")
    args = ap.parse_args()

    out = build(args.md_path, args.output)
    size_kb = out.stat().st_size / 1024
    print(f"Built {out} ({size_kb:,.1f} KB)")


if __name__ == "__main__":
    main()
