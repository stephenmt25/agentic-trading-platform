"""Integration: KillSwitch tiered-level round-trip against REAL Redis.

Covers the safety contract end to end at library level:
  * set/read/clear of HaltLevel via services/hot_path/src/kill_switch.py
  * legacy "1" value back-compat + conservative parse of garbage values
  * reason truncation to 256 chars (CWE-400 guard, registry row 64b)
  * activity-log cap at 100 entries
  * operator allow-list gating (settings-driven, registry row 64a) through
    the real api_gateway route function
"""

import json

import pytest
from fastapi import HTTPException

from libs.core.enums import HaltLevel
from services.hot_path.src.kill_switch import (
    KILL_SWITCH_KEY,
    KILL_SWITCH_LOG_KEY,
    KillSwitch,
)


class TestKillSwitchLevelRoundTrip:
    @pytest.mark.asyncio
    async def test_set_read_clear_levels(self, redis_client):
        # Engage the classic kill switch level.
        await KillSwitch.set_level(
            redis_client, HaltLevel.STOP_OPENING, reason="integration", actor="test"
        )
        assert await KillSwitch.get_level(redis_client) == HaltLevel.STOP_OPENING
        assert await KillSwitch.is_active(redis_client) is True

        # Escalate to FLATTEN (most severe rung).
        await KillSwitch.set_level(
            redis_client, HaltLevel.FLATTEN, reason="integration", actor="test"
        )
        level = await KillSwitch.get_level(redis_client)
        assert level == HaltLevel.FLATTEN
        assert level.at_least(HaltLevel.NEUTRALIZE)

        # NONE clears: the key must be DELETED, not set to "NONE".
        await KillSwitch.set_level(
            redis_client, HaltLevel.NONE, reason="all clear", actor="test"
        )
        assert await redis_client.get(KILL_SWITCH_KEY) is None
        assert await KillSwitch.get_level(redis_client) == HaltLevel.NONE
        assert await KillSwitch.is_active(redis_client) is False

    @pytest.mark.asyncio
    async def test_legacy_and_garbage_values_parse_conservatively(self, redis_client):
        # Legacy binary writes ("1") read as STOP_OPENING.
        await KillSwitch.activate(redis_client, reason="legacy", activated_by="test")
        assert await redis_client.get(KILL_SWITCH_KEY) == b"1"
        assert await KillSwitch.get_level(redis_client) == HaltLevel.STOP_OPENING

        # An unrecognised value must read as a halt, never as NONE.
        await redis_client.set(KILL_SWITCH_KEY, "garbage-value")
        assert await KillSwitch.get_level(redis_client) == HaltLevel.STOP_OPENING

        # Explicit falsy spellings read as NONE.
        await redis_client.set(KILL_SWITCH_KEY, "0")
        assert await KillSwitch.get_level(redis_client) == HaltLevel.NONE

        await KillSwitch.deactivate(redis_client, reason="done", deactivated_by="test")
        assert await KillSwitch.is_active(redis_client) is False

    @pytest.mark.asyncio
    async def test_reason_truncated_to_256_chars(self, redis_client):
        long_reason = "x" * 600
        await KillSwitch.set_level(
            redis_client, HaltLevel.DE_RISK, reason=long_reason, actor="test"
        )
        raw = await redis_client.lrange(KILL_SWITCH_LOG_KEY, 0, 0)
        entry = json.loads(raw[0])
        assert len(entry["reason"]) == 256
        assert entry["action"] == "SET_DE_RISK"
        assert entry["actor"] == "test"

        status = await KillSwitch.status(redis_client)
        assert status["active"] is True
        assert status["level"] == "DE_RISK"
        assert status["recent_log"][0]["reason"] == "x" * 256

    @pytest.mark.asyncio
    async def test_activity_log_capped_at_100_entries(self, redis_client):
        for i in range(105):
            await redis_client.lpush(
                KILL_SWITCH_LOG_KEY, json.dumps({"action": f"SET_{i}"})
            )
        # One real write applies the LTRIM cap on the safety-critical log.
        await KillSwitch.set_level(
            redis_client, HaltLevel.STOP_OPENING, reason="cap check", actor="test"
        )
        assert await redis_client.llen(KILL_SWITCH_LOG_KEY) == 100


