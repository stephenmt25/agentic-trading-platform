# Design System Replication Playbook

> A how-to for rebuilding this style of design system in a different repo, for a different aesthetic. Treat the existing `docs/design/` + `frontend/components/` + `frontend/app/design-system/page.tsx` setup as the reference implementation; this playbook generalizes it.

The deliverable to replicate is the **catalog page** at `/design-system` — a single visual proof-sheet of every primitive variant — but the catalog is the *output*. The real product is the discipline upstream of it: token-bound components, written specs, ADR audit trail, mode-scoped theming. Skip the upstream and the catalog still renders, but re-skinning becomes a hex-literal hunt instead of a token swap.

---

## 1 · Mental model

Three layers, in dependency order:

```
tokens   ──→   components   ──→   surfaces
(aesthetic)    (vocabulary)       (the app)
```

- **Tokens** are where the aesthetic lives. Colors, type, motion, shadow, density.
- **Components** consume tokens. They define the *vocabulary* but not the *voice*.
- **Surfaces** compose components into pages. They define the app's information architecture, not its look.

The aesthetic-swap insight: if components are token-bound (no hex literals), changing aesthetic ≈ swap tokens + rewrite philosophy/ADRs. Components, IA, and most surface specs ride along unchanged.

This holds **only** while the *token surface shape* is preserved — same semantic vars, same mode model, same composition tiers. Changing the shape (e.g., four modes instead of three, or removing a tier) is a structural fork that ripples downward. The playbook calls these out as forks.

---

## 2 · Repo layout (target)

```
docs/design/
  00-INDEX.md
  01-design-philosophy.md         ← principles + modes + vibe
  02-information-architecture.md  ← surfaces + IA graph
  03-design-tokens/
    tokens.json                   ← canonical
    tokens.css                    ← CSS custom properties
    tailwind.preview.js           ← Tailwind preview surface
  04-component-specs/
    README.md                     ← index
    primitives.md
    data-display.md
    {domain}-specific.md          ← e.g. trading-specific.md
    {component}.md                ← e.g. chart.md when a single component earns its own file
  05-surface-specs/
    01-{surface}.md
    …
  09-decisions-log.md             ← ADRs
  11-execution-plan.md            ← phased build plan
frontend/
  DESIGN.md                       ← single load-bearing consumer-side spec
  app/
    design-tokens.css             ← in-tree copy of tokens.css
    design-system/page.tsx        ← the catalog page
  components/
    primitives/                   ← Button, Input, Tag, …
    data-display/                 ← Table, KeyValue, Sparkline, Chart, …
    {domain}/                     ← e.g. trading/, agentic/, canvas/
```

The numbered prefixes on doc files force a reading order. The composition tier directories enforce import direction — primitives can't import data-display; data-display can't import domain-specific. This is checked by convention and reviewed on PRs; an ESLint `no-restricted-imports` rule is optional but the discipline matters more than the lint.

---

## 3 · Phase 0 — Foundation decisions

Before any code or tokens, write three documents and open the ADR log.

### 3.1 Philosophy (`01-design-philosophy.md`)

5–10 numbered principles, each with:
- A one-sentence claim
- A short rationale
- An anti-pattern ("don't do X") to make the principle falsifiable

Then define **modes**. The reference implementation has three (HOT/COOL/CALM), keyed to user attention state. A new aesthetic might use modes for light/dark, or for product surfaces (workspace/admin), or have only one. Modes determine the structure of `tokens.css` (one `[data-mode="..."]` block per mode).

### 3.2 Information Architecture (`02-information-architecture.md`)

List every top-level surface. Draw the navigation graph (text or Mermaid). Decide the density default (`compact` / `standard` / `comfortable`). This document is the surface spec inventory before you write the surface specs.

### 3.3 ADR log (`09-decisions-log.md`)

Open the file empty. Append an ADR every time you make a decision worth re-explaining six months later. Format:

```markdown
## ADR-XXX — {short title}
**Date:** YYYY-MM-DD
**Status:** Accepted

### Context
Why this came up. What were we trying to solve.

### Decision
What we chose.

### Consequences
What changes downstream. What we accept as the cost.
```

Typical Phase-0 ADRs: typography choice, accent color, motion philosophy, mode model, agent-identity color rules (or whatever your domain analogue is). At least 5. If you've made fewer than 5 ADRs by the time you start coding, you haven't decided enough.

---

## 4 · Phase 1 — Token surface

The aesthetic concentrates here. Components elsewhere will inherit it through CSS custom properties.

### 4.1 Define ramps

