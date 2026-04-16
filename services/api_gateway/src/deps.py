from fastapi import Depends, HTTPException, Request
from libs.config import settings
from libs.storage import RedisClient, TimescaleClient
from libs.storage.repositories.profile_repo import ProfileRepository
from libs.storage.repositories.order_repo import OrderRepository
from libs.storage.repositories.pnl_repo import PnlRepository
from libs.storage.repositories.decision_repo import DecisionRepository
from libs.storage.repositories.market_data_repo import MarketDataRepository
from libs.storage.repositories.agent_score_repo import AgentScoreRepository
from libs.storage.repositories.weight_history_repo import WeightHistoryRepository
from fastapi.security import HTTPBearer
from .middleware.auth import verify_jwt

security = HTTPBearer()


def get_redis() -> RedisClient:
    return RedisClient.get_instance(settings.REDIS_URL).get_connection()


async def get_timescale(request: Request) -> TimescaleClient:
    """Return the lifespan-managed TimescaleClient from app.state."""
    client = getattr(request.app.state, "timescale_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return client


async def get_profile_repo(request: Request) -> ProfileRepository:
    client = await get_timescale(request)
    return ProfileRepository(client)


async def get_order_repo(request: Request) -> OrderRepository:
    client = await get_timescale(request)
    return OrderRepository(client)


async def get_pnl_repo(request: Request) -> PnlRepository:
    client = await get_timescale(request)
    return PnlRepository(client)


async def get_decision_repo(request: Request) -> DecisionRepository:
    client = await get_timescale(request)
    return DecisionRepository(client)


async def get_market_data_repo(request: Request) -> MarketDataRepository:
    client = await get_timescale(request)
    return MarketDataRepository(client)


async def get_agent_score_repo(request: Request) -> AgentScoreRepository:
    client = await get_timescale(request)
    return AgentScoreRepository(client)


async def get_weight_history_repo(request: Request) -> WeightHistoryRepository:
    client = await get_timescale(request)
    return WeightHistoryRepository(client)


def get_current_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


async def verify_token_dep(request: Request):
    if request.method == "OPTIONS":
        return
    await verify_jwt(request)
