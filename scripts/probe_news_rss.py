"""Quick probe: fetch one RSS feed and print first few entries.

Used once to validate the new RSS path in news_client.py works in this dev
env. Not part of the test suite.
"""

import asyncio
import sys

from services.sentiment.src.news_client import NewsClient


async def main():
    client = NewsClient()
    for symbol in ("BTC/USDT", "ETH/USDT"):
        headlines = await client.get_headlines(symbol, limit=3)
        sys.stdout.write(f"\n{symbol} — {len(headlines)} matched headlines:\n")
        for h in headlines:
            sys.stdout.write(f"  - {h[:140]}\n")
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