Every color is a ramp, not a single value. Twelve steps minimum (`50, 100, 200, … 900, 950, 1000`). Reference implementation has:
- `neutral` — gray scale
- `bid` / `ask` — domain-positive / domain-negative (substitute your domain's signal pair)
- `accent` — the brand voice
- `warn` / `danger` — advisory / hard-violation

Pick a different palette and the rest of the system inherits. Don't pick more than 4–5 chromatic ramps; more colors is more noise.

### 4.2 Mode-scoped semantic vars

Surface-level semantics resolve through a mode selector. Reference layout:

```css
/* Token primitives — same in every mode */
:root {
  --color-neutral-0:    #ffffff;
  --color-neutral-1000: #000000;
  --color-bid-500:      #10b981;
  --color-ask-500:      #ef4444;
  --color-accent-500:   #6366f1;
  --shadow-popover:     0 4px 8px -2px rgba(0,0,0,0.6), 0 12px 24px -6px rgba(0,0,0,0.45);
  --duration-instant:   0ms;
  --duration-ease:      220ms;
  /* … */
}

/* Mode-scoped surfaces */
[data-mode="hot"] {
  --bg-canvas:     var(--color-neutral-1000);
  --bg-panel:      var(--color-neutral-900);
  --bg-raised:     var(--color-neutral-800);
  --fg-primary:    var(--color-neutral-100);
  --fg-secondary:  var(--color-neutral-300);
  --fg-muted:      var(--color-neutral-400);
  --border-subtle: var(--color-neutral-800);
  --border-strong: var(--color-neutral-700);
}
[data-mode="cool"]  { /* slightly lighter chrome, more breathing */ }
[data-mode="calm"]  { /* deliberately quiet */ }
```

The component layer uses **only** the semantic vars (`bg-canvas`, `fg-primary`, `border-subtle`). The token primitives (`--color-neutral-900`) are reserved for tokens.css itself. This is the tokens-only discipline — see §5.2.

### 4.3 Tailwind v4 surface

Expose tokens as utility classes via `@theme inline`:

```css
@import "tailwindcss";
@import "./design-tokens.css";

@theme inline {
  --color-neutral-0:    var(--color-neutral-0);
  --color-neutral-1000: var(--color-neutral-1000);
  --color-bid-500:      var(--color-bid-500);
  --color-ask-500:      var(--color-ask-500);
  --color-accent-500:   var(--color-accent-500);

  --color-bg-canvas:    var(--bg-canvas);
  --color-bg-panel:     var(--bg-panel);
  --color-fg:           var(--fg-primary);
  --color-fg-muted:     var(--fg-muted);
  --color-border-subtle: var(--border-subtle);
  /* … */
}
```

Now `bg-bg-canvas`, `text-fg-muted`, `border-border-subtle`, `bg-bid-500/40` are all valid Tailwind classes that resolve through your tokens.

### 4.4 Verification

Before moving to Phase 2, render a smoke-test page that shows every semantic var as a swatch under each mode (`<div data-mode="hot">…</div>`). If any var is unresolved or any mode is empty, fix here — don't drag broken tokens into component work.

---

## 5 · Phase 2 — Component specs (before code)

### 5.1 Composition tiers

Order matters. Components only depend on tiers above them.

```
primitives        ← Button, Input, Tag, Tooltip, Avatar, Kbd
  ↓
data-display      ← Table, KeyValue, Sparkline, Chart, Pill, StatusDot
  ↓
{domain}          ← Trading, Agentic, Canvas in the reference impl
  ↓
surfaces          ← app/* pages
```

Each tier gets one spec file (`primitives.md`, `data-display.md`, etc.). Components large enough to deserve their own file (Chart, Canvas) get one (`chart.md`, `canvas.md`).

### 5.2 The tokens-only rule

Components MUST consume tokens via Tailwind utilities or CSS variables. Hex literals in `components/**/*.tsx` are a regression. Add a CI guardrail or pre-commit grep:

```bash
# returns nonzero if any hex literal sneaks into components/
grep -rEn '#[0-9a-fA-F]{6}\b' frontend/components/ && exit 1
```

This is the single most important discipline for re-skinnability.

### 5.3 Component spec template

Copy this template. Fill it for every component before writing TSX.

```markdown
# ComponentName

A one-paragraph description. What problem does this solve, what's its place in the system.

---

### ComponentName

**Used on:** {surfaces, e.g., "Run detail (primary), Compare (secondary)"}.

**Anatomy:**
\`\`\`
ASCII diagram of the component
showing labelled subparts
\`\`\`

Subparts:
- **Subpart A** — what it does
- **Subpart B** — what it does

**States:**
- `default`
- `hover`
- `focus` (keyboard)
- `disabled`
- `loading`
- `empty`
- `error`

**Tokens:**
- Background: `--bg-panel`
- Foreground: `--fg-primary`
- Border: `--border-subtle`
- Type: `scale.body-dense` (13px) tabular for numbers
- Motion: `--duration-ease` (220ms) on hover state changes

**Variants:**
- *Size:* `sm` (24h) / `md` (32h, default) / `lg` (40h)
- *Intent:* `primary` / `secondary` / `danger` / `bid` / `ask`

**Accessibility:**
- ARIA: role, aria-label requirements
- Keyboard: focusable, key bindings
- Focus order
- Screen-reader announcement for state changes

**Don't:**
- Don't do X (and why — short reason)
- Don't do Y

**Reference:**
- {Other systems we learned from — Stripe Dashboard, Linear, TradingView, etc.}
```

The **Don't** section is load-bearing. If you can't think of three don'ts, the spec isn't ready.

### 5.4 Index file

`04-component-specs/README.md` lists every component spec with a one-line description. Update it when you add a spec.

---

## 6 · Phase 3 — Implement components

Build to spec. Don't extend the spec inline; if the spec is wrong, update it (and ADR if the change is load-bearing).

### 6.1 Component scaffold

```tsx
"use client";

import { forwardRef, type HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const styles = cva(
  [
    // base classes
    "inline-flex items-center justify-center",
    "rounded-md font-medium",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
    "disabled:opacity-50 disabled:pointer-events-none",
    "transition-colors duration-[var(--duration-ease)]",
  ],
  {
    variants: {
      intent: {
        primary:   "bg-accent-500 text-neutral-1000 hover:bg-accent-600",
        secondary: "bg-bg-panel text-fg border border-border-subtle hover:bg-bg-raised",
        danger:    "bg-danger-500 text-white hover:bg-danger-600",
      },
      size: {
        sm: "h-6 px-2 text-[12px]",
        md: "h-8 px-3 text-[13px]",
        lg: "h-10 px-4 text-[14px]",
      },
    },
    defaultVariants: { intent: "secondary", size: "md" },
  }
);

export interface ButtonProps
  extends HTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof styles> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ intent, size, className, ...props }, ref) => (
    <button ref={ref} className={cn(styles({ intent, size }), className)} {...props} />
  )
);
Button.displayName = "Button";
```

Key patterns:
- **CVA** for variants. Cleaner than nested ternaries; compiles to plain class strings.
- **forwardRef** so callers can compose.
- **Token utilities only** — `bg-accent-500`, `text-fg`, `border-border-subtle`. No hex.
- **`cn(...)` helper** for class merging — last write wins on conflicts.
- **`focus-visible` outlines** for keyboard users — never `outline-none` without a replacement.

### 6.2 Pitfall — the `style` collision

The reference implementation has a known bug: `Tag` declared a CVA variant named `style` (values `solid` / `subtle`). That collides with the standard React `style` prop (`CSSProperties`), causing TypeScript errors that block `next build`. Don't reuse reserved attribute names as variant keys. Safe variant names: `tone`, `intent`, `appearance`, `emphasis`, `variant`, `size`, `density`, `shape`. Reserved (don't use): `style`, `color`, `className`, `id`, `ref`, `key`, `children`.

