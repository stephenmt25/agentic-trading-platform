# Redesign Execution Plan

> Status: 2026-05-07 · Author: Wrench + Claude · Scope: full visual + IA redesign of `frontend/` against the design portfolio in this folder, on a parallel branch.

This is the operational plan. Read in order; don't skip ahead. Decision points are marked **🟨 DECIDE**; execute steps are marked **▶ DO**.

---

## Phase 0 — Reconciliation decisions (before any code)

These three decisions affect the rest of the plan. Make them now, log them in `09-decisions-log.md` as ADRs, and don't relitigate during execution.

### 🟨 DECIDE 0.1 — Typography reconciliation

**Conflict:** the portfolio specifies Inter (`03-design-tokens/tokens.json`). Your existing `frontend/app/layout.tsx` uses IBM Plex Sans + IBM Plex Mono.

**Options:**
- **(a) Keep IBM Plex** — update tokens.json and tokens.css to reference IBM Plex; less work; preserves what's already loaded; IBM Plex has excellent tabular figures and a slightly more "engineered" character that fits the Praxis brief well.
- **(b) Switch to Inter** — matches the portfolio as written; more familiar in modern fintech (Linear, Stripe); means a font swap on the redesign branch only.
- **(c) Use both** — IBM Plex Mono for tabular numerics, Inter for prose. Defensible but adds complexity.

**Recommendation:** **(a) keep IBM Plex.** It was a deliberate choice in your existing build, IBM Plex Mono is one of the best mono fonts for financial data, and "the bridge of a research vessel" actually reads more like Plex than like Inter. Fix the portfolio to match reality, not the other way around.

**▶ DO** — once decided, update `03-design-tokens/tokens.json`, `tokens.css`, and `01-design-philosophy.md` §4 vibe references. Add ADR-011 to the decisions log.

---

### 🟨 DECIDE 0.2 — Agent identity colors vs. existing 3-color discipline

**Conflict:** your existing `frontend/DESIGN-SYSTEM.md` says: *"Rule: Maximum 3 semantic hues. No purple, no teal, no orange. Only emerald, red, and amber."* The portfolio's Agent Observatory needs to differentiate six agents and proposes per-agent identity colors.

**Options:**
- **(a) Honor the 3-color rule** — drop agent identity colors entirely. Differentiate agents in Observatory by **icon glyph + label + column position only**. Most disciplined. Closer to Bloomberg-terminal aesthetic. The Observatory becomes pure typography + structure. Most rigorous.
- **(b) Carve out a Cool-mode exception** — agent identities allowed only in COOL mode (Observatory + Canvas), forbidden everywhere else. Codifies the philosophy as written. Update `DESIGN-SYSTEM.md` to scope the 3-color rule to HOT and CALM modes.
- **(c) One accent for all agents** — all six agents use the existing `--primary` blue, differentiate by glyph + position. Middle ground.

**Recommendation:** **(b) carve out a Cool-mode exception.** Multi-agent debate is genuinely hard to read with only glyphs at typical density (we tested this in research — OrchVis specifically uses color-coded agent rows for this reason). The exception is principled (mode-scoped, not ad-hoc) and limited (Cool mode only, ~15% of user time). But this is a real call — option (a) is also defensible if you're willing to commit to icon-led visual differentiation.

**▶ DO** — once decided, update `frontend/DESIGN-SYSTEM.md` to reconcile, update ADR-002 in this folder with the chosen approach, and amend `01-design-philosophy.md` §3 P2 if needed.

---

### 🟨 DECIDE 0.3 — Repo strategy: in-place rewrite vs. parallel app

**Conflict:** none yet, but the structural choice shapes everything.

**Options:**
- **(a) In-place rewrite on a feature branch** — `frontend/` stays at the same path; redesign branch rewrites contents. Use a git worktree to run both UIs side-by-side locally. Cleanest diff against main. Recommended.
- **(b) Parallel app** — keep `frontend/` (old) on main, create `frontend-v2/` (new) on a branch. Both ship side-by-side under different routes (`/v2/*`) for a transition period. Higher operational cost but lower cutover risk.
- **(c) Greenfield separate repo** — overkill for a UI redesign; rejected.

