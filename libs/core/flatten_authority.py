"""Flatten-authority gate (PR3) — the decision recorded in DECISIONS.md 2026-06-10.

The cheap/reversible halt verbs (STOP_OPENING, DE_RISK) are fully automated. The
single IRREVERSIBLE verb — FLATTEN (close everything) — is gated: an *automated*
flatten is permitted only when **>= 2 independent severe triggers** are concurrently
active AND have persisted through a confirmation **dwell** (default 30s). Below
that bar a severe condition automates only DE_RISK and requests a human to
authorize the flatten (HITL).

This module is pure decision logic — it takes the current trigger booleans and a
monotonic timestamp and returns what to do. The HaltController owns reading the
trigger sources (drawdown, reconciliation drift, CRISIS regime) and acting.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from libs.core.enums import HaltLevel

# Initial thresholds live with the caller (HaltController); this gate only counts
# how many severe triggers are active. DECISIONS.md 2026-06-10 set the default
# dwell and the >=2 rule; both are tunable here without a code change downstream.
DEFAULT_DWELL_SECONDS = 30.0
DEFAULT_MIN_TRIGGERS_FOR_FLATTEN = 2


@dataclass(frozen=True)
class FlattenDecision:
    recommended_level: HaltLevel  # the level the controller should ensure
    auto_flatten_authorized: bool  # True only when >=2 triggers persisted >= dwell
    needs_human_flatten: bool  # severe, but a human must authorize the flatten
    active_triggers: List[str]
    reason: str


@dataclass
class FlattenAuthority:
    """Stateful gate — remembers when the '>= min triggers' condition first held
    so it can enforce the confirmation dwell."""

    dwell_seconds: float = DEFAULT_DWELL_SECONDS
    min_triggers: int = DEFAULT_MIN_TRIGGERS_FOR_FLATTEN
    _multi_trigger_since: Optional[float] = field(default=None, init=False)

    def evaluate(self, triggers: Dict[str, bool], now: float) -> FlattenDecision:
        """Decide the recommended halt level given the current severe triggers.

        triggers: {name: is_active}. `now`: a monotonic seconds timestamp.
        """
        active = sorted(name for name, on in triggers.items() if on)
        count = len(active)

        if count >= self.min_triggers:
            if self._multi_trigger_since is None:
                self._multi_trigger_since = now
            dwell_elapsed = now - self._multi_trigger_since
            if dwell_elapsed >= self.dwell_seconds:
                return FlattenDecision(
                    recommended_level=HaltLevel.FLATTEN,
                    auto_flatten_authorized=True,
                    needs_human_flatten=False,
                    active_triggers=active,
                    reason=(
                        f"{count} severe triggers {active} held for "
                        f"{dwell_elapsed:.0f}s >= {self.dwell_seconds:.0f}s dwell — "
                        f"automated FLATTEN authorized"
                    ),
                )
            # Multi-trigger but still inside the dwell window: automate the
            # reversible verb now; a human may authorize the flatten immediately.
            return FlattenDecision(
                recommended_level=HaltLevel.DE_RISK,
                auto_flatten_authorized=False,
                needs_human_flatten=True,
                active_triggers=active,
                reason=(
                    f"{count} severe triggers {active} active for "
                    f"{dwell_elapsed:.0f}s (< {self.dwell_seconds:.0f}s dwell) — "
                    f"DE_RISK automated, FLATTEN awaiting dwell or human authorization"
                ),
            )

        # Fewer than min_triggers: clear the dwell timer.
        self._multi_trigger_since = None
        if count >= 1:
            return FlattenDecision(
                recommended_level=HaltLevel.DE_RISK,
                auto_flatten_authorized=False,
                needs_human_flatten=False,
                active_triggers=active,
                reason=f"single severe trigger {active} — DE_RISK automated (no flatten)",
            )
        return FlattenDecision(
            recommended_level=HaltLevel.NONE,
            auto_flatten_authorized=False,
            needs_human_flatten=False,
            active_triggers=[],
            reason="no severe triggers active",
        )
