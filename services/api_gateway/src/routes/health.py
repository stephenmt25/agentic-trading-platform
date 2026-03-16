from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from libs.config import settings
from libs.storage import RedisClient

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health():
    return {"status": "healthy"}


@router.get("/ready")
async def get_ready(request: Request):
    """Readiness probe that verifies connectivity to Redis and Postgres."""
    checks: dict[str, str] = {}

    # -- Redis check --
    try:
        redis_instance = RedisClient.get_instance(settings.REDIS_URL)
        redis_ok = await redis_instance.health_check()
        checks["redis"] = "ok" if redis_ok else "unreachable"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    # -- Postgres / TimescaleDB check --
    try:
        timescale_client = getattr(request.app.state, "timescale_client", None)
        if timescale_client is None:
            checks["postgres"] = "not_initialized"
        else:
            pg_ok = await timescale_client.health_check()
            checks["postgres"] = "ok" if pg_ok else "unreachable"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
    )
