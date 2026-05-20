# Phase 0 Soak — Launch Status & Partner Update

> **Date:** 2026-05-20
> **Status:** 14-day paper-trading soak **live and running clean**.
> **Companion docs:** `PLATFORM_VIABILITY_PLAN_2026-05-18.md` (§3 Phase 0), `TECH-DEBT-REGISTRY.md`.

---

## Partner update (message sent)

> Soak update — it's **live and running clean as of today**.
>
> The Phase 0 work (the tech-debt fixes that were distorting the numbers) is done and committed. The 14-day paper-trading soak is now up on a dedicated hold-style profile.
>
> During launch we caught a real bug in verification: the entry logic stacked a new position every tick the signal held — first boot opened ~190 positions in 17 seconds. Fixed it with a re-entry guard (one position per symbol at a time, matching the backtester) and confirmed the fix live: the profile now opens one position and correctly blocks re-entries while it's held.
>
> So we're properly running now — clean measurement, 14-day clock going. Next checkpoint is reviewing the daily P&L reports as they accumulate.

---

## What's running

- **Profile:** `Phase 0 Soak — Hold Baseline` (`a05adba2-5128-4bef-bb92-a3cb429b55e1`) — the only active profile. Entry `rsi < 35` → BUY; exits stop-loss 4% / take-profit 3% / `max_holding_hours` 6h (the time-exit dominates → hour-scale holds). `exchange_key_ref=paper`.
- **Engine:** all 19 services + frontend, live Binance market data.

## Launch verification (post re-entry-guard fix)

| Check | Result |
|---|---|
| Service ports | 17/17 up, `/ready` green |
| hot_path | loaded 1 profile (soak profile only) |
| Open positions | ETH/USDT: 1 — **not 192**; pyramiding fixed |
| Re-entry guard blocks | 11 — guard blocked re-entry while the position was held |
| Crashes | none |
| Frontend | `:3001` HTTP 200 |

## Commits (branch `main`)

| Commit | What |
|---|---|
| `cfc5b9a` | Phase 0 — tech-debt rows 18/27/31/32 + doc gap G-10 |
| `cfe379f` | daily_report cold-start daemon-resilience fix |
| `b264c81` | logged backtest-vs-live exit-model divergence (HIGH) |
| `8af7a13` | hot_path re-entry guard — one open position per (profile, symbol) |

## Operational notes (soak hygiene)

- Laptop must be set to **never sleep** for the 14-day duration.
- Keep a **downtime log** — any sleep / restart / ISP blip is soak *data*, not automatically a soak failure (uptime is the property under test per `PLATFORM_VIABILITY_PLAN_2026-05-18.md` §1).
- `run_all.sh --stop` leaves an orphaned `:3001` process and detached service children — verify with `netstat` / a `python.exe` check after stopping.
- Review the daily P&L report as days accumulate; exit criterion is a coherent PnL distribution over hour-scale-hold trades.
