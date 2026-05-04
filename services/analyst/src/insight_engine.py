"""Insight Engine orchestrator (Track D.PR2 MVP).

Periodically (every 6h) sweeps the trade_decisions ledger for each
(active_profile, symbol) pair, computes per-gate efficacy reports, and
persists them to gate_efficacy_reports. PR2's other metrics
(attribution / heatmap / close-reason taxonomy) are deliberately deferred
to follow-up PRs — see SECOND-BRAIN-PRS-REMAINING.md §PR2.

Sample-size handling: when fewer than MIN_SAMPLE_SIZE blocked or passed
rows are found in a window, the report still persists with NULL metric
values so the dashboard can surface "not enough data yet" instead of
silently producing nothing.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from libs.config import settings
from libs.observability import get_logger
from libs.storage.repositories.decision_repo import DecisionRepository
from libs.storage.repositories.gate_efficacy_repo import GateEfficacyRepository
from libs.storage.repositories.market_data_repo import MarketDataRepository
from libs.storage.repositories.profile_repo import ProfileRepository

from .gate_efficacy import (
    DEFAULT_LOOKAHEAD_BARS,
    DEFAULT_TIMEFRAME,
    GateEfficacyReport,
    compute_gate_report,
    discover_gates_in_window,
)

logger = get_logger("analyst.insight_engine")

INSIGHT_RUN_INTERVAL_S = 6 * 60 * 60  # 6 hours
ANALYSIS_WINDOW_HOURS = 24 * 7        # last 7 days
DECISION_FETCH_LIMIT = 5000           # safety cap; one symbol+profile rarely exceeds


def _parse_jsonb(value: Any) -> Dict[str, Any]:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value or {}


async def _fetch_decisions_in_window(
    decision_repo: DecisionRepository,
    *,
    profile_id: str,
    symbol: str,
    window_start: datetime,
    window_end: datetime,
) -> List[Dict[str, Any]]:
    """Get every decision for a (profile, symbol) within a window.

    Implemented as a small repo-internal SQL query rather than extending
    DecisionRepository.get_decisions with new filters — gate efficacy is
    one consumer and the existing API doesn't need a date-range option.
    """
    query = """
    SELECT * FROM trade_decisions
    WHERE profile_id = $1 AND symbol = $2
      AND created_at BETWEEN $3 AND $4
    ORDER BY created_at ASC
    LIMIT $5
    """
    from uuid import UUID
    records = await decision_repo._fetch(  # noqa: SLF001 — same package, scoped read
        query, UUID(profile_id), symbol, window_start, window_end, DECISION_FETCH_LIMIT
    )
    return [dict(r) for r in records]


async def _candle_lookup(
    market_repo: MarketDataRepository,
    symbol: str,
    timeframe: str,
    decision_ts: datetime,
    lookahead_bars: int,
) -> List[Dict[str, Any]]:
    """Fetch up to ``lookahead_bars`` candles strictly after ``decision_ts``.

    For 1m timeframe this is a 60-bar (1h) window — long enough to hit a
    typical stop-loss or take-profit, short enough to keep the per-decision
    fetch cheap.
    """
    if decision_ts is None:
        return []
    if not decision_ts.tzinfo:
        decision_ts = decision_ts.replace(tzinfo=timezone.utc)
    bar_seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}.get(timeframe, 60)
    end = decision_ts + timedelta(seconds=bar_seconds * (lookahead_bars + 5))
    candles = await market_repo.get_candles_by_range(symbol, timeframe, decision_ts, end)
    return candles[:lookahead_bars]


async def run_once(
    profile_repo: ProfileRepository,
    decision_repo: DecisionRepository,
    market_repo: MarketDataRepository,
    gate_repo: GateEfficacyRepository,
    *,
    window_hours: int = ANALYSIS_WINDOW_HOURS,
    lookahead_bars: int = DEFAULT_LOOKAHEAD_BARS,
    timeframe: str = DEFAULT_TIMEFRAME,
) -> int:
    """Execute one Insight Engine pass. Returns number of report rows written."""
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(hours=window_hours)

    rows_written = 0
    profiles = await profile_repo.get_active_profiles()
    if not profiles:
        logger.info("Insight Engine: no active profiles")
        return 0

    symbols = list(settings.TRADING_SYMBOLS)

    for profile in profiles:
        profile_id = str(profile.get("profile_id"))
        risk_limits = _parse_jsonb(profile.get("risk_limits"))
        for symbol in symbols:
            decisions = await _fetch_decisions_in_window(
                decision_repo,
                profile_id=profile_id,
                symbol=symbol,
                window_start=window_start,
                window_end=window_end,
            )
            if not decisions:
                continue
            gates = discover_gates_in_window(decisions)
            if not gates:
                logger.info(
                    "Insight Engine: no blocked decisions in window — skipping",
                    profile_id=profile_id,
                    symbol=symbol,
                )
                continue

            # Pre-fetch candles per decision once; share across gate reports.
            candles_cache: Dict[Any, List[Dict[str, Any]]] = {}

            async def candles_after(ts):  # noqa: ANN001 — closure
                if ts in candles_cache:
                    return candles_cache[ts]
                fetched = await _candle_lookup(market_repo, symbol, timeframe, ts, lookahead_bars)
                candles_cache[ts] = fetched
                return fetched

            for gate_name in gates:
                # compute_gate_report expects a sync candles_after callable; bridge
                # via materialising the lookups for this profile/symbol upfront.
                gathered: Dict[Any, List[Dict[str, Any]]] = {}
                for d in decisions:
                    ts = d.get("created_at")
                    if ts not in gathered:
                        gathered[ts] = await candles_after(ts)

                report: GateEfficacyReport = compute_gate_report(
                    profile_id=profile_id,
                    symbol=symbol,
                    gate_name=gate_name,
                    window_start=window_start,
                    window_end=window_end,
                    decisions=decisions,
                    candles_after=lambda ts, g=gathered: g.get(ts, []),
                    risk_limits=risk_limits,
                    lookahead_bars=lookahead_bars,
                )
                await gate_repo.write_report(
                    profile_id=report.profile_id,
                    symbol=report.symbol,
                    gate_name=report.gate_name,
                    window_start=report.window_start,
                    window_end=report.window_end,
                    blocked_count=report.blocked_count,
                    passed_count=report.passed_count,
                    sample_size_blocked=report.sample_size_blocked,
                    sample_size_passed=report.sample_size_passed,
                    blocked_would_be_win_rate=report.blocked_would_be_win_rate,
                    blocked_would_be_pnl_pct=report.blocked_would_be_pnl_pct,
                    passed_realized_win_rate=report.passed_realized_win_rate,
                    passed_realized_pnl_pct=report.passed_realized_pnl_pct,
                    confidence_band=report.confidence_band,
                )
                rows_written += 1
                logger.info(
                    "Gate efficacy report written",
                    profile_id=profile_id,
                    symbol=symbol,
                    gate=gate_name,
                    blocked=report.blocked_count,
                    passed=report.passed_count,
                    blocked_wr=report.blocked_would_be_win_rate,
                    passed_wr=report.passed_realized_win_rate,
                )
    return rows_written


async def insight_engine_loop(
    profile_repo: ProfileRepository,
    decision_repo: DecisionRepository,
    market_repo: MarketDataRepository,
    gate_repo: GateEfficacyRepository,
) -> None:
    """Forever-loop driver. Runs ``run_once`` every INSIGHT_RUN_INTERVAL_S."""
    while True:
        try:
            written = await run_once(profile_repo, decision_repo, market_repo, gate_repo)
            logger.info("Insight Engine pass complete", reports_written=written)
        except Exception as e:
            logger.error("Insight Engine pass failed", error=str(e))
        await asyncio.sleep(INSIGHT_RUN_INTERVAL_S)
