"""Registry row 57: LearningLoop -> JobRunner enqueue contract.

The learning loop used to publish msgpack (StreamPublisher ``payload`` field)
onto ``auto_backtest_queue`` while the backtesting JobRunner parses only the
gateway shape — a raw ``{"data": json.dumps(payload)}`` field — so every
auto-backtest job was silently dropped (and carried no
symbol/strategy_rules/risk_limits anyway).

These tests pin the contract end-to-end: the message the loop enqueues is
parsed by the REAL JobRunner.run() parse path, and the payload carries the
full EN-W1 job shape including the profile's risk_limits with profile_id=""
(the latest-wins decay-baseline guard for auto-runs).
"""

import asyncio
import json
import uuid
from unittest.mock import MagicMock

import pytest

from libs.config import settings
from libs.core.enums import ValidationCheck
from services.backtesting.src.job_runner import JobRunner
from services.validation.src.learning_loop import AUTO_BACKTEST_QUEUE, LearningLoop

OWNER = str(uuid.uuid4())
PROFILE_ID = str(uuid.uuid4())
RULES = {
    "logic": "AND",
    "direction": "BUY",
    "conditions": [{"value": 35.0, "operator": "LT", "indicator": "rsi"}],
    "base_confidence": 0.6,
}
LIMITS = {
    "stop_loss_pct": 0.04,
    "take_profit_pct": 0.03,
    "max_holding_hours": 6.0,
}


class FakeQueueRedis:
    """Captures the learning loop's queue writes."""

    def __init__(self, queue_len: int = 0):
        self.queue_len = queue_len
        self.xadds: list[tuple[str, dict]] = []
        self.sets: list[tuple[str, str]] = []

    async def xlen(self, channel):
        return self.queue_len + len(self.xadds)

    async def xadd(self, channel, fields):
        self.xadds.append((channel, fields))
        return f"{len(self.xadds)}-1"

    async def set(self, key, value, ex=None):
        self.sets.append((key, value))


class FakeValidationRepo:
    """Returns one batch of RED rows on the first check, [] afterwards."""

    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    async def get_recent_events(self, check_type, hours):
        self.calls += 1
        if self.calls == 1:
            return self._rows
        return []


class FakeProfileRepo:
    def __init__(self, profile):
        self._profile = profile

    async def get_profile(self, profile_id):
        if profile_id == str(self._profile.get("profile_id")):
            return self._profile
        return None


def _red_drift_row(profile_id=PROFILE_ID):
    return {
        "event_id": uuid.uuid4(),
        "profile_id": profile_id,
        "verdict": "RED",
        "reason": "Drift RED: live win-rate decayed vs baseline",
    }


def _profile_row():
    # JSONB columns arrive as JSON strings without a codec — exercise coercion.
    return {
        "profile_id": PROFILE_ID,
        "user_id": uuid.UUID(OWNER),
        "name": "Test Profile",
        "strategy_rules": json.dumps(RULES),
        "risk_limits": json.dumps(LIMITS),
    }


def _make_loop(rows=None, queue_len=0, profile=None):
    redis = FakeQueueRedis(queue_len=queue_len)
    loop = LearningLoop(
        validation_repo=FakeValidationRepo(rows or [_red_drift_row()]),
        publisher=MagicMock(),
        profile_repo=FakeProfileRepo(profile or _profile_row()),
        redis_client=redis,
    )
    return loop, redis


class RunnerFakeRedis:
    """Feeds the captured queue message through JobRunner.run() once."""

    def __init__(self, data_field: str):
        self._data = data_field
        self._reads = 0
        self.acked: list = []

    async def xgroup_create(self, *a, **kw):
        return True

    async def xreadgroup(self, *a, **kw):
        self._reads += 1
        if self._reads == 1:
            return [
                (
                    AUTO_BACKTEST_QUEUE.encode(),
                    [(b"1-1", {b"data": self._data.encode()})],
                )
            ]
        raise asyncio.CancelledError

    async def xack(self, channel, group, *ids):
        self.acked.extend(ids)

    async def set(self, *a, **kw):
        return True


