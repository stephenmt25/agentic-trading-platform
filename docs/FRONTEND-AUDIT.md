# Frontend UI Audit Report — Praxis Trading Platform

**Date**: 2026-03-20
**Auditor**: Frontend Developer Agent
**Scope**: All pages, components, layout, and global styles in `aion-trading/frontend`
**Reference**: `.impeccable.md` design specification

---

## 1. Anti-Patterns Verdict — Does It Look AI-Generated?

**Yes. Substantially.** This codebase exhibits at least 12 distinct tells of AI-generated dashboard code. A professional trader or designer would identify this immediately.

### Specific tells:

| # | AI Tell | Where | Evidence |
|---|---------|-------|----------|
| 1 | **`shadow-2xl` everywhere** | Dashboard, Backtest, Paper Trading, Settings, AppShell dropdown | `.impeccable.md` explicitly says "No box shadows for visual depth." The spec is violated on nearly every `<Card>`. `shadow-2xl`, `shadow-xl`, `shadow-lg`, `shadow-sm` appear across every single page. |
| 2 | **Gradient decorative strips** | Dashboard agent cards (line 100), Paper Trading header (line 52), Settings exchange card (line 217) | `bg-gradient-to-r from-primary to-cyan-500`, `bg-gradient-to-r from-amber-500 to-amber-600`, `bg-gradient-to-r from-primary to-indigo-400`. The spec says "no decorative elements" and "colour means data, never decoration." These gradients communicate nothing. |
| 3 | **`text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400`** | Login page branding (line 31), AppShell sidebar logo (line 115) | The gradient text effect is the single most recognizable AI dashboard pattern. It screams "ChatGPT made this." |
| 4 | **Purple/violet primary color** | `globals.css` line 14: `--primary: oklch(0.55 0.20 280)` = Electric Violet | The spec explicitly lists "purple gradients" as an **anti-reference**. The entire primary color system is built on a purple/violet hue at 280 degrees. This is the opposite of what was requested. |
| 5 | **Cyan accent scattered everywhere** | Dashboard `text-cyan-400` (lines 99, 102), AgentStatusPanel `text-cyan-400` (line 99), chart colors `--chart-3: oklch(0.70 0.15 200)` | Cyan is the second most common AI dashboard color after purple. Combined, they create the classic "AI crypto dashboard" aesthetic. The spec allows max 3 hues: one neutral, one accent, one profit/loss pair. Cyan is a fourth hue. |
| 6 | **`animate-bounce` on notification badge** | AlertTray line 23 | A bouncing notification badge on a professional financial tool. The spec says to respect `prefers-reduced-motion` and disable non-essential animation. A bouncing badge is gamification. |
| 7 | **`animate-pulse` on crisis badge** | RegimeBadge line 23, RiskMonitorCard line 118 | Pulsing elements are distracting in a tool used for hours. The spec requires `prefers-reduced-motion` support. Neither animation checks this media query. |
| 8 | **`hover:scale-[1.02]` on financial data** | PnLDisplay line 34 | A P&L card that scales up on hover. This is a consumer SaaS pattern, not a trading terminal pattern. Financial data should never physically move when you interact with it. |
| 9 | **`drop-shadow-[0_0_15px_rgba(...)]` glow effects** | PortfolioSummaryCard line 38 | Neon glow on the P&L number. Again, the spec says no shadows for depth. This is decorative. |
| 10 | **`group-hover:scale-[1.6]` on background icon** | PortfolioSummaryCard line 27 | An enormous invisible TrendingUp/TrendingDown icon that scales on hover. Pure decoration. |
| 11 | **`shadow-[0_0_30px_rgba(245,158,11,0.1)]`** | Paper Trading disclaimer (line 51) | Custom amber glow shadow on the paper trading warning. Decorative shadow explicitly banned by spec. |
| 12 | **`backdrop-blur-sm` decorative blur** | PortfolioSummaryCard line 44, modals | Frosted glass effects are a consumer design pattern. Financial dashboards need sharp, clear boundaries. |

