import json
import time
from decimal import Decimal
from datetime import datetime, timezone

from libs.storage._redis_client import RedisClient
from libs.messaging import PubSubBroadcaster
from libs.messaging.channels import PUBSUB_PNL_UPDATES
from libs.storage.repositories import PnlRepository
from libs.core.schemas import PnlUpdateEvent, DailyPnlPayload, DrawdownPayload

_ZERO = Decimal("0")
_SNAPSHOT_THRESHOLD = Decimal("0.005")


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
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
            position_id=snapshot.position_id,
            symbol=snapshot.symbol,
            net_post_tax=snapshot.net_post_tax,
            net_pre_tax=snapshot.net_pre_tax,
            roi_pct=snapshot.pct_return,
            timestamp_us=int(time.time() * 1000000),
            source_service="pnl"
        )

        # 1. Pub/Sub (Dashboard)
        await self._pubsub.publish(PUBSUB_PNL_UPDATES, ev)

        # 2. Redis Latest (Dashboard loads instantly)
        cache_key = f"pnl:{profile_id}:{snapshot.position_id}:latest"
        await self._redis.set(cache_key, json.dumps(ev.dict(), cls=_DecimalEncoder))

        # 3. Maintain daily running total for CircuitBreaker
        await self._update_daily_pnl(profile_id, snapshot.pct_return)

        # 4. Write drawdown to Redis
        await self._update_drawdown(profile_id, snapshot)

        # 5. TimescaleDB Periodic Snapshot (if diff > 0.5%)
        last_pct = self._last_snapshot.get(snapshot.position_id, _ZERO)
        diff = abs(snapshot.pct_return - last_pct)
        if diff > _SNAPSHOT_THRESHOLD:
            await self._pnl_repo.write_snapshot(ev)
            self._last_snapshot[snapshot.position_id] = snapshot.pct_return

    async def _update_daily_pnl(self, profile_id: str, pct_return: Decimal):
        """Maintain running daily PnL total in Redis with midnight UTC expiry."""
        key = f"pnl:daily:{profile_id}"
        raw = await self._redis.get(key)

        if raw:
            parsed = DailyPnlPayload.model_validate_json(raw)
            data = {"total_pct": str(parsed.total_pct_decimal() + pct_return)}
        else:
            data = {"total_pct": str(pct_return)}

        # Calculate seconds until next midnight UTC
        now = datetime.now(timezone.utc)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        next_midnight = midnight.replace(day=now.day + 1) if now.hour > 0 or now.minute > 0 else midnight
        try:
            ttl = int((next_midnight - now).total_seconds())
        except OverflowError:
            ttl = 86400
        ttl = max(1, min(ttl, 86400))

        await self._redis.set(key, json.dumps(data), ex=ttl)

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
