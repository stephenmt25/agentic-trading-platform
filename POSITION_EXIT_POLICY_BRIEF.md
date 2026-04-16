# Position Exit Policy — Decision Brief

**Audience:** decision-making agent tasked with choosing an exit policy for the Praxis Trading Platform.
**Date:** 2026-04-13
**Scope:** determine how open positions should close (stop-loss, take-profit, time-based, signal-based). A blocking bug was just fixed; a design gap remains.

---

## 1 · Executive summary

Praxis is a 19-microservice paper-trading platform. As of 2026-04-13, **3,221 positions are open across 2 symbols (BTC/USDT, ETH/USDT) and zero have ever closed**. Positions have accumulated since 2026-04-08.

Two problems drove this:

1. **Fixed (2026-04-13):** the `pnl` service only hydrated its position cache at startup, so positions opened mid-session were invisible to the stop-loss monitor. The cache now re-hydrates every 30s from the DB — stop-loss enforcement is live on all open positions.

2. **Open design question:** even with monitoring restored, the system has **only one exit mechanism: stop-loss triggering at loss ≥ 5%**. There is no take-profit, no time-based exit, and no signal-reversal close. With 5% losses rarely occurring at current volatility, almost nothing closes. Cumulative PnL is ≈ −$75k across 4 days (+$98k, +$69k, 0, −$243k).

The agent must decide: **what additional exit policies should the system enforce, and with what parameters?**

---

## 2 · System context (minimum viable)

### 2.1 · What Praxis is

- 19 Python microservices, FastAPI + asyncio, Redis Streams/Pub-Sub, TimescaleDB.
- Frontend: Next.js on Vercel.
- Currently in **paper trading mode** (no real money). Exchange adapter is `PAPER` (simulated fills).
- Two symbols active: BTC/USDT, ETH/USDT.
- Cryptocurrency trading, driven by ML agents (TA, sentiment, regime HMM, debate) feeding a decision pipeline.

### 2.2 · Relevant pipeline

```
ingestion (market data) ──► hot_path (signals) ──► strategy ──► validation ──► execution ──► positions table
                                                                                                   │
                                                                           pnl ◄─ pubsub:price_ticks
                                                                            │
                                                                            ├─► publishes PnL updates
                                                                            └─► stop-loss enforcement (close_position)
```

### 2.3 · Services that matter for this decision

| Service | Role in exit logic | Port |
|---|---|---|
| `pnl` | Monitors open positions on every price tick. Owns `StopLossMonitor` and `PositionCloser`. | 8084 |
| `execution` | Opens positions. Does **not** own exit logic. | 8083 |
| `risk` | Pre-trade risk limits. Does **not** close positions. | 8093 |
| `strategy` | Produces buy/sell signals. Currently has no "flip" or "exit" output. | worker |

### 2.4 · Schema highlights

**`positions` table** (`migrations/versions/001_initial_schema.sql`):
- `position_id`, `profile_id`, `symbol`, `side`, `entry_price`, `quantity`, `entry_fee`, `opened_at`, `status` (OPEN/CLOSED), `closed_at`, `exit_price`.

**`RiskLimitsPayload`** (`libs/core/schemas.py:464`):
```python
class RiskLimitsPayload(BaseModel):
    max_allocation_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = 0.05          # ← only exit threshold that exists
    max_drawdown_pct: Optional[float] = None
    circuit_breaker_daily_loss_pct: Optional[float] = None
```

Only `stop_loss_pct` is enforced on open positions. `max_drawdown_pct` and `circuit_breaker_daily_loss_pct` are portfolio-level, not per-position.

---

## 3 · What the `pnl` service does today

On every price tick (`pubsub:price_ticks`), for each open position on that symbol:

1. Compute gross PnL, net PnL pre-tax, unrealized return percentage.
2. Publish a PnL update event.
3. Call `StopLossMonitor.check()`:
   - If `pct_return >= 0` → return (no action on winners).
   - If `abs(pct_return) < stop_loss_pct` → return.
   - Else → call `PositionCloser.close()` which updates the DB (`status='CLOSED'`, `exit_price`), writes realized PnL, and tags agent-score outcomes for weight feedback.

**Relevant files:**
- `services/pnl/src/main.py` — tick handler, cache, `hydrate_positions`, `rehydrate_loop` (new, 30s).
- `services/pnl/src/stop_loss_monitor.py` — threshold check.
- `services/pnl/src/closer.py` — DB close + agent feedback.
- `services/pnl/src/calculator.py` — PnL math.

