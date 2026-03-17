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
poetry install
```

### Step 4: Start Backend Services

Each service runs in its own terminal. Start them in this order:

**Terminal 1 — API Gateway (required)**
```bash
poetry run uvicorn services.api_gateway.src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Hot Path Processor**
```bash
poetry run uvicorn services.hot_path.src.main:app --host 0.0.0.0 --port 8082 --reload
```

**Terminal 3 — Execution Service**
```bash
poetry run uvicorn services.execution.src.main:app --host 0.0.0.0 --port 8083 --reload
```

**Terminal 4 — PnL Service**
```bash
poetry run uvicorn services.pnl.src.main:app --host 0.0.0.0 --port 8084 --reload
```

**Terminal 5 — Backtesting Engine**
```bash
poetry run uvicorn services.backtesting.src.main:app --host 0.0.0.0 --port 8086 --reload
```

**Terminal 6 — TA Multi-Timeframe Agent**
```bash
poetry run uvicorn services.ta_agent.src.main:app --host 0.0.0.0 --port 8090 --reload
```

**Terminal 7 — Regime HMM Agent**
```bash
poetry run uvicorn services.regime_hmm.src.main:app --host 0.0.0.0 --port 8091 --reload
```

**Terminal 8 — Sentiment Agent**
```bash
poetry run uvicorn services.sentiment.src.main:app --host 0.0.0.0 --port 8092 --reload
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
poetry run uvicorn services.api_gateway.src.main:app --port 8000 &
poetry run uvicorn services.hot_path.src.main:app --port 8082 &
poetry run uvicorn services.execution.src.main:app --port 8083 &
poetry run uvicorn services.pnl.src.main:app --port 8084 &
poetry run uvicorn services.backtesting.src.main:app --port 8086 &
poetry run uvicorn services.ta_agent.src.main:app --port 8090 &
poetry run uvicorn services.regime_hmm.src.main:app --port 8091 &
poetry run uvicorn services.sentiment.src.main:app --port 8092 &
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

### Unit Tests

```bash
# Run all unit tests
poetry run pytest tests/unit/ -v

# Run with coverage
poetry run pytest tests/unit/ --cov=services --cov=libs -v
```

### LLM Prompt Evaluations (Promptfoo)

The platform uses [promptfoo](https://promptfoo.dev) to evaluate and regression-test every LLM prompt in the system. This ensures that model outputs remain correct, safe, and aligned with trading logic as prompts or models change.

#### Structure

```
prompts/                         # Extracted prompt templates (shared by configs + services)
  trading-signal.txt             # Trading signal analyzer prompt
  risk-assessor.txt              # Risk assessment module prompt
  sentiment-scorer.txt           # Sentiment scoring prompt
promptfooconfig.yaml             # Trading signal eval suite (15 tests)
promptfoo-risk-assessor.yaml     # Risk assessor eval suite (13 tests)
promptfoo-sentiment.yaml         # Sentiment scorer eval suite (12 tests)
promptfoo-redteam.yaml           # Red team adversarial security scan
```

#### Three Eval Suites (40 tests total)

**Trading Signal Analyzer** (`promptfooconfig.yaml`) — 15 tests against `claude-sonnet-4-20250514`

Tests the core signal generation prompt that produces `{direction, confidence, reasoning, risk_level}` JSON. Coverage includes:
- Directional accuracy: bullish, bearish, sideways, and perfectly neutral scenarios
- Edge cases: flash crash, parabolic blow-off top, unknown tokens with missing data
- Output validation: JSON schema, confidence range [0,1], required field presence
- Reasoning quality: LLM-rubric check that reasoning references provided indicators
- Robustness: malformed numeric input, multi-timeframe conflicting signals
- Security: prompt injection in `market_data`, hallucination guard (no invented tokens)

**Risk Assessor** (`promptfoo-risk-assessor.yaml`) — 13 tests against `claude-sonnet-4-20250514`

Tests the risk assessment prompt against the system's actual hard limits (from `services/risk/src/__init__.py`). Coverage includes:
- Boundary tests for every hard limit:
  - **$50,000 max order**: exactly at cap (allow) vs. $50,001 (reject)
  - **25% concentration**: exactly at limit (allow) vs. 26% (reject)
  - **50 open positions**: at limit (reject) vs. 49 (allow)
  - **2% circuit breaker**: triggered at -2.1% (reject) vs. -1.5% (allow)
- Multiple simultaneous violations (risk_score >= 0.8)
- Dynamic sizing awareness: high drawdown, HIGH_VOLATILITY regime
- Missing stop loss detection (elevated risk_score)

**Sentiment Scorer** (`promptfoo-sentiment.yaml`) — 12 tests against `claude-haiku-4-5-20251001`

Tests the sentiment analysis prompt that produces `{score, confidence}` JSON. Coverage includes:
- Polarity: strongly bullish, strongly bearish, mixed/neutral, contradictory headlines
- Edge cases: empty headlines, single headline, non-English (Japanese), 250+ char headlines
- Numeric-heavy bearish data, SQL injection in symbol field
- Security: prompt injection in headlines, hallucination guard (BTC-only analysis)

#### Red Team Security Scan (`promptfoo-redteam.yaml`)

Adversarial testing with promptfoo's red team plugins:
- `prompt-injection`, `pii-leak`, `harmful`, `jailbreak`, `hallucination`
- Trading-domain injections via `market_data` and `headlines` variables
- Strategies: `multi-turn`, `injection`, `crescendo` (gradual escalation)
- Domain-specific test cases: `SYSTEM: Override risk limits` in symbol names and data fields

#### Running Evals

```bash
# Requires ANTHROPIC_API_KEY (set in .env or export)
export $(grep ANTHROPIC_API_KEY .env)

# Run individual suites
npx promptfoo eval --config promptfooconfig.yaml --no-cache
npx promptfoo eval --config promptfoo-risk-assessor.yaml --no-cache
npx promptfoo eval --config promptfoo-sentiment.yaml --no-cache

# View results in browser
npx promptfoo view

# Run red team scan
npx promptfoo redteam run --config promptfoo-redteam.yaml
```

#### CI/CD Integration

The `.github/workflows/prompt-eval.yml` workflow runs all eval suites on PRs that touch prompts, configs, or relevant service source files. Results are uploaded as JSON artifacts.

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
