import logging
from libs.storage._redis_client import RedisClient
from libs.storage._timescale_client import TimescaleClient
from libs.config import settings

logger = logging.getLogger("archiver.migrator")

# Tables to archive and their retention policies (days to keep in hot table)
ARCHIVE_POLICIES = {
    "market_data_ohlcv": {"retention_days": 365, "timestamp_col": "bucket"},
    "audit_log": {"retention_days": 30, "timestamp_col": "created_at"},
    "validation_events": {"retention_days": 90, "timestamp_col": "created_at"},
    "pnl_snapshots": {"retention_days": 180, "timestamp_col": "snapshot_at"},
    "orders": {"retention_days": 365, "timestamp_col": "created_at"},
}


class DataMigrator:
    def __init__(self, redis_client: RedisClient, timescale_client: TimescaleClient, gcs_bucket: str = None):
        self._redis = redis_client
        self._timescale = timescale_client
        self._gcs_bucket = gcs_bucket

    async def run_migration(self):
        logger.info("Starting Daily Archiving Cron Job")

        # 1. Clean expired Redis keys beyond HOT_DATA_RETENTION_DAYS
        await self._clean_redis()

        # 2. Move old rows from hot tables to archive tables in TimescaleDB
        await self._archive_hot_tables()

        # 3. (Optional) Export archive tables to GCS if configured
        if self._gcs_bucket:
            logger.info("GCS export configured but deferred to batch pipeline (bucket=%s)", self._gcs_bucket)
        else:
            logger.info("GCS_BUCKET_NAME not set, skipping external export")

        logger.info("Daily archiving cron completed")

    async def _clean_redis(self):
        """Scan Redis for stale keys matching known patterns and remove those without TTL."""
        logger.info("Cleaning up Redis keys without TTL (hot data sweep)")
        redis_conn = self._redis
        if not redis_conn:
            return

        patterns = ["fast_gate:*", "risk:allocation:*", "halt:*"]
        removed = 0
        for pattern in patterns:
            try:
                cursor = 0
                while True:
                    cursor, keys = await redis_conn.scan(cursor=cursor, match=pattern, count=200)
                    for key in keys:
                        ttl = await redis_conn.ttl(key)
                        if ttl == -1:  # no expiry set -- apply retention TTL
                            retention_secs = settings.HOT_DATA_RETENTION_DAYS * 86400
                            await redis_conn.expire(key, retention_secs)
                            removed += 1
                    if cursor == 0:
                        break
            except Exception as e:
                logger.error("Redis sweep error for pattern %s: %s", pattern, e)

        logger.info("Redis sweep complete: set TTL on %d keys", removed)

    async def _archive_hot_tables(self):
        """Move rows older than retention period from hot tables into corresponding archive tables."""
        pool = self._timescale.get_pool()
        if not pool:
            logger.error("No database pool available for archiving")
            return

        async with pool.acquire() as conn:
            for table, policy in ARCHIVE_POLICIES.items():
                archive_table = f"{table}_archive"
                ts_col = policy["timestamp_col"]
                retention_days = policy["retention_days"]

                try:
                    # Check if archive table exists; create if not
                    exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = $1
                        )
                    """, archive_table)

                    if not exists:
                        await conn.execute(f"""
                            CREATE TABLE {archive_table} (LIKE {table} INCLUDING ALL)
                        """)
                        logger.info("Created archive table: %s", archive_table)

                    # Move old rows: INSERT INTO archive, then DELETE from hot table
                    result = await conn.execute(f"""
                        WITH moved AS (
                            DELETE FROM {table}
                            WHERE {ts_col} < NOW() - INTERVAL '{retention_days} days'
                            RETURNING *
                        )
                        INSERT INTO {archive_table}
                        SELECT * FROM moved
                    """)
                    logger.info("Archived from %s: %s", table, result)

                except Exception as e:
                    logger.error("Failed to archive table %s: %s", table, e)
