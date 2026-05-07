# Known Gaps — Slated for v1.1

This file is the audit trail of issues identified during the v1 portfolio review (2026-05-07) that were *not* fixed in v1 because they're scope-bounded for v1.1. They are deliberately surfaced here so neither the user nor the harness has to rediscover them.

A v1 issue resolved in this draft is **not** listed here — see commit history of the relevant file.

---

## Surface-level gaps

### G-1. Onboarding surface
**Issue:** The portfolio defines six surfaces but no onboarding/first-run flow. New users have no documented path through "create first profile → connect first exchange → run first paper backtest → activate live."

**v1.1 plan:** Add `05-surface-specs/07-onboarding.md`. Likely a multi-step wizard surface in CALM mode that ends by depositing the user on Pipeline Canvas with a starter template loaded.

### G-2. Notifications viewer surface
**Issue:** `06-profiles-settings.md` §6 covers notification *configuration* (what to send, where) but no surface exists for *viewing* the notification history (alerts received, kill-switch trips logged).

**v1.1 plan:** Decide between (a) extending the audit log surface or (b) standalone `/notifications` surface. Likely (a) given low frequency.

### G-3. Multi-account / account-switcher
**Issue:** `02-information-architecture.md` §2.1 mentions a session/profile switcher in the bottom of the left rail but there's no surface spec for managing multiple accounts (separate users on the same install) or switching between them.

**v1.1 plan:** Defer until multi-tenancy is a real product requirement; not v1 scope.

### G-4. Account recovery flows
**Issue:** Password reset, 2FA recovery, lost-API-key recovery — none of these have flow specs.

**v1.1 plan:** Standard `/auth/recover` flows; CALM mode; mostly off-the-shelf patterns.

### G-5. Help / docs surface
**Issue:** No in-app docs surface. The `?` keyboard reference modal is mentioned (IA §2.1) but full keyboard reference, glossary, and contextual help aren't specified.

**v1.1 plan:** Decide between in-app embedded docs vs. external docs site. Likely external, with `?` modal and contextual `ⓘ` tooltips covering the in-app needs.

---

## Component-level gaps

### G-6. P5 (confidence intervals) under-implemented
**Issue:** Philosophy P5 mandates "confidence intervals, not point estimates" wherever the underlying value is uncertain. `ConfidenceBar` is the only component that fully delivers on this. `PnLBadge` doesn't have a confidence variant (it shows a point estimate). Agent direction predictions and price projections don't yet show ranges.

**v1.1 plan:**
- Add `withConfidenceInterval` variant to `PnLBadge`
- Add `PriceRange` component (mid-point + ±band)
- Update `agentic.md` to require all probabilistic outputs use either ConfidenceBar or PriceRange explicitly

### G-7. Chart indicator panels
**Issue:** `Chart` component (newly added in v1) doesn't yet specify multi-pane indicator panels (RSI/MACD strips below candles).

**v1.1 plan:** Extend Chart with `indicators: Indicator[]` prop and an Indicator type system. Defer until users ask for it.

### G-8. Density modes for individual components
**Issue:** `Table` documents three density modes; not all components do (Button has size, but not "density" per IA §5).

**v1.1 plan:** Reconcile component-level "size" variants with surface-level "density" toggles. Likely: surface-level density adjusts component size selection automatically rather than each component having its own density.

---

## Documentation cross-reference gaps

### G-9. ConfidenceBar in DebatePanel
**Issue:** It's not specified whether each agent's stance in DebatePanel includes an inline confidence indicator or whether confidence is shown separately.

**v1.1 plan:** Add to DebatePanel spec — show stance label + small confidence number (e.g., "for · 0.78") in the row; full ConfidenceBar reserved for the orchestrator's synthesis row.

### G-10. DebatePanel supersession behavior in Observatory feed
**Issue:** What happens when a new round arrives while user is viewing an older one — auto-scroll, badge, or both?

**v1.1 plan:** Document: superseded debates remain visible inline with "superseded by round X" link; stream auto-scroll lock applies; "▼ N new" badge follows TapeRow convention.

### G-11. Cross-surface navigation animation
**Issue:** No spec for surface transitions. Are they instant? Cross-fade? Slide? Probably instant for HOT mode, brief cross-fade for CALM, but not documented.

**v1.1 plan:** Add to philosophy doc §2 (mode budgets): HOT mode surface transitions instant; COOL mode 220ms; CALM mode 320ms. None should slide horizontally — that's a phone pattern.

---

## Empty-state / failure-state gaps

### G-12. Empty-state copy needs a content review
**Issue:** Empty-state copy in surface specs was authored quickly. A pass by a content designer would tighten the voice (especially for CALM mode — currently feels engineering-spec, not user-facing).

**v1.1 plan:** Content-design pass; aim for 1-line + 1-action shape consistently.

### G-13. Loading states under-specified
**Issue:** What does "loading" look like in HOT mode? Skeleton? Spinner? Don't show? Surfaces don't say.

**v1.1 plan:** Default: HOT mode shows last-known data with stale indicator (don't show skeletons, they hide info); COOL mode shows skeleton blocks; CALM mode shows simple spinner + "Loading…" text.

### G-14. Network-degraded states
**Issue:** "What if WebSocket disconnects?" handled in some surfaces (Hot Trading §6), not others. The Observatory and Canvas don't cover their own degradation.

**v1.1 plan:** Add a uniform §"Edge / failure cases" treatment to Observatory and Canvas surfaces.

---

## Process gaps

### G-15. No design tokens validator / CI
**Issue:** The portfolio enforces token discipline by convention. There's no automated check that catches a generated component using a hex color that's not in the palette.

**v1.1 plan:** Either:
(a) ESLint rule that bans hex colors in `frontend/components/**` (must use Tailwind class or var)
(b) Style Dictionary build step that compiles tokens.json and exports a list of permitted tokens for runtime validation
(c) Pre-commit hook similar to the `edit-validator.sh` in CLAUDE.md §6, but for design

### G-16. No motion validator
**Issue:** Motion budgets per mode are documented but not enforced in code.

**v1.1 plan:** Add a hook/lint rule that flags `transition-duration` or `animation-duration` values exceeding the mode's budget.

### G-17. Accessibility deep-dive
**Issue:** Component specs cover keyboard + ARIA hints. Screen-reader walkthroughs, focus management within complex composites (DebatePanel, Canvas), color-contrast verification across the palette — all need a thorough pass.

**v1.1 plan:** Schedule an a11y review before the redesign branch merges to main.

---

## Status

This list is non-exhaustive. As the harness generates code against the v1 portfolio, expect to discover additional gaps. Append them here with a `G-NN` ID, severity, and v1.1 plan.

**Open count: 17.** Next review: when the redesign branch reaches feature parity with `main`.