### Overall assessment:
This looks like a prompt along the lines of "build me a dark mode crypto trading dashboard" was given to an AI with no design system enforcement. The result is visually "impressive" in screenshots but fails every principle in the design specification.

---

## 2. Critical Issues

### 2.1 Accessibility — Missing ARIA and Semantic HTML

| Issue | Location | Severity |
|-------|----------|----------|
| **Modal dialogs have no ARIA roles** | Profiles page create modal (line 361), delete modal (line 422) | Critical |
| Modals use raw `<div>` with no `role="dialog"`, no `aria-modal="true"`, no `aria-labelledby` | Both modals in Profiles, Settings is not modal-based | Critical |
| **No focus trap in modals** | All modals | Critical — keyboard users can tab behind the modal into invisible content |
| **Toggle switches have no ARIA** | Settings page lines 342, 354 | Critical — `<button>` with visual-only state, no `role="switch"`, no `aria-checked` |
| **Alert tray slide panel has no ARIA** | AlertTray.tsx line 29 | Critical — `role="complementary"` or `role="dialog"` missing, no `aria-label` |
| **Sortable table header has no ARIA** | TradesTable.tsx line 43 | Critical — no `aria-sort`, no `role="columnheader"`, no keyboard activation |
| **Pagination buttons lack context** | TradesTable.tsx lines 110, 117 | High — "Prev" and "Next" have no `aria-label` indicating what they paginate |
| **Inline SVG icons have no `aria-hidden`** | Login page Google/GitHub SVGs (lines 61, 76) | High — screen readers will attempt to announce raw SVG paths |
| **`<img>` with user avatar has no meaningful alt** | AppShell line 185 — `alt="User avatar"` | Medium — should say "Profile photo for [user name]" |
| **Color-only state communication** | PnLDisplay, PortfolioSummaryCard, TradesTable, RiskMonitorCard, MetricCard | Critical — profit/loss is communicated only through green/red color, no text prefix like "Profit:" or "Loss:", no icon alternative for colorblind users |

### 2.2 Contrast Failures

| Issue | Location |
|-------|----------|
| `text-slate-600` on dark backgrounds | Login disclaimer (line 84), Settings allocation hint (line 393), Paper Trading report detail labels `text-[9px] text-slate-600` |
| `text-muted-foreground/50` and `text-muted-foreground/70` | AgentStatusPanel fallback dashes, RiskMonitorCard empty state |
| `text-slate-500` on `bg-slate-950` | Multiple locations — Login subtitle, profile dormant state |
| `opacity-50` on deleted profiles | Profiles page line 230 — entire card at 50% opacity reduces all text below WCAG AA |
| `text-[9px]` body text | Paper Trading detail labels, AgentStatusPanel labels, RiskMonitorCard labels — 9px is below WCAG minimum for body text (should be 12px minimum for readability) |

### 2.3 Touch Targets

| Issue | Location |
|-------|----------|
| Refresh button is only `p-1` (~24px) | AgentStatusPanel line 64, RiskMonitorCard line 68 — minimum 44x44px required |
| Pagination buttons at `px-3 py-1` | TradesTable lines 110, 117 — approximately 28px tall, below 44px minimum |
| Close button on modal is bare icon | Profiles create modal line 365 — `<button>` wrapping a 20px icon with no padding |
| Alert tray toggle is `p-2` | AlertTray line 18 — approximately 34px, below 44px minimum |
| User avatar button is `h-8 w-8` (32px) | AppShell line 186 — below 44px minimum |

---

## 3. High Issues

### 3.1 Hard-Coded Colors Bypassing Design Tokens

The design system defines CSS custom properties via `globals.css`, but components routinely bypass them with hard-coded Tailwind slate/indigo/cyan values:

| Hard-coded pattern | Count | Should be |
|--------------------|-------|-----------|
| `text-slate-200`, `text-slate-300`, `text-slate-400`, `text-slate-500` | 80+ occurrences | `text-foreground`, `text-muted-foreground`, or new semantic tokens |
| `bg-slate-900`, `bg-slate-950`, `bg-slate-800` | 30+ occurrences | `bg-card`, `bg-background`, `bg-secondary` |
| `border-slate-700`, `border-slate-800` | 20+ occurrences | `border-border` |
| `text-indigo-400`, `text-indigo-600`, `bg-indigo-600`, `bg-indigo-500` | 8 occurrences | `text-primary`, `bg-primary` |
| `text-cyan-400`, `text-cyan-500` | 5 occurrences | Not in the design system at all — should be removed |
| `text-violet-400`, `bg-violet-500/10` | 2 occurrences | Not in design system — should be removed |
| `#34d399`, `#f43f5e`, `#0f172a`, `#334155`, `#64748b`, `#1e293b` | EquityCurveChart.tsx | Should reference CSS variables or at minimum a shared constants file |

**Impact**: Changing the theme requires editing every file individually. A design token change in `globals.css` will have no effect on most of the UI.

### 3.2 Missing Responsive Breakpoints

| Issue | Location |
|-------|----------|
| **Sidebar is fixed 256px with no collapse** | AppShell.tsx line 114 — `w-64 shrink-0`. On tablet (768-1024px), this consumes 25-33% of the viewport. No hamburger menu, no collapse. |
| **No mobile navigation at all** | AppShell.tsx — no `md:hidden` mobile menu, no bottom tab bar. On screens below 768px, the sidebar presumably overflows or the main content is crushed. |
| **Profiles page master-detail breaks on mobile** | Profiles page line 197 — `grid-cols-1 lg:grid-cols-12` means on mobile both the list and editor stack vertically with `min-h-[600px]`, likely causing scroll issues. |
| **Paper Trading grid has `col-span-2` without responsive override** | Paper Trading line 79 — `col-span-2` is not prefixed with a breakpoint, so it may behave unexpectedly at smaller grid configurations. |
| **Header buttons crowd on mobile** | Profiles page line 183 — "Active" badge + "NEW PROFILE" button side by side with no responsive stacking. |
| **Settings tabs are vertical on all sizes** | Settings page line 141 — `md:grid-cols-4` means on mobile the tabs and content stack, but the tab buttons (`justify-start`) will look awkward full-width. |

### 3.3 Inconsistent Spacing

The spec says "one spacing scale." In practice:

- `gap-6`, `gap-8`, `gap-4`, `gap-3`, `gap-2` are used inconsistently for the same semantic purpose (section separation)
- `mb-4`, `mb-8`, `mb-12` are mixed with `gap` utility for inter-section spacing
- `p-4`, `p-5`, `p-6` are used interchangeably for card internal padding
- `py-2`, `py-3`, `py-4`, `py-5` for list items
- `space-y-3`, `space-y-4`, `space-y-6`, `space-y-8` for vertical stacking — no consistent rule

### 3.4 Exceeds Maximum 3 Color Hues

Current hue inventory:
1. **Neutral** (slate) — correct
2. **Purple/Violet** (primary, 280deg) — violates "no purple" anti-reference
3. **Emerald/Green** (profit) — correct
4. **Rose/Red** (loss) — correct
5. **Cyan** (agent names, chart accents) — fourth hue, violates 3-hue max
6. **Amber** (warnings, paper trading) — fifth hue, violates 3-hue max
7. **Violet** (sentiment badges) — sixth distinct hue

The spec allows 3: neutral + accent + profit/loss pair. The current implementation uses 6-7 distinct hues.

---

## 4. Medium Issues

### 4.1 Performance Concerns

