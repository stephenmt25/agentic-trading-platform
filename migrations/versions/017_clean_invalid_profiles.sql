-- Migration 017: Delete trading profiles whose strategy_rules don't conform to
-- the canonical {logic, direction, base_confidence, conditions} shape, plus all
-- referencing child rows. The narrative shape ({symbols, strategy, timeframe,
-- entry_conditions, exit_conditions}) was being silently skipped by hot_path,
-- producing inert profiles with no trading activity.
--
-- Idempotent: re-running with no invalid rows is a no-op.
--
-- Tables touched (in dependency order):
--   1. closed_trades       — RESTRICT on profile_id, must clean first
--   2. trade_decisions     — RESTRICT, hypertable
--   3. positions           — RESTRICT
--   4. orders              — RESTRICT, hypertable
--   5. trading_profiles    — DELETE; CASCADE handles pnl_snapshots,
--                            validation_events, config_changes, auto_backtest_queue

BEGIN;

CREATE TEMP TABLE invalid_profile_ids ON COMMIT DROP AS
SELECT profile_id
FROM trading_profiles
WHERE NOT (
    strategy_rules ? 'logic'
    AND strategy_rules ? 'direction'
    AND strategy_rules ? 'base_confidence'
    AND strategy_rules ? 'conditions'
);

DELETE FROM closed_trades    WHERE profile_id IN (SELECT profile_id FROM invalid_profile_ids);
DELETE FROM trade_decisions  WHERE profile_id IN (SELECT profile_id FROM invalid_profile_ids);
DELETE FROM positions        WHERE profile_id IN (SELECT profile_id FROM invalid_profile_ids);
DELETE FROM orders           WHERE profile_id IN (SELECT profile_id FROM invalid_profile_ids);
DELETE FROM trading_profiles WHERE profile_id IN (SELECT profile_id FROM invalid_profile_ids);

COMMIT;
