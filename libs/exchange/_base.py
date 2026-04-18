from abc import ABC, abstractmethod
from typing import Callable, Coroutine, List, Any, Optional
from dataclasses import dataclass
from libs.core.types import ExchangeName, ProfileId, SymbolPair, Quantity, Price
from libs.core.enums import OrderSide, OrderStatus
from libs.core.models import NormalisedCandle, NormalisedTick

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
