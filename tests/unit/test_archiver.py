"""Tests for Archiver service: data migration and retention policies."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.archiver.src.migrator import DataMigrator, ARCHIVE_POLICIES


# ---------------------------------------------------------------------------
# ARCHIVE_POLICIES tests
# ---------------------------------------------------------------------------

class TestArchivePolicies:
    def test_all_tables_present(self):
        expected = {"market_data_ohlcv", "audit_log", "validation_events", "pnl_snapshots", "orders"}
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
        redis.scan = AsyncMock(side_effect=[
            (0, [b"fast_gate:prof-1"]),  # first pattern returns a key
        ] + [(0, [])] * 5)  # rest empty
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
        redis = AsyncMock()
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=True)  # archive table exists
        conn.execute = AsyncMock(return_value="DELETE 5")
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=False)))
        ts = MagicMock()
        ts.get_pool = MagicMock(return_value=pool)

        migrator = DataMigrator(redis, ts)
        await migrator._archive_hot_tables()

        assert conn.execute.call_count == len(ARCHIVE_POLICIES)

    @pytest.mark.asyncio
    async def test_run_migration_completes(self):
        redis = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        ts = MagicMock()
        ts.get_pool = MagicMock(return_value=None)  # no pool available

        migrator = DataMigrator(redis, ts)
        # Should not raise even without DB pool
        await migrator.run_migration()
