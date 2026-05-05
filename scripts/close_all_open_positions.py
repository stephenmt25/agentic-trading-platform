"""Manually close every open position via the PositionCloser.

Drives the same close path StopLossMonitor / ExitMonitor use — DB row update,
realised-PnL calc, closed_trades audit row, agent outcome stream, and Redis
snapshot cleanup. close_reason="manual" so the audit log is honest about why
the position closed.

Exit price is the most recent 1m candle close in market_data_ohlcv for the
symbol. taker_rate matches the pnl service default (0.2%).

Usage:
  poetry run python scripts/close_all_open_positions.py            # dry run
  poetry run python scripts/close_all_open_positions.py --apply    # do it
  poetry run python scripts/close_all_open_positions.py --apply --profile-id <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402
from libs.core.enums import OrderSide, PositionStatus  # noqa: E402
from libs.core.models import Position  # noqa: E402
from libs.storage import RedisClient  # noqa: E402
from libs.storage._timescale_client import TimescaleClient  # noqa: E402
from libs.storage.repositories import (  # noqa: E402
    ClosedTradeRepository,
    PositionRepository,
)
from libs.storage.repositories.profile_repo import ProfileRepository  # noqa: E402
from services.pnl.src.closer import PositionCloser  # noqa: E402

TAKER_RATE = Decimal("0.002")  # matches pnl/main.py DEFAULT_TAKER_RATE


def _record_to_position(rec) -> Position:
    """Same shape as services/pnl/src/main.py:_record_to_position."""
    return Position(
        position_id=rec["position_id"],
        profile_id=str(rec["profile_id"]),
        symbol=rec["symbol"],
        side=OrderSide(rec["side"]),
        entry_price=Decimal(str(rec["entry_price"])),
        quantity=Decimal(str(rec["quantity"])),
        entry_fee=Decimal(str(rec["entry_fee"])),
        opened_at=rec["opened_at"],
        status=PositionStatus(rec["status"]) if rec.get("status") else PositionStatus.OPEN,
        closed_at=rec.get("closed_at"),
        exit_price=Decimal(str(rec["exit_price"])) if rec.get("exit_price") else None,
        order_id=rec.get("order_id"),
        decision_event_id=rec.get("decision_event_id"),
    )


async def _latest_close_price(timescale: TimescaleClient, symbol: str) -> Decimal | None:
    """Most recent 1m candle close for a symbol."""
    row = await timescale.fetchrow(
        """
        SELECT close FROM market_data_ohlcv
        WHERE symbol = $1 AND timeframe = '1m'
        ORDER BY bucket DESC LIMIT 1
        """,
        symbol,
    )
    return Decimal(str(row["close"])) if row else None


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually close (default: dry run)")
    parser.add_argument("--profile-id", help="restrict to a single profile UUID (default: all)")
    args = parser.parse_args()

    timescale = TimescaleClient(settings.DATABASE_URL)
    await timescale.init_pool()
    redis = RedisClient.get_instance(settings.REDIS_URL).get_connection()

    position_repo = PositionRepository(timescale)
    closed_trade_repo = ClosedTradeRepository(timescale)
    profile_repo = ProfileRepository(timescale)

    closer = PositionCloser(
        position_repo=position_repo,
        redis_client=redis,
        closed_trade_repo=closed_trade_repo,
        profile_repo=profile_repo,
    )

    # Read open positions
    if args.profile_id:
        rows = await position_repo.get_open_positions(args.profile_id)
        scope = f"profile {args.profile_id[:8]}"
    else:
        rows = await position_repo.get_open_positions()
        scope = "all profiles"

    print(f"=== Open positions ({scope}): {len(rows)} ===")
    if not rows:
        print("  (none — nothing to close)")
        await timescale.close()
        return 0

    # Cache latest prices by symbol so we don't hit the DB once per position
    price_cache: dict[str, Decimal] = {}
    for rec in rows:
        sym = rec["symbol"]
        if sym not in price_cache:
            price = await _latest_close_price(timescale, sym)
            if price is None:
                print(f"  WARNING: no recent 1m candle for {sym} — skipping its positions")
            price_cache[sym] = price

    # Show what we'd do
    for rec in rows:
        pos = _record_to_position(rec)
        price = price_cache.get(pos.symbol)
        if price is None:
            continue
        cost_basis = pos.entry_price * pos.quantity
        gross = (price - pos.entry_price) * pos.quantity
        print(
            f"  {pos.symbol:<10} {pos.side.value:<4}  qty={float(pos.quantity):.6f}  "
            f"entry=${float(pos.entry_price):.2f}  exit=${float(price):.2f}  "
            f"gross=${float(gross):.2f}  cost=${float(cost_basis):.2f}"
        )

    if not args.apply:
        print("\n(dry run — pass --apply to close them)")
        await timescale.close()
        return 0

    # Close them
    print(f"\n=== Closing {len(rows)} positions (close_reason='manual') ===")
    closed = 0
    failed = 0
    for rec in rows:
        pos = _record_to_position(rec)
        price = price_cache.get(pos.symbol)
        if price is None:
            print(f"  SKIP   {pos.position_id} — no price available")
            failed += 1
            continue
        try:
            snap = await closer.close(
                position=pos,
                exit_price=price,
                taker_rate=TAKER_RATE,
                close_reason="manual",
            )
            outcome = "win" if snap.pct_return > 0 else "loss" if snap.pct_return < 0 else "breakeven"
            print(
                f"  CLOSED {pos.position_id}  {pos.symbol}  "
                f"pnl=${float(snap.net_pre_tax):+.2f}  "
                f"({outcome})"
            )
            closed += 1
        except Exception as e:
            print(f"  FAIL   {pos.position_id} — {e}")
            failed += 1

    print(f"\nDone — closed {closed}, failed {failed}.")
    await timescale.close()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
