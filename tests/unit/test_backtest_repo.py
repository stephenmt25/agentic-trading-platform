"""Unit tests for the BacktestRepository's history-related additions
(Track-Item B.2). Exercises the SQL parameterization without spinning up a
real Postgres — uses a fake client that records the query + params and
returns canned rows."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from libs.storage.repositories.backtest_repo import (
    BacktestRepository,
    _coerce_dt,
    _coerce_uuid,
)


class FakeTimescale:
    """Records the last SQL + args that the repo executes, returns canned data."""

    def __init__(self, fetch_rows=None, fetchrow_row=None):
        self.last_query: str | None = None
        self.last_args: tuple = ()
        self._fetch_rows = fetch_rows or []
        self._fetchrow_row = fetchrow_row

    async def execute(self, query, *args):
        self.last_query = query
        self.last_args = args
        return ""

    async def fetch(self, query, *args):
        self.last_query = query
        self.last_args = args
        return list(self._fetch_rows)

    async def fetchrow(self, query, *args):
        self.last_query = query
        self.last_args = args
        return self._fetchrow_row


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------

class TestCoercion:
    def test_coerce_uuid_passes_str(self):
        u = "11111111-2222-3333-4444-555555555555"
        assert _coerce_uuid(u) == u

    def test_coerce_uuid_handles_empty(self):
        assert _coerce_uuid("") is None
        assert _coerce_uuid(None) is None

    def test_coerce_dt_passes_datetime(self):
        d = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)
        assert _coerce_dt(d) is d

    def test_coerce_dt_parses_iso(self):
        out = _coerce_dt("2026-05-07T12:00:00+00:00")
        assert isinstance(out, datetime)
        assert out.year == 2026 and out.month == 5 and out.day == 7

    def test_coerce_dt_returns_none_for_empty(self):
        assert _coerce_dt(None) is None
        assert _coerce_dt("") is None


# ---------------------------------------------------------------------------
# get_history filtering
# ---------------------------------------------------------------------------

class TestGetHistory:
    @pytest.mark.asyncio
    async def test_user_scope_required_for_history(self):
        """When user_id is provided, the WHERE clause must filter on created_by."""
        client = FakeTimescale(fetch_rows=[])
        repo = BacktestRepository(client)
        await repo.get_history(user_id="abc-123")
        assert "created_by" in client.last_query
        # First positional arg is the user_id, last is the limit.
        assert client.last_args[0] == "abc-123"
        assert client.last_args[-1] == 20  # default limit

    @pytest.mark.asyncio
    async def test_optional_filters_appended(self):
        client = FakeTimescale(fetch_rows=[])
        repo = BacktestRepository(client)
        await repo.get_history(
            user_id="user-1", profile_id="prof-1", symbol="BTC/USDT", limit=5,
        )
        assert "profile_id" in client.last_query
        assert "symbol" in client.last_query
        # Order: user_id, profile_id, symbol, limit
        assert client.last_args[0] == "user-1"
        assert client.last_args[1] == "prof-1"
        assert client.last_args[2] == "BTC/USDT"
        assert client.last_args[3] == 5

    @pytest.mark.asyncio
    async def test_limit_clamped_to_100(self):
        client = FakeTimescale(fetch_rows=[])
        repo = BacktestRepository(client)
        await repo.get_history(user_id="u", limit=999)
        assert client.last_args[-1] == 100

    @pytest.mark.asyncio
    async def test_limit_minimum_1(self):
        client = FakeTimescale(fetch_rows=[])
        repo = BacktestRepository(client)
        await repo.get_history(user_id="u", limit=0)
        assert client.last_args[-1] == 1

    @pytest.mark.asyncio
    async def test_returns_dict_rows(self):
        canned = [{"job_id": "j1", "symbol": "BTC/USDT", "total_trades": 3}]
        client = FakeTimescale(fetch_rows=canned)
        repo = BacktestRepository(client)
        rows = await repo.get_history(user_id="u")
        assert rows == canned

    @pytest.mark.asyncio
    async def test_no_user_scope_returns_unscoped_rows(self):
        """Operator tooling can pass user_id=None to see all rows; the
        WHERE clause must NOT filter on created_by in that case (the column
        still appears in the SELECT list, which is fine)."""
        client = FakeTimescale(fetch_rows=[])
        repo = BacktestRepository(client)
        await repo.get_history(user_id=None)
        # Strip the SELECT-list section before asserting on the WHERE clause.
        where_clause = client.last_query.split("WHERE", 1)[1]
        assert "created_by" not in where_clause


# ---------------------------------------------------------------------------
# save_result with new fields
# ---------------------------------------------------------------------------

class TestSaveResult:
    @pytest.mark.asyncio
    async def test_save_result_passes_history_fields(self):
        client = FakeTimescale()
        repo = BacktestRepository(client)
        payload = {
            "job_id": "j1",
            "profile_id": "p1",
            "symbol": "BTC/USDT",
            "strategy_rules": {},
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "profit_factor": 0.0,
            "equity_curve": [],
            "trades": [],
            "created_by": "11111111-2222-3333-4444-555555555555",
            "start_date": "2026-05-01T00:00:00+00:00",
            "end_date": "2026-05-07T00:00:00+00:00",
            "timeframe": "1m",
        }
        await repo.save_result(payload)
        assert client.last_args[12] == payload["created_by"]
        # ISO strings are coerced to datetime by the repo before asyncpg.
        assert isinstance(client.last_args[13], datetime)
        assert isinstance(client.last_args[14], datetime)
        assert client.last_args[15] == "1m"

    @pytest.mark.asyncio
    async def test_save_result_handles_missing_history_fields(self):
        """Old call sites that don't pass the B.2 fields keep working — the
        new columns just become NULL."""
        client = FakeTimescale()
        repo = BacktestRepository(client)
        await repo.save_result({
            "job_id": "j1",
            "profile_id": "",
            "symbol": "BTC/USDT",
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "profit_factor": 0.0,
        })
        # created_by, start_date, end_date, timeframe all None
        assert client.last_args[12] is None
        assert client.last_args[13] is None
        assert client.last_args[14] is None
        assert client.last_args[15] is None
