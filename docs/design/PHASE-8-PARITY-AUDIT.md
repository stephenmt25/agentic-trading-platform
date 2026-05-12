# Phase 8.1 — Functional parity audit (legacy main → redesign)

> Generated 2026-05-10. Walks every legacy main-branch URL and API namespace and confirms coverage on `redesign/frontend-v2`. Closes the §8.1 gate from `11-redesign-execution-plan.md` modulo the four gaps logged below — those are tracked in `docs/TECH-DEBT-REGISTRY.md` and are Phase 9 cutover blockers.

---

## Method

1. `git ls-tree -r origin/main app | grep page.tsx` enumerates every legacy URL.
2. For each URL, locate the redesign surface that owns the same task (per the IA in `02-information-architecture.md`).
3. `grep "api\.<namespace>\."` across `frontend/app/` confirms every API namespace consumed by the legacy hubs is also consumed by the redesign surfaces.
4. The §8.1 spec checklist (every URL + every API call + auth + profile CRUD + live orders/positions + backtests + kill switch) is verified item by item.

---

## URL coverage matrix

Legacy URLs on `origin/main` and where the redesign covers them.

| Main URL | Legacy task | Redesign route | Status |
|---|---|---|---|
| `/` | Entry redirect → `/trade` | Still redirects to `/trade` | **GAP-1** — root must redirect to `/hot/BTC-USDT` before merge |
| `/trade` | Legacy hub: positions + decisions + daily report + risk + approval + analysis + performance | Decomposed: positions in `/hot/[symbol]`, agent feed in `/agents/observatory`, risk in `/risk`, analytics in `/backtests` | Covered (legacy file retained until Phase 9 deletes) |
| `/agent-view` | Legacy agent observability | `/agents/observatory` | Covered (legacy retained) |
| `/analysis` | Price chart + agent score overlay | Price chart in `/hot/[symbol]`, agent scores in `/agents/observatory` | Covered (legacy retained) |
| `/analyze` | Already redirects to `/trade` on main | Same redirect; will follow `/trade` deletion | Covered |
| `/approval` | HITL approval queue (`api.hitl.respond`) | **No redesign surface integrates HITL** | **GAP-2** — HITL queue must land somewhere (Observatory `?` or new sub-route) before merge |
| `/backtest` (singular) | Legacy single-run backtest | `/backtests` (plural) covers list + run detail + compare | Covered |
| `/docs/*` | Internal docs viewer | Same `/docs/*` route | Covered |
| `/login` | NextAuth login | Same | Covered |
| `/paper-trading` | Status + mode badge (PAPER/TESTNET/LIVE) + manual daily-report generation | `/hot` chrome surfaces PnL via `portfolioStore`; **no mode badge, no daily-report button** | **GAP-3** mode badge, **GAP-4** daily-report generation |
| `/performance` | Performance metrics (agent accuracy, gate analytics, weight evolution) | `/backtests/[run_id]` covers per-run forensics; the standalone agent-accuracy page is legacy-only | Covered for backtest analytics; standalone page is Phase-9-deletable |
| `/pipeline` | Strategy pipeline editor (legacy) | `/canvas/[profile_id]` (redesign) | Covered (legacy retained) |
| `/profiles` | Profile list | Same `/profiles` (still functional) plus `/settings/profiles` | Covered |
| `/settings` | Combined settings page | Decomposed into `/settings/{risk,notifications,tax,sessions,exchange,profiles,audit,account}` | Covered |
| `/strategies` | Strategy/profile management | Effectively `/profiles` + `/canvas/[profile_id]` | Covered (legacy retained) |

---

## API namespace coverage

Every namespace defined in `lib/api/client.ts` and where it's consumed.

| Namespace | Consumers on redesign | Notes |
|---|---|---|
| `api.profiles.*` | `/hot`, `/risk`, `/canvas`, `/backtests`, `/settings/profiles`, `/profiles` | ✓ |
| `api.positions.*` | `/hot`, `/risk` | ✓ |
| `api.orders.*` | `/hot` | ✓ added in 7.3 |
| `api.commands.*` (kill switch) | `/hot`, `/risk`, `RedesignShell` | ✓ |
| `api.marketData.*` | `/hot` (candles), `/backtests` | ✓ |
| `api.agents.*` | `/risk`, `/canvas`, `/backtests`, `/agents/observatory` (via WS) | ✓ |
| `api.agentPerformance.*` | `/backtests`, `/analytics` content components | ✓ |
| `api.agentConfig.*` | `/canvas`, `/settings/profiles` | ✓ |
| `api.exchangeKeys.*` | `/settings/exchange` | ✓ |
| `api.preferences.*` | `/settings/notifications` | ✓ |
| `api.audit.*` | `/settings/audit` | ✓ |
| `api.auth.*` | `/login`, `RedesignShell` | ✓ |
| `api.backtest.*` | `/backtests` | ✓ |
| `api.paperTrading.*` | Partial: status read by `usePortfolioStore` via WS; **`mode()` and `generateReport()` unread** | **GAP-3, GAP-4** |
| `api.hitl.*` | Only legacy `/approval` | **GAP-2** |

---

## §8.1 checklist

- [x] Every URL on main renders something on redesign (or has a documented intentional removal). Four gaps below.
- [x] Every API call from main is also made from the redesign — three exceptions: `api.paperTrading.mode`, `api.paperTrading.generateReport`, `api.hitl.respond`. All are tracked.
- [x] Authentication / sessions work — `/login` retained; `RedesignShell` reads session JWT via `apiClient`.
- [x] Profile create/edit/delete works — `/settings/profiles/[id]`, `/profiles`, `/canvas/[profile_id]` all hit `api.profiles.*`.
- [x] Live orders, fills, positions visible — `/hot` Open Orders + Positions tabs (Fills tab is Pending; tracked).
- [x] Backtests dispatch and complete — `/backtests` page + `/backtests/[run_id]` detail.
- [x] Kill switch arms and disarms — `/risk` arming UX, global `Cmd+Shift+K` modal, chrome pill.

---

## Gaps (logged in TECH-DEBT-REGISTRY)

| ID | Gap | Severity | Phase 9 blocker? |
|---|---|---|---|
| GAP-1 | `app/page.tsx` redirects to `/trade` (legacy) | HIGH | YES — change to `/hot/BTC-USDT` before merge |
| GAP-2 | HITL approval queue not surfaced on any redesign surface | MEDIUM | YES — either land an Observatory integration or restore `/approval` under redesign chrome |
| GAP-3 | Trading-mode badge (PAPER/TESTNET/LIVE) absent from redesign chrome | MEDIUM | YES — small chrome pill; reuses `api.paperTrading.mode()` |
| GAP-4 | Daily-report manual-generation button absent | LOW | NO — mark as deferred or move to `/backtests` |

Phase 9 cutover should not happen until GAP-1, GAP-2, and GAP-3 are closed (or formally accepted as feature regressions in `09-decisions-log.md`). GAP-4 is small enough to defer.

---

## What this audit didn't cover

- **Behavioral parity** beyond surface presence — e.g., does `/hot` truly produce identical fills to `/paper-trading`'s legacy submission flow? That requires the §8.3 resilience runs and a full integration test on the local stack.
- **Visual diff** — the surfaces are intentionally redesigned; visual parity isn't a goal.
- **Performance parity** — covered by §8.4.
