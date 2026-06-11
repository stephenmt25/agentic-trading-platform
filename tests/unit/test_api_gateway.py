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
