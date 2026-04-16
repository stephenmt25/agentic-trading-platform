-- Migration 011: Agent Score History
-- Continuous timeseries of agent scores for charting overlays.
-- Unlike trade_decisions (which captures scores at decision time only),
-- this table records every scoring cycle from each agent.

CREATE TABLE IF NOT EXISTS agent_score_history (
    symbol          TEXT NOT NULL,
    agent_name      TEXT NOT NULL,       -- 'ta', 'sentiment', 'debate', 'regime_hmm'
    score           NUMERIC(10,6) NOT NULL,
    confidence      NUMERIC(10,6),
    metadata        JSONB,               -- agent-specific (e.g., regime name, debate reasoning)
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('agent_score_history', 'recorded_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_ash_lookup
    ON agent_score_history (symbol, agent_name, recorded_at DESC);
