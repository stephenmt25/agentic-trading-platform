"""Regression tests for the daily_report daemon's startup resilience.

The daemon must survive a transient cold-start DB timeout on its initial
backfill rather than letting the exception kill the whole process — the
fragility found during the Phase 0 boot smoke-test (run_all.sh boots all 19
services + migrations concurrently, and the backfill query timed out against
the cold, contended TimescaleDB).
"""

import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, patch

# scripts/ is not a Python package — load the module by file path.
_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "daily_report.py"
_spec = importlib.util.spec_from_file_location("daily_report", _MODULE_PATH)
daily_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(daily_report)


class TestInitialBackfill:
    def test_retries_then_succeeds(self):
        """A backfill that fails twice then succeeds is retried, not fatal."""
        calls = {"n": 0}

        async def flaky(_db):
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimeoutError("cold DB")

        with (
            patch.object(daily_report, "backfill", flaky),
            patch.object(daily_report.asyncio, "sleep", AsyncMock()),
        ):
            asyncio.run(daily_report._initial_backfill(object(), attempts=5))
        assert calls["n"] == 3

    def test_survives_when_all_attempts_fail(self):
        """After exhausting retries the daemon proceeds — it must NOT raise."""

        async def always_fail(_db):
            raise TimeoutError("cold DB")

        with (
            patch.object(daily_report, "backfill", always_fail),
            patch.object(daily_report.asyncio, "sleep", AsyncMock()),
        ):
            # No exception escapes — the daemon falls through to its loop.
            asyncio.run(daily_report._initial_backfill(object(), attempts=3))

    def test_succeeds_first_try_no_sleep(self):
        """A healthy backfill runs once and never sleeps/retries."""
        sleep_mock = AsyncMock()

        async def ok(_db):
            return None

        with (
            patch.object(daily_report, "backfill", ok),
            patch.object(daily_report.asyncio, "sleep", sleep_mock),
        ):
            asyncio.run(daily_report._initial_backfill(object(), attempts=5))
        sleep_mock.assert_not_awaited()
