"""Wipe all paper-trading history: orders, positions, pnl, decisions, validations, scores.

Preserves: trading_profiles, users, exchange_keys, market_data_ohlcv, backtest_results,
news_headlines, inference_cache, audit_log, config_changes.

Live trading is disabled in this dev environment (TRADING_ENABLED=False), so every
row in these tables is paper data. If live trading is ever enabled, this script needs
a WHERE clause filtering by profile mode.

Usage:
    python scripts/reset_paper_trading.py          # dry run — shows counts, does nothing
    python scripts/reset_paper_trading.py --confirm  # actually wipes the data
"""

import argparse
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.config import settings
from libs.storage._timescale_client import TimescaleClient


# Order matters: child tables before parents to respect FK constraints even without CASCADE.
# Hypertables (orders, pnl_snapshots, trade_decisions, validation_events, agent_score_history,
# agent_weight_history) are truncated via TRUNCATE which Timescale handles natively.
TABLES_TO_WIPE = [
    "validation_events",
    "trade_decisions",
    "pnl_snapshots",
    "positions",
    "orders",
    "paper_trading_reports",
    "agent_score_history",
    "agent_weight_history",
]


async def count_rows(client: TimescaleClient, table: str) -> int:
    rows = await client.fetch(f"SELECT COUNT(*) AS c FROM {table}")
    return rows[0]["c"] if rows else 0


async def main():
    parser = argparse.ArgumentParser(
        description="Wipe paper-trading history.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually perform the wipe. Without this flag, prints counts only (dry run).",
    )
    args = parser.parse_args()

    client = TimescaleClient(settings.DATABASE_URL)
    await client.init_pool()

    try:
        counts_before = {}
        print("Current row counts:")
        for t in TABLES_TO_WIPE:
            cnt = await count_rows(client, t)
            counts_before[t] = cnt
            print(f"  {t:<25} {cnt:>10,}")
        total = sum(counts_before.values())
        print(f"  {'TOTAL':<25} {total:>10,}")

        if not args.confirm:
            print(
                "\nDry run. Re-run with --confirm to wipe these tables.\n"
                "Profiles, users, exchange keys, market data, and backtest results are preserved."
            )
            return

        print("\nTruncating tables...")
        for t in TABLES_TO_WIPE:
            # CASCADE handles any FK dependencies; RESTART IDENTITY resets bigserial PKs.
            await client.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
            print(f"  Cleared {t}")

        print("\nDone. All paper-trading history wiped.")
        print(f"Removed {total:,} rows across {len(TABLES_TO_WIPE)} tables.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
