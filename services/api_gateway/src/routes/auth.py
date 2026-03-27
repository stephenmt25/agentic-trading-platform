"""Authentication routes for Phase 2.

Supports OAuth callback from NextAuth.js, user session management,
and refresh token rotation.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from datetime import timedelta
import uuid

import jwt as pyjwt

from libs.core.schemas import OAuthCallbackRequest, AuthResponse, RefreshRequest, UserProfile
from libs.config import settings
from libs.observability import get_logger
from ..middleware.auth import create_access_token, create_refresh_token, verify_refresh_token, revoke_refresh_token, is_refresh_token_revoked
from ..deps import get_timescale, get_current_user, get_redis

logger = get_logger("auth-routes")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/callback", response_model=AuthResponse)
async def oauth_callback(req: OAuthCallbackRequest, request: Request):
    """Handle OAuth callback from NextAuth.js.

    Receives the authenticated user info from the frontend's NextAuth session,
    verifies the id_token against the provider, upserts the user in the database,
    and returns backend JWT tokens.
    """
    # Verify the NextAuth.js session token using the shared NEXTAUTH_SECRET
    if not settings.NEXTAUTH_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Server authentication not configured"
        )
    try:
        pyjwt.decode(
            req.id_token,
            settings.NEXTAUTH_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session token"
        )

    # Generate deterministic user_id from provider info
    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{req.provider}:{req.provider_account_id}"))

    # Upsert user into the database — block login on failure to prevent orphaned tokens
    db = await get_timescale(request)
    try:
        await db.execute(
            """
            INSERT INTO users (user_id, email, display_name, provider, provider_account_id,
                               hashed_password, jurisdiction, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET email = EXCLUDED.email,
                display_name = EXCLUDED.display_name,
                updated_at = NOW()
            """,
            uuid.UUID(user_id),
            req.email,
            req.name,
            req.provider,
            req.provider_account_id,
            "oauth_no_password",   # OAuth users don't have passwords
            "global",              # Default jurisdiction
        )
    except Exception as e:
        logger.error("Failed to upsert user", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=503,
            detail="Unable to complete authentication. Please try again."
        )

    logger.info(
        "OAuth callback received",
        provider=req.provider,
        user_id=user_id,
    )

    # Only include sub claim in JWT — fetch profile data server-side
    token_data = {"sub": user_id}

    access_token = create_access_token(token_data, timedelta(hours=1))
    refresh_token = create_refresh_token({"sub": user_id}, timedelta(days=7))

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        display_name=req.name,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_tokens(req: RefreshRequest, request: Request):
    """Exchange a valid refresh token for a new access + refresh token pair (rotation).

    The old refresh token is revoked immediately to prevent reuse.
    """
    # Check if this refresh token has been revoked
    redis = get_redis()
    if await is_refresh_token_revoked(redis, req.refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    payload = verify_refresh_token(req.refresh_token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Verify user still exists in DB
    db = await get_timescale(request)
    user = await db.fetchrow("SELECT user_id, display_name FROM users WHERE user_id = $1", uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    # Revoke the old refresh token before issuing new ones
    await revoke_refresh_token(redis, req.refresh_token)

    token_data = {"sub": user_id}
    new_access = create_access_token(token_data, timedelta(hours=1))
    new_refresh = create_refresh_token({"sub": user_id}, timedelta(days=7))

    return AuthResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user_id=user_id,
        display_name=str(user["display_name"]),
    )


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    request: Request,
    user_id: str = Depends(get_current_user),
):
    """Return the current user's profile from the database."""
    db = await get_timescale(request)
    user = await db.fetchrow(
        "SELECT user_id, email, display_name, provider FROM users WHERE user_id = $1",
        uuid.UUID(user_id),
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfile(
        user_id=str(user["user_id"]),
        email=user["email"],
        display_name=user["display_name"],
        provider=user["provider"],
    )
