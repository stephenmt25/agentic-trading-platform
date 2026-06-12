# Safe System Shutdown

> Rewritten 2026-06-13 (registry item A-4). Derived from `run_all.sh` and each service's
> `main.py` lifespan teardown. Covers the full launch set: **19 HTTP services + the portless
> `strategy` worker + the `daily_report` daemon** (21 tracked processes; +1 `frontend` when
> launched with `--local-frontend`).

## TL;DR — the one supported command

```bash
bash run_all.sh --stop
```

Never stop/start services individually (CLAUDE.md §2C): it leaves zombie processes, port
conflicts, and stale Redis consumer-group state. `--stop` performs a three-layer sweep:

1. **Tracked PIDs** — kills each process **tree** from `.praxis_pids` (`taskkill //F //T`;
   each entry is the poetry wrapper, so the tree kill is what reaps the python child).
2. **Port sweep** — kills any PID still listening on a Praxis port
   (`8000, 8080–8097, 3001`), covering orphans that lost their pidfile entry.
3. **Command-line sweep** — PowerShell `Get-CimInstance Win32_Process` kill of any
   `python.exe` matching `services\.|daily_report` and any `node.exe` matching
   `aion-trading` — this is what catches the portless `strategy` worker and the
   `daily_report` daemon even with no pidfile and no port.

Finally it runs `docker compose -f deploy/docker-compose.yml down` (stops Redis +
TimescaleDB containers; **data volumes are preserved** — only `down -v` would wipe them).

`Ctrl+C` in the foreground `run_all.sh` terminal triggers the same teardown via the
`cleanup` trap (plain `kill` per pidfile entry + compose down) — it is gentler but less
thorough than `--stop`; if in doubt, follow a Ctrl+C with an explicit
`bash run_all.sh --stop`.

## What "graceful" means here

