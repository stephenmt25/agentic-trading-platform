-- Migration 021: User-level risk defaults
-- Persists per-user risk caps that surface on /settings/risk. Scope is
-- explicitly account-level: these defaults are intended to apply to newly
-- created profiles. Propagation/recompile to *running* profiles is a
-- separate project (the recompile fan-out mechanism doesn't exist yet);
-- until that lands, /settings/risk shows a small inline note disclosing
-- "applies to new profiles only".
--
-- Schema is a single JSONB column rather than a wide row so adding a new
-- cap (e.g. per-symbol limits) doesn't require a migration. Validation
-- lives in libs/core/schemas.py::UserRiskDefaultsPayload.

CREATE TABLE IF NOT EXISTS user_risk_defaults (
    user_id      UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    defaults     JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- No additional indexes — user_id is the PK, queries are always single-row by user_id.
