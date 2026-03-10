from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import asyncio
import json
import jwt
from libs.config import settings
from ..deps import get_redis
from libs.messaging import PubSubBroadcaster
from libs.messaging.channels import PUBSUB_PNL_UPDATES, PUBSUB_SYSTEM_ALERTS

router = APIRouter(tags=["ws"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    # Authenticate via query param token or header
    if not token:
        # Fallback to headers if supported client
        auth = websocket.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth.split(" ")[1]
            
    if not token:
        await websocket.close(code=1008)
        return
        
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=1008)
        return
        
    await manager.connect(websocket)
    redis_instance = get_redis()
    pubsub = PubSubBroadcaster(redis_instance)
    
    # We spawn a background listening task for this user
    # Subscribing to PnL Updates and Alerts
    async def listen_to_redis():
        async for channel, message in pubsub.subscribe(PUBSUB_PNL_UPDATES, PUBSUB_SYSTEM_ALERTS, "market_sentiment"):
            # Envelope before sending
            env = {
                "channel": channel.decode('utf-8') if isinstance(channel, bytes) else channel,
                "data": message
            }
            try:
                await websocket.send_text(json.dumps(env))
            except Exception:
                break
                
    listener = asyncio.create_task(listen_to_redis())
    
    try:
        while True:
            # Heartbeats implementation maintaining connection liveness
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        listener.cancel()
