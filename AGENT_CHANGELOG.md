# Praxis Trading — Agent Changelog

Living document tracking all changes made by agency agents across the platform.
Updated after each agent session.

---

## Session 1 — 2026-03-16

### Agent: Backend Architect

**Task:** Full API design review of the `aion-trading` API gateway and supporting libraries.

**Scope:** 11 route groups, 8 repositories, middleware stack, settings, schemas, and microservice architecture.

#### Findings (20 issues across 4 severity levels)

**P0 — Security Critical**

| # | Issue | Severity | Resolution |
|---|-------|----------|------------|
| 1 | No tenant isolation — `GET /profiles` returned all users' data. `PUT/DELETE` didn't verify ownership. Same for P&L, orders, risk. | CRITICAL | All queries now filter by `user_id` from JWT. Added `get_profile_for_user`, `get_all_profiles_for_user`, `get_orders_for_user`, `cancel_order_for_user` repo methods. |
| 2 | `/agents/risk` and `/backtest` were public — exposed per-user drawdown, P&L, allocation. Unauthenticated `POST /backtest` enabled DoS. | CRITICAL | Moved behind JWT auth. Risk endpoints verify profile ownership. Backtest results check `user_id`. |
| 3 | `SECRET_KEY` defaulted to `"praxis-dev-secret-key-change-in-production"` with no startup check. | CRITICAL | Added `is_secret_key_secure()`. Startup raises `RuntimeError` if trading enabled with default key. |
| 4 | OAuth callback accepted arbitrary email/name/provider without verifying against OAuth provider. DB failure silently issued tokens. | CRITICAL | Now verifies `id_token` against `NEXTAUTH_SECRET`. DB failure blocks login (raises 503). |
| 5 | Stub endpoints returned fake data — orders: hardcoded `CONFIRMED`, P&L: zeros, `/auth/me`: `user@example.com`. | CRITICAL | All now query real DB/Redis. |

**P1 — High Priority**

| # | Issue | Resolution |
|---|-------|------------|
| 6 | `profiles.py` used raw `dict` request bodies, bypassing Pydantic validation. | Added `ProfileCreate`, `ProfileUpdate`, `ProfileToggle` models with field constraints. |
| 7 | Rate limiter key used full path (`/orders/abc-123`), creating per-URL buckets. | Key uses matched route pattern (`/orders/{order_id}`). Rate-limited requests no longer counted. |
| 8 | Duplicate `TimescaleClient` — `deps.py` and `main.py` created separate pools. `paper_trading.py` re-initialized on every request. | Single instance on `app.state`. Removed redundant `init_pool()`. |
| 9 | Same signing key for access and refresh tokens. | Added `REFRESH_SECRET_KEY` setting, separate `create_refresh_token()` / `verify_refresh_token()`. |
| 10 | Refresh token issued but no endpoint to use it. | Added `POST /auth/refresh` with token rotation and user verification. |

**P2 — Medium Priority**

| # | Issue | Resolution |
|---|-------|------------|
| 11 | No global exception handler. Domain exceptions unhandled. | Added handlers mapping all `libs/core/exceptions.py` types to HTTP codes (503, 403, 422, 429, 502, 500). |
| 12 | No request/correlation ID. | Added middleware: UUID per request, `X-Request-ID` response header. |
| 13 | WebSocket `broadcast()` silently swallowed errors, dead connections accumulated. | Logs failures, removes dead connections. |
| 14 | No pagination on list endpoints. | Orders: SQL `OFFSET`/`LIMIT` (capped 200). P&L history: `start`/`end` params. |
| 15 | CORS hardcoded to `localhost:3000`. | Moved to `settings.CORS_ORIGINS`. |

**P3 — Best Practices**

| # | Issue | Resolution |
|---|-------|------------|
| 16 | No API versioning. | Added `version="1.0.0"` to FastAPI metadata. |
| 17 | Inconsistent response envelopes. | Added `response_model=` and Pydantic response models on key routes. |
| 18 | Missing OpenAPI metadata. | Added `description`, `version` to app. |
| 19 | Backtest queue unbounded, no backpressure. | Added `BACKTEST_MAX_QUEUE_DEPTH` (default 100). Queue depth checked before accepting. |
| 20 | Deprecated `datetime.utcnow()`. | Replaced with `datetime.now(timezone.utc)`. |

