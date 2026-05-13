# Handoff — Post-PDF-push (2026-05-13)

> Generated mid-session. The PDF walkthrough push wrapped today. This handoff captures **everything that landed alongside the PDF work but is independent of it** — backend wiring for two Pending settings pages, a chart-stability fix, a perf diagnosis with a proposed mitigation, and remaining backlog. The PDF itself is tracked separately (`docs/PRAXIS-UI-WALKTHROUGH-REDESIGN.md` is the source; the rendered PDF lives at `docs/PRAXIS-UI-WALKTHROUGH-REDESIGN.pdf`).

This supersedes the relevant rows in `HANDOFF-POST-CUTOVER.md` (Risk defaults + Sessions are now wired, not Pending). Carry-forward items from that earlier handoff are restated below in §6.

---

## 1. What landed in this push

### 1.1 `/settings/risk` — user-level risk defaults (MVP)

**Status:** wired end-to-end. Defaults persist; apply to *newly created* profiles. Recompile fan-out to running profiles is **deferred** and documented inline.

| Layer | File | Change |
|---|---|---|
| Migration | `migrations/versions/021_user_risk_defaults.sql` | New `user_risk_defaults` table, JSONB store keyed on `user_id` |
| Schemas | `libs/core/schemas.py` | `UserRiskDefaultsPayload`, `UserRiskDefaultsResponse`, `DEFAULT_USER_RISK_DEFAULTS` |
| Repo | `libs/storage/repositories/user_risk_defaults_repo.py` (new) | `get` / `upsert` |
| Route | `services/api_gateway/src/routes/risk_defaults.py` (new) | `GET/PUT /risk-defaults` |
| Wiring | `services/api_gateway/src/main.py` | Registered under `/risk-defaults` with `verify_token_dep` |
| FE client | `frontend/lib/api/client.ts` | `api.riskDefaults.get/save` |
| FE page | `frontend/app/settings/risk/page.tsx` | Rewritten: 5 numeric inputs (max position size, max leverage, max daily loss, rate limit, auto-pause drawdown), sticky save bar, dirty-state banner, last-saved timestamp, honest inline note about new-profiles-only scope |

**Five caps validated** (`UserRiskDefaultsPayload`):

| Field | Bounds | Unit |
|---|---|---|
| `max_position_size_pct` | 0.0 – 1.0 | fraction of free capital × confidence |
| `max_leverage` | 1.0 – 20.0 | × notional / margin |
| `max_daily_loss_pct` | 0.0 – 1.0 | halt-for-day threshold |
| `rate_limit_orders_per_min` | 1 – 600 | orders / minute |
| `auto_pause_drawdown_pct` | 0.0 – 1.0 | drawdown trip |

**Deferred work — its own backlog item:** the recompile fan-out. When the user saves defaults, only *new* profiles created after that save inherit them. Existing profiles are untouched. A real fan-out mechanism needs:

1. A list-of-active-profiles query
2. A recompile step that re-evaluates each profile's `risk_limits` against the new defaults (only overriding fields the user hasn't explicitly set on the profile)
3. Optimistic concurrency / conflict resolution if the user is editing a profile while the fan-out is in flight
4. Notification to running services that profile rules changed

Scope this as a separate session. Should NOT be bundled into the next thing you do unless explicitly prioritized.

### 1.2 `/settings/sessions` — real session list + revoke (MVP)

**Status:** wired end-to-end. Real cross-device session list, individual revoke. API tokens + webhooks still Pending — each is its own project.

| Layer | File | Change |
|---|---|---|
| Migration | `migrations/versions/022_user_sessions.sql` | New `user_sessions` table keyed by `jti`, with `revoked_at` flag, INET column for IP, active-sessions index |
| Repo | `libs/storage/repositories/user_session_repo.py` (new) | `create`, `get_by_jti`, `rotate_jti`, `list_active`, `revoke`, coarse `parse_ua` helper |
| Middleware | `services/api_gateway/src/middleware/auth.py` | `create_refresh_token` now returns `(token, jti)` and always carries a `jti` claim; `verify_jwt` propagates `session_id` claim to `request.state.session_id` |
| Route | `services/api_gateway/src/routes/auth.py` | `/auth/callback` inserts session row with parsed UA/device/IP; `/auth/refresh` validates session via DB (rejects revoked) and rotates the jti; new `GET /auth/sessions` and `POST /auth/sessions/{id}/revoke` |
| Deps | `services/api_gateway/src/deps.py` | `get_user_session_repo`, `get_current_session_id` |
| FE client | `frontend/lib/api/client.ts` | `api.sessions.list/revoke` |
| FE page | `frontend/app/settings/sessions/page.tsx` | Rewritten: live device list, "This session" pill driven by access-token claim, individual revoke per row, signOut() called when revoking the current session |

