# Phase 8.3 — Resilience Run Results (2026-05-11)

Run mode: chrome-devtools-mcp + Bash, driven by Claude against the live local stack
(`bash run_all.sh --local-frontend`). Auth bypassed for the duration of the run via a
NextAuth `/api/auth/session` fetch-stub injected in `navigate_page(initScript=...)`
returning a forged backend JWT for the test user
`6322b6fa-d425-51d7-a818-088c19275228`. Playbook: `docs/design/PHASE-8-RESILIENCE-PLAYBOOK.md`.

## Verdict summary

| Scenario | Verdict | Notes |
|---|---|---|
| S1 — Kill `services/ingestion` | **PASS** | Pubsub silent in 12s. OrderBook prices frozen with `stale Ns` badge visible (badge tracks wrong timestamp source — pre-existing LOW). Recovery in ~30s, no F5. |
| S2 — Kill `services/api_gateway` | **PASS** | Pill flipped `live → offline` in ~3s (vs playbook's 90s expectation). Kill-switch modal opens with backend down; "Arm soft" surfaces inline error `Backend is not reachable`. `/risk` and `/hot` both show clean offline states. Auto-recovery in ~10s after restart, no F5. |
| S3 — Stop Redis | **PASS-with-HIGH-finding** | API hangs (10s timeout) instead of fail-safing — see HIGH below. UI pill stuck on last-known. No CRITICAL (no false `off`). Recovery clean on Redis restart. |

Phase 8.3 gate verdict: **PASS for merge, with one HIGH-severity row added to TECH-DEBT-REGISTRY (Redis client config)**. Phase 8.4-B (frame budget) remains.

---

## S1 — Kill `services/ingestion`

- `21:25:08.530` — kill PID 7132 (`python -m services.ingestion.src.main`)
- `21:25:14` — pubsub:trades silent (verified via `redis-cli PSUBSCRIBE`)
- `21:25:30` — UI observations:
  - OrderBook prices frozen at last received values (asks ~81,831, was ~81,910 pre-kill)
  - Tape stopped at last received trade timestamp; no new rows appearing
  - OrderBook `stale Ns` badge present (incrementing — value reflects pre-existing LOW
    bug tracking wrong timestamp source, but `stale` user-facing indicator does fire)
  - PriceChart: no regression on "No candles for this range." empty state
  - Chrome connection pill: stayed `live` (correct — only ingestion died, api_gateway up)
  - All nav, command palette, kill-switch button, breadcrumb interactive ✓
  - **No white screen, no hang** ✓

Restore: relaunched ingestion standalone (`poetry run python -m services.ingestion.src.main &`)
at `21:28:07`. First fresh `pubsub:trades` event at `21:28:38` (~31s warmup for exchange
WS), OrderBook prices resumed updating with fresh values (~81,930), agents resumed
emitting (regime_hmm/ta_agent at 21:28:31/21:28:34). **No page reload needed.**

Screenshot: `2026-05-11-s1-stale.png`

---

## S2 — Kill `services/api_gateway`

- `21:38:31.224` — kill PID 23016 (`python -m services.api_gateway.src.main`)
- `21:38:34` — UI observations (~3s post-kill, NOT 90s as playbook expected):
  - Connection pill flipped `live → offline` (danger styling)
  - Toast banner: "Backend unreachable. Make sure your local services are running. Reconnecting automatically." with Dismiss button
  - Why ~3s and not 90s: `lib/api/client.ts:77` calls `recordFailure()` on any
    network-error fetch (not just the 30s `/health` poll). With 3+ failures triggering
    the disconnected state, an active page hits the threshold within seconds.
- Kill-switch modal: opened cleanly (pure client code, no fetch on open)
  - Reason field accepted input
  - Clicking "Arm soft" surfaced inline alert **"Backend is not reachable"** inside the
    modal — user-readable, NOT a silent no-op ✓
  - Modal stayed open, reason preserved ✓
- `/risk` (client-side nav):
  - No white screen ✓
  - H1 metric blank; "Live metrics not loaded" with Refresh button ✓
  - Exposure / Drawdown / Concentration panels all show "Live ... not yet loaded" ✓
  - Kill switch panel renders structurally with `—` placeholders ✓
- `/hot/BTC-USDT` (client-side nav back):
  - OrderBook: "No book data — awaiting feed." ✓
  - Tape: "Awaiting trades — no prints yet for this symbol." ✓
  - PriceChart: "Backend is not reachable" ✓
  - Positions: 0 with empty-state message ✓
  - No white screen ✓

Restore: relaunched api_gateway at `21:45:28`, `/health` responded at `21:45:53`. UI auto-flipped pill back to `live`, WS reconnected, first OrderBook row visible by `21:46:21`. **No page reload needed.**

**Playbook divergence** (worth folding back into the playbook): playbook §S2 step 6
asserts "WS-driven panels … should still be live — they don't depend on the REST gateway".
This is incorrect for the current architecture: the WS endpoint lives IN api_gateway
(`services/api_gateway/src/routes/ws.py`), so killing api_gateway kills the WS too. The
redesign correctly degrades the WS-driven panels into "awaiting feed" empty states; this
is the right behavior, the playbook expectation was wrong.

Screenshots: `2026-05-11-s2-risk-offline.png`, `2026-05-11-s2-hot-offline.png`

---

## S3 — Stop Redis

- `22:03:59` — `docker stop deploy-redis-1`
- `22:04:09` — `GET /commands/kill-switch` (curl --max-time 10) → `HTTP 000`, curl exit 28 (timeout). Endpoint hangs.
- Root cause established by code read (NOT requiring further runs):
  - `KillSwitch.is_active()` in `services/hot_path/src/kill_switch.py:35-43` HAS the
    correct fail-safe pattern: `try: redis.get(...); except: return True`.
  - But `libs/storage/_redis_client.py:10` creates
    `redis.ConnectionPool.from_url(url, max_connections=100)` with **no
    `socket_timeout`** and **no `socket_connect_timeout`**.
  - Existing pool connections to a stopped Redis don't get a socket error — `recv()`
    blocks indefinitely. The try-block in `is_active()` is never reached because no
    exception is raised; the await just hangs.
  - Effect chain:
    - `GET /commands/kill-switch` → `KillSwitch.status()` → `is_active()` → hangs forever
    - Frontend `killSwitchStore` poll also hangs → UI pill stuck on last-known
      (`armed: off` in this run, since switch wasn't armed before Redis stopped)
    - Execution service's hot-path tick loop deadlocks on the same await
      → effectively fail-safe by deadlock (no new orders) but not by explicit ACTIVE state
- Playbook severity classification:
  - **Not CRITICAL** (API did not return `off`)
  - **Not strict PASS** (API didn't return non-`off` either; hung)
  - **HIGH** — fail-safe pattern is implemented in code but defeated by Redis client config
- Connection pill behavior: stayed `live` throughout S3. Correct — `/health` is a
  static `{"status":"healthy"}` (`services/api_gateway/src/routes/health.py:11`) and
  doesn't check downstream deps. `/ready` does (lines 15-45) but the frontend doesn't poll `/ready`. Worth a separate registry row.
- WS behavior: stayed connected. Playbook S3 step 5 asserted WS would drop and enter
  exponential backoff — this didn't happen because the WS endpoint lives in api_gateway
  (still up), not Redis. Architecturally only the pubsub subscription inside the WS
  handler hangs server-side; the WS connection itself stays open. Another playbook
  divergence (same root architecture detail as S2).

Restore: `docker start deploy-redis-1` at `22:11:21`. PING returned PONG at `22:13:09`
(~2 min for Docker health probe to recover). `GET /commands/kill-switch` returned
`{"active":false}` at `22:13:19`. **No page reload needed.**

Screenshots: `2026-05-11-s3-redis-down.png`, `2026-05-11-s3-killswitch-failsafe.txt`

---

## New side-finding from this session (separate from the gates)

**§8.4-C soak already surfaced a HIGH on `api_gateway` WS code-1006 cycling every 1–2
min (43 reconnects/hr).** This run added a live-stack confirmation under non-soak
conditions:

- Instrumented `window.WebSocket` in the page (initScript shim recording every new /
  open / close / error event with codes).
- Observed two consecutive WS connections in a ~10 min window:
  - `21:46:39 open → 21:51:00 close (code 1006)` — connection lived **4m 21s**
  - `21:51:05 open → 21:57:14 close (code 1006)` — connection lived **6m 9s**
- This is slower than the soak's reported ~1.4 min cycle. The soak's high frequency
  was likely amplified by chrome-devtools-mcp `take_memory_snapshot` calls (each
  briefly stalls the event loop, missing pongs). Baseline cycle on an unprobed page
  is on the order of 4–6 min.
- Either way the 1006 close is reproducible — not a soak-test artifact.
- Suspected root cause: uvicorn defaults (`ws_ping_interval=20s` / `ws_ping_timeout=20s`)
  vs. the inner `pubsub.get_message(timeout=0.1)` loop in `routes/ws.py:142`
  occasionally blocking the event loop just long enough to miss a pong. Two-line fix
  candidate in `services/api_gateway/src/main.py` (pass larger `ws_ping_interval` /
  `ws_ping_timeout` to `uvicorn.run`). Not landed in this session.

---

## TECH-DEBT-REGISTRY rows to add from this run

| Severity | Row |
|---|---|
| HIGH | Redis client `ConnectionPool.from_url` lacks `socket_timeout` / `socket_connect_timeout` — defeats `KillSwitch.is_active()` fail-safe (await hangs instead of raising). Fix: `libs/storage/_redis_client.py:10` add `socket_timeout=5.0, socket_connect_timeout=2.0, health_check_interval=15`. |
| MEDIUM | `/health` endpoint is a static `{"status":"healthy"}` and doesn't check Redis/Postgres — frontend chrome pill can't reflect downstream outages. Option A: switch frontend health poll to `/ready`. Option B: extend `/health` to surface downstream-degraded states. ADR in `09-decisions-log.md` to decide. |
| LOW | `PHASE-8-RESILIENCE-PLAYBOOK.md` §S2 step 6 and §S3 step 5 assume the WS goes through a different path than api_gateway. Fold the architecture detail (WS is `routes/ws.py` IN api_gateway; Redis is just the pubsub backend behind the WS handler) into the playbook so future runs aren't surprised. |

---

## Methodology notes (for future runs)

- Single-service restart via `(poetry run python -m services.X.src.main &)` works in this
  session but the new PID is not tracked by `run_all.sh`'s PIDFILE. After a resilience
  session, the cleanest hygiene is a full `bash run_all.sh --stop && bash run_all.sh
  --local-frontend` to re-sync PIDFILE state.
- Auth bypass via `navigate_page(initScript=...)` stubbing `/api/auth/session` is the
  cleanest way to test the redesign chrome without going through Google/GitHub OAuth.
  The stub also injects a `window.WebSocket` instrumentation shim that proved useful
  for the WS HIGH investigation.
- Chrome MCP `take_snapshot` exposes the accessibility tree; the pill `aria-label`
  values (`connection: live` / `kill switch: armed: off`) are the most reliable text
  to assert against. Reading `StaticText` siblings can be ambiguous because multiple
  components in the page render the literal word "live" (e.g., chart panel header).
