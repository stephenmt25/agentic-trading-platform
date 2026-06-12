"""Integration: learning_loop -> job_runner enqueue contract (registry row 57).

The validation LearningLoop must publish gateway-wire-shaped jobs — a raw
{"data": json.dumps(payload)} stream field on auto_backtest_queue — that the
backtesting JobRunner's REAL parse path (xreadgroup -> b"data" -> json.loads)
accepts. Auto-runs ride with profile_id == "" so they can never become a
profile's decay baseline (the latest-wins landmine); the originating profile
travels as source_profile_id.

Real Redis + real TimescaleDB; the JobRunner's compute step (_process_job) is
stubbed so only the queue contract is under test.
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from libs.core.enums import (
    EventType,
    ValidationCheck,
    ValidationMode,
    ValidationVerdict,
)
from libs.core.schemas import ValidationResponseEvent
from libs.messaging import StreamPublisher
from libs.storage.repositories import ValidationRepository
from services.backtesting.src.job_runner import JobRunner
from services.validation.src.learning_loop import AUTO_BACKTEST_QUEUE, LearningLoop

from .conftest import parse_json, wait_for


async def _reset_validation_events(db) -> None:
    """The hourly scan reads ALL recent validation_events — clear residue from
    earlier tests in this session so enqueue counts are deterministic.
    (praxis_test only; the session gate refuses non-test databases.)"""
    await db.execute("TRUNCATE TABLE validation_events")


async def _seed_drift_red_event(db, profile_id) -> None:
    """A RED Drift verdict in validation_events within the scan window."""
    repo = ValidationRepository(db)
    event = ValidationResponseEvent(
        event_type=EventType.VALIDATION_BLOCK,
        timestamp_us=int(time.time() * 1_000_000),
        source_service="validation",
        verdict=ValidationVerdict.RED,
        check_type=ValidationCheck.CHECK_4_DRIFT,
        mode=ValidationMode.ASYNC_AUDIT,
        reason="Drift RED: live sharpe degraded vs baseline",
        response_time_ms=12.5,
    )
    await repo.write_validation_event(str(profile_id), event, {"signal": "drift"})


class TestLearningLoopEnqueueContract:
    @pytest.mark.asyncio
    async def test_scan_enqueues_gateway_shaped_job(
        self, redis_client, db, seeded_profile, monkeypatch
    ):
        from libs.config import settings

        monkeypatch.setattr(settings, "TRADING_SYMBOLS", ["BTC/USDT"])
        await _reset_validation_events(db)
        await _seed_drift_red_event(db, seeded_profile["profile_id"])

        loop = LearningLoop(ValidationRepository(db), StreamPublisher(redis_client))
        enqueued = await loop.scan_once()
        assert enqueued == 1  # one job per tracked symbol

        entries = await redis_client.xrange(AUTO_BACKTEST_QUEUE)
        assert len(entries) == 1
        _msg_id, fields = entries[0]

        # Gateway wire shape: a raw "data" field, NOT the msgpack "payload"
        # field StreamPublisher writes — the JobRunner reads only "data".
        assert b"data" in fields or "data" in fields
        assert b"payload" not in fields and "payload" not in fields

        payload = parse_json(fields.get(b"data") or fields.get("data"))
        # Decay-baseline guard: auto-runs must NEVER carry the profile id.
        assert payload["profile_id"] == ""
        assert payload["source_profile_id"] == str(seeded_profile["profile_id"])
        assert payload["job_id"].startswith("auto-what_if_halted-")
        assert payload["user_id"] == str(seeded_profile["user_id"])
        assert payload["symbol"] == "BTC/USDT"
        assert payload["timeframe"] == "1m"
        assert payload["slippage_pct"] == "0.001"
        assert isinstance(payload["strategy_rules"], dict)
        assert payload["strategy_rules"]  # carried from the profile row
        assert isinstance(payload["risk_limits"], dict)
        assert payload["walk_forward"] is None
        assert payload["risk_limits_grid"] is None

        # Status key written for FE polling.
        status = parse_json(
            await redis_client.get(f"backtest:status:{payload['job_id']}")
        )
        assert status == {
            "status": "queued",
            "job_id": payload["job_id"],
            "user_id": str(seeded_profile["user_id"]),
        }

    @pytest.mark.asyncio
    async def test_job_runner_parse_path_accepts_learning_loop_message(
        self, redis_client, db, seeded_profile, monkeypatch
    ):
        """End-to-end queue contract: the REAL JobRunner consume/parse loop
        (xreadgroup on auto_backtest_queue) must decode the learning loop's
        message and dispatch _process_job with profile_id == ''."""
        from libs.config import settings

        monkeypatch.setattr(settings, "TRADING_SYMBOLS", ["BTC/USDT"])
        await _reset_validation_events(db)
        await _seed_drift_red_event(db, seeded_profile["profile_id"])

        loop = LearningLoop(ValidationRepository(db), StreamPublisher(redis_client))
        assert await loop.scan_once() == 1

        runner = JobRunner(
            consumer=None,  # unused by the queue path (raw xreadgroup)
            publisher=None,
            data_loader=None,
            backtest_repo=None,
            redis_client=redis_client,
        )
        captured = AsyncMock()
        monkeypatch.setattr(runner, "_process_job", captured)

        task = asyncio.create_task(runner.run())
        try:
            await wait_for(
                lambda: _await_called(captured),
                timeout_s=10,
            )
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        payload, job_id, user_id = captured.await_args.args
        assert payload["profile_id"] == ""  # decay-baseline guard held end-to-end
        assert payload["source_profile_id"] == str(seeded_profile["profile_id"])
        assert job_id == payload["job_id"]
        assert job_id.startswith("auto-what_if_halted-")
        assert user_id == str(seeded_profile["user_id"])

        # The runner acks even processed jobs — nothing left pending.
        pending = await redis_client.xpending(AUTO_BACKTEST_QUEUE, "backtest_engine")
        assert pending["pending"] == 0

    @pytest.mark.asyncio
    async def test_scan_dedupes_red_event_bursts(
        self, redis_client, db, seeded_profile, monkeypatch
    ):
        """A burst of identical RED events must produce ONE job set per
        (profile, diagnosis), not flood the queue."""
        from libs.config import settings

        monkeypatch.setattr(settings, "TRADING_SYMBOLS", ["BTC/USDT"])
        await _reset_validation_events(db)
        for _ in range(5):
            await _seed_drift_red_event(db, seeded_profile["profile_id"])

        loop = LearningLoop(ValidationRepository(db), StreamPublisher(redis_client))
        assert await loop.scan_once() == 1
        assert await redis_client.xlen(AUTO_BACKTEST_QUEUE) == 1


async def _await_called(mock: AsyncMock) -> bool:
    return mock.await_count >= 1
