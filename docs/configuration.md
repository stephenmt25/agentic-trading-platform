# Praxis Trading Platform -- Configuration Reference

> Complete reference for every environment variable, constant, feature flag, and
> tunable parameter in the Praxis Trading Platform.  All settings use the `PRAXIS_`
> prefix and are managed through Pydantic `BaseSettings`
> (see `libs/config/settings.py`).

---

## Table of Contents

- [Environment Variables](#environment-variables)
  - [Infrastructure](#infrastructure)
  - [Exchange Connectivity](#exchange-connectivity)
  - [Feature Flags](#feature-flags)
  - [Validation and Safety](#validation-and-safety)
  - [External API Keys](#external-api-keys)
  - [Authentication and Secrets](#authentication-and-secrets)
  - [CORS](#cors)
  - [Database Connection Pool](#database-connection-pool)
  - [Trading Symbols](#trading-symbols)
  - [Backtesting](#backtesting)
- [Frontend Environment Variables](#frontend-environment-variables)
- [Docker / Compose Variables](#docker--compose-variables)
- [Compile-Time Constants](#compile-time-constants)
  - [Technical Analysis](#technical-analysis)
  - [Risk and Drift Detection](#risk-and-drift-detection)
  - [Data Retention](#data-retention)
  - [Performance](#performance)
- [Exchange API Configuration](#exchange-api-configuration)
  - [Binance](#binance)
  - [Coinbase](#coinbase)
  - [Testnet and Sandbox Switching](#testnet-and-sandbox-switching)
- [Agent Configuration](#agent-configuration)
- [Risk Parameter Configuration](#risk-parameter-configuration)
- [Feature Flags -- Detailed Behavior](#feature-flags----detailed-behavior)
- [Startup Sequence](#startup-sequence)
- [Service Ports](#service-ports)
- [Known Port Conflicts](#known-port-conflicts)

---

## Environment Variables

Every application-level setting is read from the process environment (or a
`.env` file) with the `PRAXIS_` prefix.  For example, the setting `REDIS_URL` in
`libs/config/settings.py` maps to the environment variable `PRAXIS_REDIS_URL`.

Copy `config/.env.example` to `config/.env` and edit the values for your
environment.  Never commit `.env` files that contain real credentials.

### Infrastructure

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_REDIS_URL` | `str` | No | `redis://localhost:6379/1` | Redis connection URL. Used for pub/sub messaging between agents, rolling-window caches, and the sentiment cache. | All agents, Hot-Path, Sentiment |
| `PRAXIS_DATABASE_URL` | `str` | No | `postgresql://postgres:postgres@localhost:5432/praxis_trading` | TimescaleDB connection string. Stores OHLCV data, PnL snapshots, audit logs, backtest results, and user accounts. | All agents that persist data, API Gateway, Backtesting |
| `PRAXIS_LOG_LEVEL` | `str` | No | `INFO` | Logging verbosity. Accepts `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Uses `structlog` throughout. | All services |

### Exchange Connectivity

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_BINANCE_TESTNET` | `bool` | No | `True` | When `true`, all Binance API calls route to the testnet endpoint. Set to `false` only when you are ready for live trading. | Ingestion, Execution |
| `PRAXIS_COINBASE_SANDBOX` | `bool` | No | `True` | When `true`, all Coinbase API calls route to the sandbox endpoint. Set to `false` only when you are ready for live trading. | Ingestion, Execution |

### Feature Flags

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_TRADING_ENABLED` | `bool` | No | `False` | Master kill-switch for live order execution. When `false`, the Execution agent rejects all order requests regardless of other flags. Must be explicitly set to `true` to allow any orders. | Execution, Validation |
| `PRAXIS_PAPER_TRADING_MODE` | `bool` | No | `False` | When `true`, Execution simulates fills locally instead of sending orders to exchange APIs. Useful for end-to-end testing without exchange credentials. | Execution |

### Validation and Safety

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_FAST_GATE_TIMEOUT_MS` | `int` | No | `50` | Maximum milliseconds allowed for fast-gate validation checks. If validation exceeds this SLA, the signal is rejected. | Validation |
| `PRAXIS_CIRCUIT_BREAKER_DAILY_LOSS_PCT` | `Decimal` | No | `0.02` | Portfolio-wide daily loss threshold (as a decimal fraction, e.g., `0.02` = 2%). When cumulative realized + unrealized losses hit this level, the circuit breaker halts all trading for the remainder of the day. | PnL, Risk, Execution |
| `PRAXIS_HOT_DATA_RETENTION_DAYS` | `int` | No | `7` | Number of days to keep OHLCV and tick data in the hot (TimescaleDB) tier before the Archiver moves it to cold storage. | Archiver, TA Agent, Hot-Path |
| `PRAXIS_SENTIMENT_CACHE_TTL_S` | `int` | No | `900` | Time-to-live in seconds for cached sentiment scores in Redis. Prevents redundant LLM/news API calls for the same asset within the TTL window. | Sentiment |

### External API Keys

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_LLM_API_KEY` | `str` | No | `""` | API key for the LLM service (used by the Analyst agent for trade reasoning and the Sentiment agent for news summarization). Leave empty to disable LLM-dependent features. | Analyst, Sentiment |
| `PRAXIS_NEWS_API_KEY` | `str` | No | `""` | API key for the news data provider. Required for the Sentiment agent to fetch headlines. | Sentiment |
| `PRAXIS_PAGERDUTY_API_KEY` | `str` | No | `""` | PagerDuty integration key for alerting on circuit breaker trips, service crashes, and drift threshold violations. | Logger, Risk |
| `PRAXIS_GCS_BUCKET_NAME` | `str` | No | `""` | Google Cloud Storage bucket for cold-tier archival of historical OHLCV data. Leave empty to skip archival (data remains in TimescaleDB). | Archiver |

### Authentication and Secrets

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_SECRET_KEY` | `str` | **Yes (production)** | `praxis-dev-secret-key-change-in-production` | JWT signing key for access tokens. The default value is intentionally insecure. The `Settings.is_secret_key_secure()` method returns `False` if the default is still in use. You **must** change this before deploying. | API Gateway |
| `PRAXIS_REFRESH_SECRET_KEY` | `str` | **Yes (production)** | `""` | Separate signing key for refresh tokens. Must differ from `SECRET_KEY`. | API Gateway |
| `PRAXIS_NEXTAUTH_SECRET` | `str` | **Yes (production)** | `""` | Must match the `NEXTAUTH_SECRET` value configured in the frontend `.env.local`. Used to validate session tokens across the backend and NextAuth.js. Generate with `openssl rand -base64 32`. | API Gateway, Frontend |
| `PRAXIS_GCP_PROJECT_ID` | `str` | No | `""` | GCP project ID for Secret Manager integration. When empty, the platform falls back to local Fernet encryption for exchange API key storage. | API Gateway |

### CORS

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_CORS_ORIGINS` | `List[str]` | No | `["http://localhost:3000"]` | Allowed CORS origins for the API Gateway. In production, set this to your frontend domain(s). Accepts a JSON array string. | API Gateway |

### Database Connection Pool

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_DB_POOL_MIN_SIZE` | `int` | No | `5` | Minimum number of connections maintained in the asyncpg connection pool. | All services using TimescaleDB |
| `PRAXIS_DB_POOL_MAX_SIZE` | `int` | No | `20` | Maximum number of connections the pool will open. Size this based on the number of concurrent agents. | All services using TimescaleDB |
| `PRAXIS_DB_POOL_TIMEOUT` | `int` | No | `30` | Seconds to wait for a connection from the pool before raising a timeout error. | All services using TimescaleDB |

### Trading Symbols

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_TRADING_SYMBOLS` | `List[str]` | No | `["BTC/USDT", "ETH/USDT"]` | The list of trading pairs the platform monitors and trades. This is the single source of truth -- all agents read symbols from this setting. Accepts a JSON array string. | Ingestion, Strategy, TA Agent, Execution, PnL |

### Backtesting

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_BACKTEST_MAX_QUEUE_DEPTH` | `int` | No | `100` | Maximum number of pending backtest jobs allowed in the queue. New submissions are rejected with HTTP 429 when this limit is reached. | Backtesting |

### Local SLM Inference

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_LLM_BACKEND` | `str` | No | `"cloud"` | LLM backend mode. `"cloud"` = Claude API only. `"local"` = local SLM only. `"auto"` = try local first, fall back to cloud. | Sentiment, Debate |
| `PRAXIS_SLM_INFERENCE_URL` | `str` | No | `"http://localhost:8095"` | URL of the local SLM inference service. | Sentiment, Debate |
| `PRAXIS_SLM_MODEL_PATH` | `str` | No | `""` | Absolute path to the GGUF model file. Empty = mock mode (returns neutral responses). | SLM Inference |
| `PRAXIS_SLM_CONTEXT_LENGTH` | `int` | No | `4096` | Context window size for the loaded SLM model. | SLM Inference |
| `PRAXIS_SLM_GPU_LAYERS` | `int` | No | `-1` | Number of model layers to offload to GPU. `-1` = all layers. `0` = CPU only. | SLM Inference |

### HITL (Human-in-the-Loop)

| Variable | Type | Required | Default | Description | Consumed By |
|----------|------|----------|---------|-------------|-------------|
| `PRAXIS_HITL_ENABLED` | `bool` | No | `false` | Enable the HITL execution gate in the hot-path pipeline. When disabled, the gate is a no-op pass-through. | Hot Path |
| `PRAXIS_HITL_SIZE_THRESHOLD_PCT` | `float` | No | `5.0` | Trade size as a percentage of max allocation that triggers HITL approval. | Hot Path |
| `PRAXIS_HITL_CONFIDENCE_THRESHOLD` | `float` | No | `0.5` | Signal confidence below this value triggers HITL approval. | Hot Path |
| `PRAXIS_HITL_TIMEOUT_S` | `int` | No | `60` | Seconds to wait for human approval response. Fail-safe: timeout = reject. | Hot Path |

---

## Frontend Environment Variables

The Next.js frontend reads its own environment from `frontend/.env.local`.
Copy `frontend/.env.local.example` to `frontend/.env.local` and fill in
the values.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXTAUTH_URL` | Yes | `http://localhost:3000` | Canonical URL of the frontend. Used by NextAuth.js for callback URLs. |
| `NEXTAUTH_SECRET` | Yes | -- | Session signing secret. Must match `PRAXIS_NEXTAUTH_SECRET` on the backend. Generate with `openssl rand -base64 32`. |
| `GOOGLE_CLIENT_ID` | No | -- | OAuth client ID from Google Cloud Console. Required for Google sign-in. |
| `GOOGLE_CLIENT_SECRET` | No | -- | OAuth client secret from Google Cloud Console. |
| `GITHUB_CLIENT_ID` | No | -- | OAuth client ID from GitHub Developer Settings. Required for GitHub sign-in. |
| `GITHUB_CLIENT_SECRET` | No | -- | OAuth client secret from GitHub Developer Settings. |
| `NEXT_PUBLIC_API_URL` | Yes | `http://localhost:8000` | Backend API Gateway URL. Exposed to the browser (public prefix). |

---

## Docker / Compose Variables

These variables are consumed by `deploy/docker-compose.yml` directly (no
`PRAXIS_` prefix). Set them in a `.env` file alongside the compose file or export
them in your shell.

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_PASSWORD` | `changeme_redis_dev` | Redis `requirepass` value. Must match the password segment in `PRAXIS_REDIS_URL`. |
| `POSTGRES_USER` | `postgres` | TimescaleDB superuser name. |
| `POSTGRES_PASSWORD` | `postgres` | TimescaleDB superuser password. Must match the password in `PRAXIS_DATABASE_URL`. |

---

## Compile-Time Constants

Defined in `libs/core/constants.py`. These are not configurable at runtime.
To change them, edit the source file and redeploy.

### Technical Analysis

| Constant | Value | Description |
|----------|-------|-------------|
| `RSI_PERIOD` | `14` | Lookback period for the RSI indicator. |
| `MACD_FAST` | `12` | Fast EMA period for MACD. |
| `MACD_SLOW` | `26` | Slow EMA period for MACD. |
| `MACD_SIGNAL` | `9` | Signal line EMA period for MACD. |

### Risk and Drift Detection

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_CIRCUIT_BREAKER_PCT` | `0.02` | Compile-time mirror of the circuit breaker setting. Agents use `Settings.CIRCUIT_BREAKER_DAILY_LOSS_PCT` at runtime; this constant is used when settings are not yet loaded. |
| `DEFAULT_DRIFT_MULTIPLIER` | `3.0` | Multiplier applied to the rolling standard deviation of returns to set the drift alert threshold. |
| `DEFAULT_DRIFT_WINDOW_DAYS` | `7` | Rolling window (in days) over which portfolio drift is measured. |
| `MIN_DRIFT_THRESHOLD_PCT` | `0.15` | Minimum drift threshold (15%). Even if the multiplier calculation yields a smaller value, drift alerts do not fire below this floor. |
| `RECONCILIATION_DRIFT_THRESHOLD_PCT` | `0.001` | Position reconciliation tolerance (0.1%). Differences between local state and exchange state below this threshold are ignored. |
| `THRESHOLD_PROXIMITY_BAND_PCT` | `0.10` | When a signal price is within 10% of a risk threshold, the Validation agent attaches a proximity warning to the signal metadata. |

### Data Retention

| Constant | Value | Description |
|----------|-------|-------------|
| `HOT_DATA_RETENTION_DAYS` | `7` | Mirrors `PRAXIS_HOT_DATA_RETENTION_DAYS`. Used by the Archiver to decide which rows to move to cold storage. |
| `COLD_BACKTEST_BOUNDARY_MONTHS` | `12` | Backtests can request up to 12 months of cold-tier historical data. Requests beyond this boundary are rejected. |

### Performance

| Constant | Value | Description |
|----------|-------|-------------|
| `FAST_GATE_TIMEOUT_MS` | `50` | Compile-time mirror of the fast-gate SLA. |
| `SENTIMENT_CACHE_TTL_S` | `900` | Compile-time mirror of the sentiment cache TTL. |
| `REDIS_ROLLING_WINDOW_SIZE` | `1000` | Maximum number of data points stored in Redis rolling-window lists (e.g., recent ticks, recent signals). |

---

## Exchange API Configuration

The platform uses [ccxt](https://github.com/ccxt/ccxt) (v4.2+) for exchange
connectivity. Exchange API keys are stored encrypted in TimescaleDB (Fernet
locally, or GCP Secret Manager in production) and are associated with user
accounts.

### Binance

- Controlled by `PRAXIS_BINANCE_TESTNET`.
- When `true` (the default), ccxt is configured with `{'options': {'defaultType': 'future'}, 'sandbox': True}`, routing all requests to `testnet.binancefuture.com`.
- When `false`, requests go to the production Binance API.
- API key and secret are per-user and loaded from the encrypted `exchange_keys` table.

### Coinbase

- Controlled by `PRAXIS_COINBASE_SANDBOX`.
- When `true` (the default), ccxt routes to the Coinbase sandbox environment.
- When `false`, requests go to production Coinbase Advanced Trade.
- API key and secret are per-user and loaded from the encrypted `exchange_keys` table.

### Testnet and Sandbox Switching

To move from testnet to live trading, you must change **three** settings
together. Enabling only one creates an inconsistent state that the Validation
agent should reject.

```bash
# Production configuration (handle with extreme care)
PRAXIS_BINANCE_TESTNET=false
PRAXIS_COINBASE_SANDBOX=false
PRAXIS_TRADING_ENABLED=true
```

The recommended progression is:

1. **Development**: All defaults (testnet=true, sandbox=true, trading=false).
   No orders are sent anywhere.
2. **Paper trading**: Set `PRAXIS_PAPER_TRADING_MODE=true` and
   `PRAXIS_TRADING_ENABLED=true`. Orders are simulated locally.
3. **Testnet trading**: Set `PRAXIS_TRADING_ENABLED=true` with testnet/sandbox
   still `true`. Real orders hit exchange testnets.
4. **Live trading**: Flip testnet/sandbox to `false`. Real orders, real money.

---

## Agent Configuration

Each agent in the platform reads from the shared `Settings` object. The
following table maps agents to the settings they consume most heavily.

| Agent | Key Settings | Tunables |
|-------|-------------|----------|
| **Ingestion** | `TRADING_SYMBOLS`, `BINANCE_TESTNET`, `COINBASE_SANDBOX`, `REDIS_URL` | Symbols list controls which WebSocket feeds are opened. |
| **Validation** | `FAST_GATE_TIMEOUT_MS`, `CIRCUIT_BREAKER_DAILY_LOSS_PCT` | Timeout and loss threshold determine which signals pass the gate. |
| **Strategy** | `TRADING_SYMBOLS`, `REDIS_URL`, `DATABASE_URL` | Symbols list determines which assets the strategy evaluates. |
| **Hot-Path** | `REDIS_URL`, `FAST_GATE_TIMEOUT_MS` | Latency budget for the critical signal path. |
| **Execution** | `TRADING_ENABLED`, `PAPER_TRADING_MODE`, `BINANCE_TESTNET`, `COINBASE_SANDBOX` | All four flags determine whether and where orders are sent. |
| **PnL** | `DATABASE_URL`, `CIRCUIT_BREAKER_DAILY_LOSS_PCT` | Tracks portfolio value; triggers circuit breaker. |
| **TA Agent** | `HOT_DATA_RETENTION_DAYS`, `DATABASE_URL` | TA lookback is bounded by the hot data window. Constants `RSI_PERIOD`, `MACD_*` are compile-time. |
| **Regime HMM** | `DATABASE_URL`, `REDIS_URL` | Reads OHLCV from TimescaleDB, publishes regime state to Redis. |
| **Sentiment** | `LLM_API_KEY`, `NEWS_API_KEY`, `SENTIMENT_CACHE_TTL_S`, `REDIS_URL` | Cache TTL controls how often the LLM is called per asset. |
| **Backtesting** | `DATABASE_URL`, `BACKTEST_MAX_QUEUE_DEPTH` | Queue depth prevents runaway backtest submissions. |
| **Archiver** | `HOT_DATA_RETENTION_DAYS`, `GCS_BUCKET_NAME`, `DATABASE_URL` | Moves data older than retention window to GCS. |
| **Logger** | `LOG_LEVEL`, `PAGERDUTY_API_KEY` | Structured logging; PagerDuty for critical alerts. |
| **Risk** | `CIRCUIT_BREAKER_DAILY_LOSS_PCT`, `DATABASE_URL` | Monitors portfolio-level risk metrics. |
| **API Gateway** | `SECRET_KEY`, `REFRESH_SECRET_KEY`, `NEXTAUTH_SECRET`, `CORS_ORIGINS`, `DATABASE_URL` | Auth, CORS, and user management. |

---

## Risk Parameter Configuration

Risk parameters form a layered defense. Each layer operates independently so
that a bug in one layer does not disable the others.

### Layer 1 -- Fast Gate (per-signal)

- **Setting**: `PRAXIS_FAST_GATE_TIMEOUT_MS` (default `50`)
- **Constant**: `THRESHOLD_PROXIMITY_BAND_PCT` (`0.10`)
- Rejects signals that take too long to validate or that land within the
  proximity band of a risk threshold.

### Layer 2 -- Circuit Breaker (portfolio-wide)

- **Setting**: `PRAXIS_CIRCUIT_BREAKER_DAILY_LOSS_PCT` (default `0.02`)
- **Constant**: `DEFAULT_CIRCUIT_BREAKER_PCT` (`0.02`)
- The PnL agent computes cumulative daily P&L. When losses exceed the threshold,
  the circuit breaker fires and the Execution agent stops accepting orders for
  the rest of the trading day.

### Layer 3 -- Drift Detection (portfolio-wide)

- **Constants**: `DEFAULT_DRIFT_MULTIPLIER` (`3.0`), `DEFAULT_DRIFT_WINDOW_DAYS` (`7`), `MIN_DRIFT_THRESHOLD_PCT` (`0.15`)
- Detects abnormal portfolio drift using a rolling z-score. If the portfolio
  return over the drift window exceeds `multiplier * rolling_std`, and is above
  the minimum threshold, a drift alert is raised.

### Layer 4 -- Reconciliation (per-position)

- **Constant**: `RECONCILIATION_DRIFT_THRESHOLD_PCT` (`0.001`)
- Compares local position state against exchange-reported positions.
  Discrepancies above 0.1% trigger a reconciliation event.

---

## Feature Flags -- Detailed Behavior

The three boolean flags interact as a state matrix:

| `TRADING_ENABLED` | `PAPER_TRADING_MODE` | `BINANCE_TESTNET` / `COINBASE_SANDBOX` | Behavior |
|--------------------|----------------------|-----------------------------------------|----------|
| `false` | any | any | **Read-only mode.** Signals are generated and logged but never executed. This is the default. |
| `true` | `true` | any | **Paper trading.** Execution simulates fills locally. No API calls to any exchange. |
| `true` | `false` | `true` / `true` | **Testnet trading.** Real orders are sent to exchange testnet/sandbox APIs. No real money at risk. |
| `true` | `false` | `false` / `false` | **Live trading.** Real orders on production exchanges. Real money at risk. |
| `true` | `false` | mixed | **Invalid.** One exchange on testnet, one on production. The Validation agent should flag this. Avoid this state. |

---

## Startup Sequence

Services must start in a specific order because of data and messaging
dependencies. The correct sequence is:

### Phase 1 -- Infrastructure

```
1. Redis           (pub/sub bus, caches -- no dependencies)
2. TimescaleDB     (persistent storage -- no dependencies)
```

Start with Docker Compose:

```bash
docker compose -f deploy/docker-compose.yml up -d
```

Wait for health checks to pass before proceeding. Both services include
health checks in the compose file (Redis: `redis-cli ping`, TimescaleDB:
`pg_isready`).

### Phase 2 -- Schema

```
3. Migrations      (creates tables, hypertables, indexes)
```

```bash
poetry run python scripts/migrate.py
```

This applies all 8 SQL migrations in `migrations/versions/` in order:

1. `001_initial_schema.sql` -- Core OHLCV and positions tables
2. `002_audit_tables.sql` -- Audit trail for all state changes
3. `003_validation_log.sql` -- Fast-gate validation event log
4. `004_pnl_snapshots.sql` -- PnL snapshot hypertable
5. `005_paper_trading.sql` -- Paper trading simulation tables
6. `006_users_and_exchange_keys.sql` -- User accounts and encrypted exchange keys
7. `007_profile_soft_delete.sql` -- Soft delete support for user profiles
8. `008_backtest_results.sql` -- Backtest result storage

### Phase 3 -- Agents (order matters)

```
4. Strategy Agent       (must hydrate state from DB before other agents send signals)
5. Ingestion Agent      (opens WebSocket feeds; publishes raw market data to Redis)
6. Validation Agent     (subscribes to raw data; applies fast-gate checks)
7. Hot-Path Agent       (consumes validated signals on the critical path)
8. Execution Agent      (receives execution requests from Hot-Path)
9. PnL Agent            (tracks fills and computes portfolio P&L)
10. Logger Agent        (aggregates structured logs and alerts)
```

**Why this order matters:**

- **Strategy before Ingestion**: The Strategy agent must load its state (open
  positions, current regime, pending signals) from TimescaleDB before market data
  starts flowing. If Ingestion starts first, the Hot-Path may process signals
  against stale or empty strategy state, leading to hangs (see Known Issues).
- **Validation before Hot-Path**: The Hot-Path expects a functioning validation
  layer. Without it, unvalidated signals reach Execution.
- **Execution before PnL**: PnL subscribes to fill events from Execution. If
  PnL starts first, it may miss initial fills.

### Phase 4 -- Supporting services

```
11. TA Agent            (technical analysis -- can start anytime after DB)
12. Regime HMM          (regime detection -- can start anytime after DB + Redis)
13. Sentiment Agent     (news/LLM -- can start anytime after Redis)
14. Backtesting         (isolated -- can start anytime after DB)
15. Archiver            (data lifecycle -- can start anytime after DB)
16. Analyst             (LLM reasoning -- can start anytime after Redis)
17. Risk Agent          (monitoring -- can start anytime after DB + Redis)
18. Tax Agent           (reporting -- can start anytime after DB)
```

### Phase 5 -- Frontend

```
19. API Gateway         (must start before frontend; serves REST + WebSocket)
20. Frontend            (Next.js -- connects to API Gateway)
```

```bash
# Terminal 1: API Gateway
poetry run uvicorn services.api_gateway.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend && npm install && npm run dev
```

---

## Service Ports

| Service | Port | Protocol |
|---------|------|----------|
| API Gateway | `8000` | HTTP / WebSocket |
| Hot-Path | `8082` | HTTP |
| Execution | `8083` | HTTP |
| PnL | `8084` | HTTP |
| Logger | `8085` | HTTP |
| Backtesting | `8086` | HTTP |
| Analyst (weight engine) | `8087` | HTTP |
| TA Agent | `8090` | HTTP |
| Regime HMM | `8091` | HTTP |
| Sentiment | `8092` | HTTP |
| SLM Inference | `8095` | HTTP |
| Debate Agent | `8096` | HTTP |
| Frontend (Next.js) | `3000` | HTTP |
| Redis | `6379` | TCP |
| TimescaleDB | `5432` | TCP |

### Known Port Conflicts

The following services are all documented or configured to use port `8080`:

- Ingestion
- Archiver
- Analyst
- Tax

This is a known conflict. If you need to run more than one of these services
simultaneously in local development, assign distinct ports via each service's
`--port` flag or `UVICORN_PORT` environment variable. Track resolution of this
issue in the project changelog.

---

## Configuration Files Reference

| File | Purpose |
|------|---------|
| `libs/config/settings.py` | Pydantic `BaseSettings` class. Single source of truth for all `PRAXIS_` variables. |
| `libs/core/constants.py` | Compile-time constants for TA indicators, risk thresholds, and data retention. |
| `config/.env.example` | Template for local development. Copy to `config/.env`. |
| `config/.env.test` | Pre-configured values for the test suite. Used by `scripts/run_tests.sh`. |
| `frontend/.env.local.example` | Template for frontend environment. Copy to `frontend/.env.local`. |
| `deploy/docker-compose.yml` | Development infrastructure (Redis + TimescaleDB). |
| `deploy/docker-compose.test.yml` | Test infrastructure on offset ports (Redis 6380, TimescaleDB 5433). |
