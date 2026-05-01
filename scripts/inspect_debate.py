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
        cols = await c.fetch(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='debate_transcripts' ORDER BY ordinal_position"
        )
        print("debate_transcripts columns:")
        for r in cols:
            print(" ", dict(r))
        n = await c.fetchval("SELECT COUNT(*) FROM debate_transcripts")
        print(f"\ntotal rows: {n}")
        if n:
            sample = await c.fetchrow("SELECT * FROM debate_transcripts LIMIT 1")
            print("\nsample row keys:", list(dict(sample).keys()))
            for k, v in dict(sample).items():
                sv = str(v)
                if len(sv) > 300:
                    sv = sv[:300] + "..."
                print(f"  {k}: {sv}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
