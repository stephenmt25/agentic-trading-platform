import json
from typing import Optional, Dict, Any
from ._repository_base import BaseRepository


class BacktestRepository(BaseRepository):
    async def save_result(self, result_data: Dict[str, Any]):
        query = """
        INSERT INTO backtest_results (
            job_id, profile_id, symbol, strategy_rules, total_trades,
            win_rate, avg_return, max_drawdown, sharpe, profit_factor,
            equity_curve, trades
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
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
        )

    async def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        query = """
        SELECT job_id, profile_id, symbol, strategy_rules, total_trades,
               win_rate, avg_return, max_drawdown, sharpe, profit_factor,
               equity_curve, trades, created_at
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
