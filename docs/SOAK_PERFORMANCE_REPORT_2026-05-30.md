# Phase 0 Soak Profile — Performance Report

> **Reporting window:** 2026-05-26 13:00 UTC → 2026-05-30 12:56 UTC (~3.99 days)
> **Profile:** `Phase 0 Soak — Hold Baseline`
> **Profile ID:** `a05adba2-5128-4bef-bb92-a3cb429b55e1`
> **Created:** 2026-05-20 (purpose-built for the May 18 plan's §3 Phase 0 measurement)
> **Mode:** Paper trading (no real money at risk)

## Starting conditions

| Field | Value |
|---|---|
| Notional capital (paper) | **$10,000** |
| Allocation cap per trade | 25% of notional (`max_allocation_pct: 0.25`) |
| Actual position sizing observed | ~$1,500 per trade (~15% of notional) |
| Exchange | Binance Spot (live market data, paper-fill simulation) |
| Fee model | 0.10% taker per side = 0.20% round-trip (matches Binance retail) |
| Symbol universe | BTC/USDT + ETH/USDT (only ETH has fired so far) |

## Strategy configuration

```
Entry:  RSI < 35  →  BUY    (long-only, no short)
Logic:  AND                  (single condition)
Base confidence: 0.6
```

## Risk limits

| Field | Value |
|---|---|
| Stop-loss | 4% adverse move |
| Take-profit | 3% favourable move |
| Max holding time | **6 hours** (the dominant exit in this sample) |
| Max drawdown (profile-level) | 10% |
| Daily circuit-breaker | 5% loss |

Profile was deliberately designed to be a slow, hold-style "honest measurement instrument" per May 18 plan §3 Phase 0. Stop-loss/take-profit are intentionally wide so the 6h time-exit dominates, producing reliable hour-scale holds that exercise the laptop-uptime hypothesis.

## Trade-by-trade

| # | Date (UTC) | Symbol | Entry | Exit | Qty | Hold | Realised P&L | % return | Close reason |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | 05/27 08:33 → 14:33 | ETH/USDT | $2,095.10 | $2,061.42 | 0.7429 | 6.00h | **-$28.11** | -1.81% | `time_exit` |
| 2 | 05/27 17:45 → 05/28 10:32 | ETH/USDT | $2,056.56 | $1,992.70 | 0.7740 | **16.78h** ⚠ | **-$52.56** | -3.30% | `time_exit` |
| 3 | 05/28 10:53 → 16:53 | ETH/USDT | $1,990.91 | $2,012.97 | 0.7671 | 6.00h | **+$13.85** | +0.91% | `time_exit` |
| 4 | 05/29 06:33 → 12:33 | ETH/USDT | $2,017.30 | $2,002.98 | 0.7243 | 6.00h | **-$13.28** | -0.91% | `time_exit` |
| 5 | 05/30 04:28 → 10:28 | ETH/USDT | $2,011.19 | $2,019.93 | 0.7492 | 6.00h | **+$3.53** | +0.23% | `time_exit` |
| **Open** | 05/30 12:08 → ... | ETH/USDT | $2,018.78 | _live_ | 0.7100 | _in flight_ | _unrealised_ | _live_ | `time_exit` due ~18:08 |

**Total fees paid:** $15.18 across 5 round-trips (~$3.04 per trade).

## Headline aggregates

| Metric | All 5 closed | Excluding the downtime-contaminated trade #2 |
|---|---:|---:|
| Trades | 5 | 4 |
| Net realised P&L | **-$76.57** | **-$24.01** |
| % of notional | -0.77% | -0.24% |
| Win rate | 40% (2W / 3L) | 50% (2W / 2L) |
| Avg P&L per trade | -$15.31 | -$6.00 |
| Avg hold time | 8.16h | 6.00h (exactly the cap) |
| Trades hitting take-profit (3%) | **0** | 0 |
| Trades hitting stop-loss (4%) | **0** | 0 |
| Trades closed via `time_exit` | **5 (100%)** | 4 (100%) |

## Decision pipeline funnel (transparency)

Total signals the strategy produced during the window:

| Decision outcome | Count | What it means |
|---|---:|---|
| APPROVED | 26 | Strategy fired + passed all gates + emitted order |
| BLOCKED_REENTRY | 88 | Strategy fired but re-entry guard correctly blocked (open position already held) |
| Total decisions | 114 | |

Of the 26 APPROVED, only **6 became actual filled positions** (5 closed + 1 open). The 20 missing fills all happened **2026-05-26 → 27** during a silent-fail incident where execution's main loop had crashed from a Redis timeout (the bug we discovered, root-caused, and fixed during this session with three layers of new safeguards). **Since the fix landed on 2026-05-27 ~13:00, the funnel has been 100% honest: every APPROVED decision has become a filled position.**

## Operational notes that affect interpretation

| Event | Window | Duration | Impact on the soak |
|---|---|---:|---|
| Execution silent fail | 05/26 22:13 → 05/27 ~12:40 | ~14.5h | Lost 20 APPROVED-to-fill conversions — non-fee soak data loss |
| Laptop sleep — charger failed | 05/27 23:41 → 05/28 10:31 | **~10h 49m** | Trade #2 held 16.8h instead of 6h; rode ETH down for ~$24 of excess loss |
| Laptop nap cluster | 05/29 06:48 → 08:04 | ~31m intermittent | No trade impact (none open) |
| Laptop nap | 05/30 09:36 | <30s | No trade impact |
| **Total observed downtime** | | **~12h of the 96h window (~12.5%)** | |

After the fail-safe stack was built (Layers 1, 2, and 3), every subsequent restart and every laptop sleep has been recovered from cleanly — no silent failures since the fix.

## Reading the numbers

Three things stand out.

**1. The strategy has no demonstrated edge in this sample.** All 5 exits hit the 6h time cap. Take-profit (3%) and stop-loss (4%) bands were touched **zero times** — across 5 positions × 6h each = 30 trading hours, ETH never moved 3% or 4% inside any window. The price oscillates ±0.2 to ±1.8% during the hold, never reaching either intentional exit. Net realised: small grinding losses, statistically indistinguishable from noise on a 4-trade sample (excluding the downtime outlier).

**2. This matches the May 16 partner-meeting finding exactly.** That review of legacy data found *"86% of trades exit via time_exit at a small loss; the system enters positions that don't reach their take-profit target."* The soak is now reproducing that pattern on a clean, fresh sample with all the new fail-safes in place. The diagnosis was correct: the strategy as configured is not finding edge.

**3. The downtime contamination is real but bounded.** Trade #2's extra $24 of loss is purely attributable to the laptop sleeping through its intended 6h exit. Strip it, and the honest result is -$24 across 4 trades — small bleed, not catastrophic. But this is exactly the failure mode the May 18 plan §1 warned about: a laptop is not a trustworthy measurement instrument for hold strategies. The soak is, in a sense, *succeeding* — it's proving §1's thesis with hard data.

## What it does NOT tell us

- **Whether the strategy works on a longer hold window.** The current 6h cap may simply be too short. A 24h or 48h cap might let the mean-reversion thesis play out.
- **Whether the strategy works on BTC.** BTC RSI hasn't dipped below 35 once during this window — the soak has only sampled ETH behaviour.
- **Whether the strategy works in different market regimes.** This was a 4-day mid-volatility window with both symbols range-bound around their entry levels. Strong trends (up or down) would produce very different statistics.
- **Statistical significance.** 5 trades is too few to draw meaningful conclusions about edge or its absence. The 4-trade clean sample is essentially break-even and within noise.

## System health behind the numbers

| Layer | Status |
|---|---|
| End-to-end pipeline (signal → gate → fill → close → realised P&L) | working since 2026-05-27 ~13:00 |
| Fail-safe Layer 1 (per-service supervisors) | active, 0 unrecovered crashes in 3.5 days |
| Fail-safe Layer 2 (cross-service heartbeat watcher) | active, correctly fired wake alerts on every sleep event |
| Fail-safe Layer 3 (predicted-trade oracle) | active, 0 unexplained divergence alerts after the stage-1 tuning fix |
| Silent failures since 2026-05-27 fix | **0** |

The infrastructure is in a state where, going forward, any new soak data is genuinely trustworthy. Whatever's underperforming is the *strategy*, not the system.

## Recommendation

Two parallel paths once a decision is made:

1. **Move to cloud** (May 18 plan §3 Phase 1) — eliminate the laptop-substrate contamination so the measurement instrument is honest. The soak proved its own thesis here: ~12.5% downtime over 4 days, one trade meaningfully distorted.
2. **Either widen the exit bands or extend `max_holding_hours`** — the current parameters produce a degenerate measurement where 100% of trades exit on time. We're measuring the *time-exit safety valve*, not the *strategy*.

If you want a different-shaped soak measurement, just say the word and we can clone the profile with adjusted parameters and run it in parallel.
