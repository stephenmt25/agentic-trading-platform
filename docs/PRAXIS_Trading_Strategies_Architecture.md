# PRAXIS - Tier 2 Trading Strategies & Architecture

## The 3-Profile Parallel Architecture
Running three non-correlated, mathematically isolated strategies in parallel is exactly how quantitative hedge funds operate. By splitting a $15,000 starting fund into three $5,000 profiles (or "sleeves"), you create a robust ecosystem. If one strategy experiences a flat month or a minor drawdown, the other two continue to pull the portfolio forward.

### Profile 1: The Yield Harvester (Cash and Carry Arbitrage)
* **The Mandate:** Generate steady, baseline yield completely immune to price action.
* **The Setup:** The $5,000 is split. $2,500 buys a spot asset (e.g., BTC), and $2,500 shorts the exact same asset on the Perpetual Futures market.
* **The Execution:** The engine collects the Funding Rate every 8 hours.
* **How to Compound for 1 Year:** As funding rate profits accrue in your futures wallet, the Python 2nd Brain sweeps those profits every week. It automatically calculates the new total balance, buys slightly more spot BTC, and proportionally increases the short position.

### Profile 2: The Mean Reverter (Statistical Arbitrage / Pairs Trading)
* **The Mandate:** Profit from market volatility and chaos without taking a directional stance.
* **The Setup:** The $5,000 is deployed to monitor cointegrated pairs (like BTC/ETH).
* **The Execution:** When the price ratio diverges past a 2.5 Z-score, the engine shorts the winner and longs the loser. When the ratio snaps back to the mean, it closes both for a profit.
* **How to Compound for 1 Year:** Reinvestment alters Position Sizing. As the $5,000 grows to $5,500, the Risk Agent recalculates the 1% maximum exposure, taking slightly larger lot sizes on the next rubber-band snap.

### Profile 3: The Latency Exploiter (Triangular Arbitrage)
* **The Mandate:** Capture micro-profits from order book imbalances before the exchange's internal servers can correct them.
* **The Setup:** You stay entirely in cash (e.g., USDT) until the exact millisecond an opportunity strikes.
* **The Execution:** The Rust agent constantly monitors three intersecting order books simultaneously (e.g., Sell USDT for BTC -> Sell BTC for ETH -> Sell ETH for USDT). If the loop yields a net profit after fees, it fires all three orders instantly.
* **The Risk Guardrail:** You must use FOK (Fill or Kill) orders to guarantee all three trades execute perfectly, or the exchange cancels the entire sequence.
* **How to Compound for 1 Year:** Profits scale linearly with capital size. With zero overnight risk, the engine uses the new, larger stablecoin balance for the next triangular loop.

### The 1-Year Realistic Projection
* **The Baseline (Profile 1):** Provides the safety net, steadily grinding upward via funding rates.
* **The Alpha (Profiles 2 & 3):** Provides outsized returns during high volatility and panic.
* **The Psychological Edge:** Delta-neutral and FOK latency strategies mean you don't care about market direction or crashes.
* **Target:** A realistic target for this multi-strat approach is 30% to 50% APY.

---

## Institutional Best Practice: The Sub-Account Architecture
Executing all three strategies out of one master account is a massive architectural trap. A live, high-volatility environment will almost certainly cause strategies to cannibalize each other.

### Poking Holes in the Single Master Account
1.  **The Position Netting Nightmare:** Most crypto exchanges default to "One-Way Mode." If Profile 1 shorts 1 BTC and Profile 2 longs 1 BTC, the exchange nets your position to zero. When agents try to close trades, APIs throw errors and the system crashes.
2.  **Margin Cross-Contamination:** If the Tri-Arb bot experiences a flash crash, it will eat into the cross-margin protecting your Yield Harvester. The exchange will auto-liquidate "safe" positions to cover the losses.
3.  **API Rate Limit Cannibalization:** Triangular Arbitrage requires immense API throughput. Sharing keys will chew through rate limits, preventing other profiles from executing trades due to `HTTP 429: Too Many Requests` errors.
4.  **The Blast Radius:** An AI-generated logic bug in one profile could rapidly buy/sell until fees drain the entire unified master account balance.

### The Realistic Best Practice: Isolated Sub-Accounts
Every institutional quant desk uses a Sub-Account structure. Major exchanges allow isolated sub-accounts under a main master account, specifically designed for API trading.

* **Master Account:** Holds $0. Used only for login, security (2FA), and viewing the global dashboard.
* **Sub-Account 1 (Yield Harvester):** Funded with exactly $5,000. Has its own dedicated API keys.
* **Sub-Account 2 (Mean Reverter):** Funded with exactly $5,000. Has its own dedicated API keys.
* **Sub-Account 3 (Triangular Arb):** Funded with exactly $5,000. Has its own dedicated API keys.

**Why this solves the problems:**
* **True Isolation:** Profile 1 can short while Profile 2 longs without netting issues.
* **Margin Firewalls:** Maximum loss for a rogue bot is mathematically hard-capped to its specific $5,000 allocation.
* **Dedicated Rate Limits:** API limits are calculated per sub-account, giving each bot its own dedicated highway.

### Redefining Your Centralized Risk Agent
The Python Risk Agent should act as a Global Portfolio Manager sitting above the execution agents:
1.  **The Global Kill Switch:** Monitors equity of all three sub-accounts via WebSocket. If global drawdown hits a threshold (e.g., 5%), it instantly revokes all API keys to kill the engine.
2.  **Automated Rebalancing (The Compounder):** At the end of the week, it uses the Master Account's Universal Transfer API to sweep funds, rebalancing each sub-account to its new compounded baseline.
3.  **State Verification:** Routinely checks actual exchange balances against what the internal database expects, ensuring logs haven't drifted from reality.
