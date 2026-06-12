# Phase 8.3 — Critical-Path Resilience Playbook for `/hot/[symbol]` (Real-Browser Session)

> Generated 2026-05-11. Closes the §8.3 gate from `11-redesign-execution-plan.md`. This playbook injects three failures into the live local stack and verifies that the redesign degrades gracefully — no white screens, no hangs, no silent data corruption. Run it after §8.4 in the same Chrome session. Capture one screenshot per scenario plus a one-line PASS/FAIL; commit only the verdict, not service logs.
>
> **S2/S3 corrected 2026-06-13** (registry row 35) against the 2026-05-11 run results
> (`perf-traces/2026-05-11-resilience-results.md`). Two architectural facts the original
> playbook got wrong:
>
> 1. **The WebSocket endpoint IS the api_gateway.** `/ws` is served by
>    `services/api_gateway/src/routes/ws.py` on :8000 — there is no separate WS path.
>    Killing api_gateway therefore kills the WS too, and the correct S2 expectation is
>    that WS-driven panels degrade to "awaiting feed" empty states (which they do).
> 2. **Redis is the pubsub backend *behind* the WS handler, not the WS transport.**
>    Stopping Redis does NOT drop the browser's WS connection — the socket to the gateway
>    stays open; only the server-side `pubsub.get_message()` subscription inside
>    `listen_to_redis` stops yielding (and now reconnects with backoff per the handler's
>    retry loop). The correct S3 expectation is a silent feed (open-but-idle WS), not
>    client reconnect churn.

---

## Pass / fail thresholds

From `11-redesign-execution-plan.md` §8.3, paraphrased into testable conditions:

| Scenario | Pass condition | Fail condition |
|---|---|---|
| **S1** Kill `services/ingestion` | OrderBook + Tape show `stale Ns` warn tag within 5–10 s. PriceChart shows the "No candles" empty state if no cached candles, or freezes at the last bar (acceptable). `/hot` route stays interactive (kill switch button, settings menu, chrome nav all clickable). | Any panel white-screens, the page hangs, or a panel renders stale data with no staleness indicator. |
| **S2** Kill `services/api_gateway` | Connection pill (`StatusPills`) flips from `live` to `offline` within 90 s (3 × 30-s `/health` poll). `/risk` shows a clear backend-offline state — either empty + error tag, or a banner, but not a crashed render. KillSwitchModal still opens; attempting the toggle surfaces a user-readable error (does not silently fail). | Connection pill stays green > 120 s. `/risk` white-screens. KillSwitchModal silently fails or throws an unhandled rejection. |
| **S3** Kill Redis (`deploy-redis-1`) | The `KillSwitch.is_active` server-side check fail-safes to ACTIVE — verify via `GET /commands/kill-switch` returning a non-`off` state OR the chrome kill-switch pill showing `armed: hard`/`armed: soft`. The browser WS connection **stays open** (the WS terminates at api_gateway, which is still up); the feed simply goes silent while the server-side pubsub subscription reconnects with backoff. The chrome should surface degradation via the `/ready`-driven `degraded` pill (ADR-017), not via WS drop. | Kill switch returns `off` after Redis loss (this is a real-money risk and a P0 finding). The frontend crashes. |
| **S4** Restore each service in turn | After each restore: the affected surface reconnects without a page reload. WebSocket resumes inside one reconnect-backoff window; HTTP-poll-based stores (connection pill, kill-switch state) recover at the next poll interval (≤ 30 s). | Any surface requires F5 to recover. |

If any threshold fails, capture the screenshot, log a HIGH-severity row in `docs/TECH-DEBT-REGISTRY.md`, and **do not merge** until resolved. Resilience failures are by definition real-money-risk regressions.

---

## Pre-flight (5 min — assume you just finished §8.4)

The stack should already be up from §8.4. Verify:

1. `bash run_all.sh --local-frontend` shows "All services started" and no service is in restart-loop. Quick check:
   ```bash
   docker ps --format "table {{.Names}}\t{{.Status}}"
   ```
   Every container should be `Up N minutes (healthy)` or just `Up`. Anything in `Restarting` or `unhealthy` — stop and fix before injecting failures.
2. `http://localhost:3001/hot/BTC-USDT` rendering live data, connection pill = `live`, kill switch pill = `armed: off`.
3. Keep DevTools open on the **Network** tab (filter: `WS`) — you'll watch WebSocket reconnect behavior here.
4. Open a second terminal window for the failure-injection commands. Keep it visible alongside the browser so you can timestamp the failure against what the UI shows.
5. **Do not** use incognito for this session — you want to keep the same browser state across scenarios. (Perf measurement needed incognito; resilience does not.)

---

## S1. Kill `services/ingestion` (10 min)

**What this simulates:** market-data pipe failure. The most common production incident — exchange WS times out, CCXT loops, or the ingestion service OOMs.

