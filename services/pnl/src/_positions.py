"""Shared DB-record -> Position hydration for the PnL service.

Used by both the tick handler (main.py) and the close-fill consumer
(executed_consumer.py). Populates order_id / decision_event_id so the
closed_trades audit chain is complete for auto-closed positions too (the old
inline helper dropped them, leaving NULLs in the ledger).
"""

from decimal import Decimal

from libs.core.enums import OrderSide, PositionStatus
from libs.core.models import Position


def record_to_position(rec) -> Position:
    """Convert an asyncpg Record (SELECT * FROM positions) to a Position."""
    return Position(
        position_id=rec["position_id"],
        profile_id=str(rec["profile_id"]),
        symbol=rec["symbol"],
        side=OrderSide(rec["side"]),
        entry_price=Decimal(str(rec["entry_price"])),
        quantity=Decimal(str(rec["quantity"])),
        entry_fee=Decimal(str(rec["entry_fee"])),
        opened_at=rec["opened_at"],
        status=(
            PositionStatus(rec["status"]) if rec.get("status") else PositionStatus.OPEN
        ),
        closed_at=rec.get("closed_at"),
        exit_price=Decimal(str(rec["exit_price"])) if rec.get("exit_price") else None,
        order_id=rec.get("order_id"),
        decision_event_id=rec.get("decision_event_id"),
        close_order_id=rec.get("close_order_id"),
        protective_order_id=rec.get("protective_order_id"),
    )
