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

    async def _update_allocation(self, profile_id: str, quantity: float):
        """Update allocation tracking in Redis (Sprint 10.3)."""
        if not self._redis:
            return
        try:
            key = f"risk:allocation:{profile_id}"
            raw = await self._redis.get(key)
            if raw:
                data = json.loads(raw)
                data["allocation_pct"] = data.get("allocation_pct", 0.0) + quantity
            else:
                data = {"allocation_pct": quantity}
            await self._redis.set(key, json.dumps(data), ex=86400)
        except Exception as e:
            logger.error("Failed to update allocation", error=str(e), profile_id=profile_id)
