# Primitives

Foundational components. Used everywhere. Get these right and everything else follows.

---

### Button
**Used on:** all surfaces
**Anatomy:** `[icon? | label | shortcut?]` — icon optional left-side; label always; keyboard shortcut hint optional right-side rendered in `Kbd`.

**States:**
- `default` — bg `transparent` (ghost) or `accent.500` (primary), border `border.subtle` (ghost only)
- `hover` — bg lifts one neutral step (ghost) or `accent.600` (primary)
- `active` — bg drops one step
- `focus` — `2px solid accent.500` outline, offset 2px
- `disabled` — `fg.disabled`, no hover, `cursor: not-allowed`
- `loading` — replace icon with 14px spinner; label stays; pointer-events disabled

**Tokens:**
`--color-accent-{500,600,700}`, `--bg-panel`, `--bg-raised`, `--fg-primary`, `--fg-disabled`, `--radius-md`, `--space-{2,3,4}`, `--duration-snap`, type `scale.label`

**Variants:**
- `size`: `xs` (24h), `sm` (28h), `md` (32h, default), `lg` (40h)
- `intent`: `primary` (accent fill), `secondary` (ghost), `danger` (danger fill — kill switch only), `bid` / `ask` (order entry only)
- `iconOnly`: square hit area = height; icon centered

**Accessibility:** every button has either a label or `aria-label`. Focus ring visible. Min hit area 32×32 even when visual is smaller (use padding to expand). `Enter` and `Space` activate.

**Don't:**
- Use `intent="primary"` more than once per visible viewport — primary signals "the one obvious action."
- Use `intent="danger"` for ordinary destructive actions (deleting a draft profile etc.) — that's `intent="secondary"` with confirmation. Reserve danger for truly irreversible/catastrophic.
- Stack two `lg` buttons next to each other — increase spacing or downgrade one to `md` ghost.

**Reference:** Linear button system, Stripe Dashboard button hierarchy.

---

### Input (text)
**Used on:** all surfaces
**Anatomy:** `[label?] [adornment-left? | input | adornment-right?] [hint? | error?]`

**States:**
- `default` — bg `bg.raised`, border `border.subtle`, placeholder `fg.muted`
- `hover` — border `border.strong`
- `focus` — border `accent.500`, ring 2px `accent.500/20%`
- `error` — border `ask.500`, hint replaced with error in `ask.500`
- `disabled` — bg `bg.panel`, fg `fg.disabled`

**Tokens:** `--bg-raised`, `--border-{subtle,strong}`, `--color-accent-500`, `--color-ask-500`, `--radius-md`, `--space-3`, type `scale.body-dense` for input value, `scale.label` for label, `scale.caption` for hint

**Variants:**
- `density`: `compact` (28h), `standard` (32h, default), `comfortable` (40h)
- `mono`: switch to mono font for values where alignment matters (API keys, hashes)
- `numeric`: right-align, tabular numerals, treat `-` and `.` as valid early chars

**Accessibility:** label is always present (visible or `aria-label`). Error text uses `aria-describedby` linkage. Numeric inputs use `inputmode="decimal"`.

**Don't:**
- Inline-strip the label and rely on placeholder alone — bad for dyslexia and screen readers.
- Use placeholder for examples *and* hint copy — pick one, the hint area is for the hint.

**Reference:** Linear inputs, Stripe field treatment.

---

### Select / Combobox
**Used on:** all surfaces
**Anatomy:** combobox button (looks like Input) + popover listbox

**States:** as Input, plus listbox states `expanded`/`collapsed`. Listbox option states: `default`, `hover` (bg `bg.row-hover`), `selected` (left bar 2px `accent.500` + bg `bg.raised`), `focused` (keyboard) (`bg.row-hover` + ring inside).

**Tokens:** Input tokens + `--shadow-popover`, `--bg-panel` for listbox surface, `--z-popover`, `--duration-tick` for open/close

**Variants:**
- `mode`: `select` (single, click-to-pick) vs `combobox` (typing filters)
- `searchable` boolean — show inline search at top of listbox
- `multiSelect` — checkboxes inside options, "Apply" button at bottom

