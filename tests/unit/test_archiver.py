"""Tests for Archiver service: data migration and retention policies."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.archiver.src.migrator import ARCHIVE_POLICIES, DataMigrator

# ---------------------------------------------------------------------------
# ARCHIVE_POLICIES tests
# ---------------------------------------------------------------------------


class TestArchivePolicies:
    def test_all_tables_present(self):
        expected = {
            "market_data_ohlcv",
            "audit_log",
            "validation_events",
            "pnl_snapshots",
            "orders",
        }
        assert set(ARCHIVE_POLICIES.keys()) == expected

    def test_each_policy_has_required_fields(self):
        for table, policy in ARCHIVE_POLICIES.items():
            assert "retention_days" in policy
            assert "timestamp_col" in policy
            assert policy["retention_days"] > 0

    def test_audit_log_30_day_retention(self):
        assert ARCHIVE_POLICIES["audit_log"]["retention_days"] == 30

    def test_market_data_365_day_retention(self):
        assert ARCHIVE_POLICIES["market_data_ohlcv"]["retention_days"] == 365


# ---------------------------------------------------------------------------
# DataMigrator tests
# ---------------------------------------------------------------------------


class TestDataMigrator:
    @pytest.mark.asyncio
    async def test_clean_redis_scans_patterns(self):
        redis = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        ts = AsyncMock()
        migrator = DataMigrator(redis, ts)
        await migrator._clean_redis()
        # Should have scanned for at least 3 patterns
        assert redis.scan.call_count >= 3

    @pytest.mark.asyncio
    async def test_clean_redis_sets_ttl_on_no_expiry_keys(self):
        redis = AsyncMock()
        redis.scan = AsyncMock(
            side_effect=[
                (0, [b"fast_gate:prof-1"]),  # first pattern returns a key
            ]
            + [(0, [])] * 5
        )  # rest empty
        redis.ttl = AsyncMock(return_value=-1)  # no TTL set
        redis.expire = AsyncMock(return_value=True)
        ts = AsyncMock()

        with patch("services.archiver.src.migrator.settings") as mock_settings:
            mock_settings.HOT_DATA_RETENTION_DAYS = 7
            migrator = DataMigrator(redis, ts)
            await migrator._clean_redis()

        redis.expire.assert_called()

    @pytest.mark.asyncio
    async def test_archive_hot_tables_executes_for_each_policy(self):
        """Plain-table path: every policy table gets its CTE move."""
        redis = AsyncMock()
        conn = _make_conn(is_hypertable=False)
        ts = _make_ts(conn)

        migrator = DataMigrator(redis, ts)
        await migrator._archive_hot_tables()

        moves = [c for c in conn.execute.await_args_list if "WITH moved" in c.args[0]]
        assert len(moves) == len(ARCHIVE_POLICIES)
        # The pool default command_timeout is 5s — bulk moves must carry
        # their own generous per-statement timeout (the row-47 blank error
        # was exactly this statement timing out).
        for c in moves:
            assert c.kwargs.get("timeout", 0) >= 60

    @pytest.mark.asyncio
    async def test_run_migration_completes(self):
        redis = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        ts = MagicMock()
        ts.get_pool = MagicMock(return_value=None)  # no pool available

        migrator = DataMigrator(redis, ts)
        # Should not raise even without DB pool
        await migrator.run_migration()


# ---------------------------------------------------------------------------
# Chunk-aware hypertable archiving (registry row 47)
# ---------------------------------------------------------------------------

CHUNK_ROW = {
    "chunk_schema": "_timescaledb_internal",
    "chunk_name": "_hyper_9_1_chunk",
    "range_end": datetime(2026, 1, 1, tzinfo=timezone.utc),
}


def _make_conn(
    is_hypertable: bool,
    archive_exists: bool = True,
    chunks=None,
    chunk_count: int = 5,
    insert_result: str = "INSERT 0 5",
):
    """Build a mock asyncpg connection that routes by query text."""
    conn = MagicMock()
    conn.drop_calls = []

    async def fetchval(query, *args, **kwargs):
        if "information_schema" in query:
            return archive_exists
        if "hypertables" in query:
            return is_hypertable
        if "COUNT(*)" in query:
            return chunk_count
        return None

    async def fetch(query, *args, **kwargs):
        if "timescaledb_information.chunks" in query:
            return list(chunks if chunks is not None else [CHUNK_ROW])
        if "drop_chunks" in query:
            conn.drop_calls.append(args)
            return [("dropped",)]
        return []

    async def execute(query, *args, **kwargs):
        if query.strip().startswith("INSERT INTO"):
            return insert_result
        return "OK"

    conn.fetchval = AsyncMock(side_effect=fetchval)
    conn.fetch = AsyncMock(side_effect=fetch)
    conn.execute = AsyncMock(side_effect=execute)

    @asynccontextmanager
    async def tx():
        yield

    conn.transaction = tx
    return conn


def _make_ts(conn):
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    ts = MagicMock()
    ts.get_pool = MagicMock(return_value=pool)
    return ts


POLICY = {"retention_days": 30, "timestamp_col": "created_at"}


class TestHypertableChunkArchiving:
    @pytest.mark.asyncio
    async def test_verified_copy_then_drop(self):
        """Happy path: copy rowcount matches the chunk rowcount -> the chunk
        is dropped via drop_chunks bounded to that chunk's range_end."""
        conn = _make_conn(is_hypertable=True)
        migrator = DataMigrator(AsyncMock(), _make_ts(conn))

        await migrator._archive_table(conn, "audit_log", POLICY)

        inserts = [
            c
            for c in conn.execute.await_args_list
            if c.args[0].strip().startswith("INSERT INTO")
        ]
        assert len(inserts) == 1
        assert "_timescaledb_internal._hyper_9_1_chunk" in inserts[0].args[0]
        assert conn.drop_calls == [("audit_log", CHUNK_ROW["range_end"])]

    @pytest.mark.asyncio
    async def test_copy_mismatch_keeps_chunk(self):
        """Verification failure must NOT drop the chunk (no data loss)."""
        conn = _make_conn(is_hypertable=True, chunk_count=5, insert_result="INSERT 0 3")
        migrator = DataMigrator(AsyncMock(), _make_ts(conn))

        with pytest.raises(RuntimeError, match="verification failed"):
            await migrator._archive_table(conn, "audit_log", POLICY)

        assert conn.drop_calls == []

    @pytest.mark.asyncio
    async def test_no_aged_chunks_is_a_quiet_noop(self):
        conn = _make_conn(is_hypertable=True, chunks=[])
        migrator = DataMigrator(AsyncMock(), _make_ts(conn))

        moved = await migrator._archive_hypertable_chunks(
            conn, "audit_log", "audit_log_archive", datetime.now(timezone.utc)
        )
        assert moved == 0
        assert conn.drop_calls == []

    @pytest.mark.asyncio
    async def test_hypertable_never_uses_cte_delete(self):
        """Row 47: hypertables get chunk-aware retention, not the CTE move."""
        conn = _make_conn(is_hypertable=True)
        migrator = DataMigrator(AsyncMock(), _make_ts(conn))

        await migrator._archive_table(conn, "audit_log", POLICY)

        assert not any("WITH moved" in c.args[0] for c in conn.execute.await_args_list)

    @pytest.mark.asyncio
    async def test_archive_table_created_when_missing(self):
        conn = _make_conn(is_hypertable=True, archive_exists=False)
        migrator = DataMigrator(AsyncMock(), _make_ts(conn))

        await migrator._archive_table(conn, "audit_log", POLICY)

        creates = [
            c
            for c in conn.execute.await_args_list
            if "CREATE TABLE audit_log_archive" in c.args[0]
        ]
        assert len(creates) == 1

    @pytest.mark.asyncio
    async def test_policies_override_honoured(self):
        """The policies constructor override drives which tables run —
        enables throwaway archtest_* verification without real tables."""
        conn = _make_conn(is_hypertable=False)
        migrator = DataMigrator(
            AsyncMock(),
            _make_ts(conn),
            policies={"archtest_src": POLICY},
        )
        await migrator._archive_hot_tables()
        moves = [c for c in conn.execute.await_args_list if "WITH moved" in c.args[0]]
        assert len(moves) == 1
        assert "archtest_src" in moves[0].args[0]

    @pytest.mark.asyncio
    async def test_blank_error_now_diagnosable(self, caplog):
        """Row 47(a): str(asyncio.TimeoutError()) is EMPTY — the log line
        must carry the exception type/repr so failures are diagnosable."""
        conn = _make_conn(is_hypertable=True)
        conn.fetchval = AsyncMock(side_effect=asyncio.TimeoutError())
        migrator = DataMigrator(AsyncMock(), _make_ts(conn))

        with caplog.at_level(logging.ERROR, logger="archiver.migrator"):
            await migrator._archive_hot_tables()

        assert "TimeoutError" in caplog.text
