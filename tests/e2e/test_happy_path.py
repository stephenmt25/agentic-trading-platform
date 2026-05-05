"""Synthetic-trade harness — drive every scenario through the production gate
sequence and assert the decision matches.

Replaces the prior `assert True` placeholder. Catches regressions in the
class of `a08d576` (CRISIS short-circuit silently disabled): the harness
fails the moment any gate's wiring or short-circuit logic stops firing for
a given scenario.

Limitations: gates that require external systems (KillSwitch, AgentModifier,
HITLGate, ValidationClient) are not exercised here. A future live-stack
harness should boot `run_all.sh` and call into the real consumer loop.
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
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
async def test_pipeline_scenario(scenario):
    state = make_state(scenario)
    tick = make_tick(scenario)
    signal = make_signal(scenario)
    indicators = make_indicators(scenario)

    outcome = await run_pipeline(
        profile_state=state,
        signal=signal,
        tick=tick,
        indicators=indicators,
        redis_client=None,
        pubsub=None,
    )

    assert outcome.decision == scenario.expected_decision, (
        f"scenario={scenario.name}: expected {scenario.expected_decision} "
        f"but got {outcome.decision} (reason={outcome.reason!r})"
    )
    if scenario.expected_reason_substring is not None:
        assert outcome.reason is not None, (
            f"scenario={scenario.name}: expected reason containing "
            f"{scenario.expected_reason_substring!r} but got None"
        )
        assert scenario.expected_reason_substring in outcome.reason, (
            f"scenario={scenario.name}: reason {outcome.reason!r} does "
            f"not contain expected substring {scenario.expected_reason_substring!r}"
        )
    if scenario.expected_decision == "APPROVED":
        assert outcome.final_signal is not None
        assert outcome.suggested_quantity is not None
        assert outcome.suggested_quantity > 0