**Additional changes (not from findings):**
- JWT payload stripped of PII (email, name, provider) — now only contains `sub`
- Exchange key test returns 422 (not 401) for invalid exchange credentials
- `get_current_user` raises proper 401 `HTTPException`
- Added `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`, `DB_POOL_TIMEOUT` settings
- Profile creation returns 201 status code

---

### Agent: API Tester

**Task:** Comprehensive endpoint validation after Backend Architect fixes.

**Scope:** Contract validation, security coverage, data flow, error handling, cross-cutting concerns across all modified files.

#### Validation Results

**A. Endpoint Contract Validation**
- Route registration & prefix logic: PASS (all 11 route groups resolve correctly)
- Request/response models: 13 endpoints still lack `response_model` (WARN — raw dicts may leak internal columns)
- Path parameters: `profile_id` declared as `str` but repos call `UUID()` — invalid strings cause unhandled `ValueError` (WARN)
- HTTP status codes: PASS
- Dependency injection chains: PASS (all resolve correctly)

**B. Security Validation**
- Authentication coverage: 4 critical gaps found (see fixes below)
- Tenant isolation: PASS on all routes except `/commands/` (no `user_id`)
- JWT token flow: PASS (access + refresh creation, separate keys, rotation)
- Refresh token revocation: FAIL — no denylist mechanism
- Rate limiter logic: PASS (route patterns, check-before-add, sliding window)
- SECRET_KEY validation: PASS

**C. Data Flow Validation**
- `deps.py` reads from `app.state`: PASS
- `paper_trading.py` no longer calls `init_pool()`: PASS
- Repository method signatures match route calls: PASS
- WebSocket used wrong PubSub class: FAIL — `PubSubBroadcaster` is publisher-only
- `exchange_keys.py` created separate `Settings()` instance at import time: FAIL

**D. Error Handling Validation**
- Global exception handlers cover all domain exception types: PASS
- No silent exception swallowing: PASS (1 WARN in profiles create — not logged)
- Error responses don't leak internals: FAIL (3 locations in exchange_keys.py)
- WebSocket listener has no reconnect on Redis disconnect: WARN

**E. Cross-Cutting Concerns**
- Request ID middleware positioned correctly: PASS
- CORS uses `settings.CORS_ORIGINS`: PASS
- `datetime.utcnow()` remaining: FAIL (2 locations: `pnl.py`, `position_repo.py`)
- `/commands/` is a non-functional stub exposed as production endpoint: WARN
- `/ready` does not check actual dependencies: WARN

#### Fixes Applied (7 issues)

| # | Issue | Severity | Resolution |
|---|-------|----------|------------|
| 21 | `/auth/me` broken — `verify_jwt` skipped all `/auth/*` paths, so `get_current_user` always returned 401. | CRITICAL | `verify_jwt` now only skips `/auth/callback` and `/auth/refresh`. |
| 22 | WebSocket used `PubSubBroadcaster` (publisher) instead of subscriber, with incompatible async generator pattern. | CRITICAL | Rewrote to use raw `redis.pubsub()` for multi-channel subscribe with proper `unsubscribe`/`close` cleanup and `CancelledError` handling. |
| 23 | `/commands/` had no `user_id` dependency. Mock logic could affect arbitrary profiles. | CRITICAL | Added `get_current_user` dependency. Returns 501 Not Implemented (stub clearly marked). |
| 24 | No refresh token revocation. Stolen tokens valid for full 7-day lifetime. | CRITICAL | Added Redis denylist (`auth:revoked:{token}` with TTL). Old token revoked on each `/auth/refresh` call. Refresh endpoint checks denylist before accepting. |
| 25 | `exchange_keys.py` leaked raw `str(e)` in 3 HTTP responses. Could expose GCP paths, network topology, library internals. | HIGH | Errors logged server-side with `logger.error()`. Generic messages returned to client. |
| 26 | `exchange_keys.py` created `Settings()` and `SecretManager()` at module import time. Separate settings instance, network side effects during import. | HIGH | Uses shared `from libs.config import settings` singleton. `SecretManager` lazy-initialized via `_get_secret_manager()` on first use. |
| 27 | Remaining `datetime.utcnow()` in `pnl.py` and `position_repo.py`. Returns naive datetime, causes timezone comparison issues. | HIGH | Replaced with `datetime.now(timezone.utc)`. |

