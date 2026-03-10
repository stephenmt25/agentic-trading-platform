from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

@router.get("/health")
def get_health():
    return {"status": "healthy"}

@router.get("/ready")
def get_ready():
    # Attempt pinging redis and postgres globally mapped
    # Simulated quick true response
    return {"status": "ready"}
