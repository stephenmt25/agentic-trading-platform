import asyncio
import json
import msgpack
from decimal import Decimal
from libs.core.schemas import DrawdownPayload, AllocationPayload
from libs.messaging.channels import PUBSUB_PNL_UPDATES
from libs.observability import get_logger

logger = get_logger("hot-path.pnl-sync")


class PnlSync:
    """Background task that keeps ProfileState risk fields hydrated from Redis.

    Subscribes to pubsub:pnl_updates for near-real-time updates.
    Also polls Redis keys every 5 seconds as fallback reconciliation.
    Updates: daily_realised_pnl_pct, current_drawdown_pct, current_allocation_pct
    """

    POLL_INTERVAL_S = 5

    def __init__(self, redis_client, pubsub_subscriber, state_cache):
        self._redis = redis_client
        self._subscriber = pubsub_subscriber
        self._state_cache = state_cache

    async def run(self):
        """Start both the pubsub listener and the polling reconciliation."""
        await asyncio.gather(
            self._pubsub_listener(),
            self._poll_reconciliation(),
            return_exceptions=True,
        )

    async def _pubsub_listener(self):
        """Subscribe to PnL updates for near-real-time state hydration."""
        logger.info("PnL sync pubsub listener started")

        async def on_message(data):
            try:
                if isinstance(data, bytes):
                    # PubSubBroadcaster serialises with msgpack — decode accordingly
                    raw = msgpack.unpackb(data, raw=False)
                    message = raw
                elif isinstance(data, str):
                    message = json.loads(data)
                else:
                    message = data
                profile_id = message.get("profile_id")
                if not profile_id:
                    return

                state = self._state_cache.get(profile_id)
                if not state:
                    return

                pct_return = message.get("pct_return", message.get("roi_pct", 0.0))
                if pct_return:
                    pct_val = Decimal(str(pct_return))
                    # Use HINCRBY for atomic increment in Redis (avoids race with poll overwrite)
                    if self._redis:
                        # Store as integer micro-percent for HINCRBY (Redis only does int incr)
                        incr_micro = int(pct_val * 1_000_000)
                        new_micro = await self._redis.hincrby(
                            f"pnl:daily:{profile_id}", "total_pct_micro", incr_micro
                        )
                        state.daily_realised_pnl_pct = Decimal(new_micro) / Decimal("1000000")
                    else:
                        state.daily_realised_pnl_pct += pct_val
                    logger.debug(
                        "PnL sync updated from pubsub",
                        profile_id=profile_id,
                        daily_pnl=state.daily_realised_pnl_pct,
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

                    # Daily PnL - read from atomic hash, don't overwrite increments
                    daily_micro = await self._redis.hget(f"pnl:daily:{pid}", "total_pct_micro")
                    if daily_micro is not None:
                        state.daily_realised_pnl_pct = Decimal(int(daily_micro)) / Decimal("1000000")

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

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("PnL sync poll error", error=str(e))

            await asyncio.sleep(self.POLL_INTERVAL_S)
