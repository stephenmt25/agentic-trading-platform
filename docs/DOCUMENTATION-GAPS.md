# Documentation Gaps and Defects

> This document tracks known documentation gaps, code defects discovered during the
> documentation audit, discrepancies between existing docs and actual code, and
> Phase 2 readiness issues. Each item includes a severity, location, and recommended action.

**Audit date**: 2026-03-19

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
| G-8 | Port 8080 collision: Ingestion, Archiver, Analyst, and Tax services all claim port 8080. | Actual runtime behavior is unclear. Services may fail to bind or silently shadow each other. | Assign unique ports per service or document the container/network isolation that prevents conflicts. |
| G-9 | No documented rate limits per exchange. | CCXT's internal rate limiter is used but limits are not surfaced in documentation. | Document per-exchange rate limits and how the system enforces them. |
| G-10 | Strategy rules JSON schema not formally documented. | The `strategy_rules` JSONB column is validated by `RuleValidator` but the expected schema is not published. | Extract and publish the JSON Schema from `RuleValidator`. |
| G-11 | No documented maximum number of concurrent WebSocket connections. | Unknown scaling ceiling for real-time market data subscriptions. | Benchmark and document per-process and per-host WebSocket limits. |

---

## Code Defects

### Financial Precision (CRITICAL)

These defects involve the use of floating-point types (`float`, `DOUBLE PRECISION`) for
financial calculations. IEEE 754 floating-point arithmetic introduces rounding errors that
accumulate over time, leading to incorrect P&L, fee calculations, and risk assessments.

**Recommended fix**: Use `Decimal` (Python) and `NUMERIC`/`DECIMAL` (PostgreSQL) for all
monetary values. Set explicit precision (e.g., `DECIMAL(20, 8)` for crypto quantities).

| # | Description | Location | Severity |
|---|-------------|----------|----------|
| D-1 | `backtest_results` table uses `DOUBLE PRECISION` for 5 financial columns (`win_rate`, `avg_return`, `max_drawdown`, `sharpe`, `profit_factor`). Should be `DECIMAL`. | `migrations/versions/008_backtest_results.sql` | **CRITICAL** |
| D-2 | `PnLSnapshot` dataclass uses `float` for all monetary fields (`gross_pnl`, `fees`, `net_pre_tax`, `net_post_tax`, `pct_return`, `tax_estimate`). Should be `Decimal`. | `services/pnl/src/calculator.py` | **CRITICAL** |
| D-3 | 24+ `float()` conversions scattered across financial code paths. | See breakdown below. | **CRITICAL** |
| D-4 | `SignalEvent.confidence` is typed as `float` in the Pydantic schema. | `libs/core/schemas.py:60` | HIGH |
| D-5 | `PnlUpdateEvent.pct_return` is typed as `float`. | `libs/core/schemas.py:106` | HIGH |
| D-6 | `ThresholdProximityEvent` fields (`current_value`, `threshold`, `distance`) are typed as `float`. | `libs/core/schemas.py:124-126` | HIGH |
| D-7 | `ProfileState` risk fields use `float` for financial thresholds. | `services/hot_path/src/state.py` | HIGH |

**D-3 detailed breakdown** -- `float()` conversions in financial code paths:

| Subsystem | File | Lines |
|-----------|------|-------|
| Order placement | `libs/exchange/_binance.py` | 59-60 |
| Order placement | `libs/exchange/_coinbase.py` | 52-53 |
| PnL calculation | `services/pnl/src/calculator.py` | 22-23, 32 |
| Risk validation | `services/validation/src/check_6_risk_level.py` | 6 conversions |
| Risk gate | `services/hot_path/src/risk_gate.py` | 22-23, 26 |
| Circuit breaker | `services/hot_path/src/circuit_breaker.py` | 26 |
| Execution fees | `services/execution/src/executor.py` | 144 |
| Reconciliation | `services/execution/src/reconciler.py` | 84, 94 |

### Missing Implementations

Features that are referenced in comments, configuration, or documentation but have no
functional implementation.

| # | Description | Location | Severity |
|---|-------------|----------|----------|
| D-8 | Kill switch / emergency shutdown is **not implemented**. Referenced in comments but no code exists to halt all trading globally. | N/A (missing) | **CRITICAL** |
| D-9 | Position-level stop-loss enforcement is **not implemented**. `risk_limits` contains `stop_loss_pct` but no code checks or enforces it against open positions. | `risk_limits` schema | **CRITICAL** |
| D-10 | CHECK_3 (Bias validation) is **stubbed**. Always returns `GREEN` regardless of input. | Validation service, CHECK_3 handler | HIGH |
| D-11 | Rate limiter service is a **stub**. Always returns `allowed=True`. No actual rate limiting occurs. | `libs/exchange/_rate_limiter_client.py` | HIGH |
| D-12 | `/commands/` endpoint returns `501 Not Implemented`. | API router | LOW |

