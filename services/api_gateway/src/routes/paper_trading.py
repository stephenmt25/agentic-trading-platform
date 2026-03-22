from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_timescale, get_current_user
from libs.storage._timescale_client import TimescaleClient

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])


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
