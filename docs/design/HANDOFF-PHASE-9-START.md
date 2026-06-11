# Handoff — Phase 9 cutover (post Phase 8 close)

> Generated 2026-05-12. **Phase 8 is fully closed end-to-end.** All five gates green, all four GAPs resolved, two HIGH findings deferred to this phase. This handoff supersedes `HANDOFF-PHASE-8-FINAL.md` (leave that file in place as the audit trail). Read this end-to-end before booting the stack. Estimate: **1 pre-flight session + 1 cutover-day session** to merge, with a 24-h monitoring tail.

---

## Branch state

- Branch: `redesign/frontend-v2`
- Worktree: `C:\Users\stevo\DEV\agent_trader_1\aion-trading-redesign`
- Last commit (head): `0386a72 redesign(8.4-B + 8.1 GAPs): frame budget green + all 4 GAPs closed`
- Working tree at handoff time:
  - `M  .claude/settings.local.json` — **do not commit** (local harness permissions)
  - `?? frontend/.perf-traces-tmp/` — gitignored local soak artifacts; delete or keep as reference
- Tests: vitest 65/65 still green. `tsc --noEmit` clean on redesign code. `next build` produces a clean prod bundle (proved during 8.4-A/B).
- Backend tests: `bash run_all.sh --stop` exits cleanly (verified end of last session).

---

## Phase 8 scoreboard — final

```
[x] 8.1 Functional parity with main          — GAP-1/2/3/4 all RESOLVED (see registry)
[x] 8.2 Design fidelity                       — green; legacy hex exceptions documented
[x] 8.3 Critical-path resilience              — S1/S2/S3 all PASS (one HIGH spawned, deferred)
[x] 8.4 Performance budget                    — 8.4-A ✅ FCP 892 ms · 8.4-B ✅ 0 long tasks · 8.4-C ✅ −9 MB / 50 MB gate
[x] 8.5 Accessibility minimum                 — green
```

**Phase 8 closes here.** Phase 9 is the cutover phase. Two HIGH-severity findings spawned during Phase 8 are deferred to Phase 9 pre-flight — see below.

---

## Local env setup (unchanged)

For cutover work the live stack is only needed for the pre-flight session (8.3 follow-ups). For the cutover commits themselves you don't need the stack running.

- Live stack (pre-flight): `bash run_all.sh --local-frontend`
- Stack stop: `bash run_all.sh --stop` (reliable; verify `.praxis_pids` is gone afterwards)
- Test profile: `9c94da6c-8d20-42f3-b086-9170e3ba8f2c` (Mean Reversion — RSI + Z-Score), owner `6322b6fa-d425-51d7-a818-088c19275228`

`bash run_all.sh --stop` followed by `Get-Process node | Stop-Process` is a safe full-cleanup pattern if a previous session crashed and left frontend processes behind.

---

## What shipped between Phase 8 close and now

Eight commits in build order (single working day, 2026-05-11 → 2026-05-12):

1. `ab6b304` — Phase 8 parity audit + perf/resilience playbooks + GAP registry
2. `e5c160b` — CORS fix for prod-frontend port 3001
3. `7aa9aae` — 8.4-A first (incorrect) FCP measurement on `next dev` — 2,204 ms FAIL
4. `0a08f2d` — 8.4-A real measurement on prod build — **FCP 892 ms** PASS (cleared 5 TS errors to make `next build` succeed)
5. `7a63ea5` — playbook update: require prod build for §8.4 measurements
6. `b8f8d5c` — 8.4-C memory soak — **−9 MB / 50 MB gate** PASS (321K WS frames over 60 min)
7. `7194132` — 8.3 resilience — S1/S2/S3 all PASS; 3 new registry rows
8. `0386a72` — 8.4-B frame budget green (0 long tasks > 50 ms) + all 4 GAPs closed (mode pill, HITL on /agents/observatory, root redirect, ADR-015 for daily-report)

ADRs added:
- **ADR-015** — Manual daily-report button removed (daemon handles it; backfill is an API call)
- **ADR-016** — HITL approval queue lives on `/agents/observatory`, not a dedicated `/approvals` surface

