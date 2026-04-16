-- Migration 013: Pipeline Config
-- Adds a JSONB column to trading_profiles for storing custom pipeline DAG configs.
-- NULL = use default linear pipeline, non-null = custom DAG.

ALTER TABLE trading_profiles ADD COLUMN IF NOT EXISTS pipeline_config JSONB DEFAULT NULL;
