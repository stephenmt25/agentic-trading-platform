"""Integration: repository CRUD against a REAL TimescaleDB (praxis_test).

positions / closed_trades / backtest_results, including the tenant-scoped
`latest_for_profile` (registry row 59): a foreign owner's newer row must not
be returned as a profile's decay baseline.

All money assertions check exact Decimal round-trips — the repo layer must
never hand back IEEE floats (registry row 61 / CLAUDE.md 2A).
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from libs.core.enums import OrderSide, PositionStatus
from libs.core.models import Position
from libs.storage.repositories import ClosedTradeRepository, PositionRepository
from libs.storage.repositories.backtest_repo import BacktestRepository


def _position(profile_id, symbol="BTC/USDT", entry_price="50000.12345678"):
    return Position(
        position_id=uuid.uuid4(),
        profile_id=str(profile_id),
        symbol=symbol,
        side=OrderSide.BUY,
        entry_price=Decimal(entry_price),
        quantity=Decimal("0.5"),
        entry_fee=Decimal("25.000061"),
        opened_at=datetime.now(timezone.utc),
        status=PositionStatus.OPEN,
        order_id=uuid.uuid4(),
    )


class TestPositionRepository:
    @pytest.mark.asyncio
    async def test_create_and_query_open_positions(self, db, seeded_profile):
        repo = PositionRepository(db)
        pos = _position(seeded_profile["profile_id"])
        await repo.create_position(pos)

        # NB: positions.status is UPPERCASE — the repo must find the row.
        rows = await repo.get_open_positions(str(seeded_profile["profile_id"]))
        assert [r["position_id"] for r in rows] == [pos.position_id]
        row = dict(rows[0])
        assert row["status"] == "OPEN"
        assert isinstance(row["entry_price"], Decimal)
        assert row["entry_price"] == Decimal("50000.12345678")
        assert row["entry_fee"] == Decimal("25.000061")

    @pytest.mark.asyncio
    async def test_close_lifecycle_cas_is_exactly_once(self, db, seeded_profile):
        """OPEN -> PENDING_CLOSE -> CLOSED with compare-and-set semantics:
        only the first transition wins, duplicates are no-ops."""
        repo = PositionRepository(db)
        pos = _position(seeded_profile["profile_id"], symbol="ETH/USDT")
        await repo.create_position(pos)

        close_order_id = uuid.uuid4()
        assert await repo.begin_close(pos.position_id, close_order_id) is True
        # Second begin_close must lose the CAS (no duplicate close order).
        assert await repo.begin_close(pos.position_id, uuid.uuid4()) is False

        row = await repo.get_by_id(pos.position_id)
        assert row["status"] == "PENDING_CLOSE"
        assert row["close_order_id"] == close_order_id

        # While PENDING_CLOSE: not OPEN, but still unsettled (reconciler view).
        assert await repo.get_open_positions(str(seeded_profile["profile_id"])) == []
        unsettled = await repo.get_unsettled_positions(
            str(seeded_profile["profile_id"])
        )
        assert [r["position_id"] for r in unsettled] == [pos.position_id]

        exit_price = Decimal("51000.87654321")
        assert await repo.finalize_close(pos.position_id, exit_price) is True
        # Duplicate fill event must be a no-op.
        assert await repo.finalize_close(pos.position_id, exit_price) is False
        # And a revert after CLOSED must also lose.
        assert await repo.revert_close(pos.position_id) is False

        row = await repo.get_by_id(pos.position_id)
        assert row["status"] == "CLOSED"
        assert isinstance(row["exit_price"], Decimal)
        assert row["exit_price"] == exit_price
        assert row["closed_at"] is not None

    @pytest.mark.asyncio
    async def test_revert_close_returns_position_to_monitoring(
        self, db, seeded_profile
    ):
        repo = PositionRepository(db)
        pos = _position(seeded_profile["profile_id"], symbol="SOL/USDT")
        await repo.create_position(pos)
        assert await repo.begin_close(pos.position_id, uuid.uuid4()) is True
        assert await repo.revert_close(pos.position_id) is True
        row = await repo.get_by_id(pos.position_id)
        assert row["status"] == "OPEN"
        assert row["close_order_id"] is None


class TestClosedTradeRepository:
    @pytest.mark.asyncio
    async def test_write_round_trip_and_conflict_guard(self, db, seeded_profile):
        positions = PositionRepository(db)
        pos = _position(seeded_profile["profile_id"])
        await positions.create_position(pos)

        repo = ClosedTradeRepository(db)
        opened = datetime.now(timezone.utc) - timedelta(hours=2)
        closed = datetime.now(timezone.utc)
        kwargs = dict(
            position_id=pos.position_id,
            profile_id=uuid.UUID(str(seeded_profile["profile_id"])),
            symbol=pos.symbol,
            side="BUY",
            decision_event_id=uuid.uuid4(),
            order_id=pos.order_id,
            entry_price=Decimal("50000.12345678"),
            entry_quantity=Decimal("0.5"),
            entry_fee=Decimal("25.000061"),
            entry_regime="TRENDING_UP",
            entry_agent_scores={"ta": {"score": 0.7}},
            exit_price=Decimal("51000.87654321"),
            exit_fee=Decimal("25.50"),
            close_reason="take_profit",
            opened_at=opened,
            closed_at=closed,
            holding_duration_s=7200,
            realized_pnl=Decimal("449.86871721"),
            realized_pnl_pct=Decimal("0.017995"),
            outcome="win",
            slippage_cost=Decimal("12.34567890"),
            funding_cost=Decimal("0"),
        )
        await repo.write_closed_trade(**kwargs)

        row = await repo.get_by_position(pos.position_id)
        assert row is not None
        assert isinstance(row["realized_pnl"], Decimal)
        assert row["realized_pnl"] == Decimal("449.86871721")
        assert row["realized_pnl_pct"] == Decimal("0.017995")
        assert row["slippage_cost"] == Decimal("12.34567890")
        assert row["close_reason"] == "take_profit"
        assert row["outcome"] == "win"

        # Append-only conflict guard: a duplicate close event must not
        # overwrite the audited outcome (ON CONFLICT (position_id) DO NOTHING).
        kwargs["realized_pnl"] = Decimal("-1")
        kwargs["outcome"] = "loss"
        await repo.write_closed_trade(**kwargs)
        row = await repo.get_by_position(pos.position_id)
        assert row["realized_pnl"] == Decimal("449.86871721")
        assert row["outcome"] == "win"

    @pytest.mark.asyncio
    async def test_net_of_cost_rollup_returns_exact_decimals(self, db, seeded_profile):
        positions = PositionRepository(db)
        repo = ClosedTradeRepository(db)
        profile_uuid = uuid.UUID(str(seeded_profile["profile_id"]))

        for i, (pnl, outcome) in enumerate(
            [(Decimal("100.5"), "win"), (Decimal("-250.25"), "loss")]
        ):
            pos = _position(seeded_profile["profile_id"], symbol=f"ALT{i}/USDT")
            await positions.create_position(pos)
            now = datetime.now(timezone.utc)
            await repo.write_closed_trade(
                position_id=pos.position_id,
                profile_id=profile_uuid,
                symbol=pos.symbol,
                side="BUY",
                decision_event_id=None,
                order_id=None,
                entry_price=Decimal("100"),
                entry_quantity=Decimal("1"),
                entry_fee=Decimal("0.1"),
                entry_regime=None,
                entry_agent_scores=None,
                exit_price=Decimal("101"),
                exit_fee=Decimal("0.1"),
                close_reason="stop_loss",
                opened_at=now - timedelta(hours=1),
                closed_at=now,
                holding_duration_s=3600,
                realized_pnl=pnl,
                realized_pnl_pct=pnl / Decimal("10000"),
                outcome=outcome,
                slippage_cost=Decimal("0.5"),
                funding_cost=Decimal("0"),
            )

        rollup = await repo.net_of_cost_by_profile(profile_id=profile_uuid)
        assert len(rollup) == 1
        r = rollup[0]
        assert r["trade_count"] == 2
        # Money fields are exact Decimal — never float (registry row 61).
        assert isinstance(r["net_pnl"], Decimal)
        assert r["net_pnl"] == Decimal("-149.75")
        assert r["total_fees"] == Decimal("0.4")
        assert r["total_slippage"] == Decimal("1.0")
        assert r["net_negative"] is True


class TestBacktestRepository:
    @staticmethod
    def _result(job_id, profile_id="", created_by=None, sharpe="1.23456789"):
        return {
            "job_id": job_id,
            "profile_id": profile_id,
            "symbol": "BTC/USDT",
            "strategy_rules": {"conditions": []},
            "total_trades": 42,
            "win_rate": Decimal("0.52380952"),
            "avg_return": Decimal("0.00123456"),
            "max_drawdown": Decimal("0.08765432"),
            "sharpe": Decimal(sharpe),
            "profit_factor": Decimal("1.10000001"),
            "equity_curve": [10000.0, 10100.0],
            "trades": [],
            "created_by": created_by,
            "start_date": "2026-05-01T00:00:00+00:00",
            "end_date": "2026-06-01T00:00:00+00:00",
            "timeframe": "1m",
        }

    @pytest.mark.asyncio
    async def test_save_and_get_result_decimal_round_trip(self, db, seeded_profile):
        repo = BacktestRepository(db)
        job_id = f"itest-{uuid.uuid4().hex[:12]}"
        await repo.save_result(
            self._result(
                job_id,
                profile_id=str(seeded_profile["profile_id"]),
                created_by=str(seeded_profile["user_id"]),
            )
        )

        row = await repo.get_result(job_id)
        assert row is not None
        # DECIMAL(20,8) metric columns come back as exact Decimal (migration
        # 009 — do NOT regress to DOUBLE PRECISION semantics).
        assert isinstance(row["sharpe"], Decimal)
        assert row["sharpe"] == Decimal("1.23456789")
        assert row["win_rate"] == Decimal("0.52380952")
        assert row["max_drawdown"] == Decimal("0.08765432")
        assert row["total_trades"] == 42
        assert row["strategy_rules"] == {"conditions": []}
        assert row["equity_curve"] == [10000.0, 10100.0]
        assert row["timeframe"] == "1m"

        # Idempotent on job_id (ON CONFLICT DO NOTHING).
        await repo.save_result(
            self._result(job_id, profile_id=str(seeded_profile["profile_id"]))
        )
        history = await repo.get_history(user_id=str(seeded_profile["user_id"]))
        assert [h["job_id"] for h in history] == [job_id]

    @pytest.mark.asyncio
    async def test_latest_for_profile_is_tenant_scoped(self, db, seeded_profile):
        """Registry row 59: only rows created_by the profile OWNER qualify as
        the decay baseline — newer foreign-owned or ownerless rows must lose."""
        repo = BacktestRepository(db)
        profile_id = str(seeded_profile["profile_id"])
        owner = str(seeded_profile["user_id"])
        foreigner = str(seeded_profile["foreign_user_id"])

        owner_job = f"itest-owner-{uuid.uuid4().hex[:8]}"
        await repo.save_result(
            self._result(owner_job, profile_id=profile_id, created_by=owner)
        )
        await asyncio.sleep(0.05)  # ensure strictly newer created_at below

        # NEWER row owned by a foreign user — must never become the baseline.
        foreign_job = f"itest-foreign-{uuid.uuid4().hex[:8]}"
        await repo.save_result(
            self._result(
                foreign_job, profile_id=profile_id, created_by=foreigner, sharpe="9.9"
            )
        )
        await asyncio.sleep(0.05)

        # NEWER ownerless row (pre-migration-020 shape) — must also lose.
        orphan_job = f"itest-orphan-{uuid.uuid4().hex[:8]}"
        await repo.save_result(
            self._result(orphan_job, profile_id=profile_id, created_by=None)
        )

        baseline = await repo.latest_for_profile(profile_id)
        assert baseline is not None
        assert baseline["job_id"] == owner_job
        assert baseline["sharpe"] == Decimal("1.23456789")

    @pytest.mark.asyncio
    async def test_latest_for_profile_empty_without_owned_rows(
        self, db, seeded_profile
    ):
        repo = BacktestRepository(db)
        profile_id = str(seeded_profile["profile_id"])
        # Only a foreign-owned row exists for this profile.
        await repo.save_result(
            self._result(
                f"itest-{uuid.uuid4().hex[:8]}",
                profile_id=profile_id,
                created_by=str(seeded_profile["foreign_user_id"]),
            )
        )
        assert await repo.latest_for_profile(profile_id) is None
