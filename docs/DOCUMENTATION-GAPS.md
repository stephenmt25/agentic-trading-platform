# Documentation Gaps and Defects

> This document tracks known documentation gaps, code defects discovered during the
> documentation audit, discrepancies between existing docs and actual code, and
> Phase 2 readiness issues. Each item includes a severity, location, and recommended action.

**Audit date**: 2026-03-19
**Last updated**: 2026-06-13

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
| ~~G-1~~ | ~~No documented SLA targets beyond the fast gate (50ms).~~ | **RESOLVED at v1** (2026-06-13, ruling D-L): `docs/ops/SLA-TARGETS.md` — code-pinned values cited file:line; all other targets marked PROPOSED (dev-box) pending ops review. | — |
| ~~G-2~~ | ~~No documented capacity planning guidelines.~~ | **RESOLVED at v1** (2026-06-13, ruling D-L): `docs/ops/CAPACITY.md` — method + dev-box numbers (WS fan-out measured via `scripts/ws_bench.py`; symbol/profile/DB limits derived from config with derivations marked PROPOSED). | — |
| ~~G-3~~ | ~~No documented disaster recovery procedures.~~ | **RESOLVED at v1** (2026-06-13, ruling D-L): `docs/ops/DR-PLAYBOOK.md` — folds the tested S1–S3 resilience evidence (2026-05-11 run + row-33 fail-safe validation); untested domains (TimescaleDB loss, host loss, exchange outage) explicitly marked with code-derived expectations. | — |
| ~~G-4~~ | ~~No documented data retention policy beyond `HOT_DATA_RETENTION_DAYS=7`.~~ | **RESOLVED at v1** (2026-06-13, ruling D-L): `docs/ops/DATA-RETENTION.md` — hot/warm/cold tiers from `HOT_DATA_RETENTION_DAYS` + archiver `ARCHIVE_POLICIES` (30/90/180/365-day windows, chunk-aware moves to `*_archive`); policy choices marked PROPOSED; off-host gap flagged (D-21 blocked-on-cloud). | — |
| ~~G-5~~ | ~~No documented monitoring or alerting thresholds.~~ | **RESOLVED at v1** (2026-06-13, ruling D-L): `docs/ops/ALERTING.md` — existing signal inventory + code-pinned tripwires (incl. the new hot_path order-burst tripwire: WARN >10 / CRITICAL >25 orders/profile/60s with `pubsub:system_alerts`) + 12 PROPOSED alert rules with P1–P3 severities. | — |
| ~~G-6~~ | ~~No documented rollback procedures for failed deployments.~~ | **RESOLVED at v1** (2026-06-13, ruling D-L): `docs/ops/ROLLBACK.md` — git-revert reality, the honest migration story (forward-only `migrate.py`, no down-migrations: dump-restore / inverse-migration / dev-reset paths), env-flag emergency rollbacks, `run_all.sh` relaunch verification. Worked example: `docs/ROLLBACK-PROCEDURE.md`. | — |
| ~~G-7~~ | ~~No documented exchange API key rotation procedures.~~ | **RESOLVED at v1** (2026-06-13, ruling D-L): `docs/ops/KEY-ROTATION.md` — full secret inventory + today's manual rotation steps (JWT keys, exchange keys via `SecretManager`/Fernet, infra passwords) + PROPOSED cadences. Automation stays Phase 2 P-5 (blocked on cloud target). | — |
| ~~G-8~~ | ~~Port 8080 collision between 4+ services.~~ | **RESOLVED** (2026-03-27). All services now have unique port assignments (8000–8096). See `run_all.sh`. | — |
| ~~G-9~~ | ~~No documented rate limits per exchange.~~ | **RESOLVED** (2026-03-27). Rate limits now enforced and documented: Binance 1200 req/min, Coinbase 300 req/min, default 600 req/min. Implemented via Redis sorted-set sliding window in `RateLimiterClient`. Queryable via `GET /commands/../quotas` endpoint on rate limiter service (port 8094). | — |
| ~~G-10~~ | ~~Strategy rules JSON schema not formally documented.~~ | **RESOLVED** (2026-05-19). Schema published in `docs/STRATEGY_RULES_SCHEMA.md` — both the canonical `strategy_rules` JSONB shape (`RuleSchema`/`RuleCondition` core + transformer-added `preferred_regimes`/`entry_long`/`entry_short`) and the user-facing `StrategyRulesInput` shape, with JSON Schema, validator constraints, enumerations, and examples. Notes that `RuleValidator`/`RuleSchema` only validates the four core fields. | — |
| ~~G-11~~ | ~~No documented maximum number of concurrent WebSocket connections.~~ | **RESOLVED at v1** (2026-06-13, ruling D-L): `docs/ops/WS-LIMITS.md` — measured via new `scripts/ws_bench.py` (dev-box, live stack): ~50 fully-served concurrent clients; at N=100 only 52/100 and at N=200 only 36/200 receive data while handshakes stay 100% (gateway accepts before subscribing). Binding constraint is the shared Redis pool `max_connections=100` (`libs/storage/_redis_client.py:19`) — one pubsub connection per WS client (`routes/ws.py:238`). PROPOSED operating limit: ≤40 sessions/gateway. | — |

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
| ~~D-12~~ | ~~`/commands/` endpoint returns `501 Not Implemented`.~~ **TRIAGED-CLOSED — wontfix** (2026-06-13, ruling D-F): the command palette shipped without LLM intent classification and no consumer needs the endpoint; the permanent 501 stub was deleted from `routes/commands.py` (a NOTE comment marks the removal). Kill-switch endpoints (the part that mattered) landed 2026-03-27. | `services/api_gateway/src/routes/commands.py` | ~~LOW~~ CLOSED |

