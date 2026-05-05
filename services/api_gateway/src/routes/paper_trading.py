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


@router.get("/reports/{date}/detail")
async def get_report_detail(
    date: str,
    user_id: str = Depends(get_current_user),
    db: TimescaleClient = Depends(get_timescale),
):
    """Rich detail for a single day's report: summary + every closed trade
    on that UTC date with its full decision lineage.

    Joins closed_trades to trade_decisions on decision_event_id so each
    trade carries the agent attribution, gate trace, indicators, and
    regime that was captured at decision time.

    Filter is closed_at::date = $1 — i.e. trades that CLOSED that day,
    regardless of when they opened. That matches the summary row's
    semantics (the daily report rolls up closes).
    """
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc

    summary_row = await db.fetchrow(
        "SELECT * FROM paper_trading_reports WHERE report_date = $1",
        day,
    )
    summary: Optional[dict] = None
    if summary_row:
        summary = {
            "id": summary_row["id"],
            "report_date": str(summary_row["report_date"]),
            "total_trades": summary_row["total_trades"],
            "win_rate": round(float(summary_row["win_rate"]), 4),
            "gross_pnl": round(float(summary_row["gross_pnl"]), 2),
            "net_pnl": round(float(summary_row["net_pnl"]), 2),
            "max_drawdown": round(float(summary_row["max_drawdown"]), 4),
            "sharpe_ratio": round(float(summary_row["sharpe_ratio"]), 2),
        }

    trade_rows = await db.fetch(
        """
        SELECT
            ct.position_id::text         AS position_id,
            ct.symbol,
            ct.side,
            ct.entry_price,
            ct.entry_quantity,
            ct.exit_price,
            ct.opened_at,
            ct.closed_at,
            ct.holding_duration_s,
            ct.realized_pnl,
            ct.realized_pnl_pct,
            ct.outcome,
            ct.close_reason,
            ct.entry_regime,
            ct.entry_agent_scores::text  AS entry_agent_scores_json,
            td.event_id::text            AS decision_event_id,
            td.profile_id::text          AS decision_profile_id,
            td.indicators::text          AS decision_indicators_json,
            td.agents::text              AS decision_agents_json,
            td.gates::text               AS decision_gates_json,
            td.regime::text              AS decision_regime_json,
            td.profile_rules::text       AS profile_rules_json,
            td.created_at                AS decision_at,
            ord.order_id::text           AS order_id,
            ord.price                    AS order_intended_price,
            ord.fill_price               AS order_fill_price,
            ord.quantity                 AS order_quantity,
            ord.status                   AS order_status,
            ord.exchange                 AS order_exchange,
            ord.created_at               AS order_created_at,
            ord.filled_at                AS order_filled_at
        FROM closed_trades ct
        LEFT JOIN trade_decisions td ON ct.decision_event_id = td.event_id
        LEFT JOIN orders ord            ON ord.order_id        = ct.order_id
        WHERE ct.closed_at::date = $1
        ORDER BY ct.closed_at DESC
        """,
        day,
    )

    def _parse_jsonb(raw):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (ValueError, TypeError):
                return None
        return raw  # asyncpg sometimes hands back a dict directly

    def _build_order(r) -> Optional[dict]:
        if r["order_id"] is None:
            return None
        intended = float(r["order_intended_price"]) if r["order_intended_price"] is not None else None
        fill = float(r["order_fill_price"]) if r["order_fill_price"] is not None else None
        # Slippage = (fill - intended) / intended, signed. Positive on a BUY
        # means we paid more than intended; positive on a SELL means we got
        # better than intended. Caller can interpret with the side.
        slippage_pct: Optional[float] = None
        if intended and intended != 0 and fill is not None:
            slippage_pct = (fill - intended) / intended
        latency_ms: Optional[float] = None
        if r["order_created_at"] and r["order_filled_at"]:
            latency_ms = (r["order_filled_at"] - r["order_created_at"]).total_seconds() * 1000.0
        return {
            "order_id": r["order_id"],
            "intended_price": intended,
            "fill_price": fill,
            "quantity": float(r["order_quantity"]) if r["order_quantity"] is not None else None,
            "status": r["order_status"],
            "exchange": r["order_exchange"],
            "created_at": r["order_created_at"].isoformat() if r["order_created_at"] else None,
            "filled_at": r["order_filled_at"].isoformat() if r["order_filled_at"] else None,
            "fill_latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
            "slippage_pct": round(slippage_pct, 6) if slippage_pct is not None else None,
        }

    trades = [
        {
            "position_id": r["position_id"],
            "symbol": r["symbol"],
            "side": r["side"],
            "entry_price": float(r["entry_price"]),
            "entry_quantity": float(r["entry_quantity"]),
            "exit_price": float(r["exit_price"]),
            "opened_at": r["opened_at"].isoformat() if r["opened_at"] else None,
            "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
            "holding_duration_s": r["holding_duration_s"],
            "realized_pnl": round(float(r["realized_pnl"]), 4),
            "realized_pnl_pct": round(float(r["realized_pnl_pct"]), 6),
            "outcome": r["outcome"],
            "close_reason": r["close_reason"],
            "entry_regime": r["entry_regime"],
            "entry_agent_scores": _parse_jsonb(r["entry_agent_scores_json"]),
            "decision_event_id": r["decision_event_id"],
            "decision_profile_id": r["decision_profile_id"],
            "decision_at": r["decision_at"].isoformat() if r["decision_at"] else None,
            "decision_indicators": _parse_jsonb(r["decision_indicators_json"]),
            "decision_agents": _parse_jsonb(r["decision_agents_json"]),
            "decision_gates": _parse_jsonb(r["decision_gates_json"]),
            "decision_regime": _parse_jsonb(r["decision_regime_json"]),
            "profile_rules": _parse_jsonb(r["profile_rules_json"]),
            "order": _build_order(r),
        }
        for r in trade_rows
    ]

    # Blocked decisions on this day — counts-by-outcome for at-a-glance,
    # plus a recent sample so the operator can drill into specific blocks.
    # `shadow` rows are pure shadow comparisons (C.4 SHADOW), exclude them.
    blocked_count_rows = await db.fetch(
        """
        SELECT outcome, COUNT(*) AS count
        FROM trade_decisions
        WHERE created_at::date = $1
            AND outcome != 'APPROVED'
            AND (shadow IS NULL OR shadow = FALSE)
        GROUP BY outcome
        ORDER BY count DESC
        """,
        day,
    )
    blocked_counts = {r["outcome"]: int(r["count"]) for r in blocked_count_rows}

    blocked_recent_rows = await db.fetch(
        """
        SELECT
            event_id::text       AS event_id,
            created_at,
            symbol,
            profile_id::text     AS profile_id,
            outcome,
            gates::text          AS gates_json
        FROM trade_decisions
        WHERE created_at::date = $1
            AND outcome != 'APPROVED'
            AND (shadow IS NULL OR shadow = FALSE)
        ORDER BY created_at DESC
        LIMIT 100
        """,
        day,
    )
    blocked_recent = [
        {
            "event_id": r["event_id"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "symbol": r["symbol"],
            "profile_id": r["profile_id"],
            "outcome": r["outcome"],
            "gates": _parse_jsonb(r["gates_json"]),
        }
        for r in blocked_recent_rows
    ]

    return {
        "report_date": str(day),
        "summary": summary,
        "trades": trades,
        "blocked": {
            "counts_by_outcome": blocked_counts,
            "total": sum(blocked_counts.values()),
            "recent": blocked_recent,
        },
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
