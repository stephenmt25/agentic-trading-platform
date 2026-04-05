"""Unit tests for the PnL service.

Tests PnL publisher Decimal handling, stop-loss enforcement,
and position closer with agent outcome tagging.
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.core.enums import OrderSide, PositionStatus
from services.pnl.src.stop_loss_monitor import StopLossMonitor, _DEFAULT_STOP_LOSS


# ---------------------------------------------------------------------------
# StopLossMonitor tests
# ---------------------------------------------------------------------------

class TestStopLossMonitor:
    def _make_monitor(self, mock_profile_repo):
        closer = AsyncMock()
        closer.close = AsyncMock()
        return StopLossMonitor(closer=closer, profile_repo=mock_profile_repo), closer

    @pytest.mark.asyncio
    async def test_default_stop_loss_is_decimal(self):
        """Default stop-loss threshold must be Decimal."""
        assert isinstance(_DEFAULT_STOP_LOSS, Decimal)
        assert _DEFAULT_STOP_LOSS == Decimal("0.05")

    @pytest.mark.asyncio
    async def test_no_trigger_on_profit(self, mock_profile_repo, sample_position):
        """Stop-loss should not trigger when position is profitable."""
        monitor, closer = self._make_monitor(mock_profile_repo)
        position = sample_position()

        snapshot = MagicMock()
        snapshot.pct_return = Decimal("0.05")  # 5% profit

        result = await monitor.check(
            position=position,
            snapshot=snapshot,
            current_price=Decimal("52500.00"),
            taker_rate=Decimal("0.001"),
        )
        assert result is False
        closer.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_trigger_on_loss_exceeding_threshold(self, mock_profile_repo, sample_position):
        """Stop-loss should trigger when loss exceeds the profile's threshold."""
        monitor, closer = self._make_monitor(mock_profile_repo)
        position = sample_position()

        snapshot = MagicMock()
        snapshot.pct_return = Decimal("-0.06")  # 6% loss > 5% default

        result = await monitor.check(
            position=position,
            snapshot=snapshot,
            current_price=Decimal("47000.00"),
            taker_rate=Decimal("0.001"),
        )
        assert result is True
        closer.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_trigger_on_small_loss(self, mock_profile_repo, sample_position):
        """Stop-loss should NOT trigger when loss is below threshold."""
        monitor, closer = self._make_monitor(mock_profile_repo)
        position = sample_position()

        snapshot = MagicMock()
        snapshot.pct_return = Decimal("-0.03")  # 3% loss < 5% default

        result = await monitor.check(
            position=position,
            snapshot=snapshot,
            current_price=Decimal("48500.00"),
            taker_rate=Decimal("0.001"),
        )
        assert result is False
        closer.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_avoids_repeated_db_lookups(self, mock_profile_repo, sample_position):
        """Stop-loss threshold should be cached after first lookup."""
        monitor, closer = self._make_monitor(mock_profile_repo)
        pos = sample_position()

        # Use negative pct_return so the check actually looks up the stop-loss threshold
        snap1 = MagicMock()
        snap1.pct_return = Decimal("-0.01")  # small loss, below threshold
        snap2 = MagicMock()
        snap2.pct_return = Decimal("-0.01")

        await monitor.check(pos, snap1, Decimal("49500"), Decimal("0.001"))
        await monitor.check(pos, snap2, Decimal("49500"), Decimal("0.001"))

        # Profile should only be loaded once (cached on first call)
        assert mock_profile_repo.get_profile.await_count == 1

    @pytest.mark.asyncio
    async def test_invalidate_cache_forces_reload(self, mock_profile_repo, sample_position):
        """invalidate_cache() should force a DB reload on next check."""
        monitor, closer = self._make_monitor(mock_profile_repo)
        pos = sample_position()

        snap1 = MagicMock()
        snap1.pct_return = Decimal("-0.01")  # needs threshold lookup
        snap2 = MagicMock()
        snap2.pct_return = Decimal("-0.01")

        await monitor.check(pos, snap1, Decimal("49500"), Decimal("0.001"))
        monitor.invalidate_cache(str(pos.profile_id))
        await monitor.check(pos, snap2, Decimal("49500"), Decimal("0.001"))

        # Profile should be loaded twice (cache was invalidated between calls)
        assert mock_profile_repo.get_profile.await_count == 2

    @pytest.mark.asyncio
    async def test_closer_failure_does_not_crash(self, mock_profile_repo, sample_position):
        """If PositionCloser.close() fails, check() returns False without crashing."""
        monitor, closer = self._make_monitor(mock_profile_repo)
        closer.close = AsyncMock(side_effect=Exception("Exchange unreachable"))
        position = sample_position()

        snapshot = MagicMock()
        snapshot.pct_return = Decimal("-0.10")  # 10% loss

        result = await monitor.check(
            position=position,
            snapshot=snapshot,
            current_price=Decimal("45000.00"),
            taker_rate=Decimal("0.001"),
        )
        assert result is False  # close failed, returns False


# ---------------------------------------------------------------------------
# PnL Publisher Decimal safety tests
# ---------------------------------------------------------------------------

class TestPnLPublisherDecimalSafety:
    """Verify that PnL publisher handles Decimal values correctly.

    The _DecimalEncoder converts Decimal → float for JSON serialization.
    This is a known tech debt item — ideally it should convert to str.
    These tests document the current behavior.
    """

    def test_decimal_encoder_converts_decimal_to_float(self):
        """_DecimalEncoder should handle Decimal values."""
        from services.pnl.src.publisher import _DecimalEncoder
        result = json.dumps({"value": Decimal("1.23456789")}, cls=_DecimalEncoder)
        parsed = json.loads(result)
        assert isinstance(parsed["value"], float)

    def test_decimal_zero_serializes_correctly(self):
        """Decimal("0") should serialize without error."""
        from services.pnl.src.publisher import _DecimalEncoder
        result = json.dumps({"value": Decimal("0")}, cls=_DecimalEncoder)
        parsed = json.loads(result)
        assert parsed["value"] == 0.0
