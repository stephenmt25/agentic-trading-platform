# Test-Strategy Portfolio — System-Capability & Meta-Learning Suite

### 2026-06-13 · paper-trading profiles to exercise the platform end-to-end and feed the learner

**Audience:** architect / operator · **Author:** Claude Code (handler: Stevo) · **Companions:** `docs/EXECUTION-BRIEF-2026-06-13-DEBT-BURNDOWN.md`, `docs/PARTNER-DECISIONS-BRIEF-2026-06-13.md`.

Every strategy here is **DSL-valid and grounded in the code** as it stands on `feat/snappy-honest-edge` (`7b8361d`) — the indicator names, operators, regime names, and risk-limit bounds were verified against `libs/core/schemas.py`, `libs/indicators/`, and `libs/core/enums.py` before authoring. Configs are given verbatim so they can be created directly.

---

## 1 · Purpose & framing — these are instruments, not bets

The debt burn-down made the platform's measurement honest, and that same honesty produced the headline: **no current signal family has positive out-of-sample edge.** So this portfolio is explicitly *not* a hunt for profit. It has three jobs, in priority order:

1. **Capability testing** — exercise every part of the strategy-support surface the system claims to have: every authorable indicator, both entry legs, every regime gate, every risk-limit dimension, symbol-scoping, the multi-agent ensemble, and the full close-reason vocabulary. Find the parts that don't work, or don't exist.
2. **Issue shakeout** — several profiles are deliberately built to stress edge cases (never-fires, always-fires, spot shorts, circuit-breaker trips, tight-churn ledgers, price-scale footguns) so that bugs surface in paper trading rather than in front of capital.
3. **Meta-learning diversity** — the agent EWMA weights were clean-reset this session and currently sit at `AGENT_DEFAULTS`. A learner fed only the running RSI<35 mean-reversion soak would overfit to one archetype. This suite gives it a *diverse decision-trace substrate* (long/short, fast/slow, trend/reversion/breakout, every close reason) so future autonomous weighting and decay decisions rest on varied evidence.

> **Negative or flat PnL on these profiles is an acceptable — even expected — outcome.** The deliverable is coverage and learning signal. A profile that loses money cleanly, with correctly-attributed close reasons and honest decay, is a *successful* test. The only failures that matter are system bugs and capability gaps.

**Two hard operating constraints** carried from the session, baked into the rollout plan (§6):

- The **live soak (profile `a05adba2`) must not be disrupted.** New profiles are additive and small-allocation; no existing profile is touched.
- **Decay baselines are latest-wins.** Any backtest carrying a `profile_id` overwrites that profile's baseline, so exploratory backtests for these profiles must use `profile_id=""` (the documented guard).

## 2 · What the system can and cannot express (the capability map)

Designing this suite was itself the most thorough capability audit the strategy surface has had. The findings below are as valuable as the strategies — they define the real envelope, and two of them are recommended as tech-debt rows.

### 2.1 · What a strategy CAN express today

- **Two entry legs:** `entry_long` and `entry_short`, each a list of conditions combined by `match_mode` (`all`=AND, `any`=OR). A legacy single-direction shape also exists.
- **A condition** is `{indicator, comparison, threshold}` — `comparison` ∈ {above, below, at_or_above, at_or_below, equals} → canonical {GT, LT, GTE, LTE, EQ}.
- **Regime gating** via `preferred_regimes` (allowlist subset of TRENDING_UP / TRENDING_DOWN / RANGE_BOUND / HIGH_VOLATILITY / CRISIS; empty = agnostic). CRISIS short-circuits to no-trade globally.
- **Risk limits** (all bounded this session): `stop_loss_pct`, `take_profit_pct` ∈ (0,1]; `max_holding_hours` > 0; `max_allocation_pct`, `max_drawdown_pct`, `circuit_breaker_daily_loss_pct` ∈ (0,1]. Exit precedence is SL → TP → time (`libs/core/exit_policy.py`).
- **Symbol scoping** via the `blacklist` (text[]): a profile evaluates against *every* universe symbol (BTC/USDT, ETH/USDT); to scope to one, blacklist the others. There is **no symbol allowlist field**.
- **Static confidence** scalar per profile, blended downstream with the TA/sentiment/debate agent scores via the (just-reset) dynamic EWMA weights.

### 2.2 · The authorable-indicator gap — FINDING (recommend a tech-debt row)

`SUPPORTED_INDICATORS` (the canonical engine set, `schemas.py:608-628`) lists **19** keys and all 19 are computed every tick. But the user-facing DSL (`_UserIndicatorName` + `_INDICATOR_USER_TO_CANONICAL`, `schemas.py:678-710`) only maps **12**. So `POST /profiles` **422-rejects 7 indicators that the engine fully supports**:

| | Indicators | Reachable via `POST /profiles`? |
|---|---|---|
| **Authorable (12)** | `rsi`, `atr`, `macd_line`, `macd_signal`, `macd_histogram`, `vwap`, `keltner.upper/middle/lower`, `rvol`, `z_score`, `hurst` | **Yes** |
| **Engine-only (7)** | `adx`, `obv`, `choppiness`, `bb.pct_b`, `bb.bandwidth`, `bb.upper`, `bb.lower` | **No** — canonical write only (DB / canvas), API rejects |

The single most-requested trend-strength gate (`adx > 25`) and all Bollinger-band and volume-balance signals are **not buildable through the documented API**. They are reachable only by writing canonical `strategy_rules` directly. **Recommendation:** either extend `_UserIndicatorName` + the map to all 19 (small, mechanical) or document the 12-key surface as intentional — today the mismatch is silent. (This is why 7 of the 26 strategies below are tagged CANONICAL-ONLY.)

### 2.3 · The indicator-vs-constant limitation — FINDING (the deeper one)

Every condition compares an indicator to a **fixed scalar**. The DSL has **no indicator-to-indicator, no price-relative, and no crossover/cross-event comparison.** The consequences are structural, not cosmetic:

- **Crossover strategies are inexpressible.** 'MACD line crosses above signal', 'price crosses above keltner.upper', golden/death cross, RSI divergence — none can be written. You can only ask 'is X above a constant *right now*', which fires for the whole duration the level holds, not on the cross. Entries are systematically late and noisy.
- **Price-level indicators are footguns.** `vwap`, `keltner.*`, `bb.upper/lower`, `atr` (absolute), `obv` are dollar/price-scale and *vary by symbol and over time*. A threshold sane for BTC (~$65k) is nonsense for ETH (~$3k), and the DSL applies one scalar across the whole universe. A condition like `keltner.upper above 200000` is **silently BTC-only-and-usually-dead.** Only the *normalized* indicators yield meaningful cross-symbol signals: `rsi` (0–100), `z_score` (~±3), `bb.pct_b` (0–1), `choppiness` (0–100), `rvol` (ratio), `hurst` (~0.5), and `macd_*` (oscillate around 0, sign-meaningful).
- **No stateful logic:** no trailing/break-even stops, no scale-out/partial close, no sequence/dwell ('RSI < 30 for 3 bars'), no M-of-N weighting (match_mode is binary all/any).
- **No opposing-signal close:** only SL/TP/time close a position. A long cannot be flattened by a fresh short signal — a 'flip on reversal' system degrades to 'hold to stop/target/timeout'.
- **No multi-timeframe:** indicator periods are fixed in the calculators (RSI14, MACD 12/26/9, Hurst50, …) and not settable via `rules_json`.
- **No perp / funding / leverage / multi-leg / cross-symbol spread** — all EN-W3 territory.

### 2.4 · The spot-short question (the #1 thing to watch)

`entry_short` validates, compiles to a real SELL leg, and the PnL calculator simulates it sign-correctly (`calculator.py:41-42`). So on a **spot-only** universe the paper engine will **open a real short position in an instrument the live exchange could never fill.** Whether that is the intended paper behavior, and whether the short's SL/TP precedence (SL above entry, TP below), protective-stop side, and reconciliation are all correct, is the highest-value thing this suite probes. Real shorting needs margin/perp (EN-W3).

## 3 · The test portfolio

**26 strategies across 6 categories** — after the 3 macd name-form fixes: **19 API-authorable** (deployable today via `POST /profiles`) and **7 canonical-only** (need a direct canonical write — see §2.2 / §6). Each strategy lists exactly what it tests and the behavior that would count as an issue if it deviates.

### Category — Trend-Following & Momentum

This category stress-tests the trend/momentum slice of the pipeline: the MACD trio (macd_line/signal_line/histogram), the regime-preference gate against the two TRENDING_* regimes, the `entry_short` leg (the short code path), and the long-holding-window branch of the exit policy. It is deliberately constructed to flush out three SYSTEM behaviors, not to make money (every signal family has negative OOS edge per the session context):

1. **The DSL-vs-engine indicator gap.** The hot-path eval_dict ALWAYS contains `adx`, `obv`, `choppiness`, and the four `bb.*` keys (services/hot_path/src/strategy_eval.py:126-148 — all 13 calculators are unconditionally instantiated in libs/indicators/__init__.py:67-83), but the user-facing DSL transformer `_INDICATOR_USER_TO_CANONICAL` (libs/core/schemas.py:696-710) only maps 12 names and OMITS adx/obv/choppiness/bb.*. So the prompt's headline "ADX trend-strength gate" is NOT authorable via `POST /profiles` today. I designed the ADX-strength rider to PROVE this gap (it would 422 at the schema) and then provide a hurst-based fallback that IS authorable — making the limitation concrete rather than theoretical.

2. **The short path on a spot universe.** `entry_short` compiles to a real SELL leg (services/strategy/src/compiler.py:92-111) and the PnL calculator simulates it sign-correctly: `gross = (entry - cp) * qty` (services/pnl/src/calculator.py:41-42). So a paper short opens a real short position with directionally-correct PnL — on a SPOT venue that could never actually borrow/short the asset. This category puts a live short into the soak to confirm the paper engine simulates an instrument the live exchange can't fill (EN-W3 territory).

3. **The asymmetric regime dampener.** TRENDING_DOWN multiplies confidence by 0.5 vs TRENDING_UP's 1.0 (services/hot_path/src/regime_dampener.py:30-35). A short profile gated to TRENDING_DOWN is structurally down-sized before it ever reaches the risk gate — exactly the kind of hidden sizing asymmetry the meta-learner should see reflected in realized-vs-expected fill rates.

#### MACD-Histogram Dual-Leg Momentum (BTC+ETH)  — ✅ API-authorable

