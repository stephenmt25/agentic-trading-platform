# Handoff — Phase 8 start (Phase 7 complete)

> Generated 2026-05-10 at the end of a session that landed all five Phase 7 items (kill-switch global, live orderbook + tape, order submission, perf audit, audit log) plus a smoke-test fix for the symbol-format mismatch caught when running the full stack. **Every Pending tag from the prior handoff that didn't require new schema/UX has been closed.** Read this before doing anything; it tells you where the surfaces stand, what runtime state the local stack expects, and what the Phase 8 validation gates need from you.

---

## Branch state

- Branch: `redesign/frontend-v2`
- Worktree: `C:\Users\stevo\DEV\agent_trader_1\aion-trading-redesign`
- Last commit: `2f6866c redesign(7.5): wire /settings/audit to real user-action events`
- This session's commit chain (in build order):
  - `7e2832c` (7.1 global kill-switch modal + Cmd+Shift+K)
  - `50c06d3` (7.2 live orderbook + tape via pubsub:orderbook + pubsub:trades)
  - `8f2ffcb` (7.2.1 smoke-test fixes — symbol normalization + Spot symbols)
  - `840c40c` (7.3 order submission with optimistic + rollback)
  - `7ed2819` (7.4 perf budget audit on /hot — fix re-render cascades)
  - `2f6866c` (7.5 wire /settings/audit to real user-action events)
- Tests: **65/65 vitest pass** (was 44/44 — added 21 across the session: 6 KillSwitchModal, 3 orderbookStore, 3 tapeStore, 5 ordersStore, 4 stress).
- Python: **536/536 pytest pass.**
- `tsc --noEmit`: redesign code is clean. Pre-existing legacy errors only — same files, none touched (`components/backtest/EquityCurveChart.tsx`, `components/data-display/List.tsx`, `components/decisions/`, `components/performance/`, `components/strategies/`).
- `next build`: still blocked by the legacy `EquityCurveChart.tsx` recharts formatter. `next dev` works fine. Tracked LOW in `docs/TECH-DEBT-REGISTRY.md`; Phase 9 deletes legacy.
- `eslint`: clean across all redesign files. One pre-existing warning in `OrderBook.tsx:275` (`set-state-in-effect` on the flash-decay block) — predates 7.4 and was not touched.

---

## Local env setup (read this first)

The stack now requires a local `.env` at the repo root (gitignored). This was discovered during the 7.2 smoke test — `api_gateway` refuses to start with the insecure default `SECRET_KEY`, and the docker-compose Redis container ships with `requirepass`. Minimum contents:

```
PRAXIS_SECRET_KEY=<32-byte hex>
PRAXIS_REFRESH_SECRET_KEY=<32-byte hex, different from above>
PRAXIS_REDIS_URL=redis://:changeme_redis_dev@localhost:6379/0
REDIS_PASSWORD=changeme_redis_dev
PRAXIS_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/praxis_trading
PRAXIS_TRADING_ENABLED=true
PRAXIS_PAPER_TRADING_MODE=true
PRAXIS_LOG_LEVEL=INFO
PRAXIS_BINANCE_TESTNET=false
```

Generate secrets with `python -c "import secrets; print(secrets.token_hex(32))"`. `TRADING_ENABLED=true` with `PAPER_TRADING_MODE=true` is the only combination that lets order submission complete; with `TRADING_ENABLED=false` the executor consumes events but immediately rejects them.