---

## 4 · Current state of open positions

Queried 2026-04-13 ~13:15 UTC:

| Symbol | Side | Count | Avg entry | Total qty |
|---|---|---:|---:|---:|
| BTC/USDT | BUY | 2,391+ | ~$72,123 | ~160.3 |
| ETH/USDT | BUY | 721+ | ~$2,222 | ~47.4 |
| **Total** | | **3,221** | | |

Current prices roughly BTC ~$70,869, ETH ~$2,200. Typical unrealized return per position is between **−2% and 0%** — below the 5% stop-loss threshold, above zero return. So nothing trips current logic.

### 4.1 · Daily performance (from `paper_trading_reports`)

| Date | Trades | Win Rate | Net PnL | Sharpe | Approval % |
|------|-------:|---------:|--------:|-------:|-----------:|
| 04-10 | 1,560 | 99% | +$98,927 | 2.57 | 6.6% |
| 04-11 | 298 | 58% | +$68,762 | 0.22 | 2.1% |
| 04-12 | 0 | — | $0 | — | 0.0% |
| 04-13 (partial) | 191 | 0% | −$243,041 | −2.79 | 62.8% |

**Note:** these PnL figures are **unrealized** — based on mark-to-market against `pnl_snapshots`, since no positions ever closed. The 0% win rate on 04-13 reflects snapshots, not realized trades.

### 4.2 · Approval / abstention pattern

Abstention gate (in the hot-path decision pipeline) dominates: typically 90–100% of decisions are `BLOCKED_ABSTENTION`. But on 04-13, approval jumped to 62.8% — ≈10× the usual rate — and that spike is what drove the -$243k daily mark. Something changed in the gate's thresholds or regime classification. *Relevant to exit policy only insofar as entry cadence affects how fast positions accumulate.*

---

## 5 · The design question

**What exit policies should the system enforce, and with what parameters?**

The current single-policy model (stop-loss at 5% loss) is insufficient because:

- **Winners never close.** If BTC rallies 10%, all 2,391 BTC positions stay open and the gain stays unrealized.
- **Stale positions never time out.** Holding 3,000+ simultaneously-open positions is not a realistic trading profile — it reflects a bug, not intent.
- **Opposite signals don't close positions.** If strategy flips from BUY to SELL, existing BUYs remain open.
- **The stop-loss itself is loose** relative to realized intraday volatility (<1% typical).

### 5.1 · Candidate exit policies

| Policy | Trigger | Pros | Cons |
|---|---|---|---|
| **A. Take-profit** | `pct_return ≥ take_profit_pct` | Locks in gains; symmetric with stop-loss; simple | Caps upside; picking a threshold is hard (3%? 5%? 10%?) |
| **B. Time-based exit** | `now - opened_at > max_holding_duration` | Prevents accumulation; forces turnover | May close still-valid theses; arbitrary timeout |
| **C. Trailing stop** | `pct_return drops from peak by X%` | Captures most of the upside while still stopping out | More complex state (per-position peak); larger DB writes |
| **D. Opposite-signal close** | Strategy emits SELL for symbol with open BUY | Most "trader-like"; ties exit to same logic as entry | Needs a new event channel; strategy must produce exit signals; risk of thrashing |
| **E. Tighten stop-loss** | Reduce `stop_loss_pct` from 5% to e.g. 1–2% | One-config change; makes existing mechanism effective | More whipsaws; may still not close winners |
| **F. Portfolio-level circuit** | Close all positions if daily loss > threshold | Defends downside | Blunt; operational, not strategic |

### 5.2 · Likely sensible combination

Most crypto paper-trading systems combine **(A) + (B) + (E)**: a take-profit, a time cap, and a tighter stop. **(D)** is the most principled but requires `strategy` to emit exit signals, which is a larger change. **(C)** is the highest-quality single policy but needs per-position peak tracking.

### 5.3 · Parameters the agent must also decide

- `take_profit_pct`: start with ? (common defaults: 2%, 3%, 5%)
- `max_holding_duration`: hours? days? Align with strategy horizon (unknown — agent should infer from `strategy` service or ask).
- `stop_loss_pct`: keep at 5% or tighten?
- Scope of application: global default, per-symbol, or per-profile (`profile.risk_limits`)?
- Should winners use fee-aware threshold (`net_pre_tax > 0` vs `gross_pnl > 0`)?

