# Documentation Gaps and Defects

> This document tracks known documentation gaps, code defects discovered during the
> documentation audit, discrepancies between existing docs and actual code, and
> Phase 2 readiness issues. Each item includes a severity, location, and recommended action.

**Audit date**: 2026-03-19
**Last updated**: 2026-03-27

---

## Table of Contents

- [Documentation Gaps](#documentation-gaps)
- [Code Defects](#code-defects)
  - [Financial Precision (CRITICAL)](#financial-precision-critical)
  - [Missing Implementations](#missing-implementations)
  - [Other Issues](#other-issues)
- [Architecture Doc vs Code Discrepancies](#architecture-doc-vs-code-discrepancies)
- [Phase 2 Readiness](#phase-2-readiness)

---

## Documentation Gaps

Items that could not be determined from the codebase alone and require input from the
engineering team.

| # | Gap | Impact | Recommended Action |
|---|-----|--------|--------------------|
| G-1 | No documented SLA targets for services beyond the fast gate (50ms). | Cannot set alerting thresholds or define "degraded" state for non-hot-path services. | Define P95/P99 latency targets for each service endpoint. |
| G-2 | No documented capacity planning guidelines. | Unknown how many symbols or profiles the system supports before performance degrades. | Run load tests and publish results with recommended maximums. |
| G-3 | No documented disaster recovery procedures. | No runbook for database corruption, exchange API outage, or cloud region failure. | Write DR playbook covering each failure domain. |
| G-4 | No documented data retention policy beyond `HOT_DATA_RETENTION_DAYS=7`. | Unclear how long historical candles, fills, and audit logs are retained. Compliance risk. | Define retention tiers (hot/warm/cold) with explicit TTLs. |
| G-5 | No documented monitoring or alerting thresholds. | Unknown what conditions trigger PagerDuty alerts. | Publish alert definitions with severity levels and escalation paths. |
| G-6 | No documented rollback procedures for failed deployments. | Operators have no playbook when a deploy introduces regressions. | Document rollback steps per service, including database migration rollback. |
| G-7 | No documented exchange API key rotation procedures. | Key compromise response time is unknown. Keys may be long-lived. | Document rotation steps and implement automated rotation on a schedule. |
| ~~G-8~~ | ~~Port 8080 collision between 4+ services.~~ | **RESOLVED** (2026-03-27). All services now have unique port assignments (8000–8096). See `run_all.sh`. | — |
| ~~G-9~~ | ~~No documented rate limits per exchange.~~ | **RESOLVED** (2026-03-27). Rate limits now enforced and documented: Binance 1200 req/min, Coinbase 300 req/min, default 600 req/min. Implemented via Redis sorted-set sliding window in `RateLimiterClient`. Queryable via `GET /commands/../quotas` endpoint on rate limiter service (port 8094). | — |
| G-10 | Strategy rules JSON schema not formally documented. | The `strategy_rules` JSONB column is validated by `RuleValidator` but the expected schema is not published. | Extract and publish the JSON Schema from `RuleValidator`. |
| G-11 | No documented maximum number of concurrent WebSocket connections. | Unknown scaling ceiling for real-time market data subscriptions. | Benchmark and document per-process and per-host WebSocket limits. |

---

## Code Defects

### Financial Precision — ALL RESOLVED (2026-03-27)

All financial precision defects have been remediated. The platform now uses `Decimal` (Python)
and `NUMERIC/DECIMAL` (PostgreSQL) for all monetary values throughout the critical trading path.

**What was fixed**: All `float` types and `float()` conversions in financial code paths were
replaced with `Decimal`. The only remaining `float()` calls are at system boundaries where
external APIs require it (CCXT exchange adapters) or for JSON serialization (Redis cache writes).

| # | Description | Fix | Severity |
|---|-------------|-----|----------|
| ~~D-1~~ | `backtest_results` table used `DOUBLE PRECISION` | Migration `009_backtest_decimal_precision.sql` converts all 5 columns to `DECIMAL(20, 8)`. `BacktestResult`/`SimulatedTrade` dataclasses now use `Decimal`. | ~~CRITICAL~~ RESOLVED |
| ~~D-2~~ | `PnLSnapshot` used `float` for all monetary fields | `PnLSnapshot`, `PnLCalculator`, `TaxEstimate`, `USTaxCalculator`, and tax brackets all converted to `Decimal`. Full chain: tick price → PnL calculation → tax → publisher. | ~~CRITICAL~~ RESOLVED |
| ~~D-3~~ | 110+ `float()` conversions in financial code paths | Full sweep completed (2026-04-03): financial float() removed from reconciler, publisher, stop_loss_monitor, risk service, hitl_gate, check_2_hallucination, profiles, schemas. Remaining float() calls annotated `# float-ok` with reason: indicator/numpy interop, CCXT boundary, ML scores, display formatting, or JSON serialization. | ~~CRITICAL~~ RESOLVED |
| ~~D-4~~ | `SignalEvent.confidence` typed as `float` | Changed to `Percentage` (Decimal alias) in `libs/core/schemas.py` | ~~HIGH~~ RESOLVED |
| ~~D-5~~ | `PnlUpdateEvent.pct_return` typed as `float` | Changed to `Percentage` (Decimal alias) in `libs/core/schemas.py` | ~~HIGH~~ RESOLVED |
| ~~D-6~~ | `ThresholdProximityEvent` fields typed as `float` | Changed to `Price`/`Percentage` (Decimal aliases) in `libs/core/schemas.py` | ~~HIGH~~ RESOLVED |
| ~~D-7~~ | `ProfileState` risk fields used `float` | `daily_realised_pnl_pct`, `current_drawdown_pct`, `current_allocation_pct` changed to `Decimal` in `services/hot_path/src/state.py`. `pnl_sync.py` updated to write `Decimal`. | ~~HIGH~~ RESOLVED |

### Missing Implementations

Features that are referenced in comments, configuration, or documentation but have no
functional implementation.

| # | Description | Location | Severity |
|---|-------------|----------|----------|
| ~~D-8~~ | ~~Kill switch / emergency shutdown is not implemented.~~ **RESOLVED** (2026-03-27). Global `KillSwitch` backed by Redis key `praxis:kill_switch`. Checked at top of hot-path before any processing. Toggleable via `POST /commands/kill-switch`. Fails safe (blocks trading) if Redis is unreachable. Activity log maintained. | `services/hot_path/src/kill_switch.py`, `services/hot_path/src/processor.py`, `services/api_gateway/src/routes/commands.py` | ~~HIGH~~ RESOLVED |
| ~~D-9~~ | ~~Position-level stop-loss enforcement is not implemented.~~ **RESOLVED** (2026-03-27). `StopLossMonitor` checks every position on every price tick against the profile's `stop_loss_pct`. Triggers `PositionCloser` when loss exceeds threshold. Wired into the PnL tick processor. | `services/pnl/src/stop_loss_monitor.py`, `services/pnl/src/main.py` | ~~CRITICAL~~ RESOLVED |
| ~~D-10~~ | ~~CHECK_3 (Bias validation) is stubbed.~~ **RESOLVED** (2026-03-27). Now implements rolling z-score bias detection over 100 trades. Returns `passed=False` when z-score > 2.5. | `services/validation/src/check_3_bias.py` | ~~HIGH~~ RESOLVED |
| ~~D-11~~ | ~~Rate limiter service is a stub.~~ **RESOLVED** (2026-03-27). `RateLimiterClient` now implements a Redis sorted-set sliding window. Enforces per-exchange quotas (Binance: 1200/min, Coinbase: 300/min). Returns `retry_after_ms` when limit exceeded. Service upgraded to FastAPI with `/health` and `/quotas` endpoints. | `libs/exchange/_rate_limiter_client.py`, `services/rate_limiter/src/main.py` | ~~HIGH~~ RESOLVED |
| ~~D-12~~ | ~~`/commands/` endpoint returns `501 Not Implemented`.~~ **PARTIALLY RESOLVED** (2026-03-27). Kill switch endpoints added (`GET/POST /commands/kill-switch`). LLM intent classification still returns 501. | `services/api_gateway/src/routes/commands.py` | LOW |

### Other Issues

| # | Description | Location | Severity |
|---|-------------|----------|----------|
| ~~D-13~~ | ~~Port 8080 collision between 4+ services.~~ **RESOLVED** (2026-03-27). All services now have unique ports assigned in `run_all.sh`. | — | ~~HIGH~~ RESOLVED |
| ~~D-14~~ | ~~13 API endpoints lack `response_model` declarations.~~ **RESOLVED** (2026-04-03). Response models added to kill-switch (GET/POST), exchange test, risk check, tax calculate, backtest sweep, and quotas endpoints. SSE streaming endpoints (docs_chat, telemetry) return StreamingResponse and cannot use response_model. | Various API routers | ~~MEDIUM~~ RESOLVED |
| ~~D-15~~ | ~~`profile_id` path parameters accept arbitrary strings.~~ **RESOLVED** (2026-04-03). Profile route path parameters changed from `str` to `UUID`. FastAPI auto-returns 422 on invalid UUIDs. | `services/api_gateway/src/routes/profiles.py` | ~~MEDIUM~~ RESOLVED |
| ~~D-16~~ | ~~WebSocket Redis listener has no reconnection logic on disconnect.~~ **RESOLVED** (2026-03-27). `listen_to_redis` now wraps the subscribe/listen loop in an outer retry loop with exponential backoff (1s → 30s max). On Redis disconnect, pubsub is cleaned up and re-established automatically. Only exits on WebSocket close or task cancellation. | `services/api_gateway/src/routes/ws.py` | ~~HIGH~~ RESOLVED |
| ~~D-17~~ | ~~CORS configuration uses `allow_methods=["*"]` and `allow_headers=["*"]`.~~ **RESOLVED** (2026-04-03). Methods restricted to `["GET","POST","PUT","DELETE","PATCH","OPTIONS"]`, headers to `["Authorization","Content-Type","X-Request-ID","Accept"]`. Origins already configurable via `settings.CORS_ORIGINS`. | `services/api_gateway/src/main.py` | ~~MEDIUM~~ RESOLVED |

---

## Architecture Doc vs Code Discrepancies

Conflicts between existing documentation files and the actual codebase.

| # | Document | Claim | Reality | Severity |
|---|----------|-------|---------|----------|
| ~~A-1~~ | `WALKTHROUGH.md` | "5 SQL migrations" | **RESOLVED** (2026-03-27). 9 migrations exist (`001` through `009`). Documentation updated. | ~~MEDIUM~~ RESOLVED |
| A-2 | `WALKTHROUGH.md` | `POST /auth/login` endpoint | No `/auth/login` endpoint exists. Authentication uses `/auth/callback` (OAuth flow). | HIGH |
| A-3 | `RUNTIME_ARCHITECTURE.md` | "Fast Gate responds in 35ms" | `constants.py` sets the fast gate timeout to 50ms. 35ms is not referenced anywhere in code. | MEDIUM |
| A-4 | `SHUTDOWN.md` | Lists 8 services for graceful shutdown | 19 services exist in the codebase (14 HTTP + 5 async). 11 services have no documented shutdown procedure. | HIGH |
| ~~A-5~~ | `README.md` (root) | Lists a subset of services | **RESOLVED** (2026-03-24). README updated with all services including Analyst, SLM Inference, Debate, and HITL. | ~~HIGH~~ RESOLVED |
| A-6 | `RUNTIME_ARCHITECTURE.md` | "migrate.py applies 001 to 005" | `migrate.py` applies migrations `001` through `009`. | MEDIUM |
| ~~A-7~~ | Multiple docs | Services documented on port 8080 | **RESOLVED** (2026-03-27). All services have unique port assignments. See `run_all.sh`. | ~~HIGH~~ RESOLVED |

---

## Service Port Registry (2026-03-27)

Authoritative port assignments from `run_all.sh`:

| Service | Port | Type |
|---------|------|------|
| API Gateway | 8000 | HTTP |
| Ingestion | 8080 | HTTP |
| Validation | 8081 | HTTP |
| Hot Path | 8082 | HTTP |
| Execution | 8083 | HTTP |
| PnL | 8084 | HTTP |
| Logger | 8085 | HTTP |
| Backtesting | 8086 | HTTP |
| Analyst | 8087 | HTTP |
| Archiver | 8088 | HTTP |
| Tax | 8089 | HTTP |
| TA Agent | 8090 | HTTP |
| Regime HMM | 8091 | HTTP |
| Sentiment | 8092 | HTTP |
| Risk | 8093 | HTTP |
| SLM Inference | 8095 | HTTP |
| Debate | 8096 | HTTP |
| Strategy | — | Async worker |
| Rate Limiter | 8094 | HTTP |
| Frontend | 3000 | Next.js |

---

## Phase 2 Readiness

Items required for production-grade deployment that are scaffolded but not yet complete.

| # | Item | Current State | Action Required |
|---|------|---------------|-----------------|
| P-1 | Kubernetes manifests | Overlay directories exist for dev, staging, and production but contain no service manifests. | Write Deployment, Service, and ConfigMap manifests for all 19 services. |
| P-2 | Terraform modules | `terraform/modules/` directory is empty. | Implement IaC for GCP resources (GKE, Cloud SQL, Redis, GCS). |
| P-3 | Horizontal scaling | No HPA configuration or scaling documentation. | Define scaling policies based on load test results (see G-2). |
| P-4 | Performance benchmarks | No load testing results or performance baselines exist. | Run benchmarks for hot-path latency, throughput per symbol, and database query performance. |
| P-5 | Secrets rotation | No automated key rotation. Exchange API keys and JWT signing keys are static. | Implement rotation via GCP Secret Manager with automated rollover. |
| P-6 | Deployment strategy | No blue/green or canary deployment strategy defined. | Define and document progressive rollout strategy with automated rollback triggers. |

---

## SLM Multi-Agent Implementation Status (2026-03-24)

The following 6 phases from `SLM-Multi-Agent-Implementation-Plan.md` have been implemented and documented:

| Phase | Feature | Status | Tests | Documentation |
|-------|---------|--------|-------|---------------|
| 1 | Extended Indicators (ADX, Bollinger, OBV, Choppiness) | **COMPLETE** | 20 tests | `modules/indicators.md` updated |
| 2 | Dynamic Agent Weighting (EWMA) | **COMPLETE** | 15 tests | `agent-architecture.md` updated (Analyst agent) |
| 3 | HITL Execution Gate | **COMPLETE** | 8 tests | `modules/hot-path.md` updated, `configuration.md` updated |
| 4 | Local SLM Inference | **COMPLETE** | 20 tests | `agent-architecture.md` updated (SLM Inference service) |
| 5 | Adversarial Bull/Bear Debate | **COMPLETE** | 20 tests | `agent-architecture.md` updated (Debate agent) |
| 6 | VectorBT Backtesting | **COMPLETE** | 18 tests | `README.md` updated |

**Total new tests:** 101 | **Total test suite:** 126 passed, 0 failed

### Additional fixes during implementation:
- Fixed pre-existing PID-width bug in monotonic UUID generator (`libs/core/schemas.py` — `0xFFFF` → `0xFFF`)
- Updated existing `AgentModifier` tests to work with pipeline-based Redis reads

---

## Platform Rename (2026-03-27)

The platform was renamed from **Aion** to **Praxis**:
- Environment variable prefix: `AION_` → `PRAXIS_`
- Exception base class: `AionBaseError` → `PraxisBaseError`
- Database names: `aion_trading` → `praxis_trading`, `aion_test` → `praxis_test`
- Package name: `aion-trading` → `praxis-trading` (pyproject.toml)
- K8s namespace: `aion-trading` → `praxis-trading`
- All documentation, config files, scripts, and CI workflows updated
- Directory name `aion-trading` remains unchanged (filesystem only)

---

## Open Defect Summary

| Severity | Count | Items |
|----------|-------|-------|
| **CRITICAL** | 0 | — |
| **HIGH** | 0 | — |
| **MEDIUM** | 5 | D-14, D-15, D-17, A-3, A-6 |
| **LOW** | 1 | D-12 |
| **RESOLVED** | 16 | D-1, D-2, D-3, D-4, D-5, D-6, D-7, D-8, D-9, D-10, D-11, D-13, D-16, A-1, A-5, A-7, G-8 |

---

## How to Use This Document

**For engineers**: All CRITICAL and HIGH defects have been resolved as of 2026-03-27.
Remaining MEDIUM items (D-14, D-15, D-17, A-2, A-3, A-4, A-6) should be addressed before
production deployment but are not blocking.

**For documentation**: Remaining gaps (G-1 through G-7, G-10, G-11) require input from the
engineering team. Schedule a 30-minute review session per gap to capture the missing information.

**For auditors**: Financial precision defects (D-1 through D-7) have been fully remediated.
All financial calculations now use `Decimal` (Python) and `NUMERIC` (PostgreSQL). Review the
[Data Model](data-model.md) and [Risk Management](risk-management.md) documents for the full
context of how financial values flow through the system.

---

*Last updated: 2026-03-27*
