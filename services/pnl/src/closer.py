"""Position closer with full outcome persistence.

When a position is closed (manually, by stop-loss, by take-profit, by time-exit,
or by an opposing signal), this module:
  1. Closes the position in DB (positions.status = CLOSED)
  2. Computes final PnL via PnLCalculator
  3. Reads the position-time snapshot from Redis (entry agent scores + regime)
  4. Writes a closed_trades row linking the entire decision lineage to realized PnL
  5. Records the outcome to AgentPerformanceTracker for weight EWMA updates
  6. Cleans up the Redis snapshot key

Step (4) is the new persistence write added in PR1 — never raises (failures are
logged) so the existing close path remains uninterrupted.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple
from uuid import UUID

from libs.core.agent_registry import AgentPerformanceTracker
from libs.core.models import Position
from libs.core.notional import profile_notional
from libs.observability import get_logger
from libs.storage.repositories import ClosedTradeRepository, PositionRepository
from libs.storage.repositories.profile_repo import ProfileRepository

from .calculator import PnLCalculator

logger = get_logger("pnl.closer")

_ZERO = Decimal("0")


class PositionCloser:
    def __init__(
        self,
        position_repo: PositionRepository,
        redis_client,
        closed_trade_repo: Optional[ClosedTradeRepository] = None,
        profile_repo: Optional[ProfileRepository] = None,
    ):
        self._position_repo = position_repo
        self._redis = redis_client
        self._tracker = AgentPerformanceTracker(redis_client)
        self._closed_trade_repo = closed_trade_repo
        self._profile_repo = profile_repo
        # Cache profile notional capital so we don't hit the DB on every close.
        # Populated lazily; refreshed whenever a lookup misses or returns 0.
        self._notional_cache: dict[str, Decimal] = {}

    async def close(self, position: Position, exit_price: Decimal, taker_rate: Decimal, close_reason: str = "stop_loss"):
        """Close a position, persist the closed_trades audit row, and tag agent outcomes."""
        # Single timestamp for both the DB close and the closed_trades row
        closed_at = datetime.now(timezone.utc)

        # 1. Close in DB
        await self._position_repo.close_position(position.position_id, exit_price)

        # 2. Compute final PnL
        snapshot = PnLCalculator.calculate(
            position=position,
            current_price=exit_price,
            taker_rate=taker_rate,
        )

        # 3. Determine outcome from the post-tax pct return (matches existing tracker semantics)
        if snapshot.pct_return > _ZERO:
            outcome = "win"
        elif snapshot.pct_return < _ZERO:
            outcome = "loss"
        else:
            outcome = "breakeven"

        # 4. Retrieve entry-time snapshot (agent scores + regime) from Redis
        agent_scores, entry_regime = await self._get_position_snapshot(str(position.position_id))

        # 5. Persist closed_trades audit row (PR1 ledger). Never raises.
        await self._write_closed_trade_row(
            position=position,
            exit_price=exit_price,
            taker_rate=taker_rate,
            close_reason=close_reason,
            closed_at=closed_at,
            snapshot=snapshot,
            agent_scores=agent_scores,
            entry_regime=entry_regime,
            outcome=outcome,
        )

        # 6a. Increment the daily realised P&L counter for the profile.
        # Single writer for `pnl:daily:<pid>:total_pct_micro` — feeds CircuitBreaker.
        # Counter unit is loss-as-fraction-of-equity (notional), NOT per-trade
        # return — CircuitBreaker.check compares it directly against
        # `circuit_breaker_daily_loss_pct` which is in equity-fraction units.
        await self._bump_daily_realised_pnl(
            profile_id=str(position.profile_id),
            realized_pnl_dollars=snapshot.net_pre_tax,
            closed_at=closed_at,
        )

        # 6. Record outcome for weight feedback (existing behavior)
        if agent_scores:
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
                entry_regime=entry_regime,
            )
        else:
            logger.info(
                "Position closed (no agent scores found)",
                position_id=str(position.position_id),
                outcome=outcome,
                close_reason=close_reason,
                pnl_pct=round(snapshot.pct_return, 6),
            )

        # 7. Clean up cached snapshot for this position
        await self._redis.delete(f"agent:position_scores:{position.position_id}")

        return snapshot

    async def _profile_notional(self, profile_id: str) -> Decimal:
        """Return the profile's notional capital, cached.

        Math lives in libs.core.notional.profile_notional — this method is
        just the cache + DB lookup wrapper.
        """
        cached = self._notional_cache.get(profile_id)
        if cached is not None and cached > _ZERO:
            return cached
        row: Optional[dict] = None
        if self._profile_repo is not None:
            try:
                row = await self._profile_repo.get_profile(profile_id)
            except Exception:
                logger.exception("Failed to fetch profile for notional lookup", profile_id=profile_id)
                row = None
        notional = profile_notional(row)
        self._notional_cache[profile_id] = notional
        return notional

    async def _bump_daily_realised_pnl(
        self, profile_id: str, realized_pnl_dollars: Decimal, closed_at: datetime
    ) -> None:
        """Atomically add the realised loss-as-fraction-of-equity to today's
        daily counter.

        Counter unit: integer micro-fractions of profile notional. E.g. a
        loss of $250 on a $10,000 profile increments by -25,000 (= -0.025
        × 1e6). CircuitBreaker reads `daily_pct ≈ counter / 1e6` and compares
        directly to `circuit_breaker_daily_loss_pct` (also a fraction).

        Resets the counter at UTC day rollover by tagging the hash with the
        date it represents. Failures are logged, never raised."""
        if self._redis is None:
            return
        try:
            notional = await self._profile_notional(profile_id)
            equity_fraction = realized_pnl_dollars / notional if notional > _ZERO else _ZERO

            key = f"pnl:daily:{profile_id}"
            today = closed_at.astimezone(timezone.utc).date().isoformat()
            stored_date = await self._redis.hget(key, "date")
            if isinstance(stored_date, bytes):
                stored_date = stored_date.decode()
            if stored_date != today:
                # Day rolled over (or first write today) — reset the counter
                await self._redis.delete(key)
                await self._redis.hset(key, "date", today)
            incr_micro = int(equity_fraction * Decimal("1000000"))
            await self._redis.hincrby(key, "total_pct_micro", incr_micro)
        except Exception:
            logger.exception(
                "Failed to bump daily realised PnL",
                profile_id=profile_id,
                realized_pnl_dollars=str(realized_pnl_dollars),
            )

    async def _get_position_snapshot(self, position_id: str) -> Tuple[Optional[dict], Optional[str]]:
        """Read the entry-time agent_scores + regime snapshot.

        Handles both payload shapes for backward compatibility:
          - New (PR1+):   {"agents": {...}, "regime": "..."}
          - Legacy:       {"ta": {...}, "sentiment": {...}, ...}  (no regime)
        """
        try:
            raw = await self._redis.get(f"agent:position_scores:{position_id}")
            if not raw:
                return None, None
            data = json.loads(raw)
            if isinstance(data, dict) and "agents" in data:
                return data.get("agents"), data.get("regime")
            # Legacy flat-dict format
            return data, None
        except Exception as e:
            logger.warning("Failed to retrieve position snapshot", error=str(e))
            return None, None

    async def _write_closed_trade_row(
        self,
        position: Position,
        exit_price: Decimal,
        taker_rate: Decimal,
        close_reason: str,
        closed_at: datetime,
        snapshot,
        agent_scores: Optional[dict],
        entry_regime: Optional[str],
        outcome: str,
    ) -> None:
        """Append-only write to closed_trades. Logs on failure; never raises."""
        if self._closed_trade_repo is None:
            return  # Repo not wired (e.g. older deployments) — silently skip

        try:
            exit_fee = exit_price * position.quantity * taker_rate
            cost_basis = position.entry_price * position.quantity
            realized_pnl_pct = snapshot.net_pre_tax / cost_basis if cost_basis > _ZERO else _ZERO
            holding_duration_s = (
                int((closed_at - position.opened_at).total_seconds())
                if position.opened_at else 0
            )
            profile_id_uuid = UUID(str(position.profile_id)) if not isinstance(position.profile_id, UUID) else position.profile_id
            side_str = position.side.value if hasattr(position.side, "value") else str(position.side)

            await self._closed_trade_repo.write_closed_trade(
                position_id=position.position_id,
                profile_id=profile_id_uuid,
                symbol=position.symbol,
                side=side_str,
                decision_event_id=getattr(position, "decision_event_id", None),
                order_id=getattr(position, "order_id", None),
                entry_price=position.entry_price,
                entry_quantity=position.quantity,
                entry_fee=position.entry_fee,
                entry_regime=entry_regime,
                entry_agent_scores=agent_scores,
                exit_price=exit_price,
                exit_fee=exit_fee,
                close_reason=close_reason,
                opened_at=position.opened_at,
                closed_at=closed_at,
                holding_duration_s=holding_duration_s,
                realized_pnl=snapshot.net_pre_tax,
                realized_pnl_pct=realized_pnl_pct,
                outcome=outcome,
            )
        except Exception:
            logger.exception(
                "Failed to write closed_trade row",
                position_id=str(position.position_id),
            )
