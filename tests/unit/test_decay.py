"""Unit tests for PR7 — live-vs-backtest decay tracking + shadow consumption."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from libs.core.decay import assess_decay
from libs.core.portfolio import DECAY_SNAPSHOT_KEY


class TestAssessDecay:
    def test_no_baseline(self):
        a = assess_decay(
            live_trades=50,
            live_win_rate=0.5,
            live_avg_pct=0.01,
            backtest_win_rate=None,
            backtest_avg_return=None,
        )
        assert a.status == "no_baseline" and not a.decayed

    def test_insufficient_live(self):
        a = assess_decay(
            live_trades=5,
            live_win_rate=0.4,
            live_avg_pct=0.001,
            backtest_win_rate=0.6,
            backtest_avg_return=0.01,
            min_live_trades=20,
        )
        assert a.status == "insufficient_live" and not a.decayed

    def test_ok_when_live_tracks_backtest(self):
        a = assess_decay(
            live_trades=30,
            live_win_rate=0.60,
            live_avg_pct=0.009,
            backtest_win_rate=0.62,
            backtest_avg_return=0.01,
        )
        assert a.status == "ok" and not a.decayed

    def test_decayed_on_win_rate_drop(self):
        a = assess_decay(
            live_trades=30,
            live_win_rate=0.40,
            live_avg_pct=0.009,
            backtest_win_rate=0.62,
            backtest_avg_return=0.01,
            win_rate_drop=0.15,
        )
        assert a.decayed and a.status == "decayed"
        assert any("win rate" in r for r in a.reasons)

    def test_decayed_on_avg_return_collapse(self):
        a = assess_decay(
            live_trades=30,
            live_win_rate=0.61,
            live_avg_pct=0.001,
            backtest_win_rate=0.62,
            backtest_avg_return=0.01,
            avg_factor=0.5,
        )
        assert a.decayed
        assert any("avg return" in r for r in a.reasons)


class TestDecayTracker:
    @pytest.mark.asyncio
    async def test_assess_all_flags_decay_and_alerts(self):
        from services.analyst.src.decay_tracker import DecayTracker

        ctr = AsyncMock()
        # Row 61: the repo now returns exact Decimal for the money fields —
        # the tracker must downcast at its float-typed scoring boundary.
        ctr.net_of_cost_by_profile = AsyncMock(
            return_value=[
                {
                    "profile_id": "p1",
                    "trade_count": 30,
                    "win_rate": 0.40,
                    "avg_pnl_pct": Decimal("0.001"),
                }
            ]
        )
        decision_repo = AsyncMock()
        decision_repo.shadow_summary_by_profile = AsyncMock(
            return_value=[{"profile_id": "p1", "shadow_count": 5, "shadow_share": 0.2}]
        )
        backtest_repo = AsyncMock()
        # asyncpg decodes the NUMERIC baseline columns as Decimal too.
        backtest_repo.latest_for_profile = AsyncMock(
            return_value={"win_rate": Decimal("0.62"), "avg_return": Decimal("0.01")}
        )
        profile_repo = AsyncMock()
        profile_repo.get_active_profiles = AsyncMock(
            return_value=[{"profile_id": "p1"}]
        )
        redis = AsyncMock()
        pubsub = AsyncMock()

        tracker = DecayTracker(
            ctr,
            decision_repo,
            backtest_repo,
            profile_repo,
            redis_client=redis,
            pubsub=pubsub,
        )
        reports = await tracker.assess_all()

        assert len(reports) == 1
        r = reports[0]
        assert r["profile_id"] == "p1"
        assert r["decayed"] is True
        assert r["shadow_count"] == 5
        # Decimal inputs were downcast — the report carries plain floats.
        assert isinstance(r["live_avg_pct"], float)
        assert isinstance(r["backtest_win_rate"], float)
        pubsub.publish.assert_awaited_once()  # decay alert raised
        # Snapshot lands on the SHARED libs constant (row 65) and must be
        # valid JSON — i.e. no Decimal leaked into the report dicts.
        redis.set.assert_awaited_once()
        set_args, set_kwargs = redis.set.call_args
        assert set_args[0] == DECAY_SNAPSHOT_KEY
        decoded = json.loads(set_args[1])
        assert decoded[0]["profile_id"] == "p1"
        assert set_kwargs.get("ex") == 86400

    @pytest.mark.asyncio
    async def test_assess_all_no_baseline_does_not_alert(self):
        from services.analyst.src.decay_tracker import DecayTracker

        ctr = AsyncMock()
        ctr.net_of_cost_by_profile = AsyncMock(return_value=[])
        decision_repo = AsyncMock()
        decision_repo.shadow_summary_by_profile = AsyncMock(return_value=[])
        backtest_repo = AsyncMock()
        backtest_repo.latest_for_profile = AsyncMock(return_value=None)  # no backtest
        profile_repo = AsyncMock()
        profile_repo.get_active_profiles = AsyncMock(
            return_value=[{"profile_id": "p2"}]
        )
        pubsub = AsyncMock()

        tracker = DecayTracker(
            ctr,
            decision_repo,
            backtest_repo,
            profile_repo,
            redis_client=None,
            pubsub=pubsub,
        )
        reports = await tracker.assess_all()

        assert reports[0]["status"] == "no_baseline"
        pubsub.publish.assert_not_awaited()