| Issue | Location | Impact |
|-------|----------|--------|
| **Polling without visibility check** | AgentStatusPanel (15s), RiskMonitorCard (10s), AppShell WS status (2s) | All three poll continuously even when the browser tab is in the background. Should use `document.visibilityState` or `Page Visibility API`. |
| **No `React.memo` on list items** | Profile cards in Profiles page (line 222), Agent items in AgentStatusPanel (line 93), Risk items in RiskMonitorCard (line 92) | Re-renders entire list on any state change. |
| **Full profile list re-fetched after every mutation** | Profiles page — `loadProfiles()` called after create, save, toggle, and delete | Should use optimistic updates or at minimum partial cache invalidation. |
| **No virtualization on trades table** | TradesTable.tsx — client-side pagination but renders 20 rows with full DOM | Acceptable at 20 rows, but the `sorted` array copies and sorts on every render (line 18-19). Should be memoized. |
| **EquityCurveChart recalculates min/max on every render** | EquityCurveChart.tsx lines 24-26 | `Math.min(...chartData.map(...))` is O(2n) on every render. Should be `useMemo`. |
| **`useEffect` with empty deps but references `searchParams`** | Profiles page line 47 — `loadProfiles()` uses `searchParams` from closure but effect runs once | Stale closure risk. |

### 4.2 Missing Dark Mode Variants (Light Mode Broken)

The spec says "dark mode primary, light mode support secondary." However:

- `globals.css` defines only `:root, .dark` — there is no light mode variant at all. Both selectors are merged.
- `<html>` has `className="dark"` hard-coded (layout.tsx line 24)
- `<body>` uses `bg-slate-950 text-slate-200` (hard-coded dark values, not tokens)
- All hard-coded `bg-black/20`, `bg-slate-900`, `text-slate-300` etc. will look wrong on a light background
- Light mode is effectively impossible without rewriting every component

### 4.3 No `prefers-reduced-motion` Support

The spec explicitly requires this. Zero instances of `motion-reduce:` or `@media (prefers-reduced-motion)` exist in the codebase. Animations that should be gated:

- `animate-spin` on loaders (acceptable but should be reducible)
- `animate-ping` on status indicators (AppShell line 162, Profiles page line 259, AlertTray line 58)
- `animate-bounce` on notification badge (AlertTray line 23)
- `animate-pulse` on crisis badge and circuit breaker (RegimeBadge line 23, RiskMonitorCard line 118)
- `hover:scale-[1.02]` transform (PnLDisplay line 34)
- `group-hover:scale-[1.6]` transform (PortfolioSummaryCard line 27)
- `transition-transform duration-700` (PortfolioSummaryCard line 27)

### 4.4 Card-in-Card Pattern Violation

The spec says "No card-in-card patterns — flat sections with subtle dividers or whitespace only." Violations:

- Dashboard: `<Card>` containing profile cards which are `border border-border p-5 rounded-lg` (effectively cards inside cards)
- Paper Trading: `<Card>` containing `<MetricCard>` components which are `bg-black/20 p-5 border border-border rounded-lg`
- Settings: `<Card>` containing key items which are `p-4 border border-border rounded-lg bg-black/20`
- AgentStatusPanel: `<Card>` containing agent blocks which are `p-4 rounded-lg bg-black/20 border border-border/50`

---

## 5. Low Issues

### 5.1 Inconsistent Text Sizing for Labels

Label text sizes vary with no pattern:
- `text-[10px]` — backtest labels, paper trading labels, various micro-labels
- `text-[9px]` — AgentStatusPanel, RiskMonitorCard, Paper Trading detail grids
- `text-xs` (12px) — general small text
- `text-[11px]` — PnLDisplay awaiting state
- `text-sm` (14px) — body text

A design system should have a defined type scale. The arbitrary pixel values (`9px`, `10px`, `11px`) suggest ad-hoc sizing.

### 5.2 Inconsistent Uppercase Patterns

Some labels use `uppercase tracking-wider`, others use `uppercase tracking-widest`, others use `uppercase tracking-wide`. The tracking value should be standardized for all uppercase micro-labels.

### 5.3 Mixed Component Import Styles

- Some files use `@/components/ui/...` alias imports
- `JSONRuleEditor.tsx` uses `../../lib/api/client` and imports `apiClient` (not `api`)
- PnLDisplay, PortfolioSummaryCard, AgentStatusPanel use relative paths `../../lib/...`
- Pages use a mix of `../components/...` and `@/components/...`

Should be standardized to `@/` aliases everywhere.

### 5.4 Unused Component

