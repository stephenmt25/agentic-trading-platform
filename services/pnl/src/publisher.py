import json
import time
from decimal import Decimal

from libs.storage._redis_client import RedisClient
from libs.messaging import PubSubBroadcaster
from libs.messaging.channels import PUBSUB_PNL_UPDATES
from libs.storage.repositories import PnlRepository
from libs.core.schemas import PnlUpdateEvent, DrawdownPayload

_ZERO = Decimal("0")
_SNAPSHOT_THRESHOLD = Decimal("0.005")


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if hasattr(o, 'hex'):  # UUID
            return str(o)
        return super().default(o)


class PnLPublisher:
    def __init__(self, redis_client: RedisClient, pubsub: PubSubBroadcaster, pnl_repo: PnlRepository):
        self._redis = redis_client
        self._pubsub = pubsub
        self._pnl_repo = pnl_repo
        self._last_snapshot: dict[str, Decimal] = {}

    async def publish_update(self, profile_id: str, snapshot):
        ev = PnlUpdateEvent(
            profile_id=profile_id,
            symbol=snapshot.symbol,
            gross_pnl=snapshot.gross_pnl,
            net_pnl=snapshot.net_pre_tax,
            pct_return=snapshot.pct_return,
            timestamp_us=int(time.time() * 1000000),
            source_service="pnl",
        )

        # 1. Pub/Sub (Dashboard)
        await self._pubsub.publish(PUBSUB_PNL_UPDATES, ev)

        # 2. Redis Latest (Dashboard loads instantly)
        cache_key = f"pnl:{profile_id}:{snapshot.position_id}:latest"
        await self._redis.set(cache_key, json.dumps(ev.dict(), cls=_DecimalEncoder))

        # 3. Daily running total is owned by hot_path/pnl_sync via HINCRBY on the
        # same pubsub event — see services/hot_path/src/pnl_sync.py. Writing here
        # caused a Redis WRONGTYPE collision (string vs hash).

        # 4. Write drawdown to Redis
        await self._update_drawdown(profile_id, snapshot)

        # 5. TimescaleDB Periodic Snapshot (if diff > 0.5%)
        last_pct = self._last_snapshot.get(snapshot.position_id, _ZERO)
        diff = abs(snapshot.pct_return - last_pct)
        if diff > _SNAPSHOT_THRESHOLD:
            cost_basis = snapshot.gross_pnl + snapshot.net_pre_tax  # entry_price * qty approximation
            # Use the PnLSnapshot fields directly — matches pnl_repo.write_snapshot() expected dict
            await self._pnl_repo.write_snapshot({
                "profile_id": profile_id,
                "symbol": snapshot.symbol,
                "gross_pnl": snapshot.gross_pnl,
                "net_pnl_pre_tax": snapshot.net_pre_tax,
                "net_pnl_post_tax": snapshot.net_post_tax,
                "total_fees": snapshot.fees,
                "estimated_tax": snapshot.tax_estimate,
                "cost_basis": cost_basis,
                "pct_return": snapshot.pct_return,
            })
            self._last_snapshot[snapshot.position_id] = snapshot.pct_return

    async def _update_drawdown(self, profile_id: str, snapshot):
        """Track current drawdown in Redis."""
        key = f"risk:drawdown:{profile_id}"
        drawdown_pct = max(_ZERO, -snapshot.pct_return) if snapshot.pct_return < 0 else _ZERO

        raw = await self._redis.get(key)
        if raw:
            parsed = DrawdownPayload.model_validate_json(raw)
            prev = parsed.drawdown_pct_decimal()
            data = {"drawdown_pct": str(max(prev, drawdown_pct))}
        else:
            data = {"drawdown_pct": str(drawdown_pct)}

        await self._redis.set(key, json.dumps(data), ex=86400)
