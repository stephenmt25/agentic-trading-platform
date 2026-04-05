"""Shared fixtures for the Praxis Trading Platform test suite.

Provides mock Redis, TimescaleDB, messaging, and domain object factories
so that individual service tests can focus on business logic without
boilerplate infrastructure setup.
"""

import json
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.core.enums import (
    EventType, OrderSide, OrderStatus, PositionStatus,
    SignalDirection, Regime, ValidationCheck, ValidationVerdict, ValidationMode,
)
from libs.core.schemas import (
    OrderApprovedEvent, OrderExecutedEvent, OrderRejectedEvent,
    SignalEvent, ValidationRequestEvent,
)
from libs.core.models import Order, Position


# ---------------------------------------------------------------------------
# Redis mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """AsyncMock Redis client with common operations pre-configured."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)
    redis.lpush = AsyncMock(return_value=1)
    redis.ltrim = AsyncMock(return_value=True)
    redis.lrange = AsyncMock(return_value=[])
    redis.eval = AsyncMock(return_value="0")
    redis.expire = AsyncMock(return_value=True)

    # Pipeline support
    pipe = AsyncMock()
    pipe.get = MagicMock(return_value=pipe)
    pipe.hgetall = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[None, None, None, {}])
    redis.pipeline = MagicMock(return_value=pipe)

    return redis


# ---------------------------------------------------------------------------
# TimescaleDB / repository mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_timescale():
    """AsyncMock TimescaleClient."""
    ts = AsyncMock()
    ts.init_pool = AsyncMock()
    ts.close = AsyncMock()
    ts.health_check = AsyncMock(return_value=True)
    return ts


@pytest.fixture
def mock_order_repo():
    """AsyncMock OrderRepository."""
    repo = AsyncMock()
    repo.create_order = AsyncMock()
    repo.update_order_status = AsyncMock()
    repo.get_order = AsyncMock(return_value=None)
    repo.get_orders_for_user = AsyncMock(return_value=[])
    repo.cancel_order_for_user = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_position_repo():
    """AsyncMock PositionRepository."""
    repo = AsyncMock()
    repo.create_position = AsyncMock()
    repo.close_position = AsyncMock()
    repo.get_open_positions = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_audit_repo():
    """AsyncMock AuditRepository."""
    repo = AsyncMock()
    repo.write_audit_event = AsyncMock()
    return repo


@pytest.fixture
def mock_profile_repo():
    """AsyncMock ProfileRepository with a default test profile."""
    repo = AsyncMock()
    repo.get_profile = AsyncMock(return_value={
        "profile_id": "test-profile-001",
        "exchange_key_ref": "paper",
        "allocation_pct": "1.0",
        "risk_limits": json.dumps({
            "max_allocation_pct": 0.25,
            "stop_loss_pct": 0.05,
            "max_drawdown_pct": 0.10,
            "circuit_breaker_daily_loss_pct": 0.02,
        }),
    })
    repo.get_active_profiles = AsyncMock(return_value=[])
    repo.get_all_profiles_for_user = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_market_data_repo():
    """AsyncMock MarketDataRepository with sample candles."""
    repo = AsyncMock()
    # Generate 20 candles with incrementing prices for RSI/indicator tests
    candles = [
        {"close": str(100 + i * 0.5), "open": str(99.5 + i * 0.5),
         "high": str(101 + i * 0.5), "low": str(99 + i * 0.5),
         "volume": "1000", "timestamp": 1000000 + i * 300000000}
        for i in range(20)
    ]
    repo.get_candles = AsyncMock(return_value=candles)
    repo.get_candles_by_range = AsyncMock(return_value=candles[:6])
    return repo


@pytest.fixture
def mock_pnl_repo():
    """AsyncMock PnlRepository."""
    repo = AsyncMock()
    repo.write_snapshot = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Messaging mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_publisher():
    """AsyncMock StreamPublisher."""
    pub = AsyncMock()
    pub.publish = AsyncMock(return_value="1234567890-0")
    return pub


@pytest.fixture
def mock_consumer():
    """AsyncMock StreamConsumer."""
    con = AsyncMock()
    con.consume = AsyncMock(return_value=[])
    con.ack = AsyncMock()
    return con


@pytest.fixture
def mock_pubsub():
    """AsyncMock PubSubBroadcaster."""
    ps = AsyncMock()
    ps.publish = AsyncMock()
    return ps


@pytest.fixture
def mock_telemetry():
    """AsyncMock TelemetryPublisher."""
    tel = AsyncMock()
    tel.emit = AsyncMock()
    tel.start_health_loop = AsyncMock()
    tel.stop = AsyncMock()
    return tel


# ---------------------------------------------------------------------------
# Domain object factories
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_order_approved_event():
    """Factory for valid OrderApprovedEvent instances."""
    def _make(
        profile_id="test-profile-001",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.5"),
        price=Decimal("50000.00"),
    ):
        return OrderApprovedEvent(
            event_type=EventType.ORDER_APPROVED,
            timestamp_us=1000000000,
            source_service="test",
            profile_id=profile_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
        )
    return _make


@pytest.fixture
def sample_order():
    """Factory for valid Order instances."""
    def _make(
        order_id=None,
        profile_id="test-profile-001",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.5"),
        price=Decimal("50000.00"),
        status=OrderStatus.PENDING,
    ):
        return Order(
            order_id=order_id or uuid.uuid4(),
            profile_id=profile_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            status=status,
            exchange="BINANCE",
            created_at=datetime.utcnow(),
        )
    return _make


@pytest.fixture
def sample_position():
    """Factory for valid Position instances."""
    def _make(
        position_id=None,
        profile_id="test-profile-001",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=Decimal("50000.00"),
        quantity=Decimal("0.5"),
        entry_fee=Decimal("25.00"),
    ):
        return Position(
            position_id=position_id or uuid.uuid4(),
            profile_id=profile_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            entry_fee=entry_fee,
            opened_at=datetime.utcnow(),
            status=PositionStatus.OPEN,
        )
    return _make


# ---------------------------------------------------------------------------
# Settings mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings():
    """Patch libs.config.settings with test values."""
    with patch("libs.config.settings") as s:
        s.REDIS_URL = "redis://localhost:6379/15"
        s.DATABASE_URL = "postgresql://test:test@localhost:5432/test"
        s.TRADING_SYMBOLS = ["BTC/USDT", "ETH/USDT"]
        s.TRADING_ENABLED = True
        s.BINANCE_TESTNET = True
        s.COINBASE_SANDBOX = True
        s.GCP_PROJECT_ID = "test-project"
        s.CIRCUIT_BREAKER_DAILY_LOSS_PCT = Decimal("0.02")
        s.HOT_DATA_RETENTION_DAYS = 7
        yield s