*Bet that positive MACD histogram = upward momentum (go long) and negative histogram = downward momentum (go short); a pure stateless momentum-sign reader.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "macd_histogram",
      "comparison": "above",
      "threshold": 0.0
    },
    {
      "indicator": "macd_line",
      "comparison": "above",
      "threshold": 0.0
    }
  ],
  "match_mode_long": "all",
  "entry_short": [
    {
      "indicator": "macd_histogram",
      "comparison": "below",
      "threshold": 0.0
    },
    {
      "indicator": "macd_line",
      "comparison": "below",
      "threshold": 0.0
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.6,
  "preferred_regimes": [
    "TRENDING_UP",
    "TRENDING_DOWN"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.03,"take_profit_pct":0.06,"max_holding_hours":24,"max_allocation_pct":0.1,"max_drawdown_pct":0.15,"circuit_breaker_daily_loss_pct":0.1}`  ·  **blacklist:** `[]`  ·  **regimes:** `["TRENDING_UP","TRENDING_DOWN"]`

**Tests:** Both-legs DSL shape (entry_long + entry_short, libs/core/schemas.py:773-777); the SELL/short code path end-to-end (compiler.py:92-111 -> calculator.py:41-42); sign-invariant thresholds (histogram/line crossing 0 is scale-correct across BTC ~$60-100k and ETH ~$3k since macd_line is a raw price-EMA difference, _macd.py:29,38); regime-preference gate to BOTH trending regimes; the both_legs_matched no-op guard (compiler.py:98-107) — with threshold 0.0 on both legs, hist=0 exactly can't satisfy both (strict >/<).

**Expected behavior (deviation = issue):** Fires often on both symbols (histogram flips sign frequently intraday). Long in TRENDING_UP, short in TRENDING_DOWN; BLOCKED_REGIME_MISMATCH (shadow) in RANGE_BOUND/HIGH_VOLATILITY; zero trades in CRISIS. Shorts arrive pre-halved by the TRENDING_DOWN 0.5 dampener so fewer survive the risk gate than longs. Most closes are SL/TP within the 24h window; few time-exits. Negative net PnL expected (momentum-sign chasing bleeds on fees/whipsaw).

#### Hurst Persistence Trend-Rider (BTC-only, long)  — ✅ API-authorable

*Bet that when the Hurst exponent shows persistence (H>0.5) AND MACD line is positive, the BTC trend continues — ride it with a long holding window. This is the AUTHORABLE substitute for the ADX-strength gate that the DSL can't express.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "hurst",
      "comparison": "above",
      "threshold": 0.55
    },
    {
      "indicator": "macd_line",
      "comparison": "above",
      "threshold": 0.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.5,
  "preferred_regimes": [
    "TRENDING_UP"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.05,"take_profit_pct":0.12,"max_holding_hours":120,"max_allocation_pct":0.08,"max_drawdown_pct":0.2,"circuit_breaker_daily_loss_pct":0.08}`  ·  **blacklist:** `["ETH/USDT"]`  ·  **regimes:** `["TRENDING_UP"]`

**Tests:** Long-only single-leg both-legs shape (entry_long only, no entry_short — valid per the _at_least_one_leg validator, schemas.py:786-804); the hurst calculator (single-window R/S, libs/indicators/_hurst.py — output ~log(R/S)/log(50), centred near 0.5, returns None until 51 bars prime); LONG holding window (max_holding_hours=120, 5 days) exercising the time_exit branch (exit_policy.py:147) far less often than SL/TP; blacklist as symbol-scoping (BTC-only via ["ETH/USDT"]); ReentryGate one-position-per-(profile,symbol).

**Expected behavior (deviation = issue):** Fires moderately on BTC only, only in TRENDING_UP. Long priming delay (~51+ ticks for hurst). Wide 5%/12% SL/TP with a 5-day cap means positions live long — time_exit becomes a realistic close reason here (unlike the tighter profiles). Sized at 1.0x in TRENDING_UP (no dampener penalty). Expected negative-to-flat PnL; the value is exercising the long-hold path and the hurst calculator under live ticks.

#### ADX Trend-Strength Rider (DELIBERATE DSL-LIMIT PROBE)  — ⚠ canonical-only (uses adx)

*The textbook trend-strength gate: long when ADX>25 (strong trend) and MACD line positive. Authored EXACTLY as the prompt's brief asks — to prove the public DSL rejects ADX.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "adx",
      "comparison": "above",
      "threshold": 25.0
    },
    {
      "indicator": "macd_line",
      "comparison": "above",
      "threshold": 0.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.55,
  "preferred_regimes": [
    "TRENDING_UP",
    "TRENDING_DOWN"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.04,"take_profit_pct":0.08,"max_holding_hours":72,"max_allocation_pct":0.07,"max_drawdown_pct":0.18,"circuit_breaker_daily_loss_pct":0.09}`  ·  **blacklist:** `[]`  ·  **regimes:** `["TRENDING_UP","TRENDING_DOWN"]`

**Tests:** NEGATIVE TEST: that `adx` is NOT in _UserIndicatorName / _INDICATOR_USER_TO_CANONICAL (schemas.py:678-710) even though it IS in SUPPORTED_INDICATORS (schemas.py:608-628) and always computed (strategy_eval.py:126-127). POST /profiles should REJECT this with a 422 at StrategySignal.indicator validation. Confirms the DSL-surface/engine-surface divergence and that the API gateway validates indicator names at write time. If it somehow accepts (e.g. a loose validation path), that is a high-severity finding.

**Expected behavior (deviation = issue):** Should FAIL to create (422 Unprocessable Entity — 'adx' not a valid _UserIndicatorName). It must NOT become a live profile. If creation succeeds, the system has an indicator-allowlist hole. If creation is rejected as designed, swap to the Hurst rider above as the authorable equivalent. This profile is a contract assertion, not a trader.

#### MACD Line-vs-Signal Trend Confirm (ETH-only, short-biased)  — ✅ API-authorable

*Bet that MACD line below its signal line = bearish momentum; short ETH in down-trends. Stresses the short leg in isolation on the lighter-priced symbol where macd absolute magnitudes differ from BTC.*

**rules_json:**

```json
{
  "entry_short": [
    {
      "indicator": "macd_line",
      "comparison": "below",
      "threshold": 0.0
    },
    {
      "indicator": "macd_histogram",
      "comparison": "below",
      "threshold": 0.0
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.7,
  "preferred_regimes": [
    "TRENDING_DOWN"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.025,"take_profit_pct":0.05,"max_holding_hours":12,"max_allocation_pct":0.06,"max_drawdown_pct":0.12,"circuit_breaker_daily_loss_pct":0.07}`  ·  **blacklist:** `["BTC/USDT"]`  ·  **regimes:** `["TRENDING_DOWN"]`

**Tests:** Short-ONLY profile (entry_short only — no long leg ever emitted) so 100% of its signals exercise the SELL path; the TRENDING_DOWN-only gate intersected with the 0.5 confidence dampener (regime_dampener.py:34) — high authored confidence (0.7) lands at effective 0.35, probing whether 0.35 clears the downstream confidence floor / risk gate at all; ETH-only scoping via blacklist ["BTC/USDT"]; spot-short simulation realism (calculator.py:41-42 opens a short the spot venue can't borrow).

**Expected behavior (deviation = issue):** Fires only on ETH and only in TRENDING_DOWN — rare, since TRENDING_DOWN is itself less common and the gate is narrow. Confidence arrives halved (0.7->0.35) by the dampener; if a confidence floor exists downstream, this profile may silently never trade — a useful 'never-fires wastes a profile slot' signal. Tight 2.5%/5% SL/TP with a 12h cap. Negative-to-flat PnL expected.

**Issues this category is built to surface:**

- **DSL cannot author ADX/OBV/choppiness/bb.* even though the engine computes them every tick.** SUPPORTED_INDICATORS (schemas.py:608-628) is a superset of the authorable `_UserIndicatorName` (schemas.py:678-710). The ADX rider profile is built to make `POST /profiles` 422 on this. If it instead accepts, there is an allowlist hole. Either way this is the headline finding: the prompt's own "ADX trend-strength gate" is not buildable through the public API today.
- **Does entry_short open a REAL short paper position on a SPOT-only venue?** Yes (calculator.py:41-42 + executor.py:467-480). The short profiles confirm the paper engine simulates an instrument (borrowed short of BTC/ETH) the live spot exchange could never fill — any short 'edge' is unrealizable live without margin/perp (EN-W3). This is a paper-vs-live fidelity gap the soak should expose.
- **Short profiles are silently down-sized.** TRENDING_DOWN's 0.5 confidence multiplier (regime_dampener.py:34) means the short-only ETH profile's authored 0.7 confidence reaches the risk gate as 0.35. If a downstream confidence floor exists, the profile may NEVER trade despite being is_active — a 'never-fires wastes a profile slot / CPU' edge case.
- **Two profiles trading the same symbol race the ReentryGate.** The dual-leg BTC+ETH profile and the BTC-only Hurst rider both target BTC; they are SEPARATE (profile, symbol) keys so each can hold one BTC position concurrently — confirm they don't clobber each other's open_position_symbols reconciliation (state.py:64-74) or the optimistic-ts dedupe.
- **both_legs_matched no-op.** With histogram/line both thresholded at 0.0 (strict >/<), the dual-leg profile cannot satisfy long AND short on one tick — but if a future edit relaxes to at_or_above/at_or_below, the compiler.py:98-107 warn-and-noop path triggers; the dual-leg profile is positioned to catch that regression.
- **macd_line absolute-magnitude trap.** Any non-zero macd_line/histogram threshold would behave wildly differently on BTC (~$60-100k) vs ETH (~$3k). All my MACD thresholds are 0.0 (sign-only) to stay symbol-portable; a profile authored with e.g. `macd_line above 50` would effectively be BTC-only-by-accident — worth flagging as a user footgun the DSL doesn't guard against.

**What it teaches the meta-learner:**

Feeds the freshly-reset meta-learner (AGENT_DEFAULTS EWMA weights + decay tracker) a momentum/trend archetype that is maximally distinct from the running RSI<35 mean-reversion soak (profile a05adba2):

- **Direction diversity:** both-legs, long-only, and short-only variants give the agent-modifier ensemble signed momentum signals in BOTH directions, including the rarely-exercised SELL path — so the EWMA weights learn whether TA/sentiment/debate scores correlate with momentum-sign entries differently than with mean-reversion entries.
- **Holding-horizon diversity:** 12h / 24h / 72h / 120h caps span the exit-policy time tier, letting the decay tracker observe how realized-vs-expected edge decays across short and long horizons (the RSI soak is comparatively short-hold).
- **Regime-conditioned signal:** gating to TRENDING_UP and TRENDING_DOWN (with the built-in 0.5 down-trend dampener) gives the learner regime-stratified outcome samples — momentum in up-trends at 1.0x vs down-trends at 0.5x is a natural A/B the meta-layer can exploit.
- **Honest negative signal:** since every signal family has negative OOS edge, these profiles primarily teach the learner what NOT to weight — momentum-sign chasing on fees/whipsaw — enriching the loss-side of the EWMA substrate that a pure mean-reversion soak under-samples.

**Capability gaps hit while designing this category:**

Trend/momentum ideas the current DSL CANNOT express (honest limitations found while designing):

- **No MACD crossover event.** The canonical 'MACD line crosses ABOVE signal line' is a stateful 2-bar transition. The DSL is stateless per-bar threshold-only (compiler.py:_eval_conditions is pure comparison), so I can only approximate with `macd_line above 0` AND `macd_histogram above 0` (a level snapshot), which fires for the whole duration the condition holds — not just on the cross. Same for golden/death crosses, RSI-divergence, higher-high/lower-low structure.
- **ADX/OBV/choppiness/bb.* are unauthorable.** Despite being in SUPPORTED_INDICATORS and computed every tick, they are absent from `_INDICATOR_USER_TO_CANONICAL` (schemas.py:696-710). The single most-requested trend-strength gate (ADX>25) cannot be built via the public API. Hurst is the only persistence/strength proxy that IS authorable.
- **No multi-timeframe.** Indicator periods are fixed in the calculators (RSI14, MACD12/26/9, Hurst50, etc., not configurable via rules_json). 'MACD on 1h confirmed by MACD on 4h' is inexpressible — there is one timeframe per indicator instance.
- **No trailing stop / breakeven / scale-out.** Exits are fixed SL/TP/time only (exit_policy.py:126-149). A core trend-following primitive — let-winners-run via a trailing stop — has no representation; max_holding_hours is the only 'give it room' lever.
- **No opposing-signal exit.** Only SL/TP/time close positions; a long can't be closed by the appearance of a short signal. So a 'flip on momentum reversal' trend system degrades into 'hold until stop/target/timeout' regardless of the histogram flipping against the position.
- **No perp/funding/leverage.** Short legs simulate on spot, which is directionally-correct in paper but unfillable live (EN-W3). True trend-following short exposure with funding-rate awareness is out of scope this session.

---

### Category — Mean-Reversion & Range

These profiles exercise the oscillator/band half of the indicator surface (z_score, bb.pct_b, keltner.*, choppiness, rsi) and the RANGE_BOUND regime gate — the same archetype as the live soak (profile a05adba2, RSI<35), but expressed four different ways so the meta-learner sees mean-reversion as a *family* rather than a single point. The system claims to support stateless per-bar threshold comparisons against 20 indicators (strategy_eval.py:118-148), a both-legs symmetric DSL (compiler.py:81-128), and regime gating (regime_dampener.py:78). This category is the cleanest way to test that the band/oscillator indicators actually prime and feed `eval_dict`, that the both-legs collision guard works, that RANGE_BOUND gating throttles fire rate as designed, and that absolute-price-level band indicators (keltner.upper/lower, bb.upper/lower) behave sanely across two symbols with very different price scales. Negative PnL is fully expected — every current signal family has negative OOS edge; the deliverable is COVERAGE of these code paths and diverse LEARNING SIGNAL, not edge.

#### ZRev-Symmetric-Both  — ✅ API-authorable

*Classic statistical mean reversion: buy when price is a sample-stdev outlier below its 20-bar mean (z<-2), sell when it is an outlier above (z>+2).*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "z_score",
      "comparison": "below",
      "threshold": -2.0
    }
  ],
  "match_mode_long": "all",
  "entry_short": [
    {
      "indicator": "z_score",
      "comparison": "above",
      "threshold": 2.0
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.6,
  "preferred_regimes": [
    "RANGE_BOUND"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.03,"take_profit_pct":0.012,"max_holding_hours":6,"max_allocation_pct":0.1,"max_drawdown_pct":0.2,"circuit_breaker_daily_loss_pct":0.05}`  ·  **blacklist:** `[]`  ·  **regimes:** `["RANGE_BOUND"]`

**Tests:** Both-legs symmetric DSL (compiler.py:81-112) with non-overlapping thresholds so the both_legs_matched guard can NEVER trip (z cannot be < -2 and > +2 simultaneously) — the clean control case. Exercises ZScoreCalculator priming (period 20, None on zero-stdev windows, _zscore.py:46), RANGE_BOUND gate, tight TP(1.2%)>moderate SL(3%) reversion risk window on BOTH symbols.

**Expected behavior (deviation = issue):** Fires rarely — needs both a >2-sigma move AND the resolved regime to be RANGE_BOUND (price within 2% of SMA200 and ATR<p50, regime.py:99). Both symbols eligible. Most closes via SL or 6h time-stop, occasional TP. Never logs strategy.both_legs_matched. First fire delayed ~20 bars while z_score primes.

#### BBPctB-BandTouch-Both  — ⚠ canonical-only (uses bb.pct_b, choppiness)

*Bollinger %B band-touch reversion: buy when price pierces the lower band (pct_b<0.05), sell when it pierces the upper band (pct_b>0.95).*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "bb.pct_b",
      "comparison": "at_or_below",
      "threshold": 0.05
    },
    {
      "indicator": "choppiness",
      "comparison": "above",
      "threshold": 55.0
    }
  ],
  "match_mode_long": "all",
  "entry_short": [
    {
      "indicator": "bb.pct_b",
      "comparison": "at_or_above",
      "threshold": 0.95
    },
    {
      "indicator": "choppiness",
      "comparison": "above",
      "threshold": 55.0
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.55,
  "preferred_regimes": [
    "RANGE_BOUND"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.025,"take_profit_pct":0.01,"max_holding_hours":4,"max_allocation_pct":0.08,"max_drawdown_pct":0.15,"circuit_breaker_daily_loss_pct":0.04}`  ·  **blacklist:** `[]`  ·  **regimes:** `["RANGE_BOUND"]`

**Tests:** bb.pct_b 0..1 semantics (0=lower band,1=upper band; clamps to 0.5 on zero band-range, _bollinger.py:58) plus a two-condition AND leg combining a band indicator with choppiness as a ranging filter (>55 = choppy, _choppiness.py:6). Tests at_or_below/at_or_above operators (LTE/GTE), multi-condition match_mode_long=all, and double-gating (DSL choppiness filter AND RANGE_BOUND regime gate — redundant on purpose to see if they over-throttle).

**Expected behavior (deviation = issue):** Fires rarely-to-moderately on band pierces during choppy ranges; the choppiness>55 AND-condition plus the RANGE_BOUND regime gate stack, so it should fire LESS than ZRev. Both symbols. pct_b clamp-to-0.5 on a flat window means a dead market never triggers either leg (correct, but worth confirming no spurious fire). Closes mostly SL/time; tight 1% TP catches quick snap-backs.

#### Keltner-Fade-Price-Edge  — ✅ API-authorable

*Keltner-channel fade: short when price closes above the upper Keltner band, long when it closes below the lower band — deliberately wired to an ABSOLUTE price threshold to stress the symbol-scale edge case.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "keltner.lower",
      "comparison": "above",
      "threshold": 50000.0
    }
  ],
  "match_mode_long": "all",
  "entry_short": [
    {
      "indicator": "keltner.upper",
      "comparison": "above",
      "threshold": 50000.0
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.5,
  "preferred_regimes": [
    "RANGE_BOUND"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.04,"take_profit_pct":0.015,"max_holding_hours":8,"max_allocation_pct":0.05,"max_drawdown_pct":0.25,"circuit_breaker_daily_loss_pct":0.06}`  ·  **blacklist:** `[]`  ·  **regimes:** `["RANGE_BOUND"]`

**Tests:** THE STRESS CASE. keltner.upper/lower/middle are ABSOLUTE PRICE levels (EMA +/- mult*ATR, _keltner.py:35-36), not normalized. A fixed 50000 threshold is meaningful only for BTC (~60k+) and NONSENSE for ETH (~3k). On BTC, keltner.lower>50000 is ~always true and keltner.upper>50000 is always true => BOTH legs match every tick once primed => the both_legs_matched guard (compiler.py:98-107) should fire on EVERY BTC tick, logging strategy.warning and emitting NO signal. On ETH both legs are ~always false. This profile is designed to never open a position and to flood the both_legs_matched warning log on BTC — a deliberate footgun to confirm the guard holds and to see whether a permanently-colliding profile wastes CPU silently.

**Expected behavior (deviation = issue):** Opens essentially ZERO positions. On BTC ticks it should trip strategy.both_legs_matched continuously (both price-level legs true) => no-op. On ETH ticks both legs false => no-op. Surfaces (a) that absolute-price band thresholds are a user footgun the DSL does not guard against, and (b) whether a profile that fires the collision guard every bar is logged loudly enough to be caught in a soak. blacklist=[] intentionally keeps both symbols so the divergent behavior is observable side-by-side.

#### RSI-Chop-Rev-ETHonly  — ⚠ canonical-only (uses choppiness)

*RSI mean reversion distinct from the live soak: long deep oversold (RSI<25) AND only in confirmed choppy conditions, scoped to ETH only.*

**rules_json:**

```json
{
  "direction": "long",
  "match_mode": "all",
  "signals": [
    {
      "indicator": "rsi",
      "comparison": "below",
      "threshold": 25.0
    },
    {
      "indicator": "choppiness",
      "comparison": "at_or_above",
      "threshold": 61.0
    },
    {
      "indicator": "hurst",
      "comparison": "below",
      "threshold": 0.5
    }
  ],
  "confidence": 0.65
}
```
**risk_limits:** `{"stop_loss_pct":0.05,"take_profit_pct":0.02,"max_holding_hours":12,"max_allocation_pct":0.07,"max_drawdown_pct":0.3,"circuit_breaker_daily_loss_pct":0.05}`  ·  **blacklist:** `["BTC/USDT"]`  ·  **regimes:** `[]`

**Tests:** Legacy single-direction DSL shape (direction+match_mode+signals, schemas.py:769-771) as a contrast to the both-legs profiles. Triple-AND leg combining oscillator(rsi<25), ranging filter(choppiness>=61), and a mean-reverting-regime filter(hurst<0.5 = anti-persistent/reverting, _hurst.py). REGIME-AGNOSTIC (preferred_regimes=[]) so it relies purely on DSL filters not the regime gate — tests whether DSL-level range filtering substitutes for the RANGE_BOUND gate. blacklist=["BTC/USDT"] scopes to ETH-only via the symbol-exclusion mechanism. Deeper oversold (25 vs soak's 35) makes it genuinely richer, not a duplicate.

**Expected behavior (deviation = issue):** ETH-only, long-only. Fires rarely: needs RSI<25 (deep) AND choppiness>=61 AND hurst<0.5 all at once — a narrow triple-AND. First fire delayed ~50 bars (hurst period 50 is the slowest to prime; until then the whole leg returns None per compiler.py:36-37). No short positions ever. Closes via SL(5%)/TP(2%)/12h time. Good test that a never-or-rarely-firing agnostic profile coexists with the gated ones without racing the ReentryGate (different symbol from BTC profiles, shares ETH with the both-legs profiles).

**Issues this category is built to surface:**

- **Absolute-price band threshold footgun (Keltner-Fade-Price-Edge)**: `keltner.upper/lower` and `bb.upper/lower` are dollar-denominated price levels, but the DSL accepts a single scalar `threshold` evaluated against EVERY universe symbol. A threshold sane for BTC (~60k) is nonsense for ETH (~3k). Designed to make BOTH legs true on every BTC tick → trips `strategy.both_legs_matched` (`compiler.py:98-107`) continuously and opens ZERO positions. Surfaces: (1) does the system warn loudly enough that a profile is permanently colliding, or does it waste CPU silently? (2) does the DSL/UI offer no guardrail against symbol-scale-dependent thresholds?
- **Permanently-colliding both-legs profile = silent CPU waste**: the guard returns `None` correctly, but a profile that NEVER produces a signal still runs the full 11-stage evaluation every tick. Is a never-firing (or always-colliding) profile flagged anywhere, or does it accrue cost invisibly?
- **Priming-delay asymmetry**: RSI-Chop-Rev mixes RSI(14), choppiness(14) and hurst(50). Per `compiler.py:36-37` the WHOLE leg returns None until the slowest indicator (hurst, ~50 bars) primes — so the profile is silently inert for far longer than an RSI-only profile. Does the trace/UI distinguish "priming" from "not matched"? (`evaluate_with_trace` marks both `matched=False`, `compiler.py:218-224` — potential operator confusion.)
- **ReentryGate race on shared symbol (ETH)**: ZRev, BBPctB, and RSI-Chop-Rev all trade ETH. The ReentryGate is keyed per (profile, symbol), so each should hold its own ETH position independently — does the gate truly isolate per-profile, or can two mean-reversion profiles on ETH interfere?
- **RANGE_BOUND over-throttling**: BBPctB double-gates (DSL choppiness>55 AND RANGE_BOUND regime). RANGE_BOUND already requires low ATR; choppiness-high may rarely co-occur with the regime's low-vol condition → profile may never fire. Surfaces whether stacked range filters are contradictory in practice.
- **entry_short on SPOT**: ZRev and BBPctB declare `entry_short` legs. On spot-only (no perp) — does `entry_short` open a real short paper position, get silently dropped, or convert to a reduce-only/no-op? A key capability question this category is positioned to answer.

**What it teaches the meta-learner:**

Feeds the freshly-reset meta-learner (TA+sentiment+debate EWMA weights, just reset to AGENT_DEFAULTS) four DISTINCT expressions of the same underlying thesis (price reverts to mean), which is exactly the diversity a decay tracker needs to avoid collapsing "mean-reversion" into one feature: (1) **statistical** reversion via z_score sigma-bands, (2) **volatility-band** reversion via Bollinger %B, (3) **channel** reversion via Keltner price bands, (4) **oscillator+fractal** reversion via RSI+choppiness+hurst. Because they share a thesis but differ in indicator, leg-shape (both-legs vs legacy), regime-gating (RANGE_BOUND vs agnostic), and symbol scope (both vs ETH-only), the meta-learner can attribute decay to the *expression* rather than the *idea* — e.g. learning that z-score bands and %B bands decay together (correlated) while the hurst-gated variant decays differently. The Keltner footgun contributes a near-zero-signal control (almost never trades) that tells the learner what "structurally inert" looks like vs "fires but loses". Distinct from the live soak (RSI<35 long-only) by depth (RSI<25), filters (hurst/choppiness), and direction (symmetric shorts), so it enriches rather than duplicates the existing baseline.

**Capability gaps hit while designing this category:**

Mean-reversion ideas the DSL/system CANNOT express today (honest limitations found while designing):
- **Band re-entry / crossover**: true reversion entries fire when price *crosses back inside* a band (pct_b crosses up through 0, or z-score crosses back through -2 toward 0). The DSL has only stateless per-bar threshold comparisons — NO crossover/cross-event operator (`compiler.py:40-49`). I can only test "is below band right now", which is a pierce, not a re-entry. This systematically buys falling knives.
- **Stateful / trailing exits**: reversion classically exits at the mean (z→0) or via a trailing stop. Exits are limited to fixed SL/TP/time (`libs/core/exit_policy.py`); there is NO "close when z_score returns to 0" or "close on opposing band touch" — only SL/TP/time close positions live. My TP% is a crude proxy for "reverted to mean".
- **Opposing-signal close**: a symmetric profile cannot use its short-leg condition to CLOSE a long (no opposing-signal close exists). entry_short opens a (questionable, on-spot) new position rather than flattening the long.
- **Multi-timeframe confirmation**: "oversold on 1h, ranging on 4h" is a standard reversion filter. All indicators run on one fixed timeframe with fixed periods (RSI14/BB20/ZScore20/Hurst50, NOT configurable via rules_json). No multi-timeframe.
- **Dynamic / volatility-scaled thresholds**: a robust band-fade scales the threshold by current ATR or normalizes the price-level bands (keltner/bb.upper/lower) per symbol. The DSL takes a fixed scalar threshold only — hence the Keltner footgun. No expression for "price > keltner.upper" as a relative comparison between two indicators (can't compare indicator-to-indicator, only indicator-to-constant).
- **Sequence / dwell logic**: "RSI has been <30 for 3 consecutive bars" or "first touch of the band in N bars" — no sequence/dwell/count state in the per-bar DSL.
- **Spread / pairs reversion**: BTC-ETH ratio reversion (a natural 2-symbol mean-reversion play) is impossible — a profile evaluates each symbol independently with no cross-symbol state, and there is no multi-leg/spread primitive (that is EN-W3, not designable today).

---

### Category — Breakout & Volatility-Expansion

These profiles are **system-capability instruments**, not edge bets — negative PnL is expected and acceptable. Breakout/volatility logic is the single best stressor for the current DSL because a *correct* breakout strategy fundamentally requires STATE the DSL cannot express: "the band was squeezed for N bars, THEN price crossed above the upper band on a volume spike." The DSL only offers stateless, per-bar comparisons of one indicator against one constant (`libs/core/schemas.py:632-647`). So every profile here is a deliberate degradation of an ideal breakout rule into the nearest stateless proxy, and the *gap between intent and what fires* is exactly the learning signal.

Two structural truths I verified make this category high-value as a test:

1. **`bb.pct_b` is the only price-vs-band primitive that is normalized and therefore symbol-portable.** It is computed `(close - lower) / band_range` (`libs/indicators/_bollinger.py:58`) and is *unbounded* — it exceeds 1.0 precisely when price closes above the upper Bollinger band (a real breakout), and goes negative below the lower band. This is the ONLY way to express "price broke the band" in the DSL, because there is no `close`/`price` indicator key among the 20 supported keys and conditions can never compare two indicators — only indicator-vs-constant.

2. **The absolute band keys (`keltner.upper`, `bb.upper`, `bb.lower`) are raw price levels** (Keltner = EMA ± 2·ATR, `libs/indicators/_keltner.py:35-36`). A fixed numeric threshold on them is intrinsically symbol-specific (BTC ~100k vs ETH ~3k), which I exploit to demonstrate that a numeric threshold can *silently* scope a profile to one symbol and be permanently dead on the other — a subtle footgun worth surfacing.

3. **HIGH_VOLATILITY gating is self-defeating by construction.** The rule classifier flips to HIGH_VOLATILITY whenever ATR > 75th percentile (`libs/indicators/_regime.py:92`), so the regime *is* reachable (unlike CRISIS, which also needs price <90% of SMA). But the dampener then multiplies confidence by 0.6 (`services/hot_path/src/regime_dampener.py:34`) — the lowest non-CRISIS multiplier. So a breakout profile gated to HIGH_VOLATILITY only ever fires in the one regime where its signal is most suppressed. That tension (fires-but-throttled) is a clean meta-learning probe.

#### BB-PctB-Upper-Breakout-BTC  — ⚠ canonical-only (uses bb.pct_b)

*Bets that a close above the upper Bollinger band (pct_b>1) on BTC continues upward — a classic momentum-breakout, degraded to a stateless single-bar test.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "bb.pct_b",
      "comparison": "above",
      "threshold": 1.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.6,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.04,"take_profit_pct":0.08,"max_holding_hours":12,"max_allocation_pct":0.15,"max_drawdown_pct":0.25,"circuit_breaker_daily_loss_pct":0.1}`  ·  **blacklist:** `["ETH/USDT"]`  ·  **regimes:** `[]`

**Tests:** Exercises the ONLY normalized price-vs-band primitive in the DSL (bb.pct_b unbounded, libs/indicators/_bollinger.py:58). Tests blacklist symbol-scoping to BTC-only, single-leg both-legs shape (entry_long only, no short), regime-agnostic path (empty preferred_regimes skips the C.4 gate at processor.py:465), and wider volatility-appropriate stops (4% SL / 8% TP) interacting with a moderate 15% allocation cap.

**Expected behavior (deviation = issue):** Fires occasionally on BTC only (pct_b>1 happens on real upside band-pierces, maybe a few times/day on 1m). Never opens an ETH position. Most closes will be SL or time-exit because a single-bar band-pierce has no continuation guarantee; expect net-negative or breakeven PnL. Confidence 0.6 × regime multiplier (1.0 trending-up / 0.8 range) × agent blend.

#### RVOL-Spike-Breakout-BothSymbols  — ⚠ canonical-only (uses bb.pct_b)

*Bets a relative-volume spike (current 1m volume >2.5x its 20-bar average) marks a breakout in either direction — the volume-confirmation leg of a breakout, with NO price/band confirmation possible alongside it as a single stateless condition.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rvol",
      "comparison": "at_or_above",
      "threshold": 2.5
    },
    {
      "indicator": "bb.pct_b",
      "comparison": "above",
      "threshold": 0.8
    }
  ],
  "match_mode_long": "all",
  "entry_short": [
    {
      "indicator": "rvol",
      "comparison": "at_or_above",
      "threshold": 2.5
    },
    {
      "indicator": "bb.pct_b",
      "comparison": "below",
      "threshold": 0.2
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.55,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.05,"take_profit_pct":0.06,"max_holding_hours":6,"max_allocation_pct":0.1,"max_drawdown_pct":0.2,"circuit_breaker_daily_loss_pct":0.08}`  ·  **blacklist:** `[]`  ·  **regimes:** `[]`

**Tests:** Full both-legs shape (entry_long AND entry_short) with AND-combined conditions per leg — exercises rvol (libs/indicators/_rvol.py, returns volume/SMA20, None until primed/quiet) plus the directional bb.pct_b split (>0.8 up-edge long, <0.2 down-edge short). CRITICAL ISSUE PROBE: does entry_short actually open a paper SHORT on a SPOT-only venue? Trades BOTH symbols (blacklist=[]). Short max-holding 6h, tight 5%/6% bands. Feeds the meta-learner a symmetric long/short volume-breakout archetype.

**Expected behavior (deviation = issue):** Fires rarely — requires a 2.5x volume spike AND price near a band edge simultaneously on the same bar, which is uncommon. When it fires, it fires on whichever of BTC/ETH spiked. The short leg is the key test: on spot, a short entry_short signal may be silently dropped, rejected at validation, or (the bug we want to catch) booked as a phantom short paper position. Expect very low fire rate and net-negative/flat PnL.

#### BB-Bandwidth-Expansion-HIVOL-Gated  — ⚠ canonical-only (uses adx, bb.bandwidth)

*Bets that Bollinger bandwidth expanding past 0.06 (bands wide => volatility regime under way) precedes continuation — gated to HIGH_VOLATILITY to test whether a vol-gated profile fires at all and how the severity-3 dampener throttles it.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "bb.bandwidth",
      "comparison": "above",
      "threshold": 0.06
    },
    {
      "indicator": "adx",
      "comparison": "at_or_above",
      "threshold": 25
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.7,
  "preferred_regimes": [
    "HIGH_VOLATILITY"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.06,"take_profit_pct":0.1,"max_holding_hours":24,"max_allocation_pct":0.12,"max_drawdown_pct":0.3,"circuit_breaker_daily_loss_pct":0.12}`  ·  **blacklist:** `[]`  ·  **regimes:** `["HIGH_VOLATILITY"]`

**Tests:** The HIGH_VOLATILITY regime-preference gate (processor.py:465-493 short-circuits to BLOCKED_REGIME_MISMATCH+shadow when live regime not in the allowlist) combined with the dampener's 0.6 multiplier for HIGH_VOLATILITY (regime_dampener.py:34). bb.bandwidth = (upper-lower)/mean is a price-fraction (~0.01-0.10 crypto 1m); 0.06 is a genuine expansion. ADX>=25 adds a trend-strength filter. Wide 6% SL / 10% TP for volatility. Probes: how often is HIGH_VOLATILITY actually resolved live, and is the shadow-block path the dominant outcome?

**Expected behavior (deviation = issue):** Most ticks BLOCKED_REGIME_MISMATCH (shadow=true) because live regime is usually trending/range, not HIGH_VOLATILITY. Fires only when ATR>75th-pctl AND bandwidth>0.06 AND ADX>=25 align — rare. When it does fire, confidence is cut to 0.7×0.6=0.42 before the agent blend, so it may also get filtered at the risk gate. Both symbols eligible. Expect a high block-rate, a thin trickle of low-confidence entries, net-negative/flat PnL. Good probe for whether vol-gated profiles are effectively dormant.

#### Keltner-Absolute-Level-DeadLeg  — ⚠ canonical-only (uses bb.bandwidth)

*Intentionally mis-scaled: bets price tagging an absolute Keltner-upper level above 200000 is a breakout — a number only BTC could ever approach, demonstrating that an absolute band threshold silently scopes (and here, effectively kills) the profile.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "keltner.upper",
      "comparison": "above",
      "threshold": 200000
    }
  ],
  "match_mode_long": "all",
  "entry_short": [
    {
      "indicator": "bb.bandwidth",
      "comparison": "at_or_below",
      "threshold": 0.015
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.5,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.03,"take_profit_pct":0.05,"max_holding_hours":8,"max_allocation_pct":0.05,"max_drawdown_pct":0.15,"circuit_breaker_daily_loss_pct":0.05}`  ·  **blacklist:** `[]`  ·  **regimes:** `[]`

**Tests:** EDGE/LIMIT STRESSOR. (1) keltner.upper is an absolute price level (EMA+2*ATR, _keltner.py:35), so threshold 200000 makes the LONG leg essentially never-fire on either symbol at current prices (BTC ~100k, ETH ~3k) — a deliberately near-dead leg to test whether a never-firing profile wastes CPU / logs cleanly / still primes indicators harmlessly. (2) The SHORT leg is the OPPOSITE breakout intent: bb.bandwidth<=0.015 is a SQUEEZE (bands tight), shorting into low volatility — semantically incoherent vs the long leg, intentionally, to feed the meta-learner a contradictory archetype and verify both legs are evaluated independently. (3) Tightest limits in the set (3% SL, 5% alloc) test the small-allocation/min-notional floor.

**Expected behavior (deviation = issue):** LONG leg never fires (keltner.upper < 200000 always at current prices). SHORT leg fires when bands are very tight (squeeze) on either symbol — which is the wrong time to short a breakout, so expect frequent small losses or time-exits. Net effect: a half-dead, semantically-inverted profile. The interesting observation is whether the dead long leg is logged as perpetual no-signal without churn, and whether the tiny 5% allocation produces orders that survive the min-notional/risk gate at all.

**Issues this category is built to surface:**

- **Spot short reality (profile 2, 4)**: does `entry_short` open a genuine short paper position on a SPOT-only venue, get rejected at validation/execution, or get booked as a phantom short? This is the highest-value bug probe — spot cannot be shorted, so the system's handling of a short signal is undefined by the capability surface and must be observed.
- **Never-firing leg wasting CPU (profile 4)**: `keltner.upper above 200000` can never be true at current prices — does the loader/processor evaluate it every tick cheaply, or is there pointless work? Does it log a clean perpetual no-signal or spam?
- **Absolute-threshold silent symbol-scoping (profile 4)**: a numeric threshold on a price-scale indicator silently makes a leg BTC-reachable-only / dead — confirms whether anything warns the operator that a leg is structurally dead.
- **HIGH_VOLATILITY dormancy (profile 3)**: is a HIGH_VOLATILITY-gated profile effectively never-trading because (a) the regime is rarely the *resolved* one and (b) the dampener cuts its confidence to 0.42, pushing it under the risk-gate confidence floor? Quantifies the fires-but-throttled tension.
- **ReentryGate race (profiles 2,3,4 all trade both symbols)**: with multiple both-symbols profiles plus the live soak (a05adba2, RSI<35) all running, does one-open-position-per-(profile,symbol) hold, and do two profiles signalling the same symbol on the same tick interleave cleanly at validation/execution?
- **Min-notional floor vs tiny allocation (profile 4, 5% alloc)**: does a 5% allocation produce an order below the exchange min-notional that the risk gate silently drops, and is that drop observable?
- **pct_b>1.0 frequency (profile 1)**: confirms the unbounded pct_b actually exceeds 1.0 often enough to fire — validates the only band-pierce proxy in the DSL is usable.

**What it teaches the meta-learner:**

Feeds the freshly-reset meta-learner (agent EWMA weights at AGENT_DEFAULTS, decay tracker empty) four maximally-distinct breakout archetypes so the substrate does not over-fit to the dominant RSI mean-reversion family already live (soak a05adba2): (1) a pure normalized band-pierce momentum signal (pct_b>1), (2) a symmetric volume-confirmed long/short breakout, (3) a regime-conditional volatility-expansion signal that mostly produces SHADOW decisions (teaching the learner the would-be-vs-live delta under HIGH_VOLATILITY), and (4) a deliberately contradictory/half-dead profile that emits a squeeze-short against a dead breakout-long — a noise/adversarial archetype that tests whether the decay tracker correctly de-weights an incoherent signal rather than chasing its random PnL. The spread of confidences (0.5–0.7) and regime gates gives the dampener and agent-blend a varied input distribution, and the shadow-heavy profile 3 specifically enriches the would-be performance comparison channel that a reset learner has no history for. Negative/flat PnL across all four is the expected, acceptable outcome — the signal is diversity of decision-traces, not edge.

**Capability gaps hit while designing this category:**

Ideas a *correct* breakout/vol-expansion strategy needs but the DSL **cannot express today**:

- **Squeeze-then-expand STATE** — the defining breakout pattern is "bandwidth was below X for N consecutive bars, THEN expanded above Y." The DSL is stateless per-bar (`schemas.py:632-647`); there is no memory, no consecutive-bar count, no "was-then-is" sequencing. Profile 3 can only test the *expanded* half, blind to whether a squeeze preceded it.
- **Crossover / cross-event operators** — "price CROSSES above keltner.upper" (the breakout trigger) is impossible. We only have level comparisons, so we catch price *already above* the band, not the cross itself — entries are systematically late and noisy. There is no cross operator anywhere in `SUPPORTED_OPERATORS` (`schemas.py:629`).
- **Indicator-vs-indicator comparison** — true breakout is `close > keltner.upper` or `bb.upper > keltner.upper` (Bollinger expanding outside Keltner = the TTM-squeeze fire). The DSL only allows indicator-vs-CONSTANT; there is no `close`/`price` key among the 20, and no way to reference one indicator as another's threshold. `bb.pct_b > 1` is the single lucky exception because the price-vs-band comparison is *pre-baked inside* the indicator.
- **Multi-timeframe confirmation** — breakouts are typically confirmed on a higher timeframe (e.g. 1m pierce confirmed by 15m trend). All 20 indicators are single fixed-period on one stream; periods are not even configurable via rules_json.
- **Volume-and-price-on-the-SAME-bar as a true conjunction with timing** — profile 2 ANDs rvol and pct_b, but both are evaluated on the same bar with no lead/lag; a real breakout wants the volume spike to *coincide-or-precede* the price break, which stateless AND cannot encode.
- **Trailing/ATR-chandelier stops** — volatility breakouts demand a trailing stop that widens with ATR; only fixed-percent SL/TP/time exits exist (`libs/core/exit_policy.py`), so a runaway breakout is capped at a static TP and a pullback hits a static SL.
- **Opposing-signal exit** — no way to close a long when the breakout fails (pct_b falls back below 1); only SL/TP/time close positions, so failed breakouts bleed to the stop instead of exiting on signal reversal.
- **No native short on spot** — directional symmetry (profile 2's short leg) is only *nominally* expressible; the spot universe likely cannot actually hold a short, making entry_short a test artifact rather than a real capability.

---

### Category — Multi-Factor / Confluence (rule-engine combinatorics)

This category stresses the **rule engine** (`services/strategy/src/compiler.py`) and the **agent-ensemble blend** (`services/hot_path/src/processor.py`) rather than any single indicator's edge. Four code paths are exercised deliberately:

1. **AND confluence at the condition-count extreme** — a 5-condition `all` leg. The engine's `_eval_conditions` (compiler.py:34-52) short-circuits the WHOLE leg to `None` if *any* referenced indicator is still priming (compiler.py:36-37), so a 5-factor AND that pulls in slow indicators (`hurst` primes 51 bars, `z_score` 20 bars) won't even *evaluate* for the first ~51 bars after boot, then fires only on a rare 5-way alignment. This tests both the AND path and a near-never-firing profile (does the pipeline waste CPU re-evaluating a profile that essentially never matches?).

2. **OR firehose** — a `match_mode any` leg with several wide thresholds, designed to match almost every bar (`_combine` returns `any(results)`, compiler.py:60-61). This churns the **ReentryGate** (one open position per profile+symbol) and the validation/exit pipeline hard. The point is volume of signals, not direction quality.

3. **Multi-symbol vs scoped + correlation-cluster cap** — one profile runs both BTC and ETH (`blacklist=[]`), one is BTC-only (`blacklist=["ETH/USDT"]`). Because `CORRELATION_CLUSTERS` maps **both** BTC/USDT and ETH/USDT to the single `MAJORS` cluster (settings.py:59-61) and the combined cap is `CORRELATION_CLUSTER_CAP_PCT = 0.40` (settings.py:55), a both-symbols profile that opens BTC + ETH simultaneously should trip `check_order_against_budget`'s cluster branch (portfolio.py:105-113) — the only way to reach that branch in this 2-symbol spot universe is to hold both at once.

4. **Both-legs collision no-op** — a profile whose `entry_long` and `entry_short` can both be true on the same bar, deliberately triggering the `strategy.both_legs_matched` warning + `return None` (compiler.py:98-107). This is a profile-bug detector wired into a test instrument.

Negative PnL is expected and irrelevant here — the deliverable is breadth of code-path coverage and a diverse learning signal for the freshly-reset EWMA meta-learner.

#### Confluence-5AND-NearNever (BTC-only)  — ✅ API-authorable

*Bets nominally on a rare full-stack bullish alignment (momentum + trend-persistence + mean reversion all agreeing); really an instrument for the 5-condition AND path and a profile that almost never fires.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "above",
      "threshold": 55.0
    },
    {
      "indicator": "macd_histogram",
      "comparison": "above",
      "threshold": 0.0
    },
    {
      "indicator": "hurst",
      "comparison": "above",
      "threshold": 0.58
    },
    {
      "indicator": "rvol",
      "comparison": "above",
      "threshold": 1.5
    },
    {
      "indicator": "z_score",
      "comparison": "at_or_above",
      "threshold": 1.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.7,
  "preferred_regimes": [
    "TRENDING_UP"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.03,"take_profit_pct":0.06,"max_holding_hours":48,"max_allocation_pct":0.25,"max_drawdown_pct":0.15,"circuit_breaker_daily_loss_pct":0.05}`  ·  **blacklist:** `["ETH/USDT"]`  ·  **regimes:** `["TRENDING_UP"]`

**Tests:** 5-condition AND across 5 indicator families (momentum/MACD/persistence/volume/dispersion); the priming short-circuit (compiler.py:36-37 — won't evaluate until hurst's 51-bar window primes); regime-preference gate (TRENDING_UP only); BTC-only scoping via blacklist; whether a near-never-firing profile is cheaply skipped or wastefully re-evaluated each tick.

**Expected behavior (deviation = issue):** Fires very rarely (maybe never in a multi-day soak). Stays in BLOCKED_REGIME_MISMATCH/shadow whenever regime != TRENDING_UP, and emits no signal at all for the first ~51 bars after boot while hurst primes. When it does fire, BTC only. Most closes (if any) will be time-exit or SL given the long holding window.

#### OR-Firehose-DualSymbol  — ✅ API-authorable

*Nominally 'enter long on any sign of momentum or volatility'; really a high-frequency OR firehose to churn the ReentryGate and validation pipeline on both symbols.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "above",
      "threshold": 40.0
    },
    {
      "indicator": "rvol",
      "comparison": "above",
      "threshold": 0.8
    },
    {
      "indicator": "macd_histogram",
      "comparison": "above",
      "threshold": -5.0
    },
    {
      "indicator": "z_score",
      "comparison": "above",
      "threshold": -2.0
    }
  ],
  "match_mode_long": "any",
  "confidence": 0.4,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.02,"take_profit_pct":0.02,"max_holding_hours":2,"max_allocation_pct":0.2,"max_drawdown_pct":0.2,"circuit_breaker_daily_loss_pct":0.08}`  ·  **blacklist:** `[]`  ·  **regimes:** `[]`

**Tests:** OR path (_combine any, compiler.py:60-61) with deliberately wide thresholds so nearly every primed bar matches; regime-agnostic (empty preferred_regimes) so it runs in every non-CRISIS regime; both symbols (blacklist=[]) → two independent ReentryGates; tight 2% SL/TP + 2h max-hold → high close churn → many closed-outcome samples feeding the EWMA recompute. Also stresses circuit-breaker daily-loss accounting under high trade count.

**Expected behavior (deviation = issue):** Fires on most bars for BOTH BTC and ETH once primed (rsi14 primes fast). ReentryGate keeps it to one open BTC + one open ETH at a time. Expect rapid open→close cycling (SL or TP or 2h time), high closed-trade volume, likely negative PnL from churn/fees — that volume is the point. Note: per compiler.py:36-37 even an OR leg returns None if ANY of its 4 indicators is still priming, so no signals for the first ~20 bars while z_score primes.

#### ClusterCap-DualMajors-Probe  — ✅ API-authorable

*Nominally a broad trend-follower on both majors; really a probe to force simultaneous BTC+ETH exposure and trip the MAJORS correlation-cluster cap.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "above",
      "threshold": 45.0
    },
    {
      "indicator": "macd_line",
      "comparison": "above",
      "threshold": 0.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.55,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.05,"take_profit_pct":0.1,"max_holding_hours":72,"max_allocation_pct":0.5,"max_drawdown_pct":0.25,"circuit_breaker_daily_loss_pct":0.1}`  ·  **blacklist:** `[]`  ·  **regimes:** `[]`

**Tests:** Multi-symbol concurrency + correlation-cluster cap (portfolio.py:105-113). Both BTC/USDT and ETH/USDT resolve to cluster MAJORS (settings.py:59-61); combined cap is 40% of gross budget (settings.py:55). High max_allocation_pct (0.5) and long 72h holds maximize the chance both legs are open at once so combined MAJORS notional exceeds the 0.40 cluster cap and the second order is blocked with 'correlation cluster MAJORS ... would exceed cap'. Moderate 2-condition AND keeps it firing enough to actually co-hold.

**Expected behavior (deviation = issue):** Fires fairly often on both symbols in TRENDING_UP/RANGE conditions. The first major to open consumes cluster room; when the second tries to open while the first is still held (likely given 72h max-hold), expect the cluster-cap block to fire. This is the ONLY profile in the set realistically able to hold both majors long enough to engage the cap. Closes mostly TP (10%) or time.

#### BothLegs-Collision-NoOp  — ✅ API-authorable

*Nominally a mean-reversion straddle (long when oversold, short when overbought); really engineered so both legs can be true on one bar, tripping the both-legs no-op guard.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "below",
      "threshold": 60.0
    },
    {
      "indicator": "z_score",
      "comparison": "below",
      "threshold": 1.5
    }
  ],
  "match_mode_long": "all",
  "entry_short": [
    {
      "indicator": "rsi",
      "comparison": "above",
      "threshold": 40.0
    },
    {
      "indicator": "z_score",
      "comparison": "above",
      "threshold": -1.5
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.5,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.04,"take_profit_pct":0.04,"max_holding_hours":12,"max_allocation_pct":0.2,"max_drawdown_pct":0.2,"circuit_breaker_daily_loss_pct":0.06}`  ·  **blacklist:** `["ETH/USDT"]`  ·  **regimes:** `[]`

**Tests:** Both-legs evaluation path (compiler.py:81-112) and specifically the both-matched collision: for any bar with 40<rsi<60 AND -1.5<z_score<1.5 (the common mid-range case), BOTH entry_long and entry_short match, hitting the `strategy.both_legs_matched` warning + `return None` (compiler.py:98-107). Also tests entry_short on a SPOT-only venue — does a SELL signal try to open a real short paper position, or is it dropped downstream? BTC-only to keep the signal stream legible in logs.

**Expected behavior (deviation = issue):** On most mid-range bars: both legs match → no-op + `strategy.both_legs_matched` log warning, NO trade. Trades only fire at the edges (rsi<=40 & z<=-1.5 → only short matches → SELL; rsi>=60 & z>=1.5 → only long matches → BUY). Watch whether the SELL path opens a genuine short paper position on spot (likely a surfaced issue) or is silently dropped. Expect this profile to spend most of its life in the collision no-op state — useful for confirming the guard fires and doesn't leak a signal.

**Issues this category is built to surface:**

- **CRITICAL — user-facing DSL cannot reach 8 of the 20 indicators.** The creation endpoint validates `rules_json` through `StrategySignal.indicator: _UserIndicatorName` (libs/core/schemas.py:678-691, 740-743), a 12-name Literal that EXCLUDES `adx`, `bb.pct_b`, `bb.bandwidth`, `bb.upper`, `bb.lower`, `obv`, `choppiness`. Those 8 live in `SUPPORTED_INDICATORS` (schemas.py:608-628) and ARE evaluated by the hot path, but `POST /profiles` will 422 on them because `_signals_to_canonical_conditions` does `_INDICATOR_USER_TO_CANONICAL[s.indicator]` (schemas.py:812). **I deliberately authored all four profiles using only the 12 reachable keys so they actually create** — but a confluence design that wants ADX/OBV/Bollinger/Choppiness confluence is silently impossible via the user flow. This is a real contract bug between the documented '20 keys' surface and the creation validator.
- **Both-legs collision** (BothLegs-Collision-NoOp): does the `strategy.both_legs_matched` guard (compiler.py:98-107) truly emit zero signal, or does any downstream stage (trace summary path, compiler.py:228-236) leak a BUY? The trace path sets `matched=False` but still computes a `primary='BUY'` — confirm no signal escapes.
- **Short on spot** (BothLegs-Collision + any matched short leg): the universe is SPOT-only. Does an `entry_short` SELL signal open a genuine short paper position, get inverted, or get dropped at validation/execution? This is the headline edge-case for the short leg.
- **Cluster cap reachability** (ClusterCap-DualMajors): in a 2-symbol all-MAJORS universe, the cluster branch is reachable ONLY when both BTC and ETH are open simultaneously. Confirm the cap actually engages (not dead code) and that the per-symbol `max_allocation_pct` check (check_6_risk_level.py:50-58) and the portfolio cluster cap don't double-count or conflict.
- **Near-never-firing waste** (Confluence-5AND): does the pipeline re-run the full 5-condition + priming check every tick for a profile that essentially never matches, or is there an early-out? CPU-waste signal.
- **OR + priming interaction** (Firehose): per compiler.py:36-37 even an OR leg yields None if a single referenced indicator is priming — so the 'high-frequency' profile is mute for ~20 bars after boot/restart. Confirm it isn't mis-reported as 'never firing' during the priming window.
- **Two profiles, same symbol, racing the ReentryGate**: Confluence-5AND, ClusterCap, and BothLegs all trade BTC. If two fire on BTC in the same window, confirm the per-(profile,symbol) gate keeps them independent and they don't race a shared key.

**What it teaches the meta-learner:**

The freshly-reset EWMA blend (AGENT_DEFAULTS, libs/core/agent_registry.py:22; EWMA_ALPHA=0.1, MIN_SAMPLES=10) needs a spread of closed-outcome samples per symbol to move off defaults. This set feeds it deliberately diverse signal *cadence and shape*:
- **Firehose** is the volume engine — high trade count → fastest path past MIN_SAMPLES=10 → first real EWMA weight movement on BOTH symbols. Without a high-frequency profile the reset weights would stay pinned at defaults for a long time.
- **Confluence-5AND** contributes rare, high-conviction (confidence 0.7), TRENDING_UP-only samples — a low-frequency / high-selectivity counterweight so the learner sees that not all signal sources fire at the same rate.
- **ClusterCap** contributes mid-frequency dual-symbol samples and, importantly, *blocked* outcomes (cluster-cap rejections) — signal about how often a strategy's intent is denied by portfolio risk vs filled.
- **BothLegs** contributes mostly no-ops plus sparse edge-trades, teaching the decay tracker what a near-silent profile's live baseline looks like (latest-wins decay baselines; exploratory profile_id="" caveat noted).
Together these span the full firing-frequency axis (near-never → firehose) and the long/short/blocked-outcome axis, which is exactly the diversity a reset meta-learner is starved for.

**Capability gaps hit while designing this category:**

Honest limits of the current DSL that this category bumps into:
- **No crossover/cross-event operator.** True confluence often means 'MACD line crosses above signal line' — the DSL can only ask `macd.macd_line > 0` and `macd.signal_line < X` as separate stateless threshold checks. I can approximate 'histogram > 0' (which IS macd_line>signal_line) but cannot express the *crossing event* (the bar it flips). All conditions are stateless per-bar (compiler.py:34-52).
- **No multi-timeframe confluence.** Periods are fixed in the calculators (RSI14, MACD12/26/9, BB20, Hurst50, etc.) and not settable via rules_json. 'Daily trend + hourly entry' confluence is impossible.
- **No stateful / trailing / sequence logic.** Can't express 'RSI was <30 within the last 5 bars and is now >40', trailing stops, or N-bars-in-a-row. Exits are only SL/TP/time (libs/core/exit_policy.py) — no opposing-signal or indicator-based exit.
- **8 of 20 indicators unreachable via the creation DSL** (see issues): `adx`, `bb.*`, `obv`, `choppiness` can't enter a `POST /profiles` rules_json, so a genuinely indicator-broad confluence profile (e.g. ADX>25 + choppiness<38 + OBV-trend) is not designable today through the supported user surface — only via a direct canonical write, which is out of scope.
- **No weighted confluence.** match_mode is binary all/any — can't say '3 of 5 must agree' or weight conditions. A 5-AND is all-or-nothing; there's no M-of-N.
- **No per-condition direction mixing within a leg.** A single leg is one direction; cross-factor 'long-bias score' blending only happens later in the opaque agent modifier, not in the rule DSL.
- **Spot-only.** No perp/funding/multi-leg — the `entry_short` leg's real-world meaning on spot is itself an open question (flagged as an issue), not a designable short instrument.

---

### Category — Risk-Limit & Position-Lifecycle Stress

These profiles deliberately hold the entry signal trivial (a single `rsi` or `z_score` threshold that fires often) and weaponize the **risk_limits** payload so the exercised surface is the exit/lifecycle machinery, not the signal. The targets are the four lifecycle code paths verified this session:

- **`libs/core/exit_policy.decide_exit` (exit_policy.py:143-149)** — the SINGLE source of truth for SL>TP>time precedence, consumed live by `ExitMonitor.check` (exit_monitor.py:113-119). Note the live ordering subtlety: SL/TP are evaluated first with `age_hours=-inf` (time disabled), and time is only evaluated on a *second* `decide_exit` call after `opened_at` math — so a position that is simultaneously past its time limit AND past its TP will close as `take_profit`, never `time_exit`. A churn profile is the only way to observe that precedence empirically.
- **`CircuitBreaker.check` (circuit_breaker.py:11-31)** — engage when `-daily_realised_pnl_pct > circuit_breaker_daily_loss_pct`, reset at UTC-midnight rollover (dual reset: in-process `_last_reset_date` class dict AND the Redis `pnl:daily:<pid>` hash date tag in closer.py:231-241). A low cap + loose entry is the only way to trip and then observe next-day recovery.
- **`RiskGate.check` (risk_gate.py:38-82)** — the capital-sizing gate: `trade_dollars = free_capital × max_allocation_pct × confidence`, with a hard `$10` dust floor (risk_gate.py:12, 76-79) and a `drawdown_limit_exceeded` / `exposure_at_notional` block. Varying `max_allocation_pct` from tiny to large drives this gate into its `trade_below_minimum`, `exposure_at_notional`, and normal-sizing branches.
- **`closed_trades` ledger write (closer.py:271-339)** — `close_reason` population and `realized_pnl_pct = net_pre_tax / cost_basis` (closer.py:291-293) into a `DECIMAL(10,6)` column (015_closed_trades.sql:31). High turnover stress-tests close-reason attribution, the append-only write, and the 6-decimal precision floor.

Negative PnL is fully expected and acceptable — the deliverable is COVERAGE of these exit branches and clean LEARNING SIGNAL (close_reason distributions) for the freshly-reset meta-learner, not edge.

#### Churn-TightSLTP-BTC  — ✅ API-authorable

*Mean-reversion dip-buy that exists only to flip positions in and out as fast as the exit machinery allows — tests SL/TP precedence and close-reason attribution under maximum turnover.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "below",
      "threshold": 55.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.9,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.005,"take_profit_pct":0.005,"max_holding_hours":24,"max_allocation_pct":0.25,"max_drawdown_pct":0.5,"circuit_breaker_daily_loss_pct":0.5}`  ·  **blacklist:** `["ETH/USDT"]`  ·  **regimes:** `[]`

**Tests:** exit_policy.decide_exit SL/TP branches (exit_policy.py:143-146); ExitMonitor two-pass evaluation (exit_monitor.py:113-119); closer._write_closed_trade_row close_reason population + realized_pnl_pct DECIMAL(10,6) precision (closer.py:291-329, 015:31); ReentryGate one-open-per-(profile,symbol) cycling rapidly; agent EWMA outcome tagging on every close (closer.py:154-164). BTC-only via blacklist scoping.

**Expected behavior (deviation = issue):** Fires very often on BTC (RSI<55 is loose). Each open closes within seconds-to-minutes at ±0.5%, almost always close_reason in {stop_loss, take_profit}, rarely time_exit. High closed_trades row count. Many tiny realized_pnl_pct values near the 6th-decimal floor. Net PnL likely negative after fees on 0.5%/0.5% — expected. Watch: does TP fire before time even on aged positions (precedence), and does pnl_pct round/truncate at 6 decimals on sub-0.001 returns.

#### TimeExit-30min-ETH  — ✅ API-authorable

*Wide SL/TP so price almost never trips them — forces nearly every close down the time-exit path to exercise the age-based branch heavily.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "z_score",
      "comparison": "below",
      "threshold": -1.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.8,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.9,"take_profit_pct":0.9,"max_holding_hours":0.5,"max_allocation_pct":0.2,"max_drawdown_pct":0.9,"circuit_breaker_daily_loss_pct":0.9}`  ·  **blacklist:** `["BTC/USDT"]`  ·  **regimes:** `[]`

**Tests:** exit_policy.decide_exit time branch as the dominant exit (exit_policy.py:147-148); the second-pass opened_at age computation in ExitMonitor (exit_monitor.py:115-119) using total_seconds()/3600.0 against a fractional 0.5h limit; close_reason='time_exit' attribution into closed_trades; z_score entry (mean-reversion dip below -1 sigma) on ETH-only.

**Expected behavior (deviation = issue):** Fires when ETH 20-bar z_score dips below -1.0 (moderately often). SL 90% / TP 90% are effectively unreachable on spot, so virtually all closes are close_reason='time_exit' at ~30min age. Validates the fractional-hour time path. Net PnL roughly random-walk minus fees — expected near-zero-to-negative. Issue to watch: tick cadence vs 0.5h — if ticks are sparse the actual close age overshoots 30min noticeably.

#### CircuitBreaker-Tripwire-Both  — ✅ API-authorable

*Loose two-leg entries on both symbols plus a deliberately low daily-loss cap, engineered to TRIP the daily circuit breaker fast and then verify it disengages on the next UTC day.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "below",
      "threshold": 60.0
    }
  ],
  "match_mode_long": "all",
  "entry_short": [
    {
      "indicator": "rsi",
      "comparison": "above",
      "threshold": 40.0
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.95,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.02,"take_profit_pct":0.01,"max_holding_hours":2,"max_allocation_pct":0.4,"max_drawdown_pct":0.8,"circuit_breaker_daily_loss_pct":0.02}`  ·  **blacklist:** `[]`  ·  **regimes:** `[]`

**Tests:** CircuitBreaker.check engage at -daily_realised_pnl_pct > 0.02 and UTC-midnight reset via both _last_reset_date dict and Redis pnl:daily hash date tag (circuit_breaker.py:11-31, closer.py:231-241); the int()-truncated micro-fraction counter (closer.py:240, equity-fraction × 1e6) under many small losses; both-legs shape (entry_long AND entry_short on the SAME symbol — RSI<60 and RSI>40 overlap so BOTH legs can fire); blacklist=[] => trades both symbols; risk gate sizing at max_allocation_pct 0.4.

**Expected behavior (deviation = issue):** Fires constantly on both BTC and ETH (overlapping RSI bands). Asymmetric SL2%/TP1% biases realized losses, so the daily counter should cross -2% within a handful of losing closes and the circuit breaker engages (blocking new orders) the same day. Next UTC day it should reset and resume. Issues to surface: (1) does the in-process dict reset and the Redis date-tag reset agree after a service restart? (2) does the int() micro-truncation under-count tiny losses so the breaker trips later than expected? (3) entry_long+entry_short overlap on one symbol — which leg wins and does it open the documented direction?

#### DustFloor-NeverTrades-BTC  — ✅ API-authorable

*Edge/limit stressor: an allocation so tiny the risk gate's $10 dust floor blocks every order — a profile that looks active but deterministically never opens a position.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "below",
      "threshold": 70.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.05,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.01,"take_profit_pct":0.01,"max_holding_hours":1,"max_allocation_pct":0.001,"max_drawdown_pct":0.99,"circuit_breaker_daily_loss_pct":0.99}`  ·  **blacklist:** `["ETH/USDT"]`  ·  **regimes:** `[]`

**Tests:** RiskGate trade_below_minimum branch (risk_gate.py:12, 76-79): trade_dollars = free_capital × 0.001 × 0.05 is far below the $10 _MIN_TRADE_DOLLARS floor for any realistic notional, so every signal is blocked at the sizing stage. Exercises the gate's reject-with-reason path and the abstention/blocked telemetry without ever reaching execution. Confirms a permanently-blocked profile still evaluates cleanly (no crash, no zombie position).

**Expected behavior (deviation = issue):** Signal fires almost every bar on BTC (RSI<70), passes regime/abstention, then is blocked at the risk gate with reason='trade_below_minimum' every single time. ZERO positions opened, ZERO closed_trades rows. Net PnL exactly 0. Issue to surface: does a never-firing-into-execution profile waste CPU on every tick (cost of evaluating a structurally dead profile)? Does the blocked-reason telemetry distinguish trade_below_minimum from a genuine no-signal abstention, so the meta-learner doesn't mislabel it?

**Issues this category is built to surface:**

- **close_reason attribution under precedence:** Churn-TightSLTP can have a position simultaneously past `max_holding_hours` and past TP; the live two-pass (`exit_monitor.py:113-119`) evaluates SL/TP first with time disabled, so it will tag `take_profit`, never `time_exit`. Confirm the ledger reflects the documented precedence and never mislabels.
- **realized_pnl_pct precision floor / overflow row:** `realized_pnl_pct = net_pre_tax / cost_basis` (`closer.py:291-293`) into `DECIMAL(10,6)` (`015:31`). Spot fractions fit, but ultra-tight 0.5%/0.5% churn produces sub-0.001 returns that truncate at the 6th decimal — verify rows aren't silently rounding signal away, and confirm no `numeric field overflow` on any close (the previously-logged risk).
- **int() micro-counter under-count:** `incr_micro = int(equity_fraction × 1e6)` (`closer.py:240`) truncates toward zero. With tiny allocations many losses contribute exactly 0 to the daily counter — the circuit breaker could trip LATER than the real cumulative loss. CircuitBreaker-Tripwire is sized (alloc 0.4) to make losses big enough to register, but watch whether the trip timing matches the arithmetic.
- **Circuit breaker dual-reset divergence:** in-process `_last_reset_date` (`circuit_breaker.py:9`) vs Redis `pnl:daily` date tag (`closer.py:232-239`). A hot_path restart loses the in-process dict but Redis persists — does the breaker state survive a restart consistently, or can it desync across the UTC rollover?
- **entry_long + entry_short overlap on one symbol:** CircuitBreaker-Tripwire's RSI<60 (long) and RSI>40 (short) overlap (40<RSI<60 satisfies both). Which leg wins, does the loser get suppressed cleanly, and does entry_short open a real paper SHORT on a SPOT-only venue (or is it silently dropped)? This is a genuine SPOT-vs-short capability question.
- **Never-firing profile cost:** DustFloor evaluates every bar and is always blocked at `trade_below_minimum` — does it waste CPU, and does blocked-telemetry distinguish a sizing block from a no-signal abstention so the meta-learner doesn't mislabel it as a losing strategy?
- **Two profiles racing the ReentryGate:** Churn (BTC) and CircuitBreaker-Tripwire (both) both target BTC — confirm the per-(profile,symbol) gate keeps them independent and they don't cross-contaminate each other's open-position accounting.

**What it teaches the meta-learner:**

The meta-learner was reset to AGENT_DEFAULTS this session, so it needs diverse, cleanly-attributed close outcomes to rebuild EWMA weights. This category feeds it the most heterogeneous close-reason distribution of any archetype:

- **Churn-TightSLTP** generates a high-volume stream of {stop_loss, take_profit} outcomes — fast, balanced win/loss tagging via `record_position_close` (`closer.py:154-164`) that lets the EWMA move quickly and reveals whether rapid alternating outcomes destabilize the freshly-seeded weights.
- **TimeExit-30min** contributes a near-pure `time_exit` outcome stream — a control signal where the close reason is decoupled from PnL direction, testing whether the tracker correctly attributes win/loss independent of exit cause.
- **CircuitBreaker-Tripwire** produces a regime where trading HALTS mid-day — the learner sees a profile go quiet then resume, exercising decay/staleness handling in the EWMA when a contributor stops emitting outcomes for hours.
- **DustFloor** is the negative control: it produces ZERO outcomes, so it should contribute NOTHING to any agent's weight. If the meta-learner's decay tracker ever penalizes or rewards it, that's a labeling bug surfaced for free.

Together they span the full close-reason vocabulary (stop_loss / take_profit / time_exit) plus the no-outcome and halted-then-resumed edge states — exactly the diversity a freshly-reset learning substrate needs to avoid overfitting to a single archetype.

**Capability gaps hit while designing this category:**

Honest limits of the DSL/system for this category, found while designing:

- **No trailing stop / break-even stop / stateful exit.** `risk_limits` exposes only fixed SL/TP/time (`exit_policy.py:61-67`). A trailing stop that ratchets with price, or a move-to-break-even-after-X% rule, cannot be expressed — exits are stateless threshold checks on the current snapshot only.
- **No opposing-signal close.** Per the verified surface and `decide_exit` (only SL/TP/time return a reason), a long position cannot be closed by a fresh short signal. A true reversal strategy is inexpressible; the only way to exit is a risk limit firing. This caps how the lifecycle can be driven.
- **No partial close / scale-out.** Positions are all-or-nothing; you cannot take 50% off at TP1 and trail the rest. The ledger and closer assume a single full close.
- **No per-position or per-trade dynamic sizing beyond the linear `max_allocation_pct × confidence`.** `confidence` is a static rules_json scalar (`schemas.py:780`), not a function of signal strength or volatility — so I cannot express ATR-scaled position sizing, only a flat fraction.
- **circuit_breaker_daily_loss_pct is the only daily kill;** there is no intraday max-consecutive-losses, no max-trades-per-day, and no cool-down-after-N-stops throttle. The churn profile cannot be capped by trade count, only by the daily-loss percentage.
- **Time exits are wall-clock-tick-driven, not bar-driven.** `max_holding_hours` is compared against `total_seconds()/3600.0` on tick cadence (`exit_monitor.py:116-118`); I cannot express \"exit after N bars,\" and sparse ticks mean the realized close age can overshoot the configured limit — a fidelity gap, not a config option.
- **SHORT legs on a SPOT-only universe are semantically ambiguous in the DSL** — `entry_short` validates and compiles, but whether it opens a real paper short or is silently dropped on spot is exactly the issue CircuitBreaker-Tripwire is built to surface; the DSL lets me *request* something the venue may not support.

---

### Category — Adversarial Edge-Cases & Coverage Completion

This category does not bet on market behavior at all — every profile is a probe aimed at a specific code path or invariant in the 11-stage hot-path pipeline (services/hot_path/src/processor.py) and the execution/exit machinery. The other five categories (trend, meanrev, breakout, multifactor, risk) naturally cluster on the "happy path": rules that fire sometimes, in plausible regimes, with sane thresholds. They will systematically AVOID the degenerate inputs that break systems. This suite deliberately drives the degenerate inputs:

- A NEVER-FIRES profile (impossible threshold) to confirm an always-abstaining profile is cheap and logs sanely rather than erroring or spamming.
- An ALWAYS-FIRES profile (trivially-true threshold) to saturate the ReentryGate (one open position per (profile,symbol)), hit the order-burst tripwire (processor.py:911 `_order_tripwire_record`), the rate limiter, and — critically — to prove the abstention low-ATR floor (services/hot_path/src/abstention.py:20, `atr < price*0.003`) gates even a trivially-true rule. "Always fires" is a misnomer the system should expose.
- An entry_short-ONLY profile to answer the genuinely open question: on a SPOT account, does a non-reduce-only SELL open a real short paper Position? Verified in code: it does — executor.py:467-480 creates a Position row with side=SELL with NO spot guard. That is a latent correctness question (a spot account cannot actually be short) this profile forces into the open.
- An EQ-operator-on-continuous-indicator profile to exercise the `ind_val == val` exact-float branch (services/strategy/src/compiler.py:48-49 and hot_path strategy_eval) which has no isclose tolerance and therefore ~never matches — a near-never-fires path distinct from (a).
- A CRISIS-only preferred_regimes profile to exercise BOTH the regime-preference shadow gate (processor.py:465-494) and the CRISIS abstention short-circuit (abstention.py:23) — and to surface that they DOUBLE-block: CRISIS is caught by abstention BEFORE the regime gate even runs, so a CRISIS-only profile is dead by construction.
- A raw-price-level / rare-indicator profile (vwap, keltner.middle, macd.signal_line, hurst) to complete indicator coverage for keys the other categories skip.

The value is COVERAGE and BUG-DISCOVERY, not edge. Negative PnL — or zero trades — is the expected and acceptable outcome for most of these.

#### ADV-01 Never-Fires Sentinel (z_score impossible)  — ✅ API-authorable

*Tests that a profile whose entry condition is mathematically impossible (z_score above 99, when z_score is bounded ~-3..3) NEVER emits a signal and wastes no execution resources while still being evaluated each tick.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "z_score",
      "comparison": "above",
      "threshold": 99.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.5,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.05,"take_profit_pct":0.1,"max_holding_hours":24,"max_allocation_pct":0.1,"max_drawdown_pct":0.2,"circuit_breaker_daily_loss_pct":0.1}`  ·  **blacklist:** `[]`  ·  **regimes:** `[]`

**Tests:** Rule-eval stage returns False every bar -> ABSTAIN; never reaches abstention/regime/agent/risk stages. Exercises the per-tick eval cost of a profile that emits zero orders on BOTH symbols (blacklist=[]). z_score calculator (libs/indicators/_zscore.py: bounded ~-3..3, sample stdev).

**Expected behavior (deviation = issue):** Fires NEVER. Zero positions on either symbol for the life of the soak. Decision log should show consistent rule-eval=False (no signal) with no downstream gate noise. CPU spent on indicator computation only. If this profile ever opens a position, that is a serious eval bug.

#### ADV-02 Always-Fires Saturator (rsi at_or_above 0)  — ✅ API-authorable

*Tests ReentryGate saturation, order-burst tripwire, rate limiting, and the abstention low-ATR floor by making the long leg trivially true (rsi at_or_above 0; rsi is 0..100 so always passes).*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "at_or_above",
      "threshold": 0.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 1.0,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.02,"take_profit_pct":0.02,"max_holding_hours":1,"max_allocation_pct":0.05,"max_drawdown_pct":0.2,"circuit_breaker_daily_loss_pct":0.05}`  ·  **blacklist:** `["ETH/USDT"]`  ·  **regimes:** `[]`

**Tests:** ReentryGate (one open position per profile+symbol) under a rule that wants to fire on EVERY tick; order-burst tripwire (processor.py:911); rate_limiter; AND proves the abstention floor (abstention.py:20, atr<price*0.003) gates even a trivially-true rule in calm markets. Tight SL/TP (0.02) + max_holding_hours=1 forces rapid open->close->reopen churn to stress the reopen race. BTC-only via ETH blacklist isolates the saturation signal.

**Expected behavior (deviation = issue):** On the FIRST tick after priming it opens one BTC position, then ReentryGate blocks every subsequent tick until SL/TP/time closes it; then it immediately reopens. Should produce the highest trade count of the suite — a churn machine. Watch for: tripwire/rate-limit throttling, abstention blocking it during low-ATR lulls (proving 'always fires' is false), and any double-open race at the close/reopen boundary.

#### ADV-03 Spot-Short Probe (entry_short only)  — ✅ API-authorable

*Answers whether a SELL entry with no existing position opens a real short paper Position on a SPOT account, which is physically impossible on spot — a latent correctness question.*

**rules_json:**

```json
{
  "entry_short": [
    {
      "indicator": "rsi",
      "comparison": "at_or_above",
      "threshold": 55.0
    }
  ],
  "match_mode_short": "all",
  "confidence": 0.6,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.03,"take_profit_pct":0.03,"max_holding_hours":6,"max_allocation_pct":0.05,"max_drawdown_pct":0.2,"circuit_breaker_daily_loss_pct":0.1}`  ·  **blacklist:** `["ETH/USDT"]`  ·  **regimes:** `[]`

**Tests:** entry_short -> SignalDirection SELL -> OrderApprovedEvent side=SELL (processor.py:898) -> executor creates Position side=SELL with NO spot guard (executor.py:467-480). Then tests whether the protective stop (executor.py:240-245 close_side=BUY for a short) and the PnL/exit path correctly handle a SELL-side position. rsi>=55 fires often enough to actually exercise the path. BTC-only.

**Expected behavior (deviation = issue):** rsi>=55 is common, so it WILL attempt to open. If the system has no spot-short guard it opens a side=SELL Position and PnL is inverted (profit when price falls). The interesting failure modes: PnL sign errors on a short, SL>TP exit-band confusion for a short (exit_policy.py), or the protective-stop side flipping wrong. If instead SELL-with-no-position errors or no-ops, that's the cleaner-but-also-worth-knowing outcome. Either way this surfaces the spot-short contract.

#### ADV-04 EQ Exact-Float Trap (rsi equals 50)  — ✅ API-authorable

*Tests the EQ operator on a continuous indicator — exact float equality (rsi equals 50.0) which has no isclose tolerance, so it essentially never matches even when rsi is 'around' 50.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "equals",
      "threshold": 50.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.5,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.05,"take_profit_pct":0.08,"max_holding_hours":12,"max_allocation_pct":0.05,"max_drawdown_pct":0.2,"circuit_breaker_daily_loss_pct":0.1}`  ·  **blacklist:** `[]`  ·  **regimes:** `[]`

**Tests:** EQ branch in _eval_conditions (compiler.py:48-49 / hot_path strategy_eval: `ind_val == val`, no math.isclose). rsi is a float that rarely lands on exactly 50.000000. Distinct code path from ADV-01: ADV-01 is structurally impossible; ADV-04 is theoretically-possible-but-practically-never. Trades both symbols (blacklist=[]) to maximize the chance of an exact-50 hit and confirm it still ~never fires.

**Expected behavior (deviation = issue):** Fires effectively never (perhaps a freak exact-50.0 hit across millions of bars, unlikely). Confirms EQ is exact-equality and that the system tolerates a profile that compiles, validates, and runs but practically never matches. If it fires implausibly often, that hints at rsi being rounded/quantized somewhere upstream — itself a finding.

#### ADV-05 CRISIS-Only Ghost (preferred_regimes=[CRISIS])  — ✅ API-authorable

*Tests the CRISIS short-circuit: a profile gated to ONLY trade in CRISIS should never trade, because CRISIS is independently caught by the abstention short-circuit before the regime-preference gate.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "rsi",
      "comparison": "below",
      "threshold": 40.0
    }
  ],
  "match_mode_long": "all",
  "confidence": 0.7,
  "preferred_regimes": [
    "CRISIS"
  ]
}
```
**risk_limits:** `{"stop_loss_pct":0.1,"take_profit_pct":0.15,"max_holding_hours":48,"max_allocation_pct":0.05,"max_drawdown_pct":0.3,"circuit_breaker_daily_loss_pct":0.2}`  ·  **blacklist:** `[]`  ·  **regimes:** `["CRISIS"]`

**Tests:** Two interacting CRISIS paths: (1) regime-preference gate (processor.py:465-494) blocks with BLOCKED_REGIME_MISMATCH + shadow=true whenever live regime != CRISIS; (2) abstention CRISIS short-circuit (abstention.py:23) abstains WHEN regime IS CRISIS. Since abstention runs BEFORE the regime-preference gate in the pipeline, a CRISIS-only profile is dead by construction. rsi<40 is a plausible entry so the only thing stopping trades is the regime double-block.

**Expected behavior (deviation = issue):** Fires NEVER. In non-CRISIS regimes: shadow-blocked (BLOCKED_REGIME_MISMATCH, decision row written with shadow=true). In CRISIS: abstained (crisis_regime reason). Net zero trades ever. The decision log should clearly show the two distinct block reasons in different regimes — that contrast is the deliverable. Confirms preferred_regimes=[CRISIS] is effectively a permanent no-trade switch.

#### ADV-06 Raw-Price-Level Coverage (vwap + keltner.middle + macd.signal_line + hurst)  — ✅ API-authorable

*Completes indicator coverage by touching keys the other five categories typically skip: vwap and keltner.middle used as raw PRICE thresholds, macd.signal_line (vs the more common macd_line/histogram), and hurst as a trend-persistence gate.*

**rules_json:**

```json
{
  "entry_long": [
    {
      "indicator": "hurst",
      "comparison": "above",
      "threshold": 0.5
    },
    {
      "indicator": "macd_signal",
      "comparison": "above",
      "threshold": 0.0
    },
    {
      "indicator": "keltner.middle",
      "comparison": "above",
      "threshold": 1.0
    }
  ],
  "match_mode_long": "any",
  "confidence": 0.5,
  "preferred_regimes": []
}
```
**risk_limits:** `{"stop_loss_pct":0.06,"take_profit_pct":0.1,"max_holding_hours":24,"max_allocation_pct":0.05,"max_drawdown_pct":0.25,"circuit_breaker_daily_loss_pct":0.1}`  ·  **blacklist:** `[]`  ·  **regimes:** `[]`

**Tests:** Four otherwise-untested user-facing keys: hurst (libs/indicators/_hurst.py ~0..1, >0.5=persistent), macd_signal (the EMA-of-MACD line, distinct from macd_line/histogram), keltner.middle (an EMA = a raw PRICE level, so threshold 1.0 is trivially below BTC/ETH price -> always-true leg), vwap is covered conceptually here via keltner.middle being a price level. match_mode_long='any' (OR) means ANY leg passing fires — and keltner.middle>1.0 is always true for these symbols, so this is also a soft always-fires via a PRICE-level gotcha (a user mistaking a price-level indicator for a normalized one). Trades both symbols.

**Expected behavior (deviation = issue):** Fires often because keltner.middle>1.0 (price>$1) is always true and the legs are OR'd — exposing the foot-gun of comparing a raw-price indicator (keltner.middle/vwap/bb.upper/lower) against a small numeric threshold. Effectively reduces to an always-open-when-ATR-permits profile gated only by the abstention floor. The hurst>0.5 and macd_signal>0 legs are the genuinely informative ones but are masked by the OR. Confirms hurst/macd_signal/keltner.middle all compute and route through the pipeline without error.

**Issues this category is built to surface:**

**1. Spot-short correctness (highest value).** ADV-03 forces the question: executor.py:467-480 creates a Position with side=SELL on a non-reduce-only SELL with NO check that the account/symbol supports shorting. On SPOT this is physically impossible. Downstream risks to flush out: (a) PnL sign — does a SELL-side position profit when price FALLS? (b) exit-band logic in exit_policy.py — for a short, SL is ABOVE entry and TP BELOW; does SL>TP precedence still hold correctly? (c) protective stop side (executor.py:241-245 picks close_side=BUY for a short) — does it place the stop on the correct side? (d) does the reconciler treat a phantom short sanely?

**2. 'Always-fires' is gated by the abstention floor.** ADV-02 should prove that rsi>=0 does NOT fire in calm markets because atr<price*0.003 abstains first (abstention.py:20). If it fires anyway during a verified low-ATR lull, the floor is broken.

**3. ReentryGate reopen race.** ADV-02 with SL/TP=0.02 and max_holding_hours=1 churns open->close->reopen fast. Surfaces whether the optimistic held-mark (processor.py:913) + the real close can double-open at the boundary, or strand allocation (executor.py:435-438 notes decrement-on-close is a separate follow-up — allocated_qty may leak on close).

**4. CRISIS double-block ordering.** ADV-05 should show two DIFFERENT block reasons by regime (shadow regime-mismatch when not CRISIS; crisis_regime abstain when CRISIS). If a CRISIS-only profile EVER trades, the short-circuit ordering is wrong.

**5. Price-level foot-gun.** ADV-06's keltner.middle>1.0 (and by extension vwap/bb.upper/bb.lower) is always-true for BTC/ETH — surfaces that the DSL lets a user compare a raw-PRICE indicator against a normalized-looking threshold with no warning, silently producing an always-on leg under OR match_mode.

**6. Resource waste of dead profiles.** ADV-01/04/05 should consume only indicator-compute, never reaching execution. If a never-firing profile shows up in order/validation logs, the early-abstain path leaks.

**7. Two profiles on the same symbol (BTC).** ADV-02 and ADV-03 are both BTC-only — surfaces whether two profiles race the per-(profile,symbol) ReentryGate independently (they should; the gate keys on profile_id) or contend on a shared lock/allocation.

**What it teaches the meta-learner:**

The freshly-reset meta-learner (agent EWMA weights at AGENT_DEFAULTS this session) benefits from EXTREME signal diversity at the tails, which the happy-path categories cannot provide:

- **Null/degenerate samples** (ADV-01, ADV-04, ADV-05): profiles that emit zero decisions teach the decay tracker what a permanently-silent profile looks like in the baseline (latest-wins: these carry a profile_id, so their backtest baseline becomes the canonical 'dead' reference) — useful as a negative control against which firing profiles are compared.
- **Short-side samples** (ADV-03): the ONLY source of SELL-direction execution outcomes in the whole suite. The agent ensemble snapshots scores at execution keyed on side (executor.py:484-486 `_record_agent_scores(..., ev.side)`); without a short profile the learner sees only BUY-side attributions. ADV-03 enriches the side dimension.
- **Saturation/churn samples** (ADV-02): a high-frequency stream of open/close outcomes gives the EWMA weights many rapid update events in a short window — a different temporal density than the slow happy-path profiles, testing whether fast feedback destabilizes the freshly-reset weights.
- **Regime-edge samples** (ADV-05): shadow decisions (BLOCKED_REGIME_MISMATCH, shadow=true) feed the would-be-vs-live comparison (PR3) with a profile that is shadow-blocked in EVERY non-CRISIS regime — a clean stress of the shadow-accounting path.

Collectively these define the BOUNDARY of the learning substrate (never-fires, always-fires, short, regime-dead) so the meta-learner's behavior is characterized at its extremes, not just its center.

**Capability gaps hit while designing this category:**

**Whole-suite indicator coverage audit (the load-bearing finding).** There are 20 canonical SUPPORTED_INDICATORS (schemas.py:608-628) but the user-facing DSL `StrategySignal.indicator` is typed as the 12-key `_UserIndicatorName` Literal (schemas.py:678-691) and `strategy_rules_to_canonical` maps only those 12 via `_INDICATOR_USER_TO_CANONICAL` (schemas.py:696-710). Therefore **7 keys are UNREACHABLE via `POST /profiles`**: `adx`, `bb.pct_b`, `bb.bandwidth`, `bb.upper`, `bb.lower`, `obv`, `choppiness`. Submitting any of them makes Pydantic reject `StrategyRulesInput` at validation. The 12 REACHABLE user-facing keys are: rsi, atr, macd_line, macd_signal, macd_histogram, vwap, keltner.upper/middle/lower, rvol, z_score, hurst. Across all six categories, **the suite can at best cover those 12**; the 7 bb/adx/obv/choppiness keys can only be reached by writing canonical `strategy_rules` directly (pipeline-canvas `strategy_eval` node per pipeline_compiler.py, or DB), NOT through the documented creation API. This contradicts the prompt's premise that bb.*/adx/choppiness are usable via rules_json — they are validated as canonical but not exposed in the user DSL. **This mismatch is itself the top capability gap and should be raised with the architect** (candidate for TECH-DEBT-REGISTRY: either extend `_UserIndicatorName`+the map to all 20, or document the 12-key user surface as intentional).

Of my reachable targets, this suite directly references rsi, z_score, hurst, macd_signal, keltner.middle. Combined with the expected coverage from trend (rsi, macd_line, macd_histogram, hurst), meanrev (rsi, z_score, keltner.*), breakout (atr, rvol, keltner.upper/lower, vwap), the 12 user-facing keys are FULLY covered by the suite. **Still untested across the entire platform via the API: adx, bb.pct_b, bb.bandwidth, bb.upper, bb.lower, obv, choppiness (7 keys) — unreachable, not merely unused.**

**DSL expressiveness gaps this category wanted but could not express:**
- No crossover/cross-event operator — could not test 'macd_line crosses signal_line' (the canonical MACD signal); only static `macd_line above 0` style thresholds. A true 'always-fires on a cross' or 'never-fires impossible cross' probe is impossible.
- No stateful/trailing/sequence logic — could not build a profile that opens then trails a stop, or a 2-bar-confirmation entry; can't adversarially test trailing-stop edge cases because trailing stops aren't expressible (only fixed SL/TP/time in exit_policy.py).
- No multi-timeframe — could not probe a 1m-vs-1h disagreement edge case.
- No opposing-signal close — entry_short cannot CLOSE a long; only SL/TP/time close. So ADV-03's short and a hypothetical long on the same symbol cannot net/flatten each other, which limits how thoroughly the spot-short contract can be exercised.
- No perp/futures/funding — the spot-short question (ADV-03) is exactly the seam where the absence of a real short instrument is felt; properly shorting is EN-W3, not designable today.
- EQ has no tolerance parameter — cannot express 'rsi approximately 50'; the only equality test available is the exact-float trap (ADV-04), which is informative but a blunt instrument.
- preferred_regimes cannot express 'NOT regime X' or weighting — only an allowlist; combined with the abstention CRISIS short-circuit, a CRISIS-only profile is structurally dead and there is no way to make a profile that trades ONLY in CRISIS (the one regime the system refuses to trade).

---

## 4 · Coverage

**Indicator coverage.** The designed suite references the indicators below. All **12 authorable** keys are covered except `atr` and `vwap` (referenced in prose but absent from the final `rules_json` of any profile — a gap to close); the 7 engine-only keys are reachable only via canonical write.

| Indicator | In suite? | Path |
|---|---|---|
| `rsi` | yes | API-authorable |
| `z_score` | yes | API-authorable |
| `hurst` | yes | API-authorable |
| `macd_line` | yes | API-authorable |
| `macd_histogram` | yes | API-authorable |
| `macd_signal` | yes | API-authorable |
| `rvol` | yes | API-authorable |
| `keltner.upper` | yes | API-authorable |
| `keltner.middle` | yes | API-authorable |
| `keltner.lower` | yes | API-authorable |
| `atr` | **NOT yet** | API-authorable — add a coverage filler (see below) |
| `vwap` | **NOT yet** | API-authorable — add a coverage filler (see below) |
| `adx` | yes | canonical-only |
| `bb.pct_b` | yes | canonical-only |
| `bb.bandwidth` | yes | canonical-only |
| `choppiness` | yes | canonical-only |
| `bb.upper` | **NOT yet** | canonical-only — add a canonical filler |
| `bb.lower` | **NOT yet** | canonical-only — add a canonical filler |
| `obv` | **NOT yet** | canonical-only — add a canonical filler |

**Coverage-completion fillers** (calculator-path coverage only — these reference price/level indicators that, per §2.3, are not real signals; they exist to exercise the remaining calculators):

- **`COV-ATR-VWAP` (API-authorable, BTC-only):** `{"entry_long":[{"indicator":"atr","comparison":"at_or_above","threshold":0},{"indicator":"vwap","comparison":"at_or_above","threshold":0}],"match_mode_long":"all","confidence":0.5}`, blacklist `["ETH/USDT"]`. Always-true (atr≥0, vwap≥0) → always-fires (like the saturator) but drives the `atr` and `vwap` calculator + eval-dict path. Tiny `max_allocation_pct` (e.g. 0.03).
- **`COV-OBV-BB` (canonical-only):** a direct canonical write referencing `obv`, `bb.upper`, `bb.lower` (e.g. `obv at_or_above 0`) to cover the last three calculators once the canonical-write path (§6) is set up.

**Feature coverage** the suite achieves across the 26 profiles + fillers:

- Both entry legs (long-only, short-only, both-legs symmetric) ✓ · match_mode all AND any ✓ · 1–5 conditions per leg ✓
- All 5 regimes gated (incl. the CRISIS-only dead profile and HIGH_VOLATILITY dormancy probe) ✓
- Every risk dimension stressed: ultra-tight SL/TP, 30-min time exit, circuit-breaker trip, drawdown, tiny vs large allocation ✓
- Symbol scoping: BTC-only, ETH-only, both-symbols (cluster-cap probe) ✓
- Firing frequency: never-fires, always-fires, rare 5-AND confluence, OR firehose ✓
- Close-reason vocabulary: stop_loss, take_profit, time_exit, plus no-outcome and halted-then-resumed ✓
- The full authorable-indicator set (with the atr/vwap fillers) ✓; the 7 engine-only keys via canonical fillers ✓

## 5 · Issues this suite is built to surface (prioritized watch-list)

Deduplicated across categories, highest-value first. Each is a concrete hypothesis to confirm or refute by watching the paper run:

1. **Spot-short correctness (top priority).** Does `entry_short` open a real short paper position on a spot-only venue? If so, verify: (a) PnL profits when price *falls*; (b) for a short, SL is *above* entry and TP *below* — does the SL→TP→time precedence still resolve correctly? (c) the protective-stop side is BUY; (d) the reconciler treats it sanely. (`calculator.py:41-42`, `executor.py:467-480,241-245`, `exit_policy.py`.)
2. **`closed_trades.pnl_pct` precision/overflow** under ultra-tight churn — sub-0.001 returns truncating at the 6th decimal, and the already-logged `NUMERIC(10,6)` overflow on extreme returns. (`closer.py:291-293`, mig 015.)
3. **Circuit-breaker arithmetic & reset:** `int()` micro-counter truncation under-counting tiny losses (delayed trip), and in-process `_last_reset_date` vs Redis `pnl:daily` date desync across a restart / UTC rollover. (`closer.py:240,232-239`, `circuit_breaker.py:9`.)
4. **close_reason attribution under SL>TP>time precedence** — the two-pass monitor evaluates SL/TP before time, so a position past both TP and max-hold must tag `take_profit`, never `time_exit`. (`exit_monitor.py:113-119`.)
5. **Never-firing / always-colliding profiles** (impossible thresholds, both-legs collisions, dust-floor sizing blocks, CRISIS-only) — do they run the full 11-stage eval every tick silently, or are they flagged? Does telemetry distinguish a *sizing block* and a *priming window* from a genuine *no-signal abstention*?
6. **ReentryGate per-(profile,symbol) isolation** when several profiles (plus the soak) trade the same symbol — confirm independent open-position accounting and no shared-key race. (`state.py:64-74`.)
7. **Correlation-cluster cap** engaging when BTC and ETH are both open (both are MAJORS) — is the cap live or dead code, and does it double-count against `max_allocation_pct`? (`libs/core/correlation.py`.)
8. **Abstention floor** (`atr < price*0.003`) gating even an 'always-fires' profile in calm markets — confirm it abstains as designed. (`abstention.py:20`.)
9. **Min-notional vs tiny allocation** — does a small `max_allocation_pct` produce a sub-min-notional order the risk gate silently drops, and is the drop observable? Plus the noted `allocated_qty` decrement-on-close leak.
10. **Price-scale threshold footgun** — a numeric threshold on `vwap`/`keltner.*`/`bb.upper/lower` silently makes a leg BTC-only-or-dead; confirm nothing warns the operator.

## 6 · Meta-learning value — why diversity matters now

The agent EWMA weights were clean-reset this session to `AGENT_DEFAULTS` (`agent_registry.py`; EWMA_ALPHA=0.1, MIN_SAMPLES=10), and the decay tracker has no history. A learner fed only the RSI<35 soak would relearn one archetype. This portfolio is engineered to span the axes a reset learner is starved for:

- **Firing frequency:** never → rare 5-AND → moderate → OR-firehose. The firehose specifically drives both symbols past `MIN_SAMPLES=10` fast, so the weights actually *move off defaults* in a reasonable window.
- **Direction:** the short probes are the *only* source of SELL-side execution outcomes in the whole suite — without them the learner sees only BUY-side attributions (scores are snapshotted keyed on side, `executor.py:484-486`).
- **Holding horizon:** 0.5h → 1h → 8h → 24h → 72h → 120h, spanning the exit-policy time tier so decay can be observed across short and long horizons.
- **Close-reason vocabulary:** stop_loss / take_profit / time_exit, plus the no-outcome control (dust-floor) and the halted-then-resumed control (circuit-breaker trip) — if the learner ever rewards/penalizes the zero-outcome profile, that's a labeling bug surfaced for free.
- **Same thesis, many expressions:** mean-reversion via z-score, %B, Keltner, and RSI+choppiness lets the decay tracker attribute decay to the *expression*, not the *idea* — the diversity that prevents collapsing a family into one feature.

Because every family is negative-OOS, the dominant lesson the learner takes is **what not to weight** — which is exactly the loss-side signal a pure-mean-reversion soak under-samples.

## 7 · Rollout plan — deploy without disrupting the soak

**Principles:** additive only (never touch profile `a05adba2`), small allocations, staged activation, watch the issues list, kill-switch ready.

1. **Create paused.** Create each profile via `POST /profiles` with the owner token (`user_id 6322b6fa-…`) and `is_active=false`. Use small `max_allocation_pct` (3–10%) so the aggregate of ~20 test profiles can't crowd out the soak or saturate the portfolio gross budget.
2. **Deploy in waves, not all at once** — so an issue is attributable:
   - **Wave A (sanity):** the API-authorable mean-reversion + trend long profiles (closest to the proven soak). Activate, watch one full cycle.
   - **Wave B (shorts + lifecycle):** the short probes and the risk-lifecycle stressors — this is where the spot-short and circuit-breaker findings will land. Watch closely.
   - **Wave C (adversarial + multifactor):** never-fires, always-fires, firehose, confluence, cluster-cap.
   - **Wave D (canonical-only):** the 7 engine-only-indicator profiles — only after the §2.2 gap is resolved (extend the user DSL) or a vetted canonical-write helper exists. Do **not** hand-write raw SQL into `trading_profiles` for these without a helper: `exchange_key_ref` is NOT NULL and the canonical rule shape must be exact.
3. **Backtests use `profile_id=""`.** Any exploratory backtest for these profiles must omit the profile_id or it overwrites that profile's decay baseline (latest-wins).
4. **Watch, every wave:** `grep 'loop crashed' .praxis_logs/*.log`; the issues checklist (§5); soak profile still cycling; `risk:portfolio:snapshot` clusters still all-MAJORS; the EWMA weights beginning to move off `AGENT_DEFAULTS` once the firehose clears `MIN_SAMPLES`.
5. **Kill-switch is the brake.** If any profile misbehaves, `STOP_OPENING` halts new entries without touching open positions; deactivate the specific profile (`is_active=false`) to retire it. Never `FLATTEN` (it would hit the soak too).
6. **Tear-down:** these are tests — deactivate and soft-delete (`deleted_at`) when the capability/learning objectives are met; archive their decay baselines as the EWMA reset did.

## 8 · Recommendations

1. **Close the authorable-indicator gap (§2.2) first** — extend `_UserIndicatorName` + `_INDICATOR_USER_TO_CANONICAL` to all 19 keys (small, mechanical, unblocks 7 of the 26 strategies and the adx/bb/obv/choppiness families entirely). Recommend a TECH-DEBT-REGISTRY row.
2. **Log the indicator-vs-constant limitation (§2.3) as a known design boundary** — crossover, indicator-to-indicator, and stateful logic are the biggest expressiveness gaps; whether to extend the DSL is a roadmap decision, but it should be *recorded*, because it silently caps what any strategy (test or real) can do.
3. **Run Wave A + B before anything else** — the spot-short behavior and the circuit-breaker/ledger findings are the highest-value system answers and need no new code.
4. **Add the atr/vwap coverage filler** so the authorable-indicator coverage is genuinely complete.
5. **Treat this as the EN-W4 learning substrate** — diverse, honestly-negative decision traces are exactly what the auto-deprecation + capital-allocator machinery needs to be validated against before it governs real money.

*Companion documents: the what-happened brief and the partner-decisions brief, both dated 2026-06-13.*
