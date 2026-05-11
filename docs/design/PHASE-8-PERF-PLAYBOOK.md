# Phase 8.4 — Performance Playbook for `/hot/[symbol]` (Real-Browser Session)

> Generated 2026-05-10. Closes the §8.4 gate from `11-redesign-execution-plan.md`. This playbook turns "do a perf trace" into a deterministic 60–75 minute Chrome session with hard pass/fail thresholds. Run it once the local stack is up; capture artifacts; commit only the verdict + screenshots, not the raw `.json` traces (those are too large).

---

## Pass / fail thresholds

From `11-redesign-execution-plan.md` §8.4:

| Metric | Target | How to measure |
|---|---|---|
| First Contentful Paint (FCP) on `/hot/BTC-USDT`, clean cache | **< 1500 ms** | Lighthouse (Performance) — Mobile profile, no throttling adjustment, simulated Slow 4G is the default; record the desktop number too. |
| Frame budget on `OrderBook` under live updates | **No long task > 50 ms** during a 60-second live profile | Chrome DevTools → Performance → record 60s with live ingestion publishing |
| Memory growth in 1 h of running `/hot` on live data | **< 50 MB delta in JS heap** | Memory tab → take heap snapshot at t=0 and t=60min; compare retained size |

If any threshold fails, log the failure mode in `docs/TECH-DEBT-REGISTRY.md` with severity HIGH and **do not merge** until resolved.

---

## Pre-flight (5 min)

The local stack must be healthy before the perf session. Verify in this order:

1. `.env` exists at the repo root with `PRAXIS_SECRET_KEY`, `PRAXIS_REFRESH_SECRET_KEY`, `PRAXIS_REDIS_URL` (incl. password), `PRAXIS_DATABASE_URL`, `PRAXIS_TRADING_ENABLED=true`, `PRAXIS_PAPER_TRADING_MODE=true`. See §"Local env setup" in `HANDOFF-PHASE-8-START.md` for the full template.
2. `bash run_all.sh --local-frontend` from `aion-trading-redesign/`. Wait for "All services started" banner.
3. Verify the live data pipe:
   ```bash
   docker exec deploy-redis-1 redis-cli -a changeme_redis_dev SUBSCRIBE pubsub:orderbook pubsub:trades
   ```
   You should see top-25 BTC/USDT and ETH/USDT snapshots at ~10 Hz plus trade prints. If silent, ingestion is not publishing — fix before profiling.
4. Open a **clean** Chrome window (cmd+shift+N for incognito; the perf trace is meaningless against a profile that has extensions running).
5. Navigate to `http://localhost:3001/hot/BTC-USDT`. Confirm the page renders with live orderbook, tape ticking, and the connection pill says `live` (not `stale`).

---

## A. FCP measurement (Lighthouse — 5 min)

Goal: confirm clean-cache FCP < 1500 ms on `/hot/BTC-USDT`.

1. Open DevTools (F12) → **Lighthouse** tab.
2. Categories: check only **Performance**.
3. Mode: **Navigation** (default).
4. Device: run twice — once **Desktop**, once **Mobile**. Mobile is the spec target; Desktop is for context.
5. Click **Analyze page load**.
6. Read the FCP value off the report. Screenshot the report card.

**Pass condition:** Mobile FCP < 1500 ms.
**If it fails:** capture the trace (Lighthouse export → HTML), file under `docs/design/perf-traces/2026-05-10-fcp-fail.html`, log severity HIGH in TECH-DEBT-REGISTRY. Common causes to check first: `PRAXIS_PROFILE` font loading (IBM Plex), eager-loaded `lightweight-charts` bundle, large agent feed payload at first render.

---

## B. Frame-budget profile under live load (Chrome Performance — 15 min)

Goal: confirm no long task > 50 ms while OrderBook is updating live.

1. Stay on `/hot/BTC-USDT`. The orderbook should be ticking; the tape pane should show new prints rolling in.
2. DevTools → **Performance** tab. Settings cog → CPU: **No throttling** (we want raw render perf, not simulated mid-tier device).
3. Click **Record**. Wait 60 seconds. Click **Stop**.
4. In the timeline, look at:
   - **Long tasks** (the red triangles). Click each one. Read the bottom-up call tree.
     - Pass: every long task < 50 ms.
     - Common offenders to expect and accept (not fail conditions): the initial chart bootstrap on first frame, React commit phases on store-burst updates ≤ 20 ms.
   - **Frame rate** in the FPS strip at the top. Expect ~60 fps with momentary dips when batches arrive. Pass: no sustained dip below 30 fps.
   - **`OrderBook` render flame frames** — search the bottom call tree for `BookRow` and `OrderBook`. The 7.4 fix means each frame should render only changed rows; total `BookRow` time per frame should be < 5 ms.
