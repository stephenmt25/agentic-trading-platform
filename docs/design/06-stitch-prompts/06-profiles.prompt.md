# Stitch Prompt — Profiles & Settings Surface

## VIBE

Design a screen that feels like a research vessel's office space — calm, considered, and explicitly different from the cockpit. The lights are slightly brighter (less black, more deep gray), the typography is one step larger, controls are roomier. The user is editing intent, not reacting to markets. Stripe-API-docs energy with Linear's typographic restraint. Workmanlike and professional. Anti-marketing — no friendly hellos, no celebratory checkmarks, no illustrated empty-state mascots.

## DETAILED PROMPT

Generate a desktop settings UI named "Profiles & Settings" for the Praxis trading platform. Viewport 1440×900px.

**Background, typography, color rules:**
- Background slightly lighter than other surfaces: #0f0f12 (NOT #0b0b0d). The intent is "less black" — workmanlike, not dramatic.
- Inter font; body baseline 15px (one step larger than other surfaces).
- Same neutral palette + ONE accent (indigo #6366f1). NO bid/ask/agent colors on this surface — those don't belong in CALM mode.

**Layout — two columns:**

1. **Far-left rail** (56px, six-icon stack; ⚙ gear icon highlighted with indigo bar)

2. **Settings nav column** — 220px wide. A vertical list of section links:
   - Profiles (selected — indigo left bar, subtle bg fill)
   - Exchange keys
   - Risk defaults
   - Notifications
   - Tax
   - Account
   - Sessions / API
   - Audit log

3. **Main content** — flexible width, but content is bounded to max-width 720px and CENTERED within the available space. NOT full-bleed.

   **Show the "Profiles" section** with content:

   - **Header**: "Profiles" in 24px display semibold. Subtitle "Trading profiles compose pipelines into named strategies. Edit pipeline structure in Pipeline Canvas; configure other settings here." in 14px regular muted. Right side: a "[+ New profile]" button (ghost with indigo intent on hover).

   - **Filter bar**: small tab-like row "All (6) · Active (1) · Paused (3) · Archived (2)" with "Active" selected.

   - **Profile cards** — a vertical list of 3 profile cards, each card #18181b bg with 1px #27272a border, 8px corner, 24px internal padding:

     **Card 1: Aggressive-v3** (active)
     - Header row: title "Aggressive-v3" in 18px semibold + a small "● Live" pill in emerald
     - Meta row: "Updated 2h ago · 14 nodes · 5 agents" in 13px muted
     - "Last 7 days" subheading
     - Three inline metrics (KeyValue style): "PnL: +234.56 USDC" (emerald value, label muted) / "Trades: 42" / "Win rate: 58%"
     - Action row: "[Open in canvas ▸]   [Edit settings ▸]   [Run backtest ▸]" — three ghost text-buttons spaced apart, indigo on hover

     **Card 2: Conservative-v1** (paused)
     - Header: "Conservative-v1" + "⏸ Paused" pill in amber
     - Meta: "Updated 1d ago · 6 nodes · 1 agent"
     - Last 7 days metrics with neutral PnL
     - Same actions

     **Card 3: Experimental-v0** (paused)
     - Header: "Experimental-v0" + "⏸ Paused" pill
     - Meta: "Updated 6d ago · 9 nodes · 3 agents"
     - Last 7 days metrics
     - Same actions

   Each card has subtle hover state (border becomes #3f3f46, slight lift via shadow).

**Visual character:**
- Notably calmer and lighter feeling than other surfaces, while remaining dark
- Generous whitespace; rows breathe
- Type rhythm should feel like reading reference documentation, not a dashboard
- All controls (buttons, inputs) one size larger than HOT mode
- One accent color (indigo) used very sparingly — for hover affordances, the new-profile button, the active section indicator

**Critical UX rule — show, but don't enable, sensitive flows:** there should be a small icon or note near the "Edit settings" button on the active profile saying "(some changes require disarming kill switch)" — this surface is configural, but the platform respects safety constraints.

## REFERENCE NOTES

Priority reference uploads:
1. `08-reference-library/images/13-stripe-dashboard.png` — settings IA, generous whitespace
2. `08-reference-library/images/17-linear-settings.png` — settings nav + content layout
3. `08-reference-library/images/18-mercury-dashboard.png` — calm, monochrome accent

## ANTI-PROMPT

```
DO NOT generate:
  - "Welcome!" hero banner copy
  - illustrated empty-state mascots
  - hyperlinked card titles styled in saturated brand color (titles stay neutral)
  - mobile-shaped narrow column layouts (this is desktop)
  - emoji-driven categorization
  - chat-style "ask AI" widget on the settings page
  - playful celebratory animations on save
```
