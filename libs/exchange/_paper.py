import uuid
from decimal import Decimal
from typing import Callable, Coroutine, List, Any

from ._base import ExchangeAdapter, OrderResult
from libs.core.types import ProfileId, SymbolPair, Quantity, Price
from libs.core.enums import OrderSide, OrderStatus
from libs.core.models import NormalisedCandle, NormalisedTick
from libs.observability import get_logger

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
    ) -> OrderResult:
        # Apply directional slippage: BUY fills slightly higher, SELL slightly lower
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
        )

        return OrderResult(
            order_id=order_id,
            status=OrderStatus.CONFIRMED,
            fill_price=fill_price,
            filled_quantity=qty,
        )

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
