import asyncio
import asyncpg
from pathlib import Path


def db_url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            return v.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit("missing PRAXIS_DATABASE_URL")


async def main() -> None:
    c = await asyncpg.connect(db_url())
    try:
        rows = await c.fetch(
            """
            SELECT tc.table_name, kcu.column_name, rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu USING (constraint_schema, constraint_name)
            JOIN information_schema.referential_constraints rc USING (constraint_schema, constraint_name)
            JOIN information_schema.constraint_column_usage ccu USING (constraint_schema, constraint_name)
            WHERE ccu.table_name = 'trading_profiles' AND ccu.column_name = 'profile_id'
            ORDER BY tc.table_name
            """
        )
        for r in rows:
            print(dict(r))
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
