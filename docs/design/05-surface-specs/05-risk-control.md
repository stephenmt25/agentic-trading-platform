# Surface Spec — Risk Control

**Mode:** HOT (this surface MUST stay responsive when others degrade)
**URL:** `/risk`
**Backed by:** `risk`, `pnl`, `rate_limiter`, kill switch (Redis key)
**Frequency:** the user spends 2–10% of their session here, but it's the highest-stakes surface
**Density:** medium — togglable per IA §5 (compact / standard / comfortable), but **default is `standard`** and we recommend users keep it there. Legibility under stress is prioritized over density on this surface; users may opt into compact if they prefer.

> **Architectural note:** this is the only surface that operates correctly when the rest of Praxis is degraded. The kill switch must work even if the agent system, canvas, or backtest engine is down. The harness should treat this as a separate availability tier.

---

## 1. Layout

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◀▶ 🛡 Risk Control                                                              │
│ ⚖ portfolio +0.84%   pnl 24h +1,234.56 USDC   leverage 2.4× / max 5×           │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌── KILL SWITCH ──────────────────────────────────────────────────────────┐    │
│  │                                                                          │    │
│  │     ╔════════════════════════════════════════╗                           │    │
│  │     ║   STATE: ARMED (soft)                  ║   [ Disarm ]              │    │
│  │     ║   set 4m ago by you · reason: "review" ║   [ Hard-arm ]            │    │
│  │     ╚════════════════════════════════════════╝                           │    │
│  │                                                                          │    │
│  │   Soft-arm: blocks new orders. Existing positions remain.                │    │
│  │   Hard-arm: blocks new orders AND auto-flattens all positions at market. │    │
│  │                                                                          │    │
│  │   Cmd+Shift+K to toggle                                                  │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌── EXPOSURE ──────────────────────────────────────────────────────────────┐    │
│  │   Leverage: ●────────────● 2.4× / 5.0×    [RiskMeter]                    │    │
│  │   Portfolio VaR (1d, 95%): -2,134 USDC of 10k equity (-21%)             │    │
│  │   Concentration: BTC 62% · ETH 28% · others 10%                          │    │
│  │   Drawdown: -3.2% (peak: 2026-04-12, recovered)                         │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌── ACTIVE LIMITS ─────────────────────────────────────────────────────────┐    │
│  │  ✓ max position size BTC: 0.5  (current 0.18)                            │    │
│  │  ✓ max leverage: 5×  (current 2.4×)                                      │    │
│  │  ⚠ daily loss limit: -1,500 USDC  (current -890; 60% utilized)           │    │
│  │  ✓ rate limit: 60 orders/min  (last 1m: 4)                               │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌── RECENT VIOLATIONS ─────────────────────────────────────────────────────┐    │
│  │  14:21  rejected: would exceed max position BTC                           │    │
│  │  09:43  rejected: rate limit (60/min)                                    │    │
│  │  yesterday 22:11  warning: daily loss approaching                        │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Single column, large typography (this surface is read at distance during stress). Sections in fixed order:

1. **Kill switch** — primary, top-of-fold
2. **Exposure** — RiskMeters for leverage, VaR, concentration, drawdown
3. **Active limits** — list of all configured limits with current utilization
4. **Recent violations** — chronological log of recent rejections/warnings

---

## 2. The kill switch

This is the centerpiece. It has three states:

| State | Meaning | Visual |
|---|---|---|
| **Off** | Normal operation | neutral border, "DISARMED" label, single button "Arm soft" |
| **Soft-armed** | Blocks new orders; existing positions unaffected | `warn.500` border, label "ARMED (soft)", buttons "Disarm" + "Hard-arm" |
| **Hard-armed** | Blocks new orders AND auto-flattens at market | `danger.500` border with subtle pulse, label "ARMED (hard) — flattening", "Disarm" button visible but secondary |

