# Praxis Trading Platform -- Design System

This document is the single source of truth for visual design decisions across the Praxis Trading Platform frontend. Every component, page, and future feature should conform to these tokens and patterns.

---

## Color Tokens

All colours are defined as CSS custom properties in `app/globals.css` using OKLCH colour space. Dark mode is the primary (and currently only) theme. Colours are referenced via Tailwind utility classes that map to these variables.

### Neutral Surfaces

| Token               | Value (OKLCH)            | Usage                         |
|----------------------|--------------------------|-------------------------------|
| `--background`       | `oklch(0.13 0.005 250)` | Page background               |
| `--card`             | `oklch(0.16 0.005 250)` | Card / sidebar / header       |
| `--popover`          | `oklch(0.14 0.005 250)` | Dropdown / popover background |
| `--accent`           | `oklch(0.22 0.005 250)` | Hover state, skeleton base    |
| `--muted`            | `oklch(0.19 0.005 250)` | Muted background areas        |

### Text

| Token                  | Value (OKLCH)            | Usage                             |
|------------------------|--------------------------|-----------------------------------|
| `--foreground`         | `oklch(0.96 0.005 250)` | Primary text                      |
| `--muted-foreground`   | `oklch(0.65 0.005 250)` | Secondary text, labels, metadata  |

### Primary Accent (Cool Blue)

| Token                   | Value (OKLCH)            | Usage                          |
|-------------------------|--------------------------|--------------------------------|
| `--primary`             | `oklch(0.60 0.14 240)`  | CTA buttons, active nav, links |
| `--primary-foreground`  | `oklch(0.98 0 0)`       | Text on primary background     |

### Borders

| Token        | Value (OKLCH)            | Usage                    |
|--------------|--------------------------|--------------------------|
| `--border`   | `oklch(0.23 0.005 250)` | All borders              |
| `--input`    | `oklch(0.23 0.005 250)` | Input field borders      |

### Semantic Colours (Hard-coded, Not Tokens)

| Colour               | Tailwind Class     | Usage                            |
|----------------------|--------------------|----------------------------------|
| Emerald 500          | `text-emerald-500` | Profit, positive, uptrend, pass  |
| Red 500              | `text-red-500`     | Loss, negative, downtrend, error |
| Amber 500            | `text-amber-500`   | Warning, medium risk, high vol   |

**Rule: Maximum 3 semantic hues.** No purple, no teal, no orange. Only emerald, red, and amber.

### Destructive

| Token                       | Value (OKLCH)            | Usage                |
|-----------------------------|--------------------------|----------------------|
| `--destructive`             | `oklch(0.57 0.20 27)`   | Destructive actions  |
| `--destructive-foreground`  | `oklch(0.98 0 0)`       | Text on destructive  |

---

## Typography Scale

Font stack: **IBM Plex Sans** (UI text) + **IBM Plex Mono** (numbers, code, IDs).

All sizes are fixed pixel values, not fluid. Defined in `app/globals.css` via utility overrides.

| Class      | Size  | Line Height | Usage                        |
|------------|-------|-------------|------------------------------|
| `text-xs`  | 11px  | 1.45        | Labels, metadata, timestamps |
| `text-sm`  | 13px  | 1.5         | Body text, table cells       |
| `text-base`| 14px  | 1.6         | Default (html root)          |
| `text-lg`  | 16px  | 1.5         | Section headers              |
| `text-xl`  | 18px  | 1.4         | Page titles                  |
| `text-2xl` | 22px  | 1.3         | Primary metrics, hero numbers|

### Rules

- **ALL numbers** use `font-mono tabular-nums` for proper column alignment
- Section headers use `uppercase text-xs font-semibold text-muted-foreground tracking-wider`
- Page titles use `text-xl font-semibold tracking-tight text-foreground`
- Font smoothing: `antialiased` on WebKit, `grayscale` on Firefox

---

## Spacing Scale

Based on Tailwind's default 4px unit. Only these values are used:

| Tailwind | Pixels | Usage                          |
|----------|--------|--------------------------------|
| `gap-1`  | 4px    | Tight inline spacing           |
| `gap-2`  | 8px    | Related items, icon gaps       |
| `gap-3`  | 12px   | Card internal sections         |
| `gap-4`  | 16px   | Standard section spacing       |
| `gap-6`  | 24px   | Major section gaps, grid gaps  |
| `gap-8`  | 32px   | Page-level section separation  |
| `gap-12` | 48px   | Hero-level spacing             |

### Padding Convention

- **Mobile**: `p-3` (12px) for page content
- **Desktop**: `p-6` (24px) for page content
- Pattern: `p-3 md:p-6`

---

## Breakpoints

| Name    | Range         | Layout                                  |
|---------|---------------|-----------------------------------------|
| Mobile  | < 768px       | Single column, hamburger nav, card tables |
| Tablet  | 768px--1024px | Two columns where sensible              |
| Desktop | >= 1024px     | Multi-panel layout, sidebar nav visible |

