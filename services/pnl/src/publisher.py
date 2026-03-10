import json
from libs.storage._redis_client import RedisClient
from libs.messaging import PubSubBroadcaster
from libs.messaging.channels import PUBSUB_PNL_UPDATES
from libs.storage.repositories import PnlRepository
from libs.core.schemas import PnlUpdateEvent
import time

class PnLPublisher:
    def __init__(self, redis_client: RedisClient, pubsub: PubSubBroadcaster, pnl_repo: PnlRepository):
        self._redis = redis_client
        self._pubsub = pubsub
        self._pnl_repo = pnl_repo
        self._last_snapshot = {} # Tracking local to only flush to db on 0.5% diff

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
        
        # 3. TimescaleDB Periodic Snapshot (e.g. if diff > 0.5%)
        # For simplicity, we compare and write
        last_pct = self._last_snapshot.get(snapshot.position_id, 0.0)
        diff = abs(snapshot.pct_return - last_pct)
        if diff > 0.005: # > 0.5%
            await self._pnl_repo.write_snapshot(ev)
            self._last_snapshot[snapshot.position_id] = snapshot.pct_return
