-- Migration 022: User sessions
-- Tracks one row per (logical) authenticated session so /settings/sessions
-- can list active devices and revoke them. A "session" here = the active
-- chain of (callback → refresh → refresh → …) refresh tokens for one
-- browser/device. The chain advances on every /auth/refresh by rotating
-- the `jti` and updating last_seen_at; revocation is by DB flag and is
-- enforced inside /auth/refresh (DB is the source of truth for session
-- liveness; the existing Redis revoked-token denylist remains for
-- per-token rotation hygiene).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS user_sessions (
    session_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    jti            UUID NOT NULL,                  -- current refresh-token jti (rotates each refresh)
    user_agent     TEXT,
    ip_inet        INET,
    device         VARCHAR(64),                    -- coarse parse from UA: 'Mac', 'Windows', etc.
    browser        VARCHAR(64),                    -- coarse parse: 'Chrome', 'Safari', etc.
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at     TIMESTAMPTZ,
    revoked_reason VARCHAR(64),                    -- 'user', 'rotation', 'logout'
    UNIQUE (jti)
);

-- Listing endpoint queries by user_id and excludes revoked rows.
CREATE INDEX IF NOT EXISTS idx_user_sessions_active
    ON user_sessions(user_id, last_seen_at DESC)
    WHERE revoked_at IS NULL;

-- /auth/refresh joins by jti, fast-path lookup.
CREATE INDEX IF NOT EXISTS idx_user_sessions_jti ON user_sessions(jti);
