# Handoff — Phase 8 final stretch (post 8.4-A + 8.4-C, into 8.3 + 8.4-B)

> Generated 2026-05-11 end-of-session. **Three of five Phase 8 gates are closed; one is half-closed (8.4-A and 8.4-C green, 8.4-B still pending); one is unstarted (8.3 resilience).** This handoff supersedes `HANDOFF-PHASE-8-CONTINUE.md`; leave that file in place as audit trail. Read this end-to-end before booting the stack. Estimate: **4 more focused sessions to merge**, plus one cutover-day session.

---

## Branch state

- Branch: `redesign/frontend-v2`
- Worktree: `C:\Users\stevo\DEV\agent_trader_1\aion-trading-redesign`
- Last commit (head): `7a63ea5 docs(8.4 playbook): require prod build for measurement; add MCP-driven option`
- Uncommitted at end of this session (commit at the start of the next one):
  - `docs/design/perf-traces/2026-05-11-results.md` — §8.4-C clean PASS write-up replacing the earlier PROVISIONAL
  - `docs/TECH-DEBT-REGISTRY.md` — 3 new rows added during today's soak (HIGH WS cycling, MEDIUM expired-JWT, LOW stale badge)
  - `docs/design/HANDOFF-PHASE-8-FINAL.md` — this file
  - `frontend/.perf-traces-tmp/` — soak-t0/t60 heapsnapshots (gitignored; can delete or keep as local reference)
- Tests: vitest 65/65 still green (no test changes this session). `tsc --noEmit` clean on redesign code.
- `next build` works (the 5 TS errors that blocked 8.4-A prod re-measurement were cleared in commit `0a08f2d`).

---

## Local env setup (unchanged — see `HANDOFF-PHASE-8-CONTINUE.md` §"Local env setup" for full details)

Two reminders that bit this session:

1. **For perf measurement (8.4-A, 8.4-B, 8.4-C) you need a PROD build**, not `next dev`. The playbook now requires this (commit `7a63ea5`). Use:
   - Backend: `bash run_all.sh` (NOT `--local-frontend` — dev frontend ships unminified, broken FCP measurement)
   - Frontend: `cd frontend && npm run build && npm start` → prod build on `:3000`
   For everything else (resilience runs, GAP fixes, general work) `bash run_all.sh --local-frontend` is still the right boot.

2. **`bash run_all.sh --stop` is reliable**; the PIDFILE cleanup works correctly. If it ever leaves zombies on a port, kill via `Get-NetTCPConnection -LocalPort <N>` PowerShell snippet before retrying.

---

## What shipped today (2026-05-11)

Three commits and the uncommitted results above. In build order:

**`ab6b304 docs(redesign): Phase 8 parity audit, perf + resilience playbooks, GAP registry`**
- The four parity-audit deliverables from the previous handoff's "uncommitted" list, finally committed.

**`e5c160b fix(api_gateway): allow http://localhost:3001 in default CORS origins`**
- Tiny CORS fix to unblock the dev-mode prod-frontend port-3001 case.

**`7aa9aae redesign(8.4-A): FCP fail on /hot/BTC-USDT — 2204ms vs 1500ms gate`**
- First (incorrect) §8.4-A measurement run. Logged as HIGH in the registry before the prod-build re-measure flipped it.

**`0a08f2d redesign(8.4-A): FCP passes (892ms) on prod build — dev measurement was instrument error`**
- The real §8.4-A: cold-cache prod-build FCP = **892 ms**, passes the < 1,500 ms gate by 608 ms. Required clearing 4 redesign-branch TS errors + 1 legacy-UI TS error to make `next build` succeed. All five fixes in this commit.

**`7a63ea5 docs(8.4 playbook): require prod build for measurement; add MCP-driven option`**
- Playbook Pre-flight updated. Added a chrome-devtools-mcp-driven option alongside the human-driven flow.