`JSONRuleEditor.tsx` imports `apiClient` from `../../lib/api/client` — this appears to be an older version of the rule editor that has been superseded by the inline textarea in Profiles page. It references a different API pattern (`apiClient.post` vs `api.profiles.update`). May be dead code.

### 5.5 `<select>` Element Not Styled Consistently

Settings page line 373 uses a raw `<select>` with manual Tailwind classes instead of using a Shadcn UI Select component. This breaks consistency with the Input components used elsewhere.

### 5.6 Missing Error Boundaries per Route

Only one `<ErrorBoundary>` wraps the entire app (layout.tsx). A single unhandled error in any component crashes the entire dashboard. Route-level error boundaries would be more resilient.

### 5.7 Metadata Title is Stale

`layout.tsx` line 14: `title: 'Control Plane Dashboard | Phase 3'` — the "Phase 3" label is internal development language that should not appear in the browser tab of a production application.

---

## 6. Positive Findings

### 6.1 Solid Foundation Architecture

- **Next.js App Router** with proper `'use client'` directives on interactive components
- **Zustand store** for portfolio state management — lightweight and appropriate
- **WebSocket integration** with connection state tracking in the AppShell
- **Auth flow** is well-structured: public paths bypass the shell, protected routes redirect
- **Error handling** is present on every API call with user-facing toast messages

### 6.2 Good Data Patterns

- **Real-time P&L** via WebSocket with proper fallback states when data is unavailable
- **Backtest polling** with cancellation on unmount and attempt limits — prevents memory leaks
- **Risk monitoring** with visual threshold bars is genuinely useful UX for traders
- **RegimeBadge** component maps market states to clear, distinct visual representations

### 6.3 Correct Use of Monospace for Numbers

Financial values consistently use `font-mono` — prices, percentages, P&L figures, timestamps. This aligns with the spec requirement for tabular numbers.

### 6.4 Appropriate Empty/Error States

Every data-dependent component has three states: loading (spinner), error (message), empty (guidance). This is professional-grade UX and many production apps fail to do this.

### 6.5 CSS Custom Properties via OKLCH

The use of OKLCH color space in `globals.css` is technically sound and forward-looking. The token architecture is correct even though the actual color choices violate the spec.

### 6.6 Functional Component Quality

- TypeScript interfaces on all component props
- Proper cleanup in useEffect hooks (intervals, timeouts)
- Loading/saving states on all async operations prevent double-submission

---

## 7. Recommendations Mapped to Impeccable Commands

### `distill` — Remove All Decorative Elements

**Priority: IMMEDIATE**

Remove every element that exists for visual flair rather than conveying data:

1. **Delete all `shadow-*` classes** from every Card, modal, and panel. Replace with `border border-border` only. Files affected: every page and component.
2. **Delete all gradient strip decorations**: the `bg-gradient-to-r` top-bars on dashboard agent cards (page.tsx:100), paper trading header (paper-trading/page.tsx:52), settings exchange card (settings/page.tsx:217).
3. **Delete gradient text effect** on login branding (login/page.tsx:31) and sidebar logo (AppShell.tsx:115). Replace with `text-foreground` or a single-color accent.
4. **Delete the `drop-shadow` glow** on P&L numbers (PortfolioSummaryCard.tsx:38).
5. **Delete the background watermark icon** in PortfolioSummaryCard.tsx (lines 26-28) — the giant TrendingUp/TrendingDown icon at 3% opacity that scales on hover.
6. **Delete `backdrop-blur-sm`** from PortfolioSummaryCard.tsx:44 and all modal overlays.
7. **Delete `hover:scale-[1.02]`** from PnLDisplay.tsx:34.
8. **Delete the `animate-bounce`** from AlertTray.tsx:23.
9. **Delete the decorative circle** in Paper Trading MetricCard (paper-trading/page.tsx:219) — `absolute top-0 right-0 w-12 h-12 -mr-6 -mt-6 rounded-full bg-emerald-500/10`.
10. **Delete `shadow-[0_0_30px_...]`** from paper-trading/page.tsx:51.
11. **Delete `shadow-[0_0_10px_...]`** from paper-trading/page.tsx:89 progress bar.

