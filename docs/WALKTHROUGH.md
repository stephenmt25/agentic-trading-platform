# Praxis Trading Platform — Full Feature Walkthrough

> **Legacy Document** (written for an earlier version of the platform; auth flow, fast-gate
> timeout, and migration range corrected 2026-06-13). Remaining known drift:
> 1. The per-terminal manual startup in Step 4 predates `run_all.sh` — the supported way to
>    launch/stop the stack is `bash run_all.sh [--local-frontend]` / `bash run_all.sh --stop`
>    (it starts every backend service in the right order with port checks and a PID file).
> 2. The service walkthrough covers the original 8 core services only; the platform now runs
>    19 HTTP services (unique ports 8000–8097) plus the portless `strategy` worker and the
>    `daily_report` daemon. See `run_all.sh` and [SHUTDOWN.md](SHUTDOWN.md).
> 3. The hot-path pipeline has 11 stages (not 9 as described in Step 4.4).
>
> For the current system overview, see [Architecture Overview](architecture-overview.md). For local setup, see [Developer Guide](developer-guide.md).

A detailed guide to running, testing, and verifying every component of the platform locally on Windows.

---

## Prerequisites

Before starting, make sure you have these installed:

| Tool | Version | Check Command |
|---|---|---|
| Docker Desktop | 4.x+ | `docker --version` |
| Python | 3.11+ | `python --version` |
| Poetry | 1.7+ | `python -m poetry --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |

> [!IMPORTANT]
> All terminal commands below assume your working directory is:
> `c:\Users\stevo\DEV\agent_trader_1\aion-trading`

---

## Step 1 — Environment Configuration

The platform reads all configuration from environment variables prefixed with `PRAXIS_`. Defaults are defined in [settings.py](file:///c:/Users/stevo/DEV/agent_trader_1/aion-trading/libs/config/settings.py).

Create a `.env` file in the project root (this file is git-ignored):

```env
PRAXIS_REDIS_URL=redis://localhost:6379/1
PRAXIS_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/praxis_trading
PRAXIS_BINANCE_TESTNET=true
PRAXIS_COINBASE_SANDBOX=true
PRAXIS_TRADING_ENABLED=true
PRAXIS_PAPER_TRADING_MODE=true
PRAXIS_LOG_LEVEL=INFO
PRAXIS_FAST_GATE_TIMEOUT_MS=50
PRAXIS_CIRCUIT_BREAKER_DAILY_LOSS_PCT=0.02
```

> [!NOTE]
> `PRAXIS_TRADING_ENABLED=true` with `PRAXIS_PAPER_TRADING_MODE=true` means the system will process real market data but only execute on **testnet** exchanges. No real money is at risk.

---

## Step 2 — Boot Infrastructure Containers

Start Redis and TimescaleDB via Docker Compose:

```powershell
docker-compose -f deploy/docker-compose.yml up -d redis timescaledb
```

**Verify they are healthy:**

```powershell
docker-compose -f deploy/docker-compose.yml ps
```

You should see both containers with status `Up` and `(healthy)`. Wait ~10 seconds if they show `(health: starting)`.

**What these containers do:**
- **Redis** (`localhost:6379`) — Pub/Sub messaging, Streams for inter-service events, caching (indicator states, compiled rules, rate limits)
- **TimescaleDB** (`localhost:5432`) — PostgreSQL with time-series hypertables for OHLCV candles, orders, positions, audit logs, P&L snapshots

---

## Step 3 — Run Database Migrations

Apply the SQL migration scripts to create all tables. `scripts/migrate.py` applies **every**
file in `migrations/versions/` in sorted order — currently `001` through `024` (24 files):

```powershell
python -m poetry run python scripts/migrate.py
```

**Expected output:**
```
Starting Database Migrations...
Applying migrations/versions\001_initial_schema.sql...
Applying migrations/versions\002_audit_tables.sql...
... (one line per migration, in order) ...
Applying migrations/versions\024_trade_cost_attribution.sql...
Migrations complete.
```

**What gets created (first 9 — core schema):**

| Migration | Tables Created |
|---|---|
| `001_initial_schema.sql` | `users`, `trading_profiles`, `orders` (hypertable), `positions` |
| `002_audit_tables.sql` | `audit_log` (hypertable), `config_changes` |
| `003_validation_log.sql` | `validation_events` (hypertable), `auto_backtest_queue` |
| `004_pnl_snapshots.sql` | `pnl_snapshots` (hypertable), `market_data_ohlcv` (hypertable) |
| `005_paper_trading.sql` | `paper_trading_reports` |
| `006_users_and_exchange_keys.sql` | `users` updates, `exchange_keys` |
| `007_profile_soft_delete.sql` | Adds soft-delete columns to `trading_profiles` |
| `008_backtest_results.sql` | `backtest_results` |
| `009_backtest_decimal_precision.sql` | Converts `backtest_results` columns to `NUMERIC` |

Migrations `010`–`024` add the later-phase tables: trade decisions, agent score/weight
history, pipeline configs, intent correlation, closed trades, debate transcripts, shadow
decisions, insight-engine tables, backtest history fields, user risk defaults, user
sessions, position close lifecycle, and trade cost attribution. List them with
`ls migrations/versions/`.

**Verify manually** (optional):
```powershell
docker exec -it deploy-timescaledb-1 psql -U postgres -d praxis_trading -c "\dt"
```

---

## Step 4 — Start Services (Correct Order)

Each service runs in its own terminal. Open a **new PowerShell tab for each**.

> [!WARNING]
> Order matters! Services have startup dependencies. The Hot-Path waits for Validation Agent health, and Strategy must hydrate indicator caches before Hot-Path begins processing.

### 4.1 — Strategy Agent (pre-warms indicator caches)

```powershell
python -m poetry run python -m services.strategy.src.main
```

**What happens:** Loads all profiles from DB → fetches last 200 candles → primes RSI/EMA/MACD/ATR states into Redis → sets `hydration:{profile_id}:status = "complete"`.

**Wait for:** `"Profile states successfully hydrated"` in the logs before proceeding.

---

### 4.2 — Ingestion Agent (connects to exchange WebSockets)

```powershell
python -m poetry run python -m services.ingestion.src.main
```

**What happens:** Opens WebSocket connections to Binance testnet for `BTC/USDT` and `ETH/USDT`. Every tick is published to:
- Redis Stream `stream:market_data` (consumed by Hot-Path)
- Redis Pub/Sub `pubsub:price_ticks` (consumed by P&L Service)

Ticks are also aggregated into 1-minute OHLCV candles and written to TimescaleDB.

**Wait for:** `"Starting Ingestion Agent..."` log message. If it connects successfully to Binance you'll see tick data flowing.

---

### 4.3 — Validation Agent (safety gate — must be up before Hot-Path)

```powershell
python -m poetry run python -m services.validation.src.main
```

**What happens:** Starts 3 background loops:
1. **Fast Gate** — Consumes `stream:validation_requests`, runs Check 1 (strategy recheck) + Check 6 (risk level), responds on `stream:validation_responses` within the 50ms budget (`FAST_GATE_TIMEOUT_MS` — `libs/config/settings.py:76`, `libs/core/constants.py:3`)
2. **Async Audit** — Post-execution checks: hallucination, bias, drift, escalation
3. **Learning Loop** — Hourly scan generating backtesting jobs from anomalies

**Wait for:** `"Starting FastGate & Auditor Loops"` and verify health:
```powershell
curl http://localhost:8080/health
# Expected: {"status":"healthy"}
```

---

### 4.4 — Hot-Path Processor (the core decision engine)

```powershell
python -m poetry run python -m services.hot_path.src.main
```

**What happens on startup:**
1. Checks all `hydration:*:status` keys in Redis — waits until all are `"complete"`
2. Optionally pings Validation Agent `/health` endpoint
3. Starts consuming from `stream:market_data`

**For each tick, the processor runs this pipeline:**
1. Update indicators in `ProfileStateCache`
2. Evaluate compiled strategy rules
3. If a rule fires → `AbstentionChecker` → `RegimeDampener` (multiply confidence) → `CircuitBreaker` → `BlacklistChecker` → `RiskGate` → `ValidationClient` (50ms timeout)
4. All pass → publish `OrderApprovedEvent` to `stream:orders`

---

### 4.5 — Execution Agent (places orders on testnet)

```powershell
python -m poetry run python -m services.execution.src.main
```

**What happens:** Consumes `stream:orders`. For each approved order:
- Records `PENDING` in optimistic ledger
- Sends order to Binance testnet via `ccxt.pro` adapter
- On fill → writes `Position` to DB, updates ledger to `CONFIRMED`
- On failure → rolls back ledger to `ROLLED_BACK`

Also runs a **reconciler** cron that periodically checks ledger consistency vs exchange balances.

---

### 4.6 — P&L Service (real-time profit calculation)

```powershell
python -m poetry run python -m services.pnl.src.main
```

**What happens:** Subscribes to `pubsub:price_ticks`. For every tick:
1. Looks up open positions for that symbol
2. Calculates gross P&L, fees, estimated US tax
3. Publishes `PnlUpdateEvent` to `pubsub:pnl_updates` (consumed by API Gateway → Dashboard)
4. Periodically snapshots to `pnl_snapshots` table

---

### 4.7 — Logger Agent (audit trail)

```powershell
python -m poetry run python -m services.logger.src.main
```

**What happens:** Subscribes to **all** Redis Streams and Pub/Sub channels. Writes every event to the `audit_log` hypertable. Dispatches critical alerts (e.g., `ALERT_RED` Trading Halt) to the `Alerter`.

---

### 4.8 — API Gateway (REST + WebSocket for dashboard)

```powershell
python -m poetry run python -m services.api_gateway.src.main
```

**Runs on:** `http://localhost:8000`

