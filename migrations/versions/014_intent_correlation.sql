-- Migration 014: Intent → Order → Position correlation chain
-- Adds nullable correlation columns so trade_decisions can be joined to the
-- resulting order and the position that opened/closed.
--
-- No foreign keys to `orders` because that table is a hypertable with a
-- composite primary key (order_id, created_at); FK enforcement happens in code.
-- Existing rows have NULL (decision lineage unknown); new rows populate forward.

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS decision_event_id UUID;

CREATE INDEX IF NOT EXISTS idx_orders_decision_event
    ON orders (decision_event_id)
    WHERE decision_event_id IS NOT NULL;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS order_id UUID;

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS decision_event_id UUID;

CREATE INDEX IF NOT EXISTS idx_positions_order_id
    ON positions (order_id)
    WHERE order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_positions_decision_event
    ON positions (decision_event_id)
    WHERE decision_event_id IS NOT NULL;
