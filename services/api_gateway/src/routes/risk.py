"""Portfolio-level risk-truth read endpoints (FE-W1, locked decision #6).

Thin Redis read-throughs — no computation, no mutation:

  GET /risk/portfolio  — PR4 portfolio exposure snapshot written by
                         services/risk/src/portfolio.py to `risk:portfolio:snapshot`
                         (TTL 120s). Values are string-encoded Decimals and are
                         passed through as strings — NEVER converted to float.
  GET /risk/decay      — PR7 live-vs-backtest decay snapshot written by
                         services/analyst/src/decay_tracker.py to
                         `analyst:decay:snapshot` (TTL 1d), filtered to the
                         current user's profiles.

Both endpoints are honest about absence: a missing/expired snapshot returns
`stale: true` with empty data, never zeros-as-truth.
"""

import json

from fastapi import APIRouter, Depends

from libs.config import settings
from libs.core.portfolio import SNAPSHOT_KEY as PORTFOLIO_SNAPSHOT_KEY
from libs.observability import get_logger
from libs.storage.repositories.profile_repo import ProfileRepository

from ..deps import get_current_user, get_profile_repo, get_redis
from .commands import is_operator

router = APIRouter(tags=["risk"])

logger = get_logger("api_gateway.risk")

# Written by services/analyst/src/decay_tracker.py (SNAPSHOT_KEY). Defined
# locally to avoid importing a service module into the gateway.
DECAY_SNAPSHOT_KEY = "analyst:decay:snapshot"


def _decode(raw) -> str | None:
    """Redis client returns bytes (no decode_responses) — decode at the wire."""
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode()
    return str(raw)


@router.get("/portfolio")
async def get_portfolio_risk(
    user_id: str = Depends(get_current_user),
    redis=Depends(get_redis),
):
    """Portfolio-wide gross exposure + per-cluster / per-symbol concentration.

    All money values are string-encoded Decimals (pass-through from the
    snapshot; budget/cap from settings) — the FE parses for display only.

    Authorization (CWE-200): portfolio risk is global by nature, but the
    per-symbol / per-cluster breakdown reveals every user's open positions
    and sizes. Non-operators get the aggregate (gross vs budget) only, with
    `detail_restricted: true` so the FE renders a restricted state rather
    than empty-as-flat. See commands.is_operator for the allowlist contract
    (unconfigured = single-operator deployment = full detail).
    """
    budget = str(settings.PORTFOLIO_GROSS_BUDGET_USD)
    cap = str(settings.CORRELATION_CLUSTER_CAP_PCT)
    operator = is_operator(user_id)
    stale_payload = {
        "gross_usd": "0",
        "per_cluster": {},
        "per_symbol": {},
        "gross_budget_usd": budget,
        "cluster_cap_pct": cap,
        "stale": True,
        "detail_restricted": not operator,
    }

    try:
        raw = _decode(await redis.get(PORTFOLIO_SNAPSHOT_KEY))
    except Exception as exc:
        # Redis-down must be distinguishable from a normally-expired snapshot
        # in the logs, even though both render as `stale` to the client.
        logger.warning("portfolio snapshot read failed", error=str(exc))
        return stale_payload
    if not raw:
        return stale_payload
    try:
        snap = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("portfolio snapshot malformed", error=str(exc))
        return stale_payload

    per_cluster = (
        {str(k): str(v) for k, v in (snap.get("per_cluster") or {}).items()}
        if operator
        else {}
    )
    per_symbol = (
        {str(k): str(v) for k, v in (snap.get("per_symbol") or {}).items()}
        if operator
        else {}
    )
    return {
        "gross_usd": str(snap.get("gross_usd", "0")),
        "per_cluster": per_cluster,
        "per_symbol": per_symbol,
        "gross_budget_usd": budget,
        "cluster_cap_pct": cap,
        "stale": False,
        "detail_restricted": not operator,
    }


@router.get("/decay")
async def get_decay_status(
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    redis=Depends(get_redis),
):
    """Per-profile strategy-decay reports (PR7), filtered to the user's profiles.

    Report fields per profile: status (no_baseline | insufficient_live | ok |
    decayed), decayed, reasons[], live_win_rate, backtest_win_rate,
    live_avg_pct, backtest_avg_return, live_trades, shadow_count, shadow_share.
    """
    try:
        raw = _decode(await redis.get(DECAY_SNAPSHOT_KEY))
    except Exception as exc:
        logger.warning("decay snapshot read failed", error=str(exc))
        return {"stale": True, "profiles": []}
    if not raw:
        return {"stale": True, "profiles": []}
    try:
        reports = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("decay snapshot malformed", error=str(exc))
        return {"stale": True, "profiles": []}
    if not isinstance(reports, list):
        return {"stale": True, "profiles": []}

    profiles = await profile_repo.get_all_profiles_for_user(user_id)
    owned = {str(p.get("profile_id", "")) for p in profiles}
    filtered = [
        r
        for r in reports
        if isinstance(r, dict) and str(r.get("profile_id", "")) in owned
    ]
    return {"stale": False, "profiles": filtered}
