# Aion Trading Platform

A high-performance, agentic cryptocurrency trading engine with ML prediction agents, adversarial debate consensus, local SLM inference, and a Next.js dashboard.

---

## System Overview

### Core Capabilities
- **Latency-Optimized Hot Path**: 11-stage signal pipeline with 50ms deadline
- **ML Prediction Agents**: TA multi-timeframe confluence (8 indicators), HMM regime classification, LLM sentiment scoring, adversarial bull/bear debate
- **Dynamic Agent Weighting**: EWMA-based performance tracking replaces hardcoded weights with data-driven confidence adjustments
- **Human-in-the-Loop Gate**: Configurable HITL approval for high-risk trades with real-time WebSocket UI
- **Local SLM Inference**: Quantized language model inference via llama-cpp-python, eliminating API costs with cloud fallback
- **Dual Backtesting Engines**: Sequential replay + vectorized numpy engine with parameter grid sweep (100-1000x speedup)
- **Dynamic Risk Management**: Circuit breakers, drawdown-aware position sizing, live PnL state hydration
- **Dual-Layer Validation**: Sync fast-gate (50ms) + async LLM audit checks
- **Paper Trading Mode**: Mandatory 30-day dry run on testnet before live trading
- **Premium Control Plane**: Next.js 16 dashboard with equity curves, agent scores, trade approvals, and risk monitors

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
    │   Hot Path :8082    │     │   Backtesting :8086      │     │  ML Agents            │
    │ (11-stage pipeline) │     │   Sequential + VectorBT  │     │  TA :8090             │
    │                     │     │   /backtest/sweep         │     │  HMM :8091            │
    │ Reads agent scores  │     │                          │     │  Sentiment :8092      │
    │ + dynamic weights   │     │                          │     │  SLM Inference :8095  │
    │ from Redis          │     │                          │     │  Debate :8096         │
    └─────────┬───────────┘     └──────────────────────────┘     │  Analyst :8087        │
              │                                                  │  (weight engine)      │
    ┌─────────▼───────────┐     ┌──────────────────────────┐     └───────────────────────┘
    │  Execution :8083    │     │  PnL :8084               │
    │  (order ledger)     │     │  (daily tracking, Redis)  │
    │  Agent score capture │     │  Outcome tagging          │
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

**Terminal 6 — Analyst Agent (dynamic weight engine)**
```bash
poetry run uvicorn services.analyst.src.main:app --host 0.0.0.0 --port 8087 --reload
```

**Terminal 7 — TA Multi-Timeframe Agent**
```bash
poetry run uvicorn services.ta_agent.src.main:app --host 0.0.0.0 --port 8090 --reload
```

**Terminal 8 — Regime HMM Agent**
```bash
poetry run uvicorn services.regime_hmm.src.main:app --host 0.0.0.0 --port 8091 --reload
```

**Terminal 9 — Sentiment Agent**
```bash
poetry run uvicorn services.sentiment.src.main:app --host 0.0.0.0 --port 8092 --reload
```

**Terminal 10 — Local SLM Inference (optional, requires GGUF model)**
```bash
poetry run uvicorn services.slm_inference.src.main:app --host 0.0.0.0 --port 8095 --reload
```

