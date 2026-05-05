"""One-off: refetch all market_data_ohlcv from authoritative Binance MAINNET.

Replaces every 1m/5m/15m/1h row that overlaps the contaminated era. Two issues
being corrected:
  1. Pre-2026-04-18 rows: written by the broken candle_aggregator (volume
     inflation + OHL sampling errors).
  2. 2026-04-18 onward: written by the new aggregator, but routed through
     ccxt's testnet sandbox via PRAXIS_BINANCE_TESTNET=true. Testnet mirrors
     mainnet prices but only has ~10% of mainnet volume, so every volume-
     derived feature has been operating on garbage.

Now that services/ingestion/src/main.py forces mainnet for market data, this
script overwrites the stored history so backtests/insights see real data.

Pages through `fetch_ohlcv` 1000 bars at a time. write_candle is ON CONFLICT
DO UPDATE so re-running is safe.

Run with the live stack stopped — services should not be writing to
market_data_ohlcv concurrently.

Usage: poetry run python scripts/refetch_pre_fix_candles.py
"""
import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ccxt
from libs.config import settings
from libs.storage._timescale_client import TimescaleClient
from libs.storage.repositories.market_data_repo import MarketDataRepository

SYMBOLS = ["BTC/USDT", "ETH/USDT"]

# (timeframe, start_date) — earliest contaminated row per timeframe.
JOBS = [
    ("1m",  datetime(2026, 4, 18, tzinfo=timezone.utc)),
    ("5m",  datetime(2026, 4, 13, tzinfo=timezone.utc)),
    ("15m", datetime(2026, 4, 13, tzinfo=timezone.utc)),
    ("1h",  datetime(2026, 4, 1,  tzinfo=timezone.utc)),
]

PAGE_LIMIT = 1000

TIMEFRAME_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}


async def refetch_range(repo, exchange, symbol: str, timeframe: str, since_dt: datetime):
    interval_ms = TIMEFRAME_SECONDS[timeframe] * 1000
    since_ms = int(since_dt.timestamp() * 1000)
    now_ms = int(time.time() * 1000)

    total_written = 0
    fetches = 0

    while since_ms < now_ms:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=PAGE_LIMIT)
        except Exception as e:
            print(f"  ERROR fetch {symbol} {timeframe} since={since_ms}: {e}", flush=True)
            return total_written
        fetches += 1

        if not bars:
            break

        last_ts = since_ms
        for ts_ms, o, h, l, c, v in bars:
            ts_ms = int(ts_ms)
            if ts_ms + interval_ms > now_ms:
                continue  # in-progress bucket
            bucket = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            await repo.write_candle(
                symbol, timeframe,
                {"open":   Decimal(str(o)),
                 "high":   Decimal(str(h)),
                 "low":    Decimal(str(l)),
                 "close":  Decimal(str(c)),
                 "volume": Decimal(str(v))},
                bucket,
            )
            total_written += 1
            last_ts = ts_ms

        # advance past last bar to avoid re-fetching it on the next page
        new_since = last_ts + interval_ms
        if new_since <= since_ms:
            break  # protection against infinite loop on stalled cursor
        since_ms = new_since

    print(f"  {symbol} {timeframe}: wrote {total_written} rows over {fetches} fetches", flush=True)
    return total_written


async def refetch():
    client = TimescaleClient(settings.DATABASE_URL)
    await client.init_pool()
    repo = MarketDataRepository(client)

    # MAINNET — set_sandbox_mode is intentionally NOT called here.
    exchange = ccxt.binance({"enableRateLimit": True})

    grand_total = 0
    for symbol in SYMBOLS:
        for timeframe, since_dt in JOBS:
            print(f"Refetch {symbol} {timeframe} from {since_dt.date()}...", flush=True)
            grand_total += await refetch_range(repo, exchange, symbol, timeframe, since_dt)

    await client.close()
    print(f"Refetch complete. Total rows written: {grand_total}")


if __name__ == "__main__":
    asyncio.run(refetch())
