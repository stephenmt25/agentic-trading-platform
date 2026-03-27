import uuid as _uuid
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient
from libs.observability import get_logger
from libs.core.exceptions import (
    PraxisBaseError,
    CircuitBreakerTriggeredError,
    RiskGateBlockedError,
    BlacklistBlockedError,
    ValidationError,
    ExchangeError,
    ExchangeRateLimitError,
    OrderExecutionError,
)

from .middleware.rate_limit import RateLimiterMiddleware
from .routes import auth, profiles, orders, pnl, commands, ws, health, exchange_keys, paper_trading, backtest, agents, docs_chat

logger = get_logger("api-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Block startup with insecure default SECRET_KEY in all modes
    if not settings.is_secret_key_secure():
        raise RuntimeError(
            "FATAL: SECRET_KEY is set to the insecure default. "
            "Set PRAXIS_SECRET_KEY to a secure random value (32+ bytes) before starting. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    # Require a dedicated REFRESH_SECRET_KEY separate from SECRET_KEY
    if not settings.REFRESH_SECRET_KEY:
        raise RuntimeError(
            "FATAL: PRAXIS_REFRESH_SECRET_KEY is not set. "
            "It must be a separate secret from SECRET_KEY for refresh token security."
        )

    # Initialize shared clients and store on app.state
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()
    app.state.timescale_client = timescale_client

    logger.info("API Gateway Started")
    yield

    # Teardown
    await timescale_client.close()
    logger.info("API Gateway shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Control Plane API Gateway",
        version="1.0.0",
        description="Praxis Trading Platform API",
        lifespan=lifespan,
    )

    # CORS Configuration — configurable via settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Rate Limiter middleware
    rl_redis = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    app.middleware("http")(RateLimiterMiddleware(rl_redis, limit=60, window=60, auth_limit=10))

    # ------------------------------------------------------------------
    # Request ID middleware — adds X-Request-ID to every response
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(_uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ------------------------------------------------------------------
    # Global exception handlers — map domain exceptions to HTTP codes
    # ------------------------------------------------------------------
    @app.exception_handler(CircuitBreakerTriggeredError)
    async def circuit_breaker_handler(request: Request, exc: CircuitBreakerTriggeredError):
        return JSONResponse(status_code=503, content={"detail": "Circuit breaker triggered", "error": "circuit_breaker"})

    @app.exception_handler(RiskGateBlockedError)
    async def risk_gate_handler(request: Request, exc: RiskGateBlockedError):
        return JSONResponse(status_code=403, content={"detail": "Blocked by risk gate", "error": "risk_gate_blocked"})

    @app.exception_handler(BlacklistBlockedError)
    async def blacklist_handler(request: Request, exc: BlacklistBlockedError):
        return JSONResponse(status_code=403, content={"detail": "Asset is blacklisted", "error": "blacklisted"})

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError):
        return JSONResponse(status_code=422, content={"detail": str(exc), "error": "validation_failed"})

    @app.exception_handler(ExchangeRateLimitError)
    async def exchange_rate_limit_handler(request: Request, exc: ExchangeRateLimitError):
        return JSONResponse(status_code=429, content={"detail": "Exchange rate limit exceeded", "error": "exchange_rate_limit"})

    @app.exception_handler(ExchangeError)
    async def exchange_error_handler(request: Request, exc: ExchangeError):
        return JSONResponse(status_code=502, content={"detail": "Exchange communication error", "error": "exchange_error"})

    @app.exception_handler(OrderExecutionError)
    async def order_execution_handler(request: Request, exc: OrderExecutionError):
        return JSONResponse(status_code=500, content={"detail": "Order execution failed", "error": "order_execution"})

    @app.exception_handler(PraxisBaseError)
    async def praxis_base_handler(request: Request, exc: PraxisBaseError):
        return JSONResponse(status_code=500, content={"detail": "Internal error", "error": "internal"})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception", error=str(exc), path=request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # ------------------------------------------------------------------
    # Public routes (no auth)
    # ------------------------------------------------------------------
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(ws.router)
    app.include_router(docs_chat.router)

    # ------------------------------------------------------------------
    # Protected routes — all behind JWT auth via verify_token_dep
    # ------------------------------------------------------------------
    from .deps import verify_token_dep

    secure_routes = [
        (profiles.router, "/profiles"),
        (orders.router, "/orders"),
        (pnl.router, "/pnl"),
        (commands.router, "/commands"),
        (exchange_keys.router, "/exchange-keys"),
        (paper_trading.router, "/paper-trading"),
        (agents.router, "/agents"),
        (backtest.router, "/backtest"),
    ]

    for router, prefix in secure_routes:
        route_prefix = "" if router.prefix else prefix
        app.include_router(router, prefix=route_prefix, dependencies=[Depends(verify_token_dep)])

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("services.api_gateway.src.main:app", host="0.0.0.0", port=8000)
