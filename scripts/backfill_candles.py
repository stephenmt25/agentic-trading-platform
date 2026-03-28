"""Backfill historical candles from Binance into TimescaleDB.

Usage: poetry run python scripts/backfill_candles.py
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ccxt
from datetime import datetime, timezone
from libs.config import settings
from libs.storage._timescale_client import TimescaleClient
from libs.storage.repositories.market_data_repo import MarketDataRepository

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAMES = ["1m", "5m", "15m", "1h"]
CANDLE_LIMIT = 500  # per timeframe per symbol


async def backfill():
    # Init DB
    client = TimescaleClient(settings.DATABASE_URL)
    await client.init_pool()
    repo = MarketDataRepository(client)

    # Init CCXT (Binance public REST, no auth needed for candles)
    exchange = ccxt.binance({"enableRateLimit": True})
    if settings.BINANCE_TESTNET:
        exchange.set_sandbox_mode(True)

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            print(f"Fetching {CANDLE_LIMIT} {timeframe} candles for {symbol}...")
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=CANDLE_LIMIT)
                count = 0
                for candle in ohlcv:
                    # CCXT format: [timestamp_ms, open, high, low, close, volume]
                    ts_ms, o, h, l, c, v = candle
                    bucket = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                    await repo.write_candle(
                        symbol, timeframe,
                        {"open": o, "high": h, "low": l, "close": c, "volume": v},
                        bucket
                    )
                    count += 1
                print(f"  Wrote {count} candles")
            except Exception as e:
                print(f"  Error: {e}")

    await client.close()
    print("Backfill complete!")


if __name__ == "__main__":
    asyncio.run(backfill())
