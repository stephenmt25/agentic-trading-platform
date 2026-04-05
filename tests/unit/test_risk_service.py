"""Unit tests for the Risk service.

Tests position size limits, concentration limits, circuit breaker,
and portfolio-level risk guards.
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.risk.src import RiskService, RiskCheckResult


# ---------------------------------------------------------------------------
# RiskService tests
# ---------------------------------------------------------------------------

class TestRiskService:
    def _make_service(self, mock_profile_repo=None, mock_position_repo=None, mock_redis=None, redis_client=None):
        r = mock_redis or redis_client
        return RiskService(
            profile_repo=mock_profile_repo,
            position_repo=mock_position_repo,
            redis_client=r,
        )

    @pytest.mark.asyncio
    async def test_system_wide_limits_are_float(self):
        """System-wide limits should be numeric (currently float — tech debt for Phase B)."""
        svc = self._make_service()
        assert svc.MAX_SINGLE_ORDER_USD == 50_000.0
        assert svc.MAX_POSITION_CONCENTRATION_PCT == 0.25
        assert svc.MAX_OPEN_POSITIONS_PER_PROFILE == 50

    @pytest.mark.asyncio
    async def test_rejects_order_exceeding_hard_cap(self):
        """Orders exceeding $50k system-wide cap should be rejected."""
        svc = self._make_service()
        result = await svc.check_order(
            profile_id="prof-1", symbol="BTC/USDT",
            quantity=2.0, price=30000.0, side="BUY",
        )
        assert result.allowed is False
        assert "cap" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_allows_order_within_cap(self):
        """Orders within $50k cap should be allowed (no repos configured)."""
        svc = self._make_service()
        result = await svc.check_order(
            profile_id="prof-1", symbol="BTC/USDT",
            quantity=0.5, price=50000.0, side="BUY",
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rejects_on_too_many_open_positions(self, mock_profile_repo, mock_position_repo):
        """Reject when open position count reaches the limit."""
        # Give a large portfolio so allocation check passes
        mock_profile_repo.get_profile = AsyncMock(return_value={
            "profile_id": "prof-1",
            "allocation_pct": "100.0",  # large portfolio
            "risk_limits": json.dumps({"max_allocation_pct": 1.0}),
        })
        # Return 50 open positions (at the limit)
        mock_position_repo.get_open_positions = AsyncMock(
            return_value=[{"position_id": f"pos-{i}", "symbol": "ETH/USDT", "quantity": "0.001", "entry_price": "3000"} for i in range(50)]
        )
        svc = self._make_service(mock_profile_repo, mock_position_repo)
        result = await svc.check_order(
            profile_id="prof-1", symbol="BTC/USDT",
            quantity=0.001, price=1000.0,  # small order to pass allocation
        )
        assert result.allowed is False
        assert "position count" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_rejects_on_concentration_limit(self, mock_profile_repo, mock_position_repo):
        """Reject when adding to a symbol would exceed 25% concentration."""
        # Profile has $10k portfolio
        mock_profile_repo.get_profile = AsyncMock(return_value={
            "profile_id": "prof-1",
            "allocation_pct": "1.0",
            "risk_limits": json.dumps({"max_allocation_pct": 1.0}),
        })
        # Already holding $2000 in BTC
        mock_position_repo.get_open_positions = AsyncMock(return_value=[
            {"symbol": "BTC/USDT", "quantity": "0.04", "entry_price": "50000"},
        ])
        svc = self._make_service(mock_profile_repo, mock_position_repo)
        # Trying to add another $2000 → total $4000 / $10k = 40% > 25%
        result = await svc.check_order(
            profile_id="prof-1", symbol="BTC/USDT",
            quantity=0.04, price=50000.0,
        )
        assert result.allowed is False
        assert "concentration" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_allows_order_with_normal_concentration(self, mock_profile_repo, mock_position_repo):
        """Allow orders that keep concentration under 25%."""
        mock_profile_repo.get_profile = AsyncMock(return_value={
            "profile_id": "prof-1",
            "allocation_pct": "1.0",
            "risk_limits": json.dumps({"max_allocation_pct": 1.0}),
        })
        mock_position_repo.get_open_positions = AsyncMock(return_value=[])
        svc = self._make_service(mock_profile_repo, mock_position_repo)
        result = await svc.check_order(
            profile_id="prof-1", symbol="BTC/USDT",
            quantity=0.01, price=50000.0,  # $500 / $10k = 5%
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rejects_when_trading_halted(self, mock_redis):
        """Reject all orders when circuit breaker halt key exists in Redis."""
        mock_redis.get = AsyncMock(return_value=b"daily loss exceeded 2%")
        svc = self._make_service(redis_client=mock_redis)
        result = await svc.check_order(
            profile_id="prof-1", symbol="BTC/USDT",
            quantity=0.01, price=50000.0,
        )
        assert result.allowed is False
        assert "halted" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_allows_when_no_halt(self, mock_redis):
        """Allow orders when no halt key exists."""
        mock_redis.get = AsyncMock(return_value=None)
        svc = self._make_service(redis_client=mock_redis)
        result = await svc.check_order(
            profile_id="prof-1", symbol="BTC/USDT",
            quantity=0.1, price=1000.0,  # $100 well under cap
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_result_dataclass_fields(self):
        """RiskCheckResult should have allowed and reason fields."""
        r1 = RiskCheckResult(allowed=True)
        assert r1.allowed is True
        assert r1.reason is None

        r2 = RiskCheckResult(allowed=False, reason="test")
        assert r2.allowed is False
        assert r2.reason == "test"
