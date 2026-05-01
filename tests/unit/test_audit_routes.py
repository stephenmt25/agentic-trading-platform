"""Unit tests for the PR1 audit API routes (services/api_gateway/src/routes/audit.py).

Verifies:
  - Audit module imports cleanly and exposes a router
  - All 6 endpoints are registered at the expected paths
  - get_by_decision_event_id helpers on OrderRepository / PositionRepository
    construct the right SQL
  - The chain endpoint serializer assembles the 4-stage payload
  - 404s are returned when stages are missing
"""

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api_gateway.src.routes import audit
from services.api_gateway.src.routes.audit import router as audit_router
from libs.storage.repositories.order_repo import OrderRepository
from libs.storage.repositories.position_repo import PositionRepository
from services.api_gateway.src.deps import (
    get_closed_trade_repo,
    get_debate_repo,
    get_decision_repo,
    get_order_repo,
    get_position_repo,
)


# ---------------------------------------------------------------------------
# Repo SQL tests
# ---------------------------------------------------------------------------

class TestOrderRepoChainQuery:
    @pytest.mark.asyncio
    async def test_get_by_decision_event_id_constructs_sql(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)
        repo = OrderRepository(db)
        eid = uuid.uuid4()
        result = await repo.get_by_decision_event_id(eid)
        assert result is None
        sql, *args = db.fetchrow.call_args.args
        assert "FROM orders" in sql
        assert "WHERE decision_event_id = $1" in sql
        assert "LIMIT 1" in sql
        assert args[0] == eid

    @pytest.mark.asyncio
    async def test_returns_dict_when_row_present(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={"order_id": "abc", "status": "CONFIRMED"})
        repo = OrderRepository(db)
        result = await repo.get_by_decision_event_id(uuid.uuid4())
        assert result == {"order_id": "abc", "status": "CONFIRMED"}


class TestPositionRepoChainQuery:
    @pytest.mark.asyncio
    async def test_get_by_decision_event_id_constructs_sql(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)
        repo = PositionRepository(db)
        eid = uuid.uuid4()
        await repo.get_by_decision_event_id(eid)
        sql, *args = db.fetchrow.call_args.args
        assert "FROM positions" in sql
        assert "WHERE decision_event_id = $1" in sql
        assert "LIMIT 1" in sql
        assert args[0] == eid


# ---------------------------------------------------------------------------
# Router structure
# ---------------------------------------------------------------------------

class TestAuditRouter:
    def test_router_module_importable(self):
        assert hasattr(audit, "router")

    def test_all_endpoints_registered(self):
        paths = sorted(route.path for route in audit_router.routes)
        expected = [
            "/chain/{decision_event_id}",
            "/closed-trades",
            "/closed-trades/by-decision/{decision_event_id}",
            "/closed-trades/by-position/{position_id}",
            "/debate",
            "/debate/{cycle_id}",
        ]
        for ep in expected:
            assert ep in paths, f"Missing audit endpoint: {ep}"


# ---------------------------------------------------------------------------
# Endpoint behavior — using TestClient with dependency overrides
# ---------------------------------------------------------------------------

def _make_test_app(overrides: dict) -> TestClient:
    """Build a minimal FastAPI app mounting only the audit router with overridden deps."""
    app = FastAPI()
    app.include_router(audit_router, prefix="/audit")
    for dep, override in overrides.items():
        app.dependency_overrides[dep] = override
    return TestClient(app)