**Recommendation:** **(a) in-place rewrite + worktree** — the `git diff main..redesign/frontend-v2 -- frontend/` is your most powerful review tool. Worktrees solve the "run both locally" problem cleanly.

**▶ DO** — confirm option, then proceed to Phase 1.

---

## Phase 1 — Repo setup (concrete commands)

Assumes you chose **0.3 (a)**. Adjust paths/names if your conventions differ.

### 1.1 Stash current uncommitted work

You have 78 commits ahead of origin and uncommitted modifications. Resolve before branching.

```bash
cd C:\Users\stevo\DEV\agent_trader_1\aion-trading

# Inspect what's modified
git status

# Push your 78 commits up first (run on main before branching off it)
git push origin main

# Decide on the uncommitted changes:
#   - If they're WIP for the redesign:    stash and apply on the redesign branch
#   - If they're unrelated work for main:  commit on main first
git stash push -m "pre-redesign WIP" --include-untracked
# OR
git add -A && git commit -m "WIP before redesign branch"
```

### 1.2 Create the redesign branch

```bash
# From clean main:
git checkout main
git pull origin main
git checkout -b redesign/frontend-v2

# Push immediately so the branch exists upstream
git push -u origin redesign/frontend-v2
```

### 1.3 Set up a worktree for parallel local development

This is the key move. Worktrees let you have BOTH branches checked out at once on different paths.

```bash
# From the repo root, create a worktree of the redesign branch at a sibling path:
git worktree add ../aion-trading-redesign redesign/frontend-v2

# Now you have:
#   C:\Users\stevo\DEV\agent_trader_1\aion-trading            ← main (existing UI)
#   C:\Users\stevo\DEV\agent_trader_1\aion-trading-redesign   ← redesign branch
```

### 1.4 Configure ports so both UIs run simultaneously

In the **redesign worktree only**, edit `frontend/package.json` to use port 3001:

```json
"scripts": {
  "dev": "next dev -p 3001",
  ...
}
```

Now you can:
- `cd aion-trading/frontend && npm run dev` → old UI at http://localhost:3000
- `cd aion-trading-redesign/frontend && npm run dev` → new UI at http://localhost:3001

This is the foundation. Side-by-side comparison is your primary validation tool.

### 1.5 Verify worktree health

```bash
git worktree list
# Should show two worktrees: main and the redesign

# When you want to remove the worktree later (after merge):
# git worktree remove ../aion-trading-redesign
```

---

## Phase 2 — Integrate the design portfolio into the repo

The portfolio currently lives at `C:\Users\stevo\OneDrive\Documents\Claude\Projects\design research\`. For Claude Code to read it efficiently, it needs to live IN the repo.

### 2.1 Copy the portfolio into the redesign branch

```bash
cd ..\aion-trading-redesign

# Copy the design portfolio into a docs subfolder
mkdir docs\design
xcopy "C:\Users\stevo\OneDrive\Documents\Claude\Projects\design research\*" docs\design\ /E /I

# Or with PowerShell:
# Copy-Item -Recurse "C:\Users\stevo\OneDrive\Documents\Claude\Projects\design research\*" docs\design\
```

### 2.2 Promote 07-claude-code-context.md to be the load-bearing DESIGN.md

```bash
# Move it to where Claude Code looks for design context:
copy docs\design\07-claude-code-context.md frontend\DESIGN.md

# But: your existing frontend/DESIGN-SYSTEM.md needs reconciliation (per 0.2 above).
# Two options:
#   (a) Replace DESIGN-SYSTEM.md with the new DESIGN.md (and update its references)
#   (b) Keep both; DESIGN-SYSTEM.md becomes the legacy reference, DESIGN.md is canonical for the redesign

# Recommended: rename existing one for posterity, install new one canonically.
git mv frontend\DESIGN-SYSTEM.md frontend\DESIGN-SYSTEM.legacy.md
copy docs\design\07-claude-code-context.md frontend\DESIGN.md
```

### 2.3 Install the tokens

```bash
# Copy the CSS tokens into the actual styles folder:
copy docs\design\03-design-tokens\tokens.css frontend\app\design-tokens.css

