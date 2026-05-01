-- Migration 016: Debate Transcripts
-- Full conversational trace of each debate cycle.
-- Today, services/debate persists only a one-row summary per cycle to
-- agent_score_history.metadata. The actual bull/bear arguments per round
-- are computed and discarded. This migration adds:
--   debate_cycles      → one row per debate (judge score + market context snapshot)
--   debate_transcripts → N rows per cycle (one per round, bull + bear arguments)
-- Enables transcript replay and qualitative review of LLM reasoning.

CREATE TABLE IF NOT EXISTS debate_cycles (
    cycle_id           UUID PRIMARY KEY,
    symbol             TEXT NOT NULL,
    final_score        NUMERIC(10,6) NOT NULL,          -- judge score, -1..1
    final_confidence   NUMERIC(10,6) NOT NULL,          -- judge confidence, 0..1
    judge_reasoning    TEXT,
    num_rounds         INTEGER NOT NULL,
    total_latency_ms   NUMERIC(10,2) NOT NULL,
    market_context     JSONB NOT NULL,                  -- {price, rsi, macd_hist, regime, ta_score, sentiment_score, ...}
    recorded_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS debate_transcripts (
    cycle_id           UUID NOT NULL REFERENCES debate_cycles(cycle_id) ON DELETE CASCADE,
    symbol             TEXT NOT NULL,                   -- denormalized for symbol-only queries
    round_num          INTEGER NOT NULL,                -- 1..N
    bull_argument      TEXT NOT NULL,
    bull_conviction    NUMERIC(10,6) NOT NULL,
    bear_argument      TEXT NOT NULL,
    bear_conviction    NUMERIC(10,6) NOT NULL,
    recorded_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cycle_id, round_num)
);

CREATE INDEX IF NOT EXISTS idx_debate_cycles_symbol_recorded
    ON debate_cycles (symbol, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_debate_transcripts_symbol_recorded
    ON debate_transcripts (symbol, recorded_at DESC);
