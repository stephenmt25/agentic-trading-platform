import logging
from datetime import datetime, timedelta, timezone

from libs.config import settings
from libs.storage._redis_client import RedisClient
from libs.storage._timescale_client import TimescaleClient

logger = logging.getLogger("archiver.migrator")

# Tables to archive and their retention policies (days to keep in hot table)
ARCHIVE_POLICIES = {
    "market_data_ohlcv": {"retention_days": 365, "timestamp_col": "bucket"},
    "audit_log": {"retention_days": 30, "timestamp_col": "created_at"},
    "validation_events": {"retention_days": 90, "timestamp_col": "created_at"},
    "pnl_snapshots": {"retention_days": 180, "timestamp_col": "snapshot_at"},
    "orders": {"retention_days": 365, "timestamp_col": "created_at"},
}

# The shared asyncpg pool is created with command_timeout=5.0 (the
# kill-switch fail-safe needs snappy failures). Bulk archive statements
# legitimately run longer — audit_log alone accumulated ~885k over-retention
# rows while archiving was broken — so every copy/count/prune statement here
# carries its own generous per-call timeout. This is exactly the bug behind
# the registry-row-47 "blank error": the old single-statement CTE move blew
# the 5s command_timeout and raised asyncio.TimeoutError, whose str() is "".
ARCHIVE_STATEMENT_TIMEOUT_S = 600.0


class DataMigrator:
    def __init__(
        self,
        redis_client: RedisClient,
        timescale_client: TimescaleClient,
        gcs_bucket: str = None,
        policies: dict = None,
    ):
        self._redis = redis_client
        self._timescale = timescale_client
        self._gcs_bucket = gcs_bucket
        # Overridable for tests / throwaway verification runs.
        self._policies = policies if policies is not None else ARCHIVE_POLICIES

    async def run_migration(self):
        logger.info("Starting Daily Archiving Cron Job")

        # 1. Clean expired Redis keys beyond HOT_DATA_RETENTION_DAYS
        await self._clean_redis()

        # 2. Move old rows from hot tables to archive tables in TimescaleDB
        await self._archive_hot_tables()

        # 3. (Optional) Export archive tables to GCS if configured
        if self._gcs_bucket:
            logger.info(
                "GCS export configured but deferred to batch pipeline (bucket=%s)",
                self._gcs_bucket,
            )
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
                    cursor, keys = await redis_conn.scan(
                        cursor=cursor, match=pattern, count=200
                    )
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
            for table, policy in self._policies.items():
                try:
                    await self._archive_table(conn, table, policy)
                except Exception as e:
                    # repr/type included: str() of asyncio.TimeoutError (the
                    # actual historical failure) is EMPTY, which made this
                    # path undiagnosable from logs (registry row 47).
                    logger.error(
                        "Failed to archive table %s: %s: %r",
                        table,
                        type(e).__name__,
                        e,
                    )

    async def _archive_table(self, conn, table: str, policy: dict):
        """Archive one table: verified copy to <table>_archive, then prune."""
        archive_table = f"{table}_archive"
        ts_col = policy["timestamp_col"]
        cutoff = datetime.now(timezone.utc) - timedelta(days=policy["retention_days"])

        # Check if archive table exists; create if not
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = $1
            )
        """,
            archive_table,
        )

        if not exists:
            await conn.execute(
                f"""
                CREATE TABLE {archive_table} (LIKE {table} INCLUDING ALL)
            """
            )
            logger.info("Created archive table: %s", archive_table)

        is_hypertable = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM timescaledb_information.hypertables
                WHERE hypertable_name = $1
            )
        """,
            table,
        )

        if is_hypertable:
            moved = await self._archive_hypertable_chunks(
                conn, table, archive_table, cutoff
            )
            logger.info(
                "Archived from %s (hypertable, chunk-aware): %d rows", table, moved
            )
        else:
            # Plain table: the CTE move is fine, but needs a real statement
            # timeout (the pool default of 5s cannot move a large backlog).
            result = await conn.execute(
                f"""
                WITH moved AS (
                    DELETE FROM {table}
                    WHERE {ts_col} < $1
                    RETURNING *
                )
                INSERT INTO {archive_table}
                SELECT * FROM moved
            """,
                cutoff,
                timeout=ARCHIVE_STATEMENT_TIMEOUT_S,
            )
            logger.info("Archived from %s: %s", table, result)

    async def _archive_hypertable_chunks(
        self, conn, table: str, archive_table: str, cutoff: datetime
    ) -> int:
        """Chunk-aware retention for TimescaleDB hypertables.

        For every chunk whose entire time range is older than the cutoff:
        copy its rows into the archive table, verify the copied rowcount
        against the chunk's rowcount, then drop exactly that chunk via
        drop_chunks — all inside ONE transaction per chunk, so a failure at
        any step rolls the whole move back (drop_chunks is transactional;
        verified locally on TimescaleDB 2.13.1). Rows newer than the last
        fully-old chunk boundary stay in the hot table until their chunk
        ages out — standard Timescale retention semantics.
        """
        chunks = await conn.fetch(
            """
            SELECT chunk_schema, chunk_name, range_end
            FROM timescaledb_information.chunks
            WHERE hypertable_name = $1 AND range_end <= $2
            ORDER BY range_end
            """,
            table,
            cutoff,
        )
        if not chunks:
            logger.info("No fully-aged chunks to archive for %s", table)
            return 0

        total_moved = 0
        for chunk in chunks:
            chunk_fq = f'{chunk["chunk_schema"]}.{chunk["chunk_name"]}'
            async with conn.transaction():
                src_count = await conn.fetchval(
                    f"SELECT COUNT(*) FROM {chunk_fq}",
                    timeout=ARCHIVE_STATEMENT_TIMEOUT_S,
                )
                result = await conn.execute(
                    f"INSERT INTO {archive_table} SELECT * FROM {chunk_fq}",
                    timeout=ARCHIVE_STATEMENT_TIMEOUT_S,
                )
                copied = int(result.split()[-1])
                if copied != src_count:
                    # Raising aborts the transaction → the INSERT rolls back
                    # and the chunk is NOT dropped. No data loss possible.
                    raise RuntimeError(
                        f"archive copy verification failed for {chunk_fq}: "
                        f"copied {copied} != source {src_count}; chunk kept"
                    )
                # Chunks are processed in ascending range_end order, so
                # older_than = this chunk's range_end drops exactly this
                # chunk (earlier ones are already gone).
                await conn.fetch(
                    "SELECT drop_chunks($1::regclass, older_than => $2::timestamptz)",
                    table,
                    chunk["range_end"],
                    timeout=ARCHIVE_STATEMENT_TIMEOUT_S,
                )
            total_moved += copied
            logger.info(
                "Archived chunk %s of %s: %d rows moved, chunk dropped",
                chunk_fq,
                table,
                copied,
            )
        return total_moved
