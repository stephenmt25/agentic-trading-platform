-- Migration 020: Backtest history fields
--
-- Track-Item: B.2
--
-- Adds the columns the run-history UI needs to scope past backtests to the
-- user that submitted them and to render their date range without re-fetching
-- per-job. The existing `backtest_results` rows pre-date this migration and
-- have no created_by — they will appear under no-user filters and are
-- effectively orphaned, but the dataset is small (~70 rows on dev) and
-- nothing depends on the historic provenance.

ALTER TABLE backtest_results
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS start_date TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS end_date   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS timeframe  TEXT;

CREATE INDEX IF NOT EXISTS idx_backtest_results_user_created
    ON backtest_results (created_by, created_at DESC);
