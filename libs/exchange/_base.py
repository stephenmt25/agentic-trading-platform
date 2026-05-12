from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Callable, Coroutine, List, Any, Literal, Optional, Tuple
from dataclasses import dataclass
from libs.core.types import ExchangeName, ProfileId, SymbolPair, Quantity, Price
from libs.core.enums import OrderSide, OrderStatus
from libs.core.models import NormalisedCandle, NormalisedTick


@dataclass(frozen=True, slots=True)
class NormalisedOrderBook:
    """Top-N depth snapshot. Bids descending price, asks ascending."""
    symbol: SymbolPair
    exchange: ExchangeName
    bids: List[Tuple[Decimal, Decimal]]
    asks: List[Tuple[Decimal, Decimal]]
    timestamp_ms: int


@dataclass(frozen=True, slots=True)
class NormalisedTrade:
    """A single public trade printed on the exchange tape."""
    symbol: SymbolPair
    exchange: ExchangeName
    side: Literal["bid", "ask"]
    price: Price
    size: Quantity
    timestamp_ms: int
    trade_id: Optional[str] = None

@dataclass
class OrderResult:
    order_id: str
    status: OrderStatus
    fill_price: Optional[Price] = None
    filled_quantity: Optional[Quantity] = None

class ExchangeAdapter(ABC):
    def __init__(self, name: ExchangeName):
        self.name = name
        self.is_connected = False

    @abstractmethod
    async def connect_websocket(self, symbols: List[SymbolPair], callback: Callable[[NormalisedTick], Coroutine[Any, Any, None]]):
        """Connects to the websocket and streams ticks to the callback."""
        pass

    @abstractmethod
    async def stream_candles(
        self,
        symbols: List[SymbolPair],
        callback: Callable[[NormalisedCandle], Coroutine[Any, Any, None]],
        timeframe: str = "1m",
    ):
        """Streams authoritative OHLCV candles. Invokes callback once per finalized bar."""
        pass

    async def stream_orderbook(
        self,
        symbols: List[SymbolPair],
        callback: Callable[[NormalisedOrderBook], Coroutine[Any, Any, None]],
        depth: int = 25,
    ):
        """Streams top-N orderbook snapshots. Default raises NotImplementedError so
        adapters that don't expose depth can be skipped silently by the manager."""
        raise NotImplementedError(f"{self.name} does not implement stream_orderbook")

    async def stream_trades(
        self,
        symbols: List[SymbolPair],
        callback: Callable[[NormalisedTrade], Coroutine[Any, Any, None]],
    ):
        """Streams public trade prints. Default raises NotImplementedError so
        adapters that don't expose the trades feed can be skipped."""
        raise NotImplementedError(f"{self.name} does not implement stream_trades")

    @abstractmethod
    async def place_order(self, profile_id: ProfileId, symbol: SymbolPair, side: OrderSide, qty: Quantity, price: Price) -> OrderResult:
        """Places an order on the exchange."""
        pass

    @abstractmethod
    async def get_balance(self, profile_id: ProfileId) -> Any:
        """Retrieves balance."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str):
        """Cancels an order."""
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Gets current status of an order."""
        pass
    
    @abstractmethod
    async def close(self):
        """Closes all connections."""
        pass
