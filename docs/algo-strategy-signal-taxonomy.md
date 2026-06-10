# Federated Crypto Trading Architecture
### Outside-in audit & correction framework for an existing engine

> **What this is.** You already have a working trading engine (built iteratively). This document is **not a
> greenfield build spec** — it is (1) a *target architecture* to refactor toward and (2) an *audit lens +
> prioritized correction roadmap* you apply from the outside in. Read the reference parts for the "why," then
> **go to Part 10 for the prioritized fixes.**
>
> **Expect a monolith.** Single-builder engines almost always start as one process, one position per asset, one
> margin account, and a binary kill switch. That is normal. The point is not to rebuild — it's to correct by
> **money-at-risk first** (risk governance, contagion, position truth) and migrate structure (the federation)
> only as far as it pays.
>
> **Two committed architectural decisions** frame everything below:
> 1. **Federation, not monolith** — specialized engines sharing one risk/capital/position spine, split by
>    *infrastructure + data dependency*, not by horizon.
> 2. **Netting is only valid within a shared horizon** — across horizons it destroys edge, it doesn't resolve conflict.

---

## Part 1 — Signal-type taxonomy (master catalog) · *audit your coverage*

Each family maps to a different **information source**, performs in its native regime, and *actively loses money*
outside it. **Audit use:** for each family — is it ingested? is there a strategy on it? does something know when to
trust vs. ignore it? The right-hand column is the part most strategy lists omit and the part that determines P&L.

### A. Trend / momentum signals — *directional persistence*
| Strategy / indicator | Edge source | Works / Fails |
|---|---|---|
| MA crossovers (SMA/EMA, golden/death cross) | Trend persistence | Strong trends / chops to death in ranges |
| MACD | Momentum + trend | Sustained moves / late & whipsawy in mean-reverting markets |
| Breakout (Donchian / channel / range break) | Regime transition | Volatility expansion / false breakouts in low-vol ranges |
| Time-series momentum (12m, 30d ROC) | Autocorrelation of returns | Trending assets / reverses hard at tops |
| ADX-gated trend entries | Trend *strength* filter | Confirms trend exists / lags the actual turn |
| Ichimoku, SuperTrend, Turtle | Composite trend | Clean trends / parameter-fragile |

### B. Mean-reversion signals — *deviation from a center*
| Strategy / indicator | Edge source | Works / Fails |
|---|---|---|
| Bollinger Band reversion | Std-dev extremes | Range-bound / catastrophic in trends (you fade a breakout) |
| RSI / Stochastic OB-OS | Short-term exhaustion | Choppy ranges / "overbought stays overbought" in trends |
| Z-score reversion to VWAP/mean | Statistical pull-back | Stable distributions / regime breaks invalidate the mean |
| Pairs / cointegration (stat-arb) | Spread reversion | Stable relationship / cointegration breaks without warning |
| Ornstein-Uhlenbeck spread models | Modeled reversion speed | Mean-reverting series / mis-estimated half-life ruins it |

### C. Volatility signals — *magnitude of movement (often regime-defining)*
| Strategy / indicator | Edge source | Works / Fails |
|---|---|---|
| ATR-based breakout / sizing | Vol expansion | Transitions / noisy in stable vol |
| Bollinger squeeze | Vol compression → expansion | Pre-breakout / direction is a coin-flip |
| Vol targeting / inverse-vol sizing | Risk normalization | Always useful as an overlay / lags vol spikes |
| GARCH / realized-vol forecasting | Vol clustering | Predictable vol regimes / fails at structural breaks |
| Implied vs realized (options) | Vol risk premium | Liquid options (BTC/ETH) / sparse for alts |

### D. Volume / flow signals — *conviction behind price*
| Strategy / indicator | Edge source | Works / Fails |
|---|---|---|
| VWAP / TWAP | Execution benchmark + reversion | Intraday / weak as a standalone signal |
| OBV, Accumulation/Distribution | Volume-price divergence | Confirmation / many false divergences |
| Volume Profile / VPVR (value areas, POC) | Liquidity zones | Range/support-resistance / subjective node selection |
| Money Flow Index | Volume-weighted RSI | Same regime caveats as RSI |