#### Remaining Warnings (not yet addressed)

- 13 endpoints lack `response_model` — raw DB dicts may leak internal column names
- `profile_id` path params accept arbitrary strings — `UUID()` conversion can raise unhandled `ValueError`
- `/ready` endpoint does not verify Redis/Postgres connectivity
- WebSocket Redis listener has no reconnection logic on disconnect
- `ReconciliationDriftError` and `SchemaVersionMismatchError` use generic 500 handler
- CORS `allow_methods=["*"]` and `allow_headers=["*"]` are permissive for a trading API

---

## Files Modified (19 total)

```
libs/config/settings.py
libs/storage/repositories/profile_repo.py
libs/storage/repositories/order_repo.py
libs/storage/repositories/pnl_repo.py
libs/storage/repositories/position_repo.py
services/api_gateway/src/main.py
services/api_gateway/src/deps.py
services/api_gateway/src/middleware/auth.py
services/api_gateway/src/middleware/rate_limit.py
services/api_gateway/src/routes/auth.py
services/api_gateway/src/routes/profiles.py
services/api_gateway/src/routes/orders.py
services/api_gateway/src/routes/pnl.py
services/api_gateway/src/routes/agents.py
services/api_gateway/src/routes/backtest.py
services/api_gateway/src/routes/ws.py
services/api_gateway/src/routes/paper_trading.py
services/api_gateway/src/routes/commands.py
services/api_gateway/src/routes/exchange_keys.py
```

---

## Session 2 — 2026-03-16

### Multi-Agent Review & Remediation

**Task:** Implement the full remediation plan produced by 6 specialist agents (Security Engineer, Frontend Developer, AI Engineer, DevOps Automator, Autonomous Optimization Architect, Reality Checker) who collectively identified ~120 issues.

**Reality Checker initial verdict:** D+ / FAILED — NOT PRODUCTION READY

---

### Phase 1 — Critical Security & Bug Fixes (12 issues)

**Agent: Orchestrator (direct)**

| # | Issue | File(s) | Resolution |
|---|-------|---------|------------|
| 28 | Leaked Google OAuth credentials in `.env.local` | `frontend/.env.local` | Replaced with `CHANGE_ME` placeholders. Created `.env.local.example`. |
| 29 | Weak `NEXTAUTH_SECRET` (`ggmu4464`) | `frontend/.env.local` | Replaced with instruction to generate 32+ byte random value. |
| 30 | `.dev_secrets/` tracked in git (Fernet key exposed) | `.gitignore` | Added `.dev_secrets/` and `frontend/.env.local` to `.gitignore`. |
| 31 | Default `SECRET_KEY` only blocked when `TRADING_ENABLED=true` | `services/api_gateway/src/main.py` | Startup now blocked in ALL modes with insecure default. |
| 32 | `REFRESH_SECRET_KEY` fell back to `SECRET_KEY` | `services/api_gateway/src/middleware/auth.py` | Fallback removed. Startup requires explicit `REFRESH_SECRET_KEY`. |
| 33 | NextAuth callback missing `id_token` for backend verification | `frontend/app/api/auth/[...nextauth]/route.ts` | Encodes signed session token via `next-auth/jwt` and sends to backend. |
| 34 | `Regime.HIGH_VOL` — enum member doesn't exist (should be `HIGH_VOLATILITY`) | `libs/indicators/_regime.py:48` | Fixed to `Regime.HIGH_VOLATILITY`. |
| 35 | Validation stream name mismatch — published to `"stream:validation_responses"` (plural) but consumer reads `"stream:validation_response"` (singular) | `services/validation/src/main.py:69` | Replaced hardcoded string with `VALIDATION_RESPONSE_STREAM` constant. |
| 36 | `check_2_hallucination.py` NameError — `simulate_correct` vs `simulated_correct` | `services/validation/src/check_2_hallucination.py:28` | Fixed variable name to `simulated_correct`. |
| 37 | WebSocket broadcast all PnL to all users | `services/api_gateway/src/routes/ws.py` | Rewrote `ConnectionManager` to track per-user connections. PnL filtered by `user_id`. |
| 38 | Exchange key test only called `fetch_balance()` — no withdrawal permission check | `services/api_gateway/src/routes/exchange_keys.py` | Added withdrawal permission detection; rejects keys with withdraw access. |

