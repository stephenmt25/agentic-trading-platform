"""How much 1h candle history is in market_data_ohlcv per symbol?"""
import asyncio
from pathlib import Path
import asyncpg


def url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )
    raise SystemExit("missing PRAXIS_DATABASE_URL")


async def main() -> None:
    c = await asyncpg.connect(url())
    try:
        # Schema check first — the timeframe column might be named differently
        cols = await c.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name='market_data_ohlcv' ORDER BY ordinal_position"
        )
        print("columns:", [r["column_name"] for r in cols])

        rows = await c.fetch(
            """
            SELECT symbol, timeframe,
                   MIN(bucket) AS first,
                   MAX(bucket) AS last,
                   COUNT(*)  AS bars,
                   EXTRACT(EPOCH FROM (MAX(bucket) - MIN(bucket))) / 86400 AS span_days
            FROM market_data_ohlcv
            WHERE timeframe = '1h'
            GROUP BY symbol, timeframe
            ORDER BY symbol
            """
        )
        if not rows:
            print("\nno 1h candles in market_data_ohlcv")
        else:
            print(f"\n1h candle coverage:")
            for r in rows:
                d = dict(r)
                print(
                    f"  {d['symbol']:<12} bars={d['bars']:>6}  "
                    f"span={d['span_days']:.1f}d ({d['span_days']/30:.1f} months)  "
                    f"{d['first']}  to  {d['last']}"
                )

        # Also report on whatever timeframes do exist, so we know if we'd
        # need to aggregate up from 1m or down from 1d.
        rows = await c.fetch(
            """
            SELECT timeframe, COUNT(*) AS bars FROM market_data_ohlcv
            GROUP BY timeframe ORDER BY timeframe
            """
        )
        print("\nall timeframes in table:")
        for r in rows:
            print(f"  {r['timeframe']:<6} {r['bars']:>8}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