### Other Issues

| # | Description | Location | Severity |
|---|-------------|----------|----------|
| ~~D-13~~ | ~~Port 8080 collision between 4+ services.~~ **RESOLVED** (2026-03-27). All services now have unique ports assigned in `run_all.sh`. | — | ~~HIGH~~ RESOLVED |
| ~~D-14~~ | ~~13 API endpoints lack `response_model` declarations.~~ **RESOLVED** (2026-04-03). Response models added to kill-switch (GET/POST), exchange test, risk check, tax calculate, backtest sweep, and quotas endpoints. SSE streaming endpoints (docs_chat, telemetry) return StreamingResponse and cannot use response_model. | Various API routers | ~~MEDIUM~~ RESOLVED |
| ~~D-15~~ | ~~`profile_id` path parameters accept arbitrary strings.~~ **RESOLVED** (2026-04-03). Profile route path parameters changed from `str` to `UUID`. FastAPI auto-returns 422 on invalid UUIDs. | `services/api_gateway/src/routes/profiles.py` | ~~MEDIUM~~ RESOLVED |
| ~~D-16~~ | ~~WebSocket Redis listener has no reconnection logic on disconnect.~~ **RESOLVED** (2026-03-27). `listen_to_redis` now wraps the subscribe/listen loop in an outer retry loop with exponential backoff (1s → 30s max). On Redis disconnect, pubsub is cleaned up and re-established automatically. Only exits on WebSocket close or task cancellation. | `services/api_gateway/src/routes/ws.py` | ~~HIGH~~ RESOLVED |
| ~~D-17~~ | ~~CORS configuration uses `allow_methods=["*"]` and `allow_headers=["*"]`.~~ **RESOLVED** (2026-04-03). Methods restricted to `["GET","POST","PUT","DELETE","PATCH","OPTIONS"]`, headers to `["Authorization","Content-Type","X-Request-ID","Accept"]`. Origins already configurable via `settings.CORS_ORIGINS`. | `services/api_gateway/src/main.py` | ~~MEDIUM~~ RESOLVED |
| ~~D-18~~ | `llama-cpp-python` not in `pyproject.toml` but SLM Inference service imports it. **TRIAGED-CLOSED — documented-by-design** (2026-06-13, ruling D-G): the library requires a platform-specific C++/GPU toolchain, is lazy-imported, and the service degrades to mock responses when absent; documented as an optional dependency in `agent-architecture.md`. Terminal status — this is the intended design, not open debt. | `services/slm_inference/src/main.py` | ~~LOW~~ CLOSED (by design) |
| ~~D-19~~ | ~~Strategy Agent main loop was an empty `sleep(60)` — no profile update consumption.~~ **RESOLVED** (2026-04-16). Added periodic profile polling: fetches active profiles from DB every 60s, detects changes via hash comparison, re-validates and re-compiles rules, caches compiled rule sets in Redis (`strategy:compiled:{profile_id}`). | `services/strategy/src/main.py` | ~~MEDIUM~~ RESOLVED |
| ~~D-20~~ | ~~Logger Alerter hardcoded with `pagerduty_key=None, slack_webhook=None`.~~ **RESOLVED** (2026-04-16). Wired to `settings.PAGERDUTY_API_KEY` and new `settings.SLACK_WEBHOOK`. Alerter activates when env vars are set. | `services/logger/src/main.py`, `libs/config/settings.py` | ~~MEDIUM~~ RESOLVED |
| ~~D-21~~ | Archiver GCS export is deferred — when `PRAXIS_GCS_BUCKET_NAME` is set, the service logs "deferred to batch pipeline" but does not upload. **TRIAGED-CLOSED — blocked-on-cloud** (2026-06-13, ruling D-G): the deployment is local-only with no GCS bucket; implementing an upload path now would be untestable dead code. Redis cleanup and TimescaleDB archiving (chunk-aware as of 2026-06-13) work. Reopen when a GCS bucket exists — the off-host durability need is tracked in `docs/ops/DR-PLAYBOOK.md` (domain 6) and `docs/ops/DATA-RETENTION.md`. | `services/archiver/src/migrator.py` | ~~LOW~~ BLOCKED-ON-CLOUD |
| ~~D-22~~ | ~~News scraper silently returns `[]` when no API key is configured.~~ **RESOLVED** (2026-04-16). Added startup warning log when `NEWS_API_KEY` is not set. | `services/analyst/src/news_scraper.py` | ~~LOW~~ RESOLVED |