### E. Order-book / microstructure signals  ⚑ *crypto-critical* — *tape-level supply/demand*
| Strategy / indicator | Edge source | Works / Fails |
|---|---|---|
| Order-book imbalance | Pressure asymmetry | HFT/short horizon / spoofing & decays in ms |
| Market making / spread capture | Liquidity provision rebate + spread | Stable 2-sided flow / inventory risk on trends, adverse selection |
| Depth / liquidity-gap detection | Slippage avoidance | Thin alt books / data-latency sensitive |
| Iceberg / spoof detection | Hidden-liquidity inference | Detecting real size / arms race with manipulators |
| Latency arbitrage | Speed | Co-located only / not viable retail |

### F. Arbitrage signals  ⚑ *richest set in crypto* — *price/relationship dislocations*
| Strategy | Edge source | Works / Fails |
|---|---|---|
| Cross-exchange (spatial) arb | Price differential | 24/7 fragmentation / transfer time, withdrawal limits, fee drag |
| Triangular arb | Intra-exchange pricing loop | Always-on / gone in milliseconds, fee-sensitive |
| **Funding-rate arb (perp ↔ spot)** | Perp funding payments | Persistent in crypto / funding flips, basis blowups |
| **Cash-and-carry / basis trade** | Futures premium | Contango markets / negative basis & roll risk |
| DEX–CEX arb | On-chain vs off-chain lag | Real edge / gas, MEV competition, bridge risk |
| Stat-arb baskets | Cross-asset reversion | Diversified / correlation regime shifts |

### G. Sentiment / alt-data — *crowd positioning & narrative*
| Strategy | Edge source | Works / Fails |
|---|---|---|
| Social sentiment NLP (X, Reddit, Telegram) | Crowd emotion | Reflexive alt pumps / bots, manipulation, noise |
| News-event NLP | Information speed | Discrete catalysts / latency vs. pro feeds |
| Fear & Greed, funding as positioning proxy | Contrarian extremes | Capitulation/euphoria turns / weak in the middle |
| Google Trends / search interest | Retail attention | Macro tops/bottoms / very low frequency |

### H. On-chain signals  ⚑ *crypto-native* — *settlement-layer behavior*
| Strategy | Edge source | Works / Fails |
|---|---|---|
| Exchange in/outflows | Supply hitting/leaving sell-side | Medium-horizon / attribution noise |
| MVRV, SOPR, NVT | Valuation extremes | Cycle timing / slow, not for intraday |
| Active addresses / network growth | Adoption proxy | Trend confirmation / gameable |
| Whale-wallet / large-tx tracking | Smart-money flow | Event-driven / wallet attribution is hard |
| Stablecoin supply & flows | Dry-powder proxy | Macro liquidity / lagging |
| Miner flows / hash ribbons | Supply-side stress | Cycle bottoms / BTC-only, slow |

### I. Market-structure / positioning  ⚑ *crypto-critical* — *leverage & crowding*
| Strategy | Edge source | Works / Fails |
|---|---|---|
| Open-interest dynamics | Leverage build-up | Squeeze setups / direction ambiguous |
| Funding rate as crowding signal | Positioning extreme | Mean-reversion of crowded trades / can persist |
| Liquidation-cascade / liq-level mapping | Forced-flow targeting | Volatile / liquidation data is estimated |
| BTC dominance / correlation regime | Risk-on vs risk-off rotation | Alt timing / regime-dependent itself |

### J. Time / seasonality — *recurring temporal structure*
| Strategy | Edge source | Works / Fails |
|---|---|---|
| Time-of-day / day-of-week effects | Liquidity cycles | Statistical edge / thin and decaying |
| Funding-settlement timing | Mechanical flows (8h cycle) | Predictable windows / crowded |
| Options-expiry / max-pain effects | Dealer hedging | Around expiry (BTC/ETH) / overstated |

### K. Predictive / ML — *learned patterns across the above*
| Approach | Edge source | Works / Fails |
|---|---|---|
| Supervised return/direction classifiers | Feature combinations | Stationary regimes / overfit, decays, hard to trust |
| Reinforcement-learning agents | Sequential decision optimization | Sim / brutal sim-to-real gap, reward hacking |
| Anomaly / change-point detection | Regime-shift detection | Feeds the router well / false alarms |

---

## Part 2 — The engine federation (target structure)

Three engines along **infrastructure + data-dependency** lines (not horizon — that over-fragments). Each owns a
disjoint slice of Part 1, runs its **own** regime detection at its own cadence, and nets into the shared book.

