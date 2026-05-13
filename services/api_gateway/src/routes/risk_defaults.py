"""User-level risk defaults — /risk-defaults.

Surfaces the persistent store behind /settings/risk in the redesigned
frontend. Scope is explicitly account-level and applies to *newly
created* profiles; propagation to running profiles (the recompile fan-out)
is a separate project and is documented inline on the FE.

See migration 021_user_risk_defaults.sql and the surface spec in
docs/design/05-surface-specs/06-profiles-settings.md §5.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from libs.core.schemas import (
    UserRiskDefaultsPayload,
    UserRiskDefaultsResponse,
)
from libs.observability import get_logger
from libs.storage.repositories.user_risk_defaults_repo import (
    UserRiskDefaultsRepository,
)

from ..deps import get_current_user, get_timescale

logger = get_logger("risk-defaults")

router = APIRouter()


async def _get_repo(request: Request) -> UserRiskDefaultsRepository:
    return UserRiskDefaultsRepository(await get_timescale(request))


@router.get("", response_model=UserRiskDefaultsResponse)
async def get_risk_defaults(
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """Return persisted defaults; if the user has never saved, return the
    canonical defaults with `updated_at=null` so the FE can render the form
    without distinguishing 'unsaved' from 'empty'."""
    repo = await _get_repo(request)
    row = await repo.get(user_id)
    if row is None:
        return UserRiskDefaultsResponse(
            defaults=UserRiskDefaultsPayload(),
            updated_at=None,
        )
    return UserRiskDefaultsResponse(
        defaults=UserRiskDefaultsPayload(**row["defaults"]),
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
    )


@router.put("", response_model=UserRiskDefaultsResponse)
async def save_risk_defaults(
    payload: UserRiskDefaultsPayload,
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """Validate + persist the user's defaults. Echoes back the stored shape so
    the FE can pin its 'pristine' state from the response (avoids relying on
    optimistic state when the validator coerces values)."""
    repo = await _get_repo(request)
    try:
        row = await repo.upsert(user_id, payload.model_dump())
    except Exception as exc:
        logger.error("user_risk_defaults upsert failed", user_id=user_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to save risk defaults.")
    return UserRiskDefaultsResponse(
        defaults=UserRiskDefaultsPayload(**row["defaults"]),
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
    )