class TestOperatorGating:
    """Settings-driven allow-list (PRAXIS_KILL_SWITCH_OPERATORS)."""

    def test_is_operator_unconfigured_means_single_operator_mode(self, monkeypatch):
        from libs.config import settings
        from services.api_gateway.src.routes.commands import is_operator

        monkeypatch.setattr(settings, "KILL_SWITCH_OPERATORS", None)
        assert is_operator("anyone") is True
        monkeypatch.setattr(settings, "KILL_SWITCH_OPERATORS", "   ")
        assert is_operator("anyone") is True

    def test_is_operator_allowlist_filters(self, monkeypatch):
        from libs.config import settings
        from services.api_gateway.src.routes.commands import is_operator

        monkeypatch.setattr(settings, "KILL_SWITCH_OPERATORS", "alice, bob ,")
        assert is_operator("alice") is True
        assert is_operator("bob") is True
        assert is_operator("mallory") is False

    @pytest.mark.asyncio
    async def test_route_gates_destructive_actions_against_real_redis(
        self, redis_client, integration_env, monkeypatch
    ):
        """Drive the real POST /commands/kill-switch handler (function level)
        against the TEST Redis: anyone may pull the brake; only operators may
        NEUTRALIZE/FLATTEN or clear a halt."""
        from libs.config import settings
        from libs.storage import RedisClient
        from services.api_gateway.src.routes.commands import (
            KillSwitchRequest,
            set_kill_switch,
        )

        # Point the route's RedisClient singleton at the TEST substrate and
        # restore the prior singleton afterwards (other tests/processes never
        # see it).
        monkeypatch.setattr(settings, "REDIS_URL", integration_env["redis_url"])
        monkeypatch.setattr(RedisClient, "_instance", None)
        monkeypatch.setattr(settings, "KILL_SWITCH_OPERATORS", "alice")

        # Non-operator MAY pull the brake (non-destructive escalation).
        result = await set_kill_switch(
            KillSwitchRequest(active=True, reason="mallory pulls brake"),
            user_id="mallory",
        )
        assert result["level"] == HaltLevel.STOP_OPENING.value
        assert await KillSwitch.is_active(redis_client) is True

        # Non-operator may NOT clear the halt.
        with pytest.raises(HTTPException) as exc:
            await set_kill_switch(
                KillSwitchRequest(active=False, reason="mallory clears"),
                user_id="mallory",
            )
        assert exc.value.status_code == 403
        assert await KillSwitch.is_active(redis_client) is True

        # Non-operator may NOT request a position-destructive level.
        with pytest.raises(HTTPException) as exc:
            await set_kill_switch(
                KillSwitchRequest(level="FLATTEN", reason="mallory flattens"),
                user_id="mallory",
            )
        assert exc.value.status_code == 403
        assert await KillSwitch.get_level(redis_client) == HaltLevel.STOP_OPENING

        # Operator escalates to FLATTEN, then clears.
        result = await set_kill_switch(
            KillSwitchRequest(level="FLATTEN", reason="operator flatten"),
            user_id="alice",
        )
        assert result["level"] == HaltLevel.FLATTEN.value
        assert await KillSwitch.get_level(redis_client) == HaltLevel.FLATTEN

        result = await set_kill_switch(
            KillSwitchRequest(level="NONE", reason="operator clears"),
            user_id="alice",
        )
        assert result["level"] == HaltLevel.NONE.value
        assert await KillSwitch.is_active(redis_client) is False

        # The actor is attributed in the activity log.
        log_raw = await redis_client.lrange(KILL_SWITCH_LOG_KEY, 0, 0)
        assert json.loads(log_raw[0])["actor"] == "alice"

    def test_api_reason_bound_is_256(self):
        """The route-level Pydantic bound mirrors the class-level truncation."""
        import pydantic

        from services.api_gateway.src.routes.commands import KillSwitchRequest

        with pytest.raises(pydantic.ValidationError):
            KillSwitchRequest(active=True, reason="x" * 257)
