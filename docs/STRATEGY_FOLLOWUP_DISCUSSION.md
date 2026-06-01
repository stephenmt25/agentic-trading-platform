# Strategy Gap Analysis — Follow-up Discussion

> Companion to `STRATEGY_GAP_ANALYSIS.md`. Three questions raised after partner review of the gap analysis PDF.

These are good strategic questions. I'll be honest where I can be and explicit about what we don't know. None of this is a recommendation to deploy capital — it's framing the tradeoffs.

---

## Q1 — Separate engine for HFT?

The three strategies in the doc are bundled together but have **fundamentally different latency budgets**, and that should drive the answer:

| Strategy | Latency budget | Fits current Praxis? |
|---|---|---|
| Yield Harvester (funding-rate arb) | Seconds–minutes (funding cycles are 8h) | **Yes, with additions** — needs futures connector, funding-rate ingestion, sub-account model. Not a new engine. |
| Mean Reverter (cointegrated pairs) | Seconds | **Yes, with additions** — needs multi-leg orders + cointegration analytics. Not a new engine. |
| Latency Exploiter (triangular arb) | Sub-millisecond | **No.** Python + Redis + FastAPI + Decimal + validation HTTP hop = ~10–50ms floor. You can't fix this without rewriting the hot path. |

**Recommendation:** Don't build "one HFT engine." Build along latency lines:

1. **Extend Praxis** for Yield Harvester + Mean Reverter — these align with the existing architecture's strengths (correctness, observability, profile model). The gap analysis already lists the work: multi-leg schema, futures adapter, funding-rate ingestion, global risk aggregator.
2. **Separate engine for Latency Exploiter** if you want it at all — Rust or C++, direct WebSocket fan-out (no Redis hop), co-located with the exchange. This is a 3–6 month build from scratch and is **not worth it at retail fee tiers** (see Q2). I'd table it until you qualify for VIP fee discounts.

The doc's mistake was treating these as one category. They aren't.

---

## Q2 — $10k profitability (current vs HFT-capable)

I have to flag upfront: **I cannot tell you what you'll make.** There's no live P&L track record I've seen on Praxis, and any specific number I give would be invention. What I can give you is the math on what's *possible*, what's *typical*, and what's *eaten by costs*.

### Cost floor on $10k at Binance retail (0.10% taker each side)

- Round-trip cost: 0.20% per trade = $20 per full round-trip on $10k
- 10 trades/day → $200/day cost = $73k/year cost drag (730% of capital)
- A high-frequency strategy on $10k is almost mathematically guaranteed to lose to fees alone

### Realistic ranges (industry context, not Praxis-specific)

| Strategy class | Typical annualized (when working) | $10k notional |
|---|---|---|
| Spot momentum / threshold (current Praxis) | -30% to +30% — wide variance, most retail algo systems lose money | -$3k to +$3k, leaning negative |
| Yield Harvester (funding arb) | +3% to +8% post-2024 (compressed by crowding) | +$300 to +$800/year, capital-split across two legs |
| Mean Reverter (pairs) | +5% to +15% in a good regime, can be negative for months | +$500 to +$1,500/year if it works |
| Latency Exploiter (retail tier) | **Negative EV** — 3 legs × 0.10% = 30 bps cost, observed spreads <20 bps | Net loss |

### The honest summary

At $10k, the math gets ugly. Funding arb has to split $5k spot + $5k futures, so you're really running a ~$5k position. Triangular arb is mathematically losing money before slippage. Mean reversion needs months of capital lock-up through drawdowns. The current Praxis system has no proven edge yet — I'd treat it as a research platform, not an income source, until you have at least 90 days of live paper-trading P&L with realistic slippage.

### Cloud vs local

- **For current Praxis (medium frequency):** Cloud adds reliability (no home-internet outages during a market move) but no real edge. Cost: $50–200/month = 6–24% annual drag on $10k. **Verdict:** stay local unless you've had an outage that cost you real money.
- **For Yield Harvester / Mean Reverter:** Same — latency doesn't matter at their cadence.
- **For Latency Exploiter:** Cloud is mandatory and even cloud isn't enough — you'd need AWS Tokyo (Binance's region) at minimum, ideally co-located. But see above: it's negative-EV at retail anyway.

---

## Q3 — Probability of 1% profit over multiple timelines

This is the question I can answer the least precisely, because **probability requires a backtest or live track record, and I haven't seen one for Praxis.** What I can give you is reference points:

- **1% in 1 day on $10k = $100.** BTC moves >1% on roughly 60% of days. Whether you capture it depends entirely on strategy quality. A random coin-flip strategy gets close to 50% (minus fees).
- **1% in 1 week.** Most working long-bias strategies hit this; most losing strategies still hit it sometimes by luck.
- **1% in 1 month.** Low bar. ~12% annualized is reasonable for a working algorithm.
- **1% in 1 year.** Achievable but ~50% of retail algos fail to clear this after costs.

### What I'd actually do before believing any probability number

1. Paper-trade the current Praxis for 60–90 days against live market data with realistic slippage/fee assumptions.
2. Run backtests on the same period with the same parameters and check whether paper-trade P&L matches backtest P&L (it usually doesn't — this delta is the model error).
3. *Then* you have an empirical distribution of returns and can answer "P(1% in N days)" honestly.

Without that, anyone (me included) giving you a probability is making it up.

---

## Productive next steps

1. **Stand up a paper-trading harness** on the current Praxis and let it run for 60 days — this gives you a real P&L distribution before you decide whether to invest in HFT-capable infrastructure.
2. **Pick one strategy** from the doc to pursue — I'd suggest Yield Harvester since it's the most realistic at $10k scale and fits the current architecture with the smallest delta. The gap-analysis Phase A work feeds straight into it.
3. **Drop Latency Exploiter** from consideration unless you're prepared to fund a separate engine *and* get to VIP fee tier.