---

### Phase 2 — Replace Mock/Stub Implementations (13 issues)

**Agent: Backend Architect**

| # | Issue | File(s) | Resolution |
|---|-------|---------|------------|
| 39 | check_1 Strategy: mocked 5% divergence, always passes | `services/validation/src/check_1_strategy.py` | Fetches last 20 5m candles from TimescaleDB, computes independent RSI via Wilder's smoothing. |
| 40 | check_2 Hallucination: mock data | `services/validation/src/check_2_hallucination.py` | Queries `market_repo.get_candles_by_range()` over 30-min window to verify sentiment vs actual price move. |
| 41 | check_4 Drift: hardcoded Sharpe ratios | `services/validation/src/check_4_drift.py` | Live Sharpe from 7-day PnL snapshots. Backtest Sharpe from `backtest_repo`. |
| 42 | check_5 Escalation: `print()` instead of pubsub, halt commented out | `services/validation/src/check_5_escalation.py` | Real `PubSubBroadcaster.publish()` to `PUBSUB_SYSTEM_ALERTS`. Writes `halt:{profile_id}` key to Redis with 24h TTL. |
| 43 | check_6 Risk Level: only checks `qty > 1000` | `services/validation/src/check_6_risk_level.py` | Loads profile `risk_limits` from DB. Checks max allocation %, stop-loss, drawdown, and 10K hard cap. |
| 44 | Executor: hardcoded Binance testnet, 0.1% fee, ignored ledger returns | `services/execution/src/executor.py` | Per-order adapter resolution via user exchange keys. Exchange-specific fee rates. Ledger return value checks with rollback on failure. |
| 45 | Reconciler: `drift = 0.0` stub | `services/execution/src/reconciler.py` | Full reconciliation: loads exchange balances, aggregates DB positions, computes per-currency drift, alerts on >0.1%. |
| 46 | Ledger: `allocation_pct` stores raw qty | `services/execution/src/ledger.py` | Renamed field to `allocated_qty`. |
| 47 | Sentiment scorer: `random.uniform(-1.0, 1.0)` | `services/analyst/src/sentiment_scorer.py` | Rule-based keyword scoring engine (36+ weighted keywords). Confidence scales with match density. |
| 48 | Alerter: stdout-only logging | `services/logger/src/alerter.py` | PagerDuty Events API v2 + Slack Incoming Webhook dispatch via `httpx`. Falls back to logging if unconfigured. |
| 49 | Daily report: hardcoded fake metrics | `scripts/daily_report.py` | Real SQL queries: trade count, gross/net PnL, win rate, max drawdown, Sharpe ratio. |
| 50 | Archiver: `pass` body | `services/archiver/src/migrator.py` | Three-stage pipeline: Redis TTL cleanup, hot-to-archive table migration (5 tables), auto-create archive tables. |
| 51 | Tax calculator: always returns zeros | `services/pnl/src/main.py` | Calls `USTaxCalculator.calculate()` with real holding duration and gross PnL. Exchange-specific fee rates. |
| 52 | Risk service: blank `__init__.py` | `services/risk/src/__init__.py` | `RiskService.check_order()`: 5-layer check (notional cap, allocation %, concentration 25%, position count 50, halt key). |
| 53 | Learning loop: `events = []  # MOCK` | `services/validation/src/learning_loop.py` | Queries `validation_repo.get_recent_events()` per check type, filters RED/AMBER verdicts. |

---

### Phase 3 — Hot Path Performance Fixes (10 issues, 50ms deadline)

**Agent: Backend Architect**

