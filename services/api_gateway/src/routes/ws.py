import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List

import jwt
from libs.config import settings
from libs.observability import get_logger
from ..deps import get_redis

from libs.messaging.channels import PUBSUB_PNL_UPDATES, PUBSUB_SYSTEM_ALERTS

logger = get_logger("ws")

router = APIRouter(tags=["ws"])


class ConnectionManager:
    def __init__(self):
        # Map user_id -> list of WebSocket connections
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
        """Broadcast system-level messages (non-PnL) to all connected users."""
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
    # Authenticate via query param token or header
    if not token:
        auth = websocket.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth.split(" ")[1]

    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)

    # Use raw redis pubsub for multi-channel subscription
    redis_instance = get_redis()
    pubsub = redis_instance.pubsub()
    channels = [PUBSUB_PNL_UPDATES, PUBSUB_SYSTEM_ALERTS, "market_sentiment"]

    async def listen_to_redis():
        try:
            await pubsub.subscribe(*channels)
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if message and message.get("type") == "message":
                    channel = message["channel"]
                    channel_str = channel.decode("utf-8") if isinstance(channel, bytes) else channel
                    data_raw = message["data"]
                    data_str = data_raw.decode("utf-8") if isinstance(data_raw, bytes) else data_raw
                    try:
                        data = json.loads(data_str)
                    except (json.JSONDecodeError, TypeError):
                        data = data_str

                    env = {"channel": channel_str, "data": data}
                    msg_text = json.dumps(env)

                    # PnL updates: only send to the owning user
                    if channel_str == PUBSUB_PNL_UPDATES:
                        msg_user_id = data.get("user_id") if isinstance(data, dict) else None
                        if msg_user_id and msg_user_id != user_id:
                            continue  # Skip PnL data not belonging to this user
                        try:
                            await websocket.send_text(msg_text)
                        except Exception:
                            logger.info("WebSocket send failed, closing listener", user_id=user_id)
                            break
                    else:
                        # System alerts and sentiment: send to this user's connection
                        try:
                            await websocket.send_text(msg_text)
                        except Exception:
                            logger.info("WebSocket send failed, closing listener", user_id=user_id)
                            break
                else:
                    await asyncio.sleep(0.01)
        except Exception as e:
            logger.error("Redis listener error", error=str(e), user_id=user_id)
        finally:
            try:
                await pubsub.unsubscribe(*channels)
                await pubsub.close()
            except Exception:
                pass

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
