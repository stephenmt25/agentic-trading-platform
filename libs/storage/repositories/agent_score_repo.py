from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import json
from ._repository_base import BaseRepository


class AgentScoreRepository(BaseRepository):
    """Read/write agent score history for charting overlays."""

    async def write_score(
        self,
        symbol: str,
        agent_name: str,
        score: Decimal,
        confidence: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        query = """
        INSERT INTO agent_score_history (symbol, agent_name, score, confidence, metadata)
        VALUES ($1, $2, $3, $4, $5)
        """
        meta_json = json.dumps(metadata) if metadata else None
        await self._execute(query, symbol, agent_name, score, confidence, meta_json)

    async def get_scores(
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
        # Order DESC + LIMIT to grab the NEWEST N rows. Caller re-sorts ASC for
        # chart display. Previous ASC order returned the OLDEST N — for any
        # agent with >limit rows, today's data was invisible to the chart.
        query = f"""
        SELECT symbol, agent_name, score, confidence, metadata, recorded_at
        FROM agent_score_history
        WHERE {where}
        ORDER BY recorded_at DESC
        LIMIT ${idx}
        """
        params.append(limit)

        records = await self._fetch(query, *params)
        results = []
        for r in records:
            row = dict(r)
            if row.get("metadata") and isinstance(row["metadata"], str):
                row["metadata"] = json.loads(row["metadata"])
            # Convert Decimal to float for JSON serialization
            if row.get("score") is not None:
                row["score"] = float(row["score"])
            if row.get("confidence") is not None:
                row["confidence"] = float(row["confidence"])
            if row.get("recorded_at"):
                row["recorded_at"] = row["recorded_at"].isoformat()
            results.append(row)
        return results
