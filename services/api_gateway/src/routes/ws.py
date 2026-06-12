import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set

import jwt
import msgpack
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from libs.config import settings
from libs.messaging.channels import (
    PUBSUB_AGENT_TELEMETRY,
    PUBSUB_HITL_PENDING,
    PUBSUB_ORDERBOOK,
    PUBSUB_PNL_UPDATES,
    PUBSUB_SYSTEM_ALERTS,
    PUBSUB_TRADES,
)
from libs.observability import get_logger
from libs.storage.repositories.profile_repo import ProfileRepository

from ..deps import get_redis


def _decode_pubsub_payload(data_raw: Any) -> Any:
    """Decode a Redis pubsub payload published by either:

    - libs.messaging._pubsub.PubSubBroadcaster (msgpack bytes — internal
      services use this; first byte >= 0x80)
    - Legacy JSON publishers (UTF-8 bytes or str — first byte in printable
      ASCII range)

    Falls back to a string representation if neither decoder accepts the
    payload, so the WS handler never raises into the reconnect loop on a
    malformed message.
    """
    if isinstance(data_raw, bytes):
        if data_raw and data_raw[0] >= 0x80:
            try:
                return msgpack.unpackb(data_raw, raw=False)
            except (
                ValueError,
                TypeError,
                msgpack.exceptions.ExtraData,
                msgpack.exceptions.UnpackException,
                msgpack.exceptions.FormatError,
            ):
                pass
        try:
            data_str = data_raw.decode("utf-8")
        except UnicodeDecodeError:
            return repr(data_raw[:200])
    else:
        data_str = data_raw

    try:
        return json.loads(data_str)
    except (json.JSONDecodeError, TypeError):
        return data_str


logger = get_logger("ws")

router = APIRouter(tags=["ws"])

MAX_RECONNECT_DELAY = 30
INITIAL_RECONNECT_DELAY = 1

# Minimum seconds between profile-set refreshes per connection. A stream of
# other users' pnl events would otherwise trigger a DB query per message
# (CWE-400) — within this window, misses are simply dropped.
PNL_FILTER_REFRESH_MIN_S = 5.0


class PnlProfileFilter:
    """Server-side per-user filter for `pubsub:pnl_updates` (registry row 70).

    `PnlUpdateEvent` carries `profile_id` but deliberately NOT `user_id`
    (producers stay tenant-agnostic), so ownership is resolved at the WS edge:
    the authenticated user's profile_id set is loaded from the profile
    repository at connect, and each pnl message is forwarded only when its
    `profile_id` is in that set. On a miss the set is lazily refreshed once
    (rate-limited to one refresh per `refresh_min_s`) before deciding — this
    covers profiles created after the socket connected.

    Fail-closed: if the profile set has never loaded (DB down at connect and
    on every retry), pnl events are NOT forwarded — privacy over liveness;
    all other channels keep flowing.
    """

    def __init__(
        self,
        user_id: str,
        profile_repo: Optional[ProfileRepository],
        refresh_min_s: float = PNL_FILTER_REFRESH_MIN_S,
        clock=time.monotonic,
    ):
        self._user_id = user_id
        self._repo = profile_repo
        self._refresh_min_s = refresh_min_s
        self._clock = clock
        self._profile_ids: Optional[Set[str]] = None  # None = never loaded
        self._last_refresh_attempt = float("-inf")

    async def _refresh(self) -> None:
        self._last_refresh_attempt = self._clock()
        if self._repo is None:
            return
        try:
            profiles = await self._repo.get_all_profiles_for_user(self._user_id)
            self._profile_ids = {
                str(p.get("profile_id")) for p in profiles if p.get("profile_id")
            }
        except Exception as exc:
            logger.warning(
                "pnl filter profile-set load failed",
                user_id=self._user_id,
                error=str(exc),
            )

    async def prime(self) -> None:
        """Load the profile set once at connect."""
        await self._refresh()

    async def should_forward(self, data: Any) -> bool:
        """True when `data` is a pnl payload owned by this connection's user."""
        if not isinstance(data, dict):
            return False
        profile_id = str(data.get("profile_id") or "")
        if not profile_id:
            return False
        if self._profile_ids is not None and profile_id in self._profile_ids:
            return True
        # Miss (or never loaded) → lazily refresh once before deciding,
        # rate-limited so foreign events can't hammer the DB.
        if self._clock() - self._last_refresh_attempt >= self._refresh_min_s:
            await self._refresh()
        return self._profile_ids is not None and profile_id in self._profile_ids