---

## Architecture Doc vs Code Discrepancies

Conflicts between existing documentation files and the actual codebase.

| # | Document | Claim | Reality | Severity |
|---|----------|-------|---------|----------|
| ~~A-1~~ | `WALKTHROUGH.md` | "5 SQL migrations" | **RESOLVED** (2026-03-27). 9 migrations exist (`001` through `009`). Documentation updated. | ~~MEDIUM~~ RESOLVED |
| ~~A-2~~ | `WALKTHROUGH.md` | ~~`POST /auth/login` endpoint~~ | **RESOLVED** (2026-06-13). WALKTHROUGH.md Step 4.8 now documents the real flow: NextAuth.js OAuth → `POST /auth/callback` (NextAuth token verified against `NEXTAUTH_SECRET`, user upserted, session row created, access+refresh tokens returned) plus `/auth/refresh`, `/auth/me`, and the sessions endpoints, per `services/api_gateway/src/routes/auth.py`. | ~~HIGH~~ RESOLVED |
| ~~A-3~~ | `RUNTIME_ARCHITECTURE.md` (+ data-model.md, modules/validation.md, risk-management.md) | ~~"Fast Gate responds in 35ms"~~ | **RESOLVED** (2026-06-13) — with a correction to this row's own claim: 35ms IS in code, as the validation-internal soft-warning threshold (`fast_gate.py:40`), while the consumer-side response timeout is 50ms (`FAST_GATE_TIMEOUT_MS`, `settings.py:76` / `constants.py:3`). Docs that stated 35ms as the response budget now say 50ms timeout (35ms soft warning); docs describing the warning were already correct and were left alone. | ~~MEDIUM~~ RESOLVED |
| ~~A-4~~ | `SHUTDOWN.md` | ~~Lists 8 services for graceful shutdown~~ | **RESOLVED** (2026-06-13). SHUTDOWN.md rewritten from `run_all.sh` + every service's lifespan teardown: covers all 19 HTTP services (incl. `oracle` :8097) + the `strategy` worker + the `daily_report` daemon, the three-layer `--stop` sweep, per-service teardown/kill-safety notes, and the Redis-persistence invariants (halt state survives restarts; consumer groups redeliver). | ~~HIGH~~ RESOLVED |
| ~~A-5~~ | `README.md` (root) | Lists a subset of services | **RESOLVED** (2026-03-24). README updated with all services including Analyst, SLM Inference, Debate, and HITL. | ~~HIGH~~ RESOLVED |
| ~~A-6~~ | `RUNTIME_ARCHITECTURE.md`, `WALKTHROUGH.md` | ~~"migrate.py applies 001 to 005"~~ | **RESOLVED** (2026-06-13). Both docs now state the mechanism (migrate.py applies **every** file in `migrations/versions/` in sorted order) and the real current range `001`–`024` (24 files), so the docs can't go stale at the next migration. | ~~MEDIUM~~ RESOLVED |
| ~~A-7~~ | Multiple docs | Services documented on port 8080 | **RESOLVED** (2026-03-27). All services have unique port assignments. See `run_all.sh`. | ~~HIGH~~ RESOLVED |
| ~~A-8~~ | `architecture-overview.md`, `trading-engine.md`, `event-system.md`, `agent-architecture.md`, `SLM-Multi-Agent-Implementation-Plan.md` | Pipeline described as "9-stage" | **RESOLVED** (2026-04-16). Standardized to "11-stage" across all docs. Code has 11 labeled steps in `processor.py`. | ~~MEDIUM~~ RESOLVED |
| ~~A-9~~ | `architecture-overview.md`, `SLM-Multi-Agent-Implementation-Plan.md` | "17 services" | **RESOLVED** (2026-04-16). Updated to 19 (matching `run_all.sh`). | ~~MEDIUM~~ RESOLVED |
| ~~A-10~~ | `architecture-overview.md` | Analyst/Tax/Archiver on port 8080; Risk as "Library (no server)" | **RESOLVED** (2026-04-16). Container diagram and service catalog updated with correct ports. | ~~HIGH~~ RESOLVED |
| ~~A-11~~ | `architecture-overview.md` | Regime HMM has "3 states (bull/bear/sideways)" | **RESOLVED** (2026-04-16). Updated to 5 states matching `Regime` enum in `libs/core/enums.py`. | ~~MEDIUM~~ RESOLVED |
| ~~A-12~~ | `architecture-overview.md` | Phase Boundary table marks CHECK_3 and Rate Limiter as "Stubbed" | **RESOLVED** (2026-04-16). Updated to "Implemented" (both resolved 2026-03-27). | ~~MEDIUM~~ RESOLVED |
| ~~A-13~~ | `CLAUDE.md` | "22 markdown documentation files" | **RESOLVED** (2026-04-16). Updated to 28. | ~~LOW~~ RESOLVED |
| ~~A-14~~ | `CLAUDE.md` | "Remaining (MEDIUM): 13 API endpoints lack response_model..." | **RESOLVED** (2026-04-16). All MEDIUM defects resolved as of 2026-04-03. Note updated. | ~~LOW~~ RESOLVED |

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
| **MEDIUM** | 0 | — |
| **LOW** | 0 | — |
| **RESOLVED** | 31 | D-1–D-11, D-13–D-17, D-19, D-20, D-22, A-1–A-14, G-8 |
| **RESOLVED at v1 (PROPOSED docs, ruling D-L)** | 8 | G-1–G-7, G-11 (`docs/ops/`) |
| **TRIAGED-CLOSED** | 3 | D-12 (wontfix, ruling D-F), D-18 (by design, ruling D-G), D-21 (blocked-on-cloud, ruling D-G) |

Every row in this document is now terminal (resolved, closed, or blocked on an external
prerequisite). New gaps/defects go to `docs/TECH-DEBT-REGISTRY.md`, not here.

---

## How to Use This Document

**For engineers**: every defect and discrepancy row is terminal as of 2026-06-13. The
last four doc discrepancies (A-2, A-3, A-4, A-6) were fixed in the source docs themselves;
D-12 is closed wontfix, D-18 is by-design, D-21 is blocked until a GCS bucket exists.

**For documentation**: the operational gaps (G-1–G-7, G-11) are closed at **v1 PROPOSED**
under `docs/ops/` (ruling D-L, 2026-06-13): code-pinned numbers are cited file:line; every
unmeasured number is marked PROPOSED (dev-box) with its derivation. The remaining work is
an ops/partner review pass over the PROPOSED values, not missing documentation.

**For auditors**: Financial precision defects (D-1 through D-7) have been fully remediated.
All financial calculations now use `Decimal` (Python) and `NUMERIC` (PostgreSQL). Review the
[Data Model](data-model.md) and [Risk Management](risk-management.md) documents for the full
context of how financial values flow through the system.

---

*Last updated: 2026-06-13*
