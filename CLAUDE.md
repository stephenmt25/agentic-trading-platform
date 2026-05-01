# Praxis Trading Platform — Claude Code Instructions

> *Praxis*: theory into practice, grounded wisdom, decisive action.
>
> This file is **domain truth only** — project structure, financial precision rules, codebase conventions, and security triggers. General engineering guidance (decomposition, verification protocols, effort allocation, species framework) lives in [`docs/AGENT-FRAMEWORK.md`](docs/AGENT-FRAMEWORK.md). Invoke that explicitly when relevant.

---

## 1 · Project Overview & Structure

Agentic cryptocurrency trading platform with 19 microservices, ML prediction agents, and a Next.js dashboard. Backend is Python 3.11+ (FastAPI, asyncio), frontend is Next.js 16 (React 19, TypeScript). Services communicate via Redis Streams/Pub/Sub, persist to TimescaleDB.

Architecture is governed by a merged architecture document (v2.0) organized into Phase 1 (Core Trading Engine) and Phase 2 (ML Intelligence and Scale). A developer execution blueprint serves as the AI execution contract for sprint-level work. **Specification documents are contracts** — when a spec exists, treat it as binding. Deviations require justification in `DECISIONS.md`.

```
./ (aion-trading)
├── libs/           # Shared Python libraries (config, core, exchange, indicators, messaging, observability, storage)
├── services/       # 19 microservices (api_gateway, hot_path, execution, pnl, validation, ta_agent,
│                   #   analyst, archiver, backtesting, debate, ingestion, logger, rate_limiter,
│                   #   regime_hmm, risk, sentiment, slm_inference, strategy, tax)
├── frontend/       # Next.js 16 dashboard
├── migrations/     # 11 SQL migration files (in migrations/versions/)
├── docs/           # Markdown documentation (incl. AGENT-FRAMEWORK.md, DOCUMENTATION-GAPS.md, TECH-DEBT-REGISTRY.md)
├── deploy/         # Docker Compose, Kubernetes, Terraform
├── docker/         # Dockerfiles
├── config/         # Configuration files
├── tests/          # Unit, contract, and e2e tests
├── prompts/        # LLM prompt templates
├── scripts/        # Utility scripts (migrate.py, daily_report.py)
├── pyproject.toml  # Python project config (Poetry)
├── Makefile        # Build/run shortcuts
├── run_all.sh      # Script to launch all services
└── promptfoo*.yaml # LLM prompt evaluation configs
```

---

## 2 · Conventions, Constraints & Known Defects

Single source of truth for what is enforced, what is expected, and what is broken.

### 2A — Financial Precision (ZERO TOLERANCE)

- ALL financial values must use `Decimal` (Python) / `NUMERIC` (SQL). Never `float`. Never `double`. No exceptions.
- Type aliases (`Price`, `Quantity`, `Percentage` = `Decimal`) are defined in `libs/core/types.py` — use them.
- **Known defect**: 110+ `float()` conversions exist in financial code paths. These are tracked bugs, NOT patterns to follow. Do not add more.
- **Known defect**: `backtest_results` table uses `DOUBLE PRECISION`. This is a known bug. Do not replicate this in new tables.

The `edit-validator.sh` hook blocks new `float(` introductions in `services/execution|pnl|risk|strategy/`.

### 2B — Codebase Structure Conventions

- All enums are in `libs/core/enums.py`. Do not define enums elsewhere. Do not infer enum values — they must be explicitly defined.
- All Pydantic schemas are in `libs/core/schemas.py`.
- Settings via Pydantic BaseSettings with `PRAXIS_` env var prefix in `libs/config/settings.py`.
- Services follow the pattern: `services/<name>/src/main.py` with FastAPI + uvicorn.
- Redis Streams (ordered) and Pub/Sub (broadcast) channels are defined in `libs/messaging/channels.py`. **Do not invent channel names** — verify against this file. The `edit-validator.sh` hook blocks invented channel names.

### 2C — Architectural Constraints

