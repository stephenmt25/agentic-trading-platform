# EN-W2 Per-Profile Edge Triage — Results (2026-06-12)

Executes locked decision #3 (first half). Verdicts and their rationale live in
`DECISIONS.md` (2026-06-12 entry); this file is the numbers + method record.

## Method

- **Runner**: `scripts/en_w2_edge_triage.py` (direct queue enqueue mirroring the
  gateway payload; runs as the profile owner's UUID).
- **Data**: 1m candles — the live evaluation timeframe
  (`services/strategy/src/hydrator.py` hydrates 1m) — 2026-04-18T00:00 →
  2026-06-12T12:00 (~57k bars), coverage 99.85% on every run.
- **Walk-forward**: train 20,160 bars (14d) / test 10,080 (7d) / step 10,080 →
  4 windows. OOS aggregate = trades ENTERED in test segments only (EN-W1).
- **Exits**: each profile's real `risk_limits` through the shared
  `libs/core/exit_policy.py`. Slippage 0.1%.
- **Baseline-poisoning guard**: the exploratory sweep ran with `profile_id=""`;
  canonical baselines enqueued LAST so `latest_for_profile()` resolves to them.
- Close-reason mixes below filter `close_reason="end_of_data"` (DECISIONS
  2026-06-11: one synthetic boundary close per window).

## MACD triage — all negative OOS, killed

| Run | Trades | Win rate | OOS sharpe | Avg ret | PF | MaxDD | Close mix (no eod) |
|---|---|---|---|---|---|---|---|
| trend-btc | 21 | 47.6% | **−4.35** | −0.63% | 0.48 | 18.3% | tp6 / time8 / sl3 |
| trend-eth | 23 | 43.5% | **−6.85** | −1.21% | 0.34 | 29.3% | tp8 / time7 / sl5 |
| pullback-btc | 40 | 47.5% | **−5.85** | −0.71% | 0.36 | 31.9% | time25 / tp8 / sl3 |
| pullback-eth | 43 | 44.2% | **−5.79** | −0.92% | 0.37 | 39.6% | time20 / tp13 / sl6 |
| oversold-btc | 22 | 22.7% | **−8.21** | −0.77% | 0.14 | 17.0% | time19 / sl1 |
| oversold-eth | 21 | 42.9% | **−2.74** | −0.42% | 0.62 | 14.9% | time17 / tp1 / sl2 |

Per-window in-sample sharpes: 21 of 24 windows negative; the 3 positive-IS
windows (+1.4, +1.1, +2.1) still produced negative-OOS aggregates. No edge
exists to rebuild. **Verdict: KILL** (profiles stay inactive; history kept).

## Soak profile (RSI<35, ETH/USDT) — exit-band A/B + canonical baseline

| Run | Trades | Win rate | OOS sharpe | Avg ret | PF | MaxDD | Close mix (no eod) |
|---|---|---|---|---|---|---|---|
| exit-band sweep (18 combos) | 73 | 45.2% | **−5.41** | −0.60% | 0.44 | 42.1% | tp28 / sl25 / time17 |
| plain baseline (current bands) | 104 | 42.3% | **−4.00** | −0.41% | 0.48 | 41.5% | time91 / sl5 / tp5 |

Sweep grid: SL {2,4}% × TP {1,2,3}% × hold {6,12,24}h. Per-window winners were
unstable (w1: SL4/TP1/24h · w2: SL2/TP2/24h · w3+w4: SL2/TP1/12h) and the
swept result is WORSE out-of-sample than the untouched bands — overfit
in-sample selection with no robust OOS improvement. **Verdict: bands stay;
re-banding cannot rescue a signal with no directional edge.**

`en-w2-soak-baseline` is now the soak profile's `latest_for_profile()` decay
baseline — its `no_baseline` status is resolved with an honest OOS row.

## Convergence (PR7 cross-check) — PASSES

| Source | n | time_exit | stop_loss | take_profit |
|---|---|---|---|---|
| Live soak closes | 30 | 93% | 7% | 0% |
| Backtest OOS (filtered) | 101 | 90% | 5% | 5% |

The sim's exit behavior matches live within a few points — the EN-W1 shared
exit-policy refactor is validated end-to-end against real soak data.

## Headline

Every current signal family (RSI soak + 3 MACD variants) has **negative
out-of-sample edge** on Apr–Jun 2026 data. The instrument is now honest; the
strategies it measures are not profitable. EN-W3/EN-W4 (Tokyo substrate,
Yield Harvester) is the path to the first defensible edge — flagged for
architect prioritization.
