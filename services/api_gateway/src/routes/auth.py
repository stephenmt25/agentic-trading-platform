"""Authentication routes for Phase 2.

Supports OAuth callback from NextAuth.js, user session management,
and refresh token rotation.

Session model (added 2026-05-12, migration 022_user_sessions.sql):
  * /auth/callback creates a `user_sessions` row keyed by the refresh token's
    jti, capturing user-agent / IP / parsed device for the sessions list.
  * /auth/refresh validates the session is still active (DB is the source of
    truth for liveness) and rotates the jti on every call.
  * /auth/sessions exposes the active sessions to /settings/sessions.
  * /auth/sessions/{id}/revoke flips revoked_at — the next /auth/refresh for
    that jti will fail and the user is forced back to /login.
"""

import uuid
from datetime import timedelta

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request

from libs.config import settings
from libs.core.schemas import (
    AuthResponse,
    OAuthCallbackRequest,
    RefreshRequest,
    UserProfile,
)
from libs.observability import get_logger
from libs.storage.repositories.user_session_repo import UserSessionRepository

from ..deps import (
    get_current_session_id,
    get_current_user,
    get_redis,
    get_timescale,
    get_user_session_repo,
)
from ..middleware.auth import (
    create_access_token,
    create_refresh_token,
    is_refresh_token_revoked,
    revoke_refresh_token,
    verify_refresh_token,
)

logger = get_logger("auth-routes")

router = APIRouter(tags=["auth"])


def _client_ip(request: Request) -> str | None:
    """Honor X-Forwarded-For if the gateway sits behind a proxy (Vercel, k8s
    ingress), otherwise fall back to the direct client host. Returns the
    first IP in the chain only — that's the originating client."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return None


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
            status_code=500, detail="Server authentication not configured"
        )
    try:
        pyjwt.decode(
            req.id_token,
            settings.NEXTAUTH_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")

    # Generate deterministic user_id from provider info
    user_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"{req.provider}:{req.provider_account_id}")
    )

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
            "oauth_no_password",  # OAuth users don't have passwords
            "global",  # Default jurisdiction
        )
    except Exception as e:
        logger.error("Failed to upsert user", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=503,
            detail="Unable to complete authentication. Please try again.",
        )

    logger.info(
        "OAuth callback received",
        provider=req.provider,
        user_id=user_id,
    )

    # Mint refresh first so we have the jti to insert into the session row,
    # then propagate session_id into the access token so /auth/sessions can
    # mark the current row.
    refresh_token, jti = create_refresh_token({"sub": user_id}, timedelta(days=7))

    sessions_repo = UserSessionRepository(db)
    user_agent = request.headers.get("User-Agent")
    ip = _client_ip(request)
    device, browser = UserSessionRepository.parse_ua(user_agent)
    try:
        session_row = await sessions_repo.create(
            user_id=user_id,
            jti=jti,
            user_agent=user_agent,
            ip=ip,
            device=device,
            browser=browser,
        )
    except Exception as e:
        # Fail soft: if the session row can't be written, the user can still
        # authenticate — the sessions list just won't show this browser. This
        # protects login from a migration-021/022 race or a transient DB issue
        # without compromising the auth path itself.
        logger.warning("Failed to record user session", user_id=user_id, error=str(e))
        session_row = None

    session_id = str(session_row["session_id"]) if session_row else None
    access_token = create_access_token(
        {"sub": user_id, "session_id": session_id},
        timedelta(hours=1),
    )

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        display_name=req.name,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_tokens(req: RefreshRequest, request: Request):
    """Exchange a valid refresh token for a new access + refresh token pair (rotation).

    The old refresh token is revoked immediately to prevent reuse, and the
    session row's jti is rotated to the new jti so /auth/sessions stays in
    sync. If the session has been revoked by the user (or by another device),
    this endpoint rejects — the user is forced back to /login.
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
    user = await db.fetchrow(
        "SELECT user_id, display_name FROM users WHERE user_id = $1", uuid.UUID(user_id)
    )
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    # Validate the session — DB is the source of truth for liveness. Tokens
    # minted before migration 022 won't have a jti claim; treat those as
    # legacy and skip the session check (graceful rollout — they expire
    # naturally within the 7-day window).
    sessions_repo = UserSessionRepository(db)
    old_jti = payload.get("jti")
    session_id: str | None = None
    if old_jti:
        session = await sessions_repo.get_by_jti(old_jti)
        if session is None:
            raise HTTPException(status_code=401, detail="Session not found")
        if session["revoked_at"] is not None:
            raise HTTPException(status_code=401, detail="Session revoked")
        session_id = str(session["session_id"])

    # Revoke the old refresh token before issuing new ones
    await revoke_refresh_token(redis, req.refresh_token)

    new_refresh, new_jti = create_refresh_token(
        {"sub": user_id},
        timedelta(days=7),
    )

    # Rotate the session's jti so subsequent /auth/refresh attempts on the
    # old jti fail (defense in depth alongside the Redis denylist).
    if session_id:
        await sessions_repo.rotate_jti(session_id, new_jti)

    new_access = create_access_token(
        {"sub": user_id, "session_id": session_id},
        timedelta(hours=1),
    )

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


# ---------------------------------------------------------------------------
# Sessions — backing the /settings/sessions surface (spec §9).
# ---------------------------------------------------------------------------


@router.get("/sessions")
async def list_sessions(
    request: Request,
    user_id: str = Depends(get_current_user),
    repo: UserSessionRepository = Depends(get_user_session_repo),
    session_id: str | None = Depends(get_current_session_id),
):
    """List the requesting user's active sessions. Marks the current row
    via the `session_id` claim on the access token."""
    rows = await repo.list_active(user_id)
    # We don't know the current jti here (only the session_id from the
    # access token), so to_response gets None for current_jti — mark
    # current by matching session_id in a follow-up pass.
    items = []
    for r in rows:
        item = UserSessionRepository.to_response(r, current_jti=None)
        item["is_current"] = session_id is not None and item["session_id"] == session_id
        items.append(item)
    return {"sessions": items}


@router.post("/sessions/{target_session_id}/revoke")
async def revoke_session(
    target_session_id: str,
    request: Request,
    user_id: str = Depends(get_current_user),
    repo: UserSessionRepository = Depends(get_user_session_repo),
):
    """Revoke a session by ID. Scoped to the requesting user — one user
    cannot revoke another's session. Returns 404 if the session doesn't
    exist or already revoked. The next /auth/refresh attempt on the revoked
    session's jti will fail with 'Session revoked'."""
    try:
        uuid.UUID(target_session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid session_id")
    row = await repo.revoke(
        session_id=target_session_id, user_id=user_id, reason="user"
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail="Session not found or already revoked"
        )
    logger.info("Session revoked", user_id=user_id, session_id=target_session_id)
    return {"session_id": target_session_id, "revoked": True}
