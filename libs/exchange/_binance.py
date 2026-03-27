import asyncio
from typing import Callable, Coroutine, List, Any
import ccxt.pro as ccxt
import time
from ._base import ExchangeAdapter, OrderResult
from ._normaliser import normalise_binance_tick
from libs.core.types import ProfileId, SymbolPair, Quantity, Price
from libs.core.enums import OrderSide, OrderStatus
from libs.core.models import NormalisedTick

class BinanceAdapter(ExchangeAdapter):
    def __init__(self, api_key: str = "", secret: str = "", testnet: bool = True):
        super().__init__("BINANCE")
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)
        self.reconnect_delay = 1.0 # Base backoff seconds

    async def connect_websocket(self, symbols: List[SymbolPair], callback: Callable[[NormalisedTick], Coroutine[Any, Any, None]]):
        self.is_connected = True
        
        while self.is_connected:
            try:
                # CCXT watch_ticker usually takes one symbol per call, or multiple via watch_tickers
                tickers = await self.exchange.watch_tickers(symbols)
                for symbol, ticker in tickers.items():
                    norm_tick = normalise_binance_tick(ticker)
                    await callback(norm_tick)
                # resets backoff on success
                self.reconnect_delay = 1.0
            except ccxt.NetworkError as e:
                print(f"[{self.name}] NetworkError: {e}")
                await self._handle_reconnect()
            except ccxt.ExchangeClosedByUser as e:
                self.is_connected = False
                break
            except Exception as e:
                print(f"[{self.name}] Unexpected error: {e}")
                await self._handle_reconnect()

    async def _handle_reconnect(self):
        print(f"Reconnecting in {self.reconnect_delay}s...")
        await asyncio.sleep(self.reconnect_delay)
        # exponential backoff, max 30s
        self.reconnect_delay = min(self.reconnect_delay * 2, 30.0)
        
        # In a full design, we'd trigger a SYSTEM_ALERT if retries exceed limit
        # And trigger an order book snapshot recovery immediately after reconnecting

    async def place_order(self, profile_id: ProfileId, symbol: SymbolPair, side: OrderSide, qty: Quantity, price: Price) -> OrderResult:
        # CCXT requires float — convert at the exchange boundary only
        res = await self.exchange.create_order(
            symbol=symbol,
            type='limit',
            side=side.name.lower(),
            amount=float(qty),
            price=float(price),
        )
        return OrderResult(
            order_id=res['id'],
            status=OrderStatus.SUBMITTED # Mapping CCXT 'open' to SUBMITTED
        )

    async def get_balance(self, profile_id: ProfileId) -> Any:
        return await self.exchange.fetch_balance()

    async def cancel_order(self, order_id: str, symbol: str):
        await self.exchange.cancel_order(order_id, symbol)

    async def get_order_status(self, order_id: str, symbol: str) -> OrderStatus:
        order = await self.exchange.fetch_order(order_id, symbol)
        ccxt_stat = order.get('status', 'unknown')
        if ccxt_stat == 'open':
            return OrderStatus.SUBMITTED
        elif ccxt_stat == 'closed':
            return OrderStatus.CONFIRMED
        elif ccxt_stat == 'canceled':
            return OrderStatus.CANCELLED
        elif ccxt_stat == 'rejected':
            return OrderStatus.REJECTED
        return OrderStatus.PENDING

    async def close(self):
        self.is_connected = False
        await self.exchange.close()
