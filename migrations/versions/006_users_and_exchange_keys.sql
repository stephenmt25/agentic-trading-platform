-- Migration 006: Users and Exchange Keys tables for Phase 2
-- Supports OAuth providers (Google, GitHub) and encrypted exchange key references

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Adjust existing Users table from Phase 1 to support Phase 2 OAuth
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name    VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url      TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS provider        VARCHAR(50) NOT NULL DEFAULT 'google';
ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_account_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Make existing Phase 1 columns nullable to support OAuth-only users
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;
ALTER TABLE users ALTER COLUMN jurisdiction DROP NOT NULL;

-- Update display_name for existing users if any
UPDATE users SET display_name = split_part(email, '@', 1) WHERE display_name IS NULL;
ALTER TABLE users ALTER COLUMN display_name SET NOT NULL;

-- Add unique constraint for OAuth
ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_provider_account;
ALTER TABLE users ADD CONSTRAINT uq_provider_account UNIQUE (provider, provider_account_id);

-- Exchange keys table: stores references to secrets in GCP Secret Manager
-- NEVER stores plaintext API keys — only the secret_id pointer
CREATE TABLE IF NOT EXISTS exchange_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    exchange_name   VARCHAR(100) NOT NULL,  -- 'binance', 'coinbase'
    gcp_secret_id   VARCHAR(512) NOT NULL,  -- GCP Secret Manager resource ID (or local Fernet ref)
    label           VARCHAR(255),           -- user-friendly label, e.g. "My Binance Main"
    permissions     JSONB DEFAULT '[]',     -- e.g. ["read", "trade"]
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,            -- soft-delete timestamp

    CONSTRAINT uq_user_exchange UNIQUE (user_id, exchange_name, label)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_exchange_keys_user ON exchange_keys(user_id) WHERE deleted_at IS NULL;