**Terminal 11 — Debate Agent**
```bash
poetry run uvicorn services.debate.src.main:app --host 0.0.0.0 --port 8096 --reload
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
| Hot Path | 8082 | 11-stage signal processing pipeline | Yes |
| Execution | 8083 | Order ledger, exchange routing, agent score capture | Yes |
| PnL | 8084 | P&L calculation, daily tracking, outcome tagging | Yes |
| Backtesting | 8086 | Sequential + vectorized strategy replay engine | For backtest page |
| Analyst | 8087 | Dynamic agent weight computation engine (5-min EWMA) | For ML features |
| TA Agent | 8090 | Multi-timeframe TA confluence scoring (8 indicators) | For ML features |
| Regime HMM | 8091 | Hidden Markov Model regime classification | For ML features |
| Sentiment | 8092 | LLM-based news sentiment scoring (local or cloud) | For ML features |
| SLM Inference | 8095 | Local quantized model inference (Phi-3 / GGUF) | Optional |
| Debate | 8096 | Adversarial bull/bear debate consensus scoring | For ML features |
| Frontend | 3000 | Next.js dashboard | Yes |

---

## Frontend Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — portfolio P&L, agent scores, risk monitor |
| `/profiles` | Trading profile CRUD, JSON rule editor |
| `/backtest` | Submit backtests, view equity curves and trade tables |
| `/paper-trading` | 30-day paper trading progress tracker |
| `/approval` | HITL trade approval — pending signals, agent scores, approve/reject |
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
| POST | `/backtest` | Submit backtest job (sequential or vectorbt engine) |
| GET | `/backtest/{job_id}` | Get backtest results |
| POST | `/backtest/sweep` | Parameter grid sweep using vectorized engine |

### ML Agents & Risk
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agents/status` | Get all agent scores (TA, sentiment, HMM, debate) |
| GET | `/agents/risk/{profile_id}` | Get risk metrics for a profile |
| GET | `/agents/risk` | Get risk metrics for all profiles |

### HITL (Human-in-the-Loop)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/hitl/respond` | Submit approval/rejection for a pending trade |

### SLM Inference
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/completions` | OpenAI-compatible text completion |
| POST | `/v1/sentiment` | Structured sentiment analysis |
| GET | `/health` | Health check with GPU memory metrics |

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

## Hot Path Pipeline (11 Stages)

```
Tick → (1)  Strategy Eval (8 indicators: RSI, MACD, ATR, ADX, Bollinger, OBV, Choppiness + Regime)
     → (2)  Abstention Check
     → (3)  Regime Dampener (dual: rule-based + HMM Redis)
     → (3b) Agent Modifier (TA + sentiment + debate scores, dynamic weights from Redis)
     → (4)  Circuit Breaker (daily loss limit, hydrated from PnL service)
     → (5)  Blacklist Check
     → (6)  Risk Gate (dynamic position sizing)
     → (6b) HITL Gate (human approval for high-risk trades, configurable triggers)
     → (7)  Validation Fast Gate (50ms timeout)
     → (8)  Order Approved
```

---

## Multi-Agent SLM Architecture

The platform implements a multi-agent SLM (Small Language Model) architecture across 6 integrated features:

### Technical Indicators (Phase 1)
8 streaming indicators with O(1) updates: RSI, MACD, ATR, EMA + ADX, Bollinger Bands, OBV, Choppiness Index. New indicators enrich TA confluence scoring with trend strength (ADX), mean reversion (%B), volume confirmation (OBV), and regime filtering (Choppiness).

### Dynamic Agent Weighting (Phase 2)
Replaces hardcoded confidence adjustments with EWMA-tracked performance weights. The Analyst service (port 8087) recomputes weights every 5 minutes from closed position outcomes. Execution service snapshots agent scores at trade time; PnL service tags win/loss outcomes for the feedback loop.

### HITL Execution Gate (Phase 3)
Human-in-the-loop approval for trades that meet configurable trigger conditions: low confidence, HIGH_VOLATILITY regime, or large trade size. Fail-safe: timeout = reject. Frontend approval page at `/approval` with real-time WebSocket updates.

### Local SLM Inference (Phase 4)
FastAPI service hosting quantized GGUF models via `llama-cpp-python`. Sentiment scorer uses a protocol-based backend abstraction with fallback chain: local SLM → cloud Claude API → neutral fallback. Configurable via `AION_LLM_BACKEND = "cloud" | "local" | "auto"`.

### Adversarial Debate (Phase 5)
Bull and Bear agents argue for/against positions using market context (indicators, regime, agent scores). A Judge synthesizes the debate into a `debate_score` (-1 to +1) and `debate_confidence`. Runs every 5 minutes per symbol. Output feeds into agent_modifier with dynamic weight.

### Vectorized Backtesting (Phase 6)
Numpy-based vectorized backtesting engine alongside the sequential simulator. Converts strategy rules into vectorized signal arrays for 100-1000x faster parameter sweeps. `POST /backtest/sweep` endpoint supports grid search over any rule parameter.

---

## Testing

### Unit Tests

```bash
# Run all unit tests (126 tests)
poetry run pytest tests/unit/ -v