**Security model:**
- DB is the source of truth for session liveness (not Redis)
- `/auth/refresh` checks `user_sessions.revoked_at` before issuing new tokens; revoked → 401 → user forced back to `/login`
- jti rotates on every `/auth/refresh` (defense in depth alongside the existing Redis revoked-token denylist)
- The legacy code path (refresh tokens minted before migration 022) is honored: tokens without a `jti` claim skip the session check and expire naturally within the 7-day window. Backwards-compatible rollout.
- Session revocation is scoped to the requesting user — one user cannot revoke another's session

**Verified via smoke test:** JWT round-trips carry `jti` and `session_id` claims correctly; api_gateway composes; all three new routes (`/risk-defaults`, `/auth/sessions`, `/auth/sessions/{id}/revoke`) register with the verify-token middleware.

**Deferred work:**
- **API tokens** — needs hashed storage, scoped permissions, one-time secret display. Real auth project, days of work. Builds on the session-revocation pattern that landed today.
- **Webhook destinations** — pairs with the notification matrix (which is also still Pending). They land together.

### 1.3 `frontend/components/trading/PriceChart.tsx` — `update()` monotonic-skip fix

**Problem reported:** browser console threw `Cannot update oldest data, last time=[object Object], new time=[object Object]` at `PriceChart.useEffect` (line 266). The error fired repeatedly after page load.

**Root cause:** the append-only data path called `candle.update()` on the second-to-last bar of the `candles` array. lightweight-charts requires `update()` to be monotonic in time — passing a bar whose `time` is strictly less than the series' last applied time throws. When the effect re-fired with identical or near-identical `candles` (Strict-mode double-mount, HMR, a parent re-creating the array reference, or a late refetch landing after a newer one), the `isAppendOnly` invariant held but the tail's first bar was older than what the chart had already absorbed.

**Fix:** added a guard in the tail loop that skips bars whose time is strictly less than `lastTimeRef.current`. One-block change. Doesn't affect happy-path streaming.

```tsx
for (const bar of tail) {
  if (last !== null && bar.time < last) continue;
  candle.update(toCandleDatum(bar));
  ...
}
```

This stops the throw without changing chart behavior on real streaming updates. The `[object Object]` in the error message was lightweight-charts stringifying its internal time records, not a sign of bad input shape.

### 1.4 Perf diagnosis — `/hot/BTC-USDT` cold-load LCP 3.1 s, render delay 2.9 s

**Trace via Chrome DevTools MCP (2026-05-13):**

| Metric | Value | Read |
|---|---|---|
| LCP | 3,101 ms | Slow (target ≤ 2,500 ms) |
| TTFB | 174 ms | Backend fast |
| Render delay | 2,927 ms | Where the time goes |
| Total forced reflow | 185 ms | Concentrated in PriceChart |

**Top reflow culprit: `PriceChart.useEffect.resize` — 176 ms of forced layout.** The `ResizeObserver` in the chart's constructor effect calls a `resize` that reads `container.clientHeight` / `clientWidth` (forces layout) and then calls `chart.applyOptions({width, height})` (mutates DOM). ResizeObserver fires multiple times during mount layout-settle; each fire does another read-then-write → layout thrash.

**Proposed fix (NOT yet applied — defer to next session):** RAF-coalesce the resize callback so ResizeObserver storms collapse to one resize call per frame.

```ts
let rafId: number | null = null;
const scheduleResize = () => {
  if (rafId !== null) return;
  rafId = requestAnimationFrame(() => {
    rafId = null;
    resize();
  });
};
resize();
const ro = new ResizeObserver(scheduleResize);
ro.observe(container);

return () => {
  ro.disconnect();
  if (rafId !== null) cancelAnimationFrame(rafId);
  ...
};
```

Estimated savings: ~100–150 ms off LCP, eliminates the chart-driven reflow loop. Safe, narrow change. ~10 lines.

