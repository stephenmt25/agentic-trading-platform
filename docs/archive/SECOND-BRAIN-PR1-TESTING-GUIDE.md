# 2nd Brain PR1 — Testing & Learning Guide

This is your hands-on companion to PR1. It walks you from "system started" → "trade closed" → "I can read the whole story in SQL" → "I know what the data is telling me." Read it once cover-to-cover before testing so you know what to look for; keep it open during testing as a reference.

---

## Part 1 · Setup (one-time, before testing)

### 1.1 Apply the new migrations

```bash
python scripts/migrate.py
```
 
The script applies every `migrations/versions/*.sql` in order. The new ones (014, 015, 016) are idempotent (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`) so re-running is safe.

**Expected output:**
```
Applying migrations/versions/014_intent_correlation.sql...
Applying migrations/versions/015_closed_trades.sql...
Applying migrations/versions/016_debate_transcripts.sql...
Migrations complete.
```

If you see `Failed to execute ...` for any of these, **stop and read the error.** The most common failure is "column already exists" from a partial earlier run — that's actually fine, you can ignore it. Anything else, paste the error to me.

### 1.2 Verify the schema landed

Open a psql shell against your local TimescaleDB:

```bash
psql "$DATABASE_URL"
```

Then run:

```sql
\d closed_trades
\d debate_cycles
\d debate_transcripts
\d+ orders     -- look for decision_event_id at the bottom
\d+ positions  -- look for order_id and decision_event_id at the bottom
```

**What you should see:** Each `\d` prints the table's columns. `closed_trades` should have ~20 columns. The `\d+ orders` and `\d+ positions` outputs should now include `decision_event_id`. If a column or table is missing, the migration didn't run — re-run step 1.1.

### 1.3 Boot the system

```bash
bash run_all.sh --local-frontend
```

Wait for all 19 services to print "started" / "healthy". This usually takes 30-60 seconds. **Do not start services individually** — that's specifically called out in CLAUDE.md as causing zombie/port issues.

---

## Part 2 · Generate one trade end-to-end

Goal: produce one full row in `trade_decisions`, one matching `orders` row, one `positions` row, then close it and produce a `closed_trades` row.

### 2.1 Confirm the system is generating market ticks

```sql
SELECT symbol, COUNT(*) AS ticks_last_min
FROM market_data_ohlcv
WHERE bucket > NOW() - INTERVAL '1 minute'
GROUP BY symbol;
```

If this returns rows, ingestion is working. If empty, the ingestion service hasn't started yet — wait another minute.

### 2.2 Watch hot_path generate decisions

The hot path writes a `trade_decisions` row on **every** signal evaluation (approved AND blocked). Even with conservative rules, you should see BLOCKED rows accumulate within minutes:

```sql
SELECT outcome, COUNT(*) AS n
FROM trade_decisions
WHERE created_at > NOW() - INTERVAL '5 minutes'
GROUP BY outcome
ORDER BY n DESC;
```

**What healthy looks like:** A mix of `BLOCKED_ABSTENTION`, `BLOCKED_REGIME`, maybe a few `APPROVED`. If you see *only* `BLOCKED_VALIDATION`, something downstream of hot_path is rejecting everything — check validation service logs. If you see *zero* rows, hot_path isn't running or isn't seeing ticks.

### 2.3 Force an approval (paper mode)

If you want a guaranteed approval for testing, edit a profile's `strategy_rules` to a permissive setup (e.g. RSI < 80, base_confidence 0.99) and let it tick once. Or simply wait — natural approvals will come.

When you see at least one `APPROVED`:

```sql
SELECT event_id, symbol, created_at, order_id
FROM trade_decisions
WHERE outcome = 'APPROVED'
ORDER BY created_at DESC
LIMIT 1;
```

Note the `event_id`. **Pre-PR1 behavior:** `order_id` would be the OrderApprovedEvent's autogen UUID, useless for joining. **Post-PR1 behavior:** `order_id` will be NULL on the trace itself; the link goes the other way — the `orders` row has `decision_event_id = trade_decisions.event_id`.

### 2.4 Verify the chain forward

Using the `event_id` from step 2.3:

```sql
WITH d AS (
    SELECT '<paste-event_id-here>'::uuid AS event_id
)
SELECT
    td.event_id     AS decision_event_id,
    o.order_id,
    o.status        AS order_status,
    p.position_id,
    p.entry_price,
    p.opened_at,
    p.closed_at,
    p.exit_price
FROM d
JOIN trade_decisions td ON td.event_id = d.event_id
LEFT JOIN orders o      ON o.decision_event_id = td.event_id
LEFT JOIN positions p   ON p.order_id = o.order_id;
```

**What you should see:** Exactly one row, with `order_id` and `position_id` populated and `closed_at` still NULL (position is open). If the JOIN to `orders` produces NULL, the executor isn't writing `decision_event_id` — check `execution` logs and the `Order` model.

### 2.5 Close the position

In paper mode, exit policies (stop-loss, take-profit, time-exit) are configured in `libs/config/settings.py` — `DEFAULT_STOP_LOSS_PCT`, `DEFAULT_TAKE_PROFIT_PCT`, `DEFAULT_MAX_HOLDING_HOURS`. Pick whichever is fastest for testing.

**Quickest path to a close:** set `DEFAULT_MAX_HOLDING_HOURS=0` (or however your time-exit logic interprets minimum) and wait, OR manually invoke the close via the API gateway, OR move on to natural SL/TP.

Once closed, verify the close lifecycle:

```sql
SELECT
    p.position_id,
    p.opened_at,
    p.closed_at,
    p.exit_price,
    ct.close_reason,
    ct.realized_pnl,
    ct.realized_pnl_pct,
    ct.outcome,
    ct.holding_duration_s
FROM positions p
LEFT JOIN closed_trades ct ON ct.position_id = p.position_id
WHERE p.position_id = '<your-position-id>';
```

**Healthy:** `closed_trades` row exists, `close_reason` matches what triggered it, `outcome` ∈ {`win`, `loss`, `breakeven`}, `realized_pnl_pct` is a sane number (e.g. -0.05 for a 5% loss). **Unhealthy:** `closed_trades` row missing → `closer.py` didn't write — check pnl service logs for `Failed to write closed_trade row`.

---

## Part 3 · The Money Query (the one query that proves PR1 works)

After 24 hours of running, this is the query you'll run to see the full picture:

```sql
SELECT
    td.created_at         AS decided_at,
    td.symbol,
    td.regime->>'resolved' AS regime,
    (td.agents->>'confidence_after')::numeric AS confidence,
    ct.close_reason,
    ct.realized_pnl_pct   AS pnl_pct,
    ct.holding_duration_s / 60 AS held_min,
    ct.outcome
FROM trade_decisions td
JOIN positions p   ON p.decision_event_id = td.event_id
JOIN closed_trades ct ON ct.position_id = p.position_id
WHERE td.outcome = 'APPROVED'
  AND td.created_at > NOW() - INTERVAL '24 hours'
ORDER BY ct.realized_pnl_pct ASC;   -- worst losses first
```

**What you'll learn from reading this:**
- **Top rows = your worst trades.** Look at the regime + confidence columns. Pattern: are they all in `RANGING` regime? All at low confidence? That's a tuning lead for PR2.
- **Bottom rows = your best trades.** Same pattern hunt. Are they all `TRENDING_UP` with high confidence? That confirms the rule set is working in those conditions.
- **`held_min` distribution.** If wins hold much longer than losses, your SL is doing its job. If losses hold longer than wins, SL is too loose — your wins are getting taken too early.
- **`close_reason` mix.** Healthy paper trading has a mix of `take_profit` (good), `stop_loss` (necessary cost of doing business), `time_exit` (neutral). If 95% are `time_exit`, the strategy isn't actually triggering SL/TP at meaningful prices — likely the levels are too far away.

---

## Part 4 · Reading the data — what each output means

### 4.1 `trade_decisions.outcome` distribution

Run hourly:
```sql
SELECT outcome, COUNT(*) FROM trade_decisions
WHERE created_at > NOW() - INTERVAL '1 hour' GROUP BY outcome;
```

| Outcome | What it means | What to do |
|---|---|---|
| `APPROVED` | Hot path passed every gate and emitted an order | Healthy if 1-20% of total |
| `BLOCKED_ABSTENTION` | Confidence too low / no clear signal | Expected to dominate; this is the strategy being patient |
| `BLOCKED_REGIME` | Regime dampener said the current market regime doesn't fit the rule | Check `trade_decisions.regime` JSONB to see what regime was active |
| `BLOCKED_RISK` | Risk gate rejected (drawdown, allocation, exposure cap) | If high, you may be over-allocated |
| `BLOCKED_CIRCUIT_BREAKER` | Daily loss cap hit | If non-zero, your day is bad — investigate the trades that got you here |
| `BLOCKED_HITL` | Human-in-the-loop mode held the trade | Expected if HITL mode is on |
| `BLOCKED_VALIDATION` | Validation service red-flagged | If high, validation service is over-rejecting — investigate `validation_log` table |
| `BLOCKED_BLACKLIST` | Symbol in profile blacklist | Should be 0 unless you intentionally blacklisted |

**Rule of thumb:** If `BLOCKED_ABSTENTION` is >90%, the strategy is too picky — natural for conservative rules. If `APPROVED` is >50%, the strategy is firing on too many signals — likely overtrading.

### 4.2 `closed_trades.close_reason` × `outcome`

```sql
SELECT close_reason, outcome, COUNT(*) AS n,
       ROUND(AVG(realized_pnl_pct)::numeric, 4) AS avg_pnl_pct,
       ROUND(AVG(holding_duration_s)::numeric / 60, 1) AS avg_held_min
FROM closed_trades
WHERE closed_at > NOW() - INTERVAL '24 hours'
GROUP BY close_reason, outcome
ORDER BY close_reason, outcome;
```

This is the truth-table of your strategy. The shape you want to see:

- `take_profit` × `win` → high count, positive avg_pnl_pct, moderate avg_held_min
- `stop_loss` × `loss` → moderate count, negative avg_pnl_pct (close to your SL %), short avg_held_min
- `time_exit` × `win` or `loss` → small count if SL/TP are well-calibrated
- `take_profit` × `loss` → should be ~0 (TP triggers above entry, can only be a win or breakeven net of fees)
- `stop_loss` × `win` → should be ~0 (same logic)

**Anti-patterns to watch for:**
- `time_exit` >> `take_profit` + `stop_loss` → SL/TP levels are too wide, trades expire instead
- `stop_loss` losses > 2× `take_profit` wins (in absolute pct) → asymmetric SL/TP working against you, or selection bias toward losing setups
- avg_held_min for losses > avg_held_min for wins → "letting losers run, cutting winners early" — the cardinal sin

### 4.3 `entry_agent_scores` patterns

```sql
SELECT
    outcome,
    ROUND(AVG((entry_agent_scores->>'ta')::numeric), 3) AS avg_ta,
    ROUND(AVG((entry_agent_scores->>'sentiment')::numeric), 3) AS avg_sent,
    ROUND(AVG((entry_agent_scores->>'debate')::numeric), 3) AS avg_debate,
    COUNT(*) AS n
FROM closed_trades
WHERE entry_agent_scores IS NOT NULL
  AND closed_at > NOW() - INTERVAL '7 days'
GROUP BY outcome;
```

**What to read:** Compare avg agent scores between `win` and `loss` rows. If `avg_ta` is much higher for wins than losses, the TA agent is genuinely predictive — its weight should go UP. If `avg_debate` is the same for wins and losses, the debate agent is contributing noise — its weight should go DOWN. **This is exactly the analysis the PR2 nightly Optimization Agent will automate.** For now you're doing it by eye.

### 4.4 `entry_regime` × `outcome`

```sql
SELECT entry_regime, outcome, COUNT(*) AS n,
       ROUND(AVG(realized_pnl_pct)::numeric, 4) AS avg_pnl
FROM closed_trades
WHERE closed_at > NOW() - INTERVAL '7 days'
  AND entry_regime IS NOT NULL
GROUP BY entry_regime, outcome
ORDER BY entry_regime, outcome;
```

**What to read:** Win rates and avg pnl per regime. If you have a 70% win rate in `TRENDING_UP` but 30% in `RANGING`, the system should *only* trade in TRENDING_UP — that's a regime-dampener tuning signal.

### 4.5 Debate transcripts

Pull a recent debate cycle and read it like a conversation:

```sql
SELECT cycle_id, symbol, final_score, final_confidence, judge_reasoning, recorded_at
FROM debate_cycles
ORDER BY recorded_at DESC LIMIT 5;
```

Pick a `cycle_id` and read the rounds:

```sql
SELECT round_num, bull_conviction, bear_conviction, bull_argument, bear_argument
FROM debate_transcripts
WHERE cycle_id = '<paste-cycle_id>'
ORDER BY round_num;
```

**What to look for in the transcript:**
- Does the bull cite real numbers from the market context (RSI, MACD, regime)? Or is it generic ("BTC is bullish because adoption")? Generic = the LLM is hallucinating signal; tighten the prompt.
- Does the bear actually disagree with the bull, or just agree with caveats? Real adversarial debate produces tension. Limp debates produce centrist scores (~0.5 confidence) that aren't useful.
- Does the judge_reasoning explain WHY one side won? "Bull provided stronger evidence on RSI divergence" is useful. "Both sides have merit" is not.
- High-conviction wins on the bull side that lead to losing trades are your biggest red flag — the LLM is confidently wrong, and you should reduce its weight.

---

## Part 5 · Daily routine (suggested)

A 10-minute morning check after PR1 is shipped. Build the muscle so PR2's automated optimizer makes intuitive sense when it lands.

1. **Win rate over last 24h** — `SELECT outcome, COUNT(*) FROM closed_trades WHERE closed_at > NOW() - INTERVAL '24 hours' GROUP BY outcome;`
2. **Worst trade of the day** — run the Money Query (Part 3) and read the bottom row's regime + agent scores.
3. **Read one full debate transcript** — pick a recent one for a symbol you're trading. Does the reasoning quality match the score it produced?
4. **Block-rate health** — `BLOCKED_ABSTENTION` % over 24h. Is it trending up (more conservative) or down (more aggressive)?

Write your observations into a notebook. After two weeks you'll start to see patterns — and those patterns are the requirements doc for PR2's Optimization Agent.

---

## Part 6 · Troubleshooting

| Symptom | Likely cause | What to check |
|---|---|---|
| `closed_trades` empty after several closes | `closer.py` write_closed_trade exception swallowed | `grep "Failed to write closed_trade" services/pnl/logs/` |
| `decision_event_id` NULL in positions | Either OrderApprovedEvent missing it (hot_path) or executor not reading it | Inspect a recent OrderApprovedEvent in Redis: `XRANGE stream:orders - +` |
| `debate_transcripts` rows missing but `agent_score_history` debate rows exist | Debate writes summary but not transcript — the new write_cycle path isn't wired | Check `services/debate/src/main.py` lifespan injects `DebateRepository` |
| Migration "column already exists" | Idempotency — safe to ignore | Re-read schema with `\d+` to confirm column is correct type |
| Money Query returns zero joined rows but `trade_decisions` has APPROVED rows | Chain broken at orders step | `SELECT decision_event_id FROM orders ORDER BY created_at DESC LIMIT 5;` should be non-NULL |
| `closed_trades.entry_agent_scores` NULL | Redis snapshot key expired (7-day TTL) or executor never wrote it | Check `agent:position_scores:{pid}` in Redis at close time |
| `entry_regime` NULL on closed_trades | Redis `regime:{symbol}` key was empty at close time (regime_hmm not running?) | `redis-cli get regime:BTC/USDT` |

---

## Part 7 · What PR1 enables (the payoff)

After PR1 ships, you can answer questions you currently can't:

- "Which agent's signal is most predictive of wins for BTC?"
- "Do my losses cluster in any specific regime?"
- "What's the median holding time of a winning trade vs a losing one?"
- "Which debate cycles led to high-confidence APPROVED trades that lost money?" (the LLM-confidently-wrong query)
- "When SL fires, how often does price recover within an hour?" (would my SL be too tight?)

You can answer all of these with ad-hoc SQL today. PR2's job is to turn those queries into automated nightly directives. PR3's job is to let the system act on those directives. **None of that works without the ledger.** That's why this PR comes first.
