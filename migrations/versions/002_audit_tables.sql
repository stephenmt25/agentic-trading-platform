CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL,
    event_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    source_service TEXT NOT NULL,
    profile_id UUID,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('audit_log', 'created_at', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS config_changes (
    change_id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    field_changed TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