# Run with coverage
poetry run pytest tests/unit/ --cov=services --cov=libs -v
```

### Test Coverage by Feature
| Feature | Tests | File |
|---------|-------|------|
| Core indicators (RSI, MACD, ATR) | 3 | `test_indicators.py` |
| New indicators (ADX, Bollinger, OBV, Choppiness) | 20 | `test_new_indicators.py` |
| Dynamic agent weighting (EWMA, modifier) | 15 | `test_dynamic_weights.py` |
| HITL execution gate | 8 | `test_hitl_gate.py` |
| SLM backend protocol & fallback chain | 20 | `test_slm_backend.py` |
| Adversarial debate engine | 20 | `test_debate.py` |
| VectorBT backtesting & sweep | 18 | `test_vectorbt.py` |
| Backtesting simulator | 5 | `test_backtesting.py` |
| Regime dampener & agent modifier | 7 | `test_regime_dampener.py` |
| Risk wiring (circuit breaker, risk gate) | 10 | `test_risk_wiring.py` |

### LLM Prompt Evaluations (Promptfoo)

The platform uses [promptfoo](https://promptfoo.dev) to evaluate and regression-test every LLM prompt in the system. This ensures that model outputs remain correct, safe, and aligned with trading logic as prompts or models change.

#### Structure

```
prompts/                         # Extracted prompt templates (shared by configs + services)
  trading-signal.txt             # Trading signal analyzer prompt
  risk-assessor.txt              # Risk assessment module prompt
  sentiment-scorer.txt           # Sentiment scoring prompt
  debate/                        # Adversarial debate prompts
    bull.txt                     # Bull advocate prompt template
    bear.txt                     # Bear advocate prompt template
    judge.txt                    # Impartial judge prompt template
promptfooconfig.yaml             # Trading signal eval suite (15 tests)
promptfoo-risk-assessor.yaml     # Risk assessor eval suite (13 tests)
promptfoo-sentiment.yaml         # Sentiment scorer eval suite (12 tests)
promptfoo-redteam.yaml           # Red team adversarial security scan
```

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

---

## Configuration

### Key Environment Variables (Phase 1-6 additions)

| Variable | Default | Description |
|----------|---------|-------------|
| `AION_LLM_BACKEND` | `"cloud"` | LLM backend mode: `"cloud"`, `"local"`, or `"auto"` (local with cloud fallback) |
| `AION_SLM_INFERENCE_URL` | `"http://localhost:8095"` | URL of the local SLM inference service |
| `AION_SLM_MODEL_PATH` | `""` | Path to GGUF model file for local inference |
| `AION_SLM_CONTEXT_LENGTH` | `4096` | Context window for local SLM |
| `AION_SLM_GPU_LAYERS` | `-1` | GPU layers for model offloading (-1 = all) |
| `AION_HITL_ENABLED` | `false` | Enable human-in-the-loop execution gate |
| `AION_HITL_SIZE_THRESHOLD_PCT` | `5.0` | Trade size % that triggers HITL approval |
| `AION_HITL_CONFIDENCE_THRESHOLD` | `0.5` | Confidence below this triggers HITL |
| `AION_HITL_TIMEOUT_S` | `60` | Seconds to wait for human response (fail-safe: reject) |

See [docs/configuration.md](docs/configuration.md) for the complete reference.

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
| ML | hmmlearn (HMM), Claude API (sentiment), llama-cpp-python (local SLM) |
| Exchange | CCXT |
| Vectorized Compute | NumPy |
