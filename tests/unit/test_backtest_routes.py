"""Security regression tests for services/api_gateway/src/routes/backtest.py.

The profile-ownership check in create_backtest used to run ONLY when the
request omitted risk_limits (the branch that loads them from the profile).
Supplying any explicit risk_limits skipped the check entirely while still
copying req.profile_id verbatim into the job payload — letting an
authenticated user persist a backtest under ANOTHER user's profile_id and
poison that profile's decay-tracker baseline (latest_for_profile reads
backtest_results.profile_id with no created_by scoping).

These tests pin the fix: ownership (and UUID shape) is validated whenever
profile_id is present, regardless of risk_limits.
"""

import uuid
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api_gateway.src.deps import (
    get_current_user,
    get_profile_repo,
    get_redis,
)
from services.api_gateway.src.routes.backtest import router as backtest_router

USER_ID = str(uuid.uuid4())
PROFILE_ID = str(uuid.uuid4())

VALID_RULES = {
    "direction": "long",
    "match_mode": "all",
    "signals": [{"indicator": "rsi", "comparison": "below", "threshold": 30}],
    "confidence": 0.8,
}

EXPLICIT_LIMITS = {"stop_loss_pct": 0.03, "take_profit_pct": 0.06}


def _body(**overrides):
    body = {
        "symbol": "BTC/USDT",
        "strategy_rules": VALID_RULES,
        "start_date": "2025-01-01T00:00:00",
        "end_date": "2025-02-01T00:00:00",
    }
    body.update(overrides)
    return body


def _redis_mock():
    redis = AsyncMock()
    redis.xlen = AsyncMock(return_value=0)
    redis.xadd = AsyncMock()
    redis.set = AsyncMock()
    return redis


def _client(profile_repo, redis) -> TestClient:
    app = FastAPI()
    app.include_router(backtest_router, prefix="/backtest")
    app.dependency_overrides[get_current_user] = lambda: USER_ID
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_profile_repo] = lambda: profile_repo
    return TestClient(app)


def _enqueued_payload(redis):
    import json

    assert redis.xadd.await_count == 1
    args, _ = redis.xadd.await_args
    return json.loads(args[1]["data"])


class TestCreateBacktestProfileOwnership:
    def test_foreign_profile_with_explicit_risk_limits_is_rejected(self):
        """The exploit path: explicit risk_limits + someone else's profile_id
        must 404 and enqueue nothing."""
        profile_repo = AsyncMock()
        profile_repo.get_profile_for_user = AsyncMock(return_value=None)
        redis = _redis_mock()
        client = _client(profile_repo, redis)

        resp = client.post(
            "/backtest/",
            json=_body(profile_id=PROFILE_ID, risk_limits=EXPLICIT_LIMITS),
        )

        assert resp.status_code == 404
        profile_repo.get_profile_for_user.assert_awaited_once_with(
            PROFILE_ID, USER_ID
        )
        redis.xadd.assert_not_awaited()

    def test_non_uuid_profile_id_with_explicit_risk_limits_is_rejected(self):
        """profile_id is stored as TEXT — the UUID parse must run on the
        explicit-risk_limits path too (400, nothing enqueued)."""
        profile_repo = AsyncMock()
        profile_repo.get_profile_for_user = AsyncMock(
            side_effect=ValueError("badly formed hexadecimal UUID string")
        )
        redis = _redis_mock()
        client = _client(profile_repo, redis)

        resp = client.post(
            "/backtest/",
            json=_body(profile_id="not-a-uuid", risk_limits=EXPLICIT_LIMITS),
        )

        assert resp.status_code == 400
        redis.xadd.assert_not_awaited()

    def test_owned_profile_with_explicit_risk_limits_enqueues(self):
        """Owner + explicit risk_limits: ownership verified, the explicit
        limits (not the profile's) ride the job payload."""
        profile_repo = AsyncMock()
        profile_repo.get_profile_for_user = AsyncMock(
            return_value={
                "profile_id": PROFILE_ID,
                "risk_limits": {"stop_loss_pct": 0.99},
            }
        )
        redis = _redis_mock()
        client = _client(profile_repo, redis)

        resp = client.post(
            "/backtest/",
            json=_body(profile_id=PROFILE_ID, risk_limits=EXPLICIT_LIMITS),
        )

        assert resp.status_code == 200
        profile_repo.get_profile_for_user.assert_awaited_once_with(
            PROFILE_ID, USER_ID
        )
        payload = _enqueued_payload(redis)
        assert payload["profile_id"] == PROFILE_ID
        assert payload["risk_limits"] == EXPLICIT_LIMITS

    def test_owned_profile_without_risk_limits_loads_profile_limits(self):
        """Original behavior preserved: no explicit limits → the profile's
        risk_limits are resolved and enqueued."""
        profile_limits = {"stop_loss_pct": 0.02, "take_profit_pct": 0.05}
        profile_repo = AsyncMock()
        profile_repo.get_profile_for_user = AsyncMock(
            return_value={"profile_id": PROFILE_ID, "risk_limits": profile_limits}
        )
        redis = _redis_mock()
        client = _client(profile_repo, redis)

        resp = client.post("/backtest/", json=_body(profile_id=PROFILE_ID))

        assert resp.status_code == 200
        payload = _enqueued_payload(redis)
        assert payload["risk_limits"] == profile_limits

    def test_no_profile_id_skips_ownership_check(self):
        profile_repo = AsyncMock()
        redis = _redis_mock()
        client = _client(profile_repo, redis)

        resp = client.post("/backtest/", json=_body(risk_limits=EXPLICIT_LIMITS))

        assert resp.status_code == 200
        profile_repo.get_profile_for_user.assert_not_awaited()
        payload = _enqueued_payload(redis)
        assert payload["profile_id"] == ""
        assert payload["risk_limits"] == EXPLICIT_LIMITS
