# Disaster Recovery Playbook — v1 PROPOSED (dev-box)

> **Status: PROPOSED (dev-box), 2026-06-13.** Closes DOCUMENTATION-GAPS **G-3** at v1 per
> ruling D-L. The S1–S3 failure domains below carry **real evidence** from the 2026-05-11
> resilience run (`docs/design/perf-traces/2026-05-11-resilience-results.md`, playbook
> `docs/design/PHASE-8-RESILIENCE-PLAYBOOK.md`) and the 2026-05-12 row-33 fix validation.
> The domains never injected locally (TimescaleDB loss, full-host loss, exchange outage)
> are honestly marked **untested** with the expected behavior derived from code.

## Safety invariants that hold in every scenario (verified)

- **Kill switch fails safe.** `KillSwitch.is_active()` returns ACTIVE on any Redis
  error; with Redis stopped, `GET /commands/kill-switch` answered `active=true` in
  **288 ms** (validated 2026-05-12 after the row-33 socket-timeout fix; before that fix
  it hung — see "Redis loss" below).
- **Halt state survives restarts.** The kill switch lives in the Redis key
  `praxis:kill_switch` (AOF-persisted); restarting services or Redis does NOT clear a
  halt — an operator must clear it explicitly.
- **Streams redeliver.** Consumer groups + stale-event guards (execution skips orders
  > 60 s old; hot_path skips ticks > 60 s old) mean a crash cannot silently drop or
  belatedly fire trades.
- **Rate limiter fails open** on Redis loss (`middleware/rate_limit.py`) so the
  kill-switch endpoint stays reachable during the exact outage where it matters.

## Failure domain 1 — market-data loss (ingestion death / exchange WS drop) — TESTED

**Evidence (S1, 2026-05-11):** pubsub silent within 12 s of kill; UI froze honestly with
`stale` badges; no white screen; recovery ~31 s after restart (exchange WS warmup), no
page reload.

1. Detect: tape/orderbook staleness on `/hot`; `.praxis_logs/ingestion.log`.
2. No trading risk while data is stale: hot_path's stale-tick guard stops acting on old
   data, and no fresh signals fire without fresh ticks. Positions remain protected by
   the PnL-side `ExitMonitor` only while ticks flow — **if the outage is long, consider
   arming the kill switch** (`POST /commands/kill-switch`, STOP_OPENING or higher).
3. Recover: `bash run_all.sh --stop && bash run_all.sh --local-frontend` (single-service
   restarts leave the PID file stale — see SHUTDOWN.md). Candle gaps backfill via REST
   on startup (`libs/exchange/backfill.py`).

## Failure domain 2 — gateway loss (REST + WS) — TESTED

**Evidence (S2, 2026-05-11):** connection pill flipped offline in ~3 s; kill-switch modal
surfaced a readable error; WS-driven panels degraded to awaiting-feed (the WS endpoint
IS the gateway — corrected in the resilience playbook 2026-06-13); auto-recovery ~10 s
after restart.

