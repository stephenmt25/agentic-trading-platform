"""Strategy-decay assessment (PR7 — closes the comparison part of 3.14).

Compares a strategy's LIVE performance (closed_trades, net-of-cost from PR5)
against its BACKTEST expectation (backtest_results) and flags decay when live
materially underperforms. Pure scoring logic — the DecayTracker owns reading the
live / baseline / shadow data and surfacing the result.

NOTE: this is the live-vs-backtest *comparison* the brief scopes to PR7. The
deeper 3.14 gap — walk-forward, look-ahead/survivorship guards, an out-of-sample
backtest engine, and auto-deprecation — is a separate, larger effort (tracked in
TECH-DEBT-REGISTRY) and is NOT built here.
"""

from dataclasses import dataclass, field
from typing import List, Optional

# Initial thresholds (tunable). Decay fires if the live win rate falls more than
# WIN_RATE_DROP below backtest, or live avg return drops below AVG_FACTOR of it.
DEFAULT_MIN_LIVE_TRADES = 20
DEFAULT_WIN_RATE_DROP = 0.15
DEFAULT_AVG_FACTOR = 0.5


@dataclass
class DecayAssessment:
    status: str  # "no_baseline" | "insufficient_live" | "ok" | "decayed"
    decayed: bool
    reasons: List[str] = field(default_factory=list)
    live_win_rate: Optional[float] = None
    backtest_win_rate: Optional[float] = None
    live_avg_pct: Optional[float] = None
    backtest_avg_return: Optional[float] = None


def assess_decay(
    *,
    live_trades: int,
    live_win_rate: Optional[float],
    live_avg_pct: Optional[float],
    backtest_win_rate: Optional[float],
    backtest_avg_return: Optional[float],
    min_live_trades: int = DEFAULT_MIN_LIVE_TRADES,
    win_rate_drop: float = DEFAULT_WIN_RATE_DROP,
    avg_factor: float = DEFAULT_AVG_FACTOR,
) -> DecayAssessment:
    base = dict(
        live_win_rate=live_win_rate,
        backtest_win_rate=backtest_win_rate,
        live_avg_pct=live_avg_pct,
        backtest_avg_return=backtest_avg_return,
    )

    if backtest_win_rate is None and backtest_avg_return is None:
        return DecayAssessment(
            "no_baseline", False, ["no backtest baseline for this profile"], **base
        )
    if live_trades < min_live_trades:
        return DecayAssessment(
            "insufficient_live",
            False,
            [f"only {live_trades} live trades (< {min_live_trades} needed)"],
            **base,
        )

    reasons: List[str] = []
    if backtest_win_rate is not None and live_win_rate is not None:
        drop = backtest_win_rate - live_win_rate
        if drop > win_rate_drop:
            reasons.append(
                f"live win rate {live_win_rate:.0%} is {drop:.0%} below "
                f"backtest {backtest_win_rate:.0%}"
            )
    if (
        backtest_avg_return is not None
        and live_avg_pct is not None
        and backtest_avg_return > 0
        and live_avg_pct < backtest_avg_return * avg_factor
    ):
        reasons.append(
            f"live avg return {live_avg_pct:.4f} < {avg_factor:.0%} of "
            f"backtest {backtest_avg_return:.4f}"
        )

    decayed = len(reasons) > 0
    return DecayAssessment("decayed" if decayed else "ok", decayed, reasons, **base)