# Import them in app/globals.css (add to the top):
#   @import './design-tokens.css';
```

Then update `frontend/tailwind.config.ts` (or however your existing tailwind config is structured) using `docs/design/03-design-tokens/tailwind.preview.js` as a reference. This is a hand-merge, not a copy — your existing config has the OKLCH-based tokens you want to preserve or migrate.

### 2.4 Update CLAUDE.md to reference the new design source

Add a section at the bottom of the existing `CLAUDE.md` (or under §6 alongside the harness mechanics):

```markdown
## 7 · Design (frontend redesign branch only)

The frontend on the `redesign/frontend-v2` branch follows the design portfolio at `docs/design/`. The single load-bearing file is `frontend/DESIGN.md` — read it before generating any frontend component. The full portfolio (component specs, surface specs, tokens, ADRs) is at `docs/design/`.

When this CLAUDE.md and `docs/design/01-design-philosophy.md` disagree, the design portfolio wins on visual/IA topics; CLAUDE.md wins on architecture, security, and codebase conventions.
```

### 2.5 Commit Phase 2

```bash
git add docs/design frontend/DESIGN.md frontend/DESIGN-SYSTEM.legacy.md frontend/app/design-tokens.css CLAUDE.md
git commit -m "redesign: integrate design portfolio (docs/design, DESIGN.md, tokens)"
git push
```

---

## Phase 3 — Stitch workflow (in parallel with code work)

Stitch isn't blocking — you can run it in parallel with Phase 4–6. But the visual targets it produces help validate code generation, so don't skip it.

### 3.1 Capture the reference image library

Per `08-reference-library/README.md` §"Suggested capture list" — the highest-leverage screenshots to take first:

1. `01-hyperliquid-trading.png` — primary density anchor
2. `03-linear-app.png` — typography/spacing discipline
3. `05-claude-tool-use.png` — agent reasoning vocabulary
4. `08-n8n-canvas.png` — node editor anatomy
5. `13-stripe-dashboard.png` — calm-mode metric cards

Save them to `docs/design/08-reference-library/images/`. Capture at native resolution (≥1280px wide). Blur out personal account info.

### 3.2 Generate one surface in Stitch as a calibration run

Pick **Profiles & Settings** as the first Stitch run — it's the simplest surface, lowest cost if iteration is needed.

1. Open https://stitch.withgoogle.com/
2. Choose **Experimental Mode** (Gemini 2.5 Pro)
3. Paste the contents of `06-stitch-prompts/06-profiles.prompt.md` (VIBE + DETAILED PROMPT + ANTI-PROMPT, all three sections)
4. Upload `13-stripe-dashboard.png`, `17-linear-settings.png`, `18-mercury-dashboard.png` as references
5. Iterate using Stitch's natural-language editing — anchor changes with token names from `tokens.json` ("use bg-canvas not bg-panel here")
6. Export the result to Figma when satisfied
7. Save the Figma URL into `docs/design/08-reference-library/stitch-outputs.md` (create this file as you go)

This is the calibration pass. After Profiles, the Stitch outputs for the harder surfaces will be more predictable.

### 3.3 Stitch outputs as visual grounding for Claude Code

When you pin Claude Code to a component or surface task, include the Figma URL or a screenshot of the Stitch output in the message. Claude Code's multimodal vision will use it as visual ground-truth alongside the markdown specs.

---

## Phase 4 — Foundation build (3–5 sessions)

Don't build any feature components yet. Build the platform.

### 4.1 Tokens are wired

Verify in the redesign worktree:

```bash
cd aion-trading-redesign\frontend
npm run dev
```

Then in any component, write a one-off test:

```tsx
<div className="bg-bg-canvas text-fg p-4 border border-border-subtle">
  Mode: <span className="text-accent-500">test</span>