1. Trading continues headless (hot_path/execution don't depend on the gateway), but
   operators lose **visibility and the kill-switch API**. That makes this higher
   severity than it looks: treat > 5 min of gateway loss as a halt-worthy incident —
   the fallback control is setting the Redis key directly:
   `docker exec deploy-redis-1 redis-cli -a <pw> -n 1 SET praxis:kill_switch FLATTEN`
   (verb values: `libs/core/enums.py` HaltLevel).
2. Recover: full relaunch as above; frontend reconnects without F5.

## Failure domain 3 — Redis loss (messaging + state) — TESTED

**Evidence (S3, 2026-05-11 + 2026-05-12 re-validation):** trading halts by construction
(every gate path errors → fail-safe); kill-switch endpoint answers ACTIVE in < 300 ms;
WS sockets stay open but silent (Redis is the backend behind the WS handler, not the WS
transport); server-side pubsub resubscribes with 1→30 s backoff on restore; the chrome
`degraded` pill is driven by `/ready` (ADR-017).

1. Detect: `/ready` returns 503; degraded pill; every stream consumer logs timeouts.
2. Do NOT restart services while Redis is down (boot AOF replay + 19 services
   reconnecting makes it worse — registry row 45). Restore Redis first:
   `docker start deploy-redis-1` (or `docker compose -f deploy/docker-compose.yml up -d redis`).
   Health probe can take ~2 min to PONG (observed).
3. After restore: services reconnect on their own (health_check_interval=15 keeps pools
   honest). Grep `.praxis_logs/*.log` for `loop crashed`. The kill switch will read
   whatever the key holds — if the failure armed it, **clearing it is an explicit
   operator decision**, not part of recovery.
4. Data loss: Redis is AOF-persisted; a container stop loses nothing. Loss of the
   *volume* loses stream backlogs, daily P&L counters, compiled rules, indicator caches
   — all reconstructible (hydration at boot, counters rebuild from DB closes), but daily
   circuit-breaker state resets. PROPOSED: accept this (paper trading); revisit for live.

## Failure domain 4 — TimescaleDB loss — UNTESTED (derived from code)

- Expected: gateway REST 5xx on DB-backed routes; `/ready` 503; hot_path keeps
  evaluating (state is in Redis) but execution cannot persist fills — the optimistic
  ledger + reconciler are the safety net; daily_report dies (registry row 42 fix adds
  retry). **Arm the kill switch first** if the outage exceeds minutes.
- Recover: `docker start deploy-timescaledb-1`; then full relaunch to re-run migrations
  and reconcile (`run_all.sh` does both). Reconciler + `scripts/scan_redis_invariants.py`
  to verify coherence.
- **Corruption/loss of the volume:** restore from the most recent `pg_dump` following
  the worked procedure in `docs/ROLLBACK-PROCEDURE.md` (full restore incl. hypertable
  fallback path). **PROPOSED gap: there is no scheduled pg_dump today** — backups exist
  only when taken manually before risky sessions. Adopt a daily dump before live
  trading. TODO(ops-review).

## Failure domain 5 — exchange API outage (Binance) — UNTESTED

- Market data: ingestion's exchange WS drops → behaves as domain 1 (stale, guarded).
- Order routing (testnet today): ccxt errors → executor marks the order failed and
  rolls back the ledger; rate-limiter quotas prevent hammering
  (`_rate_limiter_client.py`). Open positions: exchange-resident protective stops are
  OFF by default (`PROTECTIVE_STOP_ENABLED=false`, `settings.py:34`) — during a
  *sustained* exchange outage, stop-loss enforcement (PnL-side) cannot execute closes
  either; this is an accepted paper-trading risk. PROPOSED: revisit before live (enable
  protective stops once validated).

## Failure domain 6 — full host loss — UNTESTED

What exists off-host vs on-host today:

| Asset | Recoverable from | Notes |
|---|---|---|
| Code | GitHub (`origin`) | full history; CI on PRs |
| DB data | **manual** `pg_dump` files under `backups/` (gitignored, on-host!) | no off-host copy — a true host loss loses trading history. TODO(ops-review) |
| Redis state | nothing | reconstructible operational state (see domain 3.4) |
| `.env` (secrets) | nowhere (gitignored, on-host) | re-creatable by hand; see [KEY-ROTATION.md](KEY-ROTATION.md) inventory |

Rebuild order on a fresh machine: clone → install Docker/Poetry/Node → recreate `.env`
→ `bash run_all.sh --local-frontend` (migrations run automatically) → restore DB dump if
one survives. PROPOSED: archiver GCS export (D-21) is the designed off-host path; it is
**blocked-on-cloud** until a GCS bucket exists.

## Cloud region failure

Not applicable — there is no cloud deployment (Phase 2 P-1/P-2 unstarted). This section
exists so the gap is explicit rather than silent.
