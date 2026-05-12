import asyncio
from decimal import Decimal
from typing import Callable, Coroutine, Dict, List, Any
import ccxt.pro as ccxt
import time
from ._base import ExchangeAdapter, NormalisedOrderBook, NormalisedTrade, OrderResult
from ._normaliser import normalise_binance_tick
from libs.core.types import ProfileId, SymbolPair, Quantity, Price
from libs.core.enums import OrderSide, OrderStatus
from libs.core.models import NormalisedCandle, NormalisedTick


def _to_candle(
    symbol: str,
    exchange: str,
    timeframe: str,
    bar: List,
    closed: bool,
) -> NormalisedCandle:
    """Convert a CCXT OHLCV row [ts_ms, o, h, l, c, v] to NormalisedCandle."""
    ts_ms, o, h, l, c, v = bar
    return NormalisedCandle(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        bucket_ms=int(ts_ms),
        open=Decimal(str(o)),
        high=Decimal(str(h)),
        low=Decimal(str(l)),
        close=Decimal(str(c)),
        volume=Decimal(str(v)),
        closed=closed,
    )


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

    async def stream_candles(
        self,
        symbols: List[SymbolPair],
        callback: Callable[[NormalisedCandle], Coroutine[Any, Any, None]],
        timeframe: str = "1m",
    ):
        """Stream authoritative OHLCV bars.

        `watch_ohlcv` is used only as a wake-up signal: when a new bucket_ms
        appears for a symbol, we REST-fetch the just-closed bucket via
        `fetch_ohlcv` to get Binance's final, kline-authoritative values.
        This avoids a race where CCXT's cached bar still carries partial
        pre-close values at the moment we detect rollover.
        """
        self.is_connected = True
        # Most recent bucket_ms observed on the stream per symbol.
        _last_bucket: Dict[str, int] = {s: 0 for s in symbols}

        async def _fetch_final(symbol: str, bucket_ms: int):
            """REST-fetch the closed bar for `bucket_ms` and emit it."""
            for attempt in range(3):
                try:
                    bars = await self.exchange.fetch_ohlcv(
                        symbol, timeframe, since=bucket_ms, limit=1
                    )
                except Exception as e:
                    if attempt == 2:
                        print(f"[{self.name}] fetch_ohlcv failed for {symbol}@{bucket_ms}: {e}")
                        return
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                if bars and int(bars[0][0]) == bucket_ms:
                    await callback(_to_candle(symbol, self.name, timeframe, bars[0], closed=True))
                    return

        async def _watch_one(symbol: str):
            while self.is_connected:
                try:
                    ohlcv = await self.exchange.watch_ohlcv(symbol, timeframe)
                    latest_bucket = _last_bucket[symbol]
                    for bar in ohlcv:
                        ts_ms = int(bar[0])
                        if ts_ms > latest_bucket:
                            if latest_bucket > 0 and latest_bucket < ts_ms:
                                # Bucket closed — fetch the authoritative final values.
                                await _fetch_final(symbol, latest_bucket)
                            latest_bucket = ts_ms
                    _last_bucket[symbol] = latest_bucket
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

    async def stream_orderbook(
        self,
        symbols: List[SymbolPair],
        callback: Callable[[NormalisedOrderBook], Coroutine[Any, Any, None]],
        depth: int = 25,
    ):
        """Top-N orderbook snapshots via CCXT watch_order_book.

        CCXT debounces internally — Binance Spot delivers ~10Hz updates per
        symbol, well within Redis pubsub headroom. Each loop yields a fresh
        dict; we trim to `depth` levels per side and emit one snapshot per
        change.
        """
        self.is_connected = True

        async def _watch_one(symbol: str):
            while self.is_connected:
                try:
                    ob = await self.exchange.watch_order_book(symbol, limit=depth)
                    bids = [(Decimal(str(p)), Decimal(str(s))) for p, s in (ob.get("bids") or [])[:depth]]
                    asks = [(Decimal(str(p)), Decimal(str(s))) for p, s in (ob.get("asks") or [])[:depth]]
                    ts_ms = int(ob.get("timestamp") or 0)
                    if not ts_ms:
                        ts_ms = int(time.time() * 1000)
                    if not bids and not asks:
                        continue
                    await callback(
                        NormalisedOrderBook(
                            symbol=symbol,
                            exchange=self.name,
                            bids=bids,
                            asks=asks,
                            timestamp_ms=ts_ms,
                        )
                    )
                    self.reconnect_delay = 1.0
                except ccxt.NetworkError as e:
                    print(f"[{self.name}] orderbook NetworkError ({symbol}): {e}")
                    await self._handle_reconnect()
                except ccxt.ExchangeClosedByUser:
                    break
                except Exception as e:
                    print(f"[{self.name}] orderbook unexpected error ({symbol}): {e}")
                    await self._handle_reconnect()

        await asyncio.gather(*(_watch_one(s) for s in symbols))

    async def stream_trades(
        self,
        symbols: List[SymbolPair],
        callback: Callable[[NormalisedTrade], Coroutine[Any, Any, None]],
    ):
        """Public trade prints via CCXT watch_trades.

        Each call returns the trades that occurred since the last poll; we
        emit one NormalisedTrade per row. CCXT canonicalises Binance's
        'buy' / 'sell' to lowercase 'buy'/'sell'; we map to bid/ask
        (taker side: a buy lifts the ask, a sell hits the bid).
        """
        self.is_connected = True

        async def _watch_one(symbol: str):
            while self.is_connected:
                try:
                    trades = await self.exchange.watch_trades(symbol)
                    for t in trades:
                        ccxt_side = (t.get("side") or "").lower()
                        side = "ask" if ccxt_side == "buy" else "bid"
                        ts = t.get("timestamp")
                        ts_ms = int(ts) if ts else int(time.time() * 1000)
                        try:
                            price = Decimal(str(t.get("price")))
                            size = Decimal(str(t.get("amount")))
                        except Exception:
                            continue
                        await callback(
                            NormalisedTrade(
                                symbol=symbol,
                                exchange=self.name,
                                side=side,
                                price=price,
                                size=size,
                                timestamp_ms=ts_ms,
                                trade_id=str(t.get("id")) if t.get("id") is not None else None,
                            )
                        )
                    self.reconnect_delay = 1.0
                except ccxt.NetworkError as e:
                    print(f"[{self.name}] trades NetworkError ({symbol}): {e}")
                    await self._handle_reconnect()
                except ccxt.ExchangeClosedByUser:
                    break
                except Exception as e:
                    print(f"[{self.name}] trades unexpected error ({symbol}): {e}")
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