1. In the second terminal:
   ```bash
   bash run_all.sh --stop-service ingestion
   ```
   If that flag isn't supported, fall back to:
   ```bash
   pkill -f "services/ingestion"
   ```
   Note the wall-clock time the moment the kill lands. Tape pane should stop appending new prints within 1–2 s.
2. **Watch the UI for 30 s.** Expected observations, in order:
   - t+1–2 s: Tape stops scrolling. OrderBook stops flickering.
   - t+5–10 s: OrderBook header shows a `stale Ns` warn tag (the threshold is `STALE_AFTER_MS` in `frontend/app/hot/[symbol]/page.tsx:524`). Tape header should show the same.
   - t+10+ s: PriceChart either freezes at the last received bar (acceptable) or shows the "No candles" empty state if backed by REST (less common on a long-running tab).
   - At all times: chrome nav clickable, kill-switch button responds, command palette opens via Cmd+K. **No white screen.**
3. Screenshot the `/hot` page once `stale Ns` has appeared on both panels. Save as `docs/design/perf-traces/2026-05-11-s1-stale.png` (this directory is created in §8.4; reuse it).

**Pass:** all four expected observations above. **Fail:** anything missing, especially the absence of a staleness tag — that means a user could be looking at frozen data that they believe is live.

**Restore:** `bash run_all.sh` (no `--stop`) will not restart a single service. Easiest restore: `bash run_all.sh --stop` then `bash run_all.sh --local-frontend`. **Recovery observation:** within one debounce window of ingestion republishing to `pubsub:orderbook` / `pubsub:trades`, the staleness tags should disappear and panels resume. No page reload required.

---

## S2. Kill `services/api_gateway` (15 min)

**What this simulates:** full gateway outage — REST **and** WebSocket. The WS endpoint lives in api_gateway (`services/api_gateway/src/routes/ws.py`), so killing the gateway severs both: every HTTP request (profile load, order submission, kill switch toggle, health poll) fails AND the live feed (OrderBook, Tape, pnl pushes) stops.

1. With ingestion restored from S1, confirm the page is back to `live` and ticking.
2. Kill the API gateway:
   ```bash
   pkill -f "services/api_gateway"
   ```
