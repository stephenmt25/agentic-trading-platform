-- Migration 023: Position close lifecycle (PR1 — real exchange close)
--
-- Kills the "phantom close": before this slice, closing a position only
-- updated the DB and never sent a closing order to the exchange. Closes now
-- route through the execution OMS as a reduce-only order and the DB close is
-- finalised on fill confirmation. That introduces an in-flight state and a
-- link from a position to the order that closes it.
--
--   * close_order_id      — the reduce-only order published to flatten this
--                           position. Set when the position transitions
--                           OPEN -> PENDING_CLOSE; the matching fill finalises
--                           PENDING_CLOSE -> CLOSED.
--   * protective_order_id — an optional exchange-resident reduce-only stop
--                           placed at open (defense-in-depth; gated behind
--                           PRAXIS_PROTECTIVE_STOP_ENABLED, default off). TEXT,
--                           because it stores the EXCHANGE's order id (a venue
--                           string), unlike close_order_id which is our UUID.
--
-- The new in-flight status value 'PENDING_CLOSE' needs no DDL: positions.status
-- is unconstrained TEXT (see migration 001). PositionStatus in
-- libs/core/enums.py is the source of truth for the allowed values.

ALTER TABLE positions ADD COLUMN IF NOT EXISTS close_order_id UUID NULL;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS protective_order_id TEXT NULL;

-- The exit monitor and rehydrate load only the actively-monitored set. A
-- PENDING_CLOSE position is excluded from monitoring (it is awaiting its close
-- fill) but this partial index keeps both the OPEN filter and any
-- in-flight-close lookups cheap.
CREATE INDEX IF NOT EXISTS idx_positions_open
    ON positions (profile_id)
    WHERE status = 'OPEN';

CREATE INDEX IF NOT EXISTS idx_positions_pending_close
    ON positions (close_order_id)
    WHERE status = 'PENDING_CLOSE';
