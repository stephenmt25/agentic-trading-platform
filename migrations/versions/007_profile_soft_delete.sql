-- Add deleted_at column to trading_profiles table
ALTER TABLE trading_profiles ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

-- Create an index to quickly filter for active, non-deleted profiles mapping
CREATE INDEX IF NOT EXISTS idx_trading_profiles_active_not_deleted
ON trading_profiles (is_active, deleted_at)
WHERE is_active = true AND deleted_at IS NULL;