### Responsive Patterns

- Grid: `grid-cols-1 lg:grid-cols-2` or `grid-cols-1 xl:grid-cols-3`
- Sidebar: `hidden md:flex` (desktop only)
- Mobile nav: Slide-out overlay, `md:hidden`
- Tables: Horizontal scroll wrapper on mobile (`overflow-x-auto`)

---

## Component Patterns

### Section Container

```html
<section className="border border-border rounded-md p-4 md:p-6">
```

### Table Header Cell

```html
<th className="text-xs uppercase text-muted-foreground font-medium px-4 py-2.5">
```

Numerical columns add `text-right`.

### Table Body Cell

```html
<td className="px-4 py-2.5 text-sm">
```

Numerical cells add `text-right font-mono tabular-nums`.

### Primary Button

```html
<button className="bg-primary text-primary-foreground rounded-md min-h-[44px] px-4 font-medium hover:bg-primary/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
```

### Secondary / Outline Button

```html
<button className="border border-border text-foreground rounded-md min-h-[44px] px-4 hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
```

### Input Field

```html
<input className="border border-border bg-background rounded-md min-h-[44px] px-3 py-2.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
```

### Skeleton Loader

```html
<div className="bg-accent animate-pulse rounded-md h-14" />
```

### Error State

```html
<div className="border border-destructive/30 text-red-500 rounded-md p-3 flex items-start gap-2">
  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
  <span className="text-sm">Error message here</span>
</div>
```

### Empty State

```html
<div className="text-muted-foreground text-sm text-center py-8">
  No data available.
</div>
```

### Section Header (Uppercase Label)

```html
<h2 className="uppercase text-xs font-semibold text-muted-foreground tracking-wider mb-4">
  Section Title
</h2>
```

### Page Title

```html
<h1 className="text-xl font-semibold tracking-tight text-foreground border-b border-border pb-4">
  Page Title
</h1>
```

---

## Touch Targets

- Minimum **44x44px** on all interactive elements (`min-h-[44px] min-w-[44px]` for icon buttons)
- **8px minimum gap** between adjacent tap targets
- Primary actions (save, submit, run) positioned for thumb reach on mobile

---

## Animation Rules

### Allowed

| Animation                  | Where                         | Duration |
|----------------------------|-------------------------------|----------|
| `transition-colors`        | Interactive element hover     | 150ms    |
| `transition-transform`     | AlertTray slide-in/out        | 200ms    |
| `transition-[width]`       | Progress / score bars         | 500-700ms|
| `animate-pulse`            | Skeleton loaders only         | default  |
| `animate-spin`             | Auth loading spinner (1 only) | default  |
| `animate-spin` on Loader2  | Button loading states         | default  |

### Forbidden

- `animate-bounce`
- `animate-ping`
- `hover:scale-*`
- `transition-all` (too broad; use specific property)
- Spring, bounce, or decorative motion of any kind

### Reduced Motion

All animation is disabled when `prefers-reduced-motion: reduce` is set, via the global CSS rule:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## Focus States

Every interactive element uses:

```
focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary
```

This provides a visible but non-distracting focus ring that only appears for keyboard navigation (not mouse clicks). The shadcn/ui primitives (Button, Input, Badge) handle their own focus rings via `focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50`.

---

## Dark / Light Mode

- **Dark is primary** and defined in `:root, .dark`
- The `<html>` element has the `dark` class applied
- All colours use CSS custom properties, not hard-coded values (except semantic emerald/red/amber)
- **To add light mode**: define matching custom property values inside a `.light` class variant and toggle the class on `<html>`

---

## Icon System

Using **Lucide React** icons throughout.

| Context              | Size           | Example                                |
|----------------------|----------------|----------------------------------------|
| Inline with text     | `w-4 h-4`     | Icons in buttons, labels, table cells  |
| Standalone / header  | `w-5 h-5`     | Navigation icons, status indicators    |
| Small indicators     | `w-3 h-3`     | Score bar icons, chevrons in lists     |

### Rules

- All interactive icons must have either a visible text label or `aria-label`
- Purely decorative icons should be avoided; if present, mark with `aria-hidden="true"`
- Connection status indicator uses a 2x2px dot (`h-2 w-2 rounded-full`)

---

## Safe Area / Mobile

- Viewport meta includes `viewport-fit=cover` for notched devices
- Body has `padding-bottom: env(safe-area-inset-bottom)`
- No horizontal scroll at 320px minimum width
- All pages tested at mobile-first breakpoint

---

## File Reference

| File                          | Purpose                           |
|-------------------------------|-----------------------------------|
| `app/globals.css`             | Colour tokens, type scale, motion |
| `app/layout.tsx`              | Font loading, viewport, providers |
| `components/providers/AppShell.tsx` | App chrome, sidebar, header |
| `components/ui/*`             | shadcn/ui primitives              |
