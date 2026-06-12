"""Unit tests for the PnL service.

Tests PnL publisher Decimal handling, stop-loss enforcement,
and position closer with agent outcome tagging.
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.pnl.src.stop_loss_monitor import _DEFAULT_STOP_LOSS, StopLossMonitor

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
    async def test_trigger_on_loss_exceeding_threshold(
        self, mock_profile_repo, sample_position
    ):
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
    async def test_cache_avoids_repeated_db_lookups(
        self, mock_profile_repo, sample_position
    ):
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
    async def test_invalidate_cache_forces_reload(
        self, mock_profile_repo, sample_position
    ):
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
    async def test_closer_failure_does_not_crash(
        self, mock_profile_repo, sample_position
    ):
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
    """Verify that PnL publisher str-encodes Decimal values (registry row 54).

    Decimals are strings on the wire — no binary-float precision loss in
    transit. Consumers parse explicitly (frontend Number(x), hot_path
    Decimal(str(x))).
    """

    def test_decimal_encoder_converts_decimal_to_str(self):
        """_DecimalEncoder must emit str for Decimal — exact value preserved."""
        from services.pnl.src.publisher import _DecimalEncoder

        result = json.dumps({"value": Decimal("1.23456789")}, cls=_DecimalEncoder)
        parsed = json.loads(result)
        assert isinstance(parsed["value"], str)
        assert Decimal(parsed["value"]) == Decimal("1.23456789")

    def test_decimal_zero_serializes_correctly(self):
        """Decimal("0") should serialize without error, as a string."""
        from services.pnl.src.publisher import _DecimalEncoder

        result = json.dumps({"value": Decimal("0")}, cls=_DecimalEncoder)
        parsed = json.loads(result)
        assert parsed["value"] == "0"


# ---------------------------------------------------------------------------
# PnL Publisher wire-shape tests (FE-W2)
# ---------------------------------------------------------------------------


class TestPnLPublisherWireShape:
    """publish_update must carry the full per-position breakdown the
    dashboard reads (position_id, fees, net_pre_tax, net_post_tax,
    tax_estimate) and str-encode Decimals in the cached JSON payload."""

    def _make_snapshot(self):
        from services.pnl.src.calculator import PnLSnapshot

        return PnLSnapshot(
            position_id="11111111-2222-4333-8444-555555555555",
            symbol="BTC/USDT",
            gross_pnl=Decimal("125.50"),
            fees=Decimal("3.25"),
            net_pre_tax=Decimal("122.25"),
            net_post_tax=Decimal("103.91"),
            pct_return=Decimal("0.0207"),
            tax_estimate=Decimal("18.34"),
        )

    def _make_publisher(self):
        from services.pnl.src.publisher import PnLPublisher

        redis_client = AsyncMock()
        redis_client.get = AsyncMock(return_value=None)
        pubsub = AsyncMock()
        pnl_repo = AsyncMock()
        return PnLPublisher(redis_client, pubsub, pnl_repo), redis_client, pubsub

    @pytest.mark.asyncio
    async def test_event_published_on_canonical_channel(self):
        """Channel must come from libs/messaging/channels.py — never invented."""
        from libs.messaging.channels import PUBSUB_PNL_UPDATES

        publisher, _, pubsub = self._make_publisher()
        await publisher.publish_update("profile-1", self._make_snapshot())

        pubsub.publish.assert_awaited_once()
        channel = pubsub.publish.await_args.args[0]
        assert channel == PUBSUB_PNL_UPDATES

    @pytest.mark.asyncio
    async def test_event_carries_position_breakdown(self):
        """New FE-W2 fields are populated from the snapshot; net_pnl keeps
        its historical semantics (PRE-tax net)."""
        publisher, _, pubsub = self._make_publisher()
        snapshot = self._make_snapshot()
        await publisher.publish_update("profile-1", snapshot)

        event = pubsub.publish.await_args.args[1]
        assert event.position_id == snapshot.position_id
        assert event.fees == snapshot.fees
        assert event.net_pre_tax == snapshot.net_pre_tax
        assert event.net_post_tax == snapshot.net_post_tax
        assert event.tax_estimate == snapshot.tax_estimate
        assert event.net_pnl == snapshot.net_pre_tax  # pre-tax, unchanged
        # ZERO TOLERANCE: every financial field stays Decimal in-process
        for value in (
            event.gross_pnl,
            event.net_pnl,
            event.fees,
            event.net_pre_tax,
            event.net_post_tax,
            event.tax_estimate,
            event.pct_return,
        ):
            assert isinstance(value, Decimal)

    @pytest.mark.asyncio
    async def test_redis_latest_cache_str_encodes_decimals(self):
        """The pnl:<profile>:<position>:latest JSON payload must carry all
        Decimal fields as strings (registry row 54)."""
        publisher, redis_client, _ = self._make_publisher()
        snapshot = self._make_snapshot()
        await publisher.publish_update("profile-1", snapshot)

        latest_calls = [
            c
            for c in redis_client.set.await_args_list
            if str(c.args[0]).startswith("pnl:")
        ]
        assert len(latest_calls) == 1
        assert latest_calls[0].args[0] == f"pnl:profile-1:{snapshot.position_id}:latest"

        payload = json.loads(latest_calls[0].args[1])
        for field in (
            "gross_pnl",
            "net_pnl",
            "fees",
            "net_pre_tax",
            "net_post_tax",
            "tax_estimate",
            "pct_return",
        ):
            assert isinstance(payload[field], str), field
        assert payload["position_id"] == snapshot.position_id
        assert Decimal(payload["net_post_tax"]) == snapshot.net_post_tax
        assert Decimal(payload["pct_return"]) == snapshot.pct_return
