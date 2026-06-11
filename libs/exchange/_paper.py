import uuid
from decimal import Decimal
from typing import Any, Callable, Coroutine, List, Optional

from libs.core.enums import OrderSide, OrderStatus
from libs.core.models import NormalisedCandle, NormalisedTick
from libs.core.types import Price, ProfileId, Quantity, SymbolPair
from libs.observability import get_logger

from ._base import ExchangeAdapter, OrderResult

logger = get_logger("exchange.paper")

# Simulated slippage for paper fills (0.05% — realistic for BTC/ETH majors)
DEFAULT_SLIPPAGE_PCT = Decimal("0.0005")


class PaperTradingAdapter(ExchangeAdapter):
    """Simulates order fills locally without hitting any exchange API.

    - place_order() fills immediately at submitted price +/- slippage
    - All other methods are no-ops or return sensible defaults
    """

    def __init__(self, slippage_pct: Decimal = DEFAULT_SLIPPAGE_PCT):
        super().__init__("PAPER")
        self._slippage_pct = slippage_pct

    async def connect_websocket(
        self,
        symbols: List[SymbolPair],
        callback: Callable[[NormalisedTick], Coroutine[Any, Any, None]],
    ):
        # No-op: market data comes from the real ingestion service
        pass

    async def stream_candles(
        self,
        symbols: List[SymbolPair],
        callback: Callable[[NormalisedCandle], Coroutine[Any, Any, None]],
        timeframe: str = "1m",
    ):
        # No-op: paper adapter does not produce market data
        pass

    async def place_order(
        self,
        profile_id: ProfileId,
        symbol: SymbolPair,
        side: OrderSide,
        qty: Quantity,
        price: Price,
        reduce_only: bool = False,
    ) -> OrderResult:
        # Apply directional slippage: BUY fills slightly higher, SELL slightly
        # lower. A reduce-only close uses the OPPOSITE side of the open (SELL to
        # close a long, BUY to close a short), so the same directional model
        # gives a realistic simulated exit fill — which is exactly what makes
        # paper fidelity honest (the recorded exit is a fill, not the raw mark).
        if side == OrderSide.BUY:
            fill_price = price * (Decimal("1") + self._slippage_pct)
        else:
            fill_price = price * (Decimal("1") - self._slippage_pct)

        # Round to 8 decimal places (standard crypto precision)
        fill_price = fill_price.quantize(Decimal("0.00000001"))

        order_id = str(uuid.uuid4())

        logger.info(
            "paper_fill",
            order_id=order_id,
            profile_id=profile_id,
            symbol=symbol,
            side=side.value,
            qty=str(qty),
            price=str(price),
            fill_price=str(fill_price),
            slippage_pct=str(self._slippage_pct),
            reduce_only=reduce_only,
        )

        return OrderResult(
            order_id=order_id,
            status=OrderStatus.CONFIRMED,
            fill_price=fill_price,
            filled_quantity=qty,
        )

    async def place_protective_order(
        self,
        profile_id: ProfileId,
        symbol: SymbolPair,
        side: OrderSide,
        qty: Quantity,
        stop_price: Price,
    ) -> Optional[OrderResult]:
        # Paper mode keeps no exchange-resident order — the software stop
        # (ExitMonitor) provides the simulated protection. Record intent so the
        # gated-on path is observable in logs without hitting any API.
        logger.info(
            "paper_protective_stop_noop",
            symbol=symbol,
            side=side.value,
            qty=str(qty),
            stop_price=str(stop_price),
        )
        return None

    async def get_balance(self, profile_id: ProfileId) -> Any:
        # Paper balances are tracked in the positions/PnL tables, not here
        return {"info": "paper_trading", "total": {}}

    async def cancel_order(self, order_id: str):
        # Paper orders fill instantly — nothing to cancel
        pass

    async def get_order_status(self, order_id: str) -> OrderStatus:
        # All paper orders are immediately confirmed
        return OrderStatus.CONFIRMED

    async def close(self):
        # No connections to close
        pass
