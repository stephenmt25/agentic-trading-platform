from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from ._repository_base import BaseRepository


class WeightHistoryRepository(BaseRepository):
    """Read/write agent weight history for performance evolution charts."""

    async def write_weights(
        self,
        symbol: str,
        weights: Dict[str, Dict[str, Any]],
    ) -> None:
        """Persist a snapshot of agent weights and accuracy.

        weights: {"ta": {"weight": 0.2, "ewma": 0.65, "samples": 42}, ...}
        """
        for agent_name, data in weights.items():
            query = """
            INSERT INTO agent_weight_history (symbol, agent_name, weight, ewma_accuracy, sample_count)
            VALUES ($1, $2, $3, $4, $5)
            """
            await self._execute(
                query,
                symbol,
                agent_name,
                Decimal(str(data["weight"])),
                Decimal(str(data.get("ewma", 0))),
                int(data.get("samples", 0)),
            )

    async def get_history(
        self,
        symbol: str,
        agent_name: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        conditions = ["symbol = $1"]
        params: list = [symbol]
        idx = 2

        if agent_name:
            conditions.append(f"agent_name = ${idx}")
            params.append(agent_name)
            idx += 1

        if start:
            conditions.append(f"recorded_at >= ${idx}")
            params.append(start)
            idx += 1

        if end:
            conditions.append(f"recorded_at <= ${idx}")
            params.append(end)
            idx += 1

        where = " AND ".join(conditions)
        query = f"""
        SELECT symbol, agent_name, weight, ewma_accuracy, sample_count, recorded_at
        FROM agent_weight_history
        WHERE {where}
        ORDER BY recorded_at ASC
        LIMIT ${idx}
        """
        params.append(limit)

        records = await self._fetch(query, *params)
        results = []
        for r in records:
            row = dict(r)
            row["weight"] = float(row["weight"])
            row["ewma_accuracy"] = float(row["ewma_accuracy"])
            if row.get("recorded_at"):
                row["recorded_at"] = row["recorded_at"].isoformat()
            results.append(row)
        return results
