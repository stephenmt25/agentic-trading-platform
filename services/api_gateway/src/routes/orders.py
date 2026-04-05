from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from uuid import UUID
from ..deps import get_order_repo, get_current_user
from libs.storage.repositories import OrderRepository

router = APIRouter(tags=["orders"])


@router.get("/")
async def get_orders(
    profile_id: Optional[str] = None,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    repo: OrderRepository = Depends(get_order_repo),
):
    """List orders for the current user, with optional filters."""
    if limit > 200:
        limit = 200
    orders = await repo.get_orders_for_user(
        user_id=user_id,
        profile_id=profile_id,
        symbol=symbol,
        status=status,
        skip=skip,
        limit=limit,
    )
    return orders


@router.get("/{order_id}")
async def get_order_detail(
    order_id: UUID,
    user_id: str = Depends(get_current_user),
    repo: OrderRepository = Depends(get_order_repo),
):
    """Get order detail (must belong to a profile owned by the current user)."""
    order = await repo.get_order_for_user(order_id, user_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    user_id: str = Depends(get_current_user),
    repo: OrderRepository = Depends(get_order_repo),
):
    """Cancel a pending/submitted order (must belong to a profile owned by the current user)."""
    result = await repo.cancel_order_for_user(order_id, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found or not cancellable")
    return {"status": "cancelled", "order_id": str(order_id)}