**Endpoints available:**
- `POST /auth/callback` — OAuth callback (there is **no** `/auth/login` endpoint). The
  frontend authenticates the user via NextAuth.js (Google/GitHub OAuth) and then POSTs the
  NextAuth session token (HS256-signed with the shared `PRAXIS_NEXTAUTH_SECRET`) plus the
  provider account info to this endpoint. The gateway verifies the token, upserts the user,
  records a `user_sessions` row, and returns a backend access token (1h) + refresh token
  (7d). See `services/api_gateway/src/routes/auth.py`.
- `POST /auth/refresh` — Rotate the refresh token (old jti revoked; session liveness checked
  against the `user_sessions` row — a revoked session forces re-login)
- `GET /auth/me` — Current user profile
- `GET /auth/sessions` / `POST /auth/sessions/{id}/revoke` — Active-session list + revocation
  (backs `/settings/sessions`)
- `GET /profiles/` — List trading profiles
- `POST /profiles/` — Create profile (validates rules via `RuleValidator`)
- `GET /orders/` — Order history
- `GET /pnl/{profile_id}` — P&L data
- `POST /commands/` — Natural language commands (e.g., "stop trading BTC")
- `WS /ws?token=<jwt>` — Real-time WebSocket (P&L updates, alerts)
- `GET /health` — Health check

