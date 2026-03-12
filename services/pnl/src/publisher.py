import json
import time
import calendar
from datetime import datetime, timezone

from libs.storage._redis_client import RedisClient
from libs.messaging import PubSubBroadcaster
from libs.messaging.channels import PUBSUB_PNL_UPDATES
from libs.storage.repositories import PnlRepository
from libs.core.schemas import PnlUpdateEvent


class PnLPublisher:
    def __init__(self, redis_client: RedisClient, pubsub: PubSubBroadcaster, pnl_repo: PnlRepository):
        self._redis = redis_client
        self._pubsub = pubsub
        self._pnl_repo = pnl_repo
        self._last_snapshot = {}  # Tracking local to only flush to db on 0.5% diff

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
        await self._redis.set(cache_key, json.dumps(ev.dict()))

        # 3. Maintain daily running total for CircuitBreaker (Sprint 10.1)
        await self._update_daily_pnl(profile_id, snapshot.pct_return)

        # 4. Write drawdown to Redis (Sprint 10.3)
        await self._update_drawdown(profile_id, snapshot)

        # 5. TimescaleDB Periodic Snapshot (e.g. if diff > 0.5%)
        last_pct = self._last_snapshot.get(snapshot.position_id, 0.0)
        diff = abs(snapshot.pct_return - last_pct)
        if diff > 0.005:  # > 0.5%
            await self._pnl_repo.write_snapshot(ev)
            self._last_snapshot[snapshot.position_id] = snapshot.pct_return

    async def _update_daily_pnl(self, profile_id: str, pct_return: float):
        """Maintain running daily PnL total in Redis with midnight UTC expiry."""
        key = f"pnl:daily:{profile_id}"
        raw = await self._redis.get(key)

        if raw:
            data = json.loads(raw)
            data["total_pct"] = data.get("total_pct", 0.0) + pct_return
        else:
            data = {"total_pct": pct_return}

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
        """Track current drawdown in Redis (Sprint 10.3)."""
        key = f"risk:drawdown:{profile_id}"
        # Simple drawdown: negative of cumulative loss from peak
        drawdown_pct = max(0.0, -snapshot.pct_return) if snapshot.pct_return < 0 else 0.0

        raw = await self._redis.get(key)
        if raw:
            data = json.loads(raw)
            # Running max drawdown for the day
            data["drawdown_pct"] = max(data.get("drawdown_pct", 0.0), drawdown_pct)
        else:
            data = {"drawdown_pct": drawdown_pct}

        await self._redis.set(key, json.dumps(data), ex=86400)
