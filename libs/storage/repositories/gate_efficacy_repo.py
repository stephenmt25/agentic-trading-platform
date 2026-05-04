"""Persistence for gate_efficacy_reports (Track D.PR2 MVP).

Two operations only: ``write_report`` (called by the analyst worker every
6h) and ``get_recent`` (called by the api_gateway endpoint).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from ._repository_base import BaseRepository


def _to_numeric(value) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value))


class GateEfficacyRepository(BaseRepository):
    async def write_report(
        self,
        *,
        profile_id: str,
        symbol: str,
        gate_name: str,
        window_start: datetime,
        window_end: datetime,
        blocked_count: int,
        passed_count: int,
        sample_size_blocked: int,
        sample_size_passed: int,
        blocked_would_be_win_rate: Optional[float],
        blocked_would_be_pnl_pct: Optional[float],
        passed_realized_win_rate: Optional[float],
        passed_realized_pnl_pct: Optional[float],
        confidence_band: Optional[float],
    ) -> None:
        query = """
        INSERT INTO gate_efficacy_reports (
            profile_id, symbol, gate_name, window_start, window_end,
            blocked_count, passed_count,
            blocked_would_be_win_rate, blocked_would_be_pnl_pct,
            passed_realized_win_rate, passed_realized_pnl_pct,
            sample_size_blocked, sample_size_passed, confidence_band
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """
        await self._execute(
            query,
            UUID(profile_id),
            symbol,
            gate_name,
            window_start if window_start.tzinfo else window_start.replace(tzinfo=timezone.utc),
            window_end if window_end.tzinfo else window_end.replace(tzinfo=timezone.utc),
            blocked_count,
            passed_count,
            _to_numeric(blocked_would_be_win_rate),
            _to_numeric(blocked_would_be_pnl_pct),
            _to_numeric(passed_realized_win_rate),
            _to_numeric(passed_realized_pnl_pct),
            sample_size_blocked,
            sample_size_passed,
            _to_numeric(confidence_band),
        )

    async def get_recent(
        self,
        *,
        symbol: str,
        profile_id: Optional[str] = None,
        gate_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        conds: list[str] = ["symbol = $1"]
        params: list = [symbol]
        idx = 2
        if profile_id:
            conds.append(f"profile_id = ${idx}")
            params.append(UUID(profile_id))
            idx += 1
        if gate_name:
            conds.append(f"gate_name = ${idx}")
            params.append(gate_name)
            idx += 1
        where = "WHERE " + " AND ".join(conds)
        query = f"""
        SELECT
            report_id::text, profile_id::text, symbol, gate_name,
            window_start, window_end,
            blocked_count, passed_count,
            blocked_would_be_win_rate, blocked_would_be_pnl_pct,
            passed_realized_win_rate, passed_realized_pnl_pct,
            sample_size_blocked, sample_size_passed,
            confidence_band, created_at
        FROM gate_efficacy_reports
        {where}
        ORDER BY created_at DESC
        LIMIT ${idx}
        """
        params.append(limit)
        records = await self._fetch(query, *params)
        return [dict(r) for r in records]
