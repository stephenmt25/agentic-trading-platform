from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Literal, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from libs.core.enums import OrderSide
from libs.core.schemas import OrderApprovedEvent
from libs.messaging import ORDERS_STREAM, StreamPublisher
from libs.storage.repositories import OrderRepository, ProfileRepository
from services.hot_path.src.kill_switch import KillSwitch

from ..deps import get_current_user, get_order_repo, get_profile_repo, get_redis

router = APIRouter(tags=["orders"])


class OrderSubmitRequest(BaseModel):
    profile_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    type: Literal["market", "limit"] = "limit"
    quantity: str = Field(..., description="Decimal-as-string; coerced to Decimal server-side")
    price: Optional[str] = Field(
        default=None,
        description="Required for limit orders; ignored for market orders.",
    )


class OrderSubmitResponse(BaseModel):
    order_id: str
    status: str
    submitted_at: str


@router.post("/", response_model=OrderSubmitResponse, status_code=202)
async def submit_order(
    body: OrderSubmitRequest,
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    redis=Depends(get_redis),
):
    """Manual order submission from /hot.

    Pipeline:
      1. Reject if kill switch is active (defense in depth — clients should
         already disable submit when the local kill state is armed, but
         server enforces).
      2. Verify the profile is owned by the authenticated user.
      3. Validate input (positive quantity, positive price for limit).
      4. Pre-allocate an order_id so the HTTP response can return it
         immediately. Publish OrderApprovedEvent on stream:orders for the
         executor to pick up — order_id flows through the event so the
         persisted Order row uses the same id (services/execution/src/executor.py).

    Returns HTTP 202 because execution happens asynchronously. Frontend
    optimistically inserts the order at this id and reconciles via
    polling api.orders.list.
    """
    if await KillSwitch.is_active(redis):
        raise HTTPException(status_code=403, detail="Kill switch is active — trading halted.")

    profile = await profile_repo.get_profile_for_user(body.profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found or not owned by current user")

    try:
        quantity = Decimal(body.quantity)
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=422, detail="Invalid quantity")
    if quantity <= 0:
        raise HTTPException(status_code=422, detail="Quantity must be positive")

    if body.type == "limit":
        if body.price is None:
            raise HTTPException(status_code=422, detail="Limit orders require a price")
        try:
            price = Decimal(body.price)
        except (InvalidOperation, TypeError):
            raise HTTPException(status_code=422, detail="Invalid price")
        if price <= 0:
            raise HTTPException(status_code=422, detail="Price must be positive")
    else:
        # Market order: executor uses the price field as the marker but the
        # actual fill price comes from the exchange. Use 0 as a sentinel —
        # OrderApprovedEvent's Price (Decimal) accepts it, executor ignores.
        # NOTE: market orders aren't fully wired through the executor's limit
        # path yet — flagged for follow-up; the endpoint accepts the shape so
        # the frontend doesn't need a re-deploy when it lands.
        price = Decimal("0")

    order_id = uuid4()
    submitted_at = datetime.utcnow()

    event = OrderApprovedEvent(
        profile_id=body.profile_id,
        symbol=body.symbol,
        side=OrderSide(body.side),
        quantity=quantity,
        price=price,
        order_id=order_id,
        timestamp_us=int(submitted_at.timestamp() * 1_000_000),
        source_service="api_gateway",
    )

    publisher = StreamPublisher(redis)
    await publisher.publish(ORDERS_STREAM, event)

    return OrderSubmitResponse(
        order_id=str(order_id),
        status="PENDING",
        submitted_at=submitted_at.isoformat() + "Z",
    )


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
