from uuid import UUID
from typing import List, Optional
from libs.core.models import Order
from libs.core.enums import OrderStatus, OrderSide
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

    async def get_orders_for_user(
        self, user_id: str,
        profile_id: str = None,
        symbol: str = None,
        status: str = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[dict]:
        conditions = ["o.profile_id = tp.profile_id", "tp.user_id = $1"]
        params: list = [UUID(user_id)]
        idx = 2

        if profile_id:
            conditions.append(f"o.profile_id = ${idx}")
            params.append(UUID(profile_id))
            idx += 1
        if symbol:
            conditions.append(f"o.symbol = ${idx}")
            params.append(symbol)
            idx += 1
        if status:
            conditions.append(f"o.status = ${idx}")
            params.append(status)
            idx += 1

        where = " AND ".join(conditions)
        query = f"""
        SELECT o.* FROM orders o
        JOIN trading_profiles tp ON o.profile_id = tp.profile_id
        WHERE {where}
        ORDER BY o.created_at DESC
        OFFSET ${idx} LIMIT ${idx + 1}
        """
        params.extend([skip, limit])
        records = await self._fetch(query, *params)
        return [dict(r) for r in records]

    async def get_order_for_user(self, order_id: UUID, user_id: str) -> Optional[dict]:
        query = """
        SELECT o.* FROM orders o
        JOIN trading_profiles tp ON o.profile_id = tp.profile_id
        WHERE o.order_id = $1 AND tp.user_id = $2
        """
        record = await self._fetchrow(query, order_id, UUID(user_id))
        return dict(record) if record else None

    async def cancel_order_for_user(self, order_id: UUID, user_id: str) -> Optional[dict]:
        query = """
        UPDATE orders SET status = $1
        FROM trading_profiles tp
        WHERE orders.order_id = $2
          AND orders.profile_id = tp.profile_id
          AND tp.user_id = $3
          AND orders.status IN ($4, $5)
        RETURNING orders.*
        """
        record = await self._fetchrow(
            query,
            OrderStatus.CANCELLED.value,
            order_id,
            UUID(user_id),
            OrderStatus.PENDING.value,
            OrderStatus.SUBMITTED.value,
        )
        return dict(record) if record else None

    # Legacy methods for inter-service use
    async def get_orders_by_profile(self, profile_id: str) -> list:
        query = "SELECT * FROM orders WHERE profile_id = $1 ORDER BY created_at DESC"
        records = await self._fetch(query, profile_id)
        return [dict(r) for r in records]

    async def get_order(self, order_id: UUID) -> Optional[dict]:
        query = "SELECT * FROM orders WHERE order_id = $1"
        record = await self._fetchrow(query, order_id)
        return dict(record) if record else None
