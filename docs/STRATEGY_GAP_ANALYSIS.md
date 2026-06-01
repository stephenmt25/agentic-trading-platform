# Strategy Gap Analysis — PRAXIS Tier-2 Strategies vs Current System

> **Source doc:** `docs/PRAXIS_Trading_Strategies_Architecture.md`
> **Analyst:** Claude Code (Opus 4.7)
> **Date:** 2026-05-13
> **Branch:** `main`
> **Method:** Code-first audit. The doc was treated as a requirements spec; every gap below is anchored to a file path so the claim is checkable. Where the doc and the code disagree, the **code wins** and the doc is flagged as inaccurate.

---

## 1. Executive Summary

The PRAXIS strategy document proposes three strategies (Yield Harvester, Mean Reverter, Latency Exploiter) running in parallel across three isolated exchange sub-accounts, governed by a global portfolio risk agent. The current Praxis platform was designed and built as a **single-symbol, single-leg, directional indicator-rule engine on spot markets** (see `libs/core/schemas.py:469-533`, `services/hot_path/src/strategy_eval.py`). The strategies in the doc are structurally outside the system's current expressive range.

### Verdict per strategy

| Strategy | Verdict | Headline reason |
|---|---|---|
| Profile 1 — Yield Harvester (cash-and-carry) | **BLOCKED** | No perpetual-futures market support, no funding-rate ingestion, no spot+perp atomic pair execution, no sub-account isolation. |
| Profile 2 — Mean Reverter (cointegrated pairs) | **BLOCKED** | Strategy DSL is single-symbol; no cointegration computation; no concept of simultaneous long-A + short-B order pair; pair-ratio z-score not modeled. |
| Profile 3 — Latency Exploiter (triangular arb) | **BLOCKED** | No FOK/IOC order types (executor hardcodes `type='limit'`); no atomic 3-leg execution orchestrator; per-order adapter instantiation imposes ~hundreds-of-ms overhead per order; not a "Rust agent" as the doc claims. |
| Architecture — sub-account isolation + global risk | **BLOCKED** | No exchange sub-account abstraction; one API-key-per-profile model exists but is not the same thing; no Universal Transfer; global risk is binary kill-switch, not aggregated drawdown across accounts. |

### Severity heatmap

| | Blockers | Major | Minor |
|---|---|---|---|
| Yield Harvester | 5 | 3 | 2 |
| Mean Reverter | 4 | 3 | 1 |
| Latency Exploiter | 5 | 4 | 1 |
| Cross-cutting (architecture, ops) | 4 | 5 | 3 |

### Five most important takeaways

1. **The strategy DSL is the load-bearing constraint.** `StrategyRulesInput` / `CompiledRuleSet` (`libs/core/schemas.py:484`, `services/strategy/src/compiler.py:62`) expresses single-symbol indicator-threshold rules. None of the three strategies are single-symbol indicator-threshold strategies. No amount of "configuring a profile" gets there — the DSL itself has to be extended (or a parallel one introduced).
2. **The system has never traded a perpetual contract.** The CCXT instance in `libs/exchange/_binance.py:39` is a vanilla spot client with no `defaultType: 'future'`, no margin mode, no leverage, no funding-rate access. The `max_leverage` field in `libs/core/schemas.py:779` is a configurable *limit* that nothing reads — it is decoration, not capability.
3. **The order primitive is too narrow.** `ExchangeAdapter.place_order` (`libs/exchange/_base.py:78`) takes only `(profile_id, symbol, side, qty, price)` — no order type, no time-in-force, no reduce-only, no post-only. The Binance adapter hardcodes `type='limit'` (`libs/exchange/_binance.py:241`). Triangular arb literally cannot run on this primitive — FOK is non-negotiable for that strategy.
4. **There is no multi-leg execution concept anywhere in the code.** Every event in `libs/core/schemas.py` (`OrderApprovedEvent`, `OrderExecutedEvent`) carries one symbol and one side. Hedge legs, pair legs, and tri-arb legs all need correlation IDs and atomic-failure semantics. None of this exists today.
5. **The doc has at least three concrete inaccuracies and one large unverified assumption.** It refers to a "Rust agent" that does not exist, claims a `KillSwitch` that "revokes all API keys" (it sets one Redis key — keys are never revoked), and presumes "global drawdown monitoring" that is implemented only per-profile. Bias: target of "30–50% APY" on $15k is presented without the cost/slippage modeling that would expose how thin these edges are on retail tier accounts.

---

## 2. Cross-Cutting Themes

These are gaps that block more than one strategy. Fixing them once unblocks several.

### 2.1 Missing primitives that block multiple strategies

**Order-type expressiveness** — Blocks Latency Exploiter (FOK), Yield Harvester (perp orders with reduce-only on close, possibly post-only on entry to avoid taker fees), Mean Reverter (paired limit orders with time-in-force coherence).
- Evidence: `libs/exchange/_base.py:78` (no `order_type` param); `libs/exchange/_binance.py:241` (hardcoded limit).
- Fix shape: extend `place_order` signature with `order_type: OrderType` and `time_in_force: TimeInForce`; add enums to `libs/core/enums.py`; thread through `OrderApprovedEvent`.