---

### 4.9 — Next.js Dashboard

Open a **new terminal**:

```powershell
cd c:\Users\stevo\DEV\agent_trader_1\aion-trading\frontend
npm run dev
```

**Runs on:** `http://localhost:3000`

---

## Step 5 — Test the Dashboard Features

Open `http://localhost:3000` in your browser.

### 5.1 — Dashboard Home (`/`)
- **Portfolio Summary Card** — Shows aggregated P&L (gross, fees, tax estimate, net post-tax)
- **Active Profiles** — Each profile shows its real-time P&L, updated via WebSocket with no page refresh
- Numbers update live as ticks flow from Ingestion → P&L → API Gateway WebSocket → Zustand store → React component

### 5.2 — Validation Alert Tray
- Click the **Bell icon** on the right edge of the screen
- The sliding tray shows safety alerts from the Validation Agent's async audit:
  - **AMBER** alerts — warnings (bias detected, drift detected)
  - **RED** alerts — trading halt, requires manual **"ACKNOWLEDGE HALT"** button click
- Unread count badge pulses on the bell icon

### 5.3 — Paper Trading Page (`/paper-trading`)
- Navigate to `http://localhost:3000/paper-trading`
- Shows the mandatory 30-day observation progress bar
- Metric cards track: Uptime, Returns, Max Drawdown, Safety Net activations
- Daily system report links appear as days pass

