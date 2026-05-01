"""Repository for debate_cycles + debate_transcripts.

Persists the full conversational trace of each adversarial debate cycle.
debate_cycles holds the cycle-level summary (judge score, confidence,
market context snapshot). debate_transcripts holds per-round bull/bear
arguments and convictions. CASCADE delete from cycle to rounds.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from ._repository_base import BaseRepository


class _JsonEncoder(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, "item"):
            return o.item()
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _dumps(obj) -> str:
    return json.dumps(obj, cls=_JsonEncoder)


class DebateRepository(BaseRepository):
    async def write_cycle(
        self,
        cycle_id: UUID,
        symbol: str,
        final_score: Decimal,
        final_confidence: Decimal,
        judge_reasoning: str,
        num_rounds: int,
        total_latency_ms: float,
        market_context: dict,
        rounds: List[dict],   # each: {round_num, bull_argument, bull_conviction, bear_argument, bear_conviction}
    ) -> None:
        cycle_q = """
        INSERT INTO debate_cycles
            (cycle_id, symbol, final_score, final_confidence, judge_reasoning,
             num_rounds, total_latency_ms, market_context)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        await self._execute(
            cycle_q,
            cycle_id,
            symbol,
            final_score,
            final_confidence,
            judge_reasoning,
            num_rounds,
            Decimal(str(total_latency_ms)),
            _dumps(market_context),
        )

        if rounds:
            round_q = """
            INSERT INTO debate_transcripts
                (cycle_id, symbol, round_num, bull_argument, bull_conviction,
                 bear_argument, bear_conviction)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            for r in rounds:
                await self._execute(
                    round_q,
                    cycle_id,
                    symbol,
                    int(r["round_num"]),
                    str(r["bull_argument"]),
                    Decimal(str(r["bull_conviction"])),
                    str(r["bear_argument"]),
                    Decimal(str(r["bear_conviction"])),
                )

    async def get_cycle_with_rounds(self, cycle_id: UUID) -> Optional[Dict[str, Any]]:
        cycle = await self._fetchrow(
            "SELECT * FROM debate_cycles WHERE cycle_id = $1", cycle_id
        )
        if not cycle:
            return None
        rounds = await self._fetch(
            "SELECT * FROM debate_transcripts WHERE cycle_id = $1 ORDER BY round_num",
            cycle_id,
        )
        return {"cycle": dict(cycle), "rounds": [dict(r) for r in rounds]}

    async def get_recent_cycles(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if symbol:
            rows = await self._fetch(
                """
                SELECT * FROM debate_cycles
                WHERE symbol = $1
                ORDER BY recorded_at DESC
                LIMIT $2
                """,
                symbol,
                limit,
            )
        else:
            rows = await self._fetch(
                """
                SELECT * FROM debate_cycles
                ORDER BY recorded_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [dict(r) for r in rows]