**What the trace does NOT explain:** sustained input lag during normal interaction (hover/click → page response in ~1 s). That's a different problem from cold-load LCP — the trace captured initial paint, not interaction. The likely culprit for sustained lag is the SSE telemetry stream flooding `agentViewStore.globalFeed`, which `/hot/BTC-USDT` subscribes to via the whole-array selector. Every event re-renders the whole subtree. Mitigation:

- **Quick fix already applied to the MCP-driven browser** — `localStorage['praxis:slow-mode'] = {enabled:true, rateMs:1000}` enables the existing `useSlowMode` hook which batches events. Users with hover lag in dev can paste this in their own DevTools console to apply per-tab:
  ```js
  localStorage.setItem('praxis:slow-mode', JSON.stringify({enabled: true, rateMs: 1000})); location.reload();
  ```
- **Proper fix:** narrow the store subscription on `/hot/BTC-USDT` to a selector that returns just the trace list (computed inside the selector with memo). The page should only re-render when the *derived* trace list changes, not on every raw event. ~30 min of refactor + verification. Touches `frontend/app/hot/[symbol]/page.tsx:223` and adjacent.
- **Bigger-hammer:** add `subscribeWithSelector` middleware to the store so consumers can subscribe to specific paths without renders firing on unrelated mutations.

**Also worth knowing:** ~2.7 s of the render delay is dev-mode React 19 + Turbopack compile-on-demand. A `npm run build && npm run start` will likely cut LCP roughly in half without any code change. Always validate perf on prod build before chasing dev-mode numbers.

---

## 2. Files touched this push (full list)

```
M frontend/app/settings/risk/page.tsx           # rewritten — risk MVP
M frontend/app/settings/sessions/page.tsx       # rewritten — sessions MVP
M frontend/lib/api/client.ts                    # api.riskDefaults, api.sessions
M frontend/components/trading/PriceChart.tsx    # monotonic-skip fix
M libs/core/schemas.py                          # UserRiskDefaultsPayload + Response
M libs/storage/repositories/__init__.py         # export new repos
M services/api_gateway/src/deps.py              # session repo dep + current_session_id
M services/api_gateway/src/main.py              # register /risk-defaults
M services/api_gateway/src/middleware/auth.py   # jti + session_id claims
M services/api_gateway/src/routes/auth.py       # /auth/sessions endpoints, session create/rotate

?? migrations/versions/021_user_risk_defaults.sql
?? migrations/versions/022_user_sessions.sql
?? libs/storage/repositories/user_risk_defaults_repo.py
?? libs/storage/repositories/user_session_repo.py
?? services/api_gateway/src/routes/risk_defaults.py

?? docs/PRAXIS-UI-WALKTHROUGH-REDESIGN.md       # walkthrough source for the PDF (handled separately)
?? docs/design/HANDOFF-POST-PDF-PUSH.md         # this file
```

Plus untracked files that pre-date this push (`docs/PRAXIS-UI-WALKTHROUGH_updated.pdf`, `docs/praxis_ui_walkthrough.md`, `frontend/public/html2canvas.min.js`, `scripts/build_ui_walkthrough_pdf.py`) — leave or commit per existing convention.

**Not yet committed.** Recommend splitting into three commits:

1. `feat(/settings): wire user-level risk defaults (MVP, defers recompile fan-out)`
2. `feat(/settings): wire real session list + revoke (MVP, defers API tokens + webhooks)`
3. `fix(/hot): PriceChart monotonic-skip in append-only update path`

The walkthrough MD + PDF can be a fourth commit (`docs: add redesign UI walkthrough`).

---

## 3. Migration ordering

Both new migrations are `CREATE TABLE IF NOT EXISTS`, so safe to re-run. The `scripts/migrate.py` runner globs `migrations/versions/*.sql` in sorted order and applies each. On next `bash run_all.sh --local-frontend` (or any boot that touches the migrator), 021 and 022 will land.

**Verify after migration runs:**

```sql
SELECT table_name FROM information_schema.tables
 WHERE table_name IN ('user_risk_defaults', 'user_sessions');
```

Both should be present.

---

## 4. Open backlog (deferred work from this push)