class TestClosedTradesEndpoint:
    def test_list_returns_serialized_rows(self):
        ctr = AsyncMock()
        ctr.get_recent = AsyncMock(return_value=[
            {"position_id": uuid.uuid4(), "symbol": "BTC/USDT", "outcome": "win"},
            {"position_id": uuid.uuid4(), "symbol": "BTC/USDT", "outcome": "loss"},
        ])
        client = _make_test_app({get_closed_trade_repo: lambda: ctr})
        resp = client.get("/audit/closed-trades?symbol=BTC/USDT&limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        # UUIDs are stringified
        assert isinstance(body[0]["position_id"], str)
        ctr.get_recent.assert_awaited_once_with(symbol="BTC/USDT", limit=10)

    def test_by_position_404_when_missing(self):
        ctr = AsyncMock()
        ctr.get_by_position = AsyncMock(return_value=None)
        client = _make_test_app({get_closed_trade_repo: lambda: ctr})
        pid = str(uuid.uuid4())
        resp = client.get(f"/audit/closed-trades/by-position/{pid}")
        assert resp.status_code == 404

    def test_by_position_invalid_uuid_returns_400(self):
        ctr = AsyncMock()
        client = _make_test_app({get_closed_trade_repo: lambda: ctr})
        resp = client.get("/audit/closed-trades/by-position/not-a-uuid")
        assert resp.status_code == 400


class TestDebateEndpoints:
    def test_get_cycle_returns_cycle_plus_rounds(self):
        cid = uuid.uuid4()
        repo = AsyncMock()
        repo.get_cycle_with_rounds = AsyncMock(return_value={
            "cycle": {"cycle_id": cid, "symbol": "BTC/USDT", "final_score": 0.42},
            "rounds": [
                {"round_num": 1, "bull_argument": "a", "bear_argument": "b"},
                {"round_num": 2, "bull_argument": "c", "bear_argument": "d"},
            ],
        })
        client = _make_test_app({get_debate_repo: lambda: repo})
        resp = client.get(f"/audit/debate/{cid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cycle"]["cycle_id"] == str(cid)
        assert len(body["rounds"]) == 2
        assert body["rounds"][0]["round_num"] == 1

    def test_get_cycle_404(self):
        repo = AsyncMock()
        repo.get_cycle_with_rounds = AsyncMock(return_value=None)
        client = _make_test_app({get_debate_repo: lambda: repo})
        resp = client.get(f"/audit/debate/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestChainEndpoint:
    def test_assembles_full_lineage(self):
        eid = uuid.uuid4()
        decision_repo = AsyncMock()
        decision_repo.get_decision = AsyncMock(return_value={"event_id": eid, "outcome": "APPROVED"})
        order_repo = AsyncMock()
        order_repo.get_by_decision_event_id = AsyncMock(return_value={"order_id": uuid.uuid4(), "status": "CONFIRMED"})
        position_repo = AsyncMock()
        position_repo.get_by_decision_event_id = AsyncMock(return_value={"position_id": uuid.uuid4(), "status": "CLOSED"})
        ctr = AsyncMock()
        ctr.get_by_decision_event = AsyncMock(return_value={"position_id": uuid.uuid4(), "outcome": "win"})

        client = _make_test_app({
            get_decision_repo: lambda: decision_repo,
            get_order_repo: lambda: order_repo,
            get_position_repo: lambda: position_repo,
            get_closed_trade_repo: lambda: ctr,
        })
        resp = client.get(f"/audit/chain/{eid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] is not None
        assert body["order"] is not None
        assert body["position"] is not None
        assert body["closed_trade"] is not None
        assert body["closed_trade"]["outcome"] == "win"

    def test_404_when_decision_missing(self):
        decision_repo = AsyncMock()
        decision_repo.get_decision = AsyncMock(return_value=None)
        order_repo = AsyncMock()
        position_repo = AsyncMock()
        ctr = AsyncMock()
        client = _make_test_app({
            get_decision_repo: lambda: decision_repo,
            get_order_repo: lambda: order_repo,
            get_position_repo: lambda: position_repo,
            get_closed_trade_repo: lambda: ctr,
        })
        resp = client.get(f"/audit/chain/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_returns_nulls_for_downstream_stages_not_yet_present(self):
        """Decision exists but order/position/closed_trade do not (e.g. brand new APPROVED, still in flight)."""
        eid = uuid.uuid4()
        decision_repo = AsyncMock()
        decision_repo.get_decision = AsyncMock(return_value={"event_id": eid, "outcome": "APPROVED"})
        order_repo = AsyncMock()
        order_repo.get_by_decision_event_id = AsyncMock(return_value=None)
        position_repo = AsyncMock()
        position_repo.get_by_decision_event_id = AsyncMock(return_value=None)
        ctr = AsyncMock()
        ctr.get_by_decision_event = AsyncMock(return_value=None)
        client = _make_test_app({
            get_decision_repo: lambda: decision_repo,
            get_order_repo: lambda: order_repo,
            get_position_repo: lambda: position_repo,
            get_closed_trade_repo: lambda: ctr,
        })
        resp = client.get(f"/audit/chain/{eid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] is not None
        assert body["order"] is None
        assert body["position"] is None
        assert body["closed_trade"] is None
