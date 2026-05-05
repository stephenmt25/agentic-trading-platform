import json
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from ..deps import get_timescale, get_current_user, get_decision_repo
from libs.reports.daily import generate_for_date
from libs.storage._timescale_client import TimescaleClient
from libs.storage.repositories.decision_repo import DecisionRepository
from libs.config import settings

router = APIRouter(tags=["paper-trading"])


class GenerateReportRequest(BaseModel):
    """Body for POST /paper-trading/reports/generate."""
    date: str  # YYYY-MM-DD, UTC

    @field_validator("date")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("date must be in YYYY-MM-DD format") from exc
        return v


@router.get("/mode")
async def get_trading_mode(user_id: str = Depends(get_current_user)):
    """Return the current trading mode configuration flags."""
    if settings.PAPER_TRADING_MODE:
        effective = "PAPER"
    elif settings.BINANCE_TESTNET or settings.COINBASE_SANDBOX:
        effective = "TESTNET"
    else:
        effective = "LIVE"

    return {
        "trading_enabled": settings.TRADING_ENABLED,
        "paper_trading_mode": settings.PAPER_TRADING_MODE,
        "binance_testnet": settings.BINANCE_TESTNET,
        "coinbase_sandbox": settings.COINBASE_SANDBOX,
        "effective_mode": effective,
    }


@router.get("/status")
async def get_paper_trading_status(
    user_id: str = Depends(get_current_user),
    db: TimescaleClient = Depends(get_timescale),
):
    """Return paper trading summary: days elapsed, metrics, and daily reports."""
    # Count days with reports (paper_trading_reports is a global table, not per-profile)
    days_row = await db.fetchrow(
        """
        SELECT COUNT(DISTINCT report_date) as days_count, MIN(report_date) as start_date
        FROM paper_trading_reports
        """,
    )
    days_elapsed = int(days_row["days_count"]) if days_row and days_row["days_count"] else 0
    start_date = str(days_row["start_date"]) if days_row and days_row["start_date"] else None

    # Get aggregate metrics
    metrics_row = await db.fetchrow("""
        SELECT
            COALESCE(SUM(total_trades), 0) as total_trades,
            COALESCE(AVG(win_rate), 0) as avg_win_rate,
            COALESCE(SUM(gross_pnl), 0) as total_gross_pnl,
            COALESCE(SUM(net_pnl), 0) as total_net_pnl,
            COALESCE(MAX(max_drawdown), 0) as max_drawdown,
            COALESCE(AVG(sharpe_ratio), 0) as avg_sharpe
        FROM paper_trading_reports
    """)

    # Get daily reports (most recent first)
    reports = await db.fetch(
        """
        SELECT * FROM paper_trading_reports
        ORDER BY report_date DESC LIMIT 30
        """,
    )

    return {
        "days_elapsed": days_elapsed,
        "target_days": 30,
        "start_date": start_date,
        "metrics": {
            "total_trades": int(metrics_row["total_trades"]) if metrics_row else 0,
            "avg_win_rate": round(float(metrics_row["avg_win_rate"]), 2) if metrics_row else 0,
            "total_gross_pnl": round(float(metrics_row["total_gross_pnl"]), 2) if metrics_row else 0,
            "total_net_pnl": round(float(metrics_row["total_net_pnl"]), 2) if metrics_row else 0,
            "max_drawdown": round(float(metrics_row["max_drawdown"]), 4) if metrics_row else 0,
            "avg_sharpe": round(float(metrics_row["avg_sharpe"]), 2) if metrics_row else 0,
        },
        "daily_reports": [
            {
                "id": r["id"],
                "report_date": str(r["report_date"]),
                "total_trades": r["total_trades"],
                "win_rate": round(float(r["win_rate"]), 2),
                "gross_pnl": round(float(r["gross_pnl"]), 2),
                "net_pnl": round(float(r["net_pnl"]), 2),
                "max_drawdown": round(float(r["max_drawdown"]), 4),
                "sharpe_ratio": round(float(r["sharpe_ratio"]), 2),
            }
            for r in reports
        ],
    }


