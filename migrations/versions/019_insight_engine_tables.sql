-- Migration 019: Insight Engine tables (Track D.PR2 — gate efficacy MVP)
-- Stores periodic gate-efficacy reports computed by services/analyst/src/insight_engine.py.
-- Each row answers "of decisions blocked by gate G in window W, what fraction
-- would have been profitable had they passed?" by replaying decisions through
-- the next K candles using the profile's risk_limits.

CREATE TABLE IF NOT EXISTS gate_efficacy_reports (
    report_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id       UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    symbol           TEXT NOT NULL,
    gate_name        TEXT NOT NULL,
    window_start     TIMESTAMPTZ NOT NULL,
    window_end       TIMESTAMPTZ NOT NULL,
    blocked_count    INT NOT NULL,
    passed_count     INT NOT NULL,
    blocked_would_be_win_rate  NUMERIC(6,4),
    blocked_would_be_pnl_pct   NUMERIC(10,4),
    passed_realized_win_rate   NUMERIC(6,4),
    passed_realized_pnl_pct    NUMERIC(10,4),
    sample_size_blocked        INT NOT NULL,
    sample_size_passed         INT NOT NULL,
    confidence_band            NUMERIC(6,4),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gate_efficacy_profile_gate
    ON gate_efficacy_reports (profile_id, gate_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_gate_efficacy_symbol_window
    ON gate_efficacy_reports (symbol, window_end DESC);

-- Scaffold for the rule-heatmap follow-up. The MVP doesn't write here yet;
-- the table is ready so adding the heatmap worker doesn't need a migration.
CREATE TABLE IF NOT EXISTS rule_fingerprint_outcomes (
    fingerprint      TEXT NOT NULL,
    profile_id       UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    symbol           TEXT NOT NULL,
    window_start     TIMESTAMPTZ NOT NULL,
    window_end       TIMESTAMPTZ NOT NULL,
    trade_count      INT NOT NULL,
    win_rate         NUMERIC(6,4),
    avg_pnl_pct      NUMERIC(10,4),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fingerprint, profile_id, symbol, window_end)
);
