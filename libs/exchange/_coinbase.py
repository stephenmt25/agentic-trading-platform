import asyncio
from decimal import Decimal
from typing import Callable, Coroutine, Dict, List, Any
import ccxt.pro as ccxt
import time
from ._base import ExchangeAdapter, OrderResult
from ._binance import _to_candle
from ._normaliser import normalise_coinbase_tick
from libs.core.types import ProfileId, SymbolPair, Quantity, Price
from libs.core.enums import OrderSide, OrderStatus
from libs.core.models import NormalisedCandle, NormalisedTick

class CoinbaseAdapter(ExchangeAdapter):
    def __init__(self, api_key: str = "", secret: str = "", testnet: bool = True):
        super().__init__("COINBASE")
        self.exchange = ccxt.coinbase({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)
        self.reconnect_delay = 1.0

    async def connect_websocket(self, symbols: List[SymbolPair], callback: Callable[[NormalisedTick], Coroutine[Any, Any, None]]):
        self.is_connected = True
        while self.is_connected:
            try:
                tickers = await self.exchange.watch_tickers(symbols)
                for symbol, ticker in tickers.items():
                    norm_tick = normalise_coinbase_tick(ticker)
                    await callback(norm_tick)
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
        print(f"Reconnecting {self.name} in {self.reconnect_delay}s...")
        await asyncio.sleep(self.reconnect_delay)
        self.reconnect_delay = min(self.reconnect_delay * 2, 30.0)

    async def stream_candles(
        self,
        symbols: List[SymbolPair],
        callback: Callable[[NormalisedCandle], Coroutine[Any, Any, None]],
        timeframe: str = "1m",
    ):
        """Mirror of BinanceAdapter.stream_candles using Coinbase's watch_ohlcv."""
        self.is_connected = True
        _pending: Dict[str, List] = {s: None for s in symbols}

        async def _watch_one(symbol: str):
            while self.is_connected:
                try:
                    ohlcv = await self.exchange.watch_ohlcv(symbol, timeframe)
                    for bar in ohlcv:
                        ts_ms = int(bar[0])
                        prev = _pending[symbol]
                        if prev is None or ts_ms == prev[0]:
                            _pending[symbol] = bar
                        elif ts_ms > prev[0]:
                            await callback(_to_candle(symbol, self.name, timeframe, prev, closed=True))
                            _pending[symbol] = bar
                    self.reconnect_delay = 1.0
                except ccxt.NetworkError as e:
                    print(f"[{self.name}] candle NetworkError ({symbol}): {e}")
                    await self._handle_reconnect()
                except ccxt.ExchangeClosedByUser:
                    break
                except Exception as e:
                    print(f"[{self.name}] candle unexpected error ({symbol}): {e}")
                    await self._handle_reconnect()

        await asyncio.gather(*(_watch_one(s) for s in symbols))

    async def place_order(self, profile_id: ProfileId, symbol: SymbolPair, side: OrderSide, qty: Quantity, price: Price) -> OrderResult:
        # CCXT requires float — convert at the exchange boundary only
        res = await self.exchange.create_order(
            symbol=symbol,
            type='limit',
            side=side.name.lower(),
            amount=float(qty),  # float-ok: ccxt api requires float
            price=float(price),  # float-ok: ccxt api requires float
        )
        return OrderResult(
            order_id=res['id'],
            status=OrderStatus.SUBMITTED
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
