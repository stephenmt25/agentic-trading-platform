from typing import Optional
from libs.core.enums import OrderStatus
from libs.storage.repositories import OrderRepository
from libs.observability import get_logger
import uuid

logger = get_logger("execution.ledger")

class OptimisticLedger:
    def __init__(self, repo: OrderRepository):
        self._repo = repo

    async def submit(self, order_id: uuid.UUID) -> bool:
        """Transitions PENDING -> SUBMITTED"""
        try:
            # We assume the initial create_order made it PENDING or direct insert
            # Here it's an update to SUBMITTED
            await self._repo.update_order_status(order_id, OrderStatus.SUBMITTED)
            logger.info("Order transitioned to SUBMITTED", order_id=str(order_id))
            return True
        except Exception as e:
            logger.error("Failed to submit in ledger", error=str(e), order_id=str(order_id))
            return False

    async def confirm(self, order_id: uuid.UUID, fill_price: float) -> bool:
        """Transitions SUBMITTED -> CONFIRMED"""
        try:
            await self._repo.update_order_status(order_id, OrderStatus.CONFIRMED, fill_price=fill_price)
            logger.info("Order transitioned to CONFIRMED", order_id=str(order_id), fill_price=fill_price)
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