**Multi-leg / atomic-order semantics** — Blocks all three strategies. Each needs ≥2 simultaneous legs (spot+perp, long+short pair, three FOK loops). The single-event-single-order model in `libs/core/schemas.py:88-115` cannot express "these N orders are a logical group; if any fails, undo or never start the others."
- Fix shape: add a `correlation_id` / `leg_group_id` to order events; introduce an `ExecutionPlan` concept; build an `AtomicMultiLegExecutor` that either submits all FOK in parallel (tri-arb), or rolls back via offsetting trades (cash-and-carry / pairs) on partial fill.

**Perpetual / futures market access** — Blocks Yield Harvester directly; weakly relevant to Mean Reverter (which would be vastly more capital-efficient with perps). No code path constructs a futures CCXT client; no migration carries `market_type` or `contract_type` columns; no service understands the difference. Evidence: grep for `perpetual|perp|futures|margin_mode|leverage` matches only docs and frontend cosmetics (see audit log), plus the dead `max_leverage` config field.

**Sub-account routing / per-account isolation** — Blocks the architecture. Today there is "one API key per profile" via `trading_profiles.exchange_key_ref` (`migrations/versions/001_initial_schema.sql:20`) which the executor resolves at order-time (`services/execution/src/executor.py:71-96`). This is necessary but not sufficient — the executor has no concept that those keys correspond to sub-accounts under one master, no Universal-Transfer surface, no consolidated balance view.

**Funding-rate data plane** — Blocks Yield Harvester completely. `grep -ri funding` returns zero Python hits (only the doc, a frontend lockfile, and a promptfoo config). No ingestion, no storage, no signal channel.

**Pair / multi-symbol correlated state** — Blocks Mean Reverter. Indicators in `services/hot_path/src/strategy_eval.py:38-100` are computed per-symbol from `MarketTickEvent` (one symbol per event). The `z_score` indicator (`libs/indicators`) takes only `price` — a single-symbol z-score of returns, not a pair-ratio z-score. Cointegration tests (Engle-Granger / Johansen) don't exist anywhere in the indicators library or the strategy code.

### 2.2 Architectural flexibility assessment

**Where the system bends:**
- Profiles + exchange-key-ref + per-profile risk limits already gives a meaningful blast-radius isolation per profile, even on a single exchange account. Three profiles each pointing at a Binance sub-account API key would partially realize the doc's "Isolated Sub-Accounts" model without database changes.
- The strategy node in `pipeline_config` (`libs/core/pipeline_compiler.py`) is one node in a DAG, with other nodes describing gates — so in principle new strategy-class nodes (`funding_arb_eval`, `pairs_eval`, `tri_arb_eval`) could coexist alongside the current `strategy_eval` and the canvas would render them. The compile-to-canonical path would need to widen, but the canvas surface itself does not.
- Indicators are pluggable via `create_indicator_set()` and the `SUPPORTED_INDICATORS` allowlist (`libs/core/schemas.py:386`). Adding new computations is straightforward.

**Where it would break:**
- **The single-direction signal model is hardcoded all the way down.** `SignalDirection` (`libs/core/enums.py:64`) is `BUY | SELL | ABSTAIN`. There is no `BUY_A_SELL_B`, no `OPEN_HEDGED_PAIR`, no `LEG_OF_ATOMIC_GROUP`. `OrderApprovedEvent.side` is a single `OrderSide`. Every downstream consumer (validation, execution, PnL, position-close logic) assumes one symbol, one direction.
- **Per-tick evaluation loop.** `HotPathProcessor.run()` (`services/hot_path/src/processor.py:69-`) consumes `MarketTickEvent`s and evaluates each profile against each tick. Tri-arb needs an order-book-driven loop, not a tick-driven one — and it needs to evaluate the *joint* state of 3 books, not the price of 1 symbol.
- **Order lifecycle is single-shot.** `OrderExecutor.run()` opens a fresh exchange adapter per order (`services/execution/src/executor.py:182, 301`). For tri-arb you'd want a long-lived connection, request pipelining, and probably colocated hosting — none of which the current architecture is set up for.
- **PnL and position model is per-row.** `positions` table has one row per `(profile_id, symbol, side)` (`migrations/versions/001_initial_schema.sql:45-57`). No concept of a "hedged pair position" or "arb-loop fill" that should be PnL-attributed as one unit.

**Verdict:** the system can be *extended* to host these strategies, but it cannot be *configured* to host them. The expressive boundary is in the schemas and event model, not in business logic. Anything that extends those schemas is touching every downstream service.

### 2.3 Systemic risks (precision, latency, data quality, observability, kill-switch coverage)