**Engine 1 — Microstructure / Execution-Edge** (ms–sec, latency-critical)
Owns: family E + latency/triangular arb. Strategies: market-making, OB-imbalance scalps, latency/triangular arb.
Infra: colocation, kernel-bypass, in-memory books, raw tick feeds, **dedicated low-latency execution path. No LLM
in the hot loop.** Profile: high Sharpe, low capacity. Killed by: latency loss, adverse selection, fee changes.

**Engine 2 — Tactical** (sec–days; intraday + swing)
Owns: families A, B, C, D, cross-exchange & funding/basis arb, G, I, J. The broad directional + relative-value
middle; the regime router primarily lives here. Infra: websocket/REST, broad coverage, no colocation. Profile:
medium capacity/turnover. Killed by: regime whipsaw, edge decay, cost drag.
*Intraday vs swing share infra → keep as one engine, two modules. Split only if risk profiles truly diverge.*

**Engine 3 — Positioning / Macro** (days–weeks)
Owns: family H, macro/liquidity, longer carry/basis, dominance/correlation, macro sentiment. **Also sets the
gross-exposure budget the faster engines operate within (the macro overlay).** Infra: on-chain indexers,
low-frequency, patient TWAP execution. Profile: high capacity, low turnover. Killed by: attribution noise,
signals too slow, narrative regime shifts.

---

## Part 3 — The shared platform spine

The federation only works if engines plug into a common platform. This layer — not the strategies — is where it
compounds or quietly bleeds.

1. **Unified position & exposure book** — every engine nets into one *intended* and one *actual* position per
   asset + aggregate. The truth is the net, not the sum of each engine's view.
2. **Cross-engine arbitration / netting policy** (Part 5).
3. **Capital allocator** across engines (Part 7) — risk-budget weighted, not equal-weight.
4. **Aggregate risk manager + kill switches** (Part 6) — net-level limits override per-engine.
5. **Macro overlay** — Engine 3 sets gross-exposure budget/bias for Engines 1–2.
6. **Execution / OMS** — shared smart router for 2–3; **Engine 1 keeps its own dedicated path.**
7. **Market-data layer** — shared normalized feed for 2–3; Engine 1 has a dedicated raw/low-latency feed.
8. **Cost & PnL attribution per engine** — net-of-cost, so you can kill an engine that isn't paying.
9. **Reconciliation & accounting** — true PnL, drift detection between local engine state and the book.
10. **Agentic orchestration tier** — supervisory only; proposes within hard deterministic rails it cannot override;
    **never in the hot loop, never in the kill-switch path.**
11. **Backtest/sim + decay-detection harness** — walk-forward, look-ahead/survivorship guards, live-vs-backtest tracking.

---

## Part 4 — Regime detection & routing (runs *inside each engine*)

Each engine classifies regime on its own clock and gates **strategy weight** — not on/off switches.

**Dimensions:** directionality (ADX, Hurst, efficiency ratio) · volatility (RV/ATR percentile, GARCH) · liquidity
(spread, depth, volume) · correlation (risk-on/off, BTC dominance) · positioning (funding, OI).

**Methods, by robustness:** rule-based thresholds (brittle at boundaries) → vol-percentile bucketing (simple,
effective) → Hurst/variance-ratio → HMM/Markov switching (overfits in-sample) → change-point detection (transitions)
→ ML classifiers (only with brutal walk-forward).

| Regime | Lean into | Suppress |
|---|---|---|
| Strong trend, expanding vol | Trend, breakout, momentum | Mean-reversion |
| Range-bound, low vol | Mean-reversion, market-making, range | Breakout |
| Vol compression | Squeeze/breakout *setups*, reduce size | Directional conviction |
| High vol / crisis | Cut gross, vol-target down, arb only | Leveraged directional, illiquid alts |
| Crowded leverage (funding extreme) | Contrarian/fade, funding arb | Trend-chasing into the crowd |
| Thin liquidity | Pull market-making, widen, reduce | Anything size-sensitive |

**Use weights + hysteresis** (separate enter/exit thresholds) to avoid threshold thrashing.

---

## Part 5 — Position-truth & netting policy

**Principle: netting is only valid between positions sharing a horizon + execution style. Across horizons it is
edge destruction, not conflict resolution.**

