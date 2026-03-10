CREATE TABLE IF NOT EXISTS validation_events (
    id BIGSERIAL,
    event_id UUID NOT NULL,
    profile_id UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    check_type TEXT NOT NULL,
    signal_data JSONB NOT NULL,
    verdict TEXT NOT NULL,
    reason TEXT,
    check_mode TEXT NOT NULL,
    response_time_ms DECIMAL NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('validation_events', 'created_at', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS auto_backtest_queue (
    job_id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    source_validation_event_id UUID NOT NULL,
    parameters JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
