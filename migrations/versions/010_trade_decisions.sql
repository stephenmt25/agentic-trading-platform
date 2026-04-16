-- Migration 010: Trade Decision Trace
-- Captures the full decision context at each gate evaluation point in the hot path.
-- Records both APPROVED and BLOCKED decisions for debugging and strategy tuning.

CREATE TABLE IF NOT EXISTS trade_decisions (
    event_id        UUID NOT NULL,
    profile_id      UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE RESTRICT,
    symbol          TEXT NOT NULL,
    outcome         TEXT NOT NULL,   -- APPROVED, BLOCKED_ABSTENTION, BLOCKED_REGIME, BLOCKED_CIRCUIT_BREAKER, BLOCKED_BLACKLIST, BLOCKED_RISK, BLOCKED_HITL, BLOCKED_VALIDATION
    input_price     DECIMAL NOT NULL,
    input_volume    DECIMAL,
    indicators      JSONB NOT NULL,
    strategy        JSONB NOT NULL,
    regime          JSONB,
    agents          JSONB,
    gates           JSONB NOT NULL,
    profile_rules   JSONB NOT NULL,
    order_id        UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, created_at)
);

SELECT create_hypertable('trade_decisions', 'created_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_trade_decisions_profile ON trade_decisions (profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trade_decisions_symbol ON trade_decisions (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trade_decisions_outcome ON trade_decisions (outcome, created_at DESC);
