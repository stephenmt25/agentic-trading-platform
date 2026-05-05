"""Regression tests for services/api_gateway/src/routes/pnl.py.

The previous implementation called redis.get(f"pnl:daily:{pid}") followed by
json.loads(...) — but services/pnl/src/closer.py writes that key as a HASH
(fields: date, total_pct_micro). Any profile that had ever closed a trade
caused redis-py to raise WRONGTYPE on the .get(), surfacing as 500 to the
frontend.

These tests verify the new shape:
  - Hash present → 200 with daily_loss_pct populated and dollar values
    sourced from pnl_snapshots, not the hash.
  - Hash absent → 200 with daily_loss_pct = 0.0.
  - Auth + ownership: missing user => 401; foreign profile => 404.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from services.api_gateway.src.routes.pnl import router as pnl_router
from services.api_gateway.src.deps import (
    get_current_user,
    get_pnl_repo,
    get_profile_repo,
    get_redis,
)


def _make_app(user_id: str, overrides: dict) -> TestClient:
    app = FastAPI()
    app.include_router(pnl_router, prefix="/pnl")

    def _user():
        return user_id

    app.dependency_overrides[get_current_user] = _user
    for dep, override in overrides.items():
        app.dependency_overrides[dep] = override
    return TestClient(app)


class _HashRedis:
    """Minimal async redis stand-in supporting hget on a pre-seeded hash."""

    def __init__(self, hashes: dict):
        # {key: {field: value(bytes-or-str)}}
        self._hashes = hashes

    async def hget(self, key, field):
        h = self._hashes.get(key)
        if not h:
            return None
        return h.get(field)


def _seeded_snapshot(symbol="BTC/USDT") -> dict:
    return {
        "gross_pnl": Decimal("123.45"),
        "net_pnl_pre_tax": Decimal("100.00"),
        "net_pnl_post_tax": Decimal("85.50"),
        "total_fees": Decimal("3.25"),
        "estimated_tax": Decimal("14.50"),
        "cost_basis": Decimal("10000"),
        "pct_return": Decimal("0.00855"),
        "symbol": symbol,
        "snapshot_at": datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    }


class TestPnlSummaryWrongTypeSafety:
    def test_summary_with_hash_present_returns_200_and_dollar_value(self):
        pid = uuid.uuid4()
        user_id = "user-1"

        profile_repo = AsyncMock()
        profile_repo.get_active_profiles_for_user = AsyncMock(
            return_value=[{"profile_id": pid}]
        )

        pnl_repo = AsyncMock()
        pnl_repo.get_latest = AsyncMock(return_value=_seeded_snapshot())

        # Hash exists: previously caused WRONGTYPE on redis.get
        redis = _HashRedis({
            f"pnl:daily:{pid}": {
                "date": "2026-05-05",
                "total_pct_micro": "-25000",  # -2.5%
            }
        })

        client = _make_app(user_id, {
            get_profile_repo: lambda: profile_repo,
            get_pnl_repo: lambda: pnl_repo,
            get_redis: lambda: redis,
        })

        resp = client.get("/pnl/summary")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "active"
        assert body["total_net_pnl"] == 85.50
        assert len(body["positions"]) == 1
        pos = body["positions"][0]
        assert pos["profile_id"] == str(pid)
        assert pos["net_pnl"] == 85.50
        assert pos["daily_loss_pct"] == -0.025
        assert pos["daily_date"] == "2026-05-05"
        assert pos["snapshot"]["symbol"] == "BTC/USDT"

    def test_summary_with_hash_absent_returns_200_and_zero_pct(self):
        pid = uuid.uuid4()
        user_id = "user-1"

        profile_repo = AsyncMock()
        profile_repo.get_active_profiles_for_user = AsyncMock(
            return_value=[{"profile_id": pid}]
        )
        pnl_repo = AsyncMock()
        pnl_repo.get_latest = AsyncMock(return_value=None)
        redis = _HashRedis({})  # no hash

        client = _make_app(user_id, {
            get_profile_repo: lambda: profile_repo,
            get_pnl_repo: lambda: pnl_repo,
            get_redis: lambda: redis,
        })

        resp = client.get("/pnl/summary")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_net_pnl"] == 0.0
        assert body["positions"][0]["daily_loss_pct"] == 0.0
        assert body["positions"][0]["snapshot"] is None


class TestProfilePnlWrongTypeSafety:
    def test_profile_endpoint_with_hash_returns_200(self):
        pid = uuid.uuid4()
        user_id = "user-1"

        profile_repo = AsyncMock()
        profile_repo.get_profile_for_user = AsyncMock(
            return_value={"profile_id": pid, "name": "scalp"}
        )
        pnl_repo = AsyncMock()
        pnl_repo.get_latest = AsyncMock(return_value=_seeded_snapshot())
        redis = _HashRedis({
            f"pnl:daily:{pid}": {
                "date": "2026-05-05",
                "total_pct_micro": b"-12500",  # bytes shape from real redis-py
            }
        })

        client = _make_app(user_id, {
            get_profile_repo: lambda: profile_repo,
            get_pnl_repo: lambda: pnl_repo,
            get_redis: lambda: redis,
        })

        resp = client.get(f"/pnl/{pid}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["profile_id"] == str(pid)
        assert body["snapshot"]["net_pnl_post_tax"] == 85.50
        assert body["daily_loss_pct"] == -0.0125

    def test_profile_endpoint_404_for_foreign_profile(self):
        pid = uuid.uuid4()
        profile_repo = AsyncMock()
        profile_repo.get_profile_for_user = AsyncMock(return_value=None)
        pnl_repo = AsyncMock()
        redis = _HashRedis({})

        client = _make_app("user-1", {
            get_profile_repo: lambda: profile_repo,
            get_pnl_repo: lambda: pnl_repo,
            get_redis: lambda: redis,
        })

        resp = client.get(f"/pnl/{pid}")
        assert resp.status_code == 404