---

## Deferred Phase 8 findings → Phase 9 pre-flight blockers

Two HIGH-severity findings from Phase 8.3 / 8.4-C did not land in Phase 8. Both are backend-only and recommended to close **before** the cutover commit so we don't merge a known-broken safety invariant.

### HIGH-1 · `libs/storage/_redis_client.py` missing socket timeouts (defeats KillSwitch fail-safe)

- **File**: `libs/storage/_redis_client.py:10`
- **Symptom**: Phase 8.3 S3 confirmed — when Redis dies, existing pool connections block on `recv()` forever instead of raising. The `try/except → return True` fail-safe in `services/hot_path/src/kill_switch.py:35-43` never fires because no exception is ever raised. Trading is effectively halted (by deadlock) but operators can't see "ACTIVE" because every observability path also hangs.
- **Fix shape**: add `socket_timeout=5.0, socket_connect_timeout=2.0, health_check_interval=15` to the `from_url(...)` call. ~3 lines.
- **Why it's not a one-line drop-in**: `socket_timeout` affects long-blocking callers too — `BLPOP`, `XREAD blocking`, pubsub `get_message(timeout=...)`. Audit before changing:
  - `grep -rn "blpop\|xread\|pubsub.*get_message" services/ libs/`
  - For any caller that legitimately blocks > 5 s, switch it to the explicit-timeout variant or use a separate client with no socket_timeout.
- **Validation**: re-run Phase 8.3 S3 after the fix. Expected: `GET /commands/kill-switch` returns `{active: true}` within ~5 s of `docker stop deploy-redis-1`, not hangs.

### HIGH-2 · `services/api_gateway/src/routes/ws.py` WS connection cycling (code 1006 every 1–2 min)

- **File**: `services/api_gateway/src/routes/ws.py`
- **Symptom**: 43 reconnects in 60 min on a healthy stack. Frontend masks the user-facing impact perfectly, but every reconnect re-auths, re-subscribes, and rebuilds server-side state — wasteful and can mask intermittent data gaps.
- **Suspects** (in priority order):
  1. `pubsub.get_message(timeout=0.1)` polling loop interaction with `await websocket.receive_text()` — one path may be raising and the outer handler closing the socket
  2. uvicorn defaults: `ws_ping_interval=20`, `ws_ping_timeout=20` — combined with the polling cadence above, a single missed pong window could be triggering close. But code 1006 (not 1011) argues against this being the primary cause.
  3. Backend never explicitly sends `WebSocket.close()` — 1006 means client sees TCP RST or read-error, so suspect a Python exception escaping the handler that uvicorn translates to an abrupt close.
- **Fix shape**: unknown until investigation. Could be ≤10 lines (wrap the inner loop with a broader except + clean close) or could require restructuring the pubsub+receive loop.
- **Validation**: re-run a 15-min soak on `/hot/BTC-USDT` with the WS instrumented (same `initScript` shim used in 8.4-C). Expected: 0 reconnects during the window.

### Optional design call · `/health` vs `/ready` for chrome connection pill

- Registry row dated 2026-05-11 (MEDIUM, OPEN): the frontend's `useConnectionStore` polls `/health` which is static; downstream degraded states (Redis dead, Postgres dead) are invisible to the chrome pill until users hit a hanging endpoint.
- Two reasonable resolutions, needs ADR before cutover:
  - **(A)** switch the poll target to `/ready`; treat 503 as a third "degraded" chrome tone.
  - **(B)** keep `/health` static for k8s liveness; add a separate degraded-state poll that drives a third pill or banner.
- Either is small. Pick one, log as **ADR-017**, ship the fix in the same pre-flight session.

---

## Sessions remaining (the path to merge)

Estimate: **1 pre-flight + 1 cutover** with a 24-h monitoring tail. Both should ideally happen in the same week.

### Session N+1 — Phase 9 pre-flight (~75–120 min)

Goal: close the two deferred HIGHs, decide ADR-017, ready the branch for cutover. **No frontend changes.**

