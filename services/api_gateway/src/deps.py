from fastapi import Depends, Request
from libs.config import settings
from libs.storage import RedisClient, TimescaleClient
from libs.storage.repositories.profile_repo import ProfileRepository
from libs.storage.repositories.order_repo import OrderRepository
from libs.storage.repositories.pnl_repo import PnlRepository
from fastapi.security import HTTPBearer
from .middleware.auth import verify_jwt

security = HTTPBearer()

# Shared singleton instances — pool is initialized once in lifespan
_timescale_client: TimescaleClient | None = None

def get_redis() -> RedisClient:
    return RedisClient.get_instance(settings.REDIS_URL).get_connection()

async def get_timescale() -> TimescaleClient:
    global _timescale_client
    if _timescale_client is None:
        _timescale_client = TimescaleClient(settings.DATABASE_URL)
    if not _timescale_client._pool:
        await _timescale_client.init_pool()
    return _timescale_client

async def get_profile_repo() -> ProfileRepository:
    client = await get_timescale()
    return ProfileRepository(client)

async def get_order_repo() -> OrderRepository:
    client = await get_timescale()
    return OrderRepository(client)

async def get_pnl_repo() -> PnlRepository:
    client = await get_timescale()
    return PnlRepository(client)

def get_current_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise Exception("Unauthenticated via JWT middleware miss")
    return user_id

async def verify_token_dep(request: Request):
    await verify_jwt(request)
