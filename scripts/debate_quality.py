import asyncio
from pathlib import Path
import asyncpg


def url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )
    raise SystemExit("missing")


async def main() -> None:
    c = await asyncpg.connect(url())
    try:
        total = await c.fetchval("SELECT COUNT(*) FROM debate_transcripts")
        failed = await c.fetchval(
            "SELECT COUNT(*) FROM debate_transcripts WHERE bull_argument LIKE 'Failed%' OR bear_argument LIKE 'Failed%'"
        )
        cycles = await c.fetchval("SELECT COUNT(DISTINCT cycle_id) FROM debate_transcripts")
        latest_at = await c.fetchval("SELECT MAX(recorded_at) FROM debate_transcripts")
        oldest_at = await c.fetchval("SELECT MIN(recorded_at) FROM debate_transcripts")

        print(f"transcripts:     {total}")
        print(f"distinct cycles: {cycles}")
        print(f"failed rounds:   {failed}  ({100*failed/total:.1f}%)")
        print(f"date range:      {oldest_at} -> {latest_at}")

        print("\nA real (non-failed) transcript, if any:")
        row = await c.fetchrow(
            """
            SELECT cycle_id::text, symbol, round_num, bull_argument, bear_argument,
                   bull_conviction, bear_conviction, recorded_at
            FROM debate_transcripts
            WHERE bull_argument NOT LIKE 'Failed%' AND bear_argument NOT LIKE 'Failed%'
            ORDER BY recorded_at DESC LIMIT 1
            """
        )
        if not row:
            print("  (none — every round is a 'Failed to generate argument' placeholder)")
        else:
            for k, v in dict(row).items():
                sv = str(v)
                if len(sv) > 240:
                    sv = sv[:240] + "..."
                print(f"  {k}: {sv}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
