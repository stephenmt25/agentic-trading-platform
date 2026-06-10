"""Generate paper_trading_reports rows.

Modes:
  (default)           Report for today (UTC).
  --date YYYY-MM-DD   Report for a specific date.
  --backfill          Report for every date with pnl_snapshots activity and no
                      existing report row. Useful after downtime.
  --daemon            Long-running loop: on startup, run a backfill; then every
                      UTC midnight (+5 min buffer), regenerate the just-ended
                      day. Designed to be launched by run_all.sh.

Generation logic lives in libs/reports/daily.py so the API gateway's
on-demand "generate report" endpoint shares the same code path.
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime, timedelta

from libs.config import settings
from libs.reports.daily import backfill, generate_for_date
from libs.storage._timescale_client import TimescaleClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [daily_report] %(levelname)s: %(message)s",
)
logger = logging.getLogger("daily_report")


def _seconds_until_next_run() -> float:
    """Seconds until 00:05 UTC tomorrow (5-minute buffer after midnight)."""
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).date()
    target = datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC) + timedelta(
        minutes=5
    )
    return max(60.0, (target - now).total_seconds())


async def _initial_backfill(db: TimescaleClient, attempts: int = 5) -> None:
    """Run the startup backfill with retry + exponential backoff.

    A cold-start DB timeout — TimescaleDB under contention while run_all.sh
    boots all 19 services and runs migrations concurrently — must not kill the
    daemon. After exhausting retries we log and return: the scheduled loop's
    own opportunistic `backfill()` (and the next midnight cycle) will catch up
    any gap. Survive-and-continue beats a dead daemon and no daily reports.
    """
    delay = 5.0
    for attempt in range(1, attempts + 1):
        try:
            await backfill(db)
            return
        except Exception as exc:
            if attempt == attempts:
                logger.exception(
                    "Initial backfill failed after %d attempts: %s — continuing "
                    "to the scheduled loop without it.",
                    attempts,
                    exc,
                )
                return
            logger.warning(
                "Initial backfill attempt %d/%d failed (%s); retrying in %.0fs.",
                attempt,
                attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


async def daemon(db: TimescaleClient) -> None:
    """Long-running loop: backfill on startup, then regenerate each completed UTC day."""
    logger.info("Daemon started. Running initial backfill...")
    await _initial_backfill(db)

    while True:
        wait_s = _seconds_until_next_run()
        logger.info(
            "Next report run in %.1fs (at %s).",
            wait_s,
            (datetime.now(UTC) + timedelta(seconds=wait_s)).isoformat(
                timespec="seconds"
            ),
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
    parser = argparse.ArgumentParser(
        description="Generate paper trading daily reports."
    )
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--date", help="Generate report for this YYYY-MM-DD date.")
    grp.add_argument(
        "--backfill",
        action="store_true",
        help="Generate reports for every day with missing activity.",
    )
    grp.add_argument(
        "--daemon", action="store_true", help="Run as a long-lived daily scheduler."
    )
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
