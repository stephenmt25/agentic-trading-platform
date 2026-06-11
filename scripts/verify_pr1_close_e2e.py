"""End-to-end verification for PR1 (real exchange close) against REAL Redis +
Postgres — the integration the mocked unit tests can't cover: the SQL CAS
status guards, the Redis stream round-trip, consumer-group wiring, and the paper
adapter producing an authoritative fill price.

Flow exercised (paper mode):
  seed user+profile+OPEN position
    -> PositionCloseRequester.request_close   (CAS OPEN->PENDING_CLOSE, publish reduce-only to stream:orders)
    -> OrderExecutor (PAPER)                   (consumes, paper-fills, emits OrderExecutedEvent reduce_only=True)
    -> ExecutedEventConsumer                   (finalize_close: CAS PENDING_CLOSE->CLOSED at the fill price)

PASS criteria:
  * positions.status ends CLOSED, close_order_id populated
  * positions.exit_price == the simulated FILL price (mark - paper slippage),
    NOT the mark we passed in  -> proves the real fill price is authoritative
  * exactly one closed_trades row, with exit_price == fill and the close_reason
  * an orders row exists for the reduce-only close order

Run (needs Redis on :6379 and Postgres on :5432 with migrations applied):
  PRAXIS_PAPER_TRADING_MODE=true PRAXIS_TRADING_ENABLED=true \
  PRAXIS_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/praxis_trading \
  PRAXIS_REDIS_URL=redis://localhost:6379/1 \
  poetry run python scripts/verify_pr1_close_e2e.py
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.config import settings  # noqa: E402
from libs.core.enums import OrderSide, PositionStatus  # noqa: E402
from libs.core.models import Position  # noqa: E402
from libs.messaging import StreamConsumer, StreamPublisher  # noqa: E402
from libs.messaging._pubsub import PubSubBroadcaster  # noqa: E402
from libs.messaging.channels import ORDERS_STREAM  # noqa: E402
from libs.storage import (  # noqa: E402
    AuditRepository,
    OrderRepository,
    PositionRepository,
    RedisClient,
    TimescaleClient,
)
from libs.storage.repositories import (  # noqa: E402
    ClosedTradeRepository,
    ProfileRepository,
)
from services.execution.src.executor import OrderExecutor  # noqa: E402
from services.execution.src.ledger import OptimisticLedger  # noqa: E402
from services.pnl.src.close_requester import PositionCloseRequester  # noqa: E402
from services.pnl.src.closer import PositionCloser  # noqa: E402
from services.pnl.src.executed_consumer import ExecutedEventConsumer  # noqa: E402

MARK = Decimal("50000")
ENTRY = Decimal("50000")
QTY = Decimal("1.0")
# Paper adapter applies 0.05% directional slippage; a SELL (closing a long)
# fills BELOW the mark. This is the value positions.exit_price MUST end up as.
EXPECTED_FILL = (MARK * (Decimal("1") - Decimal("0.0005"))).quantize(
    Decimal("0.00000001")
)


async def main() -> int:
    assert settings.PAPER_TRADING_MODE, "set PRAXIS_PAPER_TRADING_MODE=true"

    redis = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    db = TimescaleClient(settings.DATABASE_URL)
    await db.init_pool()

    position_repo = PositionRepository(db)
    order_repo = OrderRepository(db)
    audit_repo = AuditRepository(db)
    closed_trade_repo = ClosedTradeRepository(db)
    profile_repo = ProfileRepository(db)

    # --- seed user + profile + OPEN position ---
    user_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    position_id = uuid.uuid4()
    await db.execute(
        "INSERT INTO users (user_id, email, display_name) VALUES ($1, $2, $3)",
        user_id,
        f"pr1+{user_id}@test.local",
        "PR1 E2E",
    )
    await db.execute(
        """INSERT INTO trading_profiles
           (profile_id, user_id, name, strategy_rules, risk_limits, allocation_pct,
            is_active, exchange_key_ref)
           VALUES ($1, $2, $3, '{}'::jsonb, $4::jsonb, $5, true, 'paper')""",
        profile_id,
        user_id,
        "PR1 E2E profile",
        '{"stop_loss_pct": 0.05}',
        Decimal("1.0"),
    )
    await position_repo.create_position(
        Position(
            position_id=position_id,
            profile_id=profile_id,
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_price=ENTRY,
            quantity=QTY,
            entry_fee=Decimal("50"),
            opened_at=datetime.now(timezone.utc),
            status=PositionStatus.OPEN,
            order_id=uuid.uuid4(),
        )
    )
    print(
        f"[seed] profile={profile_id} position={position_id} status=OPEN entry={ENTRY}"
    )

    # --- real wiring ---
    publisher = StreamPublisher(redis)
    ledger = OptimisticLedger(order_repo)
    executor = OrderExecutor(
        publisher=publisher,
        consumer=StreamConsumer(redis),
        order_repo=order_repo,
        position_repo=position_repo,
        audit_repo=audit_repo,
        ledger=ledger,
        orders_channel=ORDERS_STREAM,
        profile_repo=profile_repo,
        redis_client=redis,
    )
    closer = PositionCloser(
        position_repo,
        redis,
        closed_trade_repo=closed_trade_repo,
        profile_repo=profile_repo,
    )
    close_consumer = ExecutedEventConsumer(
        StreamConsumer(redis), position_repo, closer, pubsub=PubSubBroadcaster(redis)
    )
    requester = PositionCloseRequester(position_repo, publisher)

    exec_task = asyncio.create_task(executor.run())
    cons_task = asyncio.create_task(close_consumer.run())
    await asyncio.sleep(0.5)  # let both consumer groups register

    # --- drive the close ---
    close_order_id = await requester.request_close(
        _row_to_position(await position_repo.get_by_id(position_id)),
        MARK,
        close_reason="manual",
    )
    print(f"[request_close] returned close_order_id={close_order_id}")
    mid = await position_repo.get_by_id(position_id)
    print(
        f"[after request_close] status={mid['status']} close_order_id={mid['close_order_id']}"
    )

    # --- poll for terminal CLOSED ---
    final = None
    for _ in range(60):  # up to ~15s
        await asyncio.sleep(0.25)
        row = await position_repo.get_by_id(position_id)
        if str(row["status"]) == "CLOSED":
            final = row
            break

    exec_task.cancel()
    cons_task.cancel()
    await asyncio.gather(exec_task, cons_task, return_exceptions=True)

    # --- assertions ---
    ok = True

    def check(label, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label} {detail}")

    print("\n=== RESULTS ===")
    if final is None:
        print("  [FAIL] position never reached CLOSED")
        cur = await position_repo.get_by_id(position_id)
        print(f"        last status={cur['status'] if cur else 'GONE'}")
        return 1

    exit_price = Decimal(str(final["exit_price"]))
    check("position CLOSED", str(final["status"]) == "CLOSED")
    check(
        "close_order_id set",
        final["close_order_id"] is not None,
        f"= {final['close_order_id']}",
    )
    check(
        "close_order_id == requester's",
        str(final["close_order_id"]) == str(close_order_id),
    )
    check(
        "exit_price == simulated FILL (not mark)",
        exit_price == EXPECTED_FILL,
        f"exit={exit_price} expected_fill={EXPECTED_FILL} mark={MARK}",
    )
    check("exit_price != mark (slippage attributed)", exit_price != MARK)

    ct = await db.fetch(
        "SELECT exit_price, close_reason, outcome, realized_pnl FROM closed_trades WHERE position_id=$1",
        position_id,
    )
    check("exactly one closed_trades row", len(ct) == 1, f"(got {len(ct)})")
    if ct:
        r = dict(ct[0])
        check(
            "closed_trades.exit_price == fill",
            Decimal(str(r["exit_price"])) == EXPECTED_FILL,
            f"= {r['exit_price']}",
        )
        check(
            "closed_trades.close_reason == manual",
            r["close_reason"] == "manual",
            f"= {r['close_reason']}",
        )
        print(f"        realized_pnl={r['realized_pnl']} outcome={r['outcome']}")

    orders = await db.fetch(
        "SELECT order_id, side, status FROM orders WHERE order_id=$1", close_order_id
    )
    check(
        "reduce-only close order persisted",
        len(orders) == 1,
        f"(side={dict(orders[0])['side'] if orders else '-'})",
    )

    # Idempotency against real SQL: a second close on the now-CLOSED position
    # must lose the OPEN->PENDING_CLOSE CAS and publish nothing.
    second = await requester.request_close(
        _row_to_position(final), MARK, close_reason="manual"
    )
    check(
        "second close on CLOSED position rejected (CAS guard)",
        second is None,
        f"(returned {second})",
    )

    await db.close()
    print(f"\n=== {'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'} ===")
    return 0 if ok else 1


def _row_to_position(row) -> Position:
    return Position(
        position_id=row["position_id"],
        profile_id=str(row["profile_id"]),
        symbol=row["symbol"],
        side=OrderSide(row["side"]),
        entry_price=Decimal(str(row["entry_price"])),
        quantity=Decimal(str(row["quantity"])),
        entry_fee=Decimal(str(row["entry_fee"])),
        opened_at=row["opened_at"],
        status=PositionStatus(row["status"]),
        order_id=row.get("order_id"),
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
