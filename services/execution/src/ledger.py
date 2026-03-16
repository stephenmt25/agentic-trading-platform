import json
from typing import Optional
from libs.core.enums import OrderStatus
from libs.storage.repositories import OrderRepository
from libs.observability import get_logger
import uuid

logger = get_logger("execution.ledger")

class OptimisticLedger:
    def __init__(self, repo: OrderRepository, redis_client=None):
        self._repo = repo
        self._redis = redis_client

    async def submit(self, order_id: uuid.UUID) -> bool:
        """Transitions PENDING -> SUBMITTED"""
        try:
            await self._repo.update_order_status(order_id, OrderStatus.SUBMITTED)
            logger.info("Order transitioned to SUBMITTED", order_id=str(order_id))
            return True
        except Exception as e:
            logger.error("Failed to submit in ledger", error=str(e), order_id=str(order_id))
            return False

    async def confirm(self, order_id: uuid.UUID, fill_price: float, profile_id: str = None, quantity: float = None) -> bool:
        """Transitions SUBMITTED -> CONFIRMED and updates allocation tracking."""
        try:
            await self._repo.update_order_status(order_id, OrderStatus.CONFIRMED, fill_price=fill_price)
            logger.info("Order transitioned to CONFIRMED", order_id=str(order_id), fill_price=fill_price)

            # Sprint 10.3: Write allocation tracking to Redis after recording fills
            if self._redis and profile_id and quantity is not None:
                await self._update_allocation(profile_id, quantity)

            return True
        except Exception as e:
            logger.error("Failed to confirm in ledger", error=str(e), order_id=str(order_id))
            return False

    async def rollback(self, order_id: uuid.UUID, reason: str) -> bool:
        """Transitions SUBMITTED -> ROLLED_BACK"""
        try:
            await self._repo.update_order_status(order_id, OrderStatus.ROLLED_BACK)
            logger.warning("Order transitioned to ROLLED_BACK", order_id=str(order_id), reason=reason)
            return True
        except Exception as e:
            logger.error("Failed to rollback in ledger", error=str(e), order_id=str(order_id))
            return False

    # Lua script for atomic allocation increment
    _ALLOC_INCR_SCRIPT = """
    local key = KEYS[1]
    local incr = tonumber(ARGV[1])
    local ttl = tonumber(ARGV[2])
    local raw = redis.call('GET', key)
    local data
    if raw then
        data = cjson.decode(raw)
        data['allocated_qty'] = (data['allocated_qty'] or 0) + incr
    else
        data = {allocated_qty = incr}
    end
    redis.call('SET', key, cjson.encode(data), 'EX', ttl)
    return tostring(data['allocated_qty'])
    """

    async def _update_allocation(self, profile_id: str, quantity: float):
        """Update allocation tracking in Redis atomically (Sprint 10.3)."""
        if not self._redis:
            return
        try:
            key = f"risk:allocation:{profile_id}"
            await self._redis.eval(
                self._ALLOC_INCR_SCRIPT, 1, key, str(quantity), "86400"
            )
        except Exception as e:
            logger.error("Failed to update allocation", error=str(e), profile_id=profile_id)