class TestLearningLoopEnqueueShape:
    @pytest.mark.asyncio
    async def test_publishes_gateway_data_json_shape(self):
        """Regression: the runner reads ONLY the raw `data` JSON field."""
        loop, redis = _make_loop()
        n = await loop.scan_once()

        assert n == len(settings.TRADING_SYMBOLS)
        assert len(redis.xadds) == len(settings.TRADING_SYMBOLS)
        for channel, fields in redis.xadds:
            assert channel == AUTO_BACKTEST_QUEUE
            assert set(fields.keys()) == {"data"}  # NOT msgpack `payload`
            payload = json.loads(fields["data"])
            assert payload["symbol"] in settings.TRADING_SYMBOLS
            assert payload["strategy_rules"] == RULES
            assert payload["risk_limits"] == LIMITS
            assert payload["user_id"] == OWNER
            assert payload["timeframe"] == "1m"
            assert payload["start_date"] and payload["end_date"]

    @pytest.mark.asyncio
    async def test_profile_id_always_empty_decay_baseline_guard(self):
        """Auto-runs must NEVER become a profile's latest-wins decay
        baseline: profile_id is "" and the origin rides as
        source_profile_id."""
        loop, redis = _make_loop()
        await loop.scan_once()

        for _, fields in redis.xadds:
            payload = json.loads(fields["data"])
            assert payload["profile_id"] == ""
            assert payload["source_profile_id"] == PROFILE_ID
            assert payload["job_type"] == "what_if_halted"

    @pytest.mark.asyncio
    async def test_job_runner_parses_enqueued_message(self, monkeypatch):
        """Contract test: the REAL JobRunner.run() parse path consumes the
        exact message the learning loop produced."""
        loop, redis = _make_loop()
        await loop.scan_once()
        data_field = redis.xadds[0][1]["data"]

        runner_redis = RunnerFakeRedis(data_field)
        runner = JobRunner(
            consumer=None,
            publisher=None,
            data_loader=None,
            backtest_repo=None,
            redis_client=runner_redis,
        )
        captured = []

        async def fake_process(payload, job_id, user_id):
            captured.append((payload, job_id, user_id))

        monkeypatch.setattr(runner, "_process_job", fake_process)
        with pytest.raises(asyncio.CancelledError):
            await runner.run()

        assert len(captured) == 1
        payload, job_id, user_id = captured[0]
        assert payload is not None  # the old msgpack shape parsed to None
        assert payload["symbol"] == json.loads(data_field)["symbol"]
        assert payload["strategy_rules"] == RULES
        assert payload["risk_limits"] == LIMITS
        assert payload["profile_id"] == ""
        assert job_id.startswith("auto-what_if_halted-")
        assert user_id == OWNER
        assert runner_redis.acked == [b"1-1"]

    @pytest.mark.asyncio
    async def test_dedupes_profile_jobtype_per_scan(self):
        rows = [_red_drift_row(), _red_drift_row()]  # identical diagnosis
        loop, redis = _make_loop(rows=rows)
        await loop.scan_once()
        assert len(redis.xadds) == len(settings.TRADING_SYMBOLS)

    @pytest.mark.asyncio
    async def test_backpressure_respects_queue_depth(self):
        loop, redis = _make_loop(queue_len=settings.BACKTEST_MAX_QUEUE_DEPTH)
        await loop.scan_once()
        assert redis.xadds == []

    @pytest.mark.asyncio
    async def test_non_actionable_or_profileless_events_skipped(self):
        rows = [
            {  # actionable reason but no profile
                "event_id": uuid.uuid4(),
                "profile_id": None,
                "verdict": "RED",
                "reason": "Drift RED",
            },
            {  # profile but non-actionable reason
                "event_id": uuid.uuid4(),
                "profile_id": PROFILE_ID,
                "verdict": "AMBER",
                "reason": "Some other warning",
            },
        ]
        loop, redis = _make_loop(rows=rows)
        await loop.scan_once()
        assert redis.xadds == []

    @pytest.mark.asyncio
    async def test_status_key_written_per_job(self):
        loop, redis = _make_loop()
        await loop.scan_once()
        assert len(redis.sets) == len(redis.xadds)
        for key, value in redis.sets:
            assert key.startswith("backtest:status:auto-what_if_halted-")
            assert json.loads(value)["status"] == "queued"

    def test_checks_enum_importable(self):
        # scan_once iterates ValidationCheck — pin that the enum exists in
        # libs.core.enums (conventions: enums live there only).
        assert len(list(ValidationCheck)) >= 1
