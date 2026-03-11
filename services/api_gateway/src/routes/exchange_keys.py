from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import json
import ccxt.async_support as ccxt

from libs.core.secrets import SecretManager
from libs.config.settings import Settings
from services.api_gateway.src.dependencies import get_db, require_user

router = APIRouter()
settings = Settings()

# Instantiate secret manager once (uses GCP if GCP_PROJECT_ID is set, else Fernet fallback)
secret_manager = SecretManager(gcp_project_id=settings.GCP_PROJECT_ID)

class ExchangeKeyCreate(BaseModel):
    exchange_id: str
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None

class ExchangeKeyTest(ExchangeKeyCreate):
    pass

class ExchangeKeyResponse(BaseModel):
    id: str
    exchange_id: str
    created_at: str

@router.get("/", response_model=List[ExchangeKeyResponse])
async def list_exchange_keys(
    db=Depends(get_db), 
    user_id: str = Depends(require_user)
):
    """List connected exchange keys for the current user."""
    query = """
        SELECT id, exchange_id, created_at 
        FROM exchange_keys 
        WHERE user_id = $1 AND deleted_at IS NULL
    """
    records = await db.fetch(query, user_id)
    return [
        {
            "id": str(r["id"]),
            "exchange_id": r["exchange_id"],
            "created_at": str(r["created_at"])
        }
        for r in records
    ]

@router.post("/test")
async def test_exchange_connection(data: ExchangeKeyTest):
    """Test API keys with CCXT before saving them."""
    if not hasattr(ccxt, data.exchange_id):
        raise HTTPException(status_code=400, detail=f"Exchange '{data.exchange_id}' not supported")
        
    exchange_class = getattr(ccxt, data.exchange_id)
    exchange_params = {
        "apiKey": data.api_key,
        "secret": data.api_secret,
        "enableRateLimit": True,
    }
    
    # Binance testnet adjustment
    if data.exchange_id == "binance" and settings.BINANCE_TESTNET:
        exchange_params["options"] = {"defaultType": "future"}
        exchange = exchange_class(exchange_params)
        exchange.set_sandbox_mode(True)
    elif data.exchange_id == "coinbase" and settings.COINBASE_SANDBOX:
        exchange = exchange_class(exchange_params)
        exchange.set_sandbox_mode(True)
    else:
        exchange = exchange_class(exchange_params)

    try:
        # Check authentication by fetching balances
        await exchange.fetch_balance()
        return {"status": "success", "message": "Connection verified successfully"}
    except ccxt.AuthenticationError as e:
        raise HTTPException(status_code=401, detail="Invalid API key or secret")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection test failed: {str(e)}")
    finally:
        await exchange.close()

@router.post("/")
async def save_exchange_key(
    data: ExchangeKeyCreate, 
    db=Depends(get_db), 
    user_id: str = Depends(require_user)
):
    """Securely store an exchange key in Secret Manager and save reference to DB."""
    # 1. Package the payload
    payload = {
        "apiKey": data.api_key,
        "secret": data.api_secret,
    }
    if data.passphrase:
        payload["password"] = data.passphrase
        
    # 2. Generate a unique secret reference ID
    secret_ref = f"usr-{user_id}-{data.exchange_id}-keys"
    
    # 3. Store securely in GCP Secret Manager (or local Fernet)
    try:
        await secret_manager.store_secret(secret_ref, json.dumps(payload))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store secret securely: {str(e)}")
        
    # 4. Insert or update the database tracking row
    query = """
        INSERT INTO exchange_keys (user_id, exchange_id, key_ref)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, exchange_id) 
        DO UPDATE SET key_ref = EXCLUDED.key_ref, deleted_at = NULL, updated_at = NOW()
        RETURNING id
    """
    row = await db.fetchrow(query, user_id, data.exchange_id, secret_ref)
    
    return {"status": "success", "id": str(row["id"]), "message": "Exchange keys securely stored"}

@router.delete("/{key_id}")
async def delete_exchange_key(
    key_id: str, 
    db=Depends(get_db), 
    user_id: str = Depends(require_user)
):
    """Destroy exchange key from Secret Manager and soft-delete from DB."""
    # Verify ownership
    query = "SELECT key_ref FROM exchange_keys WHERE id = $1 AND user_id = $2"
    record = await db.fetchrow(query, key_id, user_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="Exchange key not found")
        
    secret_ref = record["key_ref"]
    
    # 1. Destroy the actual secret payload
    try:
        await secret_manager.delete_secret(secret_ref)
    except Exception as e:
        # Ignore if file not found locally
        if not isinstance(e, FileNotFoundError):
            raise HTTPException(status_code=500, detail=f"Failed to destroy secret: {str(e)}")
            
    # 2. Soft-delete the database tracking row
    delete_query = "UPDATE exchange_keys SET deleted_at = NOW(), updated_at = NOW() WHERE id = $1"
    await db.execute(delete_query, key_id)
    
    return {"status": "success", "message": "Exchange key permanently destroyed"}
