# WebSocket Connection Limits — v1, measured (dev-box)

> **Status: measured on the dev box, 2026-06-13** (Windows 11, Docker Desktop WSL2,
> single host, live soak stack). Closes DOCUMENTATION-GAPS **G-11** at v1 per ruling D-L.
> Numbers are real measurements, but from one local run against one machine — treat the
> absolute latencies as **dev-box** figures and the *architectural ceiling* as the
> durable finding. Benchmark: `scripts/ws_bench.py` (re-runnable, bounded, ≤ 200 clients,
> < 5 min).

## Architecture (what a "WS connection" costs)

- The only WS endpoint is the api_gateway's `/ws`
  (`services/api_gateway/src/routes/ws.py`); it requires a `?token=` JWT with `sub` +
  `exp` claims (`require=["exp"]` at the decode site).
- The handler **accepts the socket first**, then creates a **dedicated Redis pubsub
  connection per WS connection** (`routes/ws.py:238`) subscribed to 7 channels
  (pnl_updates, system_alerts, agent_telemetry, hitl_pending, orderbook, trades,
  market_sentiment). Both orderbook and trades are global channels — every client
  receives every symbol's traffic.
- That pubsub connection comes from the gateway's default Redis pool,
  `max_connections=100` (`libs/storage/_redis_client.py:19`), **shared with all REST
  handlers**. When the pool is exhausted, `pubsub.subscribe` fails into the handler's
  retry loop (1 s → 30 s backoff) — the WS stays open but **silent**.

## Benchmark method

`poetry run python scripts/ws_bench.py --url ws://127.0.0.1:8000/ws` — ramps independent
steps of N concurrent clients (25/50/100/200), each step ~20 s; JWT minted locally from
`settings.SECRET_KEY`; staggered connects (25 at a time); all sockets closed cleanly per
step; ramp stops if handshake success drops below 80%. Run 2026-06-13 against the live
stack mid-soak; gateway `/health` and `/ready` stayed 200 throughout and the soak was
unaffected.

> Use `127.0.0.1`, not `localhost`: on this Windows box `localhost` adds ~2 s of IPv6
> (::1) fallback to every handshake (measured 2,170 ms vs 25 ms median).

## Results (2026-06-13, dev box)

| N clients | Handshake success | Handshake (med/p95) | Clients receiving data | TTFM (med/p95) | Aggregate throughput |
|---|---|---|---|---|---|
| 25 | 25/25 (100%) | 95 / 98 ms | **25/25** | 211 / 275 ms | 1,359 msg/s · 0.92 MB/s |
| 50 | 50/50 (100%) | 134 / 143 ms | **50/50** | 355 / 756 ms | 1,646 msg/s · 1.63 MB/s |
| 100 | 100/100 (100%) | 349 / 357 ms | **52/100** | 442 / 702 ms | 4,651 msg/s · 2.77 MB/s |
| 200 | 200/200 (100%) | 514 / 541 ms | **36/200** | 605 / 662 ms | 2,244 msg/s · 1.55 MB/s |

(TTFM = time from handshake to first received message. Throughput varies with live
market activity — compare the "clients receiving" column across steps, not msg/s.)

## Findings

1. **The ceiling is ~50 fully-served concurrent connections**, and it is the Redis
   connection pool, not CPU/sockets: N=50 served every client; N=100 served 52; N=200
   served 36 (worse, because 200 retrying subscribers churn the exhausted pool).
2. **Handshake success rate is a misleading capacity metric here** — it was 100% at
   every step including N=200, because the gateway accepts the WS before subscribing to
   Redis. A connection-count health check would happily report 200 "connected" clients
   while 164 of them receive nothing. Monitor *time-to-first-message* or per-connection
   delivery, not connection counts (see [ALERTING.md](ALERTING.md)).
3. Latency degrades gracefully up to the ceiling: handshake median grows 95 → 514 ms
   from N=25 → 200; TTFM for the clients that do get served stays sub-second throughout.
4. The gateway process survived all steps; sockets and pubsubs were released cleanly on
   close (log shows paired "connection closed"; pool recovered immediately — the
   post-run `/ready` was 200).

## PROPOSED operating limits (pending ops review)

- **Plan for ≤ 40 concurrent dashboard WS sessions per gateway process** — leaves
  default-pool headroom for REST traffic sharing the same 100-connection pool.
- Raising `max_connections` lifts the ceiling roughly 1:1 (each WS needs exactly one
  pubsub connection) at the cost of more Redis server connections; the structural fix is
  a **single shared pubsub subscription fanned out to all WS clients in-process** —
  that makes the ceiling OS-socket/CPU-bound instead of pool-bound. Logged as future
  work; not scheduled.
- Re-run `scripts/ws_bench.py` after any change to `_redis_client.py` pool settings,
  the WS handler, or host hardware, and update this file + CAPACITY.md.

## Per-host note

Uvicorn defaults apply (`ws_ping_interval=20 s`, `ws_ping_timeout=20 s` — no override in
`services/api_gateway/src/main.py`). Client-side, the frontend keeps **one** WS
connection per tab (`frontend/lib/ws/client.ts` singleton) with exponential reconnect
backoff capped at 60 s — so "concurrent connections" ≈ concurrent open dashboard tabs.
