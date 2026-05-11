# Handoff — Phase 8 continue (post 8.1/8.2/8.5 + 8.4 prep)

> Generated 2026-05-10 at the end of a desk-only session. Three of the five Phase 8 gates are closed. The remaining two (8.4 perf, 8.3 resilience) are gated on a real-browser session against the live local stack — that's tomorrow's work, and it's mostly your hand on the keyboard. **This handoff supersedes `HANDOFF-PHASE-8-START.md`**; leave that one in place as audit trail. Read this end-to-end before booting the stack — it tells you what shipped, what's still open, and the exact step sequence for tomorrow.

---

## Branch state

- Branch: `redesign/frontend-v2`
- Worktree: `C:\Users\stevo\DEV\agent_trader_1\aion-trading-redesign`
- Last commit (head): `7547df5 redesign(8.2 + 8.5): design fidelity + /hot keyboard audit complete`
- Pending uncommitted (this session's analysis deliverables — commit before starting tomorrow):
  - `docs/design/PHASE-8-PARITY-AUDIT.md` (new) — 8.1 coverage matrix
  - `docs/design/PHASE-8-PERF-PLAYBOOK.md` (new) — 8.4 step-by-step runbook
  - `docs/TECH-DEBT-REGISTRY.md` (modified) — 4 new rows for the parity gaps
  - `docs/design/HANDOFF-PHASE-8-CONTINUE.md` (this file)
- Tests: vitest 65/65 still green. PriceChart.test 14/14 green after the aria-label tweak.
- `tsc --noEmit`: redesign code clean. Same pre-existing legacy errors.
- `next dev`: works. `next build` still blocked by legacy `EquityCurveChart`. Phase 9 deletes it.

---

## Local env setup (unchanged from last handoff — read here first if you've forgotten)

The `.env` at the repo root must contain the keys listed in `HANDOFF-PHASE-8-START.md` §"Local env setup". If you generated them last session, they're still good. Two reminders:

- **Frontend serves on :3001**, not :3000 (the `run_all.sh` banner lies).
- **`PRAXIS_TRADING_ENABLED=true` + `PRAXIS_PAPER_TRADING_MODE=true`** is the only combination that lets order submission complete.

Boot: `bash run_all.sh --local-frontend` from `aion-trading-redesign/`. Stop: `bash run_all.sh --stop`.

---

## What shipped today

Commit chain in build order:

**8.2 + 8.5 — design fidelity + keyboard audit** (commit `7547df5`)
- 8.2 hex grep: 19 files match. All in legacy paths (slated for Phase 9 deletion: `decisions/`, `performance/`, `agent-view/`, `analysis/`) or two documented exceptions in active redesign (`trading/PriceChart.tsx` `FALLBACK_TOKENS` for canvas-paint defaults; `docs/MermaidDiagram.tsx` Mermaid `themeVariables` runtime config). The handoff's expected-legacy list was incomplete — `agent-view/` and `analysis/` aren't called out there but are in fact legacy (consumed only by `app/agent-view/` and `app/trade/` respectively).
- 8.2 component-spec consumer check: all 36 components specified in `docs/design/04-component-specs/` have implementation files; the rare ones (DepthChart, RiskMeter, MiniMap, ReasoningStream, ToolCall, ConfidenceBar, Chart) all have at least one consumer in `app/risk/`, `app/canvas/`, `app/agents/observatory/`, `app/backtests/`, or the `app/design-system/` showcase.
- 8.5 keyboard audit on `/hot`: every interactive has focus-visible + accessible name; OrderBook is a real ARIA grid with arrow-key nav; OrderEntryPanel uses explicit `tabIndex={1..5}` per spec for `side → size → price → leverage → submit`; PriceChart canvas is `aria-hidden` with `role="region"` on the wrapper (lightweight-charts compromise documented in the prior handoff). Cmd+Shift+K still global on `RedesignShell`.
- One small fix: `frontend/components/trading/PriceChart.tsx:344` — added `aria-label="Drawing tools (Pending v2)"` to the disabled drawing-tools placeholder. It only had `title`, which AT support is inconsistent for.

**8.1 + 8.4 prep — uncommitted as of writing this handoff**
- `PHASE-8-PARITY-AUDIT.md` — every legacy URL on `origin/main` mapped to its redesign owner. Every API namespace in `lib/api/client.ts` mapped to its redesign consumer. The §8.1 spec checklist (URLs, API calls, auth, profile CRUD, orders/positions, backtests, kill switch) verified item by item.
- `PHASE-8-PERF-PLAYBOOK.md` — runnable Chrome session for §8.4. Pass/fail thresholds (FCP < 1500 ms, no long task > 50 ms, < 50 MB heap growth in 1 h), pre-flight checks, four numbered sections (Lighthouse, Performance record, memory soak, micro-checks), reporting protocol.
- TECH-DEBT-REGISTRY.md — 4 new rows for the gaps the parity audit found.

---

## Phase 8 scoreboard

```
[x] 8.1 Functional parity with main          — 4 gaps logged in TECH-DEBT-REGISTRY (3 are Phase 9 blockers)
[x] 8.2 Design fidelity                       — green; legacy hex literals expected, exceptions documented
[ ] 8.3 Critical-path resilience              — needs failure-injection runs against the live local stack
[ ] 8.4 Performance budget                    — playbook ready; needs Chrome session against live data
[x] 8.5 Accessibility minimum                 — green; one minor a11y fix shipped
```

**Phase 8 unblocks Phase 9 once 8.3 + 8.4 land green AND parity gaps GAP-1/2/3 close (or get formally accepted as feature regressions in `09-decisions-log.md`). GAP-4 is deferrable.**

---

## The four parity gaps (from `PHASE-8-PARITY-AUDIT.md`)

These are real things missing from the redesign that exist on legacy main. Each is logged in TECH-DEBT-REGISTRY with severity and Phase 9 blocker status.

| ID | What | Effort | Blocker? | Recommended action |
|---|---|---|---|---|
| GAP-1 | `app/page.tsx` redirects to `/trade` (legacy). After Phase 9 deletes `app/trade/`, root will 404. | S (2-line change) | YES | Fix solo — change redirect to `/hot/BTC-USDT`. |
| GAP-2 | HITL approval queue (`api.hitl.respond`) only consumed by legacy `app/approval/`. No redesign surface integrates it. | M | YES | Needs a design call from you: embed in DebatePanel override flow on `/agents/observatory`, or new `/approvals` sub-route. |
| GAP-3 | Trading-mode badge (PAPER/TESTNET/LIVE) absent from redesign chrome. Misreading mode = real-money risk. | S | YES | Small `Pill` next to kill-switch in `HotChrome` + replicated in `RedesignShell.ChromeBar`. |
| GAP-4 | Manual daily-report-generation button absent. Daemon auto-generates, so the manual button is for backfilling. | S | NO | Defer or move to `/settings/audit` or `/backtests`. |

---

## Tomorrow's task (in order)

The recommended sequence is one Chrome session for 8.4 + 8.3 back-to-back, then small fix-up commits for GAP-1/3 if you have time. GAP-2 needs your design call before any code.

### Step 1 · Boot the stack (5 min)

```
bash run_all.sh --local-frontend
```

from `aion-trading-redesign/`. Wait for "All services started" banner. Then verify the live data pipe:

```
docker exec deploy-redis-1 redis-cli -a changeme_redis_dev SUBSCRIBE pubsub:orderbook pubsub:trades
```

You should see top-25 BTC/USDT and ETH/USDT snapshots at ~10 Hz plus trade prints with real `trade_id`s. **If silent, stop and fix ingestion before doing perf work** — the entire perf trace is meaningless against a degraded data feed.

### Step 2 · Run §8.4 perf playbook (~75 min, mostly walking away)

Open `docs/design/PHASE-8-PERF-PLAYBOOK.md` in a second window. Follow A → B → C → D in order:

- **A** Lighthouse FCP, 5 min — pass: < 1500 ms on Mobile profile.
- **B** 60-s Performance record under live load, 15 min — pass: zero long tasks > 50 ms, `BookRow` < 5 ms/frame.
- **C** 1-h memory soak — pass: < 50 MB heap delta. Walk away during this.
- **D** Micro-checks (network/console/React Profiler), 10 min in parallel with C.

If anything fails, capture the trace and log a HIGH-severity row in TECH-DEBT-REGISTRY before moving on. The playbook tells you exactly what to look for in each failure mode.

If everything passes, commit `redesign(8.4): perf budget green — FCP <1.5s, no >50ms tasks, no leak` with a short results file at `docs/design/perf-traces/2026-05-10-results.md` listing the three numbers.

### Step 3 · Run §8.3 resilience (~30 min, same browser session)

The §8.3 playbook isn't written yet — that's a 5-minute prep job. Ask your assistant to write `docs/design/PHASE-8-RESILIENCE-PLAYBOOK.md` first thing in the next session, before booting the stack. Concept:

- Kill `services/ingestion`. `/hot` should show `stale Xs` tags on OrderBook + Tape, `awaiting feed` on PriceChart, no white screen.
- Kill `services/api_gateway`. `/risk` should show backend-offline banner; chrome connection pill should reflect; kill-switch modal should still try to flip via Redis fallback.
- Kill Redis. `KillSwitch.is_active` should fail-safe to ACTIVE — verify by checking the chrome pill goes to "armed" or the modal shows the fail-safe state.
- Restore each service in turn; surfaces should reconnect without page reload.

Each scenario gets a screenshot and a one-line PASS/FAIL. If any surface white-screens or hangs, that's a HIGH-severity find — log and fix before merge.

### Step 4 (optional) · Close GAP-1 + GAP-3 in one small commit (~30 min)

These two are pure frontend, low-risk:

- **GAP-1**: `frontend/app/page.tsx` — change `redirect('/trade')` → `redirect('/hot/BTC-USDT')`. Two-line change. Test by visiting `localhost:3001/` after the change.
- **GAP-3**: Add a small `Pill` next to the kill-switch pill in `HotChrome` (and in `RedesignShell.ChromeBar` for cross-surface coverage) showing PAPER/TESTNET/LIVE from `api.paperTrading.mode()`. Reuse the `Pill` primitive (no new component); intent should be `warn` for PAPER, `accent` for TESTNET, `danger` for LIVE.

Commit as `redesign(8.1 GAP-1 + GAP-3): root redirect to /hot, mode badge in chrome` and update the registry rows to RESOLVED.

### Step 5 · Decide on GAP-2 (HITL)

This needs your call before any code. Two options:

- **(a) Embed in DebatePanel override flow on `/agents/observatory`** — already specced (per `04-component-specs/agentic.md` §DebatePanel "interventionEnabled" variant). HITL becomes a special case of override.
- **(b) Dedicated `/approvals` sub-route** — restores the legacy queue under redesign chrome. Lower-risk because it's a 1:1 port; higher cost because it's a new surface to maintain.

If you can't decide today, defer to a follow-up session. Phase 9 cutover blocks until this lands one way or the other.

### Step 6 · Decide on GAP-4 (daily report)

Either land a small button in `/settings/audit` or `/backtests`, or formally accept the removal in `09-decisions-log.md` as ADR-015. Lower priority than the rest.

---

## Things to be aware of

- **The §8.4 playbook assumes a clean Chrome incognito window.** Extensions on your normal profile will skew every measurement. Use `Ctrl+Shift+N` for the perf session.
- **Use Mobile Lighthouse, not Desktop, for the FCP threshold.** Spec says FCP < 1.5s "on Hot Trading"; the rest of the spec uses Mobile-as-default for budgets, so that's the gate. Capture Desktop too for context.
- **Don't open extra `/hot` tabs during the 1-h soak.** Each tab opens its own WebSocket and skews the multi-symbol traffic. Keep the soak window single-tab.
- **Live data publishes at ~10 Hz today, not 100 Hz.** The spec's "100 updates/s" budget on OrderBook is for a worst-case future. Your perf trace will be against the 10 Hz reality. The 7.4 perf work was done against a synthetic stress test that approximates 100 Hz; the live trace tomorrow validates the lower-traffic path.
- **`set-state-in-effect` warning at `OrderBook.tsx:275`** is pre-existing (predates 7.4). Console will show it. **Not a regression.** Don't fix opportunistically.
- **The PriceChart canvas is `aria-hidden`** intentionally — `lightweight-charts` doesn't expose a meaningful tree to AT. The wrapper has `role="region"` with an aria-label. This is the documented compromise; don't try to "fix" it during the resilience runs.
- **The 4 parity gaps are tracked in `docs/TECH-DEBT-REGISTRY.md`**, not in the surface specs. If you fix one, update the registry row to RESOLVED with date + commit hash; don't delete it.
- **Order submission is real in PAPER mode.** Same caveat as last handoff — the executor places fictional fills via the PAPER adapter. Don't toggle `PRAXIS_PAPER_TRADING_MODE=false` unless you mean it.
- **Test profile in DB** for manual smoke testing: `9c94da6c-8d20-42f3-b086-9170e3ba8f2c` (Mean Reversion (RSI + Z-Score)) owned by user `6322b6fa-d425-51d7-a818-088c19275228`. JWT-forge command in the prior handoff §"Things to be aware of".

---

## Suggested next-session prompt

> Continue the Praxis frontend redesign on `redesign/frontend-v2`. Phase 8 is half done — gates 8.1, 8.2, 8.5 are closed; 8.3 and 8.4 are the remaining gates and need a real-browser session against the live local stack. Read `docs/design/HANDOFF-PHASE-8-CONTINUE.md` before anything else.
>
> Plan for today:
> 1. First: ask the assistant to write `docs/design/PHASE-8-RESILIENCE-PLAYBOOK.md` (the §8.3 runbook — kill ingestion / api_gateway / Redis in turn, verify graceful degradation). This is a 5-minute prep job and unblocks running 8.4 + 8.3 in the same session.
> 2. Then boot the stack: `bash run_all.sh --local-frontend` from the redesign root. Verify live ingestion via `docker exec deploy-redis-1 redis-cli -a changeme_redis_dev SUBSCRIBE pubsub:orderbook pubsub:trades`.
> 3. Run the §8.4 perf playbook in incognito Chrome: Lighthouse FCP, 60-s Performance record, 1-h memory soak, micro-checks. Pass thresholds: FCP < 1.5s, no long task > 50ms, < 50MB heap growth.
> 4. Run the §8.3 resilience tests in the same browser session.
> 5. If both pass: commit `redesign(8.3 + 8.4): resilience and perf budgets green` with a results file. Phase 8 closes.
> 6. If time remains: close GAP-1 (root redirect to `/hot/BTC-USDT`) and GAP-3 (mode badge in chrome). Both are S-effort.
>
> If anything fails, capture the trace, log HIGH severity in TECH-DEBT-REGISTRY, and stop — Phase 9 cannot start until 8.3/8.4 are green.

---

## Other artifacts to know about

- **`HANDOFF-PHASE-8-START.md`** is now superseded by this file. Leave in place as audit trail.
- **`PHASE-8-PARITY-AUDIT.md`** (new this session) — coverage matrix; reference when deciding GAP fixes.
- **`PHASE-8-PERF-PLAYBOOK.md`** (new this session) — load-bearing for tomorrow's §8.4.
- **`PHASE-8-RESILIENCE-PLAYBOOK.md`** — does not yet exist; first thing tomorrow.
- **`TECH-DEBT-REGISTRY.md`** — 4 new GAP rows; close them as you fix or defer them.
- **`11-redesign-execution-plan.md`** — Phase 8 §8.1–8.5 and Phase 9 are described there at the same level of detail as 4–7. Use as the spec when interpreting playbook results.