**§8.4-C memory soak — PASS (today, uncommitted in `2026-05-11-results.md`)**
- t0 → t60 delta on `usedJSHeapSize`: **−9.0 MB** against the < 50 MB gate. Measured with WS load instrumented via a `window.WebSocket` shim: **321,536 frames** received across 54 connections / 43 successful reconnects over 60 minutes. First attempt was a false PROVISIONAL pass (Chrome backgrounded the tab, soak measured 21 min live + 93 min dormant); second attempt instrumented the WS to prove load was applied and got a clean read. Methodology delta documented in the results file.

---

## Phase 8 scoreboard (updated)

```
[x] 8.1 Functional parity with main          — 4 GAP rows in TECH-DEBT-REGISTRY (3 are Phase 9 blockers)
[x] 8.2 Design fidelity                       — green; legacy hex exceptions documented
[ ] 8.3 Critical-path resilience              — NOT STARTED. Playbook doesn't exist yet.
[~] 8.4 Performance budget                    — 8.4-A ✅ (892 ms), 8.4-B ❌ (deferred), 8.4-C ✅ (−9 MB)
[x] 8.5 Accessibility minimum                 — green
```

**Phase 8 closes when 8.3 lands green AND 8.4-B lands green AND GAP-1/2/3 close (or get formal removal in `09-decisions-log.md`).**

---

## New HIGH finding from today's soak (separate from the gates)

Phase 8.4-C instrumented the WebSocket connection and surfaced three backend/frontend issues. Two are LOW/MEDIUM hygiene; one is HIGH and likely needs to be touched during 8.3 resilience work:

| Severity | What | Why it matters |
|---|---|---|
| **HIGH** | `api_gateway` WS closes every 1–2 min with code 1006 (abnormal closure). 43 reconnects in 60 min on a healthy stack. | Frontend reconnect logic masks it perfectly, but the backend behavior is wrong. Every reconnect re-auths, re-subscribes, and rebuilds server-side state. Likely an idle-timeout or heartbeat misconfig in `services/api_gateway/src/routes/ws.py`. **Will affect §8.3 resilience scenarios** — kill-and-recover may behave inconsistently if the connection's already cycling. |
| MEDIUM | WS auth: expired JWT (`exp 15:37Z`) accepted at handshake for ~50 min into the soak. | Token expiry not enforced at WS connect. Security hygiene + WS reliability. 5-line fix in `routes/ws.py`. |
| LOW | `OrderBook` "stale Xs" badge tracks a different timestamp source than the one that mutates row data. Badge climbed 60s → 488s during the soak while rows rendered fresh prices throughout. | UI-only display bug. A "stale" badge that always reads stale trains users to ignore it. |

All three rows are in `docs/TECH-DEBT-REGISTRY.md`. The HIGH should be folded into the next session's 8.3 work.

---

## Sessions remaining (the path to merge)

Estimate: **4–5 sessions** to merge, give or take. Here's the proposed sequence, with what each session must accomplish.

### Session N+1 — Phase 8.3 resilience + the WS HIGH (~90 min)

This is the next session. Hand-on-keyboard with the live stack.

1. **Commit the uncommitted from today first** (one commit: §8.4-A + §8.4-C results, the 3 new registry rows, this handoff). Suggested message: `redesign(8.4-A + 8.4-C): perf gates green — FCP 892ms, soak −9MB / 50MB`.
2. **Write `docs/design/PHASE-8-RESILIENCE-PLAYBOOK.md` first** (5-min prep job). Concept:
   - Kill `services/ingestion`. `/hot` should show `stale Xs` on OrderBook + Tape, `awaiting feed` on PriceChart, no white screen. Restore — surfaces should reconnect without page reload.
   - Kill `services/api_gateway`. `/risk` should show backend-offline banner; chrome connection pill should reflect; kill-switch modal should still try to flip via Redis fallback. Restore.
   - Kill Redis (`docker stop deploy-redis-1`). `KillSwitch.is_active` should fail-safe to ACTIVE — verify chrome pill flips to "armed" or the modal shows fail-safe state. Restore.
   - Each scenario: one screenshot, one PASS/FAIL line in `docs/design/perf-traces/2026-05-11-resilience-results.md`.
