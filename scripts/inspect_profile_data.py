import asyncio
import asyncpg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def db_url() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            return v.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit("missing PRAXIS_DATABASE_URL")


async def main() -> None:
    c = await asyncpg.connect(db_url())
    try:
        async def show(title, q):
            print(f"\n--- {title} ---")
            for r in await c.fetch(q):
                print(dict(r))

        await show("orders by profile",          "SELECT profile_id::text, COUNT(*) AS n FROM orders GROUP BY profile_id")
        await show("trade_decisions by profile", "SELECT profile_id::text, COUNT(*) AS n FROM trade_decisions GROUP BY profile_id")
        await show("positions by profile",       "SELECT profile_id::text, COUNT(*) AS n FROM positions GROUP BY profile_id")
        await show("closed_trades by profile",   "SELECT profile_id::text, COUNT(*) AS n FROM closed_trades GROUP BY profile_id")
        await show("pnl_snapshots by profile",   "SELECT profile_id::text, COUNT(*) AS n FROM pnl_snapshots GROUP BY profile_id")
        await show("paper_trading_reports",      "SELECT id, report_date, total_trades, net_pnl FROM paper_trading_reports ORDER BY report_date")
        await show("all profiles",               "SELECT profile_id::text, name, is_active, deleted_at FROM trading_profiles ORDER BY created_at")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
