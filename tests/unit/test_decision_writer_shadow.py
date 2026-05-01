"""Tests for the shadow flag passthrough on decision writes."""

import uuid
from unittest.mock import AsyncMock

import pytest

from services.hot_path.src.decision_writer import DecisionTraceWriter


@pytest.mark.asyncio
async def test_shadow_defaults_to_false_when_absent():
    repo = AsyncMock()
    writer = DecisionTraceWriter(repo)
    await writer.write({
        "profile_id": str(uuid.uuid4()),
        "symbol": "BTC/USDT",
        "outcome": "APPROVED",
        "input_price": 50000,
    })
    repo.write_decision.assert_awaited_once()
    kwargs = repo.write_decision.await_args.kwargs
    assert kwargs["shadow"] is False


@pytest.mark.asyncio
async def test_shadow_true_passes_through():
    repo = AsyncMock()
    writer = DecisionTraceWriter(repo)
    await writer.write({
        "profile_id": str(uuid.uuid4()),
        "symbol": "ETH/USDT",
        "outcome": "BLOCKED_REGIME_MISMATCH",
        "input_price": 3000,
        "shadow": True,
    })
    kwargs = repo.write_decision.await_args.kwargs
    assert kwargs["shadow"] is True


@pytest.mark.asyncio
async def test_shadow_truthy_value_coerced_to_bool():
    repo = AsyncMock()
    writer = DecisionTraceWriter(repo)
    await writer.write({
        "profile_id": str(uuid.uuid4()),
        "symbol": "BTC/USDT",
        "outcome": "APPROVED",
        "input_price": 50000,
        "shadow": 1,
    })
    kwargs = repo.write_decision.await_args.kwargs
    assert kwargs["shadow"] is True
    assert isinstance(kwargs["shadow"], bool)
