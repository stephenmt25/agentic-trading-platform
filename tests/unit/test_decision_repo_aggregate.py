"""Unit tests for DecisionRepository.aggregate_approved_by_attribute.

Pure SQL-shape verification: ensures the bucket dispatch picks the right
expression for each dimension and that the WHERE clause restricts to
APPROVED, non-shadow rows. No real DB required.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from libs.storage.repositories.decision_repo import DecisionRepository


def _make_repo():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    return DecisionRepository(db), db


class TestAggregateApprovedByAttribute:
    @pytest.mark.parametrize(
        "dimension,fragment",
        [
            ("symbol", "d.symbol AS bucket"),
            ("direction", "d.strategy->>'direction'"),
            ("regime", "d.regime->>'regime'"),
            ("hour", "EXTRACT(hour FROM d.created_at AT TIME ZONE 'UTC')"),
            ("day_of_week", "EXTRACT(dow FROM d.created_at AT TIME ZONE 'UTC')"),
        ],
    )
    @pytest.mark.asyncio
    async def test_dimension_picks_correct_bucket_expr(self, dimension, fragment):
        repo, db = _make_repo()
        await repo.aggregate_approved_by_attribute(dimension=dimension)
        sql = db.fetch.call_args.args[0]
        assert fragment in sql

    @pytest.mark.asyncio
    async def test_filters_to_approved_non_shadow(self):
        repo, db = _make_repo()
        await repo.aggregate_approved_by_attribute(dimension="symbol")
        sql = db.fetch.call_args.args[0]
        assert "d.outcome = 'APPROVED'" in sql
        assert "d.shadow = FALSE" in sql

    @pytest.mark.asyncio
    async def test_unknown_dimension_raises(self):
        repo, _ = _make_repo()
        with pytest.raises(ValueError, match="Unknown dimension"):
            await repo.aggregate_approved_by_attribute(dimension="garbage")

    @pytest.mark.asyncio
    async def test_filters_by_profile_and_symbol(self):
        repo, db = _make_repo()
        pid = uuid.uuid4()
        await repo.aggregate_approved_by_attribute(
            dimension="symbol",
            profile_id=pid,
            symbol="BTC/USDT",
            window_hours=72,
            limit=20,
        )
        sql, *args = db.fetch.call_args.args
        assert "d.profile_id = $2" in sql
        assert "d.symbol = $3" in sql
        assert args == ["72", pid, "BTC/USDT", 20]

    @pytest.mark.asyncio
    async def test_post_processing_returns_floats_for_percent(self):
        from decimal import Decimal as D
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[
            {"bucket": "BUY", "count": 30, "percent": D("0.75")},
            {"bucket": "SELL", "count": 10, "percent": D("0.25")},
        ])
        repo = DecisionRepository(db)
        out = await repo.aggregate_approved_by_attribute(dimension="direction")
        assert out[0]["percent"] == 0.75
        assert out[1]["percent"] == 0.25
        assert isinstance(out[0]["percent"], float)

    @pytest.mark.asyncio
    async def test_query_emits_count_and_percent(self):
        repo, db = _make_repo()
        await repo.aggregate_approved_by_attribute(dimension="direction")
        sql = db.fetch.call_args.args[0]
        # The percent column comes from a CROSS JOIN to the totals CTE
        # so we don't divide by zero.
        assert "WITH bucketed AS" in sql
        assert "COUNT(*)::INT  AS count" in sql
        assert "CROSS JOIN totals" in sql
