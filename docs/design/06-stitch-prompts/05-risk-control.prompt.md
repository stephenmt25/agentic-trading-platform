# Stitch Prompt — Risk Control Surface

## VIBE

Design a screen that feels like a vehicle's emergency control panel — high contrast, large hit areas, unmistakable consequence. The visual hierarchy is built around one element (the kill switch) that the user must be able to find and operate even under stress. Calm but ready. Like the dashboard of a research vessel where the "all stop" command lives — labeled clearly, never hidden, never decorative. Slightly larger type and more breathing room than Hot Trading; this surface optimizes for legibility under stress over information density.

## DETAILED PROMPT

Generate a desktop risk control UI named "Risk Control" for the Praxis trading platform. Viewport 1440×900px.

**Background, typography, color rules:** same dark #0b0b0d canvas, Inter font, same palette. NOTE: this surface uses slightly LARGER typography than Hot Trading — body 14px instead of 13px, display sizes one step up. More whitespace per section. Generous padding inside cards (24px instead of 16px).

**Layout — single column, max-width 960px centered:**

1. **Top bar** (44px): breadcrumb "Risk Control" with shield 🛡 icon. Below it, a chrome row of four pills: "⚖ portfolio +0.84%", "pnl 24h +1,234.56 USDC" (emerald), "leverage 2.4× / max 5×", "🛡 armed (soft)" in amber.

2. **THE KILL SWITCH section** — the centerpiece. A large card #0f0f12 bg, 1px amber #f59e0b border (because it's currently soft-armed), 6px corner radius, 24px internal padding. Internally:
   - Header row: a 32×32 shield icon on the left in amber, then "KILL SWITCH" label in 14px caption muted, with current STATE label below in 24px display semibold "ARMED (soft)" in amber #f59e0b.
   - To the right of the state, two action buttons: "[Disarm]" (large, ~120px wide, secondary ghost) and "[Hard-arm]" (large, danger red intent #dc2626).
   - Below the header row, two muted explanation lines:
     - "Soft-arm: blocks new orders. Existing positions remain."
     - "Hard-arm: blocks new orders AND auto-flattens all positions at market."
   - Footer: "Set 4m ago by you · reason: 'review'" in 11px caption muted.
   - Bottom-right, a small keyboard hint: "Cmd+Shift+K to toggle" in mono font.

3. **EXPOSURE section** — card with same bg/border/padding. Title "EXPOSURE" in 11px caption muted, 16px below the title. Four rows:
   - **Leverage row**: label "Leverage" + a horizontal segmented bar (the RiskMeter component): three segments — emerald (0–60%), amber (60–85%), red (85–100%). Width spans most of the card. A needle marker at 48% (= 2.4× of 5× max). Right side of row: "2.4× / 5.0×" tabular numerals.
   - **VaR row**: label "Portfolio VaR (1d, 95%)" + a thinner horizontal bar showing utilization, current utilization fill in muted gray (it's at -21% of equity, well within bounds). Right side: "−2,134 USDC of 10k" in mono.
   - **Concentration row**: label "Concentration" + a horizontal stacked bar with three labeled segments: "BTC 62%", "ETH 28%", "others 10%" — each segment labeled directly on the bar with its symbol and percent. Colors are NEUTRAL grays at different values, not bid/ask (these are symbols, not directions).
   - **Drawdown row**: label "Drawdown" + a small sparkline (last 30 days of equity curve) with a marker at the deepest point. Right side: "-3.2% (peak: 2026-04-12, recovered)" in muted text.

4. **ACTIVE LIMITS section** — card. Title "ACTIVE LIMITS". A list of four limit rows:
   ```
   ✓ max position size BTC: 0.5     current 0.18    [● 36% utilized]
   ✓ max leverage: 5×                current 2.4×    [● 48% utilized]
   ⚠ daily loss limit: -1,500 USDC   current -890   [● 60% utilized]   amber
   ✓ rate limit: 60 orders/min       current 4 in 1m [● 6%  utilized]
   ```
   Each row: status dot (green/amber based on utilization), limit label, current value, a thin utilization bar with text. Each row has an "edit ▸" link at the right end (muted gray, indigo on hover).

5. **RECENT VIOLATIONS section** — card. Title "RECENT VIOLATIONS". A reverse-chronological log:
   ```
   14:21   rejected: would exceed max position BTC
   09:43   rejected: rate limit (60/min)
   yesterday 22:11   warning: daily loss approaching
   ```
   Each entry: timestamp (mono, 13px), event severity icon (X for rejection, ⚠ for warning), description text. The timestamp is muted; the event description is at default fg. Each entry hovers to show "view detail ▸".

**Visual character:**
- Higher contrast than Hot Trading — slightly more breathing room
- The kill-switch card is unmistakably the visual focal point (largest, distinct border color matching state)
- Type one step larger than other HOT surfaces
- Color usage is heavy on AMBER (warn) and RED (danger), used purposefully — most of the screen remains neutral
- The user should be able to tell the kill-switch state from across the room

## REFERENCE NOTES

Priority reference uploads:
1. `08-reference-library/images/15-aviation-cockpit.png` — emergency control aesthetic
2. `08-reference-library/images/16-hyperliquid-margin.png` — RiskMeter pattern
3. `08-reference-library/images/03-linear-app.png` — typography rhythm

## ANTI-PROMPT

```
DO NOT generate:
  - "danger zone" cliche red-bordered cards with skull icons
  - oversized confirm/cancel modal previews
  - cute illustrations (NO empty-state characters)
  - playful or tutorial-tooltip aesthetics
  - light theme variants
  - dashboard cards-on-cards
  - shopping-cart-like "add to limits" UX
```