| # | Issue | File(s) | Resolution |
|---|-------|---------|------------|
| 54 | Validation RPC polling loop wastes 5-15ms | `services/hot_path/src/validation_client.py`, `services/validation/src/main.py` | Replaced with single `BLPOP` on `validation:resp:{event_id}`. Fast gate `LPUSH`es response to per-request key with 5s TTL. |
| 55 | `_ensure_group` called on every `consume()` | `libs/messaging/_streams.py` | Cached known groups in `_known_groups: set`. Only issues `XGROUP CREATE` for unseen groups. |
| 56 | Two sequential Redis GETs in agent_modifier | `services/hot_path/src/agent_modifier.py` | Single `pipeline(transaction=False)` fetches both TA + sentiment scores in one round trip. |
| 57 | Regime read from Redis on every tick | `services/hot_path/src/regime_dampener.py` | 1-second in-process cache via `time.monotonic()` with `_regime_cache` dict. |
| 58 | `update(price, price, price)` gives zero ATR | `services/hot_path/src/strategy_eval.py` | Uses `tick.bid`/`tick.ask` as low/high, or `max/min(price, prev_close)` when bid/ask unavailable. |
| 59 | Pydantic `model_dump`/`model_validate` too slow | `libs/messaging/_serialisation.py` | Fast path: `__dict__` iteration + msgpack. Pydantic fallback only on exception. |
| 60 | PubSub uses JSON serialization | `libs/messaging/_pubsub.py` | Switched to `encode_event()` (msgpack). |
| 61 | `uuid4()` syscall on every event | `libs/core/schemas.py` | Monotonic ID factory: process ID + atomic counter. No syscall. |
| 62 | PnL sync race: pubsub increments vs polling overwrites | `services/hot_path/src/pnl_sync.py` | Atomic `HINCRBY` on `pnl:daily:{profile_id}` hash field. Poll reads same hash instead of overwriting. |
| 63 | Allocation tracking: non-atomic read-modify-write | `services/execution/src/ledger.py` | Lua script atomically reads JSON, increments `allocated_qty`, writes back with TTL. |
| 64 | Circuit breaker daily PnL never resets | `services/hot_path/src/circuit_breaker.py` | Auto-reset on date change via `_last_reset_date` dict. |

---

### Phase 4 — AI/ML Agent Improvements (9 issues)

**Agent: AI Engineer**

| # | Issue | File(s) | Resolution |
|---|-------|---------|------------|
| 65 | HMM trains and predicts on same data | `services/regime_hmm/src/main.py` | Train on `prices[:-1]`, predict on full series (last point unseen). |
| 66 | Regime mapper assumes fixed state ordering | `services/regime_hmm/src/regime_mapper.py` | Emission-characteristic-based classification: normalized volatility percentile + mean return direction. |
| 67 | `model.fit()` blocks async event loop | `services/regime_hmm/src/main.py` | Wrapped in `asyncio.to_thread()` with `asyncio.wait_for()` 30s timeout. |
| 68 | `or True` forces re-fit every cycle | `services/regime_hmm/src/main.py` | Removed `or True`. Condition now works as intended. |
| 69 | TA agent only fetches 50 candles (MACD needs 35 warmup) | `services/ta_agent/src/main.py` | Increased to 150 candles via `CANDLE_LIMIT` constant. |
| 70 | Confluence scoring is binary +1/-1 | `services/ta_agent/src/confluence.py` | Continuous signals: RSI → `(50-rsi)/50`, MACD → `histogram/|macd_line|`. |
| 71 | Sentiment prompt: no JSON extraction, no retry, no rate limiting | `services/sentiment/src/scorer.py` | `_extract_json()` with regex fallback, 2-attempt retry, 2s rate limiter. |
| 72 | Agent modifier multiplicative compounding drives confidence → 0 | `services/hot_path/src/agent_modifier.py` | Additive adjustment (TA ±0.20, sentiment ±0.15) with clamp [0.0, 1.0]. |
| 73 | Hardcoded symbol lists in 3 agents | `libs/config/settings.py`, `services/regime_hmm/src/main.py`, `services/ta_agent/src/main.py`, `services/sentiment/src/main.py` | Centralized `TRADING_SYMBOLS` in settings (`PRAXIS_TRADING_SYMBOLS` env var). |

