"""Position closer with agent outcome tagging.

When a position is closed (manually, by stop-loss, or by opposing signal),
this module:
1. Calls PositionRepository.close_position()
2. Computes final PnL
3. Tags the outcome against the contributing agents for weight feedback
"""

import json
from decimal import Decimal
from typing import Optional
from uuid import UUID

from libs.core.models import Position
from libs.core.agent_registry import AgentPerformanceTracker
from libs.storage.repositories import PositionRepository
from libs.observability import get_logger

from .calculator import PnLCalculator

logger = get_logger("pnl.closer")


class PositionCloser:
    def __init__(self, position_repo: PositionRepository, redis_client):
        self._position_repo = position_repo
        self._redis = redis_client
        self._tracker = AgentPerformanceTracker(redis_client)

    async def close(self, position: Position, exit_price: Decimal, taker_rate: Decimal, close_reason: str = "stop_loss"):
        """Close a position and record outcome for agent weight feedback."""
        # 1. Close in DB
        await self._position_repo.close_position(position.position_id, exit_price)

        # 2. Compute final PnL
        snapshot = PnLCalculator.calculate(
            position=position,
            current_price=exit_price,
            taker_rate=taker_rate,
        )

        # 3. Determine outcome
        outcome = "win" if snapshot.pct_return > 0 else "loss"

        # 4. Retrieve agent scores that were snapshotted at execution time
        agent_scores = await self._get_agent_scores(str(position.position_id))

        if agent_scores:
            # 5. Record closed position outcome for weight feedback
            await self._tracker.record_position_close(
                symbol=position.symbol,
                position_id=str(position.position_id),
                outcome=outcome,
                pnl_pct=snapshot.pct_return,
                agent_scores=agent_scores,
            )
            logger.info(
                "Position closed with agent outcome tagging",
                position_id=str(position.position_id),
                outcome=outcome,
                close_reason=close_reason,
                pnl_pct=round(snapshot.pct_return, 6),
                agents=list(agent_scores.keys()),
            )
        else:
            logger.info(
                "Position closed (no agent scores found)",
                position_id=str(position.position_id),
                outcome=outcome,
                close_reason=close_reason,
                pnl_pct=round(snapshot.pct_return, 6),
            )

        # 6. Clean up cached agent scores for this position
        await self._redis.delete(f"agent:position_scores:{position.position_id}")

        return snapshot

    async def _get_agent_scores(self, position_id: str) -> Optional[dict]:
        """Retrieve agent scores that were recorded at execution time."""
        try:
            raw = await self._redis.get(f"agent:position_scores:{position_id}")
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning("Failed to retrieve agent scores", error=str(e))
        return None