- **Phase boundary**: Phase 1 (Core Trading Engine) scope must not bleed into Phase 2 (ML Intelligence and Scale). Do not introduce ML-heavy or multi-agent patterns into Phase 1 work unless explicitly approved.
- **Architecture document is the contract**: The merged architecture doc (v2.0) defines the system boundary. Deviations require justification logged in `DECISIONS.md`.
- **Startup ordering**: Services must follow the documented startup sequence. Changing startup order requires explicit human approval. Always use `bash run_all.sh` — never start/stop services individually.
- **Database schemas first**: No dependent code may be written before the schema it depends on exists and is verified. Missing schema = blocking issue — stop and report.
- **Profile config model**: `trading_profiles.pipeline_config` (the canvas) is authoritative for what a profile does. `trading_profiles.strategy_rules` is a build artifact compiled from the canvas's `strategy_eval` node config — see `libs/core/pipeline_compiler.py`. Saving the canvas via `PUT /agent-config/{profile_id}/pipeline` updates both atomically. Direct edits to `strategy_rules` (e.g., via `PUT /profiles/{id}`) still work for the user-facing creation flow but should be considered a write into a single computed field — the long-term path is canvas-only edits.

### 2D — Resolved Defects (2026-03-27) & Remaining Gaps

| Defect | Status |
|---|---|
| `float()` conversions in financial code paths | **RESOLVED** — all financial calculations use `Decimal` |
| `backtest_results` table uses `DOUBLE PRECISION` | **RESOLVED** — migration 009 converts to `DECIMAL(20,8)` |
| CHECK_3 (Bias) validation is stubbed | **RESOLVED** — rolling z-score bias detection implemented |
| Rate limiter service always returns `allowed=True` | **RESOLVED** — Redis sliding-window rate limiting implemented |
| Kill switch / emergency shutdown | **RESOLVED** — `KillSwitch` via Redis key + API endpoint |
| Position-level stop-loss enforcement | **RESOLVED** — `StopLossMonitor` in PnL tick processor |
| `market_data_ohlcv` volume inflation + OHL sampling error + no gap-fill | **RESOLVED** (2026-04-18) — ingestion uses `watch_ohlcv` (authoritative 1m klines), aggregates higher timeframes in `services/ingestion/src/candle_aggregator.py`, gap-fills via `libs/exchange/backfill.py` on startup/reconnect |

**Remaining:** All MEDIUM code defects (D-14, D-15, D-17) resolved as of 2026-04-03. Open items are architecture doc discrepancies (A-2, A-3, A-4, A-6) and documentation gaps (G-1 through G-7, G-10, G-11). See `docs/DOCUMENTATION-GAPS.md`.

### 2E — Tech Debt Handling

When you encounter tech debt unrelated to your current task: **do not fix it opportunistically.** Append to `docs/TECH-DEBT-REGISTRY.md` (Service, Description, Severity, Effort, Date) and move on. Opportunistic fixes cause scope creep and regressions.

---

## 3 · Service Quick-Reference Map

Consult before greping. Saves exploration tokens.

| Service | Port | Key Libs | Redis Channels |
|---------|------|----------|----------------|
| api_gateway | 8000 | core, config, storage | — (HTTP only) |
| ingestion | 8080 | core, exchange, messaging | pub: stream:market_data |
| validation | 8081 | core, messaging | sub: stream:orders → pub: stream:validation_response |
| hot_path | 8082 | core, indicators, messaging | sub: stream:market_data |
| execution | 8083 | core, exchange, messaging | sub: stream:validation_response |
| pnl | 8084 | core, storage, messaging | pub: pubsub:pnl_updates |
| logger | 8085 | core, observability | sub: multiple |
| backtesting | 8086 | core, storage, indicators | — (on-demand) |
| analyst | 8087 | core | pub: analysis reports |
| archiver | 8088 | core, storage | — (scheduled) |
| tax | 8089 | core, storage | — (on-demand) |
| ta_agent | 8090 | core, indicators | sub: stream:market_data |
| regime_hmm | 8091 | core, indicators (hmmlearn) | pub: regime signals |
| sentiment | 8092 | core | pub: sentiment signals |
| risk | 8093 | core, storage | sub: pubsub:pnl_updates |
| rate_limiter | 8094 | core, messaging (Redis) | — (Redis keys) |
| slm_inference | 8095 | core | — (HTTP inference) |
| debate | 8096 | core | sub: multiple agent signals |
| strategy | (worker) | core, messaging | sub: stream:market_data → pub: stream:orders |