### 6.3 Tests — critical paths only

Per component, one vitest file with 3–10 tests covering:
- The contract (e.g., bids/asks render in priority order; ARIA grid attribute is set; spread bps math)
- The discipline (no hex literals leak; transition-* classes absent where the spec forbids motion)
- The accessibility (focusable when it should be, not when it shouldn't)

Skip exhaustive snapshot tests. Skip "renders without crashing" tests. The catalog page is the visual smoke test.

```tsx
// Component.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Component } from "./Component";

describe("Component — critical-path", () => {
  it("uses CSS var color tokens (no hex literals)", () => {
    const { container } = render(<Component />);
    const html = container.innerHTML;
    expect(html).not.toMatch(/#[0-9a-f]{6}/i);
  });

  it("is keyboard-focusable when interactive", () => {
    render(<Component interactive />);
    expect(screen.getByRole("button").getAttribute("tabindex")).toBe("0");
  });
});
```

---

## 7 · Phase 4 — Catalog page

The catalog (`frontend/app/design-system/page.tsx`) is one big client-side page that renders every component variant in a labeled grid. Internal route, not in the IA, not linked from the left rail. It's a **visual regression check** and an **onboarding tool** — both jobs done by simply existing.

### 7.1 Scaffold helpers

Two helpers do most of the work:

```tsx
function Section({
  title,
  tokens,
  children,
}: {
  title: string;
  tokens?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-10">
      <h2 className="text-[11px] font-semibold uppercase tracking-widest text-fg-muted mb-3 num-tabular">
        {title}
      </h2>
      {tokens && (
        <p className="text-[11px] text-fg-muted mb-4 font-mono num-tabular">{tokens}</p>
      )}
      <div className="rounded-md border border-border-subtle bg-bg-panel p-5 flex flex-col gap-4">
        {children}
      </div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-[11px] uppercase tracking-wider text-fg-muted w-40 shrink-0 num-tabular">
        {label}
      </span>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  );
}
```

The `tokens` prop on Section is a one-line note about which CSS vars the component consumes — useful when re-skinning to grep for affected components.

### 7.2 Page skeleton

```tsx
"use client";

import { useState } from "react";
import { Button, Input, Tag, /* … */ } from "@/components/primitives";
import { KeyValue, Sparkline, Chart, /* … */ } from "@/components/data-display";

export default function DesignSystemPage() {
  const [text, setText] = useState("");

  return (
    <div data-mode="cool" className="min-h-screen bg-bg-canvas text-fg p-8">
      <header className="mb-8">
        <h1 className="text-[20px] font-semibold tracking-tight">Design system</h1>
        <p className="text-[12px] text-fg-muted mt-1">
          Visual catalog. HOT mode by default; sections override via{" "}
          <code className="text-fg-secondary">data-mode</code>.
        </p>
      </header>

      {/* BUTTON */}
      <Section title="Button" tokens="--color-accent-{500,600,700}, --bg-panel, --bg-raised">
        <Row label="Intents (md)">
          <Button intent="primary">Primary</Button>
          <Button intent="secondary">Secondary</Button>
          <Button intent="danger">Danger</Button>
        </Row>
        <Row label="Sizes">
          <Button size="sm">sm</Button>
          <Button size="md">md</Button>
          <Button size="lg">lg</Button>
        </Row>
      </Section>

      {/* … one Section per component family … */}
    </div>
  );
}
```

### 7.3 Coverage rule

Every component family in `components/` has a `Section`. Every variant the spec defines has a `Row`. If a spec has 6 intents and 4 sizes, you should see a row of 6 intents and a row of 4 sizes (not a 24-cell grid — labeled rows scan better).

### 7.4 Mode preview

Sections that look different in HOT vs COOL vs CALM should render under each. Drop a `data-mode="..."` wrapper inside the Row. Don't try to make the whole page a mode toggle — visual diff is easier when modes sit side-by-side.

```tsx
<Row label="Modes">
  <div data-mode="hot"  className="bg-bg-canvas p-3 border border-border-subtle">…</div>
  <div data-mode="cool" className="bg-bg-canvas p-3 border border-border-subtle">…</div>
  <div data-mode="calm" className="bg-bg-canvas p-3 border border-border-subtle">…</div>
</Row>
```

### 7.5 Live state

Some components (Toggle, Input, dismissable Tag) need real state to demo. Use `useState` at the page level. Don't over-engineer — these are demo callbacks, not persistence.

---

## 8 · Phase 5 — Surface specs + implementation

### 8.1 Surface spec template

```markdown
# Surface Spec — {Name}

**Mode:** {hot|cool|calm}
**URL:** `/route`
**Backed by:** {services or APIs}
**Frequency:** {how often the user lands here — drives density default}
**Density:** {compact|standard|comfortable}

---

## 1. Layout

\`\`\`
┌─────────────────────────────────────────────────┐
│ ASCII layout                                     │
│ showing the surface at standard density          │
└─────────────────────────────────────────────────┘
\`\`\`

## 2. Sections

1. **Header** — breadcrumb, primary action
2. **{Region}** — what it shows, which components it composes
3. …

## 3. Live behaviour

- Polling cadence
- Optimistic updates
- Live indicators

## 4. Empty states

| Region | State |
|---|---|
| No data | "{copy}" |
| Loading | spinner with "{copy}" |
| Error | inline error with retry |

## 5. Critical-path note

What must hold for this surface to be valid. (E.g., "the snapshot must be archived with the run — without it, this surface is misleading.")
```

### 8.2 Implementation rule

Surface code composes existing components only. If a surface needs something a component doesn't have:
- Small gap → extend the component spec, then the component, then use it
- Large gap → log to tech-debt registry, surface as Pending tag, ship the surface

The reference implementation's Pending-tag pattern is load-bearing. When a backend doesn't yet emit some metric, render the structure with `<Tag intent="warn">Pending</Tag>` and a one-line caveat. Don't fake values. Don't hide the section. The structure being visible drives the backend conversation.

---

## 9 · Phase 6 — Working with the system

### 9.1 Handoff docs (multi-session work)

When work spans sessions, the last action of each session is to write a handoff doc. Format:

- **Branch state** — last commit, test status, known errors
- **What shipped** — concrete files changed
- **What's next, in priority order** — with decisions to make first
- **Things to be aware of** — gotchas, pre-existing bugs, dev-server gotchas
- **Suggested next-session prompt** — verbatim instruction the user can paste

This file goes in `docs/design/HANDOFF-{phase}-CONTINUATION.md` and is committed as a `docs(redesign)` commit. The reference implementation does this between every redesign session.

### 9.2 Tech-debt registry

`docs/TECH-DEBT-REGISTRY.md` — append-only log of debt encountered during unrelated work. Don't fix opportunistically. Format: `Service | Description | Severity | Effort | Date`.

### 9.3 ADR triggers

Open an ADR when:
- A decision is reversible only at significant cost
- A future you (or a new collaborator) would ask "why did we do this"
- The decision conflicts with the philosophy and you're choosing the override deliberately

Don't ADR every small choice. The log loses force when it's a chore.

---

## 10 · Re-skinning (existing repo, new aesthetic)

When the work is to change the look without changing the system:

1. **Branch** — `redesign/{aesthetic-name}-v{N}`. Don't do this in `main`.
2. **Rewrite philosophy + ADRs.** New principles, new vibe. ADR-001 explains the break from the prior aesthetic.
3. **Swap tokens** — `tokens.json` + `tokens.css` + the Tailwind `@theme` exposure. Modes can be redefined here too.
4. **Re-render the catalog page** — `npm run dev`, visit `/design-system`. This is your visual diff. Anything broken means a hex literal leaked, or a component used a token that doesn't exist in the new surface.
5. **Hex-literal sweep** — `grep -rEn '#[0-9a-fA-F]{6}\b' frontend/components/`. Fix hits before declaring done.
6. **Surface walkthrough** — visit each top-level surface in the browser. Anything that looks wrong in the new aesthetic is either (a) a token gap (extend tokens.css) or (b) a component spec gap (the spec didn't constrain enough — update spec, update component).
7. **Update spec references** — grep the docs for color names that moved (`indigo`, `emerald`) and update.

If the new aesthetic needs a structurally different mode model (different number of modes, different scoping rules), that's not a re-skin — it's a fork. Treat it as Phase 0 of a fresh build.

---

## 11 · Pitfalls (learned the hard way in the reference impl)

| Pitfall | Symptom | Mitigation |
|---|---|---|
| Hex literals in components | Re-skin requires component edits | Grep on pre-commit; CI guard |
| CVA variant named `style` | `next build` fails on type collision with HTMLAttributes.style | Reserved-name list in §6.2 |
| Inventing component variants beyond the spec | Spec / code drift; surfaces use the wrong variants | Update spec first, then code |
| Faking unwired backend data | Surfaces look complete but mislead | Pending tag pattern |
| Opportunistic refactors | Scope creep in unrelated PRs | Tech-debt registry |
| Skipping ADRs for "obvious" choices | Future-you can't reconstruct rationale | ADR triggers in §9.3 |
| Catalog page rotting | New components missing; broken demos | One catalog `Section` per component family is a build-time review item |
| `next build` failing while `next dev` works | TS errors deferred to build time | Run `tsc --noEmit` in CI; don't accumulate |

---

## 12 · Glossary

- **Token surface shape** — the set of semantic CSS vars (`bg-canvas`, `fg`, etc.) that components consume. Aesthetic change = preserve shape, change values.
- **Composition tier** — primitives → data-display → domain → surfaces. Imports flow downward; reverse imports break the system.
- **Mode contract** — every surface declares `data-mode="..."` on its root; components reference semantic vars, not raw color tokens; modes redefine the semantic vars.
- **Pending tag** — `<Tag intent="warn">Pending</Tag>` on a section whose backend isn't wired. Surfaces the structure; surfaces the gap.
- **ADR** — Architecture Decision Record. One per load-bearing decision.

---

## 13 · The minimum-viable replication

If you only had a weekend, this is the order:

1. `01-design-philosophy.md` — three principles, three modes
2. `tokens.css` + Tailwind `@theme` exposure
3. Three primitives (Button, Input, Tag) with specs and CVA variants
4. Catalog page with three Sections
5. One surface composing the primitives
6. `09-decisions-log.md` with three ADRs (mode model, accent color, type)

That's a system. Everything else is depth.
