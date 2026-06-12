"""ExchangeAdapter base-contract tests (TECH-DEBT row 51, 2026-06-13).

The base `cancel_order` / `get_order_status` signatures now carry `symbol`
because CCXT venues (Binance/Coinbase) cannot cancel/fetch an order by
order_id alone — the override signature mismatch was an LSP violation
(mypy [override] at _binance.py / _coinbase.py). These tests pin:

1. Signature parity: every concrete adapter's cancel_order/get_order_status
   accepts exactly the base contract's parameters (order_id, symbol).
2. Paper adapter behavior: cancel is a no-op, status is CONFIRMED — both
   callable through the BASE type with the symbol argument.
"""

import inspect

import pytest

from libs.core.enums import OrderStatus
from libs.exchange._base import ExchangeAdapter
from libs.exchange._binance import BinanceAdapter
from libs.exchange._coinbase import CoinbaseAdapter
from libs.exchange._paper import PaperTradingAdapter

ADAPTERS = [PaperTradingAdapter, BinanceAdapter, CoinbaseAdapter]


def _param_names(func) -> list:
    return list(inspect.signature(func).parameters)


class TestCancelGetStatusContract:
    """Every adapter must match the base signature exactly (LSP)."""

    def test_base_contract_carries_symbol(self):
        assert _param_names(ExchangeAdapter.cancel_order) == [
            "self",
            "order_id",
            "symbol",
        ]
        assert _param_names(ExchangeAdapter.get_order_status) == [
            "self",
            "order_id",
            "symbol",
        ]

    @pytest.mark.parametrize("adapter_cls", ADAPTERS)
    def test_cancel_order_signature_parity(self, adapter_cls):
        assert _param_names(adapter_cls.cancel_order) == _param_names(
            ExchangeAdapter.cancel_order
        ), f"{adapter_cls.__name__}.cancel_order breaks the base contract"

    @pytest.mark.parametrize("adapter_cls", ADAPTERS)
    def test_get_order_status_signature_parity(self, adapter_cls):
        assert _param_names(adapter_cls.get_order_status) == _param_names(
            ExchangeAdapter.get_order_status
        ), f"{adapter_cls.__name__}.get_order_status breaks the base contract"


class TestPaperAdapterThroughBaseType:
    """Callers holding the BASE type can cancel/fetch with a symbol —
    the exact usage the old base signature made impossible on CCXT venues."""

    @pytest.mark.asyncio
    async def test_cancel_order_is_noop(self):
        adapter: ExchangeAdapter = PaperTradingAdapter()
        # Must not raise; paper fills instantly so there is nothing to cancel
        assert await adapter.cancel_order("order-1", "BTC/USDT") is None

    @pytest.mark.asyncio
    async def test_get_order_status_confirmed(self):
        adapter: ExchangeAdapter = PaperTradingAdapter()
        status = await adapter.get_order_status("order-1", "BTC/USDT")
        assert status == OrderStatus.CONFIRMED
