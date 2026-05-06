import json
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from libs.core.schemas import BacktestRequest, BacktestResponse, strategy_rules_to_canonical
from libs.config import settings
from libs.storage import RedisClient
from libs.storage.repositories.backtest_repo import BacktestRepository
from ..deps import get_redis, get_current_user, get_backtest_repo

router = APIRouter()


@router.post("/", response_model=BacktestResponse)
async def create_backtest(
    req: BacktestRequest,
    user_id: str = Depends(get_current_user),
    redis=Depends(get_redis),
):
    """Submit a backtest job (authenticated, with queue depth limit)."""
    # Validate dates
    try:
        datetime.fromisoformat(req.start_date)
        datetime.fromisoformat(req.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO 8601.")

    # Backpressure: check queue depth before accepting
    queue_len = await redis.xlen("auto_backtest_queue")
    if queue_len >= settings.BACKTEST_MAX_QUEUE_DEPTH:
        raise HTTPException(
            status_code=429,
            detail="Backtest queue is full. Please try again later."
        )

    job_id = str(uuid.uuid4())
    canonical_rules = strategy_rules_to_canonical(req.strategy_rules)
    payload = {
        "job_id": job_id,
        "user_id": user_id,
        "symbol": req.symbol,
        "strategy_rules": canonical_rules,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "timeframe": req.timeframe,
        # Stringify Decimal to preserve precision through JSON — the consumer
        # (services/backtesting/src/job_runner.py) parses it back via Decimal(str(...)).
        "slippage_pct": str(req.slippage_pct),
    }

    await redis.xadd("auto_backtest_queue", {"data": json.dumps(payload)})

    await redis.set(
        f"backtest:status:{job_id}",
        json.dumps({"status": "queued", "job_id": job_id, "user_id": user_id}),
        ex=3600,
    )

    return BacktestResponse(job_id=job_id, status="queued")


@router.get("/history")
async def get_backtest_history(
    profile_id: Optional[str] = Query(None, description="Filter by trading profile id"),
    symbol: Optional[str] = Query(None, description="Filter by symbol, e.g. BTC/USDT"),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    repo: BacktestRepository = Depends(get_backtest_repo),
):
    """List the current user's past backtest runs, newest-first.

    Returns lightweight metric rows. Equity curve and trades are loaded on
    demand via GET /backtest/{job_id}. Pre-migration-020 rows have NULL
    created_by and are intentionally hidden from this user-scoped view.
    """
    rows = await repo.get_history(
        user_id=user_id, profile_id=profile_id, symbol=symbol, limit=limit,
    )
    # Decimal/datetime → JSON-friendly. asyncpg returns Decimal for the
    # NUMERIC columns; FastAPI's default encoder serializes Decimal as
    # string, which the frontend already handles for the live result fetch.
    out = []
    for r in rows:
        item = dict(r)
        for dt_field in ("created_at", "start_date", "end_date"):
            v = item.get(dt_field)
            item[dt_field] = v.isoformat() if v else None
        if item.get("created_by") is not None:
            item["created_by"] = str(item["created_by"])
        out.append(item)
    return {"items": out, "limit": limit}


@router.get("/{job_id}")
async def get_backtest_result(
    job_id: str,
    user_id: str = Depends(get_current_user),
    redis=Depends(get_redis),
    repo: BacktestRepository = Depends(get_backtest_repo),
):
    """Get backtest result.

    First checks the Redis status cache (1h TTL). When the cache has expired
    but a row exists in `backtest_results`, falls back to the DB so past
    runs loaded via the history panel still resolve. User-scoping is enforced
    by `created_by` on the DB row; Redis-cached entries store user_id inside
    the JSON payload.
    """
    cached = await redis.get(f"backtest:status:{job_id}")
    if cached:
        data = json.loads(cached)
        if data.get("user_id") != user_id:
            raise HTTPException(status_code=404, detail="Backtest job not found")
        return data

    row = await repo.get_result(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Backtest job not found")

    row_owner = row.get("created_by")
    if row_owner is None or str(row_owner) != user_id:
        # Pre-history rows or other users' runs are hidden.
        raise HTTPException(status_code=404, detail="Backtest job not found")

    # Shape the response to match the cached-status contract so the frontend
    # poll loop's `status === 'completed'` branch still applies.
    return {
        "status": "completed",
        "user_id": user_id,
        "job_id": row["job_id"],
        "profile_id": row.get("profile_id", ""),
        "symbol": row["symbol"],
        "strategy_rules": row.get("strategy_rules", {}),
        "total_trades": row["total_trades"],
        "win_rate": row["win_rate"],
        "avg_return": row["avg_return"],
        "max_drawdown": row["max_drawdown"],
        "sharpe": row["sharpe"],
        "profit_factor": row["profit_factor"],
        "equity_curve": row.get("equity_curve", []),
        "trades": row.get("trades", []),
        "start_date": row["start_date"].isoformat() if row.get("start_date") else None,
        "end_date": row["end_date"].isoformat() if row.get("end_date") else None,
        "timeframe": row.get("timeframe"),
    }