**Redis channels source of truth**: `libs/messaging/channels.py`
**Port assignments source of truth**: `run_all.sh`

---

## 4 · Anti-Patterns That Matter Here

| Mistake | Why It Fails | Correct Approach |
|---|---|---|
| Using `float` in financial code | Rounding errors compound across trades; breaks Decimal contract | Use `Decimal` + type aliases from `libs/core/types.py` |
| Inventing Redis channels or enum values | Breaks contract with existing services; messages never delivered | Verify against `libs/messaging/channels.py` and `libs/core/enums.py` |
| Pulling Phase 2 (ML) patterns into Phase 1 | Complexity Phase 1 can't support; violates phase boundary | Respect the phase boundary |
| Starting services individually | Zombies, port conflicts, stale consumer groups | `bash run_all.sh` always |
| Opportunistic refactors during unrelated work | Scope creep, regressions | Log to `TECH-DEBT-REGISTRY.md` and move on |
| Writing dependent code before schema exists | Breaks on first run; wastes the session | Verify schema first; if missing, stop and report |

---

## 5 · Security-Sensitive Code Protocol

### 5A — Automatic Security Review Triggers

Stop and run a security pass when modifying code in any of these categories:
- Authentication / authorization (JWT, sessions, API keys)
- Financial transactions (order execution, PnL, risk calculations)
- Database queries (SQL, TimescaleDB operations)
- User input processing (API request parsing, form data)
- Secrets / credentials (env vars, config, settings)
- External API calls (exchange APIs, third-party services)

The `security-scan.sh` hook runs an advisory pass automatically on Edit/Write to files under `services/{execution,pnl,risk,strategy,api_gateway,rate_limiter,exchange,auth}/`.

### 5B — Financial Transaction Checklist

Additional domain-specific checks for `services/execution/`, `services/pnl/`, `services/risk/`, `services/strategy/`:

- [ ] Kill switch integration — can trading be halted via `KillSwitch` Redis key?
- [ ] Stop-loss enforcement — `StopLossMonitor` checks position-level stops?
- [ ] Position size limits — maximum position sizes enforced before order submission?
- [ ] Decimal types — ALL calculations use `Decimal`, type aliases from `libs/core/types.py`?
- [ ] Rate limiter — order submission endpoints are rate-limited?

### 5C — ML Service Checklist

Additional domain-specific checks for `services/regime_hmm/`, `services/sentiment/`, `services/ta_agent/`, `services/slm_inference/`:

- [ ] Model input validation — NaN and Infinity values rejected before inference?
- [ ] Output bounding — model outputs clipped to valid ranges before downstream use?
- [ ] Checkpoint safety — model files loaded from trusted paths only?
- [ ] Numerical stability — division-by-zero guards? Log-of-zero guards?
- [ ] Async-safe serving — model inference is thread-safe for concurrent requests?

---

## 6 · Harness Mechanics (Hooks Active in This Project)

- `stale-read-guard.sh` (PreToolUse Edit/Write) — blocks edits to files not Read in this session or modified since last Read.
- `edit-validator.sh` (PreToolUse Edit) — blocks invented Redis channel names and `float(` in financial paths.
- `security-scan.sh` (PostToolUse Edit/Write) — advisory scan on security-sensitive `.py` files.
- `stop-test.sh` (Stop) — runs unit tests when a turn ends if Python files under `services/` or `libs/` were modified (throttled to at most every 15 min). Advisory — does not block.

If a hook blocks you with exit 2, the reason string explains what to fix.

---

*General engineering framework (species classification, decomposition, verification protocol, self-critique, todo-tracking rules, effort allocation) is archived in [`docs/AGENT-FRAMEWORK.md`](docs/AGENT-FRAMEWORK.md). Invoke it by reference when a task genuinely benefits.*