3. **Trigger an API request immediately** to test the surface-level error path: click the kill-switch button in the chrome (top right). Expected:
   - Modal opens normally (modal shell is pure client code, doesn't fetch on open).
   - Attempting to toggle the switch produces a user-readable error — toast, inline message, or modal-level banner. Should **not** silently no-op.
4. **Wait up to 90 s** for the connection pill to flip. The poller in `lib/stores/connectionStore.ts:80-84` runs every 30 s and requires 3 consecutive failures, so worst case is 90 s + jitter. The pill should flip `live → offline` (color tone goes from `ok` to `danger` per `components/shell/StatusPills.tsx:47-56`).
5. Navigate to `/risk` (via chrome nav). Expected:
   - Backend-offline state of some kind — banner, empty table with a clear error tag, or skeleton-with-error. NOT a white screen, NOT a partial render with stale numbers presented as fresh.
6. Navigate back to `/hot/BTC-USDT`. WebSocket-driven panels (OrderBook, Tape, PriceChart) are **also down** — the WS is served by the same api_gateway process, so the client enters reconnect backoff (visible in DevTools Network as repeated failed WS handshakes). The pass condition is graceful degradation: each panel shows its "awaiting feed" / "no data" empty state (verified in the 2026-05-11 run: "No book data — awaiting feed.", "Awaiting trades…", "Backend is not reachable"), with no white screen and no stale data presented as live.
7. Screenshot: `/hot` showing offline pill + the WS-driven panels in their awaiting-feed empty states. Save as `docs/design/perf-traces/2026-05-11-s2-offline.png`.

**Pass:** all observations above, no white screen, KillSwitchModal surfaces a real error.
**Fail:** pill stays green > 120 s after kill (health poll regression), `/risk` crashes, or KillSwitchModal silently fails the toggle.

**Restore:** `bash run_all.sh --stop` then `bash run_all.sh --local-frontend`. **Recovery observation:** connection pill should flip back to `live` within 30 s of `/health` returning 200 again.

---

## S3. Kill Redis (10 min — the riskiest scenario)

**What this simulates:** total messaging-layer loss. This is the kill switch's stress test — Redis stores the kill-switch state, so the safety guarantee is "if Redis is unreachable, fail-safe to ACTIVE."

> **Why this matters:** `KillSwitch.is_active()` checking Redis is the last safety gate between the execution service and the exchange. If a Redis outage caused that check to return `false` (= switch is off = trading allowed), an outage would silently re-enable trading. The fail-safe must be ACTIVE.

1. Restore the stack (api_gateway and ingestion both running). Confirm `/hot` is `live`.
2. Stop Redis:
   ```bash
   docker stop deploy-redis-1
   ```
3. **Probe the server-side fail-safe directly** — don't rely on the UI to tell you the truth here:
   ```bash
   curl -s http://localhost:8000/v1/kill-switch/status | jq
   ```
   The response should indicate the switch is `active` / `hard` / `soft` — anything other than `off`. If the API returns `off` (or 500s without a fail-safe interpretation), that is a **P0 finding** — log it as CRITICAL severity, not HIGH.
4. **Then check the UI:** the chrome kill-switch pill in `StatusPills` should show `armed: soft` or `armed: hard` (per `components/shell/StatusPills.tsx:58-60`). If it still shows `armed: off`, the frontend hasn't picked up the fail-safe — check the polling cadence in `killSwitchStore`.
5. **Observe WebSocket behavior:** in DevTools Network (filter `WS`), the connection **stays open** — the WS terminates at api_gateway (still running); Redis is only the pubsub backend behind the WS handler (`routes/ws.py` `listen_to_redis`). What actually happens: the server-side pubsub subscription errors/goes silent and the handler retries it with exponential backoff (1 s → 30 s, server-side), so the client sees an open-but-idle socket and the feed simply stops. Confirmed in the 2026-05-11 run: no WS drop, no client reconnect churn. Panels should go stale/empty honestly; **no frontend crash.** (The client backoff at `lib/ws/client.ts` only engages in S2, when the gateway itself dies.)
6. Screenshot:
   - The `curl` output showing fail-safe ACTIVE state. Save as `docs/design/perf-traces/2026-05-11-s3-killswitch-failsafe.txt`.
   - The `/hot` page with the kill-switch pill armed + WS reconnect attempts visible in Network. Save as `docs/design/perf-traces/2026-05-11-s3-redis-down.png`.

**Pass:** API fail-safes to non-`off`, UI pill reflects it, WS reconnects without crashing the page.
**Fail (HIGH):** UI pill stays `off` while server says active.
**Fail (CRITICAL):** API returns `off` after Redis loss — real-money risk.

**Restore:**
```bash
docker start deploy-redis-1
```
Then wait ~10 s (Docker's health probe can take longer — the 2026-05-11 run saw ~2 min to PONG). **Recovery observation:** the browser WS never dropped, so there is no client reconnect to wait for — the server-side pubsub subscription re-establishes on its next backoff attempt (1–30 s) and the feed resumes on the same socket. Do not F5. Once flowing, OrderBook / Tape resume. Kill-switch pill returns to `armed: off` only after the operator explicitly resets the switch via `POST /v1/kill-switch/off` — Redis restoration alone is NOT supposed to clear the safety state, since the operator hasn't acknowledged the incident. Confirm this behavior; if the switch auto-clears, log as HIGH severity.

---

## Reporting

If everything passes:
1. Three screenshots (S1, S2, S3 — the last is two artifacts) committed under `docs/design/perf-traces/`.
2. One short Markdown report at `docs/design/perf-traces/2026-05-11-resilience-results.md` listing the four scenarios, the actual wall-clock observations (e.g., "S2 pill flipped at 67 s"), and a one-line PASS verdict per scenario.
3. Mark §8.3 as ✓ in the next handoff. Combined with §8.4 green, Phase 8 closes (except the four parity gaps in `PHASE-8-PARITY-AUDIT.md`).

If anything fails:
1. Capture the screenshot and any relevant logs (`docker logs deploy-redis-1`, or service stderr from `run_all.sh`).
2. Log a HIGH-severity (or CRITICAL for S3 fail-safe failures) row in `docs/TECH-DEBT-REGISTRY.md` with one-line repro + screenshot path.
3. Flag the failure — Phase 8 is not green and Phase 9 cannot start.

---

## Stack hygiene reminders

- **Do these scenarios in order**, restoring fully between each. Overlapping failures will produce ambiguous results — if Redis is already down, killing api_gateway tells you nothing new.
- **Do not F5 to "fix" a panel** mid-scenario. The point of the test is whether the surface recovers on its own. A reload masks the regression you are trying to find.
- **The 90-s ceiling on the connection pill flip is by design** — three failures × 30 s poll. Don't shorten this for the test; it's the production behavior.
- **`run_all.sh --stop` is the cleanest restart path.** Individual `pkill` works for one-service kills but the restore is messier; `--stop` then `--local-frontend` is reliable.
- **`pubsub:orderbook` and `pubsub:trades` carry both BTC and ETH globally** (per `libs/messaging/channels.py:21-27`). Killing ingestion stops both symbols at once; you'll see staleness on whatever symbol you're viewing.
- **Watch DevTools Console during all three scenarios.** Pre-existing warnings (`set-state-in-effect` from `OrderBook.tsx:275`) are accepted. Any *new* errors during a failure scenario — especially uncaught promise rejections — are findings worth logging even if the UI looks OK.