---

### Phase 5 — Frontend Fixes (15 issues)

**Agent: Frontend Developer**

| # | Issue | File(s) | Resolution |
|---|-------|---------|------------|
| 74 | authStore JWT always null — WebSocket never authenticates | `frontend/lib/stores/authStore.ts`, `frontend/components/providers/AuthProvider.tsx` | `SessionSync` component reads `session.accessToken` from NextAuth and pushes into Zustand store. |
| 75 | JWT passed in WebSocket URL query param (logged in server logs) | `frontend/lib/ws/client.ts` | JWT sent as first message (`{ type: "auth", token }`) after `onopen`. |
| 76 | Duplicate auth guard (AppShell + AuthGuard) | `frontend/components/providers/AuthGuard.tsx` | Reduced to deprecated no-op passthrough. All auth in `AppShell.tsx`. |
| 77 | Unsafe `(session as any)` type casts | `frontend/app/settings/page.tsx`, `frontend/types/next-auth.d.ts` | Created NextAuth type declarations with `accessToken`, `provider`, `backendUserId`. Removed all casts. |
| 78 | No ErrorBoundary anywhere | `frontend/components/providers/ErrorBoundary.tsx`, `frontend/app/layout.tsx` | Class-based ErrorBoundary with styled fallback. Wraps entire app in layout. |
| 79 | Backtest polling: no cleanup on unmount | `frontend/app/backtest/page.tsx` | Added `pollTimerRef` + `cancelledRef` with `useEffect` cleanup. |
| 80 | No API response validation | `frontend/lib/api/client.ts` | Zod schemas for profiles, exchange keys, backtest results. `validatedRequest()` helper. |
| 81 | Settings preferences not persisted (toast only) | `frontend/app/settings/page.tsx`, `frontend/lib/api/client.ts` | Added `api.preferences.save()` / `api.preferences.get()`. Preferences sent to backend. |
| 82 | Empty `next.config.ts` | `frontend/next.config.ts` | `reactStrictMode`, image remote patterns (Google/GitHub avatars), 6 security headers (CSP, HSTS, etc). |
| 83 | Hardcoded `ws://localhost:8000/ws` | `frontend/lib/ws/client.ts` | Dynamic URL from `NEXT_PUBLIC_API_URL` with `http→ws` / `https→wss` conversion. |
| 84 | `<a>` tags instead of `next/link` | `frontend/components/providers/AppShell.tsx`, `frontend/app/page.tsx` | Replaced 8 anchor tags with `<Link>` components. |
| 85 | "Strategy Strategy Editor" typo | `frontend/components/profiles/JSONRuleEditor.tsx` | Fixed to "Strategy Editor". |
| 86 | Static "Active" connection indicator | `frontend/components/providers/AppShell.tsx` | Reflects real WebSocket state: green pulse "Connected" / grey "Disconnected". |
| 87 | Hardcoded "$0.00" Invested and tax estimate | `frontend/components/pnl/PortfolioSummaryCard.tsx` | Computed from real portfolio data and `totalTaxEst` from PnL snapshots. |

---

### Phase 6 — DevOps & Infrastructure (18 issues)

**Agent: DevOps Automator**

