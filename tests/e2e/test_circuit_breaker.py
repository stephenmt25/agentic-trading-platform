"""Focused circuit-breaker e2e — drives a profile whose daily realised PnL
already exceeds the configured threshold through the full gate sequence and
asserts the pipeline blocks at the circuit breaker.

The broader scenario matrix lives in `test_happy_path.py`; this file exists
to keep the circuit-breaker case discoverable by name in CI logs and to fail
loudly if the gate is ever moved or removed from the production pipeline.
"""

import pytest

from ._pipeline import run_pipeline
from .scenarios import (
    SCENARIOS,
    make_indicators,
    make_signal,
    make_state,
    make_tick,
)


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_when_daily_loss_exceeds_threshold():
    scenario = next(s for s in SCENARIOS if s.name == "circuit-breaker-trip")
    outcome = await run_pipeline(
        profile_state=make_state(scenario),
        signal=make_signal(scenario),
        tick=make_tick(scenario),
        indicators=make_indicators(scenario),
    )
    assert outcome.decision == "BLOCKED_CIRCUIT_BREAKER", (
        f"expected circuit breaker to block, got {outcome.decision} (reason={outcome.reason!r})"
    )