class ConnectionManager:
    def __init__(self):
        self._user_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self._user_connections:
            self._user_connections[user_id] = []
        self._user_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        conns = self._user_connections.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._user_connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, message: str):
        dead: List[WebSocket] = []
        for ws in self._user_connections.get(user_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)

    async def broadcast_system(self, message: str):
        dead_pairs: List[tuple] = []
        for user_id, connections in self._user_connections.items():
            for ws in connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead_pairs.append((ws, user_id))
        for ws, uid in dead_pairs:
            self.disconnect(ws, uid)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    if not token:
        auth = websocket.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth.split(" ")[1]

    if not token:
        await websocket.close(code=1008)
        return

    try:
        # require=["exp"] rejects tokens minted without an expiry; verify_exp
        # (PyJWT default) rejects already-expired ones. A token with no exp
        # would otherwise be accepted indefinitely at the WS handshake.
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"require": ["exp"], "verify_exp": True},
        )
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)

    # Registry row 70: pnl events are filtered to the user's own profiles.
    # The lifespan-managed TimescaleClient lives on app.state (see deps.py);
    # absent (e.g. bare test app) → repo None → filter fails closed for pnl.
    ts_client = getattr(websocket.app.state, "timescale_client", None)
    profile_repo = ProfileRepository(ts_client) if ts_client is not None else None
    pnl_filter = PnlProfileFilter(user_id, profile_repo)
    await pnl_filter.prime()

    redis_instance = get_redis()
    channels = [
        PUBSUB_PNL_UPDATES,
        PUBSUB_SYSTEM_ALERTS,
        PUBSUB_AGENT_TELEMETRY,
        PUBSUB_HITL_PENDING,
        PUBSUB_ORDERBOOK,
        PUBSUB_TRADES,
        "market_sentiment",
    ]

    async def listen_to_redis():
        """Subscribe to Redis pubsub with automatic reconnection on failure."""
        reconnect_delay = INITIAL_RECONNECT_DELAY

        while True:
            pubsub = redis_instance.pubsub()
            try:
                await pubsub.subscribe(*channels)
                logger.info("Redis pubsub connected", user_id=user_id)
                reconnect_delay = INITIAL_RECONNECT_DELAY  # reset on success

                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=0.1
                    )
                    if message and message.get("type") == "message":
                        channel = message["channel"]
                        channel_str = (
                            channel.decode("utf-8")
                            if isinstance(channel, bytes)
                            else channel
                        )
                        data = _decode_pubsub_payload(message["data"])

                        env = {"channel": channel_str, "data": data}
                        msg_text = json.dumps(env, default=str)

                        if channel_str == PUBSUB_PNL_UPDATES:
                            # Row 70 fix: the old filter keyed on a `user_id`
                            # field that PnlUpdateEvent never carried — a
                            # permanent no-op that broadcast every profile's
                            # pnl to every user. Filter by profile ownership.
                            if not await pnl_filter.should_forward(data):
                                continue

                        try:
                            await websocket.send_text(msg_text)
                        except Exception:
                            logger.info(
                                "WebSocket send failed, stopping listener",
                                user_id=user_id,
                            )
                            return  # WebSocket is dead — exit entirely
                    else:
                        await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                # Clean shutdown — don't reconnect
                return
            except Exception as e:
                logger.warning(
                    "Redis pubsub disconnected, reconnecting",
                    user_id=user_id,
                    error=str(e),
                    retry_in_s=reconnect_delay,
                )
            finally:
                try:
                    await pubsub.unsubscribe(*channels)
                    await pubsub.close()
                except Exception:
                    pass

            # Exponential backoff before reconnect
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY)

    listener = asyncio.create_task(listen_to_redis())

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        listener.cancel()
        try:
            await listener
        except asyncio.CancelledError:
            pass