1. **Boot live stack**: `bash run_all.sh --local-frontend`
2. **HIGH-1 audit** — `grep -rn "blpop\|xread\|pubsub.*get_message" services/ libs/`. For each match, decide: does the caller depend on indefinite blocking? If yes, give that caller a dedicated client; if no, add the timeouts. Then patch `libs/storage/_redis_client.py:10` with `socket_timeout=5.0, socket_connect_timeout=2.0, health_check_interval=15`.
3. **Validate HIGH-1**: rerun Phase 8.3 S3 scenario — `docker stop deploy-redis-1`, hit `/commands/kill-switch`, expect timeout-exception fail-safe (returns `active=true`) inside 5 s. Restore Redis. Verify chrome pill recovers.
4. **HIGH-2 investigation** — run a 15-min instrumented WS soak first to capture the current close-code distribution. Then:
   - Add granular `try/except` around the inner `listen_to_redis()` loop with explicit `await websocket.close(code=1011, reason=str(e))` on exception paths
   - Check whether `pubsub.get_message(timeout=0.1)` is raising `ConnectionError` periodically — if so, that's the smoking gun
   - Compare uvicorn server logs (`logs/api_gateway.log`) at each 1006 close timestamp from the instrumented client log
5. **Validate HIGH-2**: rerun the instrumented 15-min soak. Expected: 0 reconnects (or only-on-actual-failure reconnects).
6. **ADR-017 decision** (`/health` vs `/ready`):
   - If **(A)**: change `frontend/lib/stores/connectionStore.ts:32-43` to poll `/ready`, add a `degraded` tone to the chrome pill primitive.
   - If **(B)**: leave `/health` alone, add a new poll + new chrome banner.
   - Write ADR-017 in `docs/design/09-decisions-log.md`.
