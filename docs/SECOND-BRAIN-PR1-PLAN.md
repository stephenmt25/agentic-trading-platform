# 2nd Brain — PR1: The Ledger

> **Status:** Plan, awaiting approval. No code changes yet.
> **Goal:** Make every trade fully reconstructable end-to-end: from the strategy intent that generated it, through the gates and agent scores at decision time, through execution, all the way to the close reason and final PnL — with the full debate transcript that informed the call.
> **Behavior change:** **None.** This PR is pure observability. No gate logic, sizing, or order flow changes.

---

## 0 · Why this is the foundation

Today, the audit shows three persistence layers (`trade_decisions`, `agent_score_history`, `agent_weight_history`) that almost capture what we need — but the **chain is broken in two places**:

1. **`trade_decisions.order_id` stores the wrong UUID.** In `services/hot_path/src/processor.py:359`, we write `order_ev.event_id` (the OrderApprovedEvent's auto-generated event UUID). But `services/execution/src/executor.py:158` generates a brand-new `order_id = uuid.uuid4()` for the actual order. The two never connect. So even if you have a `trade_decisions` row, you cannot SQL-join it to the order that resulted, the position that opened, or the PnL that closed.

2. **No `closed_trades` row exists.** When `services/pnl/src/closer.py` closes a position, it updates `positions.exit_price` and `positions.closed_at` (position_repo.py:32-38) and writes a `pnl_snapshot`. But nothing records: *which decision opened this? what was the close reason? which agent scores at entry → which PnL at exit?* `closer.py:51` writes to a Redis EWMA tracker, but that's a moving aggregate — not a per-trade audit row.

3. **Debate transcripts are summarized, not persisted.** `services/debate/src/main.py:108-115` writes a one-row summary per cycle. The actual `result.rounds` (a list of bull/bear arguments with conviction scores, defined in `engine.py:26-42`) is computed and discarded. We can never replay a debate.

PR1 fixes all three. After PR1, this query becomes possible (and is the foundational query for everything else):

```sql
SELECT
    td.event_id,
    td.symbol,
    td.outcome,
    td.regime,
    td.agents,
    o.order_id,
    p.position_id,
    p.entry_price,
    ct.exit_price,
    ct.close_reason,
    ct.realized_pnl_pct,
    ct.holding_duration_s
FROM trade_decisions td
JOIN orders o ON o.decision_event_id = td.event_id
JOIN positions p ON p.order_id = o.order_id
JOIN closed_trades ct ON ct.position_id = p.position_id
WHERE td.symbol = 'BTC/USDT'
  AND td.created_at > NOW() - INTERVAL '7 days';
```

If that query works at the end of PR1, we are done.

---

## 1 · Migrations

Three additive migrations. **No existing column types or constraints change.** All new columns are nullable so existing rows remain valid.

### `migrations/versions/014_intent_correlation.sql`

Adds `decision_event_id` columns linking `orders` and `positions` back to `trade_decisions.event_id`. Indexed for join performance.

```sql
-- Migration 014: Intent → Order → Position correlation chain
-- Allows joining trade_decisions to the resulting order and position.
-- Existing rows have NULL (unknown decision); new rows populate forward.

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS decision_event_id UUID;

CREATE INDEX IF NOT EXISTS idx_orders_decision_event
    ON orders (decision_event_id)
    WHERE decision_event_id IS NOT NULL;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS order_id UUID;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS decision_event_id UUID;

CREATE INDEX IF NOT EXISTS idx_positions_order_id
    ON positions (order_id)
    WHERE order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_positions_decision_event
    ON positions (decision_event_id)
    WHERE decision_event_id IS NOT NULL;
```

> **Note:** No FK constraint to `trade_decisions` because that table is a TimescaleDB hypertable partitioned on `created_at`, and FKs to hypertables require composite refs. We enforce the link in code, not at the schema level. Indexes still work.

### `migrations/versions/015_closed_trades.sql`

The outcome-mapping table. One row per closed position. This is the table the nightly Optimization Agent (PR2) will read.

```sql
-- Migration 015: Closed Trades — outcome mapping
-- One row per closed position. Links the entire decision lineage to the realized PnL.

CREATE TABLE IF NOT EXISTS closed_trades (
    position_id          UUID PRIMARY KEY REFERENCES positions(position_id) ON DELETE RESTRICT,
    profile_id           UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE RESTRICT,
    symbol               TEXT NOT NULL,
    side                 TEXT NOT NULL,                 -- BUY / SELL
    decision_event_id    UUID,                          -- → trade_decisions.event_id
    order_id             UUID,                          -- → orders.order_id

    -- Entry context (snapshot at fill time)
    entry_price          DECIMAL(20,8) NOT NULL,
    entry_quantity       DECIMAL(20,8) NOT NULL,
    entry_fee            DECIMAL(20,8) NOT NULL,
    entry_regime         TEXT,                          -- e.g. 'TRENDING_UP', 'RANGING'
    entry_agent_scores   JSONB,                         -- {ta: 0.7, sentiment: 0.3, debate: 0.55}

    -- Exit context
    exit_price           DECIMAL(20,8) NOT NULL,
    exit_fee             DECIMAL(20,8) NOT NULL,
    close_reason         TEXT NOT NULL,                 -- 'stop_loss' / 'take_profit' / 'time_exit' / 'manual' / 'opposing_signal'
    opened_at            TIMESTAMPTZ NOT NULL,
    closed_at            TIMESTAMPTZ NOT NULL,
    holding_duration_s   INTEGER NOT NULL,

    -- Realized PnL
    realized_pnl         DECIMAL(20,8) NOT NULL,        -- net of fees
    realized_pnl_pct     DECIMAL(10,6) NOT NULL,        -- net % return
    outcome              TEXT NOT NULL,                 -- 'win' / 'loss' / 'breakeven'

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_closed_trades_symbol_closed_at
    ON closed_trades (symbol, closed_at DESC);
CREATE INDEX IF NOT EXISTS idx_closed_trades_profile_closed_at
    ON closed_trades (profile_id, closed_at DESC);
CREATE INDEX IF NOT EXISTS idx_closed_trades_decision_event
    ON closed_trades (decision_event_id) WHERE decision_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_closed_trades_outcome_close_reason
    ON closed_trades (outcome, close_reason);
```

### `migrations/versions/016_debate_transcripts.sql`

Full-fidelity debate persistence. One row per round (bull arg + bear arg + convictions), grouped by `cycle_id`.

```sql
-- Migration 016: Debate Transcripts
-- Full conversational trace of each debate cycle (currently summarized to a string in agent_score_history).

CREATE TABLE IF NOT EXISTS debate_transcripts (
    cycle_id           UUID NOT NULL,                   -- one cycle = one full debate (N rounds + judge)
    symbol             TEXT NOT NULL,
    round_num          INTEGER NOT NULL,                -- 1..N
    bull_argument      TEXT NOT NULL,
    bull_conviction    NUMERIC(10,6) NOT NULL,
    bear_argument      TEXT NOT NULL,
    bear_conviction    NUMERIC(10,6) NOT NULL,
    recorded_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cycle_id, round_num)
);

CREATE TABLE IF NOT EXISTS debate_cycles (
    cycle_id           UUID PRIMARY KEY,
    symbol             TEXT NOT NULL,
    final_score        NUMERIC(10,6) NOT NULL,          -- judge score, -1..1
    final_confidence   NUMERIC(10,6) NOT NULL,          -- judge confidence, 0..1
    judge_reasoning    TEXT,
    num_rounds         INTEGER NOT NULL,
    total_latency_ms   NUMERIC(10,2) NOT NULL,
    market_context     JSONB NOT NULL,                  -- {price, rsi, macd, regime, ta_score, sentiment_score}
    recorded_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_debate_cycles_symbol_recorded
    ON debate_cycles (symbol, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_debate_transcripts_symbol
    ON debate_transcripts (symbol, recorded_at DESC);
```

> Why two tables: `debate_cycles` is the cycle-level summary (one row per debate); `debate_transcripts` is the per-round detail (N rows). This shape supports both "show me all debates" and "show me the rounds for cycle X" without bloat.

---

## 2 · New repositories

Two new repositories under `libs/storage/repositories/`. Both follow the existing pattern (subclass `BaseRepository`, async methods, `_execute` / `_fetch`).

### `libs/storage/repositories/closed_trade_repo.py` (new)

```python
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
import json
from ._repository_base import BaseRepository


class ClosedTradeRepository(BaseRepository):
    async def write_closed_trade(
        self,
        position_id: UUID,
        profile_id: UUID,
        symbol: str,
        side: str,
        decision_event_id: Optional[UUID],
        order_id: Optional[UUID],
        entry_price: Decimal,
        entry_quantity: Decimal,
        entry_fee: Decimal,
        entry_regime: Optional[str],
        entry_agent_scores: Optional[dict],
        exit_price: Decimal,
        exit_fee: Decimal,
        close_reason: str,
        opened_at: datetime,
        closed_at: datetime,
        holding_duration_s: int,
        realized_pnl: Decimal,
        realized_pnl_pct: Decimal,
        outcome: str,
    ) -> None:
        query = """
        INSERT INTO closed_trades (
            position_id, profile_id, symbol, side, decision_event_id, order_id,
            entry_price, entry_quantity, entry_fee, entry_regime, entry_agent_scores,
            exit_price, exit_fee, close_reason, opened_at, closed_at, holding_duration_s,
            realized_pnl, realized_pnl_pct, outcome
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
        ON CONFLICT (position_id) DO NOTHING
        """
        await self._execute(
            query,
            position_id, profile_id, symbol, side, decision_event_id, order_id,
            entry_price, entry_quantity, entry_fee, entry_regime,
            json.dumps(entry_agent_scores) if entry_agent_scores else None,
            exit_price, exit_fee, close_reason, opened_at, closed_at, holding_duration_s,
            realized_pnl, realized_pnl_pct, outcome,
        )

    async def get_recent(self, symbol: Optional[str], limit: int = 100) -> List[Dict[str, Any]]:
        if symbol:
            q = "SELECT * FROM closed_trades WHERE symbol = $1 ORDER BY closed_at DESC LIMIT $2"
            rows = await self._fetch(q, symbol, limit)
        else:
            q = "SELECT * FROM closed_trades ORDER BY closed_at DESC LIMIT $1"
            rows = await self._fetch(q, limit)
        return [dict(r) for r in rows]
```

### `libs/storage/repositories/debate_repo.py` (new)

```python
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
from ._repository_base import BaseRepository


class DebateRepository(BaseRepository):
    async def write_cycle(
        self,
        cycle_id: UUID,
        symbol: str,
        final_score: Decimal,
        final_confidence: Decimal,
        judge_reasoning: str,
        num_rounds: int,
        total_latency_ms: float,
        market_context: dict,
        rounds: List[dict],   # each: {round_num, bull_argument, bull_conviction, bear_argument, bear_conviction}
    ) -> None:
        cycle_q = """
        INSERT INTO debate_cycles
            (cycle_id, symbol, final_score, final_confidence, judge_reasoning,
             num_rounds, total_latency_ms, market_context)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """
        await self._execute(
            cycle_q, cycle_id, symbol, final_score, final_confidence,
            judge_reasoning, num_rounds, Decimal(str(total_latency_ms)),
            json.dumps(market_context),
        )

        if rounds:
            round_q = """
            INSERT INTO debate_transcripts
                (cycle_id, symbol, round_num, bull_argument, bull_conviction,
                 bear_argument, bear_conviction)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            """
            for r in rounds:
                await self._execute(
                    round_q, cycle_id, symbol, r["round_num"],
                    r["bull_argument"], Decimal(str(r["bull_conviction"])),
                    r["bear_argument"], Decimal(str(r["bear_conviction"])),
                )

    async def get_cycle_with_rounds(self, cycle_id: UUID) -> Optional[Dict[str, Any]]:
        cycle = await self._fetchrow("SELECT * FROM debate_cycles WHERE cycle_id = $1", cycle_id)
        if not cycle:
            return None
        rounds = await self._fetch(
            "SELECT * FROM debate_transcripts WHERE cycle_id = $1 ORDER BY round_num", cycle_id
        )
        return {"cycle": dict(cycle), "rounds": [dict(r) for r in rounds]}
```

Wire both into `libs/storage/repositories/__init__.py`.

---

## 3 · Code changes (the correlation chain)

### 3A · `libs/core/schemas.py`

Add `decision_event_id` to `OrderApprovedEvent`. Optional so old in-flight messages don't break.

```python
class OrderApprovedEvent(BaseEvent):
    profile_id: UUID
    symbol: str
    side: SignalDirection
    quantity: Decimal
    price: Decimal
    decision_event_id: Optional[UUID] = None   # ← NEW
    timestamp_us: int
    source_service: str
```

### 3B · `services/hot_path/src/processor.py:344-360`

Pass the decision event_id into the order event, **and** stop using `order_ev.event_id` as the trace's order_id (it was wrong). Instead leave `order_id` NULL on the trace at write time — the link is now `decision_event_id` flowing forward through the order.

```python
# at line 344 — add decision_event_id to the order event
order_ev = OrderApprovedEvent(
    profile_id=profile_state.profile_id,
    symbol=tick.symbol,
    side=SignalDirection(sig_res.direction),
    quantity=qty,
    price=tick.price,
    decision_event_id=trace["event_id"] if trace else None,  # ← NEW
    timestamp_us=tick.timestamp,
    source_service="hot-path"
)
await self._publisher.publish(self._orders_channel, order_ev)
MetricsCollector.increment_counter("orders.approved")

# Write approved decision trace (no longer fakes order_id from event_id)
if self._decision_writer:
    trace["outcome"] = "APPROVED"
    # order_id stays unset — execution writes it back via decision_event_id linkage
    await self._decision_writer.write(trace)
```

### 3C · `services/execution/src/executor.py:158-230`

Persist `decision_event_id` on the order and on the position.

```python
# at line 158
order_id = uuid.uuid4()
decision_event_id = ev.decision_event_id   # ← NEW (may be None for legacy events)

# at line 165-175 — extend Order construction (and Order model + create_order signature)
order = Order(
    order_id=order_id,
    profile_id=ev.profile_id,
    symbol=ev.symbol,
    side=ev.side,
    quantity=ev.quantity,
    price=ev.price,
    status=OrderStatus.PENDING,
    exchange=exchange_name,
    created_at=datetime.utcnow(),
    decision_event_id=decision_event_id,   # ← NEW
)
await self._order_repo.create_order(order)

# at line 213-226 — extend Position construction
pos = Position(
    position_id=pos_id,
    profile_id=ev.profile_id,
    symbol=ev.symbol,
    side=ev.side,
    entry_price=fill_price,
    quantity=ev.quantity,
    entry_fee=entry_fee,
    opened_at=datetime.utcnow(),
    status=PositionStatus.OPEN,
    order_id=order_id,                      # ← NEW
    decision_event_id=decision_event_id,    # ← NEW
)
await self._position_repo.create_position(pos)
```

Update `libs/core/models.py` `Order` and `Position` dataclasses to add `decision_event_id: Optional[UUID] = None` and `order_id: Optional[UUID] = None` (on Position).

Update `libs/storage/repositories/order_repo.py:create_order` and `position_repo.py:create_position` to insert the new columns.

### 3D · `services/pnl/src/closer.py`

The current closer already snapshots agent scores from Redis. Now also write the full `closed_trades` row.

```python
# constructor: inject ClosedTradeRepository + PositionRepository (already there)
def __init__(self, position_repo, redis_client, closed_trade_repo: ClosedTradeRepository):
    ...
    self._closed_trade_repo = closed_trade_repo

async def close(self, position, exit_price, taker_rate, close_reason="stop_loss"):
    closed_at = datetime.now(timezone.utc)
    await self._position_repo.close_position(position.position_id, exit_price)

    snapshot = PnLCalculator.calculate(position=position, current_price=exit_price, taker_rate=taker_rate)
    outcome = "win" if snapshot.pct_return > 0 else ("breakeven" if snapshot.pct_return == 0 else "loss")
    agent_scores = await self._get_agent_scores(str(position.position_id))

    # Snapshot regime at close time from Redis
    entry_regime = None
    try:
        regime_raw = await self._redis.get(f"regime:{position.symbol}")
        if regime_raw:
            entry_regime = regime_raw.decode() if isinstance(regime_raw, bytes) else str(regime_raw)
    except Exception:
        pass

    holding_s = int((closed_at - position.opened_at).total_seconds()) if position.opened_at else 0
    exit_fee = taker_rate * position.quantity * exit_price

    try:
        await self._closed_trade_repo.write_closed_trade(
            position_id=position.position_id,
            profile_id=UUID(position.profile_id) if isinstance(position.profile_id, str) else position.profile_id,
            symbol=position.symbol,
            side=position.side.value if hasattr(position.side, "value") else str(position.side),
            decision_event_id=getattr(position, "decision_event_id", None),
            order_id=getattr(position, "order_id", None),
            entry_price=position.entry_price,
            entry_quantity=position.quantity,
            entry_fee=position.entry_fee,
            entry_regime=entry_regime,
            entry_agent_scores=agent_scores,
            exit_price=exit_price,
            exit_fee=exit_fee,
            close_reason=close_reason,
            opened_at=position.opened_at,
            closed_at=closed_at,
            holding_duration_s=holding_s,
            realized_pnl=snapshot.net_pre_tax,
            realized_pnl_pct=Decimal(str(snapshot.pct_return)),
            outcome=outcome,
        )
    except Exception:
        logger.exception("Failed to write closed_trade row", position_id=str(position.position_id))

    # ... rest unchanged (tracker.record_position_close, redis cleanup, return snapshot)
```

Wire `ClosedTradeRepository` into `services/pnl/src/main.py` lifespan and pass it to `PositionCloser`.

### 3E · `services/debate/src/main.py:108-115` and `services/debate/src/engine.py`

In `engine.py`, generate a `cycle_id` per debate run and include it on the `DebateResult`:

```python
@dataclass
class DebateResult:
    symbol: str
    score: float
    confidence: float
    reasoning: str
    cycle_id: UUID = field(default_factory=uuid.uuid4)   # ← NEW
    rounds: list[DebateRound] = field(default_factory=list)
    total_latency_ms: float = 0.0
```

In `main.py:debate_loop`, after writing the score, also persist the full transcript:

```python
if debate_repo:
    try:
        await debate_repo.write_cycle(
            cycle_id=result.cycle_id,
            symbol=symbol,
            final_score=Decimal(str(result.score)),
            final_confidence=Decimal(str(result.confidence)),
            judge_reasoning=result.reasoning,
            num_rounds=len(result.rounds),
            total_latency_ms=result.total_latency_ms,
            market_context={
                "price": ctx.price, "rsi": ctx.rsi, "macd_hist": ctx.macd_histogram,
                "adx": ctx.adx, "bb_pct_b": ctx.bb_pct_b, "atr": ctx.atr,
                "regime": ctx.regime, "ta_score": ctx.ta_score, "sentiment_score": ctx.sentiment_score,
            },
            rounds=[
                {
                    "round_num": r.round_num,
                    "bull_argument": r.bull_argument,
                    "bull_conviction": r.bull_conviction,
                    "bear_argument": r.bear_argument,
                    "bear_conviction": r.bear_conviction,
                }
                for r in result.rounds
            ],
        )
    except Exception as pe:
        logger.warning("Failed to persist debate transcript", error=str(pe))
```

Wire `DebateRepository(timescale)` into the lifespan and pass it to `debate_loop`.

---

## 4 · API additions (read-only)

Add three endpoints to `services/api_gateway/src/routes/` so the frontend (or you in a browser) can pull traces. All read-only, no behavior change.

- `GET /audit/trade/{position_id}` → joined chain (decision + order + position + closed_trade)
- `GET /audit/closed-trades?symbol=X&limit=50` → recent closed trades
- `GET /audit/debate/{cycle_id}` → full transcript

These are thin wrappers over the new repos. Mount under `/audit/*` to keep the namespace clean.

---

## 5 · Files touched (full inventory)

**New (5 files):**
- `migrations/versions/014_intent_correlation.sql`
- `migrations/versions/015_closed_trades.sql`
- `migrations/versions/016_debate_transcripts.sql`
- `libs/storage/repositories/closed_trade_repo.py`
- `libs/storage/repositories/debate_repo.py`

**Modified (10 files):**
- `libs/storage/repositories/__init__.py` (export new repos)
- `libs/core/schemas.py` (add `decision_event_id` to `OrderApprovedEvent`)
- `libs/core/models.py` (add fields to `Order` and `Position` dataclasses)
- `libs/storage/repositories/order_repo.py` (insert `decision_event_id`)
- `libs/storage/repositories/position_repo.py` (insert `order_id`, `decision_event_id`)
- `services/hot_path/src/processor.py` (carry decision_event_id; stop misusing order_id field on trace)
- `services/execution/src/executor.py` (propagate decision_event_id through Order and Position)
- `services/pnl/src/closer.py` (write closed_trades row)
- `services/pnl/src/main.py` (lifespan: instantiate ClosedTradeRepository, inject into closer)
- `services/debate/src/main.py` (write debate cycles + transcripts)
- `services/debate/src/engine.py` (add cycle_id to DebateResult)
- `services/api_gateway/src/routes/audit.py` (new file — three GET endpoints)
- `services/api_gateway/src/main.py` (mount audit router)

**Tests to add (`tests/`):**
- `tests/unit/storage/test_closed_trade_repo.py` — round-trip insert/fetch
- `tests/unit/storage/test_debate_repo.py` — cycle + rounds insert/fetch
- `tests/contract/test_decision_chain.py` — simulate intent → order → position → close, assert all four rows exist and join correctly via `decision_event_id`

---

## 6 · Risk & rollback

| Risk | Likelihood | Mitigation |
|---|---|---|
| `decision_event_id` carried in OrderApprovedEvent breaks deserialization on consumers built from old code | Low | Field is `Optional` with default `None`. Old events still deserialize. |
| `closed_trade_repo.write` failure blocks position close | **Medium** | Wrapped in try/except in closer.py — logged, never raises. The position close itself still completes. |
| Debate transcript write doubles DB load on debate cycles | Low | One cycle row + N round rows per 5min per symbol. With 4 symbols × 2 rounds = 12 inserts / 5min = trivial. |
| Migration adds column to live `orders` and `positions` tables | Low | `ADD COLUMN ... IF NOT EXISTS` is non-blocking in Postgres 11+. No table rewrite. |
| `decision_event_id` flowing through means hot-path could be slowed by extra dict key | Negligible | One UUID assignment in a hot loop — sub-microsecond. |

**Rollback:** All migrations are additive (new columns nullable, new tables independent). To roll back: drop the new tables and the two new columns. No data loss in existing tables. The code rollback is the git revert — no migration reversal needed for safety.

---

## 7 · Implementation order (recommended sequence)

Each step independently testable, system stays runnable between steps.

1. **Migrations + repos** — write 014/015/016, write repo classes, write unit tests, run `python scripts/migrate.py`. Verify schema with `\d closed_trades` in psql. **No service code changes yet.**
2. **Schema + model field additions** — extend `OrderApprovedEvent`, `Order`, `Position`. System still runs (fields default to None).
3. **Hot path** — propagate `decision_event_id` into `OrderApprovedEvent`. Verify in Redis stream that field is present on new messages.
4. **Execution** — persist `decision_event_id` and `order_id` on Order and Position rows. Run a test order; verify `SELECT decision_event_id FROM positions ORDER BY opened_at DESC LIMIT 1` returns a non-null UUID that matches `trade_decisions.event_id`.
5. **PnL closer** — write `closed_trades` row on close. Force a position close (manual or wait for SL/TP); verify row appears with full chain populated.
6. **Debate persistence** — write `debate_cycles` + `debate_transcripts`. Wait one debate cycle (5min); verify rows appear.
7. **API endpoints** — add `/audit/*` routes; smoke-test from a browser.
8. **Contract test** — `tests/contract/test_decision_chain.py` end-to-end.

Estimated effort: **8 dev-hours** spread across these 8 steps. Most of the time goes into step 5 (closer.py) and step 8 (the contract test).

---

## 8 · What PR1 deliberately does NOT do

Out of scope, planned for PR2/PR3:

- ❌ No nightly Optimization Agent
- ❌ No `system_constants` table or tunable globals store
- ❌ No signal-replay backtester
- ❌ No vector DB / pgvector / embeddings
- ❌ No correlation-check audit agent
- ❌ No changes to risk gates, sizing, or any decision logic
- ❌ No frontend changes (just the API endpoints; UI in a later PR)

If you want any of these in PR1, say so now and I'll fold them in — but I'd recommend keeping PR1 scoped tightly to the ledger so it ships quickly and you have data to reason about before deciding what to optimize.