- **Latency budget for tri-arb is not credible on this stack.** Python asyncio + per-order CCXT adapter recreation + Redis-mediated order pipeline = end-to-end latency well into the tens of milliseconds before the order even reaches the exchange. On Binance Spot, retail tri-arb opportunities have been arbitraged out by colocated bots in single-digit-millisecond windows for years. The doc's framing ("Rust agent constantly monitors three intersecting order books") implicitly acknowledges this — but the Rust agent does not exist; the executor is Python. **This is the single biggest miscalculation in the doc as presented.** See §3.1 for the full critique.
- **Decimal precision is sound for spot.** `CLAUDE.md §2A` and the schemas confirm Decimal usage end-to-end. Perp PnL math (funding accrual, mark-vs-index, liquidation distance) would have to follow the same rule when introduced.
- **Kill switch is binary and global.** `services/hot_path/src/kill_switch.py:34-44` — a single Redis key. The doc's claim that it "revokes all API keys" is wrong; it halts the hot-path consumer loop. The exchange keys remain valid; a bug in the executor that bypassed the kill-switch check could still send orders.
- **No global / portfolio drawdown aggregator exists.** `services/hot_path/src/circuit_breaker.py` operates per-profile (line 10: `check(state: ProfileState)`). The doc's "if global drawdown hits 5%, kill everything" needs a new aggregating service, plus a trigger that calls `KillSwitch.activate`.
- **Reconciliation against the exchange is partial.** `services/execution/src/reconciler.py` exists but does not implement the doc's "state verification — routinely checks actual exchange balances against what the internal database expects." This is essential for the Yield Harvester (funding payments accrue silently on the exchange side) and any leveraged position (liquidation could remove a position without a fill event).

---

## 3. Critical Analysis Findings

The user explicitly asked for vigilance on miscalculations, false assumptions, hallucinations, and bias. The doc is short (60 lines) but carries several.

### 3.1 Miscalculations

- **Triangular arb economics on $5,000 retail capital at Binance Spot are extremely thin.**
  - Retail spot taker fee: 0.10% per leg → 0.30% per loop, before slippage.
  - Typical observable USDT→BTC→ETH→USDT loop edges in normal regimes: low single-digit basis points, rarely exceeding 5 bps for retail-visible windows. Net of fees, the strategy is structurally negative-EV without VIP-tier rebates, BNB-fee discount (which the system does not model), or maker-side execution (FOK is taker-side by definition).
  - The doc's "Risk Guardrail: must use FOK" guarantees the trade either fills entirely or not at all — but it does *not* fix the fee problem. FOK + 0.10% taker × 3 ≥ 30 bps round-trip cost is the floor.
  - Conclusion: the 30–50% APY target attributed to Profile 3 is not supported by the fee/slippage arithmetic on a retail account at the proposed capital. The strategy is plausible at VIP tier with maker rebates and colocated infra; it is implausible on stock CCXT against retail Binance Spot.
- **Funding-rate compounding model is over-precise.** Funding rates are signed and volatile — a "steady baseline yield" framing is optimistic. Sustained periods of negative funding (bear market, basis inversion) flip the strategy from yield-collecting to yield-paying. The Yield Harvester needs a *trigger* (only enter when 30-day-mean funding > some threshold) and a *roll-out* policy (close the position when funding turns persistently negative). The doc presents it as set-and-forget; that is a miscalculation.
- **Position sizing model is misstated.** Profile 2 says "as $5,000 grows to $5,500, the Risk Agent recalculates the 1% maximum exposure, taking slightly larger lot sizes." The current risk service computes `order_value / portfolio_value` against `max_allocation_pct` (`services/risk/src/__init__.py:66-73`) — `max_allocation_pct` defaults to `1.0` (i.e. 100%, not 1%). The doc and the code use the same variable name with two different semantics; reading the doc and then implementing against the code would produce a 100× larger position.

### 3.2 Incorrect assumptions

