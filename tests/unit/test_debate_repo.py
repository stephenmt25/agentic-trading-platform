"""Unit tests for DebateRepository.

Verifies cycle + transcript inserts produce the expected number of writes
in the right order, with correct JSONB serialization for market_context.
"""

import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from libs.storage.repositories.debate_repo import DebateRepository


def _make_repo():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    return DebateRepository(db), db


def _sample_market_ctx():
    return {
        "price": 50000.0,
        "rsi": 55.5,
        "macd_hist": 0.0023,
        "adx": 22.1,
        "bb_pct_b": 0.62,
        "atr": 412.5,
        "regime": "RANGING",
        "ta_score": 0.4,
        "sentiment_score": 0.1,
    }


def _sample_rounds(n=2):
    return [
        {
            "round_num": i + 1,
            "bull_argument": f"bull arg round {i + 1}",
            "bull_conviction": 0.7 - i * 0.1,
            "bear_argument": f"bear arg round {i + 1}",
            "bear_conviction": 0.4 + i * 0.05,
        }
        for i in range(n)
    ]


class TestWriteCycle:
    @pytest.mark.asyncio
    async def test_writes_cycle_then_each_round(self):
        repo, db = _make_repo()
        cycle_id = uuid.uuid4()
        rounds = _sample_rounds(n=3)

        await repo.write_cycle(
            cycle_id=cycle_id,
            symbol="BTC/USDT",
            final_score=Decimal("0.42"),
            final_confidence=Decimal("0.71"),
            judge_reasoning="Bull provided stronger evidence on momentum.",
            num_rounds=3,
            total_latency_ms=1234.5,
            market_context=_sample_market_ctx(),
            rounds=rounds,
        )

        # 1 cycle insert + 3 round inserts = 4 calls
        assert db.execute.await_count == 4

        # First call inserts the cycle
        cycle_call = db.execute.await_args_list[0]
        cycle_sql = cycle_call.args[0]
        assert "INSERT INTO debate_cycles" in cycle_sql
        cycle_args = cycle_call.args[1:]
        assert cycle_args[0] == cycle_id
        assert cycle_args[1] == "BTC/USDT"
        assert cycle_args[2] == Decimal("0.42")
        assert cycle_args[3] == Decimal("0.71")
        assert cycle_args[4] == "Bull provided stronger evidence on momentum."
        assert cycle_args[5] == 3
        assert cycle_args[6] == Decimal("1234.5")
        # market_context serialized to JSON
        decoded = json.loads(cycle_args[7])
        assert decoded["regime"] == "RANGING"
        assert decoded["price"] == 50000.0

        # Subsequent calls insert each round in order
        for i, call in enumerate(db.execute.await_args_list[1:]):
            sql = call.args[0]
            args = call.args[1:]
            assert "INSERT INTO debate_transcripts" in sql
            assert args[0] == cycle_id
            assert args[1] == "BTC/USDT"
            assert args[2] == i + 1
            assert args[3] == f"bull arg round {i + 1}"
            # convictions arrive as Decimal
            assert isinstance(args[4], Decimal)
            assert isinstance(args[6], Decimal)

    @pytest.mark.asyncio
    async def test_writes_only_cycle_when_no_rounds(self):
        repo, db = _make_repo()
        await repo.write_cycle(
            cycle_id=uuid.uuid4(),
            symbol="ETH/USDT",
            final_score=Decimal("0"),
            final_confidence=Decimal("0.3"),
            judge_reasoning="Judge fallback — no rounds available.",
            num_rounds=0,
            total_latency_ms=500.0,
            market_context=_sample_market_ctx(),
            rounds=[],
        )
        assert db.execute.await_count == 1
        assert "debate_cycles" in db.execute.await_args.args[0]

    @pytest.mark.asyncio
    async def test_decimal_market_context_values_serialize(self):
        repo, db = _make_repo()
        ctx = {"price": Decimal("50000.5"), "rsi": Decimal("55.5")}
        await repo.write_cycle(
            cycle_id=uuid.uuid4(),
            symbol="BTC/USDT",
            final_score=Decimal("0"),
            final_confidence=Decimal("0.5"),
            judge_reasoning="",
            num_rounds=1,
            total_latency_ms=100.0,
            market_context=ctx,
            rounds=[],
        )
        cycle_args = db.execute.await_args.args[1:]
        decoded = json.loads(cycle_args[7])
        assert decoded == {"price": 50000.5, "rsi": 55.5}


class TestQueries:
    @pytest.mark.asyncio
    async def test_get_cycle_with_rounds_returns_none_when_missing(self):
        repo, _ = _make_repo()
        result = await repo.get_cycle_with_rounds(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cycle_with_rounds_assembles_payload(self):
        db = AsyncMock()
        cycle_row = {"cycle_id": "abc", "symbol": "BTC/USDT", "final_score": Decimal("0.5")}
        round_rows = [
            {"round_num": 1, "bull_argument": "a"},
            {"round_num": 2, "bull_argument": "b"},
        ]
        db.fetchrow = AsyncMock(return_value=cycle_row)
        db.fetch = AsyncMock(return_value=round_rows)
        repo = DebateRepository(db)

        result = await repo.get_cycle_with_rounds(uuid.uuid4())
        assert result is not None
        assert result["cycle"] == cycle_row
        assert len(result["rounds"]) == 2
        assert result["rounds"][0]["round_num"] == 1

    @pytest.mark.asyncio
    async def test_get_recent_cycles_no_symbol(self):
        repo, db = _make_repo()
        await repo.get_recent_cycles(limit=10)
        sql, *args = db.fetch.call_args.args
        assert "FROM debate_cycles" in sql
        assert "WHERE" not in sql
        assert args == [10]

    @pytest.mark.asyncio
    async def test_get_recent_cycles_with_symbol(self):
        repo, db = _make_repo()
        await repo.get_recent_cycles(symbol="BTC/USDT", limit=5)
        sql, *args = db.fetch.call_args.args
        assert "WHERE symbol = $1" in sql
        assert args[0] == "BTC/USDT"
        assert args[1] == 5
