-- Migration 018: Shadow trade decisions
-- Adds a `shadow` flag to trade_decisions so the hot-path can record decisions
-- that were short-circuited by profile-level filters (e.g. preferred_regimes
-- mismatch) without exposing them in the live Decision Feed.
--
-- The default Decision Feed query stays unchanged — shadow=true rows are
-- excluded unless the caller opts in. PR3's Analyst will read the shadow set
-- to compare would-be performance against live performance.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS + index IF NOT EXISTS.

ALTER TABLE trade_decisions
    ADD COLUMN IF NOT EXISTS shadow BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_trade_decisions_shadow
    ON trade_decisions (shadow, created_at DESC);
