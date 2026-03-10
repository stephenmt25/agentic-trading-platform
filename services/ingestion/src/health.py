from fastapi import FastAPI, Response, status
from .ws_manager import WebSocketManager

def create_health_app(ws_manager: WebSocketManager) -> FastAPI:
    app = FastAPI(title="Ingestion Agent Health")

    @app.get("/health")
    async def get_health(response: Response):
        if ws_manager.is_healthy():
            return {"status": "healthy"}
        
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy"}

    @app.get("/ready")
    async def get_ready(response: Response):
        if ws_manager.is_partially_healthy():
            return {"status": "ready"}
            
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready"}
        
    return app