3. **Investigate the HIGH WS cycling in parallel** — when you stop `api_gateway` and restart it in the playbook above, observe the WS reconnect behavior. The `routes/ws.py` heartbeat / idle-timeout config is the suspect; a fix in this session would close the HIGH row and strengthen the 8.3 resilience signal in one move.
4. **Commit**: `redesign(8.3): resilience runs green` + (if the WS HIGH closes) `fix(api_gateway): WS heartbeat / idle-timeout`.

If any scenario white-screens or hangs, log HIGH and stop — Phase 9 is blocked.

### Session N+2 — Phase 8.4-B + polish fixes (~60–90 min)

Same boot (prod build on :3000 for measurement, live backend).

1. **Run §8.4-B from the playbook**: 60-s Performance record in Chrome DevTools (or chrome-devtools-mcp `performance_start_trace` / `performance_stop_trace`) on `/hot/BTC-USDT` under live load. Pass criteria: no long task > 50 ms, `BookRow` render < 5 ms/frame.
2. **Fix the §8.4-A CLS spinner** (registry row, LOW): one-line `will-change-transform` on `Loader2` in `frontend/components/trading/PriceChart.tsx:360`. Also audit `frontend/app/hot/[symbol]/page.tsx:787` and any other `animate-spin` callsites.
3. **Fix the OrderBook stale-badge bug** (today's LOW row): probably 10-min investigation, ~10 LOC in `frontend/components/trading/OrderBook.tsx`.
4. **Optional: GAP-1 in the same commit** — `frontend/app/page.tsx` redirect `/trade` → `/hot/BTC-USDT`. 2-line change. Test by visiting `localhost:3001/`.
5. **Commit**: `redesign(8.4-B + polish): frame budget green, CLS spinner, OrderBook stale badge, GAP-1`.

### Session N+3 — GAP-2 design call + GAP-3 + GAP-4 (~60 min)

This is where the redesign needs a **design decision from you** before code starts.

1. **Decide GAP-2 first**: HITL approval queue needs a home in the redesign chrome. Two options:
   - **(a) Embed in `DebatePanel` override flow on `/agents/observatory`** — already specced (`04-component-specs/agentic.md` §DebatePanel "interventionEnabled" variant). HITL becomes a special case of override. Lower surface count.
   - **(b) Dedicated `/approvals` sub-route** — restores the legacy queue under redesign chrome. 1:1 port; safer; higher surface count.
   - Log decision as **ADR-016** in `09-decisions-log.md` whichever way you go.
2. **Land GAP-3** (mode badge in chrome): small `Pill` next to kill-switch in `HotChrome` + `RedesignShell.ChromeBar`. Reuse the `Pill` primitive; intent should be `warn` for PAPER, `accent` for TESTNET, `danger` for LIVE. Reads `api.paperTrading.mode()`.
3. **Land GAP-4 decision**: either land a small button in `/settings/audit` or `/backtests`, or formally accept removal in `09-decisions-log.md` as **ADR-015**. Lower priority than GAP-2/3.
4. **Commit**: `redesign(8.1 GAPs): mode badge + GAP-4 decision + ADR-015/016`. Mark the registry rows RESOLVED.

### Session N+4 — GAP-2 implementation (~60–90 min)

Whichever option you chose in N+3.

- **If (a) DebatePanel override**: extend the `interventionEnabled` variant in `frontend/components/agentic/DebatePanel.tsx` to render the HITL approve/reject buttons when `api.hitl.pending()` has items. Wire `api.hitl.respond()` from the existing client. Surface only on `/agents/observatory` when there are pending approvals.
- **If (b) dedicated `/approvals` route**: port `frontend/app/approval/page.tsx` into the redesign chrome at `frontend/app/approvals/page.tsx`. Use redesign primitives only; the legacy file can be deleted at Phase 9 cutover.
- **Commit**: `redesign(8.1 GAP-2): HITL via {DebatePanel | /approvals}`.

### Session N+5 — Phase 9 cutover (~half a day with monitoring)

When 8.3 + 8.4-B are green AND GAPs 1/2/3 are closed AND GAP-4 has a decision:

1. **Pre-flight**: `git tag pre-redesign-cutover` on `main`. Schedule low-volatility window (weekend, no live profiles). Notify yourself.
2. **Merge**:
   ```
   git checkout main
   git pull origin main
   git merge --no-ff redesign/frontend-v2
   git push origin main
   ```
3. **Deploy frontend**. Smoke test the canonical surfaces against prod data. Monitor errors for 24 h.
4. **Cleanup**: `git worktree remove ../aion-trading-redesign`. Archive `frontend/DESIGN-SYSTEM.legacy.md` to `docs/historical/` or delete. Update the design portfolio where reality diverged from spec (per `11-redesign-execution-plan.md` §9.3).

If anything regresses in the 24h window, the rollback path is `git revert --no-ff <merge-sha>` (preferred — preserves history) or `git reset --hard pre-redesign-cutover` (nuclear option).

---

## Things to be aware of (carrying forward + new)

Old (from `HANDOFF-PHASE-8-CONTINUE.md`, still valid):
- **§8.4 playbook assumes prod build, mobile Lighthouse, clean Chrome incognito.** Extensions on your normal profile skew everything. Use `Ctrl+Shift+N`.
- **Don't open extra `/hot` tabs during 8.4-B / 8.4-C.** Each tab opens its own WebSocket and skews traffic.
- **`set-state-in-effect` warning at `OrderBook.tsx:275`** is pre-existing; not a regression.
- **`PriceChart` canvas is `aria-hidden`** intentionally — `lightweight-charts` doesn't expose a meaningful tree to AT. Don't try to "fix" during resilience runs.
- **Test profile**: `9c94da6c-8d20-42f3-b086-9170e3ba8f2c` (Mean Reversion (RSI + Z-Score)) owned by user `6322b6fa-d425-51d7-a818-088c19275228`.

New from this session:
- **`bash run_in_background` notifications are unreliable for long sleeps.** Today's first soak hung past its target because the 60-min notification never fired. Use the `Monitor` tool for waits > 5 min in future runs — its event-stream model is reliable.
- **chrome-devtools-mcp's heap-snapshot capture briefly drops the WS connection** (code 1006). The frontend reconnect logic recovers in ~3 s, so post-snapshot `performance.memory` readings reflect a live page. Account for this if you're measuring at sub-second granularity.
- **The expired JWT in WS URL still works.** Today's instrumented soak showed handshakes succeeding for ~50 min on a token whose `exp` was already 1h 46m past. If you observe weird WS behavior during 8.3, check this isn't masking another bug.
- **PIDFILE-based stop is clean** when used correctly. `bash run_all.sh --stop` walked through all 20 PIDs today without leaving zombies. But if a previous session crashed mid-run, the PIDFILE may be stale — check `.praxis_pids` exists before assuming stop works.
- **Prod build artifacts at `frontend/.next/`** are still warm from today — `npm start` should work without rebuild for the next session if no frontend files change. If you touch `app/` or `components/`, run `npm run build` first.

---

## Open registry rows the next sessions will close

Tracking only redesign-branch items still OPEN (legacy / backend items elided):

| Severity | What | Owner session |
|---|---|---|
| HIGH | api_gateway WS code-1006 cycling every 1–2 min | N+1 |
| HIGH | GAP-1 root redirect `/trade` → `/hot/BTC-USDT` | N+2 (bundled) |
| MEDIUM | GAP-2 HITL has no redesign home | N+3 + N+4 |
| MEDIUM | GAP-3 PAPER/TESTNET/LIVE badge missing | N+3 |
| MEDIUM | WS auth: expired JWT accepted at handshake | N+1 (during WS investigation) |
| LOW | GAP-4 manual daily-report button | N+3 (ADR-015) |
| LOW | §8.4-A CLS spinner `animate-spin` non-composited | N+2 |
| LOW | OrderBook "stale Xs" badge wrong timestamp source | N+2 |
| MEDIUM | Settings/profiles backend gaps (risk defaults, notifications, tax client, sessions, audit) | Deferred — in-page "Pending" tags acceptable for Phase 9 |
| MEDIUM | Orderbook WS gap (selective channel dropouts) | Deferred — not blocking; may affect 8.4-B |
| LOW | Coinbase adapter not wired into ingestion main.py | Deferred — non-blocking |
| MEDIUM | Backtesting simulator doesn't honor `preferred_regimes` | Deferred — backtest fidelity, separate work |
| LOW | `pnl:daily:...` malformed hash, self-healing | Deferred — operational |

The "Deferred" items are explicitly NOT Phase 9 blockers. They land after merge as separate work.

---

## Suggested next-session prompt

> Continue the Praxis frontend redesign on `redesign/frontend-v2`. Phase 8 is 70% done — 8.1, 8.2, 8.4-A, 8.4-C, 8.5 are green; 8.3 (resilience) and 8.4-B (frame budget) remain. **Read `docs/design/HANDOFF-PHASE-8-FINAL.md` before anything else** — it lays out the 4–5 sessions left to merge.
>
> Plan for today (Session N+1 in the handoff):
> 1. Commit the uncommitted from the prior session (perf results + 3 new registry rows + the FINAL handoff).
> 2. Write `docs/design/PHASE-8-RESILIENCE-PLAYBOOK.md` — kill-and-recover scenarios for ingestion, api_gateway, Redis.
> 3. Boot `bash run_all.sh --local-frontend` and run all three scenarios. Screenshot each. PASS/FAIL into `docs/design/perf-traces/2026-05-11-resilience-results.md`.
> 4. While api_gateway is stopped and restarted in (3), investigate the HIGH WS cycling issue from yesterday's soak (registry row dated 2026-05-11). Likely an idle-timeout / heartbeat misconfig in `services/api_gateway/src/routes/ws.py`. Fix in the same session if straightforward.
> 5. Commit `redesign(8.3): resilience runs green` and, if applicable, `fix(api_gateway): WS heartbeat / idle-timeout`.
>
> Stop and ask if any resilience scenario white-screens, hangs, or the WS investigation is deeper than a single session.

---

## Other artifacts to know about

- **`HANDOFF-PHASE-8-CONTINUE.md`** — superseded by this file. Leave in place as audit trail.
- **`HANDOFF-PHASE-8-START.md`** — earlier handoff, still in place as audit trail.
- **`docs/design/PHASE-8-PERF-PLAYBOOK.md`** — has the §8.4-A / B / C procedures. Updated this session to require prod build.
- **`docs/design/PHASE-8-PARITY-AUDIT.md`** — coverage matrix; reference when deciding GAP fixes.
- **`docs/design/PHASE-8-RESILIENCE-PLAYBOOK.md`** — does not yet exist. First thing in session N+1.
- **`docs/design/perf-traces/2026-05-11-results.md`** — §8.4-A and §8.4-C results live here. §8.4-B run will append.
- **`docs/TECH-DEBT-REGISTRY.md`** — open rows tracked in the table above.
- **`docs/design/09-decisions-log.md`** — ADR-015 (GAP-4) and ADR-016 (GAP-2) need writing during session N+3.
- **`docs/design/11-redesign-execution-plan.md`** — Phase 8 §8.1–8.5 and Phase 9 are described there at the same detail level as 4–7. Use as the spec.
