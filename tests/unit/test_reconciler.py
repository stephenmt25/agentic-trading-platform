"""Unit tests for BalanceReconciler (PR2 — wire reconciler + live drift alarms).

Covers:
  - dead-wire safety: no profile_repo -> graceful no-op (the bug PR2 fixes)
  - paper profiles are skipped (nothing to reconcile)
  - drift within tolerance -> no alert
  - drift > 0.1% -> ALERT_RED published to PUBSUB_SYSTEM_ALERTS
  - uses get_unsettled_positions (OPEN + PENDING_CLOSE), so an in-flight close
    doesn't read as drift
  - BUY adds / SELL subtracts in the DB aggregate
"""

from unittest.mock import AsyncMock, patch

import pytest

from libs.core.enums import EventType
from libs.messaging.channels import PUBSUB_SYSTEM_ALERTS
from services.execution.src.reconciler import BalanceReconciler

KEY_REF = "usr-1-binance-keys"  # non-paper; parses to BINANCE


def _reconciler(unsettled, profile_repo=None, pubsub=None):
    position_repo = AsyncMock()
    position_repo.get_unsettled_positions = AsyncMock(return_value=unsettled)
    position_repo.get_open_positions = AsyncMock(return_value=unsettled)
    secret_manager = AsyncMock()
    secret_manager.get_secret = AsyncMock(return_value='{"apiKey": "k", "secret": "s"}')
    rec = BalanceReconciler(
        position_repo,
        profile_repo=profile_repo,
        pubsub=pubsub,
        secret_manager=secret_manager,
    )
    return rec, position_repo


def _adapter(balances):
    a = AsyncMock()
    a.get_balance = AsyncMock(return_value=balances)
    a.close = AsyncMock()
    return a


class TestReconciler:
    @pytest.mark.asyncio
    async def test_no_profile_repo_is_noop(self):
        """The exact bug PR2 fixes: with no profile_repo it must not crash and
        must do nothing (the pre-PR2 dead-wired state)."""
        rec, position_repo = _reconciler([], profile_repo=None, pubsub=AsyncMock())
        await rec._reconcile_all_profiles()  # must not raise
        position_repo.get_unsettled_positions.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_paper_profiles(self):
        profile_repo = AsyncMock()
        profile_repo.get_active_profiles = AsyncMock(
            return_value=[{"profile_id": "p1", "exchange_key_ref": "paper"}]
        )
        rec, position_repo = _reconciler(
            [], profile_repo=profile_repo, pubsub=AsyncMock()
        )
        with patch("services.execution.src.reconciler.get_adapter") as ga:
            await rec._reconcile_all_profiles()
            ga.assert_not_called()  # no exchange touched for paper
        position_repo.get_unsettled_positions.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_drift_within_tolerance_no_alert(self):
        pubsub = AsyncMock()
        # DB 1.0 BTC, exchange 1.0 BTC -> 0% drift
        rec, position_repo = _reconciler(
            [{"symbol": "BTC/USDT", "quantity": "1.0", "side": "BUY"}],
            profile_repo=AsyncMock(),
            pubsub=pubsub,
        )
        with patch(
            "services.execution.src.reconciler.get_adapter",
            return_value=_adapter({"BTC": {"total": "1.0"}, "USDT": {"total": "5000"}}),
        ):
            await rec._reconcile_profile("p1", KEY_REF)
        pubsub.publish.assert_not_awaited()
        position_repo.get_unsettled_positions.assert_awaited_once_with("p1")

    @pytest.mark.asyncio
    async def test_drift_exceeds_threshold_publishes_red_alert(self):
        pubsub = AsyncMock()
        # DB 1.0 BTC, exchange 0.5 BTC -> 50% drift
        rec, _ = _reconciler(
            [{"symbol": "BTC/USDT", "quantity": "1.0", "side": "BUY"}],
            profile_repo=AsyncMock(),
            pubsub=pubsub,
        )
        with patch(
            "services.execution.src.reconciler.get_adapter",
            return_value=_adapter({"BTC": {"total": "0.5"}}),
        ):
            await rec._reconcile_profile("p1", KEY_REF)
        pubsub.publish.assert_awaited_once()
        channel = pubsub.publish.call_args.args[0]
        alert = pubsub.publish.call_args.args[1]
        assert channel == PUBSUB_SYSTEM_ALERTS
        assert alert.event_type == EventType.ALERT_RED
        assert alert.level == "RED"
        assert "p1" in alert.message

    @pytest.mark.asyncio
    async def test_uses_unsettled_not_open(self):
        """Reconciliation must count OPEN + PENDING_CLOSE (via
        get_unsettled_positions), never the OPEN-only query — so an in-flight
        close isn't mistaken for drift."""
        pubsub = AsyncMock()
        rec, position_repo = _reconciler(
            [{"symbol": "BTC/USDT", "quantity": "1.0", "side": "BUY"}],
            profile_repo=AsyncMock(),
            pubsub=pubsub,
        )
        with patch(
            "services.execution.src.reconciler.get_adapter",
            return_value=_adapter({"BTC": {"total": "1.0"}}),
        ):
            await rec._reconcile_profile("p1", KEY_REF)
        position_repo.get_unsettled_positions.assert_awaited_once_with("p1")
        position_repo.get_open_positions.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_short_position_subtracts(self):
        """A SELL leg subtracts from the DB base total; exchange flat vs DB -1.0
        is 100% drift -> alert."""
        pubsub = AsyncMock()
        rec, _ = _reconciler(
            [{"symbol": "BTC/USDT", "quantity": "1.0", "side": "SELL"}],
            profile_repo=AsyncMock(),
            pubsub=pubsub,
        )
        with patch(
            "services.execution.src.reconciler.get_adapter",
            return_value=_adapter({"BTC": {"total": "0"}}),
        ):
            await rec._reconcile_profile("p1", KEY_REF)
        pubsub.publish.assert_awaited_once()
