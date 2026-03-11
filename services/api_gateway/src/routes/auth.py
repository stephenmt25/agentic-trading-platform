"""Authentication routes for Phase 2.

Supports OAuth callback from NextAuth.js and user session management.
Replaces the Phase 1 mock login with real user upsert logic.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import timedelta
from typing import Optional
import uuid

import jwt as pyjwt

from libs.config import settings
from libs.observability import get_logger
from ..middleware.auth import create_access_token
from ..deps import get_timescale

logger = get_logger("auth-routes")

router = APIRouter(prefix="/auth", tags=["auth"])


class OAuthCallbackRequest(BaseModel):
    """Payload sent from the NextAuth.js frontend after OAuth completion."""
    email: str
    name: str
    image: Optional[str] = None
    provider: str  # "google" or "github"
    provider_account_id: str


class AuthResponse(BaseModel):
    """JWT tokens returned to the frontend for API authentication."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    display_name: str


class UserProfile(BaseModel):
    """Current user profile returned by /auth/me."""
    user_id: str
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    provider: str


@router.post("/callback", response_model=AuthResponse)
async def oauth_callback(req: OAuthCallbackRequest):
    """Handle OAuth callback from NextAuth.js.
    
    Receives the authenticated user info from the frontend's NextAuth session,
    upserts the user in the database, and returns backend JWT tokens.
    """
    # Generate deterministic user_id from provider info
    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{req.provider}:{req.provider_account_id}"))
    
    # Upsert user into the database so foreign keys work
    try:
        db = await get_timescale()
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
        # Don't block login if DB upsert fails — user can still get a token
    
    logger.info(
        "OAuth callback received",
        email=req.email,
        provider=req.provider,
        user_id=user_id,
    )
    
    token_data = {
        "sub": user_id,
        "email": req.email,
        "name": req.name,
        "provider": req.provider,
    }
    
    access_token = create_access_token(token_data, timedelta(hours=1))
    refresh_token = create_access_token(
        {"sub": user_id, "type": "refresh"}, timedelta(days=7)
    )
    
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        display_name=req.name,
    )


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    user_id: str = Depends(lambda: ""),  # Placeholder until proper DI
):
    """Return the current user's profile from the JWT."""
    return UserProfile(
        user_id=user_id or "unknown",
        email="user@example.com",
        display_name="User",
        provider="google",
    )