---

## 6 · Constraints & conventions the agent must respect

These are enforced across the codebase (from `CLAUDE.md`):

1. **All financial values use `Decimal`.** Never `float`. Types in `libs/core/types.py`.
2. **Enums live in `libs/core/enums.py`**, schemas in `libs/core/schemas.py`. Don't invent either.
3. **Redis channels are defined in `libs/messaging/channels.py`.** No inventing channel names.
4. **Stay in Phase 1 (Core Trading Engine).** Don't pull in Phase 2 (ML / multi-agent) patterns.
5. **Kill switch exists** (`KillSwitch` Redis key) and should be honored by any exit logic.
6. **Per-service pattern:** `services/<name>/src/main.py` with FastAPI + uvicorn lifespan.
7. **Preserve existing patterns.** Extend `StopLossMonitor` or create a sibling `ExitMonitor` — don't restructure the pipeline.

---

## 7 · Observability & data sources the agent can use

| Source | Query / file | Use |
|---|---|---|
| `paper_trading_reports` | `SELECT * FROM paper_trading_reports ORDER BY report_date;` | Daily aggregate PnL |
| `pnl_snapshots` | per-tick unrealized PnL | Distribution of `pct_return` to pick thresholds |
| `positions` | all opens / closes | Holding-duration histogram, closure reasons |
| `trade_decisions` | per-decision audit | Approval rate, abstention gate behavior |
| `orders` | all orders with status | Execution audit |
| `.praxis_logs/pnl.log` | | `position_cache_rehydrated` every 30s (verification) |
| `.praxis_logs/*.log` | | Per-service health |

Recommended empirical step before picking parameters: **compute the distribution of `pct_return` across `pnl_snapshots` to see what thresholds actually correspond to meaningful moves.** Example:

```sql
SELECT
  width_bucket(pct_return, -0.1, 0.1, 20) AS bucket,
  COUNT(*)
FROM pnl_snapshots
GROUP BY bucket ORDER BY bucket;
```

---

## 8 · What was just fixed, and what it leaves untouched

**Fixed in `services/pnl/src/main.py`:**
- Added `rehydrate_loop(position_repo, interval_s=30.0)` running as an asyncio task alongside the tick listener.
- `hydrate_positions` now does an atomic cache swap (build new dict, clear, update) so in-flight ticks aren't disrupted.
- Emits `position_cache_rehydrated` log line every 30s with `{symbols, positions, delta}` for audit. Verified firing in production as of 2026-04-13 11:13 UTC.

**Not touched:**
- `StopLossMonitor` logic (still only fires on loss ≥ `stop_loss_pct`).
- `RiskLimitsPayload` schema (no `take_profit_pct`, no `max_holding_duration`).
- Strategy service (no exit signals produced).
- The 3,221 positions currently open — they won't close unless market drops ≥5% OR the agent's new policy is implemented and applied to them.

---

## 9 · Known related issues (context, not blockers)

- **`validation_events` table is empty** despite `trade_decisions` recording `BLOCKED_VALIDATION` events. Validation service appears idle (0-byte log); validation is happening inline somewhere else. Observability gap; not a trading blocker.
- **`api_gateway` emits ~3,300 Pydantic warnings** per session: `daily_pnl_pct` and `drawdown_pct` declared `float` but serialized `Decimal`. Response data is correct; warnings are noise.
- **WebSocket pubsub gzip decode bug**: consumer hits `0x8b` (gzip magic) on every Redis pubsub message and reconnect-loops. Publisher is compressing payloads a consumer expects as UTF-8.
- **Abstention-gate regime shift on 04-13** (see §4.2) — separate investigation.

---

## 10 · Suggested decision output

The agent should return, in order:

1. **Chosen policy set** (one or more of A–F, with rationale).
2. **Parameters** (`stop_loss_pct`, `take_profit_pct`, `max_holding_hours`, etc.) with justification tied to observed data (§7).
3. **Scope**: global, per-symbol, or per-profile.
4. **Handling of the 3,221 already-open positions**: apply the new policy immediately, grandfather them, or force-close with a specific exit price.
5. **Implementation sketch**: which service(s) and file(s) change, and which new schema fields (if any) need a migration.
6. **Rollback plan**: if the new policy causes excessive closures in the first N hours, how do we revert?

---

*End of brief. All figures and file paths verified against live state at 2026-04-13 13:15 UTC.*