**Boot:** `bash run_all.sh --local-frontend` from `aion-trading-redesign/`. Frontend lands on **:3001** (the banner says :3000 — that's stale; the actual config is :3001). **Stop:** `bash run_all.sh --stop`.

To verify the live data pipe:
```
docker exec deploy-redis-1 redis-cli -a changeme_redis_dev SUBSCRIBE pubsub:orderbook pubsub:trades
```
You should see top-25 BTC/USDT and ETH/USDT snapshots at ~10Hz plus trade prints with real `trade_id`s.

---

## What shipped this session

Six commits in build order.

**7.1 — Global kill-switch modal + hotkey** (commit `7e2832c`)
- `components/shell/KillSwitchModal.tsx` (new, ~190 LOC) — single global modal mounted in `RedesignShell`. Reads armed state from `killSwitchStore`, refreshes on open in case the store is stale.
- `components/shell/RedesignShell.tsx` — registers `Cmd/Ctrl+Shift+K` and mounts `<KillSwitchModal />` once.
- `lib/stores/killSwitchStore.ts` — `modalOpen`, `setModalOpen`, `toggleModal`.
- `app/risk/page.tsx`, `app/hot/[symbol]/page.tsx` — dropped per-surface modal duplicates and the local key handler. Closes Pending on both surfaces. Unblocks Phase 8 §8.5 ("kill switch ≤2 keystrokes from any surface").

**7.2 — Live orderbook + tape** (commit `50c06d3`)
- Backend: new `EventType.ORDERBOOK_SNAPSHOT` + `TRADE_TICK`; `OrderBookSnapshotEvent` + `TradeTickEvent` schemas (Decimal-typed); `PUBSUB_ORDERBOOK` + `PUBSUB_TRADES` channels; `BinanceAdapter.stream_orderbook` (CCXT `watch_order_book` top-25) + `stream_trades` (`watch_trades` with taker side → bid/ask); `WebSocketManager._run_orderbook` + `_run_trades` tasks with `NotImplementedError` catch so non-Binance adapters skip silently; `services/ingestion/src/main.py` `handle_orderbook` + `handle_trade` callbacks; `services/api_gateway/src/routes/ws.py` subscribes to the new channels.
- Frontend: `lib/stores/orderbookStore.ts` (per-symbol top-N snapshot) + `lib/stores/tapeStore.ts` (per-symbol ring buffer cap 100); `lib/ws/client.ts` routes the new channels; `app/hot/[symbol]/page.tsx` `OrderBookPanel` reads snapshot with 5s staleness indicator; `TapePanel` renders top 50 prints live.

**7.2.1 — Smoke-test fixes** (commit `8f2ffcb`)
- Caught running the full stack: CCXT publishes `"BTC/USDT"` while the frontend keys stores by URL-safe `"BTC-USDT"`. `lib/ws/client.ts` now normalizes (`/` → `-`, uppercase) at the ingest boundary.
- `/hot` redirect: `BTC-PERP` → `BTC-USDT`. Ingestion publishes Spot pairs (`services/ingestion/src/main.py:47`); the surface spec wanted PERP but the data path is Spot. Symbol switcher mirrors the ingestion list.

**7.3 — Order submission with optimistic + rollback** (commit `840c40c`)
- Backend: `OrderApprovedEvent` gains optional `order_id` so the api_gateway can pre-allocate; executor honors `ev.order_id` if present. New `POST /orders/` enforces auth, profile ownership (`ProfileRepository.get_profile_for_user`), kill switch (defense in depth at the api_gateway layer), positive Decimal quantity + price. Publishes `OrderApprovedEvent` to `stream:orders`. Returns 202 with the pre-allocated `order_id` so the HTTP response and the persisted Order row match.
- Frontend: `api.orders.submit / .list / .cancel`; `lib/stores/ordersStore.ts` with `beginSubmit → confirmSubmit | rejectSubmit + reconcile()`; `app/hot/[symbol]/page.tsx` `handleSubmit` is now a real submit; Open Orders tab polls `api.orders.list` every 5s, merges optimistic shadows, drops them once the server surfaces the same `order_id`. Rejected entries get a dismiss button.

**7.4 — Perf budget audit on /hot** (commit `7ed2819`)
- Static review of the OrderBook + Tape render path under live load surfaced three re-render cascade issues:
  1. `TapePanel` selector returned a fresh `[]` literal when the symbol had no data → re-rendered on every store update of any symbol. Fixed with stable `EMPTY_TRADES` const.
  2. `OrderBook` did `allLevelsForKeyboard.findIndex` per visible row per render (50 × 50 = 2500 comparisons). Fixed with a precomputed `keyboardIndex: Map<string, number>` (O(1) lookup).
  3. `BookRow` wasn't memoized — every parent re-render re-ran all 50 rows. Wrapped in `React.memo`.
- New `lib/stores/stress.test.ts` asserts ingest is well under one frame each and selector identity is stable across unrelated-symbol updates — regressions surface immediately.

**7.5 — Audit log surface** (commit `2f6866c`)
- Backend: `GET /audit/user-events` aggregates user-action events from sources that emit today (kill switch via `praxis:kill_switch:log`). Filterable by `event_type` and ms-epoch `from`/`to`. Returns `{ events, available_types, pending_types, fetched_at }`. The shape is stable so each future emitter (profile / api_key / override / auth_fail) flips its tag without a UI change.
- Frontend: `app/settings/audit/page.tsx` polls every 30s; renders events newest first; CSV export builds from the in-memory filter set; "What gets recorded" rows now show **Recorded vs Pending** per source driven by the response.

---

## Phase 7 outcome (the scoreboard)

```
[x] 7.1   Global kill-switch modal + Cmd+Shift+K       components/shell/KillSwitchModal.tsx
[x] 7.2   Live orderbook + tape via pubsub             services/ingestion + libs/exchange/_binance.py + frontend stores
[x] 7.2.1 Smoke-test fixes (symbol normalization)      lib/ws/client.ts + /hot redirect
[x] 7.3   Order submission optimistic + rollback       services/api_gateway + frontend ordersStore
[x] 7.4   Perf budget audit on /hot                    OrderBook + TapePanel + stress test
[x] 7.5   Audit log surface wired                      services/api_gateway/audit + /settings/audit
```

**Every Pending tag from `HANDOFF-PHASE-7-START.md` that didn't require a new event source emission has been closed.** The remaining Pending tags on `/risk` (portfolio VaR, violation log, soft/hard arm), `/hot` (Fills tab, regime/latency/agent-count chrome pills), `/agents/observatory` (debate event type, override / silence / replay), and `/settings/audit` (profile / api_key / override / auth_fail rows) are all gated on backend producers that don't exist yet — none of them are blocked on frontend work.

---

## What's next: Phase 8 — Validation gates

Per `11-redesign-execution-plan.md` §8.1–8.5. Each gate is a checklist; the merge to main waits on all five.

| Gate | Status entering Phase 8 |
|---|---|
| **8.1 Functional parity with main** | Mostly closed by 7.x. Order submit + kill-switch + live data + audit log are wired. Remaining: walk every legacy endpoint and confirm the redesign branch either covers it or has a tracked deferral (e.g. fills WS, debate event type, profile-edit diff log). |
| **8.2 Design fidelity** (no hex literals, mode-correct, tabular, every component used) | Likely green. Spot-check: `grep -r "#[0-9a-fA-F]\{6\}" frontend/components/` should return only legacy paths (`backtest/`, `decisions/`, `performance/`, `strategies/`). Every component in `04-component-specs/` has at least one consumer. |
| **8.3 Critical-path resilience** (Risk Control works when other services are down, kill switch works when api_gateway is degraded, Hot Trading degrades gracefully) | Untested — needs a failure-injection session. Suggested: kill ingestion, watch `/hot` show stale-data tags + empty book; kill api_gateway, watch `/risk` go to backend-offline banner; kill Redis, watch the kill switch refuse to flip (current behavior: `KillSwitch.is_active` fails-safe to ACTIVE). |
| **8.4 Performance budget** (FCP <1.5s on Hot Trading, no frame drop on `OrderBook` at 100 updates/s, no >50MB memory growth in 1h) | Partial. Static review + stress test done at 7.4. Real Chrome profiler trace under live 100Hz updates and 1h memory soak still pending — needs a browser session. Lighthouse run on `/hot/BTC-USDT` for FCP. |
| **8.5 Accessibility minimum** (Hot Trading keyboard-only, kill switch ≤2 keystrokes from any surface, focus rings, accessible names) | Largely green after 7.1. Remaining: full keyboard-only audit of `/hot` (cycle every interactive without a mouse, verify tab order matches visual order), focus rings present on every interactive (most primitives ship with them via the component lib), and accessible names on the OrderBook canvas (currently `aria-hidden` because `lightweight-charts` doesn't expose a meaningful tree). |

**Recommended Phase 8 order:**

1. **8.2 design fidelity spot-check** (5 min) — grep + visual diff of design tokens.
2. **8.5 keyboard audit on /hot** (30 min) — cycle every interactive, fix gaps.
3. **8.4 real-browser perf trace** (1 session) — Lighthouse on `/hot/BTC-USDT`, 5-min profile under live load (we publish at ~10Hz today, not 100Hz; the 100-update/s budget is for a worst-case future), 1h leave-running for memory.
4. **8.3 resilience tests** (1 session) — most expensive; run last because failures here may surface real bugs that need fixes before merge.
5. **8.1 gap audit** (last) — sweep over legacy main and confirm coverage; defer non-blockers to `TECH-DEBT-REGISTRY.md`.

Items 1–2 are quick. Item 3 is the highest-stakes ahead of merge. Items 4–5 are the most expensive but also the most likely to find real issues.

---

## Phase 9 — Cutover

Per `11-redesign-execution-plan.md` §9. Don't start until Phase 8 is fully green. The branch carries 30+ commits at this point; the merge will be substantial. Tag `pre-redesign-cutover` before merging. Document a rollback. Remove the worktree after.

---

## Things to be aware of

- **Local `.env` is not portable.** Anyone cloning fresh has to generate their own `PRAXIS_SECRET_KEY` and `PRAXIS_REFRESH_SECRET_KEY` — see "Local env setup" above. The `.env.example` at `config/.env.example` doesn't include either of those today; consider updating it before Phase 9.
- **Frontend port is :3001, not :3000.** The `run_all.sh` banner says 3000; the actual config is in `frontend/package.json` / `frontend/.env.local` (or wherever) and serves on 3001. Don't fix this yet — it's load-bearing for active local sessions.
- **Symbol format**: backend (CCXT) publishes `BTC/USDT`; frontend uses URL-safe `BTC-USDT`. Normalization happens in `lib/ws/client.ts` at the ingest boundary. Every store is keyed by the URL-safe form. **Don't add a new symbol without first adding it to `services/ingestion/src/main.py:47`** — the `/hot` symbol switcher mirrors that list.
- **`/hot` defaults to BTC-USDT**, not BTC-PERP as the surface spec said. Spot is what we ingest today; revisit the redirect when futures land.
- **Order submission is real.** `OrderEntryPanel.onSubmit` now hits `POST /orders/` which publishes to `stream:orders` and the executor places. In `PRAXIS_PAPER_TRADING_MODE=true` it's safe (PAPER adapter, fictional fills). In LIVE mode this would place real orders. Default is paper; the stack-level safety comes from `PRAXIS_TRADING_ENABLED` (executor refuses if false) + the kill switch (api_gateway refuses if armed).
- **Pre-allocated `order_id` flows api_gateway → event → executor → DB.** The HTTP 202 response and the eventual DB row use the same UUID. Smoke-verified at 7.3.
- **Test profile in DB** for manual smoke testing: `9c94da6c-8d20-42f3-b086-9170e3ba8f2c` (Mean Reversion (RSI + Z-Score)) owned by user `6322b6fa-d425-51d7-a818-088c19275228`. Forge a JWT with `python -c "import jwt, datetime; print(jwt.encode({'sub': '6322b6fa-d425-51d7-a818-088c19275228', 'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)}, '<your PRAXIS_SECRET_KEY>', algorithm='HS256'))"`.
- **Audit endpoint surfaces only `kill_switch` events today.** `profile`, `api_key`, `override`, `auth_fail` are tagged Pending in the response and the UI surfaces that distinction. To wire any of them, emit at the source (e.g. `audit_log` row with the event type, or a new Redis log) and add a branch in `services/api_gateway/src/routes/audit.py:list_user_audit_events`.
- **The OrderBook stress test caps at jsdom-time, not real browser time.** jsdom render is faster than Chrome for trivial DOM but slower for complex layout. Use the test as a regression guard, not a real perf budget assertion — the real budget needs Chrome DevTools.
- **CCXT `watch_order_book` and `watch_trades` are public on Binance Spot mainnet.** No API keys needed. The earlier "Authentication required" errors during the smoke test were Redis NOAUTH bubbling through CCXT's exception handler — not a Binance issue.
- **The `react-hooks/set-state-in-effect` lint rule is strict.** Don't pass a `useCallback` containing setState as the only dependency of a `useEffect`; inline the polling logic instead. Pattern is in `app/hot/[symbol]/page.tsx:useOpenOrdersForSymbol`.

---

## Suggested next-session prompt

> Continue the Praxis frontend redesign on `redesign/frontend-v2`. Phase 7 is complete (5 ranked items + a smoke-test fix all shipped); commit `2f6866c` is the head. Read `docs/design/HANDOFF-PHASE-8-START.md` before anything else.
>
> Today's task: Phase 8 — validation gates. Pick one of the five gates per the recommended order in §"Recommended Phase 8 order" — recommend starting with **8.2 design fidelity spot-check + 8.5 keyboard audit on /hot** since they're quick and unblock the rest. After landing, commit + push as `redesign(8.x): <what you did>`.
>
> If you're starting fresh: the local stack needs a `.env` — see §"Local env setup" in the handoff. Run `bash run_all.sh --local-frontend` from the redesign root; frontend serves on :3001.

---

## Other artifacts to know about

- **`HANDOFF-PHASE-7-START.md`** is now superseded by this file. Leave in place as audit trail.
- **`REPLICATION-PLAYBOOK.md`** (`docs/design/`) — stable through this session.
- **`TECH-DEBT-REGISTRY.md`** (`docs/`) — append-only. The legacy `EquityCurveChart` row stays OPEN until Phase 9. The Settings backend gaps row from 6.1 is partially closed (audit done; profile/api-key emitters remain).
- **`11-redesign-execution-plan.md`** is the authoritative phase plan. Phase 8 §8.1–8.5 and Phase 9 are described there in the same level of detail as 4–7.
- **Phase 7 commit count**: 6 commits (`7e2832c` through `2f6866c`), spanning 2026-05-09 through 2026-05-10. No rebases, no force-pushes.
