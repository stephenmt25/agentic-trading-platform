from uuid import UUID
from typing import List, Optional
from libs.core.models import Order
from libs.core.enums import OrderStatus
from ._repository_base import BaseRepository

class OrderRepository(BaseRepository):
    async def create_order(self, order: Order):
        query = """
        INSERT INTO orders (order_id, profile_id, symbol, side, quantity, price, status, exchange, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """
        await self._execute(
            query,
            order.order_id,
            str(order.profile_id),
            order.symbol,
            order.side.value,
            order.quantity,
            order.price,
            order.status.value,
            order.exchange,
            order.created_at
        )

    async def update_order_status(self, order_id: UUID, status: OrderStatus, fill_price=None, filled_at=None):
        query = """
        UPDATE orders 
        SET status = $1, fill_price = $2, filled_at = $3
        WHERE order_id = $4
        """
        await self._execute(query, status.value, fill_price, filled_at, order_id)

    async def get_orders_by_profile(self, profile_id: str) -> List[Order]:
        query = "SELECT * FROM orders WHERE profile_id = $1 ORDER BY created_at DESC"
        records = await self._fetch(query, profile_id)
        # Type conversions omitted for brevity pending complete model matching
        return []

    async def get_order(self, order_id: UUID) -> Optional[Order]:
        query = "SELECT * FROM orders WHERE order_id = $1"
        record = await self._fetchrow(query, order_id)
        if record:
            pass
        return None
