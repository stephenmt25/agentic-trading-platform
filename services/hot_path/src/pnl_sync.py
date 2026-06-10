import asyncio
import json
import time
from decimal import Decimal

import msgpack

from libs.core.schemas import AllocationPayload, DrawdownPayload
from libs.messaging.channels import PUBSUB_PNL_UPDATES
from libs.observability import get_logger

logger = get_logger("hot-path.pnl-sync")

# Grace window for the re-entry guard's symbol reconciliation. An order is
# emitted by the processor before its position row exists in the DB; until
# that row appears, the DB-derived symbol set must not be allowed to clobber
# the processor's optimistic add. 15s comfortably covers order→position-row
# latency even under DB load.
OPTIMISTIC_GRACE_S = 15.0


def reconcile_position_symbols(
    db_symbols: set,
    optimistic_ts: dict,
    now: float,
    grace_s: float = OPTIMISTIC_GRACE_S,
) -> tuple:
    """Reconcile the re-entry guard's open-symbol set against the DB.

    The processor optimistically adds a symbol the instant it emits an order;
    the position row only appears in ``db_symbols`` once execution has created
    it. A blind overwrite with ``db_symbols`` during that window would clobber
    a valid optimistic add and let a duplicate position open. So any symbol
    optimistically added within ``grace_s`` is preserved; optimistic
    timestamps past the window are pruned (the DB is authoritative by then).

    Returns ``(open_symbols, pruned_optimistic_ts)``.
    """
    recent = {s: t for s, t in optimistic_ts.items() if now - t < grace_s}
    open_symbols = set(db_symbols) | set(recent)
    return open_symbols, recent


class PnlSync:
    """Background task that keeps ProfileState risk fields hydrated from Redis.

    Subscribes to pubsub:pnl_updates for near-real-time updates.
    Also polls Redis keys every 5 seconds as fallback reconciliation.
    Updates: daily_realised_pnl_pct, current_drawdown_pct, current_allocation_pct,
    open_exposure_dollars (from positions table when position_repo is wired).
    """

    POLL_INTERVAL_S = 5

    def __init__(
        self, redis_client, pubsub_subscriber, state_cache, position_repo=None
    ):
        self._redis = redis_client
        self._subscriber = pubsub_subscriber
        self._state_cache = state_cache
        self._position_repo = position_repo

    async def run(self):
        """Start both the pubsub listener and the polling reconciliation."""
        await asyncio.gather(
            self._pubsub_listener(),
            self._poll_reconciliation(),
            return_exceptions=True,
        )

    async def _pubsub_listener(self):
        """Subscribe to PnL updates for live drawdown/allocation refresh.

        PNL_UPDATE messages are per-position, per-tick *unrealized* snapshots —
        treating them as deltas and accumulating into daily_realised_pnl_pct
        produced runaway values (see TECH-DEBT 2026-04-29). Daily realised P&L
        is now incremented only by services/pnl/src/closer.py on close. This
        listener exists so we can react to live PnL events for non-accumulating
        state (drawdown, allocation) — those are still hydrated by the poll
        loop below."""
        logger.info("PnL sync pubsub listener started (read-only; no accumulation)")

        async def on_message(data):
            try:
                if isinstance(data, bytes):
                    raw = msgpack.unpackb(data, raw=False)
                    message = raw
                elif isinstance(data, str):
                    message = json.loads(data)
                else:
                    message = data
                profile_id = message.get("profile_id")
                if not profile_id:
                    return
                logger.debug(
                    "PnL update observed",
                    profile_id=profile_id,
                    pct_return=message.get("pct_return"),
                )
            except Exception as e:
                logger.error("PnL sync pubsub callback error", error=str(e))

        try:
            await self._subscriber.subscribe(PUBSUB_PNL_UPDATES, on_message)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("PnL sync pubsub listener error", error=str(e))

    async def _poll_reconciliation(self):
        """Poll Redis keys for risk state reconciliation every 5 seconds."""
        logger.info("PnL sync polling reconciliation started")
        while True:
            try:
                for state in self._state_cache.itervalues():
                    if not state.is_active:
                        continue

                    pid = state.profile_id

                    # Daily PnL - read from the hash maintained by closer.py
                    # (single writer). Missing key means "no realised PnL today",
                    # so reset state to 0 — otherwise stale in-memory values
                    # would keep tripping CircuitBreaker after a manual reset.
                    daily_micro = await self._redis.hget(
                        f"pnl:daily:{pid}", "total_pct_micro"
                    )
                    if daily_micro is None:
                        state.daily_realised_pnl_pct = Decimal("0")
                    else:
                        state.daily_realised_pnl_pct = Decimal(
                            int(daily_micro)
                        ) / Decimal("1000000")

                    # Drawdown
                    dd_raw = await self._redis.get(f"risk:drawdown:{pid}")
                    if dd_raw:
                        parsed = DrawdownPayload.model_validate_json(dd_raw)
                        state.current_drawdown_pct = parsed.drawdown_pct_decimal()

                    # Allocation
                    alloc_raw = await self._redis.get(f"risk:allocation:{pid}")
                    if alloc_raw:
                        parsed = AllocationPayload.model_validate_json(alloc_raw)
                        state.current_allocation_pct = parsed.allocation_pct_decimal()

                    # Open exposure in dollars — drives the aggregate-exposure cap
                    # in RiskGate. Sum of cost_basis (entry_price × quantity) across
                    # currently open positions for this profile.
                    if self._position_repo is not None:
                        try:
                            open_rows = await self._position_repo.get_open_positions(
                                profile_id=pid
                            )
                            total = Decimal("0")
                            symbols: set = set()
                            for r in open_rows:
                                sym = r.get("symbol")
                                if sym:
                                    symbols.add(str(sym))
                                ep = r.get("entry_price")
                                qty = r.get("quantity")
                                if ep is None or qty is None:
                                    continue
                                total += Decimal(str(ep)) * Decimal(str(qty))
                            state.open_exposure_dollars = total
                            # Reconcile the re-entry guard's symbol set against
                            # the DB, preserving optimistic adds still inside
                            # the grace window so an in-flight order isn't
                            # clobbered into a duplicate position.
                            open_syms, pruned_ts = reconcile_position_symbols(
                                symbols,
                                state.open_position_symbols_optimistic_ts,
                                time.monotonic(),
                            )
                            state.open_position_symbols = open_syms
                            state.open_position_symbols_optimistic_ts = pruned_ts
                        except Exception as e:
                            logger.warning(
                                "Failed to refresh open positions",
                                profile_id=pid,
                                error=str(e),
                            )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("PnL sync poll error", error=str(e))

            await asyncio.sleep(self.POLL_INTERVAL_S)
