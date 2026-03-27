# Glossary and Domain Model

> Canonical definitions for trading terms, technical indicators, market regimes, and
> system-specific concepts used throughout the Praxis Trading Platform codebase.

---

## Trading Domain Terms

| Term | Definition |
|------|------------|
| **Signal** | A trading recommendation emitted by the strategy engine. Contains a direction (`BUY`, `SELL`, or `ABSTAIN`) and a confidence score in the range `[0.0, 1.0]`. Signals flow through the hot-path processor before reaching execution. |
| **Position** | An open holding tracked by the system. Records entry price, quantity, accumulated fees, and unrealized P&L. A position is opened on fill confirmation and closed when quantity reaches zero. |
| **Fill** | Exchange confirmation that an order has been executed. Contains the actual fill price, filled quantity, fee amount, and timestamp. Fills may arrive as partial fills over multiple messages. |
| **Slippage** | The difference between the expected execution price and the actual fill price. In live trading, slippage arises from orderbook movement between signal and fill. In backtesting, slippage is simulated using a configurable model. |
| **Spread** | The difference between the best bid (highest buy) and best ask (lowest sell) prices on an exchange. Tighter spreads indicate higher liquidity. |
| **Orderbook Depth** | The available liquidity at each price level on both bid and ask sides of the orderbook. Depth determines how much volume can be traded before moving the price. |
| **TWAP** | Time-Weighted Average Price. An execution algorithm that splits a large order into equal-sized slices executed at regular intervals to minimize market impact. |
| **VWAP** | Volume-Weighted Average Price. The average price weighted by volume traded at each price level. Used both as a benchmark and as an execution algorithm. |
| **OHLCV** | Open, High, Low, Close, Volume. The standard candlestick data format representing price action over a fixed time interval. All market data ingestion normalizes to OHLCV before storage. |
| **Hypertable** | A TimescaleDB time-partitioned table optimized for efficient time-series queries. The `candles` table is the primary hypertable, partitioned by timestamp for fast range scans. |
| **Taker Rate** | The exchange fee charged for market orders that remove liquidity from the orderbook (as opposed to maker orders that add liquidity). Expressed as a decimal fraction (e.g., `0.001` = 0.1%). |
| **Cost Basis** | The total cost of entering a position, calculated as `entry_price * quantity + fees`. Used as the denominator when computing realized and unrealized P&L. |
| **Drawdown** | The peak-to-trough decline in portfolio value, expressed as a percentage. Maximum drawdown is a key risk metric tracked by the circuit breaker. |
| **Sharpe Ratio** | A risk-adjusted return metric calculated as `mean(returns) / std(returns)`. Higher values indicate better risk-adjusted performance. Annualized by multiplying by `sqrt(252)` for daily returns. |
| **Circuit Breaker** | A safety mechanism that halts all trading activity for a profile when daily realized P&L exceeds `circuit_breaker_daily_loss_pct` (default 2%). Automatically resets at UTC midnight (new trading day). See `services/hot_path/src/circuit_breaker.py`. |
| **Paper Trading** | Simulated trading executed against a testnet with real market data but no real capital at risk. Used for strategy validation before live deployment. |
| **Testnet** | An exchange sandbox environment that mirrors production APIs but uses fake funds. Binance Testnet and Coinbase Sandbox are the supported testnets. |

---

## Technical Indicators

| Indicator | Full Name | Description | Default Parameters |
|-----------|-----------|-------------|--------------------|
| **RSI** | Relative Strength Index | Momentum oscillator measuring the speed and magnitude of price changes. Values range from 0 to 100. Readings below 30 indicate oversold conditions; readings above 70 indicate overbought conditions. | Period: 14 |
| **MACD** | Moving Average Convergence Divergence | Trend-following indicator derived from the difference between two EMAs. A signal line (EMA of the MACD) generates crossover signals. Positive MACD histogram indicates bullish momentum. | Fast: 12, Slow: 26, Signal: 9 |
| **EMA** | Exponential Moving Average | A weighted moving average that assigns exponentially decreasing weights to older observations. Reacts faster to recent price changes than a simple moving average (SMA). | Configurable per strategy |
| **ATR** | Average True Range | Volatility indicator that measures the average range of price movement over a period. True range accounts for gaps by including the previous close. Used for position sizing and stop-loss placement. | Period: 14 |
| **Confluence** | *(composite)* | The alignment of multiple indicators or timeframes signaling the same direction. A confluence score increases signal confidence when RSI, MACD, and regime analysis agree. | N/A |

---

## Market Regimes

The regime classifier assigns one of the following labels to the current market state. Regime
determines which strategy rules activate and how signal confidence is dampened.