### `colorize` — Fix the Color System

**Priority: HIGH**

1. **Change primary from purple (280deg) to a blue or neutral blue-gray**. Suggested: `oklch(0.55 0.15 230)` — a restrained steel blue that reads as professional, not "crypto startup." Update `--primary`, `--ring`, `--sidebar-primary`, `--sidebar-ring` in globals.css.
2. **Remove all cyan** (`text-cyan-400`, `text-cyan-500`, `--chart-3` at hue 200). Replace with either the primary accent or a muted foreground color.
3. **Remove all violet/purple** (`text-violet-400`, `bg-violet-500/10`). These are separate from the primary and add an extra hue.
4. **Consolidate to 3 hues**: Neutral (slate base), Accent (steel blue), Semantic (emerald for profit, rose for loss). Amber for warnings is acceptable as a semantic variant of the loss/danger hue.
5. **Replace all hard-coded hex values** in EquityCurveChart.tsx with CSS variable references or a shared `CHART_COLORS` constant.
6. **Create semantic color tokens** for: `--color-profit: oklch(0.60 0.15 160)`, `--color-loss: oklch(0.60 0.20 25)`, `--color-warning: oklch(0.70 0.15 85)`. Reference these instead of raw emerald/rose/amber classes.

### `typeset` — Standardize Typography

**Priority: HIGH**

1. **Establish a type scale** and ban arbitrary pixel sizes. Suggested: `text-[10px]` for micro-labels only (timestamps, secondary metadata). Everything else uses Tailwind's scale: `text-xs` (12px), `text-sm` (14px), `text-base` (16px).
2. **Ban `text-[9px]`** entirely — it is below readable size and fails WCAG. All instances in AgentStatusPanel, RiskMonitorCard, and Paper Trading must be bumped to `text-[10px]` minimum, preferably `text-xs`.
3. **Ban `text-[11px]`** — use `text-xs` instead (PnLDisplay.tsx:19).
4. **Standardize uppercase label pattern**: `text-[10px] uppercase font-bold tracking-widest text-muted-foreground` as a single reusable class or component (`<MicroLabel />`).
5. **Standardize heading pattern**: All page titles use `text-3xl font-black tracking-tight text-white`. This is consistent already — good. But it should reference `text-foreground` not `text-white`.

### `normalize` — Unify Component Patterns

**Priority: HIGH**

1. **Create a `<MetricCard />` shared component**. There are currently three separate implementations: Backtest MetricCard (backtest/page.tsx:318), Paper Trading MetricCard (paper-trading/page.tsx:217), and the manual grid in PortfolioSummaryCard. Unify into one.
2. **Create a `<Modal />` wrapper component** with ARIA roles, focus trap, and Escape key handling. Replace the two inline modals in Profiles page and any future modals.
3. **Create a `<PageHeader />` component** — every page repeats the same `h1` + description + border-b pattern.
4. **Replace hand-built toggle switches** (Settings page) with a proper Shadcn UI Switch component that includes `role="switch"` and `aria-checked`.
5. **Standardize all imports** to `@/` alias paths. Eliminate all `../../` relative imports.
6. **Standardize card internal padding** to a single value (`p-5` or `p-6`).
7. **Flatten card-in-card patterns** — replace nested bordered cards with flat rows separated by `border-b border-border` dividers or whitespace.

### `harden` — Fix Accessibility

**Priority: CRITICAL**

