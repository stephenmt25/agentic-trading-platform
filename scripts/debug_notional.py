"""Pinpoint why exposure_at_notional fires with 0 open positions.

Replicates exactly what PnlSync does: read each active profile's
allocation_pct, compute notional via libs.core.notional, and sum cost
basis from positions table.
"""
import asyncio, sys
from decimal import Decimal
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402
from libs.core.notional import profile_notional  # noqa: E402


async def main() -> int:
    db = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    c = await asyncpg.connect(db)
    try:
        profiles = await c.fetch(
            """SELECT profile_id::text AS pid, name, is_active, allocation_pct,
                      pg_typeof(allocation_pct) AS alloc_type
               FROM trading_profiles WHERE deleted_at IS NULL"""
        )
        print(f"=== {len(profiles)} active profiles ===")
        for p in profiles:
            pid = p["pid"]
            alloc_raw = p["allocation_pct"]
            alloc_type = p["alloc_type"]
            # Mimic what hot_path's main loader passes — a dict with 'allocation_pct'
            notional = profile_notional({"allocation_pct": alloc_raw})

            # Now sum open positions for this profile
            open_rows = await c.fetch(
                """SELECT entry_price, quantity FROM positions
                   WHERE profile_id = $1::uuid AND status = 'OPEN'""",
                pid,
            )
            cost_basis = sum(
                Decimal(str(r["entry_price"])) * Decimal(str(r["quantity"]))
                for r in open_rows
            )
            free_capital = max(Decimal("0"), notional - cost_basis)
            mark = "*" if p["is_active"] else " "
            blocked = "BLOCKED" if free_capital <= Decimal("0") else "ok"
            print(
                f"  {mark} {pid[:8]}  alloc_pct={alloc_raw} ({alloc_type})"
                f"  notional=${notional}  open={len(open_rows)}  cost_basis=${cost_basis}"
                f"  free=${free_capital}  -> {blocked}  [{p['name']}]"
            )
    finally:
        await c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