**Activation flow:**
- Soft-arm: one-click, optional reason field. Confirmation: "Arm soft kill switch?" + reason input + [Confirm]
- Hard-arm: required reason. Confirmation: "ARM HARD KILL SWITCH? This will close all positions at market." + reason + [Confirm again to arm]
- Disarm: required reason. Confirmation: "Disarm? Trading will resume immediately." + reason + [Confirm]

All transitions logged to the analyst archive with user, timestamp, reason.

**The Cmd+Shift+K shortcut** opens a modal that lets the user transition state from anywhere in the app, not just on this surface. Keyboard-driven.

---

## 3. Exposure section

For each metric:
- **Leverage** — RiskMeter with thresholds at 60% (amber) and 85% (red) of configured max
- **VaR** — bar showing current VaR vs equity, with percentile
- **Concentration** — stacked horizontal bar by symbol; rendered with neutral grays + agent identity not used here (these are symbols, not agents)
- **Drawdown** — sparkline of equity, peak marked, current drawdown shown as a value

Each is clickable to expand a drawer with historical context (last 7d / 30d).

---

## 4. Active limits

A list of every limit configured for the active profile. Each row:
- StatusDot (green if utilization <60%, amber if 60–85%, red if 85%+)
- Limit name + spec (e.g., "max position size BTC: 0.5")
- Current value + utilization percentage
- "edit ▸" link → goes to Profiles & Settings for this profile

The user can see *all* limits, not just the ones being approached. Surfacing only the worrying ones would give a false sense of safety.

---

## 5. Recent violations

A reverse-chronological log of:
- order rejections (rate limit, position size, leverage, etc.)
- warnings (daily loss approaching, regime-change-triggered review)
- kill-switch state changes

Grouped by day. Each entry links to the relevant violation source: rejected order links to the would-be order detail; warnings link to the underlying calculation; kill-switch entries link to the analyst archive.

---

## 6. Live behaviour

- All metrics update on every PnL tick (subscribes to `pubsub:pnl_updates`).
- RiskMeter needles animate between values with `--duration-snap` ease.
- Limit utilization reflects rate_limiter and risk service state.
- Violations appear in the log within 200ms of occurrence.

---

## 7. Keyboard map

| Key | Action |
|---|---|
| `Cmd+Shift+K` | Open kill-switch modal (works from any surface) |
| `K` (on this surface) | Focus the kill-switch buttons |
| `D` | Focus the disarm button (when armed) |
| `J` / `K` | Down / up through violations log |
| `Cmd+K` | Command palette |

---

## 8. Edge / failure cases

| Case | Treatment |
|---|---|
| Kill switch toggle fails to write to Redis | Modal stays open, error banner: "Could not arm. Retry — the system has not changed state." Never silently fails. |
| PnL stream stalls | Metrics show the staleness in their headers ("3m ago"); RiskMeter needle stops moving but does not show stale colors |
| Risk service unreachable | Banner at top of surface: "Risk service unreachable — limits cannot be enforced." Surface remains read-only; kill-switch still operable (it talks to Redis directly) |
| User attempts to disarm when hard-armed and positions are still flattening | Disarm refused with explanation: "Cannot disarm during active flatten. Wait for completion (~30s) or contact admin." |

---

## 9. Empty states

| Region | Empty state |
|---|---|
| No active profile | "No active profile. Risk Control monitors active trading; activate a profile in Pipeline Canvas to see live risk." |
| No violations ever | "No violations recorded. Limits are working as configured." (this is intentionally a positive empty state) |
| No positions, no exposure | Exposure metrics show zero values explicitly, not hidden. "No positions — exposure is zero." |

---

## 10. Tone note

This surface is **not** spartan in the way Hot Trading is. The design philosophy here is *legibility over density*. Type one step larger. Spacing one step wider. Confirmations always. The cost of misreading risk control is much higher than the cost of an extra second to read it.

This is the only HOT-mode surface where motion can be slightly more expressive (the kill-switch border pulse, the meter needle ease) — because the user needs to *feel* the change of state, not just see it.