### 5.4 — Profiles Page (`/profiles`)
- View and manage trading profiles
- **JSON Rule Editor** — Edit strategy rules as JSON, click "COMPILE & SAVE" to validate them against the `RuleValidator` before persisting

---

## Step 6 — Verify Data in the Database

Connect to TimescaleDB directly:

```powershell
docker exec -it deploy-timescaledb-1 psql -U postgres -d praxis_trading
```

**Useful queries:**

```sql
-- Check audit log (every event in the system is recorded here)
SELECT event_type, source_service, created_at
FROM audit_log ORDER BY created_at DESC LIMIT 10;

-- Check if any orders were placed
SELECT order_id, symbol, side, quantity, price, status
FROM orders ORDER BY created_at DESC LIMIT 10;

-- Check open positions
SELECT position_id, symbol, side, entry_price, quantity, status
FROM positions WHERE status = 'OPEN';

-- Check P&L snapshots
SELECT profile_id, symbol, gross_pnl, net_pnl_post_tax, pct_return
FROM pnl_snapshots ORDER BY snapshot_at DESC LIMIT 10;

-- Check OHLCV candles being written by Ingestion
SELECT symbol, timeframe, open, close, volume, bucket
FROM market_data_ohlcv ORDER BY bucket DESC LIMIT 10;

-- Check validation events
SELECT check_type, verdict, reason, response_time_ms
FROM validation_events ORDER BY created_at DESC LIMIT 10;
```

**Exit psql:** type `\q` and press Enter.

---

## Step 7 — Run Automated Tests

### Contract Tests (schema compatibility between services)
```powershell
python -m poetry run pytest tests/contract -v
```

### End-to-End Tests (full pipeline with mocks)
```powershell
python -m poetry run pytest tests/e2e -v
```

### Unit Tests (individual component logic)
```powershell
python -m poetry run pytest tests/unit -v
```

---

## Step 8 — Shutdown

### Stop all Python services
Press `Ctrl+C` in each terminal running a service.

### Stop Docker containers
```powershell
docker-compose -f deploy/docker-compose.yml down
```

### Stop and remove all data (fresh start)
```powershell
docker-compose -f deploy/docker-compose.yml down -v
```
The `-v` flag removes the persistent volumes (Redis data + TimescaleDB data), giving you a clean slate.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'asyncpg'` | Run `python -m poetry run pip install asyncpg` |
| `ModuleNotFoundError: No module named 'numpy'` | Python 3.14 may lack prebuilt wheels. Use Python 3.12 or install via `python -m poetry run pip install numpy` |
| `database "praxis_trading" does not exist` | You started `docker-compose.test.yml` instead of `docker-compose.yml`. Run `docker-compose -f deploy/docker-compose.yml up -d` |
| `'poetry' is not recognized` | Use `python -m poetry` instead of `poetry` |
| Hot-Path hangs on startup | It's waiting for hydration keys. Make sure Strategy Agent ran first |
| WebSocket disconnects immediately | JWT token missing or expired. Check `localStorage.getItem('jwt')` in browser console |
| `cannot create a unique index` during migration | The migration was already partially applied. Run `docker-compose down -v` and start fresh |
