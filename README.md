# Agentic Trading Platform - Phase 3

A high-performance, deterministic algorithmic trading engine with ML prediction agents, backtesting, and real-time risk management.

---

## System Overview

### Core Capabilities
- **Latency-Optimized Hot Path**: 9-stage signal pipeline with 50ms deadline
- **ML Prediction Agents**: TA multi-timeframe confluence, HMM regime classification, LLM sentiment scoring
- **Real Backtesting Engine**: Replay historical candles through compiled strategy rules with slippage simulation
- **Dynamic Risk Management**: Circuit breakers, drawdown-aware position sizing, live PnL state hydration
- **Dual-Layer Validation**: Sync fast-gate (35ms) + async LLM audit checks
- **Paper Trading Mode**: Mandatory 30-day dry run on testnet before live trading
- **Premium Control Plane**: Next.js 16 dashboard with equity curves, agent scores, and risk monitors

### Architecture
```
                         ┌─────────────────────────────────────────────┐
                         │              Frontend (Next.js)             │
                         │         http://localhost:3000                │
                         └────────────────────┬────────────────────────┘
                                              │
                         ┌────────────────────▼────────────────────────┐
                         │          API Gateway (FastAPI)              │
                         │         http://localhost:8000                │
                         └────────────────────┬────────────────────────┘
                                              │
              ┌───────────────────────────────┼───────────────────────────────┐
              │                               │                               │
    ┌─────────▼──────────┐     ┌──────────────▼───────────┐     ┌────────────▼──────────┐
    │    Hot Path :8082   │     │   Backtesting :8086      │     │  ML Agents            │
    │  (9-stage pipeline) │     │   (replay engine)        │     │  TA :8090             │
    │                     │     │                          │     │  HMM :8091            │
    │  Reads agent scores │     │                          │     │  Sentiment :8092      │
    │  from Redis         │     │                          │     │  (write to Redis)     │
    └─────────┬───────────┘     └──────────────────────────┘     └───────────────────────┘
              │
    ┌─────────▼───────────┐     ┌──────────────────────────┐
    │  Execution :8083    │     │  PnL :8084               │
    │  (order ledger)     │     │  (daily tracking, Redis)  │
    └─────────────────────┘     └──────────────────────────┘
              │
    ┌─────────▼───────────────────────────────────────────────────────────────┐
    │                    Infrastructure (Docker)                              │
    │           Redis :6379          TimescaleDB :5432                        │
    └─────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Docker Desktop (must be running)
- Node.js 20+
- pip (Python package manager)

### Step 1: Start Infrastructure (Redis + TimescaleDB)

```bash
docker compose -f deploy/docker-compose.yml up -d
```

Wait for healthy status:
```bash
docker compose -f deploy/docker-compose.yml ps
```

### Step 2: Apply Database Migrations

```bash
# On Windows (Git Bash / WSL):
for f in migrations/versions/*.sql; do
  docker exec -i $(docker compose -f deploy/docker-compose.yml ps -q timescaledb) psql -U postgres -d aion_trading < "$f"
done
```

### Step 3: Install Python Dependencies

```bash
pip install fastapi uvicorn pydantic pydantic-settings redis asyncpg structlog pyjwt "passlib[bcrypt]" cryptography bcrypt msgpack numpy httpx hmmlearn ccxt
```

### Step 4: Start Backend Services

Each service runs in its own terminal. Start them in this order:

**Terminal 1 — API Gateway (required)**
```bash
PYTHONPATH=. python -m uvicorn services.api_gateway.src.main:app --host 0.0.0.0 --port 8000 --reload
```
Windows PowerShell:
```powershell
$env:PYTHONPATH="."; python -m uvicorn services.api_gateway.src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Hot Path Processor**
```bash
PYTHONPATH=. python -m uvicorn services.hot_path.src.main:app --host 0.0.0.0 --port 8082 --reload
```

**Terminal 3 — Execution Service**
```bash
PYTHONPATH=. python -m uvicorn services.execution.src.main:app --host 0.0.0.0 --port 8083 --reload
```

**Terminal 4 — PnL Service**
```bash
PYTHONPATH=. python -m uvicorn services.pnl.src.main:app --host 0.0.0.0 --port 8084 --reload
```

**Terminal 5 — Backtesting Engine**
```bash
PYTHONPATH=. python -m uvicorn services.backtesting.src.main:app --host 0.0.0.0 --port 8086 --reload
```

**Terminal 6 — TA Multi-Timeframe Agent**
```bash
PYTHONPATH=. python -m uvicorn services.ta_agent.src.main:app --host 0.0.0.0 --port 8090 --reload
```

**Terminal 7 — Regime HMM Agent**
```bash
PYTHONPATH=. python -m uvicorn services.regime_hmm.src.main:app --host 0.0.0.0 --port 8091 --reload
```

**Terminal 8 — Sentiment Agent**
```bash
PYTHONPATH=. python -m uvicorn services.sentiment.src.main:app --host 0.0.0.0 --port 8092 --reload
```

### Step 5: Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## Running Services Summary

| Service | Port | Purpose | Required |
|---------|------|---------|----------|
| Redis | 6379 | State, pub/sub, streams | Yes |
| TimescaleDB | 5432 | Metrics, orders, positions | Yes |
| API Gateway | 8000 | REST API + WebSocket | Yes |
| Hot Path | 8082 | 9-stage signal processing pipeline | Yes |
| Execution | 8083 | Order ledger, exchange routing | Yes |
| PnL | 8084 | P&L calculation, daily tracking | Yes |
| Backtesting | 8086 | Strategy replay engine | For backtest page |
| TA Agent | 8090 | Multi-timeframe TA confluence scoring | For ML features |
| Regime HMM | 8091 | Hidden Markov Model regime classification | For ML features |
| Sentiment | 8092 | LLM-based news sentiment scoring | For ML features |
| Frontend | 3000 | Next.js dashboard | Yes |

### Convenience: Start All Backend Services (Single Command)

```bash
# Unix/Mac/Git Bash — starts all services in background
PYTHONPATH=. python -m uvicorn services.api_gateway.src.main:app --port 8000 &
PYTHONPATH=. python -m uvicorn services.hot_path.src.main:app --port 8082 &
PYTHONPATH=. python -m uvicorn services.execution.src.main:app --port 8083 &
PYTHONPATH=. python -m uvicorn services.pnl.src.main:app --port 8084 &
PYTHONPATH=. python -m uvicorn services.backtesting.src.main:app --port 8086 &
PYTHONPATH=. python -m uvicorn services.ta_agent.src.main:app --port 8090 &
PYTHONPATH=. python -m uvicorn services.regime_hmm.src.main:app --port 8091 &
PYTHONPATH=. python -m uvicorn services.sentiment.src.main:app --port 8092 &
```

---

## Frontend Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — portfolio P&L, agent scores, risk monitor |
| `/profiles` | Trading profile CRUD, JSON rule editor |
| `/backtest` | Submit backtests, view equity curves and trade tables |
| `/paper-trading` | 30-day paper trading progress tracker |
| `/settings` | Exchange keys, security, preferences |

---

## API Endpoints

### Profiles
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/profiles` | List all profiles |
| POST | `/profiles` | Create new profile |
| PUT | `/profiles/{id}` | Update profile rules |
| PATCH | `/profiles/{id}/toggle` | Toggle active status |
| DELETE | `/profiles/{id}` | Soft delete profile |

### Backtesting
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/backtest` | Submit backtest job |
| GET | `/backtest/{job_id}` | Get backtest results |

### ML Agents & Risk
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agents/status` | Get all agent scores (TA, sentiment, HMM) |
| GET | `/agents/risk/{profile_id}` | Get risk metrics for a profile |
| GET | `/agents/risk` | Get risk metrics for all profiles |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/auth/callback` | OAuth callback |
| GET | `/auth/me` | Current user info |
| GET | `/paper-trading/status` | Paper trading metrics |
| POST | `/exchange-keys` | Store exchange API key |
| GET | `/exchange-keys` | List stored keys |

---

## Hot Path Pipeline (9 Stages)

```
Tick → (1) Strategy Eval
     → (2) Abstention Check
     → (3) Regime Dampener (dual: rule-based + HMM Redis)
     → (3b) Agent Modifier (TA + sentiment scores from Redis)
     → (4) Circuit Breaker (daily loss limit, hydrated from PnL service)
     → (5) Blacklist Check
     → (6) Risk Gate (dynamic position sizing)
     → (7) Validation Fast Gate (50ms timeout)
     → (8) Order Approved
```

---

## Testing

```bash
# Run all unit tests
PYTHONPATH=. python -m pytest tests/unit/ -v

# Run with coverage
PYTHONPATH=. python -m pytest tests/unit/ --cov=services --cov=libs -v
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, asyncio |
| Database | TimescaleDB (PostgreSQL 15) |
| Cache/Bus | Redis 7 (Streams + Pub/Sub) |
| Frontend | Next.js 16, React 19, Tailwind CSS 4 |
| Auth | NextAuth.js v4 (Google/GitHub OAuth) |
| Charts | Recharts |
| State | Zustand |
| ML | hmmlearn (HMM), Claude API (sentiment) |
| Exchange | CCXT |