The three pure options, and why each breaks:
- **A · Capital-partitioned sleeves** — each engine trades its own sub-book; net = sum. *Flaw:* capital fragments,
  and on a shared margin account the partition doesn't isolate liquidation risk. *Virtue:* clean PnL attribution.
- **B · Priority / veto** — higher engine overrides lower. *Flaw:* which engine should win is regime-dependent, so a
  static hierarchy is wrong somewhere and a dynamic one is just another lagging classifier. Veto destroys attribution.
  A market-maker can't function under one-sided veto. **Structurally incompatible with Engine 1.**
- **C · Net-and-suppress** — cancel opposing intents internally, send only the net. *Flaw:* silently kills
  high-turnover engines (E1's 800ms scalp gets netted against E2's 3-day hold and never executes); collapses
  attribution; re-couples slow engines to the fast engine's tempo; netted orders have no coherent execution style.

**Conclusion (hybrid): partition across horizon families; net/overlay within one; never hard-veto.**
- **Engine 1 is a hard-isolated sleeve — non-negotiable.** Its edge is turnover; any netting/veto against a standing
  position kills it. Shared book only *observes* it.
- **Engines 2 + 3 are a directional family** combined as **budget, not veto**: Engine 3 sizes the gross-exposure box,
  Engine 2 allocates within it (preserves Engine 2's attribution). Optional refinement: an **internal crossing layer**
  matching opposing 2↔3 intents at mid before hitting the exchange — captures C's fee savings, keeps A's attribution.
  Works *only within* a horizon family.

**Decision principle: prefer the metered failure over the invisible one.** A's internal-wash cost is bounded and
measurable; C's suppressed-edge cost is unbounded and silent. When in doubt, take the visible, bounded failure.

> **Audit your engine →** If you run a monolith with one position per asset, your netting is *implicit*. Check whether
> a short-horizon signal can flatten a position a long-horizon signal is holding. If yes, you have silent edge
> destruction today. **Correction:** tag positions by strategy/horizon lineage; forbid cross-horizon netting.

---

## Part 6 — Risk governance & kill-switch architecture *(highest money-at-risk layer)*

**Core stance: design the central risk manager assuming it will fail.** It is the single point of failure, it runs on
stale/incomplete multi-venue state, and isolating collateral (Part 5/8) stripped its cross-engine exchange authority —
it can now only *signal* engines, which lags and fails. So **demote it to optimization** (capital allocation,
concentration nudges) and put **catastrophe prevention at the per-sub-account exchange level.** Size each engine's
exchange-enforced cap so that even if the central layer is dead, the sum of every engine's worst case is survivable.
**Each isolated unit must be independently survivable.** Defense in depth, not a central guardian.

**Kill-switch verbs (tiered, never binary "flatten-all"):**
- *Stop-opening* — no new risk, keep managing. Cheap, reversible. Automate freely.
- *De-risk* — cut gross, reduce leverage, widen MM quotes. Graduated. Automate freely.
- *Neutralize* — hedge net delta without closing legs (preserves arb/basis structure).
- *Flatten* — nuclear, expensive, irreversible. **Liquidity-aware (TWAP out), not market-dump**, except true tail.

Why binary flatten is dangerous: the breach correlates with stress, so a market-dump realizes the loss into the same
cascade at the worst prices and adds its own slippage. Halting a market-maker doesn't flatten it — it leaves inventory
naked. **Halt ≠ safe.**

**Authority asymmetry:** de-risking is cheap/reversible → empower the automated layer. Flattening is expensive/
irreversible → higher threshold or human confirmation.

> **⚑ Open decision (yours to make):** *Should the automated layer ever flatten unattended, or only de-risk —
> reserving flatten for human authorization?* Fully-automated flatten = faster tail protection, but false-positive
> self-harm + the reliability inversion below. De-risk-only = safer against your own kill switch, but a true tail can
> outrun you between human check-ins on a 24/7 book. The answer depends on unattended runtime and failure-direction
> tolerance. **Document the choice explicitly.**

**Reliability inversion:** drawdown breaches correlate with API degradation/outages — the kill switch is least able to
execute when most needed. Therefore defense is **ex ante, not ex post**: conservative standing leverage, reduce-only
resting orders, pre-placed exchange stops (eyes open that stops gap), and *don't hold positions that require a heroic
exit.*

**Two central-layer blind spots:**
- Use **stress correlations (→1 in the tail)**, not trailing correlation, for portfolio limits — or you under-margin
  exactly when it matters. Three "diversified" alt longs are one position in a crash.
- Multi-venue state is always lagged/incomplete → add **per-venue local caps** so no single venue blows up while the
  aggregator is blind.

**The agent vs. the kill switch:** the agentic tier lives **strictly below the deterministic risk floor.** It may
propose (even propose a flatten) but must never disable, delay, or sit in the kill-switch path. The kill switch must be
deterministic, dumb, auditable, and faster than the agent. *If an LLM can rationalize past your risk limits, you've
built a system that can argue itself into its own destruction.* Hierarchy: **deterministic rails > engines > agent.**

> **Audit your engine →** Your current kill switch is probably `if drawdown < threshold: close_all()`. That is likely
> the single most dangerous line in your codebase. **Correction (do first):** replace with tiered verbs + liquidity-
> aware flatten; add exchange-level per-account loss caps; verify the agent cannot bypass risk limits.

---

## Part 7 — Capital allocation

The twin of risk budgeting, and constrained by the fragmented collateral: rebalancing across isolated sub-accounts
needs transfers (slow), so the allocator runs on a **strategic cadence (daily/weekly), not tactical.** Implications:
size each engine for expected need **plus buffer**; accept some idle capital as the price of isolation; allocate to
**risk-adjusted capacity** (Engine 1 = high-Sharpe/low-capacity; Engine 3 = high-capacity/low-Sharpe), never equal-
weight. Do **not** design the allocator as if it can react in real time — it can't.

---

## Part 8 — Collateral & margin model

**Mechanic that drives everything: shared collateral = shared liquidation, and the exchange never sees your logical
sleeves.** One account → one margin ratio → the exchange liquidates on breach regardless of which engine "owned" the
position. So Engine 1's loss can force-liquidate Engine 3's healthy positions (**liquidation contagion**). A logical
sleeve gives zero protection; only separate collateral pools (sub-accounts) make isolation real.

| | Isolated sub-accounts | Shared margin, logical sleeves | Hybrid (isolate E1, share 2+3) |
|---|---|---|---|
| Liquidation contagion | Contained per engine | **Unmitigated** | E1 contained; 2+3 intentional |
| Capital efficiency | Worst (pre-fund, no offset) | Best (one pool nets margin) | Middle |
| Attribution | Exact, automatic | Approximate, needs logic | E1 exact; 2+3 modeled |
| Risk backstop | Exchange-enforced per engine | Your code only (SPOF) | Exchange backstop on E1 |
| Ops complexity | Highest | Lowest | Middle |

**Avoid portfolio margin** until your risk system is battle-tested — it nets engine risk and *rewards* stacking
correlated exposure right up until it bites.

**Recommendation: hybrid, leaning isolated.** Your cross-exchange arb strategies *require* capital pre-positioned on
multiple venues, so **you are already multi-venue and your capital is already fragmented** — the headline cost of
isolation (fragmentation) is largely *sunk* for you, making isolation far cheaper than for a single-venue shop.
Combined with Part 5 (E1 must be isolated; 2+3 are a deliberately-coupled family), the hybrid is structurally correct,
not a compromise.

**Caveats — don't oversell isolation:** it contains one engine's *idiosyncratic* blow-up, not a *common* shock (all
long, BTC craters → each sub-account just takes its own hit); and ADL/socialized-loss venues escape no structure.
**Maturity path:** start isolated (buy the exchange-level backstop while your own risk code is unproven), merge pools
selectively only once risk is battle-tested and efficiency becomes binding.

> **Audit your engine →** If you trade from one cross-margin account today, you have unmitigated contagion. Urgency
> scales with leverage: if any strategy runs leverage, isolating the fastest/most-leveraged one is a Tier-1 fix.

---

## Part 9 — Component ownership: per-engine vs. shared

| Component | Per-engine | Shared platform |
|---|---|---|
| Signal computation (owned families) | ✔ | |
| Regime detection / routing | ✔ (own cadence) | |
| Strategy logic & sizing inputs | ✔ | |
| Position book (source of truth) | local fast view | ✔ |
| Netting / arbitration policy | | ✔ |
| Capital allocation | within budget | ✔ across engines |
| Risk limits & kill switches | local | ✔ aggregate overrides |
| Exchange-level loss caps | ✔ (sub-account) | |
| Execution | E1 dedicated path | ✔ OMS for 2–3 |
| Market data | E1 raw feed | ✔ normalized for 2–3 |
| Cost / PnL attribution | | ✔ per engine |
| Reconciliation & accounting | | ✔ |
| Backtest / sim / decay detection | strategy-level | ✔ harness |
| Agentic orchestration | (never in hot loop / kill path) | ✔ supervisory |

---

## Part 10 — Prioritized correction roadmap *(apply to your existing engine — start here)*

Sequenced by **money-at-risk**, not architectural elegance. Tiers 0–1 are what actually blow up accounts; the
federation split (Tier 2) is a migration you do as it pays, not a prerequisite.

### Tier 0 — Stop the catastrophe paths (do regardless of any refactor)
1. **Replace any binary `close_all()` kill switch** with the tiered verbs (stop-opening → de-risk → neutralize →
   liquidity-aware flatten). This is the highest-priority single change.
2. **Add exchange-level loss caps** per account/sub-account. Stop relying on software-only risk for catastrophe prevention.
3. **Pull the agent/LLM out of every risk and kill-switch path.** Verify it cannot disable or exceed a limit.
4. **Switch portfolio limits to stress-correlation** assumptions (correlations → 1 in tail).
5. **Net-of-cost accounting on every strategy** (fees + funding + slippage). Kill anything net-negative now.

### Tier 1 — Position truth & contagion
6. **Single source-of-truth position book**, reconciled against the exchange continuously, with drift alarms.
7. **Tag positions by horizon/strategy lineage**; forbid cross-horizon netting (stop silent edge destruction — Part 5).
8. **If any strategy runs leverage on a shared account, isolate the fastest/most-leveraged one** into its own sub-account (Part 8).
9. **Decide & document the flatten-authority question** (Part 6 open decision).

### Tier 2 — Structure (refactor toward the federation, not urgent)
10. **Identify which of the three engine roles your code already implicitly contains**; draw the boundaries even if it
    stays one process for now.
11. **Make regime selection weight-based with hysteresis**, not binary switching.
12. **Introduce the macro overlay** as a gross-exposure budget setter (Engine 3 role).
13. **Separate execution paths** — don't route latency-sensitive flow through the same OMS as patient flow.

### Tier 3 — Governance & lifecycle
14. **Decay detection / live-vs-backtest tracking**; auto-deprecate dead edges.
15. **Capital allocator on a strategic cadence** (Part 7).
16. **Document the standing decisions** (netting policy, margin model, flatten authority) so they're explicit, not emergent.

---

## Part 11 — Critical assessment: where this fails

**Strategy-level (within engines):** regime detection lags reality; switching whipsaw (→ weights + hysteresis);
compounding router×strategy error; routers overfit and need *more* validation; crypto regimes shift in hours;
edge decay accumulates dead weight; **costs routinely exceed gross edge** (net-of-cost backtests non-negotiable).

**Federation-level (now your primary risk surface):**
- **Over-federation** — each engine is fixed overhead; build as few as constraints force. Don't split Engine 2 prematurely.
- **Shared layer is a SPOF** — if the position book / risk manager is down, all engines **safe-halt**, never trade blind.
- **Boundary leakage** — edges that span engines (funding arb in 2 *and* 3) need one owner, or you double-count.
- **Latency mismatch in the shared book** — Engine 1 updates in µs; it needs a local fast view reconciled async, or the
  book becomes its bottleneck. A real distributed-systems problem, not a config detail.
- **Reconciliation drift** — local state vs. book diverges → phantom exposure. Continuous reconciliation + alarms mandatory.
- **Agentic risk** — the smartest component, the least trusted; keep it below the deterministic risk floor.

---

**Bottom line.** You don't need to rebuild into the federation to get safe — you need Tiers 0–1. The strategy catalog
(Part 1) is a solved commodity; your survival risk lives in the **kill switch, contagion, and position-truth** layers,
and those are fixable on the engine you already have without a rewrite. The federation (Tier 2) is the direction of
travel — migrate toward it as it pays, engine by engine, keeping each isolated unit independently survivable and the
agent on a deterministic leash.
