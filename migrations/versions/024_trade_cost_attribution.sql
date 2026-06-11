-- Migration 024: Net-of-cost trade attribution (PR5 — closes 0.5)
--
-- realized_pnl is already net of entry+exit fees (and, post-PR1, computed from
-- the REAL exchange fill), so slippage is implicitly inside it. These columns
-- break the cost out so the per-strategy net-of-cost rollup is honest about WHY
-- a strategy is up or down, not just by how much.
--
--   * slippage_cost — adverse fill-vs-intended cost on the exit, signed so a
--                     positive value is a cost and a negative value is favourable
--                     slippage. Already reflected in realized_pnl (the fill price
--                     drives it) — this column is the attribution breakout, not an
--                     additional deduction.
--   * funding_cost  — perpetual-swap funding paid/received. This engine is 100%
--                     SPOT, where funding does not exist, so it is always 0 today.
--                     The column is a schema-ready placeholder for when perps land
--                     (Viability Plan Yield Harvester); no funding engine is built.

ALTER TABLE closed_trades ADD COLUMN IF NOT EXISTS slippage_cost DECIMAL(20,8) NOT NULL DEFAULT 0;
ALTER TABLE closed_trades ADD COLUMN IF NOT EXISTS funding_cost  DECIMAL(20,8) NOT NULL DEFAULT 0;

-- The net-of-cost rollup groups by profile over a recent window.
CREATE INDEX IF NOT EXISTS idx_closed_trades_profile_closed_at
    ON closed_trades (profile_id, closed_at DESC);
