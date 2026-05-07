# Surface Spec — Profiles & Settings

**Mode:** CALM (the office)
**URL:** `/settings/{section}` — `/settings/profiles`, `/settings/exchange`, `/settings/tax`, `/settings/account`
**Backed by:** `api_gateway`, `tax`, auth/profile services
**Frequency:** the user spends 1–5% of their session here
**Density:** low

---

## 1. The CALM mode contract

This surface deliberately departs from HOT and COOL modes:
- generous whitespace,
- type one step larger (15px body baseline),
- form controls one size larger,
- one accent color, no agent identity colors anywhere,
- no live updates beyond standard form-save acknowledgments.

The user is configuring intent. They are *not* reacting to markets. The visual budget should reflect that.

---

## 2. Layout

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◀▶ ⚙ Profiles & Settings                                                       │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌── SETTINGS NAV ─────┬──── CONTENT ────────────────────────────────────────┐   │
│  │                     │                                                       │   │
│  │  Profiles           │   (selected section content here)                    │   │
│  │  Exchange keys      │                                                       │   │
│  │  Risk defaults      │                                                       │   │
│  │  Notifications      │                                                       │   │
│  │  Tax                │                                                       │   │
│  │  Account            │                                                       │   │
│  │  Sessions / API     │                                                       │   │
│  │  Audit log          │                                                       │   │
│  │                     │                                                       │   │
│  └─────────────────────┴───────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Two-column: 220px nav, flexible content. Content is bounded to a max-width of 720px and centered — this is not a full-bleed dashboard.

---

## 3. Profiles section (`/settings/profiles`)

A list of all trading profiles with summary info per profile. Each entry:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Aggressive-v3                                          [● Live]      │
│  Updated 2h ago · 14 nodes · 5 agents                                  │
│                                                                        │
│  Last 7 days                                                           │
│  PnL: +234.56 USDC   Trades: 42   Win rate: 58%                       │
│                                                                        │
│  [Open in canvas ▸]   [Edit settings ▸]   [Run backtest ▸]            │
└──────────────────────────────────────────────────────────────────────┘
```

Click the title to enter the profile's individual settings page (`/settings/profiles/Aggressive-v3`):
- Identity: name, description, tags
- Risk overrides for this profile (subset of risk defaults overridable)
- Symbols whitelist
- Schedule (active hours, days)
- Auto-pause triggers (e.g., "pause if drawdown > 5%")
- Audit history of changes

> **Important:** profile *editing* is split. Pipeline structure → Pipeline Canvas. Settings/identity → here. The split is by *domain*: behavior versus configuration. The harness should not mix them.

---

## 4. Exchange keys section

API keys for connected exchanges. Per CLAUDE.md security: never enter sensitive financial data on the user's behalf — direct them to enter it themselves. The form makes that explicit:

```
┌── Add exchange ─────────────────────────────────────────┐
│  Exchange:    [ Hyperliquid                          ▾ ] │
│  Label:       [ Main account                         ]   │
│  API Key:     [ ··········· (paste here)             ]   │
│  Secret:      [ ··········· (paste here)             ]   │
│  Permissions: ☐ trade  ☐ withdraw (recommend leaving off)│
│                                                          │
│  ⓘ Praxis never stores keys with withdraw permissions    │
│    enabled by default. Confirm withdraw is off in your   │
│    exchange API settings before saving.                  │
│                                                          │
│  [Cancel]                              [Save key]        │
└──────────────────────────────────────────────────────────┘
```

Saved keys appear masked (`hl_••••••••3a4f`); user can rotate/revoke; never re-displays a saved secret.

---

## 5. Risk defaults section

User-level risk caps that apply unless a profile overrides:
- Max position size per symbol (default config)
- Max leverage
- Max daily loss
- Rate limit (orders per minute)
- Auto-pause triggers

Same component patterns as Risk Control surface, but in CALM mode density (larger controls, more spacing). Saving recompiles affected profiles.

---

## 6. Notifications section

What events the user wants surfaced where:
- Email (rare, milestone events): daily summary, monthly tax report ready, profile drawdown trigger
- Push / in-app: kill-switch state changes, large fills, agent override events
- Audible (in-app only): user-configurable per event

Each event row is a Toggle + delivery-method multi-checkbox.

> **Anti-pattern note:** do not provide an "all on" / "all off" mega-toggle. Too easy to silence everything during a stressful moment. Each event configures separately.

---

## 7. Tax section

Surfacing the `tax` service:
- Generate tax report (year selector + jurisdiction)
- View prior reports
- Export to common formats (FIFO/HIFO/LIFO method selector — not a default)
- Manual lot adjustments (rare; appears with explainer)

This is mostly form-driven and CRUD; no special components beyond primitives.

---

## 8. Account section

- Display name + avatar
- Email (verified state)
- Password (CALM mode rule: never auto-fill or auto-set; user types directly per CLAUDE.md security)
- 2FA setup
- Theme preference (system / dark / light — though light is a future commitment, not a v1)
- Density preference (per-surface, set here as defaults)

---

## 9. Sessions / API section

- Active sessions (browser, device, last seen, IP) with revoke per session
- API tokens for programmatic access (create / revoke; full secret shown once at creation, then masked)
- Webhook destinations for events

---

## 10. Audit log

A read-only log of significant user actions:
- profile created/edited/deleted (with diff)
- kill-switch transitions (state, reason, timestamp)
- API key rotations
- override events from Agent Observatory
- failed authentication attempts

Filterable by event type and date range. Exportable as CSV. **Never** mutable from the UI.

---

## 11. Save model

CALM mode forms use explicit Save buttons (no auto-save, deliberately). After save:
- Inline success indicator (`✓ Saved`) for 4s, then fades
- "Unsaved changes" banner appears at top of section if user navigates away
- Back navigation prompts confirmation if unsaved

---

## 12. Empty states

| Region | Empty state |
|---|---|
| No profiles yet | "No profiles yet. Create one in Pipeline Canvas to start trading." [Open canvas] |
| No exchanges connected | "No exchanges connected. Add an exchange to enable live trading." [Add exchange] |
| No notification events configured | (default state — show all events as toggleable, defaults sensibly chosen) |
| Empty audit log | "No audit events recorded for this date range." |

---

## 13. Tone note

CALM mode tone is *officespace, not chatbot*. No "Hi! Ready to set up?" copy. No emojis. Direct, professional, considered. The user is making decisions about their money and identity; treat that with appropriate seriousness.