- **Assumption: "the Python 2nd Brain sweeps profits every week."** No such sweeper exists. There is no scheduler, no Universal-Transfer client, no cross-account balance reconciler. This is the entirety of the compounding mechanism in the doc, and it has zero current implementation.
- **Assumption: "API limits are calculated per sub-account."** This is true on Binance (REST request weight is per-IP and per-key, with sub-account keys carrying separate budgets), but the system's rate limiter (`libs/exchange/_rate_limiter_client.py:49`) keys by `(exchange, profile_id)`. If two profiles share a key (e.g. dev testing), they will share a budget bucket — the limiter cannot tell. Coupling the budget to the API key, not the profile, would be safer.
- **Assumption: "Most crypto exchanges default to One-Way Mode."** True for Binance USDⓈ-M Futures when an account is first opened — but Binance Spot does not have a concept of position netting in the way the doc describes; you simply hold or do not hold a balance. Spot longs and spot shorts (which require margin trading, not vanilla spot) net differently. The position-netting framing conflates spot and perp. For the Yield Harvester (spot long + perp short), there is no netting because they are different markets — the risk is *cross-margin* (next bullet), not netting.
- **Assumption: cross-margin will eat the safe profile.** This is correct *only* if all three profiles share one futures wallet on cross-margin. Isolated-margin mode (which the system doesn't currently set, but Binance supports per-position) prevents cross-contamination without requiring sub-accounts. Sub-accounts are the cleanest answer, but the doc presents them as the *only* answer — they aren't.

### 3.3 Hallucinations (claims that don't match code reality)

- **"The Rust agent constantly monitors three intersecting order books."** There is no Rust code in this repository. `find . -name "*.rs"` returns nothing under `/services`, `/libs`, or the workspace root. The execution stack is all Python. Implementing tri-arb in the current Python+CCXT+Redis stack will not hit the latencies the doc implies. Either the doc is describing a future component, or this is a hallucination.
- **"The engine collects the Funding Rate every 8 hours."** No code collects funding rates. `grep -ri funding` returns zero hits in `/services`, `/libs`, `/migrations`. There is no `funding_payments` table, no funding-rate ingestion job, no scheduled task.
- **"If global drawdown hits a threshold (e.g., 5%), it instantly revokes all API keys."** `KillSwitch.activate` (`services/hot_path/src/kill_switch.py:46-61`) sets one Redis key and writes an audit log entry. It does not call the exchange, does not revoke any keys, and does not aggregate drawdown across profiles. The aggregation logic does not exist.
- **"The Master Account's Universal Transfer API."** No call to `sapi/v1/asset/transfer` or `sapi/v1/sub-account/universalTransfer` exists in `libs/exchange/_binance.py` or anywhere else in the repo.
- **"Routinely checks actual exchange balances against what the internal database expects."** `services/execution/src/reconciler.py` exists, but a read of it (not shown above; see file) shows it reconciles *orders* (pending vs. acknowledged), not *balances*. The balance-reconciliation loop described in the doc is not present.

### 3.4 Bias

- **Survivorship / selection bias in the framing.** The doc presents three "non-correlated" strategies. They are uncorrelated *in their P&L signatures* under benign conditions, but they share several common-mode failure points: same exchange (Binance), same data feed (CCXT WebSocket), same execution stack. A Binance API outage, a CCXT bug, or a Redis stream lag affects all three simultaneously. This is left unsaid.
- **Optimism about implementation effort.** Cash-and-carry, pairs trading, and triangular arb are each individually 1–3 month engineering projects on a stack already designed for them. On this stack — which was not — each is closer to 2–4 months once you include the schema changes, multi-leg execution, perp market plumbing, and the operational maturity to run them safely. The doc implicitly suggests they're configurations of an existing engine; they are not.
- **Confirmation bias toward "institutional best practice."** Sub-accounts are good practice, but the framing presents them as *the* solution to a problem (cross-margin contamination) that has cheaper solutions (isolated-margin mode + per-position margin firewalls). The doc isn't wrong that sub-accounts are best practice — it's wrong that they are the only path.
- **Recency / narrative bias on APY targets.** 30–50% APY is presented as "realistic" without a cost model. On retail Binance Spot with 0.10% fees, the high-turnover legs (tri-arb especially) are structurally unprofitable absent VIP tier and BNB rebate stacking. The system does not yet have the data to back-test this honestly, which the doc does not flag.

---

## 4. Per-Strategy Deep Dives

### 4.1 Profile 1 — Yield Harvester (Cash-and-Carry / Funding Rate Arbitrage)

**What the strategy needs:**
- Spot market access (already present, BTC/USDT) AND perpetual-futures market access (missing).
- The ability to open a long spot position and a short perp position of identical notional, atomically (or with strict drift tolerance).
- Funding-rate ingestion every 8h, persisted per-symbol.
- A funding-payment ledger (perp wallet accrues funding cashflows that must be PnL-attributed correctly — they are NOT realized PnL from a trade fill, they are wallet-level cashflows the executor never sees).
- A weekly compounding job that reads the funding-payment ledger, computes new total notional, scales both legs proportionally.
- An entry/exit policy on funding rate (mean rolling > threshold to enter; mean rolling < negative threshold to exit) — the doc does not describe this but it is necessary for the strategy not to bleed in inverted-funding regimes.

**What we have (with file:line evidence):**
- Spot ingestion for BTC/USDT (`services/ingestion/src/main.py:49`).
- Spot execution via Binance CCXT (`libs/exchange/_binance.py:39`).
- Per-profile risk limits and circuit breaker (`migrations/versions/001_initial_schema.sql:11-26`, `services/hot_path/src/circuit_breaker.py`).
- PnL realization on position close (`services/pnl/src/closer.py`).

**What's missing:**
- Perpetual-futures client construction (separate CCXT instance with `defaultType: 'future'` or a separate `binance_perp` adapter).
- Funding-rate WebSocket / REST poller (`fetchFundingRate`, `fetchFundingRateHistory`).
- A `funding_payments` migration and repository.
- Hedged-pair position model in `positions` table or a `position_groups` parent table.
- A scheduler / scheduled service to run the weekly sweep — there is no cron / scheduler service in the current 19-service set (see `run_all.sh:56`).
- Universal Transfer or balance-rebalancer call.

**Recommended path (sketch):**
1. Add `binance_perp` adapter as a separate `ExchangeAdapter` subclass; add a `MarketType` enum (`SPOT | PERP_USDM | PERP_COINM`) routed via `exchange_key_ref`.
2. Add `funding_payments` table and a 5-min poller; broadcast on a new `pubsub:funding_rate` channel.
3. Add `position_groups` (or `strategies`) parent table; rework `positions` to optionally reference one.
4. Build a dedicated `yield_harvester` service (or a strategy-class node in the canvas) that opens/closes hedged pairs.
5. Add a scheduled service (could be a new microservice, or use an in-process APScheduler) to run weekly compounding.

### 4.2 Profile 2 — Mean Reverter (Cointegrated Pairs Trading)

**What the strategy needs:**
- Cointegration testing pipeline (Engle-Granger or Johansen) run offline on candidate pairs.
- Live monitoring of the price ratio of a cointegrated pair, with a rolling z-score on the ratio.
- An entry trigger when |z| > 2.5 that fires *two* orders: long the loser, short the winner.
- An exit trigger when z reverts to a band around zero that closes both.
- A "broken cointegration" guard — if the spread is trending instead of mean-reverting, exit immediately.
- Position sizing that balances notional across both legs (not just dollar-equal; properly hedge-ratio-weighted).

**What we have:**
- BTC/USDT and ETH/USDT both ingested (`services/ingestion/src/main.py:49`).
- A single-symbol price z-score indicator (`libs/indicators`, see `services/hot_path/src/strategy_eval.py:66`).
- Risk and PnL services that can in principle handle two positions per profile (the model is one row per position, no limit on count up to `MAX_OPEN_POSITIONS_PER_PROFILE = 50`, `services/risk/src/__init__.py:29`).

**What's missing:**
- Cointegration calculation (statsmodels has `coint`; not currently imported anywhere).
- Pair-ratio z-score indicator (the current z-score takes one price stream, not a ratio).
- Multi-symbol simultaneous-evaluation primitive (`HotPathProcessor` evaluates one tick × all profiles; pairs needs a joined stream of two symbols' ticks).
- Pair-order primitive: `OrderApprovedEvent` has one symbol/side, no concept of a sibling leg.
- Hedge-ratio sizing math.
- Pair-exit logic (the existing `exit_monitor`, `services/pnl/src/exit_monitor.py`, exits one position based on its own PnL, not a paired position based on z-score).

**Recommended path:**
1. Add a `pair_definitions` table (symbol_a, symbol_b, hedge_ratio, lookback_window, z_entry, z_exit, validated_at).
2. Add an offline cointegration job (could be a scheduled task or part of the analyst service) that maintains `pair_definitions`.
3. Add a new strategy-class node `pairs_eval` in the canvas, plus a backing pipeline-compiler rule.
4. Extend `OrderApprovedEvent` with `leg_group_id` and `leg_index`; the executor publishes them atomically (parallel `place_order`).
5. Pair-exit monitor: a new component watching live z-scores and closing both legs when in-band, OR when stop-loss on the pair as a unit trips.

### 4.3 Profile 3 — Latency Exploiter (Triangular Arbitrage)

**What the strategy needs:**
- Three-symbol joined order-book monitoring (e.g. BTC/USDT, ETH/USDT, ETH/BTC) at top-of-book.
- Profit calculation per opportunity, net of fees, with a configurable minimum-profit threshold.
- Three FOK orders dispatched in parallel; the FOK guarantees that if any leg can't fill at its quoted price, the whole sequence cancels (the doc explicitly relies on this).
- End-to-end submission latency under the half-life of the opportunity — realistically single-digit ms to ~20ms on retail Binance for the marginal opportunities that survive bot competition.
- A circuit breaker that pauses the strategy if its hit rate degrades or if any leg fails to FOK (suggesting toxic flow or stale book reads).

**What we have:**
- Order-book streaming for BTC/USDT and ETH/USDT (`libs/exchange/_binance.py:139-184`).
- A `pubsub:orderbook` broadcast channel (`libs/messaging/channels.py:26`).
- An execution path that goes through Redis Streams → validation → execution → CCXT.

**What's missing:**
- A third symbol in the ingestion list (`services/ingestion/src/main.py:49` only tracks two — adding `ETH/BTC` is a one-line change, but the architecture has no test for whether triangular profitability can be computed at the latency required).
- FOK order type at the adapter (`libs/exchange/_binance.py:241` hardcodes limit).
- Atomic 3-leg execution orchestrator. The current order pipeline (`strategy → orders stream → validation → execution`) adds at least one round-trip through Redis per order. For tri-arb that's ~3× the round-trips, on the critical path. Three legs through this pipeline will not race the market.
- "Rust agent" — does not exist (see §3.3).
- Per-leg failure rollback. If leg 1 fills and leg 2 doesn't (impossible if all are FOK and submitted atomically, but possible if they're submitted serially or if FOK isn't actually FOK), the strategy needs to flatten leg 1 immediately. The current executor has no such reverse-trade logic.

**Recommended path:**
1. **Re-evaluate feasibility first.** Before any code is written, run a 7-day shadow capture against Binance to measure (a) how often a 3-leg loop offers ≥ 30 bps net of fees and (b) the half-life of those opportunities. If the answer is "rarely and milliseconds," the strategy as specified is not viable on this stack and the recommendation is to defer or descope it.
2. If feasibility check passes: build a dedicated `tri_arb` service that bypasses the Redis-mediated order pipeline and calls CCXT directly. Accept that this is a special-case strategy with its own architecture.
3. Add `OrderType.FOK` to enums; extend adapter `place_order` to honor it.
4. Maintain a single long-lived CCXT instance per arb worker (not per-order) to amortize HTTP/2 handshake and signing overhead.

### 4.4 Architecture — Isolated Sub-Accounts + Global Risk Agent

**What the architecture needs:**
- One master account, three sub-accounts, four sets of API keys.
- Per-sub-account balance and PnL views.
- Universal Transfer between sub-accounts.
- A global drawdown computation that aggregates equity across all sub-accounts and trips the kill switch at a threshold.
- A kill-switch action that *actually disables trading at the API layer* (revokes or rotates keys), not just halts the consumer loop.
- Per-key rate-limit accounting (Binance enforces these per-key, so the system's rate limiter should match).

**What we have:**
- One-key-per-profile via `trading_profiles.exchange_key_ref` (`migrations/versions/001_initial_schema.sql:20`).
- Per-profile encrypted credential storage (`libs/core/secrets.py`).
- Per-profile circuit breaker (`services/hot_path/src/circuit_breaker.py`).
- Global kill switch (binary, `services/hot_path/src/kill_switch.py`).
- Per-(exchange, profile) rate-limit bucket (`libs/exchange/_rate_limiter_client.py:49`).
- HITL escalation gate (`services/hot_path/src/hitl_gate.py`).

**What's missing:**
- An explicit `accounts` or `sub_accounts` table separate from `exchange_keys`. Today the `exchange_keys` table (`migrations/versions/006_users_and_exchange_keys.sql:27-39`) has no notion of "sub-account-of-master."
- Universal Transfer API call in the Binance adapter.
- Global drawdown aggregator service or job. Per-profile drawdown is tracked (`services/pnl/src/publisher.py:75-86`); none of it is summed across profiles.
- Auto-trip of `KillSwitch.activate` on aggregated drawdown crossing.
- Key-revocation or key-rotation API integration.

**Recommended path:**
1. Add an `accounts` table linking `(user_id, exchange_id, account_kind: master|sub, parent_account_id, label)` and migrate `exchange_keys` to reference an account.
2. Add a "Portfolio Risk" microservice (or job inside the existing risk service) that subscribes to `pubsub:pnl_updates`, aggregates per-profile drawdown into a portfolio drawdown, and calls `KillSwitch.activate` on threshold breach.
3. Add `transfer_between_accounts` to `ExchangeAdapter` ABC and implement on the Binance adapter.
4. (Optional, defensible-without-it for v1) Implement key-revocation. Until then, document explicitly that the kill switch is in-band only and that a rogue executor that bypasses it could still trade — and add a defense-in-depth check inside `OrderExecutor.run()` as well as the hot-path loop.

---

## 5. Gap Matrix (Appendix)

| # | Strategy | Capability Needed | What We Have (file:line) | Gap | Severity | Effort | Blocks Other? |
|---|---|---|---|---|---|---|---|
| 1 | Yield Harvester | Spot + perp atomic open/close | Spot only (`libs/exchange/_binance.py:39`) | No perp client, no atomic multi-leg events | Blocker | Large | Yes — Mean Rev capital efficiency |
| 2 | Yield Harvester | Funding-rate ingestion | None (zero grep hits) | Build poller + table + pubsub | Blocker | Medium | No |
| 3 | Yield Harvester | Weekly compounding sweep | None | Build scheduler + Universal Transfer | Blocker | Medium | Yes — architecture |
| 4 | Yield Harvester | Funding-payment PnL attribution | Per-fill PnL only (`services/pnl/src/calculator.py`) | Cashflow ledger separate from fills | Major | Medium | No |
| 5 | Yield Harvester | Funding-rate entry/exit policy | None | Strategy-class node | Major | Small | No |
| 6 | Yield Harvester | Hedged-pair position model | One row per position (`migrations/versions/001_initial_schema.sql:45`) | `position_groups` parent or `pair_id` column | Major | Small | Yes — Mean Rev |
| 7 | Yield Harvester | Reduce-only / post-only flags | No order-type plumbing (`libs/exchange/_base.py:78`) | Extend signature, enums, events | Blocker | Medium | Yes — Tri-arb |
| 8 | Yield Harvester | Isolated-margin mode setter | None | Adapter method | Minor | Small | No |
| 9 | Yield Harvester | Exchange-balance reconciliation | Order reconciler only (`services/execution/src/reconciler.py`) | Balance reconciler | Minor | Small | Yes — all strategies |
| 10 | Mean Reverter | Cointegration test pipeline | None | statsmodels offline job + table | Blocker | Medium | No |
| 11 | Mean Reverter | Pair-ratio z-score | Single-symbol z-score (`libs/indicators`) | New indicator over a stream of ratios | Blocker | Small | No |
| 12 | Mean Reverter | Multi-symbol joined evaluation | Single-symbol per tick (`services/hot_path/src/processor.py:86-`) | Joint-tick assembly + pair-state cache | Blocker | Medium | Yes — Tri-arb |
| 13 | Mean Reverter | Paired-order primitive | Single-leg events (`libs/core/schemas.py:88-115`) | `leg_group_id` in events | Blocker | Medium | Yes — Yield Harvester, Tri-arb |
| 14 | Mean Reverter | Pair-exit on z-revert | Single-position exit (`services/pnl/src/exit_monitor.py`) | Pair-aware exit watcher | Major | Small | No |
| 15 | Mean Reverter | Hedge-ratio sizing | Naive notional sizing (`services/risk/src/__init__.py:66-73`) | Ratio-weighted sizing | Major | Small | No |
| 16 | Mean Reverter | Broken-cointegration guard | None | Trend-detector + auto-exit | Major | Small | No |
| 17 | Latency Exploiter | FOK order type | Hardcoded limit (`libs/exchange/_binance.py:241`) | Order-type enum + plumbing | Blocker | Small | Yes — risk profile of all strategies |
| 18 | Latency Exploiter | 3-symbol orderbook | 2 symbols (`services/ingestion/src/main.py:49`) | Add ETH/BTC + 3rd channel | Blocker | Trivial | No |
| 19 | Latency Exploiter | Atomic 3-leg execution | Single-order pipeline (`services/execution/src/executor.py`) | Bypass Redis, direct-CCXT arb worker | Blocker | Large | No |
| 20 | Latency Exploiter | Sub-10ms order submission | ~50–200ms via Redis + CCXT recreation | Long-lived adapter + colocated host | Blocker | Large | No |
| 21 | Latency Exploiter | Reverse-trade rollback on partial fill | None | Compensating-trade logic | Major | Small | No |
| 22 | Latency Exploiter | Opportunity-detection latency | Per-tick processor (`processor.py:69`) | Order-book-driven worker | Major | Medium | No |
| 23 | Latency Exploiter | Hit-rate / staleness detector | None | Self-disabling circuit breaker | Major | Small | No |
| 24 | Latency Exploiter | Rust-tier execution path | Python only | Either accept Python latency floor or write Rust agent | Blocker | XL | No |
| 25 | Architecture | Sub-account model in DB | `exchange_keys` only (`migrations/versions/006_users_and_exchange_keys.sql`) | `accounts` table + FK | Blocker | Small | Yes — all |
| 26 | Architecture | Universal Transfer API | None | Adapter method + scheduled rebalancer | Blocker | Small | Yes — Yield Harvester |
| 27 | Architecture | Global drawdown aggregator | Per-profile only (`services/pnl/src/publisher.py:75-86`) | New aggregator service / job | Blocker | Small | No |
| 28 | Architecture | Auto-trip of kill switch | Manual / Redis SET only (`kill_switch.py:46`) | Wire aggregator → activate() | Blocker | Trivial | No |
| 29 | Architecture | Per-key (not per-profile) rate limit | Per-(exchange, profile) (`_rate_limiter_client.py:49`) | Key the bucket on key-id | Major | Trivial | No |
| 30 | Architecture | API-key revocation on kill | Halts loop only (`kill_switch.py:34-44`) | Call exchange key-mgmt API (Binance supports limited revocation) | Major | Small | No |
| 31 | Architecture | Order-pipeline kill-switch check | One check at top of hot_path loop (`processor.py:80`) | Second check inside `OrderExecutor` for defense in depth | Major | Trivial | No |
| 32 | Architecture | Balance reconciliation against exchange | Order reconciler only | Periodic balance compare + alert | Major | Small | Yes — Yield Harvester |
| 33 | Architecture | Scheduled-jobs framework | None (no cron in `run_all.sh`) | Lightweight scheduler service or APScheduler in an existing one | Major | Small | Yes — Yield Harvester, cointegration job |
| 34 | Cross | Decimal precision in new perp PnL | Existing pattern in `libs/core/types.py` | Apply same pattern when adding funding ledger | Minor | Trivial | No |
| 35 | Cross | Strategy-class node type system | Single `strategy_eval` node (`libs/core/pipeline_compiler.py`) | Generalize compiler to multiple node types | Minor | Medium | Yes — all three strategies as canvas-saveable |
| 36 | Cross | Backtest framework for these strategies | Backtester targets single-symbol rules (`services/backtesting`) | Multi-leg backtester | Minor | Medium | No |

**Effort key:** Trivial = <1 day, Small = 1–5 days, Medium = 1–3 weeks, Large = 3–8 weeks, XL = >2 months.

---

## 6. Recommended Sequencing

Most leverage first. Each phase unblocks the next.

### Phase A — Schema and primitives (unblocks ≥80% of downstream work)

1. Add order-type enums (`OrderType`, `TimeInForce`, `MarginMode`, `MarketType`) to `libs/core/enums.py`.
2. Extend `ExchangeAdapter.place_order` signature and `OrderApprovedEvent` / `OrderExecutedEvent` schemas to carry `order_type`, `time_in_force`, `leg_group_id`, `leg_index`.
3. Wire through `OrderExecutor` and the Binance adapter. Default behavior unchanged for existing profiles.
4. Add `accounts` table and migrate `exchange_keys` to reference an account row. Add `market_type` to accounts.
5. Implement `transfer_between_accounts` on the Binance adapter (Universal Transfer).

*Outcome: every strategy below becomes implementable on top of this foundation; no later step requires re-touching these schemas.*

### Phase B — Risk and operational maturity (do this before any new strategy goes live)

6. Build a Portfolio Risk aggregator that consumes `pubsub:pnl_updates`, sums drawdown across profiles, and calls `KillSwitch.activate` on threshold.
7. Add a defense-in-depth kill-switch check inside `OrderExecutor.run()`.
8. Build a periodic balance-reconciler that compares exchange balances vs. internal ledger and emits `SYSTEM_ALERT` on drift > threshold.
9. Add a scheduled-jobs service (or APScheduler inside an existing service) to host (a) weekly compounding sweeps, (b) cointegration recompute, (c) balance reconciliation, (d) funding-rate poller.

*Outcome: the safety perimeter is in place. New strategies can be deployed without operational risk increasing super-linearly.*

### Phase C — Yield Harvester (best risk-adjusted return per unit of build effort)

10. Add a Binance USDⓈ-M perp adapter (separate class; new `MarketType.PERP_USDM`).
11. Add funding-rate ingestion + `funding_payments` table + `funding_payments_repository`.
12. Add `position_groups` table; add a `pair_id` column to `positions`.
13. Build a `yield_harvester` strategy-class node (entry/exit on funding-rate trigger) OR a dedicated `yield_harvester` service.
14. Wire the weekly compounding sweep into the scheduled-jobs service.

*Outcome: Profile 1 live. This is the strategy with the cleanest expected value on retail tier and the highest probability of generating real revenue while Profiles 2 and 3 are being built.*

### Phase D — Mean Reverter (second-best risk-adjusted return)

15. Add cointegration test pipeline (statsmodels) and `pair_definitions` table.
16. Add pair-ratio z-score indicator and a multi-symbol joined-evaluation primitive.
17. Add `pairs_eval` strategy-class node.
18. Add pair-aware exit monitor.

*Outcome: Profile 2 live. Capital-efficient on perps if Phase C exposed perp infra cleanly.*

### Phase E — Latency Exploiter (defer until A–D are stable; reassess feasibility before committing engineering)

19. **Feasibility study first.** Run 7-day shadow capture against Binance and measure how many net-positive triangular loops actually exist at this fee tier, and their half-life. If the answer is "few and microseconds," cut the project.
20. If feasibility check passes: build a dedicated `tri_arb` worker that bypasses Redis and uses a long-lived adapter; add FOK support.
21. Optionally write the latency-critical loop in Rust. This is a significant scope expansion (new toolchain, new build step, new operational ownership) and should be weighed against just descoping the strategy.

*Outcome: Profile 3 live OR explicitly descoped with documented reasoning. Either is fine.*

### What to defer indefinitely (unless a strategy compels it)

- Real-time exchange key rotation / programmatic key revocation. The kill switch + defense-in-depth check inside the executor covers the same threat model at lower complexity.
- Multi-exchange tri-arb. Cross-exchange triangular arb adds withdrawal latency and float-management complexity. Not worth it for the proposed capital size.

---

## 7. Open Questions for the User

These are points where the doc is silent and where assumption-making would materially shape the design. Worth answering before Phase A starts.

1. **Tier.** Is the target user retail-tier on Binance (0.10% taker, no rebates) or VIP-tier? The economics of Profile 3 depend on this materially.
2. **Capital.** Is $5,000 per sleeve the actual starting capital, or a placeholder? On $5k, fixed fees per leg matter much more than they would on $50k.
3. **Exchange.** Binance only, or multi-exchange? Sub-account behavior, funding-rate semantics, and Universal-Transfer APIs all vary by exchange.
4. **Live or paper first.** Is the intent to ship to paper/testnet first (current code path supports this via `PAPER_TRADING_MODE`), or directly to live? This changes the operational-maturity bar.
5. **Latency tolerance.** Is the user willing to accept "Python-tier" latency for tri-arb (i.e., it will only capture the longer-lived, lower-EV opportunities) or is the target the same single-digit-ms window real arb desks fight over (which implies Rust + colo + significantly more spend)?
6. **30–50% APY target.** Is this a hard requirement, or an aspirational anchor? If hard, Profile 3 likely needs to be replaced by something more profitable on retail-tier infra. If aspirational, the safer phasing is A → B → C → D and treat Phase E as exploratory.
