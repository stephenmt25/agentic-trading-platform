from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import bcrypt
from datetime import timedelta
from libs.config import settings
from ..middleware.auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    # Mocking Authentication for sprint logic
    expected_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
    
    if req.username != "admin" or not bcrypt.checkpw(req.password.encode('utf-8'), expected_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token({"sub": req.username}, timedelta(minutes=60))
    refresh_token = create_access_token({"sub": req.username, "type": "refresh"}, timedelta(days=7))
    
    return LoginResponse(access_token=access_token, refresh_token=refresh_token)