@router.post("/reports/generate")
async def generate_report(
    payload: GenerateReportRequest,
    user_id: str = Depends(get_current_user),
    db: TimescaleClient = Depends(get_timescale),
):
    """Compute and upsert the daily report for a given UTC date.

    Same code path as the daily-report daemon (libs.reports.daily.generate_for_date)
    so manual and scheduled runs produce bit-identical rows. Re-running for an
    existing date overwrites that row.

    Returns:
      {
        "report_date": str,
        "wrote": bool,        # False if the day had no trades and no snapshots
        "report": {...} | None  # the row that was written / already exists
      }
    """
    requested = datetime.strptime(payload.date, "%Y-%m-%d").date()
    today_utc = datetime.now(timezone.utc).date()
    if requested > today_utc:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate a report for a future date ({requested} > {today_utc})",
        )

    wrote = await generate_for_date(db, requested)

    # Read back the row regardless of whether we wrote it now — there may
    # already be one from an earlier run, and the operator wants to see the
    # numbers either way.
    row = await db.fetchrow(
        "SELECT * FROM paper_trading_reports WHERE report_date = $1",
        requested,
    )

    report_payload: Optional[dict] = None
    if row:
        report_payload = {
            "id": row["id"],
            "report_date": str(row["report_date"]),
            "total_trades": row["total_trades"],
            "win_rate": round(float(row["win_rate"]), 2),
            "gross_pnl": round(float(row["gross_pnl"]), 2),
            "net_pnl": round(float(row["net_pnl"]), 2),
            "max_drawdown": round(float(row["max_drawdown"]), 4),
            "sharpe_ratio": round(float(row["sharpe_ratio"]), 2),
        }

    return {
        "report_date": str(requested),
        "wrote": wrote,
        "report": report_payload,
    }


def _serialize_decision(row: dict) -> dict:
    """Convert a trade_decisions DB row to a JSON-safe dict."""
    result = dict(row)
    result["event_id"] = str(result["event_id"])
    result["profile_id"] = str(result["profile_id"])
    result["input_price"] = float(result["input_price"]) if result.get("input_price") else None
    result["input_volume"] = float(result["input_volume"]) if result.get("input_volume") else None
    result["order_id"] = str(result["order_id"]) if result.get("order_id") else None
    result["created_at"] = result["created_at"].isoformat() if result.get("created_at") else None
    # JSONB columns come as dicts from asyncpg — ensure they're dicts not strings
    for col in ("indicators", "strategy", "regime", "agents", "gates", "profile_rules"):
        val = result.get(col)
        if isinstance(val, str):
            result[col] = json.loads(val)
    return result


@router.get("/decisions")
async def list_decisions(
    profile_id: Optional[str] = None,
    symbol: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    shadow: Optional[bool] = False,
    user_id: str = Depends(get_current_user),
    repo: DecisionRepository = Depends(get_decision_repo),
):
    """Return a paginated list of trade decisions (approved + blocked).

    `shadow` defaults to False so the live Decision Feed never surfaces
    profile-filtered (e.g. regime-mismatched) decisions. Pass shadow=true to
    see the shadow set, or shadow=null to include both.
    """
    capped_limit = min(limit, 200)
    rows = await repo.get_decisions(
        profile_id=profile_id,
        symbol=symbol,
        outcome=outcome,
        limit=capped_limit,
        offset=offset,
        shadow=shadow,
    )
    return [_serialize_decision(r) for r in rows]


@router.get("/decisions/{event_id}")
async def get_decision_detail(
    event_id: str,
    user_id: str = Depends(get_current_user),
    repo: DecisionRepository = Depends(get_decision_repo),
):
    """Return full decision trace for a single event."""
    row = await repo.get_decision(event_id)
    if not row:
        raise HTTPException(status_code=404, detail="Decision not found")
    return _serialize_decision(row)