**Accessibility:** WAI-ARIA combobox pattern. Arrow keys navigate options; `Enter` selects; `Esc` closes; typing filters.

**Don't:**
- Open the listbox above the trigger when there's room below — disorienting. Default below; flip only when truly clipped.
- Use Select for ≥30 options without `searchable: true`.

**Reference:** Linear's command palette options, shadcn/ui Combobox.

---

### Toggle / Switch
**Used on:** all surfaces (mostly settings + risk control arming)

**Anatomy:** `[track | thumb]` with optional `[label] | [toggle]` row.

**States:** `off` (track `neutral.700`), `on` (track `accent.500` for normal toggles, `bid.500` for opt-in, `danger.500` for kill switch arming), `disabled` (track `neutral.800`, thumb `neutral.500`).

**Tokens:** `--color-neutral-700`, `--color-accent-500`, `--color-bid-500`, `--color-danger-500`, `--duration-snap` for thumb travel.

**Variants:**
- `size`: `sm` (track 28×16), `md` (track 36×20, default)
- `confirmOnArm` (kill switch only) — show inline confirmation before flipping; toggle is two-stage.

**Accessibility:** `role="switch"`, `aria-checked`. Touch target ≥32px including label.

**Don't:**
- Use a toggle for a setting that is not boolean — use Select with two values plus an "Auto" option if needed.
- Animate the thumb longer than 180ms — it makes the platform feel laggy.

**Reference:** Linear's toggles, iOS toggle convention.

---

### Tag / Badge
**Used on:** all surfaces

**Anatomy:** `[dot? | label | x?]` — small, fixed-height (20 or 24).

**Variants:**
- `intent`: `neutral`, `accent`, `bid`, `ask`, `warn`, `danger`, `agent.{ta,regime,…}`
- `style`: `solid` (filled with intent color), `subtle` (intent-tinted bg + intent fg)
- `dismissable`: appends `x` icon

**Tokens:** intent colors at `100`/`200` for subtle bg, `700`/`800` for subtle fg; full `500` for solid.

**Reference:** Linear status badges, GitHub label tags.

---

### Kbd
**Used on:** all surfaces, esp. tooltips and command palette

**Anatomy:** small, mono, framed. `⌘ K`, `Esc`, `1–9`.

**Tokens:** `--font-mono`, `--size-11`, bg `--bg-raised`, border `--border-subtle`, radius `--radius-xs`, padding `2px 5px`.

**Don't:** invent your own modifier symbols. Mac: `⌘ ⌥ ⌃ ⇧`. Win/Linux: `Ctrl Alt Shift`. The platform reads `navigator.platform` and renders accordingly.

---

### Tooltip
**Used on:** all surfaces, esp. Hot mode where labels are minimal

**Anatomy:** trigger element (any) + popover bubble.

**States:** appears on hover after 600ms (HOT mode: 250ms), disappears on hover-out after 80ms.

**Tokens:** `--bg-raised`, `--shadow-popover`, type `scale.caption`, `--radius-sm`, `--space-2` padding, `--duration-tick`.

**Variants:**
- `placement`: `top`, `bottom`, `left`, `right` (auto-flips on viewport edge)
- `richContent`: allow `Kbd` and short helper text (max ~2 lines)

**Accessibility:** also opens on focus. `aria-describedby` linked. Never holds critical information — tooltips are progressive disclosure, never required.

---

### Avatar
**Used on:** all surfaces, esp. agentic + comments + audit

**Anatomy:** circle, 24/32/40px. Image or initials. Subtle 1px ring in `--border-subtle`.

**Variants:**
- `kind`: `user` (image or initials), `agent` (icon glyph + agent identity color ring), `system` (gear icon)
- `status`: optional dot bottom-right (`bid` if active, `neutral` if idle, `ask` if errored)

**Tokens:** for agent variant, ring color from `--color-agent-{ta|regime|…}`.

**Don't:** show a status dot for users in HOT mode — too much noise. Reserve for Observatory and audit views.
