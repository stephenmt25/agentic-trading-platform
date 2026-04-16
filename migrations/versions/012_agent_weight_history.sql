-- Migration 012: Agent Weight History
-- Tracks how agent weights evolve over time as the Analyst recomputes them.
-- Used by the performance evaluation dashboard to show weight evolution charts.

CREATE TABLE IF NOT EXISTS agent_weight_history (
    symbol          TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    weight          NUMERIC(10,6) NOT NULL,
    ewma_accuracy   NUMERIC(10,6) NOT NULL,
    sample_count    INTEGER NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('agent_weight_history', 'recorded_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_awh_lookup
    ON agent_weight_history (symbol, agent_name, recorded_at DESC);