7. **Commits** (3 small ones, separable for easy revert):
   - `fix(libs/storage): add socket_timeout to Redis pool — closes KillSwitch fail-safe gap`
   - `fix(api_gateway): WS connection lifecycle — fix code-1006 cycling` (only if landed)
   - `redesign(chrome): /ready-aware connection pill (ADR-017)` (or B's equivalent)
8. **Update registry**: mark HIGH-1, HIGH-2 (if landed), and the `/health` row RESOLVED with the commit SHAs.
9. **Stop the stack**: `bash run_all.sh --stop`

**Stop and ask if** HIGH-2 turns into a deeper investigation than a single session. It is acceptable to merge with HIGH-2 still open if we have a documented mitigation plan and the frontend reconnect logic provably masks user-facing impact — but explicitly call this out at the start of the cutover session for the user to confirm.

### Session N+2 — Phase 9 cutover day (~half a day with monitoring tail)

Goal: merge `redesign/frontend-v2` into `main`, deploy, monitor.

**This session contains destructive shared-state actions.** Pause and confirm with the user at each numbered step before executing.

1. **Pre-flight gate check** — verify in this order:
   - All Phase 8 gates remain green (re-read this handoff's scoreboard)
   - Registry shows no new HIGH-severity OPEN rows since this handoff
   - `git status` on `redesign/frontend-v2` is clean (modulo `.claude/settings.local.json`)
   - `git log --oneline main..redesign/frontend-v2` matches what we expect to merge
2. **Schedule check** — confirm low-volatility window (weekend, no live profiles). The user should explicitly confirm "go" before any merge command runs.
3. **Notify** — user posts to themselves / team that cutover is starting.
4. **Tag main**: `git tag pre-redesign-cutover` on the current `main` HEAD. `git push origin pre-redesign-cutover`. This is the rollback anchor.
5. **Merge**:
   ```bash
   git checkout main
   git pull origin main
   git merge --no-ff redesign/frontend-v2 -m "Merge redesign/frontend-v2 into main — Phase 9 cutover"
   ```
   Resolve conflicts only if they appear. Don't squash; `--no-ff` preserves the redesign branch history.
6. **Push** (only after user confirms the merge looks right): `git push origin main`
7. **Deploy frontend** — whatever the project's normal deploy path is (Vercel, etc.). Watch the deploy logs.
8. **Smoke test** the canonical surfaces against prod data:
   - `/hot/BTC-USDT` — orderbook + tape stream, can submit a paper order
   - `/agents/observatory` — pending HITL section renders (empty is fine), DebatePanel renders
   - `/risk` — chrome connection pill correct, kill-switch arms
   - `/backtests` — list loads
   - `/settings/*` — all sub-pages render with "Pending" tags where backend gaps remain
9. **24-h monitor**: error-rate dashboards + the Phase 8.3 chrome connection pill on a live session. Flag any regression.

### Session N+3 — Post-cutover cleanup (~30 min, only if 24-h monitor green)

1. **Worktree removal**: `git worktree remove ../aion-trading-redesign`
2. **Legacy archive**: `git mv frontend/DESIGN-SYSTEM.legacy.md docs/historical/` (or delete outright if you've confirmed nothing references it)
3. **Portfolio sync**: read the redesign portfolio (`docs/design/05-surface-specs/*.md`) and update any places where shipped reality diverged from spec. Per ADR-013 §Consequences.
4. **Registry cleanup**: mark all Phase 8.1 GAP rows and `frontend (redesign branch)` rows as historical; promote the surviving deferred items (settings backend gaps, vectorbt regimes, etc.) into post-cutover work queues with explicit owners.
5. **Branch policy**: delete `redesign/frontend-v2` locally and remote? Or keep it as a frozen audit trail? Recommendation: keep remote, delete local. The merge commit references it forever; the branch itself stops mattering.

---

## Rollback procedure

If anything regresses inside the 24-h window:

**Preferred — revert merge** (preserves history, audit-friendly):
```bash
git checkout main
git revert --no-ff <merge-sha>
git push origin main
```
Then redeploy frontend. The next session can re-attempt cutover after fixing whatever broke.

**Nuclear — reset to tag** (use only if revert hits ugly conflicts):
```bash
git checkout main
git reset --hard pre-redesign-cutover
git push origin main --force-with-lease
```
**Do not** run `--force-with-lease` without explicit user confirmation. This rewrites public history.

---

## Open registry rows that survive cutover

The following rows are NOT Phase 9 blockers. They land after merge as separate work — most have their own pending-state UI on the redesign branch so users see "this isn't wired yet" inline.

| Severity | What | Disposition |
|---|---|---|
| MEDIUM | Settings/profiles backend gaps (risk defaults, notifications, tax client, sessions, audit) | In-page "Pending" tags acceptable for Phase 9; spec each as separate work items |
| MEDIUM | Orderbook WS gap — selective channel dropouts on `/hot/BTC-USDT` | Discovered 2026-05-11; tape unaffected. Investigate when WS HIGH-2 is being worked. |
| MEDIUM | Backtesting simulator doesn't honour `preferred_regimes` | Affects backtest fidelity for regime-gated profiles. Separate work. |
| LOW | Coinbase adapter not wired into ingestion `main.py` | Uncomment + verify sandbox creds; 1 commit |
| LOW | `pnl:daily:...` malformed hash, self-healing | Operational only; will self-heal on next close per registry note |
| LOW | OrderBook "stale Xs" badge tracks wrong timestamp source | UI-only display bug; ~10 LOC in `frontend/components/trading/OrderBook.tsx` |
| LOW | §8.4-A CLS spinner `animate-spin` non-composited | One-line `will-change-transform`; project-wide audit warranted |
| LOW | Phase 8.3 playbook S2/S3 assume WS goes through non-gateway path | Docs hygiene; fix during next pass over the playbook |

---

## Things to be aware of (carrying forward + new)

Carrying forward from earlier handoffs (still valid):
- `PRAXIS_PAPER_TRADING_MODE` defaults to `false` on this branch; **do not toggle without explicit user direction.**
- `set-state-in-effect` warning at `OrderBook.tsx:275` is pre-existing; not a regression.
- `PriceChart` canvas is `aria-hidden` intentionally — `lightweight-charts` doesn't expose a meaningful tree.
- Test profile: `9c94da6c-8d20-42f3-b086-9170e3ba8f2c` (Mean Reversion).

New from Phase 8 close:
- **The two HIGH findings landed in the registry from Phase 8.3 / 8.4-C are deferred but not forgotten** — see Pre-flight section above. Don't merge without at least HIGH-1 (Redis socket_timeout) closed.
- **`.claude/settings.local.json`** is uncommitted and should stay that way — local harness permission state, not project state.
- **Prod build artifacts at `frontend/.next/`** may be stale by the time you start this work — run `npm run build` fresh before the smoke-test step.
- **`run_in_background` notifications for sleeps > 60 s are unreliable** — use `Monitor` for long waits if you re-run Phase 8 gates.

---

## Suggested next-session prompt

> Continue the Praxis frontend redesign on `redesign/frontend-v2`. Phase 8 is closed end-to-end; we're in Phase 9. **Read `docs/design/HANDOFF-PHASE-9-START.md` before anything else** — it lays out 2 sessions (pre-flight + cutover) plus a 24-h monitoring tail.
>
> Plan for today (Session N+1, Phase 9 pre-flight):
> 1. Boot `bash run_all.sh --local-frontend`.
> 2. Audit long-blocking Redis callers (`grep -rn "blpop\|xread\|pubsub.*get_message" services/ libs/`), then patch `libs/storage/_redis_client.py:10` with `socket_timeout=5.0, socket_connect_timeout=2.0, health_check_interval=15`. Re-run Phase 8.3 S3 to validate the KillSwitch fail-safe now fires.
> 3. Investigate the WS code-1006 cycling in `services/api_gateway/src/routes/ws.py` — start with an instrumented 15-min soak to capture close-code patterns, then patch the inner pubsub loop. Re-run the soak to validate 0 reconnects.
> 4. Decide ADR-017 (`/health` vs `/ready` for chrome connection pill); ship the fix in the same session.
> 5. Three separable commits (`fix(libs/storage): ...`, `fix(api_gateway): ...`, `redesign(chrome): ...`). Update registry.
> 6. Stop the stack.
>
> Stop and ask before any cutover-day step in Session N+2 — that session contains destructive shared-state actions (git tag, merge, push) and the user must explicitly confirm each one.

---

## Other artifacts to know about

- **`HANDOFF-PHASE-8-FINAL.md`** — superseded by this file. Leave in place as audit trail.
- **`HANDOFF-PHASE-8-CONTINUE.md`** / **`HANDOFF-PHASE-8-START.md`** / **`HANDOFF-PHASE-7-START.md`** / **`HANDOFF-6.3-START.md`** / **`HANDOFF-6.2-CONTINUATION.md`** — earlier handoffs, audit trail.
- **`docs/design/PHASE-8-PERF-PLAYBOOK.md`** — §8.4-A/B/C procedures, prod-build requirement baked in.
- **`docs/design/PHASE-8-RESILIENCE-PLAYBOOK.md`** — S1/S2/S3 scenarios. Note the 2 architectural divergences logged in the registry (LOW row 35) — fix during next pass.
- **`docs/design/PHASE-8-PARITY-AUDIT.md`** — coverage matrix; reference when deciding what post-cutover work to schedule.
- **`docs/design/perf-traces/2026-05-11-results.md`** — §8.4-A/B/C results. Frozen — Phase 8 reference.
- **`docs/design/perf-traces/2026-05-11-resilience-results.md`** — Phase 8.3 results. Frozen.
- **`docs/TECH-DEBT-REGISTRY.md`** — open rows that survive cutover tracked in the table above.
- **`docs/design/09-decisions-log.md`** — ADR-015 (daily-report removal), ADR-016 (HITL placement). ADR-017 (`/health` vs `/ready`) to be written during Session N+1.
- **`docs/design/11-redesign-execution-plan.md`** — Phase 9 §9.1–9.4 are the canonical cutover spec; this handoff operationalizes them.
