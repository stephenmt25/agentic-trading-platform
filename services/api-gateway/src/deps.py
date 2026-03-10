from fastapi import Depends, Request
from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, ProfileRepository, OrderRepository, PnlRepository
from fastapi.security import HTTPBearer
from .middleware.auth import verify_jwt

security = HTTPBearer()

def get_redis() -> RedisClient:
    return RedisClient.get_instance(settings.REDIS_URL).get_connection()

def get_timescale() -> TimescaleClient:
    # Uses a global instance for pooling bounds
    return TimescaleClient(settings.DATABASE_URL)

async def get_profile_repo() -> ProfileRepository:
    client = get_timescale()
    return ProfileRepository(client)

async def get_order_repo() -> OrderRepository:
    client = get_timescale()
    return OrderRepository(client)

async def get_pnl_repo() -> PnlRepository:
    client = get_timescale()
    return PnlRepository(client)

def get_current_user(request: Request) -> str:
    # Requires verify_jwt to have injected this
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise Exception("Unauthenticated via JWT middleware miss")
    return user_id

async def verify_token_dep(request: Request):
    await verify_jwt(request)
