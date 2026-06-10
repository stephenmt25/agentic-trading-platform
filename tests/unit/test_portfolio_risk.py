"""Unit tests for PR4 — portfolio risk + stress-correlation concentration.

Covers:
  - cluster_for: explicit pair, base-asset, and ALT fallback
  - PortfolioExposure.from_positions: gross/per-cluster/per-symbol + JSON round-trip
  - check_order_against_budget: under budget, gross breach, cluster-cap breach
  - HaltController.neutralize_to_target: trims largest-first to target, no-op under
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from libs.core.correlation import DEFAULT_ALT_CLUSTER, cluster_for
from libs.core.portfolio import PortfolioExposure, check_order_against_budget

CLUSTERS = {"BTC/USDT": "MAJORS", "ETH/USDT": "MAJORS"}


class TestClusterFor:
    def test_explicit_pair(self):
        assert cluster_for("BTC/USDT", CLUSTERS) == "MAJORS"

    def test_base_asset_match(self):
        assert cluster_for("BTC/USD", {"BTC": "MAJORS"}) == "MAJORS"

    def test_unmapped_falls_in_alt(self):
        assert cluster_for("DOGE/USDT", CLUSTERS) == DEFAULT_ALT_CLUSTER

    def test_empty_symbol(self):
        assert cluster_for("", CLUSTERS) == DEFAULT_ALT_CLUSTER


class TestPortfolioExposure:
    def _positions(self):
        return [
            {"symbol": "BTC/USDT", "quantity": "1", "entry_price": "50000"},
            {"symbol": "ETH/USDT", "quantity": "10", "entry_price": "3000"},
            {"symbol": "DOGE/USDT", "quantity": "1000", "entry_price": "0.1"},
        ]

    def test_from_positions_aggregates(self):
        exp = PortfolioExposure.from_positions(self._positions(), CLUSTERS)
        assert exp.gross_usd == Decimal("80100")
        assert exp.per_cluster["MAJORS"] == Decimal("80000")
        assert exp.per_cluster[DEFAULT_ALT_CLUSTER] == Decimal("100")
        assert exp.per_symbol["BTC/USDT"] == Decimal("50000")

    def test_skips_zero_and_bad_notional(self):
        positions = [
            {"symbol": "BTC/USDT", "quantity": "0", "entry_price": "50000"},
            {"symbol": "ETH/USDT", "quantity": "x", "entry_price": "3000"},
            {"symbol": "BTC/USDT", "quantity": "1", "entry_price": "50000"},
        ]
        exp = PortfolioExposure.from_positions(positions, CLUSTERS)
        assert exp.gross_usd == Decimal("50000")

    def test_json_round_trip(self):
        exp = PortfolioExposure.from_positions(self._positions(), CLUSTERS)
        back = PortfolioExposure.from_json(exp.to_json())
        assert back.gross_usd == exp.gross_usd
        assert back.per_cluster["MAJORS"] == Decimal("80000")

    def test_from_json_none_is_empty(self):
        exp = PortfolioExposure.from_json(None)
        assert exp.gross_usd == Decimal("0")
        assert exp.per_cluster == {}


class TestCheckOrderAgainstBudget:
    def _exposure(self):
        return PortfolioExposure(
            gross_usd=Decimal("50000"),
            per_cluster={"MAJORS": Decimal("30000")},
            per_symbol={"BTC/USDT": Decimal("30000")},
        )

    def test_within_budget_allows(self):
        breach = check_order_against_budget(
            self._exposure(),
            "BTC/USDT",
            Decimal("5000"),
            CLUSTERS,
            Decimal("100000"),
            Decimal("0.40"),
        )
        assert breach is None

    def test_gross_budget_breach(self):
        breach = check_order_against_budget(
            self._exposure(),
            "BTC/USDT",
            Decimal("60000"),
            CLUSTERS,
            Decimal("100000"),
            Decimal("0.40"),
        )
        assert breach is not None and "gross exposure" in breach

    def test_cluster_cap_breach(self):
        # gross 50k + 15k = 65k (under 100k budget) but MAJORS 30k + 15k = 45k > 40k cap
        breach = check_order_against_budget(
            self._exposure(),
            "BTC/USDT",
            Decimal("15000"),
            CLUSTERS,
            Decimal("100000"),
            Decimal("0.40"),
        )
        assert breach is not None and "cluster" in breach

    def test_disabled_when_budget_zero(self):
        breach = check_order_against_budget(
            self._exposure(),
            "BTC/USDT",
            Decimal("999999"),
            CLUSTERS,
            Decimal("0"),
            Decimal("0.40"),
        )
        assert breach is None


def _pos_row(symbol, qty, entry):
    return {
        "position_id": uuid.uuid4(),
        "profile_id": str(uuid.uuid4()),
        "symbol": symbol,
        "side": "BUY",
        "entry_price": str(entry),
        "quantity": str(qty),
        "entry_fee": "0",
        "opened_at": datetime.now(timezone.utc),
        "status": "OPEN",
    }


class TestNeutralize:
    @pytest.mark.asyncio
    async def test_trims_largest_first_until_under_target(self):
        from services.pnl.src.halt_controller import HaltController

        # Defaults: budget 100k, target pct 0.5 -> target 50k. Gross 80k.
        position_repo = AsyncMock()
        position_repo.get_open_positions = AsyncMock(
            return_value=[
                _pos_row("BTC/USDT", 1, 50000),  # 50k (largest)
                _pos_row("ETH/USDT", 5, 5000),  # 25k
                _pos_row("SOL/USDT", 50, 100),  # 5k
            ]
        )
        requester = AsyncMock()
        requester.request_close = AsyncMock(return_value=uuid.uuid4())

        hc = HaltController(AsyncMock(), position_repo, requester)
        n = await hc.neutralize_to_target()

        # 80k -> close the 50k position -> 30k <= 50k target. One close.
        assert n == 1
        assert (
            requester.request_close.call_args.kwargs["close_reason"]
            == "halt_neutralize"
        )

    @pytest.mark.asyncio
    async def test_noop_when_under_target(self):
        from services.pnl.src.halt_controller import HaltController

        position_repo = AsyncMock()
        position_repo.get_open_positions = AsyncMock(
            return_value=[_pos_row("BTC/USDT", 1, 10000)]  # 10k < 50k target
        )
        requester = AsyncMock()
        requester.request_close = AsyncMock(return_value=uuid.uuid4())

        hc = HaltController(AsyncMock(), position_repo, requester)
        assert await hc.neutralize_to_target() == 0
        requester.request_close.assert_not_awaited()