1. **Add `role="dialog"`, `aria-modal="true"`, `aria-labelledby`** to both modals in Profiles page.
2. **Implement focus trap** in all modals — when open, Tab should cycle only within the modal.
3. **Add Escape key handler** to close modals and the AlertTray slide panel.
4. **Add `role="switch"` and `aria-checked`** to toggle buttons in Settings.
5. **Add `aria-sort`** to the sortable P&L column header in TradesTable.
6. **Add `aria-hidden="true"`** to all decorative SVG icons (login page OAuth icons, lucide icons used alongside text labels).
7. **Add screen-reader-only text** for color-coded values: e.g., `<span className="sr-only">Profit</span>` before green P&L numbers, `<span className="sr-only">Loss</span>` before red ones.
8. **Increase all touch targets** to minimum 44x44px. The refresh buttons, pagination buttons, avatar button, and alert bell are all undersized.
9. **Fix contrast** on all `text-slate-600` on dark backgrounds, `text-[9px]` labels, and `opacity-50` elements. Use `text-muted-foreground` (which is `oklch(0.70 ...)`, approximately a 4.5:1 ratio against the dark background).
10. **Add `aria-label` to icon-only buttons** (refresh buttons in AgentStatusPanel, RiskMonitorCard; delete button in Settings).

### `arrange` — Fix Responsive Layout

**Priority: HIGH**

1. **Add mobile sidebar collapse**. Below `lg` breakpoint, the sidebar should collapse to a hamburger menu or slide-out drawer. The current `w-64 shrink-0` is unusable on phones.
2. **Add bottom tab navigation for mobile**. For screens below `md`, a fixed bottom bar with 5 nav items is the standard pattern for mobile trading apps.
3. **Make the Profiles master-detail responsive**. On mobile, show only the list. Tapping a profile should navigate to a full-screen editor view (or slide panel).
4. **Stack header actions vertically on mobile**. Profiles page header buttons should wrap with `flex-wrap`.
5. **Test at 320px viewport width**. The spec requires support from 320px through 2560px. The current layout is untested below tablet width.

### `animate` — Gate All Motion Behind `prefers-reduced-motion`

**Priority: HIGH**

1. **Add a global CSS rule**:
   ```css
   @media (prefers-reduced-motion: reduce) {
     *, *::before, *::after {
       animation-duration: 0.01ms !important;
       animation-iteration-count: 1 !important;
       transition-duration: 0.01ms !important;
     }
   }
   ```
2. **Or use Tailwind's `motion-reduce:` variant** on each animation: `motion-reduce:animate-none` on all `animate-ping`, `animate-pulse`, `animate-bounce`, `animate-spin` instances.
3. **Remove `hover:scale` transforms entirely** — they violate the spec's "subtract, don't add" principle regardless of motion preferences.

### `polish` — Final Pass

**Priority: LOW**

1. Fix the page title from "Control Plane Dashboard | Phase 3" to "Praxis Trading Platform" or similar production-appropriate title.
2. Remove the "PHASE 2 - OAUTH AUTHENTICATION" badge from the login page (login/page.tsx:94) — this is internal dev labeling.
3. Clean up or delete `JSONRuleEditor.tsx` if it is dead code.
4. Add `tabular-nums` to the global `font-mono` class definition so monospace numbers align in columns automatically.
5. Audit the `<select>` element in Settings and replace with Shadcn UI Select for consistency.
6. Add route-level error boundaries for each page.

---

## Summary Scorecard

| Category | Score | Notes |
|----------|-------|-------|
| Spec Compliance | 2/10 | Violates color, shadow, decoration, animation, and responsive requirements |
| Accessibility | 3/10 | No ARIA on modals, no focus traps, broken contrast, undersized touch targets |
| Visual Consistency | 4/10 | 6+ hues, inconsistent spacing, mixed hard-coded and token colors |
| Performance | 6/10 | Reasonable but polls in background, no memoization on lists |
| Code Quality | 7/10 | TypeScript, proper cleanup, good error states, but mixed import styles |
| Mobile Readiness | 2/10 | No mobile navigation, sidebar never collapses, untested below tablet |
| "Does it look AI-generated?" | Yes | 12 distinct tells identified above |

**Bottom line**: The functional architecture is solid. The data flow, state management, error handling, and API integration are well-built. But the visual layer reads as a default AI-generated dashboard. For a professional financial tool where trust and precision are paramount, the current aesthetic actively undermines credibility. The fix is subtractive — strip decoration, enforce the 3-hue constraint, flatten the card hierarchy, and fix the accessibility gaps.
