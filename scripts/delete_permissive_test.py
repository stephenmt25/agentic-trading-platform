"""Surgically delete the 'Permissive Test' profile and its remnants.

Profile id: 73228e0f-797c-42e6-abb5-596f753d9283
Removes (in dependency order, single transaction):
  - closed_trades, trade_decisions, positions, orders WHERE profile_id = ...
  - pnl_snapshots, validation_events, config_changes, auto_backtest_queue
    are CASCADE-cleaned by the profile delete
  - trading_profiles row
  - paper_trading_reports id=2 (the 2026-04-29 daily aggregate;
    100% of its 777 trades were from Permissive Test)
"""
import asyncio
from pathlib import Path

import asyncpg

PROFILE_ID = "73228e0f-797c-42e6-abb5-596f753d9283"
REPORT_ID = 2  # 2026-04-29


def db_url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            return v.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit("missing PRAXIS_DATABASE_URL")


async def main() -> None:
    c = await asyncpg.connect(db_url())
    try:
        async with c.transaction():
            steps = [
                ("closed_trades",   f"DELETE FROM closed_trades   WHERE profile_id = '{PROFILE_ID}'"),
                ("trade_decisions", f"DELETE FROM trade_decisions WHERE profile_id = '{PROFILE_ID}'"),
                ("positions",       f"DELETE FROM positions       WHERE profile_id = '{PROFILE_ID}'"),
                ("orders",          f"DELETE FROM orders          WHERE profile_id = '{PROFILE_ID}'"),
                ("trading_profiles",f"DELETE FROM trading_profiles WHERE profile_id = '{PROFILE_ID}'"),
                ("paper_trading_reports", f"DELETE FROM paper_trading_reports WHERE id = {REPORT_ID}"),
            ]
            for label, sql in steps:
                result = await c.execute(sql)
                print(f"  {label:<25} {result}")
        print("\nCommitted.")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
