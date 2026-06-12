# Capacity Planning — v1 PROPOSED (dev-box)

> **Status: PROPOSED (dev-box), 2026-06-13.** Closes DOCUMENTATION-GAPS **G-2** at v1 per
> ruling D-L. Method: read the limits the code/config already pins, plus one bounded live
> benchmark (`scripts/ws_bench.py`, run 2026-06-13 against the live local stack). Every
> extrapolation is marked. Re-derive on production hardware before trusting any of this
> beyond the dev box (Windows 11, Docker Desktop WSL2, single host).

## 1. WebSocket fan-out (measured — the one real benchmark)

Full numbers and method in [WS-LIMITS.md](WS-LIMITS.md). Headline:

- **~50 concurrent WS clients is the fully-served ceiling today.** At N=100 only 52/100
  clients ever received a message; at N=200 only 36/200 — handshakes succeed at 100% all
  the way to 200, so *handshake success is not a capacity signal* (the gateway accepts
  before it subscribes).
- Binding constraint: each WS connection creates its **own Redis pubsub connection**
  (`services/api_gateway/src/routes/ws.py:238`) from a pool capped at
  `max_connections=100` (`libs/storage/_redis_client.py:19`) that is **shared with every
  REST endpoint** in the gateway. The ceiling is an architectural constant, not a
  hardware number — more CPU will not raise it.
- PROPOSED capacity statement: plan for **≤ 40 concurrent dashboard sessions** per
  gateway process (leaves pool headroom for REST), until the WS handler is reworked to a
  shared fan-out subscription (one pubsub for all connections).

## 2. Symbol scaling (derived from config + observed rates — PROPOSED)

- Today: `TRADING_SYMBOLS = ["BTC/USDT", "ETH/USDT"]` (`libs/config/settings.py:137`).
- Observed per-symbol pubsub rates on the live stack (2026-05-11 sampling, registry
  row 27): orderbook ~20 Hz, trades ~33 Hz → **~50–55 msg/s per symbol** on the WS
  channels (both channels are global, not per-symbol — every WS client receives every
  symbol's traffic).
- Measured aggregate fan-out throughput during the 2026-06-13 bench: **up to ~4,650
  msg/s / ~2.8 MB/s** sustained across clients (N=100 step) with the gateway remaining
  healthy (`/health`, `/ready` 200 throughout). Message rate is market-dependent —
  treat as an observed point, not a max.
- PROPOSED extrapolation (unverified): WS send cost scales ≈ clients × symbols × 50
  msg/s. At the recommended 40 clients, a 3rd–5th symbol stays within the measured
  envelope; beyond ~10 symbols, per-symbol channel subscriptions (server-side filtering)
  are needed so clients stop receiving everything. Ingestion itself adds one exchange WS
  per symbol and one candle aggregator — untested beyond 2 symbols; test before adding.
- `stream:market_data` is capped at 10,000 entries
  (`services/ingestion/src/main.py:55`) and hot_path skips ticks older than 60 s
  (`processor.py:50`), so symbol growth cannot unboundedly bloat Redis AOF — backlog is
  bounded per restart.

## 3. Profiles (derived from code paths — PROPOSED, untested at scale)

- Every active profile is evaluated per tick in hot_path (per-profile indicator update +
  rule eval + gate sequence). The soak runs 1–4 profiles; nothing pins a max.
- Strategy worker re-polls/re-compiles all profiles every 60 s
  (`services/strategy/src/main.py` `POLL_INTERVAL_S`).
- Hot-path protections that bound per-profile damage, regardless of count: order-burst
  tripwire (WARN >10 / CRITICAL >25 orders per profile per 60 s,
  `services/hot_path/src/processor.py:64-66`), circuit breaker
  (`CIRCUIT_BREAKER_DAILY_LOSS_PCT=0.02`, `settings.py:77`), portfolio gross budget
  (`PORTFOLIO_GROSS_BUDGET_USD=100000`, cluster cap 40% — `settings.py:51-55`).
- PROPOSED: stay ≤ 10 active profiles until a tick-loop latency measurement under load
  exists (the per-tick loop is sequential per event — many profiles stretch tick
  processing latency linearly).

## 4. Database connections (derived from config — PROPOSED, needs verification)

- Each service builds its own asyncpg pool: min 5 / max 20 (`settings.py:132-134`).
  ~20 Python processes × min 5 = **~100 baseline connections**, bursting toward 400
  theoretical max — against a single TimescaleDB container (PostgreSQL default
  `max_connections=100` unless the image overrides it).
- This is the most likely silent capacity wall on the dev box (boot contention already
  produced the registry row 42 daily_report timeout). PROPOSED: verify actual connection
  count (`SELECT count(*) FROM pg_stat_activity`) during a relaunch and either lower
  `DB_POOL_MIN_SIZE` or raise PG `max_connections` deliberately.

## 5. Backtesting (pinned)

- Queue depth cap 100 (`BACKTEST_MAX_QUEUE_DEPTH`, `settings.py:140`); sweep cardinality
  cap ≤ 100 combos; 600 s per-job timeout (EN-W1/EN-W2, registry rows 55/71). One worker
  consumes the queue — throughput is ~1 job per (runtime ≤ 600 s), serial.

## 6. Redis (pinned + observed)

- Single container, DB 1, AOF on; `maxmemory 256M` observed in the 2026-06-01 incident
  notes (`used_memory` 18M at the time). Streams capped: `stream:orders` 10k
  (`libs/messaging/channels.py:19`), `stream:market_data` 10k
  (`services/ingestion/src/main.py:55`).
- Connection budget is the scarce resource (see §1), not memory, at current scale.

## Re-derivation checklist (when real hardware exists)

1. Re-run `scripts/ws_bench.py` (raise the hard cap deliberately if the pool is fixed).
2. Measure hot_path tick latency vs profile count (10/50/100 synthetic profiles).
3. Count real PG connections at boot and steady state.
4. Load-test ingestion at 5+ symbols on a real exchange connection.