</div>
```

If `--bg-canvas`, `--fg-primary`, `--border-subtle`, `--color-accent-500` all resolve, tokens are in. If not, the tailwind config / globals.css import isn't right.

### 4.2 Mode provider

Implement a top-level provider that sets `data-mode="hot|cool|calm"` on the `<html>` element based on the route:

```
/hot/*         → hot
/agents/*      → cool (or "hot when live debate is on")
/canvas/*      → cool
/backtests/*   → cool
/risk          → hot
/settings/*    → calm
```

Pattern: a `useMode()` hook keyed off `usePathname()`. Suggested file: `frontend/components/providers/ModeProvider.tsx`. Wire it into `app/layout.tsx` between AppShell and the page tree.

### 4.3 Layout shell — left rail + chrome top-bar

The 56px collapsible left rail and the 44px chrome top-bar are present on every surface. Build them once. Spec: `02-information-architecture.md` §2.

Suggested files:
- `frontend/components/shell/LeftRail.tsx`
- `frontend/components/shell/ChromeBar.tsx`
- `frontend/components/shell/StatusPills.tsx`
- `frontend/components/shell/CommandPalette.tsx`

Wire `KillSwitch` state from Redis into a global zustand/jotai store; the `🛡 armed-soft|hard` pill reads from there.

### 4.4 Phase 4 acceptance

Before moving to Phase 5, verify:

- [ ] You can navigate between `/hot/BTC-PERP`, `/canvas/blank`, `/risk`, `/settings/profiles` with no 500s.
- [ ] Each route shows the correct `data-mode` on `<html>` (use devtools).
- [ ] Tokens render correctly in all three modes — pages don't look identical.
- [ ] Left rail and chrome bar are present on every page.
- [ ] Kill-switch armed state visibly affects the chrome (try toggling it via the API directly).

---

## Phase 5 — Component library (5–10 sessions)

Build in dependency order. Don't generate a domain component before its primitives exist.

### 5.1 Primitives + data-display (one session each)

Generate together — they're small. Use a prompt template like:

```
Read frontend/DESIGN.md, then read docs/design/04-component-specs/primitives.md.

Generate the components in primitives.md as React components in frontend/components/primitives/.
Stack: TypeScript, base-ui/react where suitable, class-variance-authority for variants,
Tailwind classes referencing the tokens via the existing tailwind.config.

For each component:
  - One file per component (Button.tsx, Input.tsx, etc.)
  - Export a default React component
  - Implement ALL states and variants from the spec
  - Implement keyboard + ARIA per the Accessibility line
  - Add a Storybook story under stories/ OR a /design-system page route showing all variants

Don't generate a component the spec doesn't define. If a primitive needs something the spec
doesn't cover, flag it and ask before extending.
```

Repeat for `data-display.md`. Then for `trading-specific.md` (skip Chart for now if you don't have lightweight-charts integration ready). Then `agentic.md`. Then `canvas.md`.

### 5.2 Build a `/design-system` route as you go

Generate a hidden route at `/__design-system` that imports every component you've built and shows it in all variants. This is your visual regression catch-net. Lift heavily from your existing `frontend/DESIGN-SYSTEM.legacy.md` if it had one.

### 5.3 Component-by-component acceptance

For each component, verify:

- [ ] Renders in HOT, COOL, and CALM modes — switch the parent `data-mode` and confirm visual change
- [ ] All declared variants work
- [ ] Keyboard accessibility per the spec (Tab, Enter, arrows, etc.)
- [ ] Token-only colors — grep for hex literals in the file; should be none
- [ ] Tabular numerics applied where required (use `.num-tabular` utility per `tailwind.preview.js` plugin)

Critical-path components (`OrderEntryPanel`, `KillSwitchControl`, `OrderBook`, `PnLBadge`) ALSO need:
- [ ] Unit tests for the critical states (kill-switch-armed, near-liq, etc.)
- [ ] Performance test for the streaming components (OrderBook can render a 100ms update burst without dropped frames)

---

## Phase 6 — Surface build (8–12 sessions)

Build surfaces in this order. Rationale follows.

### 6.1 Order: Profiles → Backtesting → Canvas → Observatory → Hot Trading → Risk Control

| # | Surface | Why this order |
|---|---|---|
| 1 | Profiles & Settings | Simplest. CALM mode. Tests the foundation without trading complexity. Easy rollback if patterns are wrong. |
| 2 | Backtesting & Analytics | Read-only. Tests data-display + chart wrapping with no live data. Builds confidence in the chart component. |
| 3 | Pipeline Canvas | Now you need the canvas-specific components (Node, Edge, etc.) for the first time. `@xyflow/react` is already installed — wire it up. Higher cognitive load, but isolated. |
| 4 | Agent Observatory | Now the agentic components meet real WebSocket data. Tests the streaming + reasoning patterns. |
| 5 | Hot Trading | The hardest. Needs every primitive + data-display + trading-specific component, plus live order book streaming. By the time you reach it, the patterns are proven. |
| 6 | Risk Control | Last because it's the highest-stakes — kill-switch UX needs the rest of the platform fully working to test against. |

This is **inverse** to user-time-spent. You'll be tempted to start with Hot Trading because it's the most-used surface. Resist. Starting with Profiles tests your foundation in low-stakes territory.

### 6.2 Surface prompt template

```
Read frontend/DESIGN.md, then read docs/design/05-surface-specs/{N}-{name}.md.

Implement this surface in frontend/app/{route}/page.tsx (and supporting files in
frontend/app/{route}/_components/ for surface-local pieces).

Compose ONLY existing components from frontend/components/. If a needed component
doesn't exist, STOP and tell me which component spec to generate first.

Wire data via the existing API client at frontend/lib/api.ts (look at how other pages
use it). For real-time streams, use the WebSocket pattern at frontend/lib/ws.ts.

Implement the keyboard map from the spec.
Implement all declared empty / loading / error states.
Use mode={data-mode} per spec.
```

### 6.3 Surface acceptance

For each surface:

- [ ] All keyboard shortcuts work
- [ ] Empty states render correctly (test by clearing data)
- [ ] Loading states render correctly (test with throttled network)
- [ ] Failure states render correctly (kill the relevant service and observe)
- [ ] Side-by-side compare with main branch UI (visit localhost:3000 and localhost:3001 on the same data)
- [ ] Visual diff against the Stitch output for that surface (acceptable drift; flag major divergences)

---

## Phase 7 — Data wiring & polish (3–5 sessions)

By Phase 6 each surface is functional but probably has some sharp edges. Polish:

- Real-time WebSocket reliability — reconnection, exponential backoff, stale-data indicators
- Optimistic updates on order placement (with rollback on validation reject)
- Mid-render layout stability — no CLS on price ticks (the `.num-tabular` utility is doing heavy lifting here)
- Performance budgets — OrderBook should never block scroll for >16ms; profile it
- Audit log surface — the lowest-priority Settings sub-surface, do it last

---

## Phase 8 — Validation gates before merge

Don't merge until ALL of these are green. Use them as a PR template.

### 8.1 Functional parity with main

- [ ] Every URL on main renders something on the redesign (or has a documented intentional removal in `09-decisions-log.md`)
- [ ] Every API call from main is also made from the redesign (no functionality silently dropped)
- [ ] Authentication / sessions work
- [ ] Profile create/edit/delete works
- [ ] Live orders, fills, positions visible
- [ ] Backtests dispatch and complete
- [ ] Kill switch arms and disarms

### 8.2 Design fidelity

- [ ] No file under `frontend/components/` contains hex color literals (grep test)
- [ ] No transition or animation exceeds the mode budget (manual review of motion-related files)
- [ ] Every surface has the correct `data-mode`
- [ ] All numeric displays use tabular figures
- [ ] Every component listed in `04-component-specs/` exists and has at least one production usage (no zombies)

### 8.3 Critical-path resilience

- [ ] Risk Control surface remains functional when agent services are down (test by stopping `services/debate`, `services/regime_hmm`, etc.)
- [ ] Kill switch arm/disarm works when API gateway is degraded (test by stopping `api_gateway` and using the Redis CLI directly to verify state changes)
- [ ] Hot Trading degrades gracefully (no white screen) when market data feed stalls

### 8.4 Performance budget

- [ ] First Contentful Paint < 1.5s on Hot Trading on a clean cache
- [ ] No frame drop on OrderBook with 100 updates/s (Chrome DevTools Performance tab)
- [ ] No memory growth >50MB after 1h of running Hot Trading on live data (memory leak check)

### 8.5 Accessibility minimum

- [ ] Hot Trading is fully operable from keyboard alone (no mouse needed for entry)
- [ ] Risk Control kill-switch is reachable in ≤2 keystrokes from any surface
- [ ] Focus rings visible everywhere (no `outline: none` regressions)
- [ ] All interactive elements have accessible names

---

## Phase 9 — Cutover

### 9.1 Pre-merge

- [ ] Tag main: `git tag pre-redesign-cutover`
- [ ] Document rollback plan: "if X breaks, revert to tag pre-redesign-cutover, redeploy frontend"
- [ ] Schedule a low-volatility window for cutover (weekend, market closed, no live profiles)
- [ ] Notify yourself / team

### 9.2 Merge

```bash
git checkout main
git pull origin main
git merge --no-ff redesign/frontend-v2
git push origin main
```

Use `--no-ff` to preserve the redesign-branch history as a clear merge commit; useful for forensics later.

### 9.3 Post-merge

- [ ] Deploy frontend
- [ ] Run smoke tests on prod against the canonical surfaces
- [ ] Monitor errors for 24h before considering it done
- [ ] Remove the worktree: `git worktree remove ../aion-trading-redesign`
- [ ] Archive the legacy DESIGN-SYSTEM.legacy.md → either delete or move to `docs/historical/`

### 9.4 Optional: ship behind a feature flag

If you want extra safety, gate the new UI behind a query param or cookie for the first week:

```tsx
// in app/layout.tsx, conditionally render the old layout vs new based on a feature flag
const useNewUI = useFeatureFlag('redesign-v2') || searchParams.get('newUI') === '1';
```

This adds operational complexity but lets you flip back quickly if a regression slips through.

---

## Decision log to append

When you complete each Phase 0 decision, add an ADR to `09-decisions-log.md`:

- **ADR-011** — Typography choice (per 0.1)
- **ADR-012** — Agent identity colors policy (per 0.2; amends ADR-002 if needed)
- **ADR-013** — Repo strategy (per 0.3)

Append new ADRs as the redesign proceeds and you discover new decisions. The decisions log is the audit trail.

---

## Estimated effort

This is rough — adjust by your familiarity with the stack and the harness's competence on each task.

| Phase | Sessions | Calendar |
|---|---|---|
| 0 (decisions) | 1 | 1 day |
| 1 (repo setup) | 1 | half a day |
| 2 (portfolio integration) | 1 | half a day |
| 3 (Stitch run for one surface) | 2 | 1–2 days (capture + iteration) |
| 4 (foundation) | 3–5 | 1 week |
| 5 (component library) | 5–10 | 2–3 weeks |
| 6 (surfaces) | 8–12 | 3–4 weeks |
| 7 (polish) | 3–5 | 1 week |
| 8 (validation) | 2–3 | 3–5 days |
| 9 (cutover) | 1 | 1 day |
| **Total** | **27–41 sessions** | **6–10 weeks** |

If you're working alone, ~2 hours/day pace, this is a 2-month project. If you work bigger blocks, it compresses.

---

## Risks to watch

| Risk | Symptom | Mitigation |
|---|---|---|
| The harness drifts toward generic shadcn aesthetics | Components look like Tailwind UI marketing pages | Re-anchor with `01-design-philosophy.md` §4 vibe + `inspiration-catalog.md` anti-references |
| Surfaces diverge from the IA over time | New layouts emerge that aren't in `02-information-architecture.md` | Update the IA doc BEFORE writing the layout, treat the IA doc as source of truth |
| Token leakage (hex colors in components) | grep finds hex codes | Add a pre-commit hook that fails if hex appears in `frontend/components/**/*.tsx` |
| Accessibility regressions | Tabbing breaks, focus rings missing | Run axe-core on every PR; add manual keyboard test to PR template |
| Real-time perf regressions | OrderBook drops frames during volatility | Profile early (Phase 5.3), don't wait until Phase 7 |
| Merging while live profiles are running | Live orders mid-cutover | Schedule low-volatility window in 9.1; arm soft kill-switch before deploy |

---

## What "done" looks like

The redesign branch is merged when:
- Every surface in `05-surface-specs/` is implemented and meets the Phase 8 acceptance gates
- The `09-decisions-log.md` reflects every meaningful design decision made during execution
- No file in `frontend/components/` references the old DESIGN-SYSTEM.legacy.md
- The portfolio in `docs/design/` is updated where reality diverged from spec
- The legacy DESIGN-SYSTEM.legacy.md is deleted or moved to historical

Anything short of that is a partial cutover and should ship behind a feature flag.