### Other Issues

| # | Description | Location | Severity |
|---|-------------|----------|----------|
| D-13 | Port 8080 collision between 4+ services (Ingestion, Archiver, Analyst, Tax). Services will fail to start if co-located without container isolation. | Service `main.py` files | HIGH |
| D-14 | 13 API endpoints lack `response_model` declarations. May leak internal database column names or SQLAlchemy metadata in responses. | Various API routers | MEDIUM |
| D-15 | `profile_id` path parameters accept arbitrary strings. UUID conversion can raise unhandled `ValueError`, returning a 500 instead of 422. | API route handlers | MEDIUM |
| D-16 | WebSocket Redis listener has no reconnection logic on disconnect. A transient Redis failure will permanently break real-time updates until the service restarts. | WebSocket consumer | HIGH |
| D-17 | CORS configuration uses `allow_methods=["*"]` and `allow_headers=["*"]`. Overly permissive for a trading API that handles financial operations. | FastAPI middleware config | MEDIUM |

---

## Architecture Doc vs Code Discrepancies

Conflicts between existing documentation files and the actual codebase.

| # | Document | Claim | Reality | Severity |
|---|----------|-------|---------|----------|
| A-1 | `WALKTHROUGH.md` | "5 SQL migrations" | 8 migrations exist (`001` through `008`). | MEDIUM |
| A-2 | `WALKTHROUGH.md` | `POST /auth/login` endpoint | No `/auth/login` endpoint exists. Authentication uses `/auth/callback` (OAuth flow). | HIGH |
| A-3 | `RUNTIME_ARCHITECTURE.md` | "Fast Gate responds in 35ms" | `constants.py` sets the fast gate timeout to 50ms. 35ms is not referenced anywhere in code. | MEDIUM |
| A-4 | `SHUTDOWN.md` | Lists 8 services for graceful shutdown | 17 services exist in the codebase. 9 services have no documented shutdown procedure. | HIGH |
| A-5 | `README.md` (root) | Lists a subset of services | Does not mention Strategy, Ingestion, Validation, Logger, Risk, Rate Limiter, Archiver, Analyst, or Tax services. | HIGH |
| A-6 | `RUNTIME_ARCHITECTURE.md` | "migrate.py applies 001 to 005" | `migrate.py` applies migrations `001` through `008`. | MEDIUM |
| A-7 | Multiple docs | Services documented on port 8080 | At least 4 services claim port 8080 with no documented conflict resolution strategy. | HIGH |

---

## Phase 2 Readiness

Items required for production-grade deployment that are scaffolded but not yet complete.

| # | Item | Current State | Action Required |
|---|------|---------------|-----------------|
| P-1 | Kubernetes manifests | Overlay directories exist for dev, staging, and production but contain no service manifests. | Write Deployment, Service, and ConfigMap manifests for all 17 services. |
| P-2 | Terraform modules | `terraform/modules/` directory is empty. | Implement IaC for GCP resources (GKE, Cloud SQL, Redis, GCS). |
| P-3 | Horizontal scaling | No HPA configuration or scaling documentation. | Define scaling policies based on load test results (see G-2). |
| P-4 | Performance benchmarks | No load testing results or performance baselines exist. | Run benchmarks for hot-path latency, throughput per symbol, and database query performance. |
| P-5 | Secrets rotation | No automated key rotation. Exchange API keys and JWT signing keys are static. | Implement rotation via GCP Secret Manager with automated rollover. |
| P-6 | Deployment strategy | No blue/green or canary deployment strategy defined. | Define and document progressive rollout strategy with automated rollback triggers. |

---

## How to Use This Document

**For engineers**: Treat CRITICAL items as bugs. File tickets and prioritize them in the
current sprint. HIGH items should be addressed before any production deployment.

**For documentation**: Each gap (G-*) requires input from the engineering team. Schedule a
30-minute review session per gap to capture the missing information.

**For auditors**: The financial precision defects (D-1 through D-7) represent systemic risk.
Review the [Data Model](data-model.md) and [Risk Management](risk-management.md) documents
for the full context of how financial values flow through the system.

---

*Last updated: 2026-03-19*