Every HTTP service is a FastAPI app under uvicorn. On SIGTERM/SIGINT uvicorn runs the
lifespan teardown (the code after `yield` in each service's `main.py`), which cancels the
service's background tasks, awaits them (`return_exceptions=True`), stops the telemetry
heartbeat, and closes the TimescaleDB pool. Two platform-level properties make even a
hard kill safe:

- **Redis Streams use consumer groups** — an event consumed but not yet acked at kill time
  is redelivered after restart; messages survive restarts (Redis runs AOF). Consumers carry
  stale-message guards (e.g. execution skips orders older than 60s at boot; hot_path skips
  ticks older than `MAX_TICK_AGE_S=60`), so a backlog drained at the next boot cannot fire
  stale trades.
- **The kill switch lives in Redis** (`praxis:kill_switch`), not in any process — an armed
  halt **survives shutdown and restart** and must be cleared explicitly by an operator via
  `POST /commands/kill-switch`. Restarting the stack never silently re-enables trading.

## Per-service shutdown notes

Ports per `run_all.sh` (the authoritative source). "Teardown" = the lifespan code after
`yield` in `services/<name>/src/main.py`.

| Service | Port | Teardown on graceful stop | Notes / kill-safety |
|---|---|---|---|
| validation | 8081 | Cancels the 3 loops (fast_gate, async_audit, learning_loop); telemetry stop; DB pool close | Unacked validation requests redeliver via consumer group; hot_path fail-closes (rejects) on a missing fast-gate response |
| hot_path | 8082 | Cancels processor task, stall watchdog, pnl_sync, profile-refresh; telemetry stop; DB close | Pending HITL approvals fail-safe reject on timeout; unprocessed ticks older than 60s are skipped at next boot |
| execution | 8083 | Cancels executor loop, reconciler cron, watchdog; telemetry stop; DB close | Optimistic ledger + boot reconciler resolve any order in flight at kill time; stale-order guard (>60s) prevents boot-drain trading |
| pnl | 8084 | Cancels tick listener, rehydrate task, close-consumer, halt controller; telemetry stop; DB close | P&L snapshots are periodic — at most one interval of snapshots is lost; daily counters live in Redis and survive |
| api_gateway | 8000 | DB pool close; uvicorn closes all WebSocket connections | Frontend WS client auto-reconnects with backoff; REST consumers see the connection pill flip offline |
| ingestion | 8080 | Telemetry stop; exchange WS manager stop; **CandleAggregator force-flush** (partial in-memory candles written to DB); DB close | A hard kill loses at most the open (un-flushed) candle buckets; the REST gap-fill (`libs/exchange/backfill.py`) repairs candle gaps on next startup |
| logger | 8085 | Cancels stream subscriber, pubsub subscriber, invariant scanner, 3 heartbeat tasks; DB close | Audit events not yet written redeliver via consumer group |
| backtesting | 8086 | Cancels the job-runner worker; DB close | An in-flight job's queue message stays pending in the consumer group and is re-run after restart |
| analyst | 8087 | Cancels weight-recompute, insight, decay-tracker tasks; telemetry stop; DB close | EWMA tracker state is in Redis; recompute resumes from `last_ts` |
| archiver | 8088 | Cancels the daily cron task; DB close | Chunk archiving is transactional per chunk (copy-verify-drop in one tx) — a kill mid-archive cannot lose rows |
| tax | 8089 | None (stateless request/response service; no lifespan handler) | Safe to kill at any time |
| ta_agent | 8090 | Cancels scoring loop; telemetry stop; DB close | Scores are republished on the next tick |
| regime_hmm | 8091 | Cancels regime loop; telemetry stop; DB close | Regime signal is re-emitted on next fit/emit cycle |
| sentiment | 8092 | Cancels scoring loop; telemetry stop; DB close | Sentiment cache (Redis, TTL 900s) survives restart |
| risk | 8093 | Cancels portfolio-exposure aggregator; telemetry stop; DB close | `risk:portfolio:snapshot` goes stale for at most one 10s interval, refreshed at restart |
| rate_limiter | 8094 | Cancels metrics task | Quota windows are Redis sorted sets — survive restart |
| slm_inference | 8095 | Log only (model memory released with the process) | Safe to kill; reloads model (or mock mode) at startup |
| debate | 8096 | Cancels debate loop; telemetry stop; DB close | In-flight debate is abandoned; next signal triggers a fresh one |
| oracle | 8097 | Cancels refresh/synthetic/actual/divergence tasks; DB close | Layer-3 fail-safe only — no trading state of its own |
| strategy | — (async worker) | `asyncio.run` cancellation → `finally:` closes the DB pool | Compiled rules live in Redis (`strategy:compiled:{profile_id}`) and survive; re-hydration runs at next boot |
| daily_report | — (daemon) | Killed by the pidfile/command-line sweep (no graceful hook) | Report generation is idempotent (upsert) — a report interrupted mid-write is regenerated on the next run or via `POST /paper-trading/reports/generate` |
| frontend (optional) | 3001 | node process killed by sweep | Stateless dev server |

## Frontend (if running)

`--stop` kills the dev server via the pidfile and the node command-line sweep. If you
started a separate prod build (`next start -p 3000`/`3002`), that process is **not** in the
pidfile or port sweep list — stop it manually (Ctrl+C, or find the PID on the port).

## Infrastructure

`--stop` already runs `docker compose -f deploy/docker-compose.yml down`. Manual paths:

```bash
docker compose -f deploy/docker-compose.yml down       # stop containers, KEEP data
docker compose -f deploy/docker-compose.yml down -v    # stop AND WIPE Redis + TimescaleDB data
```

Redis persists via AOF: streams, kill-switch state, daily P&L counters, compiled rules,
and indicator caches all survive a container restart. That is a feature (state continuity)
and a footgun (stale stream backlogs) — which is why every consumer carries a
stale-message guard and `run_all.sh` is the only supported launcher.

## Verification after shutdown

```powershell
# No Praxis python left:
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'services\.|daily_report' }

# No service ports held (8000, 8080-8097, 3001):
Get-NetTCPConnection -LocalPort 8000,8080,8081,8082,8083,8084,8085,8086,8087,8088,8089,8090,8091,8092,8093,8094,8095,8096,8097,3001 -ErrorAction SilentlyContinue

# Containers down:
docker ps --format "table {{.Names}}\t{{.Status}}"
```

All three should return nothing Praxis-related. If a process survives, re-run
`bash run_all.sh --stop` (it is idempotent) before any manual `Stop-Process -Force`.

## Restart

```bash
bash run_all.sh --local-frontend
```

Then grep `.praxis_logs/*.log` for `loop crashed` — the supervisor surfaces latent loop
bugs on relaunch (post-crash loop-health practice). See also
[ops/ROLLBACK.md](ops/ROLLBACK.md) for rolling back a bad deploy rather than just
restarting it.
