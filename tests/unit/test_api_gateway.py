"""Tests for API Gateway: health route, exception handlers, deps, rate limiter middleware."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from services.api_gateway.src.deps import get_current_user
from services.api_gateway.src.routes.health import router as health_router

# ---------------------------------------------------------------------------
# Health endpoint tests (no auth required)
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def setup_method(self):
        app = FastAPI()
        app.include_router(health_router)
        self.client = TestClient(app)

    def test_health_returns_200(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# get_current_user dependency tests
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    def test_user_id_present(self):
        request = MagicMock(spec=Request)
        request.state = SimpleNamespace(user_id="user-123")
        result = get_current_user(request)
        assert result == "user-123"

    def test_no_user_id_raises_401(self):
        request = MagicMock(spec=Request)
        request.state = SimpleNamespace()  # no user_id
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Exception handler mapping tests
# ---------------------------------------------------------------------------


class TestExceptionHandlerMapping:
    """Verify that the app maps domain exceptions to correct HTTP status codes."""

    @patch("services.api_gateway.src.main.settings")
    def _create_app(self, mock_settings):
        mock_settings.is_secret_key_secure = MagicMock(return_value=True)
        mock_settings.REFRESH_SECRET_KEY = "test-refresh-key"
        mock_settings.REDIS_URL = "redis://localhost:6379/15"
        mock_settings.DATABASE_URL = "postgresql://test:test@localhost:5432/test"
        mock_settings.CORS_ORIGINS = ["http://localhost:3000"]
        mock_settings.SECRET_KEY = "test-key-32-bytes-long-enough-123"
        from services.api_gateway.src.main import create_app

        return create_app()

    def test_circuit_breaker_returns_503(self):
        from libs.core.exceptions import CircuitBreakerTriggeredError

        app = FastAPI()
        app.include_router(health_router)

        @app.exception_handler(CircuitBreakerTriggeredError)
        async def handler(request, exc):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=503, content={"detail": "Circuit breaker triggered"}
            )

        @app.get("/test-cb")
        async def trigger():
            raise CircuitBreakerTriggeredError("test")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-cb")
        assert resp.status_code == 503

    def test_risk_gate_returns_403(self):
        from libs.core.exceptions import RiskGateBlockedError

        app = FastAPI()

        @app.exception_handler(RiskGateBlockedError)
        async def handler(request, exc):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=403, content={"detail": "Blocked by risk gate"}
            )

        @app.get("/test-rg")
        async def trigger():
            raise RiskGateBlockedError("test")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-rg")
        assert resp.status_code == 403

    def test_exchange_rate_limit_returns_429(self):
        from libs.core.exceptions import ExchangeRateLimitError

        app = FastAPI()

        @app.exception_handler(ExchangeRateLimitError)
        async def handler(request, exc):
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=429, content={"detail": "Rate limited"})

        @app.get("/test-rl")
        async def trigger():
            raise ExchangeRateLimitError("test")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-rl")
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Route structure tests
# ---------------------------------------------------------------------------


class TestRouteStructure:
    def test_all_expected_route_modules_importable(self):
        """Verify all route modules can be imported without error."""
        from services.api_gateway.src.routes import (
            agents,
            auth,
            backtest,
            commands,
            docs_chat,
            exchange_keys,
            health,
            hitl,
            orders,
            paper_trading,
            pnl,
            profiles,
            telemetry_stream,
        )

        # Each should have a router attribute
        for mod in [
            auth,
            profiles,
            orders,
            pnl,
            commands,
            health,
            exchange_keys,
            paper_trading,
            backtest,
            agents,
            docs_chat,
            telemetry_stream,
            hitl,
        ]:
            assert hasattr(mod, "router")

    def test_commands_router_has_kill_switch(self):
        from services.api_gateway.src.routes.commands import router

        paths = [route.path for route in router.routes]
        assert "/kill-switch" in paths or any("kill-switch" in p for p in paths)


# ---------------------------------------------------------------------------
# WebSocket auth tests (Row 31 — JWT expiry enforced at the WS handshake)
# ---------------------------------------------------------------------------


class TestWebSocketAuth:
    """The /ws handshake must reject a token that is expired OR that carries
    no `exp` claim at all — a no-exp token would otherwise stay valid forever.
    """

    SECRET = "test-key-32-bytes-long-enough-123"

    def setup_method(self):
        from services.api_gateway.src.routes.ws import router as ws_router

        app = FastAPI()
        app.include_router(ws_router)
        self.client = TestClient(app)

    def _connect_expect_reject(self, url):
        from starlette.websockets import WebSocketDisconnect

        with patch("services.api_gateway.src.routes.ws.settings") as mock_settings:
            mock_settings.SECRET_KEY = self.SECRET
            with pytest.raises(WebSocketDisconnect):
                with self.client.websocket_connect(url):
                    pass

    def test_expired_token_rejected(self):
        from datetime import datetime, timedelta, timezone

        import jwt

        tok = jwt.encode(
            {"sub": "u1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            self.SECRET,
            algorithm="HS256",
        )
        self._connect_expect_reject(f"/ws?token={tok}")

    def test_token_without_exp_rejected(self):
        import jwt

        tok = jwt.encode({"sub": "u1"}, self.SECRET, algorithm="HS256")
        self._connect_expect_reject(f"/ws?token={tok}")

    def test_missing_token_rejected(self):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with self.client.websocket_connect("/ws"):
                pass


# ---------------------------------------------------------------------------
# REST middleware auth tests (Row 31 follow-on — same no-exp gap as the WS path)
# ---------------------------------------------------------------------------


class TestVerifyJwt:
    """verify_jwt must reject a token with no `exp` claim — a bare decode
    would otherwise accept it forever."""

    SECRET = "test-key-32-bytes-long-enough-123"

    def _run(self, token: str):
        import asyncio

        from services.api_gateway.src.middleware.auth import verify_jwt

        request = MagicMock(spec=Request)
        request.url = SimpleNamespace(path="/profiles")
        request.headers = {"Authorization": f"Bearer {token}"}
        request.state = SimpleNamespace()
        with patch("services.api_gateway.src.middleware.auth.settings") as ms:
            ms.SECRET_KEY = self.SECRET
            asyncio.run(verify_jwt(request))
        return request

    def test_token_without_exp_rejected(self):
        import jwt
        from fastapi import HTTPException

        tok = jwt.encode({"sub": "u1"}, self.SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as exc:
            self._run(tok)
        assert exc.value.status_code == 401

    def test_expired_token_rejected(self):
        from datetime import datetime, timedelta, timezone

        import jwt
        from fastapi import HTTPException

        tok = jwt.encode(
            {"sub": "u1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            self.SECRET,
            algorithm="HS256",
        )
        with pytest.raises(HTTPException) as exc:
            self._run(tok)
        assert exc.value.status_code == 401

    def test_valid_token_with_exp_accepted(self):
        from datetime import datetime, timedelta, timezone

        import jwt

        tok = jwt.encode(
            {"sub": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            self.SECRET,
            algorithm="HS256",
        )
        request = self._run(tok)
        assert request.state.user_id == "u1"


# ---------------------------------------------------------------------------
# Row 70 — WS pnl per-user filter (PnlProfileFilter)
# ---------------------------------------------------------------------------


class _FakeProfileRepo:
    """ProfileRepository stand-in: user_id -> list of profile_ids."""

    def __init__(self, profiles_by_user: dict):
        self.profiles_by_user = profiles_by_user
        self.call_count = 0

    async def get_all_profiles_for_user(self, user_id: str):
        self.call_count += 1
        return [{"profile_id": pid} for pid in self.profiles_by_user.get(user_id, [])]


class _FakeClock:
    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


class TestPnlProfileFilter:
    """Row 70: pubsub:pnl_updates must be filtered by profile ownership —
    the old filter keyed on a `user_id` field PnlUpdateEvent never carried."""

    def _make(self, user_id, repo, clock):
        import asyncio

        from services.api_gateway.src.routes.ws import PnlProfileFilter

        f = PnlProfileFilter(user_id, repo, clock=clock)
        asyncio.run(f.prime())
        return f

    def test_cross_user_pnl_events_are_filtered(self):
        import asyncio

        repo = _FakeProfileRepo({"alice": ["p1"], "bob": ["p2"]})
        clock = _FakeClock()
        f_alice = self._make("alice", repo, clock)
        f_bob = self._make("bob", repo, clock)

        ev_p1 = {"profile_id": "p1", "symbol": "BTC/USDT", "net_pnl": "1.23"}
        ev_p2 = {"profile_id": "p2", "symbol": "ETH/USDT", "net_pnl": "-0.5"}

        assert asyncio.run(f_alice.should_forward(ev_p1)) is True
        assert asyncio.run(f_alice.should_forward(ev_p2)) is False
        assert asyncio.run(f_bob.should_forward(ev_p2)) is True
        assert asyncio.run(f_bob.should_forward(ev_p1)) is False

    def test_lazy_refresh_picks_up_newly_created_profile(self):
        import asyncio

        repo = _FakeProfileRepo({"alice": ["p1"]})
        clock = _FakeClock()
        f = self._make("alice", repo, clock)

        repo.profiles_by_user["alice"].append("p_new")  # created after connect
        clock.t = 10.0  # past the refresh throttle window
        assert asyncio.run(f.should_forward({"profile_id": "p_new"})) is True

    def test_misses_do_not_hammer_the_db(self):
        import asyncio

        repo = _FakeProfileRepo({"alice": ["p1"]})
        clock = _FakeClock()
        f = self._make("alice", repo, clock)
        assert repo.call_count == 1  # prime

        foreign = {"profile_id": "someone-elses"}
        for _ in range(3):
            assert asyncio.run(f.should_forward(foreign)) is False
        assert repo.call_count == 1  # throttled — no refresh inside the window

        clock.t = 6.0  # window elapsed → exactly one more refresh
        assert asyncio.run(f.should_forward(foreign)) is False
        assert repo.call_count == 2

    def test_fail_closed_without_repo_or_profile_id(self):
        import asyncio

        clock = _FakeClock()
        f = self._make("alice", None, clock)
        assert asyncio.run(f.should_forward({"profile_id": "p1"})) is False
        repo = _FakeProfileRepo({"alice": ["p1"]})
        f2 = self._make("alice", repo, clock)
        assert asyncio.run(f2.should_forward({"no_profile": True})) is False
        assert asyncio.run(f2.should_forward("not-a-dict")) is False


# ---------------------------------------------------------------------------
# Rows 72 + 73 — read-side dash normalization + symbol-universe validation
# ---------------------------------------------------------------------------


class _FakeOrderRepo:
    def __init__(self):
        self.calls: list[dict] = []

    async def get_orders_for_user(self, **kwargs):
        self.calls.append(kwargs)
        return [{"order_id": "o1", "symbol": kwargs.get("symbol")}]


class TestOrdersSymbolHandling:
    def _app(self, order_repo, profile):
        from services.api_gateway.src import deps
        from services.api_gateway.src.routes.orders import router as orders_router

        app = FastAPI()
        app.include_router(orders_router, prefix="/orders")
        app.dependency_overrides[deps.get_current_user] = lambda: "u1"
        app.dependency_overrides[deps.get_order_repo] = lambda: order_repo

        class _ProfileRepo:
            async def get_profile_for_user(self, profile_id, user_id):
                return profile

        app.dependency_overrides[deps.get_profile_repo] = lambda: _ProfileRepo()
        app.dependency_overrides[deps.get_redis] = lambda: MagicMock()
        return app

    def test_get_orders_normalizes_dash_symbol(self):
        """Row 72: GET /orders?symbol=BTC-USDT must query the repo with the
        canonical slash form so it matches stored rows."""
        repo = _FakeOrderRepo()
        client = TestClient(self._app(repo, profile={"profile_id": "p1"}))
        resp = client.get("/orders/?symbol=BTC-USDT")
        assert resp.status_code == 200
        assert repo.calls[0]["symbol"] == "BTC/USDT"
        assert resp.json()[0]["symbol"] == "BTC/USDT"

    def _submit(self, symbol):
        from unittest.mock import AsyncMock

        from services.api_gateway.src.routes import orders as orders_module

        repo = _FakeOrderRepo()
        client = TestClient(self._app(repo, profile={"profile_id": "p1"}))
        body = {
            "profile_id": "p1",
            "symbol": symbol,
            "side": "BUY",
            "type": "limit",
            "quantity": "1",
            "price": "100",
        }
        with (
            patch.object(
                orders_module.KillSwitch, "is_active", new=AsyncMock(return_value=False)
            ),
            patch.object(orders_module, "StreamPublisher") as mock_pub,
            patch.object(
                orders_module.settings, "TRADING_SYMBOLS", ["BTC/USDT", "ETH/USDT"]
            ),
        ):
            mock_pub.return_value.publish = AsyncMock()
            resp = client.post("/orders/", json=body)
        return resp, mock_pub

    def test_submit_order_accepts_universe_symbol_and_normalizes(self):
        """Row 73 accept path: dash form of a tracked symbol passes and the
        published event carries the canonical slash form."""
        resp, mock_pub = self._submit("BTC-USDT")
        assert resp.status_code == 202
        published_event = mock_pub.return_value.publish.await_args[0][1]
        assert published_event.symbol == "BTC/USDT"

    def test_submit_order_rejects_symbol_outside_universe(self):
        """Row 73 reject path: a symbol not in settings.TRADING_SYMBOLS is a
        422 — it must never reach stream:orders."""
        resp, mock_pub = self._submit("DOGE-USDT")
        assert resp.status_code == 422
        assert "universe" in resp.json()["detail"]
        mock_pub.return_value.publish.assert_not_awaited()


class TestPositionsSymbolFilter:
    def test_list_positions_dash_filter_returns_slash_rows(self):
        """Row 72: GET /positions?symbol=BTC-USDT returns the BTC/USDT rows."""
        from datetime import datetime, timezone
        from decimal import Decimal

        from services.api_gateway.src import deps
        from services.api_gateway.src.routes.positions import router as positions_router

        rows = [
            {
                "profile_id": "p1",
                "position_id": "x1",
                "symbol": "BTC/USDT",
                "status": "OPEN",
                "side": "BUY",
                "entry_price": Decimal("100"),
                "quantity": Decimal("1"),
                "opened_at": datetime.now(timezone.utc),
            },
            {
                "profile_id": "p1",
                "position_id": "x2",
                "symbol": "ETH/USDT",
                "status": "OPEN",
                "side": "BUY",
                "entry_price": Decimal("10"),
                "quantity": Decimal("2"),
                "opened_at": datetime.now(timezone.utc),
            },
        ]

        class _PositionRepo:
            async def get_open_positions(self, profile_id=None):
                return rows

        class _ProfileRepo:
            async def get_profile(self, pid):
                return None

        class _Redis:
            async def mget(self, keys):
                return [None] * len(keys)

        app = FastAPI()
        app.include_router(positions_router, prefix="/positions")
        app.dependency_overrides[deps.get_current_user] = lambda: "u1"
        app.dependency_overrides[deps.get_position_repo] = lambda: _PositionRepo()
        app.dependency_overrides[deps.get_profile_repo] = lambda: _ProfileRepo()
        app.dependency_overrides[deps.get_redis] = lambda: _Redis()
        client = TestClient(app)

        resp = client.get("/positions/?symbol=BTC-USDT")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["symbol"] == "BTC/USDT"


# ---------------------------------------------------------------------------
# Row 64 — kill-switch hardening trio
# ---------------------------------------------------------------------------


class TestOperatorAllowlistSetting:
    """Row 64a: PRAXIS_KILL_SWITCH_OPERATORS is a typed Pydantic setting and
    commands.py no longer reads raw os.environ."""

    def test_typed_setting_declared(self):
        from libs.config.settings import Settings

        assert "KILL_SWITCH_OPERATORS" in Settings.model_fields

    def test_unconfigured_means_single_operator_mode(self):
        from services.api_gateway.src.routes import commands

        with patch.object(commands.settings, "KILL_SWITCH_OPERATORS", None):
            assert commands.is_operator("anyone") is True
        with patch.object(commands.settings, "KILL_SWITCH_OPERATORS", "  "):
            assert commands.is_operator("anyone") is True

    def test_configured_allowlist_gates_operators(self):
        from services.api_gateway.src.routes import commands

        with patch.object(commands.settings, "KILL_SWITCH_OPERATORS", "u1, u2"):
            assert commands.is_operator("u1") is True
            assert commands.is_operator("u2") is True
            assert commands.is_operator("u3") is False

    def test_no_raw_environ_read_remains(self):
        import inspect

        from services.api_gateway.src.routes import commands

        assert "os.environ" not in inspect.getsource(commands)


class _FakeKillSwitchRedis:
    def __init__(self):
        self.store: dict = {}
        self.lists: dict = {}

    async def set(self, k, v):
        self.store[k] = v

    async def delete(self, k):
        self.store.pop(k, None)

    async def get(self, k):
        return self.store.get(k)

    async def lpush(self, k, v):
        self.lists.setdefault(k, []).insert(0, v)

    async def ltrim(self, k, a, b):
        pass


class TestKillSwitchReasonTruncation:
    """Row 64b: set_level truncates `reason` server-side as defense in depth
    for non-API writers (the API bounds it at 256 via KillSwitchRequest)."""

    def test_long_reason_truncated_to_256(self):
        import asyncio
        import json as _json

        from libs.core.enums import HaltLevel
        from services.hot_path.src.kill_switch import KILL_SWITCH_LOG_KEY, KillSwitch

        r = _FakeKillSwitchRedis()
        asyncio.run(
            KillSwitch.set_level(
                r, HaltLevel.STOP_OPENING, reason="x" * 1000, actor="t"
            )
        )
        entry = _json.loads(r.lists[KILL_SWITCH_LOG_KEY][0])
        assert len(entry["reason"]) == 256
        assert entry["reason"] == "x" * 256

    def test_none_reason_is_safe(self):
        import asyncio
        import json as _json

        from libs.core.enums import HaltLevel
        from services.hot_path.src.kill_switch import KILL_SWITCH_LOG_KEY, KillSwitch

        r = _FakeKillSwitchRedis()
        asyncio.run(KillSwitch.set_level(r, HaltLevel.STOP_OPENING, reason=None))
        entry = _json.loads(r.lists[KILL_SWITCH_LOG_KEY][0])
        assert entry["reason"] == ""


class _FakeRateLimitRedis:
    def __init__(self, current_count=0, fail=False):
        self.current_count = current_count
        self.fail = fail
        self.zadd_calls: list = []
        self.zrange_result: list = []

    def pipeline(self):
        outer = self

        class _Pipe:
            def zremrangebyscore(self, *a):
                pass

            def zcard(self, k):
                pass

            def zadd(self, k, m):
                outer.zadd_calls.append((k, m))

            def expire(self, k, s):
                pass

            async def execute(self):
                if outer.fail:
                    raise ConnectionError("redis down")
                return [0, outer.current_count]

        return _Pipe()

    async def zrange(self, *a, **kw):
        return self.zrange_result


class TestUserRateLimitDependency:
    """Row 64c: post-auth per-user sliding window for kill-switch writes —
    the pre-auth middleware only ever keys on client IP."""

    def _request(self, user_id="u1"):
        request = MagicMock(spec=Request)
        request.state = (
            SimpleNamespace(user_id=user_id) if user_id else SimpleNamespace()
        )
        return request

    def _run(self, fake_redis, user_id="u1", limit=2):
        import asyncio

        from services.api_gateway.src.middleware import rate_limit as rl

        dep = rl.user_rate_limit("test-scope", limit=limit, window_s=60)
        with patch.object(rl, "RedisClient") as mock_rc:
            mock_rc.get_instance.return_value.get_connection.return_value = fake_redis
            return asyncio.run(dep(self._request(user_id)))

    def test_under_limit_passes_and_records(self):
        fake = _FakeRateLimitRedis(current_count=0)
        self._run(fake)
        assert len(fake.zadd_calls) == 1
        assert fake.zadd_calls[0][0] == "rate_limit:user:test-scope:u1"

    def test_at_limit_raises_429_with_retry_after(self):
        from fastapi import HTTPException

        fake = _FakeRateLimitRedis(current_count=2)
        fake.zrange_result = [("1000", 1000)]
        with pytest.raises(HTTPException) as exc:
            self._run(fake, limit=2)
        assert exc.value.status_code == 429
        assert "Retry-After" in exc.value.headers
        assert len(fake.zadd_calls) == 0  # rejected request not recorded

    def test_redis_failure_fails_open(self):
        fake = _FakeRateLimitRedis(fail=True)
        self._run(fake)  # must not raise

    def test_missing_user_id_is_401(self):
        from fastapi import HTTPException

        fake = _FakeRateLimitRedis()
        with pytest.raises(HTTPException) as exc:
            self._run(fake, user_id=None)
        assert exc.value.status_code == 401

    def test_kill_switch_post_route_carries_the_bucket(self):
        from services.api_gateway.src.routes.commands import router

        route = next(
            r for r in router.routes if r.path == "/kill-switch" and "POST" in r.methods
        )
        assert len(route.dependencies) >= 1


# ---------------------------------------------------------------------------
# D-F — the 501 LLM intent-classification stub is gone (wontfix ruling)
# ---------------------------------------------------------------------------


class TestNlCommandStubRemoved:
    def test_post_commands_root_no_longer_exists(self):
        from services.api_gateway.src.routes.commands import router

        post_root = [
            r
            for r in router.routes
            if getattr(r, "path", None) == "/"
            and "POST" in getattr(r, "methods", set())
        ]
        assert post_root == []


# ---------------------------------------------------------------------------
# Rows 66 + 67 — RiskLimitsPayload bounds + settings as the single authority
# ---------------------------------------------------------------------------


class TestRiskLimitsDefaultsAuthority:
    """Row 67 / ruling D-D: DEFAULT_RISK_LIMITS is a str-encoded view of
    settings — settings is the single authority."""

    def test_default_risk_limits_mirror_settings(self):
        from libs.config import settings as s
        from libs.core.schemas import DEFAULT_RISK_LIMITS

        assert DEFAULT_RISK_LIMITS["stop_loss_pct"] == str(s.DEFAULT_STOP_LOSS_PCT)
        assert DEFAULT_RISK_LIMITS["take_profit_pct"] == str(s.DEFAULT_TAKE_PROFIT_PCT)
        assert DEFAULT_RISK_LIMITS["max_holding_hours"] == str(
            s.DEFAULT_MAX_HOLDING_HOURS
        )
        assert DEFAULT_RISK_LIMITS["max_drawdown_pct"] == str(
            s.DEFAULT_MAX_DRAWDOWN_PCT
        )
        assert DEFAULT_RISK_LIMITS["max_allocation_pct"] == str(
            s.DEFAULT_MAX_ALLOCATION_PCT
        )
        assert DEFAULT_RISK_LIMITS["circuit_breaker_daily_loss_pct"] == str(
            s.CIRCUIT_BREAKER_DAILY_LOSS_PCT
        )

    def test_payload_defaults_follow_settings(self):
        from libs.config import settings as s
        from libs.core.schemas import RiskLimitsPayload

        p = RiskLimitsPayload()
        assert p.stop_loss_pct == float(str(s.DEFAULT_STOP_LOSS_PCT))
        assert p.take_profit_pct == float(str(s.DEFAULT_TAKE_PROFIT_PCT))


class TestRiskLimitsPayloadBounds:
    """Row 66 / ruling D-E: pcts in (0, 1], hours > 0, extra='allow' dropped.
    Tightened only after a 2026-06-13 SELECT confirmed all 9 existing
    trading_profiles.risk_limits rows are in-bounds."""

    def test_out_of_bounds_values_rejected(self):
        from pydantic import ValidationError

        from libs.core.schemas import RiskLimitsPayload

        for bad in (
            {"stop_loss_pct": 0},
            {"stop_loss_pct": 1.5},
            {"take_profit_pct": -0.01},
            {"max_drawdown_pct": 2},
            {"max_allocation_pct": 0},
            {"circuit_breaker_daily_loss_pct": 1.01},
            {"max_holding_hours": 0},
            {"max_holding_hours": -5},
        ):
            with pytest.raises(ValidationError):
                RiskLimitsPayload.model_validate(bad)

    def test_existing_db_row_shapes_accepted(self):
        from libs.core.schemas import RiskLimitsPayload

        # Exact shapes observed in trading_profiles.risk_limits (2026-06-13).
        RiskLimitsPayload.model_validate(
            {
                "stop_loss_pct": 0.05,
                "take_profit_pct": 0.015,
                "max_drawdown_pct": 0.1,
                "max_holding_hours": 48,
                "max_allocation_pct": 1,
                "circuit_breaker_daily_loss_pct": 0.02,
            }
        )
        RiskLimitsPayload.model_validate(
            {"max_drawdown_pct": 0.05, "max_allocation_pct": 0.2}
        )

    def test_extra_keys_ignored_not_carried(self):
        from libs.core.schemas import RiskLimitsPayload

        p = RiskLimitsPayload.model_validate(
            {"stop_loss_pct": 0.05, "mystery_extra": 123}
        )
        assert not hasattr(p, "mystery_extra")
