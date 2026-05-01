-- Migration 015: Closed Trades — outcome mapping
-- One row per closed position. Links the entire decision lineage to realized PnL.
-- This is the table the nightly Optimization Agent (PR2) will read to find
-- patterns in losing trades.

CREATE TABLE IF NOT EXISTS closed_trades (
    position_id          UUID PRIMARY KEY REFERENCES positions(position_id) ON DELETE RESTRICT,
    profile_id           UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE RESTRICT,
    symbol               TEXT NOT NULL,
    side                 TEXT NOT NULL,                 -- BUY / SELL
    decision_event_id    UUID,                          -- → trade_decisions.event_id (no FK: hypertable)
    order_id             UUID,                          -- → orders.order_id (no FK: hypertable)

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

    -- Realized PnL (net of fees)
    realized_pnl         DECIMAL(20,8) NOT NULL,
    realized_pnl_pct     DECIMAL(10,6) NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_closed_trades_regime_outcome
    ON closed_trades (entry_regime, outcome) WHERE entry_regime IS NOT NULL;
