"""Pull the latest indicator values from the most recent 1m candle for each symbol.

Computes RSI(14) and MACD-histogram from raw OHLCV — the same inputs the demo
profile rule (rsi<50 AND macd.histogram>0) checks. If RSI is currently >= 50
or histogram <= 0, the rule won't match and no decisions will land.
"""
import asyncio
from pathlib import Path
import asyncpg


def url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )


async def main() -> None:
    c = await asyncpg.connect(url())
    try:
        for symbol in ("BTC/USDT", "ETH/USDT"):
            print(f"\n=== {symbol} ===")
            rows = await c.fetch(
                """
                SELECT bucket, close
                FROM market_data_ohlcv
                WHERE symbol = $1 AND timeframe = '1m'
                ORDER BY bucket DESC LIMIT 30
                """,
                symbol,
            )
            if len(rows) < 27:
                print(f"  insufficient candles: {len(rows)}")
                continue
            closes = [float(r["close"]) for r in reversed(rows)]
            latest_bucket = rows[0]["bucket"]
            print(f"  latest 1m bucket: {latest_bucket}")
            print(f"  latest close:     {closes[-1]}")

            # Simple RSI(14) from the 30 closes we just pulled
            gains, losses = 0.0, 0.0
            for i in range(1, 15):
                ch = closes[-15 + i] - closes[-16 + i]
                if ch > 0:
                    gains += ch
                else:
                    losses -= ch
            avg_gain = gains / 14
            avg_loss = losses / 14
            rs = avg_gain / avg_loss if avg_loss > 0 else 0
            rsi = 100 - (100 / (1 + rs)) if avg_loss > 0 else 100
            print(f"  RSI(14)~          {rsi:.2f}  {'(< 50, rule passes)' if rsi < 50 else '(>= 50, rule MISSES this leg)'}")

            # MACD histogram from EMA(12) - EMA(26) and signal EMA(9)
            def ema(values, period):
                k = 2 / (period + 1)
                e = values[0]
                for v in values[1:]:
                    e = v * k + e * (1 - k)
                return e
            ema12 = ema(closes, 12)
            ema26 = ema(closes, 26)
            macd_line = ema12 - ema26
            signal_line = ema(closes[-9:], 9)
            histogram = macd_line - signal_line
            print(f"  MACD histogram~   {histogram:.2f}  {'(> 0, rule passes)' if histogram > 0 else '(<= 0, rule MISSES this leg)'}")
            print(f"  rule: rsi<50 AND histogram>0  →  {'MATCHES' if rsi < 50 and histogram > 0 else 'NO MATCH'}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
