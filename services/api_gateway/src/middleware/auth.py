import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from libs.config import settings

security = HTTPBearer()

# Redis key prefix for revoked refresh tokens
_REVOKED_TOKEN_PREFIX = "auth:revoked:"


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=7))
    to_encode.update({"exp": expire, "type": "refresh"})
    if not settings.REFRESH_SECRET_KEY:
        raise RuntimeError("REFRESH_SECRET_KEY must be configured separately from SECRET_KEY")
    encoded_jwt = jwt.encode(to_encode, settings.REFRESH_SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def verify_refresh_token(token: str) -> dict:
    if not settings.REFRESH_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Refresh token infrastructure not configured")
    key = settings.REFRESH_SECRET_KEY
    try:
        payload = jwt.decode(token, key, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


async def revoke_refresh_token(redis_client, token: str, ttl_seconds: int = 7 * 24 * 3600):
    """Add a refresh token to the revocation denylist in Redis."""
    key = f"{_REVOKED_TOKEN_PREFIX}{token}"
    await redis_client.set(key, "1", ex=ttl_seconds)


async def is_refresh_token_revoked(redis_client, token: str) -> bool:
    """Check if a refresh token has been revoked."""
    key = f"{_REVOKED_TOKEN_PREFIX}{token}"
    return await redis_client.exists(key)


async def verify_jwt(request: Request):
    """Middleware logic to verify JWT."""
    # Excluded paths — /auth/me requires auth so only skip callback and refresh
    excluded = ["/health", "/ready", "/auth/callback", "/auth/refresh"]
    if request.url.path in excluded:
        return

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        request.state.user_id = payload.get("sub")
        if not request.state.user_id:
            raise HTTPException(status_code=401, detail="Token invalid: missing subject")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token validation failed")
