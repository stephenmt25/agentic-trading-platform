"""Generate paper_trading_reports rows.

Modes:
  (default)           Report for today (UTC).
  --date YYYY-MM-DD   Report for a specific date.
  --backfill          Report for every date with pnl_snapshots activity and no
                      existing report row. Useful after downtime.
  --daemon            Long-running loop: on startup, run a backfill; then every
                      UTC midnight (+5 min buffer), regenerate the just-ended
                      day. Designed to be launched by run_all.sh.
"""
import argparse
import asyncio
import logging
from datetime import date, datetime, timedelta, UTC

from libs.config import settings
from libs.storage._timescale_client import TimescaleClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [daily_report] %(levelname)s: %(message)s",
)
logger = logging.getLogger("daily_report")


async def generate_for_date(db: TimescaleClient, day: date) -> bool:
    """Compute and upsert one report row. Returns True if a row was written."""
    trade_row = await db.fetchrow(
        """
        SELECT COUNT(*) AS total_trades
        FROM orders
        WHERE status = 'CONFIRMED' AND created_at::date = $1
        """,
        day,
    )
    total_trades = trade_row["total_trades"] if trade_row else 0

    pnl_row = await db.fetchrow(
        """
        SELECT
            COALESCE(SUM(gross_pnl), 0)        AS gross_pnl,
            COALESCE(SUM(net_pnl_pre_tax), 0)  AS net_pnl,
            COALESCE(MIN(pct_return), 0)       AS max_drawdown
        FROM pnl_snapshots
        WHERE snapshot_at::date = $1
        """,
        day,
    )
    gross_pnl = float(pnl_row["gross_pnl"]) if pnl_row else 0.0
    net_pnl = float(pnl_row["net_pnl"]) if pnl_row else 0.0
    max_drawdown = abs(float(pnl_row["max_drawdown"])) if pnl_row else 0.0

    wr_row = await db.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE net_pnl_pre_tax > 0) AS wins,
            COUNT(*)                                    AS total
        FROM pnl_snapshots
        WHERE snapshot_at::date = $1
        """,
        day,
    )
    wins = wr_row["wins"] if wr_row else 0
    total_snaps = wr_row["total"] if wr_row else 0
    win_rate = wins / total_snaps if total_snaps > 0 else 0.0

    returns_rows = await db.fetch(
        """
        SELECT pct_return FROM pnl_snapshots
        WHERE snapshot_at::date = $1 AND pct_return IS NOT NULL
        """,
        day,
    )
    returns = [float(r["pct_return"]) for r in returns_rows]
    if len(returns) >= 2:
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_ret = variance ** 0.5
        sharpe = (mean_ret / std_ret) if std_ret > 0 else 0.0
    else:
        sharpe = 0.0

    if total_snaps == 0 and total_trades == 0:
        logger.info("No activity on %s; skipping report.", day)
        return False

    await db.execute(
        """
        INSERT INTO paper_trading_reports
        (report_date, total_trades, win_rate, gross_pnl, net_pnl, max_drawdown, sharpe_ratio)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (report_date) DO UPDATE SET
            total_trades = EXCLUDED.total_trades,
            win_rate     = EXCLUDED.win_rate,
            gross_pnl    = EXCLUDED.gross_pnl,
            net_pnl      = EXCLUDED.net_pnl,
            max_drawdown = EXCLUDED.max_drawdown,
            sharpe_ratio = EXCLUDED.sharpe_ratio
        """,
        day, total_trades, win_rate, gross_pnl, net_pnl, max_drawdown, sharpe,
    )
    logger.info(
        "Wrote report %s: trades=%d, net_pnl=$%.2f, win_rate=%.2f, sharpe=%.2f",
        day, total_trades, net_pnl, win_rate, sharpe,
    )
    return True


async def backfill(db: TimescaleClient) -> int:
    """Generate reports for every date with activity that lacks one."""
    rows = await db.fetch(
        """
        SELECT DISTINCT snapshot_at::date AS day
        FROM pnl_snapshots
        WHERE snapshot_at::date NOT IN (SELECT report_date FROM paper_trading_reports)
        ORDER BY day
        """,
    )
    if not rows:
        logger.info("Backfill: no missing report days.")
        return 0
    written = 0
    for r in rows:
        if await generate_for_date(db, r["day"]):
            written += 1
    logger.info("Backfill complete: %d report(s) written.", written)
    return written


def _seconds_until_next_run() -> float:
    """Seconds until 00:05 UTC tomorrow (5-minute buffer after midnight)."""
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).date()
    target = datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC) + timedelta(minutes=5)
    return max(60.0, (target - now).total_seconds())


async def daemon(db: TimescaleClient) -> None:
    """Long-running loop: backfill on startup, then regenerate each completed UTC day."""
    logger.info("Daemon started. Running initial backfill...")
    await backfill(db)

    while True:
        wait_s = _seconds_until_next_run()
        logger.info(
            "Next report run in %.1fs (at %s).",
            wait_s,
            (datetime.now(UTC) + timedelta(seconds=wait_s)).isoformat(timespec="seconds"),
        )
        await asyncio.sleep(wait_s)

        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        try:
            await generate_for_date(db, yesterday)
            # Also opportunistically fill any gaps that appeared (downtime, etc.).
            await backfill(db)
        except Exception as exc:
            logger.exception("Daemon cycle failed for %s: %s", yesterday, exc)
            # Back off briefly so a persistent error doesn't spin.
            await asyncio.sleep(60)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paper trading daily reports.")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--date", help="Generate report for this YYYY-MM-DD date.")
    grp.add_argument("--backfill", action="store_true", help="Generate reports for every day with missing activity.")
    grp.add_argument("--daemon", action="store_true", help="Run as a long-lived daily scheduler.")
    args = parser.parse_args()

    logger.info("Connecting to TimescaleDB...")
    db = TimescaleClient(settings.DATABASE_URL)
    await db.init_pool()
    try:
        if args.daemon:
            await daemon(db)
        elif args.backfill:
            await backfill(db)
        elif args.date:
            day = datetime.strptime(args.date, "%Y-%m-%d").date()
            await generate_for_date(db, day)
        else:
            await generate_for_date(db, datetime.now(UTC).date())
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
