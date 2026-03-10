import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient
from libs.observability import get_logger

from .middleware.auth import verify_jwt
from .middleware.rate_limit import RateLimiterMiddleware

from .routes import auth, profiles, orders, pnl, commands, ws, health

logger = get_logger("api-gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connections globally initialized
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()
    
    logger.info("API Gateway Started")
    yield
    
    # Teardown
    await timescale_client.close()
    logger.info("API Gateway shutdown")


def create_app() -> FastAPI:
    app = FastAPI(title="Control Plane API Gateway", lifespan=lifespan)

    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"], # NextJS Dashboard Default
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Note: Using Depends in routers directly provides better typing than top-level middleware,
    # but we can apply auth across the board, or per router.
    # Below Rate Limiter uses middleware to natively catch unauthenticated hits.
    
    # Initialize Rate Limiter
    # Unpack lazy Redis via settings 
    # Because middleware fires before lifespan, we init a separate client internally for the class
    rl_redis = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    app.middleware("http")(RateLimiterMiddleware(rl_redis, limit=60, window=60, auth_limit=10))

    # We apply auth dependency per route instead of global middleware for WS+Health isolation safety
    # FastAPI Depends on each route is safer than hacking Starlette Request states directly
    
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(ws.router)
    
    # Protected grouped Router
    api_router = FastAPI(dependencies=[])
    
    from fastapi import Depends
    from .deps import verify_token_dep
    
    # Secure API mounts
    secure_routes = [
        profiles.router,
        orders.router,
        pnl.router,
        commands.router
    ]
    
    for r in secure_routes:
        app.include_router(r, dependencies=[Depends(verify_token_dep)])

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("services.api-gateway.src.main:app", host="0.0.0.0", port=8000)
