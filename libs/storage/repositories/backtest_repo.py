import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from ._repository_base import BaseRepository


def _coerce_uuid(value: Any) -> Optional[str]:
    """Cast a string-like user/profile id to a value the asyncpg UUID codec
    accepts. Returns None for empty/missing — letting the column store NULL
    rather than failing the insert. Pre-history rows had blank profile_id; we
    don't want to break new writes that have a real id."""
    if not value:
        return None
    return str(value)


def _coerce_dt(value: Any) -> Optional[datetime]:
    """asyncpg's TIMESTAMPTZ codec wants a datetime, not a string. Job
    payloads carry ISO strings so they survive Redis JSON encoding; convert
    back here. Returns None on missing/empty so the column stores NULL."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


class BacktestRepository(BaseRepository):
    async def save_result(self, result_data: Dict[str, Any]):
        query = """
        INSERT INTO backtest_results (
            job_id, profile_id, symbol, strategy_rules, total_trades,
            win_rate, avg_return, max_drawdown, sharpe, profit_factor,
            equity_curve, trades,
            created_by, start_date, end_date, timeframe
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
            $13, $14, $15, $16
        )
        ON CONFLICT (job_id) DO NOTHING
        """
        await self._execute(
            query,
            result_data["job_id"],
            result_data.get("profile_id", ""),
            result_data["symbol"],
            json.dumps(result_data.get("strategy_rules", {})),
            result_data["total_trades"],
            result_data["win_rate"],
            result_data["avg_return"],
            result_data["max_drawdown"],
            result_data["sharpe"],
            result_data["profit_factor"],
            json.dumps(result_data.get("equity_curve", [])),
            json.dumps(result_data.get("trades", [])),
            _coerce_uuid(result_data.get("created_by")),
            _coerce_dt(result_data.get("start_date")),
            _coerce_dt(result_data.get("end_date")),
            result_data.get("timeframe"),
        )

    async def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        query = """
        SELECT job_id, profile_id, symbol, strategy_rules, total_trades,
               win_rate, avg_return, max_drawdown, sharpe, profit_factor,
               equity_curve, trades, created_at,
               created_by, start_date, end_date, timeframe
        FROM backtest_results
        WHERE job_id = $1
        """
        row = await self._fetchrow(query, job_id)
        if not row:
            return None
        result = dict(row)
        result["strategy_rules"] = json.loads(result["strategy_rules"]) if isinstance(result["strategy_rules"], str) else result["strategy_rules"]
        result["equity_curve"] = json.loads(result["equity_curve"]) if isinstance(result["equity_curve"], str) else result["equity_curve"]
        result["trades"] = json.loads(result["trades"]) if isinstance(result["trades"], str) else result["trades"]
        return result

    async def get_history(
        self,
        user_id: Optional[str],
        profile_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return past completed backtest runs, newest-first.

        Filters:
          - user_id: required for user scoping. None returns historic
            (pre-migration-020) rows that have no created_by — the operator
            tooling uses this. Frontend always passes a user_id.
          - profile_id / symbol: optional secondary filters.

        Returns lightweight metric rows — full equity_curve / trades are
        loaded via get_result(job_id) when the user clicks "Load".
        """
        where = ["1=1"]
        params: list[Any] = []

        if user_id is not None:
            params.append(_coerce_uuid(user_id))
            where.append(f"created_by = ${len(params)}")
        if profile_id:
            params.append(profile_id)
            where.append(f"profile_id = ${len(params)}")
        if symbol:
            params.append(symbol)
            where.append(f"symbol = ${len(params)}")

        params.append(max(1, min(limit, 100)))
        limit_idx = len(params)

        query = f"""
        SELECT job_id, profile_id, symbol, total_trades,
               win_rate, avg_return, max_drawdown, sharpe, profit_factor,
               created_at, created_by, start_date, end_date, timeframe
        FROM backtest_results
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT ${limit_idx}
        """
        rows = await self._fetch(query, *params)
        return [dict(r) for r in rows]