| Regime | Description | Trading Behavior |
|--------|-------------|------------------|
| `TRENDING_UP` | Sustained upward price movement confirmed by EMA alignment and positive MACD. | Full signal confidence. Long signals favored. |
| `TRENDING_DOWN` | Sustained downward price movement confirmed by EMA alignment and negative MACD. | Full signal confidence. Short signals favored. |
| `RANGE_BOUND` | Price oscillating within a defined support/resistance range. No clear directional trend. | Reduced confidence. Mean-reversion strategies preferred. |
| `HIGH_VOLATILITY` | Large price swings without clear directional trend. ATR significantly above historical average. | Confidence dampened. Position sizes reduced. |
| `CRISIS` | Extreme market conditions detected. May be triggered by exchange outages, flash crashes, or external events. | **All trading halted.** Equivalent to a circuit breaker trip. |

---

## System-Specific Terms

| Term | Definition |
|------|------------|
| **Hot-Path** | The ultra-low-latency signal processing pipeline with a 50ms end-to-end target. Receives signals from Redis, applies the fast gate and risk gate, and dispatches to execution. Runs as a dedicated asyncio process. |
| **Fast Gate** | A synchronous validation checkpoint within the hot-path. Must complete within 50ms. Runs CHECK_1 (strategy RSI recheck) and CHECK_6 (risk level validation) in parallel. Signals that fail the fast gate are rejected immediately. See `services/validation/src/fast_gate.py`. |
| **Async Audit** | Background validation that runs CHECK_2 through CHECK_5 after the signal has already been dispatched for execution. Failures in async audit trigger order cancellation if the order has not yet filled. |
| **Regime Dampener** | A dual-source regime classification system combining a rule-based classifier and a Hidden Markov Model (HMM). Outputs a regime label and a dampening factor applied to signal confidence before execution. |
| **Agent Modifier** | An additive confidence adjustment applied by analysis agents. The Technical Analysis (TA) agent contributes up to +/-20 percentage points; the Sentiment agent contributes up to +/-15 percentage points. |
| **Optimistic Ledger** | A tentative order state tracker that records order intent before exchange confirmation. Allows the system to account for in-flight orders in risk calculations. Reconciled against actual fills asynchronously. |
| **Strategy Hydration** | The process of pre-warming indicator states from historical candles on startup. Ensures that indicators like EMA and RSI have sufficient history to produce valid values before the first live signal. |
| **Profile** | A user-defined trading configuration containing strategy rules (as JSON), risk limits (max drawdown, position size, stop-loss), symbol blacklists, and exchange key references. Stored in the `trading_profiles` table. See `migrations/versions/001_initial_schema.sql`. |
| **Threshold Proximity** | An event fired when a technical indicator approaches its trigger threshold. Used to pre-fetch orderbook data and pre-warm execution paths before a signal is generated, reducing hot-path latency. |
| **Dead Letter Queue (DLQ)** | A Redis stream (`stream:dlq`) that captures events which failed processing after all retry attempts. DLQ entries include the original event payload, error details, and failure timestamp for manual investigation. |
| **Monotonic ID** | A UUID generator that combines the process ID with an atomic counter to produce unique identifiers without the syscall overhead of `uuid4()`. Used in the hot-path where nanoseconds matter. |
| **Halt Key** | A Redis key (`halt:{profile_id}`) set by CHECK_5 escalation with a 24-hour TTL. When present, the Risk Service blocks all orders for that profile. See `services/validation/src/check_5_escalation.py`. |
| **Consumer Group** | A Redis Streams concept that allows multiple consumers to share work from a single stream. Each message is delivered to exactly one consumer within a group. Used by Hot-Path (`hotpath_engine`) and Execution (`execution_group`). |
| **Wash Sale** | A US tax concept where selling a security at a loss and repurchasing within 30 days disallows the loss deduction. Referenced in the Tax service for US tax calculations. See `services/tax/src/us_tax.py`. |

---

## Acronyms

| Acronym | Expansion |
|---------|-----------|
| API | Application Programming Interface |
| ATR | Average True Range |
| CCXT | CryptoCurrency eXchange Trading (library) |
| CI/CD | Continuous Integration / Continuous Deployment |
| CORS | Cross-Origin Resource Sharing |
| DLQ | Dead Letter Queue |
| EMA | Exponential Moving Average |
| GCP | Google Cloud Platform |
| GCS | Google Cloud Storage |
| HMM | Hidden Markov Model |
| HSTS | HTTP Strict Transport Security |
| JWT | JSON Web Token |
| MACD | Moving Average Convergence Divergence |
| OHLCV | Open, High, Low, Close, Volume |
| P&L (PnL) | Profit and Loss |
| RPC | Remote Procedure Call |
| RSI | Relative Strength Index |
| SLA | Service Level Agreement |
| TA | Technical Analysis |
| TTL | Time To Live |
| TWAP | Time-Weighted Average Price |
| UUID | Universally Unique Identifier |
| VWAP | Volume-Weighted Average Price |

---

*Last updated: 2026-03-19*