| # | Issue | File(s) | Resolution |
|---|-------|---------|------------|
| 88 | No `.dockerignore` | `.dockerignore` | Created with exclusions for `.git`, `node_modules`, `.next`, `__pycache__`, secrets, tests, docs. |
| 89 | TimescaleDB unpinned (`latest-pg15`) | `deploy/docker-compose.yml` | Pinned to `2.13.1-pg15`. |
| 90 | Redis: no authentication, bound to 0.0.0.0 | `deploy/docker-compose.yml` | Added `--requirepass`, bound to `127.0.0.1`, maxmemory 256mb. |
| 91 | No resource limits on containers | `deploy/docker-compose.yml` | Redis: 512m/0.5 CPU. TimescaleDB: 1g/1.0 CPU. |
| 92 | No health checks with `start_period` | `deploy/docker-compose.yml` | Improved health checks for both services with `start_period`. |
| 93 | No network segmentation | `deploy/docker-compose.yml` | `internal` (bridge, internal-only) + `external` (bridge) networks. |
| 94 | Test compose uses same ports as dev | `deploy/docker-compose.test.yml` | Redis: `6380:6379`. TimescaleDB: `5433:5432`. |
| 95 | Dockerfile: no non-root user, no multi-stage | `docker/base.Dockerfile` | Multi-stage build (builder + runtime). Non-root `appuser` (uid 1000). |
| 96 | No CI/CD pipeline | `.github/workflows/ci.yml` | 6-job pipeline: lint, test-unit, test-integration, security-scan, frontend-lint, docker-build. |
| 97 | No K8s manifests | `deploy/k8s/base/namespace.yaml`, `deploy/k8s/base/kustomization.yaml` | Base namespace + kustomization with common labels. |
| 98 | `/ready` doesn't check Redis/Postgres | `services/api_gateway/src/routes/health.py` | Real connectivity checks: Redis `health_check()` + TimescaleDB `SELECT 1`. Returns 503 on failure with per-dependency status. |
| 99 | No `REDIS_PASSWORD` in config | `.env`, `config/.env.example` | Added `REDIS_PASSWORD` field with documentation. |

---

### Files Modified (Session 2 — ~60 files)

```
# Phase 1 — Security & Bugs
.gitignore
frontend/.env.local
frontend/.env.local.example
frontend/app/api/auth/[...nextauth]/route.ts
libs/indicators/_regime.py
services/api_gateway/src/main.py
services/api_gateway/src/middleware/auth.py
services/api_gateway/src/routes/exchange_keys.py
services/api_gateway/src/routes/ws.py
services/validation/src/check_2_hallucination.py
services/validation/src/main.py

# Phase 2 — Mock Replacements
scripts/daily_report.py
services/analyst/src/sentiment_scorer.py
services/archiver/src/migrator.py
services/execution/src/executor.py
services/execution/src/ledger.py
services/execution/src/reconciler.py
services/logger/src/alerter.py
services/pnl/src/main.py
services/risk/src/__init__.py
services/validation/src/check_1_strategy.py
services/validation/src/check_4_drift.py
services/validation/src/check_5_escalation.py
services/validation/src/check_6_risk_level.py
services/validation/src/learning_loop.py

# Phase 3 — Hot Path Performance
libs/core/schemas.py
libs/messaging/_pubsub.py
libs/messaging/_serialisation.py
libs/messaging/_streams.py
services/hot_path/src/agent_modifier.py
services/hot_path/src/circuit_breaker.py
services/hot_path/src/pnl_sync.py
services/hot_path/src/regime_dampener.py
services/hot_path/src/strategy_eval.py
services/hot_path/src/validation_client.py

# Phase 4 — AI/ML
libs/config/settings.py
services/hot_path/src/agent_modifier.py
services/regime_hmm/src/main.py
services/regime_hmm/src/regime_mapper.py
services/sentiment/src/main.py
services/sentiment/src/scorer.py
services/ta_agent/src/confluence.py
services/ta_agent/src/main.py

# Phase 5 — Frontend
frontend/app/backtest/page.tsx
frontend/app/layout.tsx
frontend/app/page.tsx
frontend/app/settings/page.tsx
frontend/components/pnl/PortfolioSummaryCard.tsx
frontend/components/profiles/JSONRuleEditor.tsx
frontend/components/providers/AppShell.tsx
frontend/components/providers/AuthGuard.tsx
frontend/components/providers/AuthProvider.tsx
frontend/components/providers/ErrorBoundary.tsx (new)
frontend/lib/api/client.ts
frontend/lib/stores/authStore.ts
frontend/lib/ws/client.ts
frontend/next.config.ts
frontend/types/next-auth.d.ts (new)

# Phase 6 — DevOps
.dockerignore (new)
.env
.github/workflows/ci.yml (new)
config/.env.example
deploy/docker-compose.yml
deploy/docker-compose.test.yml
deploy/k8s/base/kustomization.yaml (new)
deploy/k8s/base/namespace.yaml (new)
docker/base.Dockerfile
services/api_gateway/src/routes/health.py
```
