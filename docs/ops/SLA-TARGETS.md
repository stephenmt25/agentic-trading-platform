# SLA Targets — v1 PROPOSED (dev-box)

> **Status: PROPOSED (dev-box), 2026-06-13.** Closes DOCUMENTATION-GAPS **G-1** at v1 per
> ruling D-L (2026-06-13 debt burn-down): numbers that code/config already pins are cited
> with file:line; everything else is a PROPOSED target derived from local measurements on
> the dev box (Windows 11, Docker Desktop, local Redis/TimescaleDB) and needs ops review
> before being treated as a production commitment. No load balancer, no replicas, single
> host — these are *targets to alert against locally*, not contractual SLAs.

## Pinned by code/config (not proposals — these are enforced or configured today)

| Target | Value | Source |
|---|---|---|
| Fast-gate response timeout (hot_path waits this long for validation) | **50 ms** | `FAST_GATE_TIMEOUT_MS` — `libs/config/settings.py:76`, `libs/core/constants.py:3`, consumed at `services/hot_path/src/main.py:106` |
| Fast-gate soft-warning threshold (validation-internal) | 35 ms | `services/validation/src/fast_gate.py:40` (warning log only, not a cutoff) |
| Gateway per-route rate limit | 60 req/min per user-or-IP per route (auth routes: 10/min) | `RateLimiterMiddleware` defaults — `services/api_gateway/src/middleware/rate_limit.py:86-93` |
| Kill-switch write rate limit | 10 writes/min per user (post-auth bucket) | `services/api_gateway/src/routes/commands.py:22` |
| Exchange API quotas | Binance 1200/min · Coinbase 300/min · default 600/min | `libs/exchange/_rate_limiter_client.py:27-30` |
| Redis client socket timeout / connect timeout | 5.0 s / 2.0 s (default pool) | `libs/storage/_redis_client.py` (registry row 33 fix) |
| DB pool per service | min 5 / max 20, acquire timeout 30 s | `libs/config/settings.py:132-134` |
| Portfolio risk snapshot cadence | 10 s | `PORTFOLIO_AGGREGATOR_INTERVAL_S` — `settings.py:65` |
| Halt controller cadence / auto-flatten dwell | 10 s / 30 s | `settings.py:43-44` |
| HITL human-response window | 60 s then fail-safe reject | `HITL_TIMEOUT_S` — `settings.py:166` |
| hot_path order-burst tripwire | WARN >10, CRITICAL >25 orders/profile/60 s | `services/hot_path/src/processor.py:64-66` |

## PROPOSED service targets (dev-box derivation in parentheses)

P95 unless stated. "Degraded" = threshold for the alerting rules in
[ALERTING.md](ALERTING.md).

| Surface | PROPOSED target | Degraded above | Derivation |
|---|---|---|---|
| `GET /health` (any service) | < 100 ms | 1 s | static responses; gateway answered < 50 ms locally throughout the 2026-06-13 WS bench |
| `GET /ready` (gateway, checks Redis+PG) | < 500 ms | 2 s | bounded by one Redis ping + one PG query on a healthy box |
| `GET /commands/kill-switch` | < 1 s; **< 5.5 s with Redis dead** (fail-safe must still answer) | 5.5 s | measured 345 ms healthy / 288 ms with Redis stopped (registry row 33 validation, 2026-05-12); the 5 s Redis `socket_timeout` bounds the worst case |
| Gateway REST reads (profiles, positions, orders, risk) | < 500 ms | 2 s | local polls run well under this; un-instrumented — needs a real latency histogram before tightening |
| `POST /orders` (submit) | < 1 s to accepted-on-stream | 3 s | enqueue + validation round-trip; fast gate bounded at 50 ms of that |
| WS handshake (`/ws`, ≤ 50 concurrent clients) | < 500 ms | 2 s | measured med 95–134 ms at N=25–50 (`scripts/ws_bench.py`, 2026-06-13; see [WS-LIMITS.md](WS-LIMITS.md)) |
| WS time-to-first-message (≤ 50 clients) | < 1 s | 5 s | measured med 211–355 ms at N=25–50 |
| Tick → P&L update on `pubsub:pnl_updates` | < 2 s | 10 s | per-tick recompute path; un-instrumented end-to-end |
| Market-data staleness (ingestion → Redis) | < 10 s between events per symbol | 60 s | S1 resilience run: pubsub silent within 12 s of ingestion death is the detection signal |
| Backtest job (single run, default window) | < 600 s | hard timeout | 600 s per-job cap pinned in the EN-W1 walk-forward work (registry row 55) |
| Frontend prod LCP on `/hot` | < 2.5 s | — | measured 675 ms prod build (FE-W2, 2026-06-12); 2.5 s is the Web Vitals "good" bound |

## Availability (PROPOSED — single-host reality)

- There is **no HA**: one host, one process per service, supervised restart inside each
  process (`supervised_task`) but no external process supervisor beyond `run_all.sh`.
  A realistic availability statement today is "best effort; minutes-scale MTTR via
  `bash run_all.sh --local-frontend`" (S1/S2 resilience runs recovered in ~10–30 s once
  the restart command ran).
- PROPOSED: treat **trading-path liveness** (ingestion → hot_path → validation →
  execution heartbeats, see logger heartbeat scan) as the availability SLI, target 99%
  measured weekly during paper trading; revisit with real infra (Phase 2 P-1/P-3).

## Review checklist before these become real SLAs

1. Wire latency histograms (even log-derived) for gateway REST + order path — most REST
   targets above are eyeballed, not measured distributions.
2. Re-run `scripts/ws_bench.py` and the resilience playbook on the production-shaped
   host once one exists.
3. Partner sign-off (these numbers gate ALERTING.md thresholds).
