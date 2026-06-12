"""Repository for user sessions — one row per logical browser/device session.

Backed by migration 022_user_sessions.sql. A session's `jti` rotates on every
/auth/refresh; revocation is by `revoked_at` flag and is enforced inside the
refresh endpoint (the DB is the source of truth for session liveness).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ._repository_base import BaseRepository


class UserSessionRepository(BaseRepository):
    async def create(
        self,
        *,
        user_id: str,
        jti: str,
        user_agent: Optional[str],
        ip: Optional[str],
        device: Optional[str],
        browser: Optional[str],
    ) -> Dict[str, Any]:
        """Create a new session row on /auth/callback. Returns the row."""
        # Annotated Any: INSERT ... RETURNING always yields a row, so the
        # Optional from _fetchrow never materialises here.
        row: Any = await self._fetchrow(
            """
            INSERT INTO user_sessions
                (user_id, jti, user_agent, ip_inet, device, browser)
            VALUES
                ($1, $2, $3, $4::inet, $5, $6)
            RETURNING session_id, user_id, jti, user_agent, host(ip_inet) AS ip,
                      device, browser, created_at, last_seen_at, revoked_at
            """,
            uuid.UUID(user_id),
            uuid.UUID(jti),
            user_agent,
            ip,
            device,
            browser,
        )
        return dict(row)

    async def get_by_jti(self, jti: str) -> Optional[Dict[str, Any]]:
        """Look up a session by its current jti. Used in /auth/refresh."""
        row = await self._fetchrow(
            """
            SELECT session_id, user_id, jti, revoked_at, last_seen_at
            FROM user_sessions
            WHERE jti = $1
            """,
            uuid.UUID(jti),
        )
        return dict(row) if row else None

    async def rotate_jti(self, session_id: str, new_jti: str) -> None:
        """Advance the session's jti and bump last_seen_at on /auth/refresh."""
        await self._execute(
            """
            UPDATE user_sessions
            SET jti = $2,
                last_seen_at = NOW()
            WHERE session_id = $1 AND revoked_at IS NULL
            """,
            uuid.UUID(session_id),
            uuid.UUID(new_jti),
        )

    async def list_active(self, user_id: str) -> List[Dict[str, Any]]:
        """List non-revoked sessions for the user, newest activity first."""
        rows = await self._fetch(
            """
            SELECT session_id, user_id, jti, user_agent, host(ip_inet) AS ip,
                   device, browser, created_at, last_seen_at
            FROM user_sessions
            WHERE user_id = $1 AND revoked_at IS NULL
            ORDER BY last_seen_at DESC
            """,
            uuid.UUID(user_id),
        )
        return [dict(r) for r in rows]

    async def revoke(
        self,
        *,
        session_id: str,
        user_id: str,
        reason: str = "user",
    ) -> Optional[Dict[str, Any]]:
        """Mark a session revoked. Scoped to the requesting user so one user
        can't revoke another's session. Returns the row (with jti) so the route
        can also drop a Redis denylist entry, or None if not found / not owned."""
        row = await self._fetchrow(
            """
            UPDATE user_sessions
            SET revoked_at = NOW(),
                revoked_reason = $3
            WHERE session_id = $1
              AND user_id = $2
              AND revoked_at IS NULL
            RETURNING session_id, jti
            """,
            uuid.UUID(session_id),
            uuid.UUID(user_id),
            reason,
        )
        return dict(row) if row else None

    @staticmethod
    def parse_ua(ua: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """Coarse device/browser parse from a User-Agent string.

        Pragmatic regex-on-substring split rather than a full UA library;
        sufficient for the sessions list. Returns (device, browser).
        """
        if not ua:
            return None, None
        device = (
            "Mac"
            if "Macintosh" in ua or "Mac OS X" in ua
            else (
                "Windows"
                if "Windows NT" in ua
                else (
                    "iPhone"
                    if "iPhone" in ua
                    else (
                        "Android"
                        if "Android" in ua
                        else "Linux" if "Linux" in ua else None
                    )
                )
            )
        )
        # Order matters — Edge identifies as Chrome too, so check Edg/ first.
        browser = (
            "Edge"
            if "Edg/" in ua
            else (
                "Chrome"
                if "Chrome/" in ua
                else (
                    "Firefox"
                    if "Firefox/" in ua
                    else "Safari" if "Safari/" in ua else None
                )
            )
        )
        return device, browser

    @staticmethod
    def to_response(
        row: Dict[str, Any], current_jti: Optional[str] = None
    ) -> Dict[str, Any]:
        """Serialize a row for the API. Adds `is_current` flag if the supplied
        jti matches — used by the FE to mark the row representing 'this browser'."""

        def _iso(v: Any) -> Optional[str]:
            if v is None:
                return None
            if isinstance(v, datetime):
                return v.astimezone(timezone.utc).isoformat()
            return str(v)

        return {
            "session_id": str(row["session_id"]),
            "device": row.get("device"),
            "browser": row.get("browser"),
            "ip": row.get("ip"),
            "user_agent": row.get("user_agent"),
            "created_at": _iso(row.get("created_at")),
            "last_seen_at": _iso(row.get("last_seen_at")),
            "is_current": current_jti is not None
            and str(row.get("jti")) == str(current_jti),
        }