5. Save the trace as `docs/design/perf-traces/2026-05-10-frame-budget.json` only if it fails. Otherwise just screenshot the FPS strip and the long-task summary.

**Pass condition:** zero long tasks > 50 ms during the 60 s window AND `BookRow` render time < 5 ms/frame.
**If it fails:** log in TECH-DEBT-REGISTRY with severity HIGH; capture the JSON trace; investigate the offending callsite (likely candidates: any selector returning a non-stable identity, a missed `React.memo`, a sync subscription burst).

---

## C. Memory soak (60 min — leave it running)

Goal: confirm < 50 MB JS heap growth across 1 h of live data.

1. Stay on `/hot/BTC-USDT` with the orderbook ticking.
2. DevTools → **Memory** tab → **Heap snapshot** → click **Take snapshot**. Wait for it to finish (~5 s). Note the **Total** size at the bottom (e.g., "Heap size: 28.4 MB"). Screenshot.
3. **Set a real timer for 60 min.** Walk away — the page must keep running. Do NOT toggle DevTools panels during this window (some panels themselves leak memory in Chrome and would taint the measurement).
4. At t=60min, return. Take a second heap snapshot. Note the size. Screenshot.
5. Compute `delta = snap2 - snap1`.

**Pass condition:** `delta < 50 MB`.
**If it fails:** in the snapshot comparator, sort by **Retained Size descending**. Common leak offenders to check first:
- WebSocket message accumulation (`tapeStore` ring buffer should cap at 100 — if `bySymbol[sym].length > 100`, the cap is broken)
- `orderbookStore` retaining old snapshots (it should overwrite, not accumulate)
- `globalFeed` in `agentViewStore` (cap should hold)
- Detached DOM nodes (look for `Detached HTMLElement` rows in the comparator)

Save the larger snapshot as `docs/design/perf-traces/2026-05-10-memory-leak.heapsnapshot` if it fails.

---

## D. Light targeted micro-checks (10 min)

These are quick sanity checks that run in parallel with the soak.

1. **Network tab during live load** — confirm the WebSocket connection at `ws://localhost:8000/ws` is open and receiving frames. If you see HTTP polling fallbacks, the `lib/ws/client.ts` reconnect logic regressed.
2. **Console** — must be free of errors during the 60-s record. Warnings about `set-state-in-effect` from `OrderBook.tsx:275` are pre-existing and accepted (per `HANDOFF-PHASE-8-START.md`); anything else is a regression.
3. **React DevTools → Profiler** — record 10 s under live load. The "Ranked" view should show `BookRow` instances NOT re-rendering when only their position in the list changed but their `level` props didn't (the 7.4 memoization). If you see all 50 rows re-rendering on every store update, memoization is broken.

---

## Reporting

If everything passes:
1. Screenshot the Lighthouse FCP, the Performance long-task summary, and the two heap-snapshot totals.
2. Commit one short Markdown report at `docs/design/perf-traces/2026-05-10-results.md` listing the three numbers (FCP, max long task, heap delta) and a one-line PASS verdict.
3. Mark §8.4 as ✓ in the next handoff.

If anything fails:
1. Capture the failing trace (HTML for Lighthouse, JSON for Performance, .heapsnapshot for Memory).
2. Log a HIGH-severity row in `docs/TECH-DEBT-REGISTRY.md` with a one-line repro and the trace path.
3. Flag the failure in this session — Phase 8 is not green yet and Phase 9 cannot start.

---

## Stack hygiene reminders

- Use **incognito/clean profile** for every measurement. Extensions skew everything.
- Use **localhost over Wi-Fi** matters when measuring perceived FCP — `localhost` over loopback is what the spec assumes.
- Run **Mobile Lighthouse** with simulated Slow 4G — that's the spec's "mobile target" interpretation, not unthrottled mobile.
- Don't open additional `/hot` tabs during the soak — each tab opens its own WS and skews the multi-symbol store traffic.