| Item | Severity | Effort | Notes |
|---|---|---|---|
| Risk defaults — recompile fan-out | MEDIUM | L | Propagate user-level saves to running profiles; needs concurrent-edit conflict resolution |
| **`/settings/risk` — total-capital field + per-profile $ cascade** | **MEDIUM** | **S–M** | User-requested 2026-05-13. Account-level "total funds available"; each profile's existing `allocation_pct` divides this pool. **Design decided:** add `total_capital_usdc` inside the existing `user_risk_defaults.defaults` JSONB (no new migration), surface as a numeric input at the top of `/settings/risk`, show per-profile $ cascade live as the value changes. **Scope of MVP: store + display only — no enforcement.** Trading engine continues to use `allocation_pct` as-is; the multiply-by-total-capital enforcement in the risk service is a separate, security-sensitive item that follows. |
| Sessions — API tokens | MEDIUM | L | Token issuance, hashed storage, scoped permissions; security-sensitive |
| Sessions — webhook destinations | MEDIUM | M | Pairs with notification matrix |
| PriceChart — RAF-coalesce resize | LOW | S | ~10 lines, ~100–150 ms LCP improvement, narrow risk |
| `/hot/BTC-USDT` — narrow store subscription | MEDIUM | M | Eliminates sustained input lag on dev; ~30 min refactor |

Append to `docs/TECH-DEBT-REGISTRY.md` row 22 if not already tracked there.

---

## 5. Carry-forward from HANDOFF-POST-CUTOVER (Pending settings work)

Three of the five originally-Pending Settings sub-pages remain Pending after this push:

| Surface | Pending area | What's still needed |
|---|---|---|
| `/settings/notifications` | Per-event delivery matrix | Replace coarse booleans with email × push × audible × event-type schema; new `/preferences` endpoint with matrix shape |
| `/settings/tax` | Report generator | Service-side persistence, FIFO/HIFO/LIFO export, year-history. The current `services/tax` is a calculator (`/calculate` only) — needs real reporting infrastructure |
| `/settings/audit` | Per-source emitters | Profile-edit / API-key-rotation / agent-override / failed-sign-in events into the audit aggregator. Today only kill-switch transitions emit (via `praxis:kill_switch:log` Redis list) |

Each is its own backlog project. The FE shells already render with honest Pending tags per ADR-013.

---

## 6. Carry-forward from HANDOFF-POST-CUTOVER (cleanup & registry)

These survived the previous handoff cleanly and remain open:

1. **Remove the `aion-trading-redesign` worktree.**
   ```bash
   cd C:/Users/stevo/DEV/agent_trader_1/aion-trading
   git worktree remove ../aion-trading-redesign
   ```
   The redesign branch ref survives (as ancestor of main); the duplicate working copy can go.

2. **Decide on `frontend/DESIGN-SYSTEM.legacy.md`** — archive to `docs/historical/` or delete outright. No inbound references in the source tree at last check.

3. **Sync surface portfolio with shipped reality.** `docs/design/05-surface-specs/06-profiles-settings.md` §5 (Risk defaults) and §9 (Sessions) should be updated to reflect that the wiring landed today — they currently describe these sections as if the backend were already in place; that's now true for the two MVPs but the §5 recompile fan-out and §9 API-tokens/webhooks remain spec-ahead-of-reality. Per ADR-013, keep the spec ahead of reality is acceptable as long as we tag what's wired vs Pending.

4. **Registry cleanup** — mark Phase 8.1 GAP rows and `frontend (redesign branch)` rows as historical; promote surviving items into clean post-cutover backlog rows.

5. **Branch policy** — delete `redesign/frontend-v2` locally once worktree is removed. The merge commit references the branch forever.

6. **Pre-redesign-cutover tag** — keep until weeks have passed without rollback. Load-bearing.

---

## 7. Live-stack carry-forwards

- `PRAXIS_PAPER_TRADING_MODE` defaults to `false` on main; do not toggle to live without explicit user direction.
- Test profile: `9c94da6c-8d20-42f3-b086-9170e3ba8f2c` (Mean Reversion).
- `PriceChart` canvas is `aria-hidden` intentionally — lightweight-charts doesn't expose a meaningful tree.
- Next.js 16 + Turbopack compile-on-demand: first navigation to any new route in dev is slow (~1–3 s). Production build doesn't have this lag.

---

## 8. Suggested next-session prompt

> Continue on `main`. Read `docs/design/HANDOFF-POST-PDF-PUSH.md` first. Decide what to tackle from the open backlog in §4 and the carry-forward in §5/§6. Recommendation if no specific priority: land the PriceChart RAF-coalesce resize (§1.4 proposed fix — small, narrow, immediate user-visible win) and the `/hot` store-subscription narrowing in the same session. Stop and ask before starting on the larger projects (recompile fan-out, API tokens, tax reporting) — each is its own week+ project.
