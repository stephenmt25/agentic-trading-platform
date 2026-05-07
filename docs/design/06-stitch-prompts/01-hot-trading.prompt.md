# Stitch Prompt — Hot Trading Surface

## VIBE

Design a screen that feels like the bridge of a research vessel at 3am during a volatile session. Instruments everywhere — but each instrument is calm, precisely labeled, and trustworthy. The lights are dim because the work is precise, not because we're hiding anything. When something needs the trader's attention, exactly one element glows. Built by people who have shipped production trading systems and also read Edward Tufte. Inspired by Hyperliquid's density discipline and Linear's typographic restraint, with zero "consumer crypto" feel — no gradients, no Robinhood casino energy.

## DETAILED PROMPT

Generate a desktop trading platform UI screen named "Hot Trading" for a derivatives trading platform called Praxis. The viewport is 1440×900px.

**Background:** near-black charcoal (#0b0b0d), not pure black. Panels in #0f0f12. Raised elements in #18181b.

**Typography:** Inter font family throughout. Tabular numerals enabled for all numbers. Sizes: 11px caption, 12px label, 13px body-dense (used for table data), 14px body, 24px display for primary numbers (PnL, mid-price). Numbers right-aligned everywhere.

**Color rules — strict:**
- Bid / positive PnL / own buys: emerald #10b981
- Ask / negative PnL / own sells: red-orange #ef4444
- Accent (interactive affordances): indigo-violet #6366f1, used SPARINGLY
- Warn (advisory amber): #f59e0b
- Danger (kill-switch only — distinct from ask): #dc2626
- Everything else: neutral grays from #f7f7f8 (text) to #18181b (panels)
- No other colors allowed.

**Layout — three columns on a 1440×900 viewport:**

1. **Left rail** — 56px wide, dark panel, vertical icon strip with 6 icons stacked top-to-bottom (lightning ⚡, robot face 🤖, plus-in-circle ⊕, chart 📊, shield 🛡, gear ⚙) representing six surfaces. The lightning icon is highlighted with a 2px left bar in indigo to indicate active surface.

2. **Center column** — flexible width. From top to bottom:
   - Top bar (44px tall): breadcrumb "Hot Trading > BTC-PERP", profile selector dropdown "Aggressive-v3", then a row of small status pills: green-dot "live", amber "regime: choppy", "12ms latency", amber "kill switch armed-soft", "5 agents", and PnL pill "+0.84%" in emerald. Right-aligned: search bar with "⌘K" hint, a notification bell, a user avatar.
   - Chart area (~50% of remaining height): TradingView-style candlestick chart with timeframe tabs at top (1m/5m/15m/1h/4h/1d), a small toolbar of drawing tools on the LEFT INSIDE THE CHART (pencil, line, fibonacci, eraser) — single-stroke 1.5px outline icons. Mid-price label in display-24 size at the top-right corner of the chart, flashing emerald green to indicate a recent up-tick. Volume histogram below candles in a thin strip.
   - Below the chart, a horizontal split: LEFT SIDE order book (60% width), RIGHT SIDE trades tape (40% width). Order book is split-style with asks descending from top (red row backgrounds at 12% opacity, scaled by cumulative size), bids ascending from bottom (emerald row backgrounds at 12% opacity), and a center "spread" badge "0.5 bps" in muted gray. Each row: price | size | cumulative — three columns, monospace-aligned numbers, 13px. Trades tape: streaming list of recent trades, each row with HH:MM:SS.mmm timestamp in mono, side indicator as a colored dot, size, price.
   - Bottom panel (~25% of height): tabs row "Positions (2) | Open Orders (1) | Fills | History", below tabs a dense table. Show 2 example position rows: BTC-PERP long 0.005 entry 42050 mark 42318 unrealized +1.34 USDC margin 42.32 leverage 5x; ETH-PERP short 0.12 entry 2450 mark 2438 unrealized +1.44 USDC. Each row has subtle action buttons appearing on hover: close 25%, close 50%, close 100%, edit stop, trace.

3. **Right column** — 360px fixed width. Two stacked panels:
   - **Order entry panel** (top, ~60% height): tab strip at top "Limit | Market | Stop | Algo" with Limit selected and underlined in indigo. Side selector as two large buttons "Buy" (emerald-tinted ghost) / "Sell" (red-tinted ghost), Buy is selected (filled emerald). Size input row with "0.005" entered, four small chips below "25% 50% 75% 100%". Price input "42318.27" with a tiny info note "within 0.3% of mid". Leverage slider 1× to 100× with current value 5×, the active fill in emerald (matching side). Two toggles "Reduce-only" off, "Post-only" on. Cost summary "Cost: 211.59 USDC | Margin used: 42.32 USDC" in muted text. Then a LARGE submit button at bottom — full width, 56px tall, background emerald #10b981, white text "Buy 0.005 BTC-PERP @ 42318.27", with a smaller subline "Press Enter".
   - **Agent summary panel** (bottom, ~40% height): heading "AGENTS — recent". Three collapsed agent trace cards stacked. Each card: small circular avatar with a colored ring (violet for "regime_hmm", blue for "ta_agent", teal for "slm_inference"), agent name, emit time "14:32:01", a one-line summary like "regime: choppy 0.71" or "signal: long(weak)". Last card is a Debate panel mini-card "open BTC long? round 3/5 ► live" in orange-tinted ring. "See all in Observatory ▸" link at bottom.

**Visual rules:**
- All borders: 1px solid #18181b for subtle, #27272a for strong
- All radius: 6px on cards, 4px on inputs, 2px on tags, 9999px (full) on pills
- All shadows: minimal — only on the order entry submit button (subtle elevation)
- Spacing: 4px base grid. Most paddings 8/12/16px. Cards have 16px padding.
- Density: this is the "standard" density — 28px row height in tables, 13px font in tables.

**Final character notes:**
- Looks expensive, restrained, dense, considered. NOT playful, NOT consumer-crypto, NOT "AI app builder" generic.
- Numbers are the protagonist of every visual hierarchy.
- The eye should fall first on PnL, then mid-price, then book mid, then position size.
- Empty space is structural, not decorative; every pixel earns its place but not by being loud.

## REFERENCE NOTES

If uploading reference images alongside this prompt, the priority order is:
1. `08-reference-library/images/01-hyperliquid-trading.png` — primary density reference
2. `08-reference-library/images/02-dydx-trading.png` — order entry layout reference
3. `08-reference-library/images/03-linear-app.png` — typographic discipline reference
4. `08-reference-library/images/04-bloomberg-tape.png` — trade tape monospace alignment

## ANTI-PROMPT (always include)

```
DO NOT generate:
  - rounded card aesthetics with >8px corners
  - any gradient or glassmorphism
  - emoji-heavy interface elements
  - light theme variants
  - "growing/shrinking" animation suggestions
  - generic admin-dashboard chart wrappers
  - cards-stacked-on-cards layouts
  - colored sidebar with marketing-style hover effects
```
