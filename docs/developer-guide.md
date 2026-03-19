# Aion Trading Platform -- Developer Guide

> Everything you need to set up a local development environment, run the
> platform, execute tests, and contribute new features.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
  - [Step 1: Clone and Install Python Dependencies](#step-1-clone-and-install-python-dependencies)
  - [Step 2: Start Infrastructure](#step-2-start-infrastructure)
  - [Step 3: Configure Environment Variables](#step-3-configure-environment-variables)
  - [Step 4: Run Database Migrations](#step-4-run-database-migrations)
  - [Step 5: Start Backend Services](#step-5-start-backend-services)
  - [Step 6: Start the Frontend](#step-6-start-the-frontend)
- [Running Against Exchange Testnets](#running-against-exchange-testnets)
- [Common Workflows](#common-workflows)
  - [Add a New Exchange Connector](#add-a-new-exchange-connector)
  - [Add a New Agent](#add-a-new-agent)
  - [Add a New Signal Source](#add-a-new-signal-source)
- [Testing Strategy](#testing-strategy)
  - [Test Locations](#test-locations)
  - [Running Tests](#running-tests)
  - [Mocking Exchanges](#mocking-exchanges)
  - [Backtesting](#backtesting)
  - [LLM Prompt Testing](#llm-prompt-testing)
  - [CI Pipeline](#ci-pipeline)
- [Makefile Reference](#makefile-reference)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Install the following before you begin. The exact versions matter -- the
platform uses Python 3.11 features and is not yet tested on 3.12+.

| Tool | Version | Installation |
|------|---------|-------------|
| Python | 3.11+ (not 3.14, see [Troubleshooting](#python-314-and-numpy)) | [python.org](https://www.python.org/downloads/) |
| Poetry | 1.7.0 | `pip install poetry==1.7.0` |
| Docker Desktop | Latest | [docker.com](https://www.docker.com/products/docker-desktop/) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) |
| npm | 9+ (ships with Node.js 20) | Included with Node.js |

Verify your installations:

```bash
python --version   # Python 3.11.x
poetry --version   # Poetry (version 1.7.0)
docker --version   # Docker version 24+
node --version     # v20.x.x
npm --version      # 9.x.x or 10.x.x
```

---

## Local Setup

### Step 1: Clone and Install Python Dependencies

```bash
cd aion-trading
poetry install
```

This installs all runtime and development dependencies defined in
`pyproject.toml`, including `fastapi`, `ccxt`, `asyncpg`, `numpy`,
`hmmlearn`, `structlog`, and dev tools (`black`, `isort`, `ruff`, `mypy`,
`pytest`).

### Step 2: Start Infrastructure

The platform requires Redis 7 and TimescaleDB (PostgreSQL 15 with the
TimescaleDB 2.13.1 extension). Both are provided via Docker Compose.

```bash
docker compose -f deploy/docker-compose.yml up -d
```

Wait for both services to become healthy:

```bash
# Check health status
docker compose -f deploy/docker-compose.yml ps
```

You should see `(healthy)` next to both `redis` and `timescaledb`. This
typically takes 10-20 seconds. The `scripts/run_local.sh` script automates
this wait if you prefer:

```bash
bash scripts/run_local.sh
```

**What this starts:**

| Service | Port | Credentials |
|---------|------|-------------|
| Redis 7 (Alpine) | `localhost:6379` | Password: `changeme_redis_dev` |
| TimescaleDB 2.13.1 (PG15) | `localhost:5432` | User: `postgres`, Password: `postgres`, DB: `aion_trading` |

Redis is configured with 256 MB max memory and an `allkeys-lru` eviction
policy. TimescaleDB is allocated 1 GB memory. Both use named Docker volumes
(`redis_data`, `timescale_data`) so data persists across container restarts.

### Step 3: Configure Environment Variables

```bash
cp config/.env.example config/.env
```

Edit `config/.env` with your local values. For basic local development, the
defaults work out of the box -- no changes are required. If you plan to use
LLM or news features, add your API keys.

See `docs/configuration.md` for a complete reference of every variable.

**Important**: The `REDIS_PASSWORD` in your `.env` must match the password
in `AION_REDIS_URL`. The example file uses `changeme_redis_dev` for both.

### Step 4: Run Database Migrations

```bash
poetry run python scripts/migrate.py
```

This applies 8 SQL migration files from `migrations/versions/` in
alphabetical order:

```
001_initial_schema.sql
002_audit_tables.sql
003_validation_log.sql
004_pnl_snapshots.sql
005_paper_trading.sql
006_users_and_exchange_keys.sql
007_profile_soft_delete.sql
008_backtest_results.sql
```

The migration script connects to TimescaleDB using `AION_DATABASE_URL` from
your settings and applies each `.sql` file via the `TimescaleClient`. If a
migration has already been applied, the script logs the error and continues
to the next file.

**Alternative** (applies migrations directly via `psql` in the Docker
container):

```bash
for f in migrations/versions/*.sql; do
  echo "Running $f"
  docker exec -i $(docker compose -f deploy/docker-compose.yml ps -q timescaledb) \
    psql -U postgres -d aion_trading < "$f"
done
```

### Step 5: Start Backend Services

Services must start in a specific order due to data dependencies. See
`docs/configuration.md` for the full rationale. For local development,
start the core pipeline first:

```bash
# Terminal 1: Strategy Agent (must start first -- hydrates state from DB)
poetry run python -m services.strategy.main

# Terminal 2: Ingestion (opens WebSocket feeds to exchanges)
poetry run python -m services.ingestion.main

# Terminal 3: Validation (fast-gate checks on incoming signals)
poetry run python -m services.validation.main

# Terminal 4: Hot-Path (critical signal routing)
poetry run python -m services.hot_path.main

# Terminal 5: Execution (order management)
poetry run python -m services.execution.main

# Terminal 6: PnL (portfolio tracking)
poetry run python -m services.pnl.main

# Terminal 7: API Gateway (REST + WebSocket API)
poetry run uvicorn services.api_gateway.main:app --host 0.0.0.0 --port 8000 --reload
```

Optional supporting services (start any you need):

```bash
# TA indicators
poetry run python -m services.ta_agent.main

# Regime detection (HMM)
poetry run python -m services.regime_hmm.main

# Sentiment analysis (requires AION_LLM_API_KEY and AION_NEWS_API_KEY)
poetry run python -m services.sentiment.main

# Backtesting engine
poetry run python -m services.backtesting.main
```

### Step 6: Start the Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

Edit `frontend/.env.local`:

```bash
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=<generate with: openssl rand -base64 32>
NEXT_PUBLIC_API_URL=http://localhost:8000
```

If you want OAuth login, add your Google and/or GitHub OAuth credentials.
Otherwise, skip those lines.

```bash
npm run dev
```

The frontend starts at `http://localhost:3000`. It connects to the API Gateway
at `http://localhost:8000`.

---

## Running Against Exchange Testnets

By default, the platform is configured for exchange testnets. No configuration
changes are needed for testnet operation -- the defaults handle it.

### Progression from Development to Live Trading

**1. Read-only mode (default)**

```bash
AION_TRADING_ENABLED=false   # default
AION_BINANCE_TESTNET=true    # default
AION_COINBASE_SANDBOX=true   # default
```

Signals are generated, validated, and logged. No orders are sent.

**2. Paper trading**

```bash
AION_TRADING_ENABLED=true
AION_PAPER_TRADING_MODE=true
```

The Execution agent simulates fills locally. No exchange API calls are made.
Useful for testing the full pipeline without exchange credentials.

**3. Testnet trading**

```bash
AION_TRADING_ENABLED=true
AION_PAPER_TRADING_MODE=false
AION_BINANCE_TESTNET=true
AION_COINBASE_SANDBOX=true
```

Real orders are sent to exchange testnet APIs. You need testnet API keys
configured per-user in the platform. No real money is at risk.

**4. Live trading**

```bash
AION_TRADING_ENABLED=true
AION_PAPER_TRADING_MODE=false
AION_BINANCE_TESTNET=false
AION_COINBASE_SANDBOX=false
```

Real orders on production exchanges. Ensure `AION_SECRET_KEY` is changed from
the default, circuit breaker thresholds are reviewed, and PagerDuty alerting
is configured.

---

## Common Workflows

### Add a New Exchange Connector

1. **Create the connector module** in `services/execution/` or a shared
   location under `libs/`. The platform uses [ccxt](https://github.com/ccxt/ccxt)
   v4.2+ for exchange connectivity.

2. **Add a testnet/sandbox flag** to `libs/config/settings.py`:
   ```python
   KRAKEN_SANDBOX: bool = Field(default=True)
   ```

3. **Add the exchange to the Ingestion agent** so it subscribes to the
   exchange's WebSocket feed for symbols in `AION_TRADING_SYMBOLS`.

4. **Add the exchange to the Execution agent** so it can route orders to the
   new exchange based on symbol configuration.

5. **Add a migration** for any exchange-specific schema needs (e.g., fee
   structures) in `migrations/versions/`.

6. **Write tests**: Add unit tests mocking the ccxt exchange class, and
   contract tests validating order format against the exchange's API.

### Add a New Agent

The platform follows a consistent agent pattern. Each agent is a standalone
service in `services/<agent_name>/`.

1. **Create the service directory**:
   ```
   services/
     my_agent/
       __init__.py
       main.py
   ```

2. **Implement the agent** in `main.py`. The agent should:
   - Import `settings` from `libs.config`
   - Connect to Redis for pub/sub messaging
   - Connect to TimescaleDB if it needs persistent state
   - Expose a health check endpoint via FastAPI/uvicorn

3. **Register the agent's port** in the project documentation and ensure it
   does not conflict with existing services (see
   `docs/configuration.md` for the port map).

4. **Add the agent to `pyproject.toml` packages** if it introduces new
   importable modules under `libs/`.

5. **Write tests** under `tests/unit/` and `tests/integration/`.

### Add a New Signal Source

Signal sources (TA indicators, regime models, sentiment scores) publish to
Redis channels that the Strategy agent subscribes to.

1. **Define the signal schema** using Pydantic models in `libs/`.

2. **Implement the signal producer** as a new agent or as a module within an
   existing agent (e.g., a new indicator in the TA Agent).

3. **Publish signals to Redis** using the established channel naming
   convention.

4. **Subscribe in the Strategy agent** to consume the new signal type.

5. **Add the signal to the Validation agent** if it requires fast-gate checks.

6. **Backtest the signal** using the Backtesting service to validate its
   contribution before enabling it in live trading.

---

## Testing Strategy

### Test Locations

```
tests/
  unit/           # Fast, no external dependencies, mocked I/O
  contract/       # Validate message schemas between agents
  integration/    # Require running Redis + TimescaleDB
  e2e/            # Full pipeline tests
```

### Running Tests

**Unit tests** (no infrastructure required):

```bash
poetry run pytest tests/unit -v
```

With coverage:

```bash
poetry run pytest tests/unit -v --cov=libs --cov=services --cov-report=term-missing
```

**Integration tests** (require Redis + TimescaleDB):

Start the test infrastructure first. The test compose file uses offset ports
(Redis on 6380, TimescaleDB on 5433) so it does not conflict with your
development containers.

```bash
docker compose -f deploy/docker-compose.test.yml up -d
poetry run pytest tests/integration -v
docker compose -f deploy/docker-compose.test.yml down -v
```

Or use the test runner script, which handles setup and teardown automatically:

```bash
bash scripts/run_tests.sh
```

The script:
1. Starts `deploy/docker-compose.test.yml`
2. Waits for health checks
3. Exports test environment variables (`AION_REDIS_URL`, `AION_DATABASE_URL`,
   `AION_TRADING_ENABLED=false`)
4. Runs `pytest` with coverage
5. Tears down containers on exit (via `trap`)

**Contract tests**:

```bash
poetry run pytest tests/contract -v
```

**End-to-end tests**:

```bash
poetry run pytest tests/e2e -v
```

**All tests via Makefile**:

```bash
make test-unit          # Unit tests with coverage
make test-integration   # Integration tests
make test-all           # Unit + integration
```

### Mocking Exchanges

For unit tests, mock the ccxt exchange classes instead of calling real APIs.
The platform uses ccxt v4.2+, so mock the async methods:

```python
from unittest.mock import AsyncMock, patch

@patch("ccxt.pro.binance")
async def test_order_submission(mock_binance):
    mock_exchange = AsyncMock()
    mock_exchange.create_order.return_value = {
        "id": "test-order-123",
        "status": "closed",
        "filled": 0.01,
        "price": 50000.0,
    }
    mock_binance.return_value = mock_exchange

    # ... test your execution logic ...
    mock_exchange.create_order.assert_called_once()
```

For integration tests against exchange testnets, use the test configuration
in `config/.env.test` which sets `AION_BINANCE_TESTNET=true` and
`AION_COINBASE_SANDBOX=true`.

### Backtesting

The Backtesting service (`services/backtesting/`) runs historical simulations
against cold-tier data.

```bash
# Start the backtesting service
poetry run python -m services.backtesting.main
```

- Backtest jobs are submitted via the API Gateway and queued in the service.
- The queue depth is limited by `AION_BACKTEST_MAX_QUEUE_DEPTH` (default: 100).
- Historical data is available up to `COLD_BACKTEST_BOUNDARY_MONTHS` (12 months)
  back from the cold tier.
- Results are stored in the `backtest_results` table (migration
  `008_backtest_results.sql`).

### LLM Prompt Testing

If you work on the Analyst or Sentiment agents, use
[promptfoo](https://www.promptfoo.dev/) to regression-test LLM prompts:

```bash
npx promptfoo eval --config promptfooconfig.yaml
```

### CI Pipeline

The GitHub Actions CI pipeline (`.github/workflows/ci.yml`) runs on pushes and
PRs to `main` and `develop`. It includes:

| Job | What It Does |
|-----|-------------|
| `lint` | Runs `black --check`, `isort --check-only`, `ruff check`, and `mypy` on `libs/` and `services/`. |
| `test-unit` | Installs dependencies with Poetry, runs `pytest tests/unit`. |
| `test-integration` | Spins up Redis (port 6380) and TimescaleDB (port 5433) as GitHub Actions services, runs `pytest tests/integration`. |
| `security-scan` | Runs `safety check` for dependency vulnerabilities and `bandit` for static security analysis. |
| `frontend-lint` | Runs `eslint` and `tsc --noEmit` on the frontend. |
| `docker-build` | Validates that the Docker image builds successfully using `docker/base.Dockerfile`. |

---

## Makefile Reference

| Target | Command | Description |
|--------|---------|-------------|
| `make install` | `poetry install` | Install all Python dependencies. |
| `make lint` | `black`, `isort`, `ruff`, `mypy` | Format code and run linters. |
| `make test-unit` | `pytest tests/unit` | Run unit tests with coverage. |
| `make test-integration` | `pytest tests/integration` | Run integration tests (requires infrastructure). |
| `make test-all` | `test-unit` + `test-integration` | Run all test suites. |
| `make run-local` | `docker compose up --build -d` | Start infrastructure containers. |
| `make build` | `docker compose build` | Build Docker images. |

---

## Troubleshooting

### Redis Connection Refused

**Symptom**: `ConnectionError: Error connecting to redis://localhost:6379`

**Fix**: Ensure the Redis container is running and healthy:

```bash
docker compose -f deploy/docker-compose.yml ps redis
```

If the container is running but you still get errors, check the password. The
default compose configuration requires authentication:

```bash
# Test the connection manually
redis-cli -a changeme_redis_dev ping
```

Ensure `AION_REDIS_URL` includes the password if you changed it from the
default, e.g., `redis://:mypassword@localhost:6379/1`.

### TimescaleDB Connection Refused

**Symptom**: `asyncpg.exceptions.ConnectionDoesNotExistError`

**Fix**: Verify the container is healthy and the database exists:

```bash
docker compose -f deploy/docker-compose.yml ps timescaledb
docker exec -it $(docker compose -f deploy/docker-compose.yml ps -q timescaledb) \
  psql -U postgres -c "\l"
```

You should see `aion_trading` in the database list. If not, the container may
have started with a different `POSTGRES_DB` value. Recreate it:

```bash
docker compose -f deploy/docker-compose.yml down -v
docker compose -f deploy/docker-compose.yml up -d
```

### Migration Failures

**Symptom**: `Failed to execute migrations/versions/00X_*.sql`

**Fix**: Migrations are not idempotent by default. If you have already applied
some migrations, later ones may fail on "relation already exists" errors. The
script logs the error and continues. If you need a clean slate:

```bash
docker compose -f deploy/docker-compose.yml down -v   # destroys data
docker compose -f deploy/docker-compose.yml up -d
poetry run python scripts/migrate.py
```

### Hot-Path Hangs on Startup

**Symptom**: The Hot-Path agent starts but stops processing signals. CPU is idle.

**Cause**: The Strategy Agent has not yet hydrated its state from TimescaleDB.
The Hot-Path waits for strategy state before routing signals.

**Fix**: Always start the Strategy Agent **before** the Ingestion and Hot-Path
agents. See the startup sequence in `docs/configuration.md`.

### WebSocket Disconnects on Expired JWT

**Symptom**: The frontend WebSocket connection drops after a period of inactivity.
Reconnection fails with 401.

**Cause**: The access token embedded in the WebSocket connection has expired, and
WebSocket does not support transparent token refresh like HTTP does.

**Workaround**: Implement client-side logic to detect the disconnect, refresh the
token via the REST API, and reconnect the WebSocket with the new token. This is
a known issue tracked in the project changelog.

### Port 8080 Conflicts

**Symptom**: `Address already in use: ('0.0.0.0', 8080)`

**Cause**: Multiple services (Ingestion, Archiver, Analyst, Tax) are configured
to use port 8080 by default.

**Fix**: Override the port when starting a service:

```bash
# Example: Start Ingestion on 8080 and Archiver on 8087
poetry run uvicorn services.ingestion.main:app --port 8080
poetry run uvicorn services.archiver.main:app --port 8087
```

Assign unique ports to each service and update your local notes. This conflict
is tracked in the project changelog.

### Python 3.14 and numpy

**Symptom**: `pip install numpy` fails with compilation errors on Python 3.14.

**Cause**: As of this writing, numpy does not ship prebuilt wheels for Python
3.14. Building from source requires a C compiler and may still fail.

**Fix**: Use Python 3.11 (the version specified in `pyproject.toml` and
`docker/base.Dockerfile`). The platform targets `^3.11` and CI runs on 3.11.

### Test Infrastructure Port Conflicts

**Symptom**: Integration tests fail because ports 6380 or 5433 are in use.

**Cause**: The test compose file (`deploy/docker-compose.test.yml`) maps Redis
to port 6380 and TimescaleDB to 5433 to avoid conflicting with development
containers. Another process may be using those ports.

**Fix**: Stop any conflicting processes, or modify the test compose file ports.
Ensure the test environment variables match:

```bash
export AION_REDIS_URL="redis://localhost:6380/1"
export AION_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/aion_test"
```

### Linting Failures in CI

**Symptom**: CI fails on the `lint` job even though code looks correct locally.

**Fix**: Run the formatters locally before committing:

```bash
make lint
```

This runs `black`, `isort`, `ruff`, and `mypy` in sequence. The CI job runs
these in check mode, so any formatting differences cause a failure.

### Docker Build Fails on Apple Silicon

**Symptom**: `docker build` fails with architecture-related errors on M1/M2 Macs.

**Fix**: The Dockerfile uses `python:3.11-slim` which supports multi-arch.
Ensure Docker Desktop is up to date and Rosetta emulation is enabled in
Docker Desktop settings if building x86 images.

---

## Further Reading

- `docs/configuration.md` -- Complete environment variable and constants reference
- `docs/RUNTIME_ARCHITECTURE.md` -- Runtime architecture and agent communication
- `docs/WALKTHROUGH.md` -- End-to-end platform walkthrough
- `docs/SHUTDOWN.md` -- Graceful shutdown procedures
- `docs/adr/` -- Architecture Decision Records
- `docs/runbooks/` -- Operational runbooks
