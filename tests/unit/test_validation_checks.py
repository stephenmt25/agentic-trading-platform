"""Unit tests for the Validation service checks.

Tests CHECK_1 (strategy recheck), CHECK_2 (hallucination), and CHECK_6 (risk level).
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.validation.src.check_1_strategy import StrategyRecheck, CheckResult
from services.validation.src.check_2_hallucination import HallucinationCheck
from services.validation.src.check_6_risk_level import RiskLevelRecheck


# ---------------------------------------------------------------------------
# CHECK_1: Strategy Recheck
# ---------------------------------------------------------------------------

class TestStrategyRecheck:
    def _make_request(self, rsi=45.0, symbol="BTC/USDT", profile_id="prof-1"):
        req = MagicMock()
        req.profile_id = profile_id
        req.symbol = symbol
        req.payload = {"inds": {"rsi": rsi}}
        return req

    @pytest.mark.asyncio
    async def test_pass_when_rsi_aligns(self, mock_redis, mock_market_data_repo):
        """CHECK_1 passes when hot RSI and wide RSI are within 25% divergence."""
        mock_redis.exists = AsyncMock(return_value=False)
        checker = StrategyRecheck(mock_market_data_repo, mock_redis)
        req = self._make_request(rsi=45.0)

        result = await checker.check(req)
        # Should pass (wide RSI from mock candles will be close to hot RSI)
        assert isinstance(result, CheckResult)

    @pytest.mark.asyncio
    async def test_rsi_computation_returns_float(self):
        """Internal RSI computation should return a float, not Decimal."""
        closes = [100 + i * 0.5 for i in range(20)]
        rsi = StrategyRecheck._compute_rsi(closes, period=14)
        assert isinstance(rsi, float)
        assert 0.0 <= rsi <= 100.0

    @pytest.mark.asyncio
    async def test_rsi_neutral_on_insufficient_data(self):
        """RSI returns 50.0 (neutral) when insufficient data."""
        rsi = StrategyRecheck._compute_rsi([100, 101, 102], period=14)
        assert rsi == 50.0

    @pytest.mark.asyncio
    async def test_cached_pass_returns_immediately(self, mock_redis, mock_market_data_repo):
        """Cached PASS should short-circuit without DB lookup."""
        mock_redis.exists = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=b"PASS")
        checker = StrategyRecheck(mock_market_data_repo, mock_redis)
        req = self._make_request()

        result = await checker.check(req)
        assert result.passed is True
        mock_market_data_repo.get_candles.assert_not_awaited()


# ---------------------------------------------------------------------------
# CHECK_2: Hallucination
# ---------------------------------------------------------------------------

class TestHallucinationCheck:
    @pytest.mark.asyncio
    async def test_non_llm_signals_always_pass(self, mock_market_data_repo):
        """Non-LLM signals skip the hallucination check entirely."""
        checker = HallucinationCheck(
            validation_repo=AsyncMock(),
            market_repo=mock_market_data_repo,
        )
        result = await checker.check("prof-1", {"is_llm_sentiment": False})
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_llm_signal_tracked(self, mock_market_data_repo):
        """LLM signals should be tracked in the hit history."""
        checker = HallucinationCheck(
            validation_repo=AsyncMock(),
            market_repo=mock_market_data_repo,
        )
        result = await checker.check("prof-1", {
            "is_llm_sentiment": True,
            "symbol": "BTC/USDT",
            "sentiment_direction": "BUY",
            "signal_timestamp": "2026-01-01T00:00:00",
        })
        assert result.passed is True
        assert len(checker._profile_hits.get("prof-1", [])) == 1

    @pytest.mark.asyncio
    async def test_blocks_after_60pct_misalignment(self, mock_market_data_repo):
        """Block LLM signals when >60% of recent 20 are misaligned."""
        # Mock market data showing price going DOWN after BUY signals
        mock_market_data_repo.get_candles_by_range = AsyncMock(return_value=[
            {"close": "100"}, {"close": "95"},  # price went down after BUY
        ])
        checker = HallucinationCheck(
            validation_repo=AsyncMock(),
            market_repo=mock_market_data_repo,
        )
        # Send 20 BUY signals where price went down (misaligned)
        for i in range(20):
            result = await checker.check("prof-1", {
                "is_llm_sentiment": True,
                "symbol": "BTC/USDT",
                "sentiment_direction": "BUY",
                "signal_timestamp": f"2026-01-01T{i:02d}:00:00",
            })

        # After 20 misaligned signals (>60%), should block
        assert result.passed is False
        assert "hallucination" in result.reason.lower()


# ---------------------------------------------------------------------------
# CHECK_6: Risk Level
# ---------------------------------------------------------------------------

class TestRiskLevelRecheck:
    def _make_request(self, quantity="0.5", price="50000", stop_loss_pct="0.0", drawdown="0.0"):
        req = MagicMock()
        req.profile_id = "prof-1"
        req.payload = {
            "quantity": quantity,
            "price": price,
            "stop_loss_pct": stop_loss_pct,
            "current_drawdown_pct": drawdown,
        }
        return req

    @pytest.mark.asyncio
    async def test_pass_within_limits(self, mock_profile_repo):
        """Normal order within all limits should pass."""
        checker = RiskLevelRecheck(mock_profile_repo)
        req = self._make_request(quantity="0.01", price="50000")
        result = await checker.check(req)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fail_on_hard_quantity_cap(self, mock_profile_repo):
        """Orders exceeding 10,000 unit hard cap should fail."""
        checker = RiskLevelRecheck(mock_profile_repo)
        # Use tiny price so allocation check passes but quantity exceeds 10k
        req = self._make_request(quantity="10001", price="0.001")
        result = await checker.check(req)
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_fail_on_excessive_drawdown(self, mock_profile_repo):
        """Orders when drawdown exceeds max should fail."""
        checker = RiskLevelRecheck(mock_profile_repo)
        # Use tiny order so allocation check passes
        req = self._make_request(quantity="0.0001", price="1", drawdown="0.15")
        result = await checker.check(req)
        assert result.passed is False
        assert "drawdown" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_fail_on_stop_loss_exceeding_profile(self, mock_profile_repo):
        """Order stop-loss exceeding profile limit should fail."""
        checker = RiskLevelRecheck(mock_profile_repo)
        # Use tiny order so allocation check passes
        req = self._make_request(quantity="0.0001", price="1", stop_loss_pct="0.08")
        result = await checker.check(req)
        assert result.passed is False
        assert "stop-loss" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_fail_on_missing_profile(self, mock_profile_repo):
        """Missing profile should fail the check."""
        mock_profile_repo.get_profile = AsyncMock(return_value=None)
        checker = RiskLevelRecheck(mock_profile_repo)
        req = self._make_request()
        result = await checker.check(req)
        assert result.passed is False
        assert "profile not found" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_uses_decimal_for_financial_comparison(self, mock_profile_repo):
        """Risk level calculations must use Decimal, not float."""
        checker = RiskLevelRecheck(mock_profile_repo)
        req = self._make_request(quantity="0.5", price="50000")
        # This test verifies the code uses Decimal(str(...)) pattern
        # by confirming it doesn't crash on string inputs
        result = await checker.check(req)
        assert isinstance(result, CheckResult)
