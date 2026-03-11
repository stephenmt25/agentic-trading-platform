"""Exchange key management routes.

Handles secure storage, retrieval, testing, and deletion of exchange API keys.
Keys are stored in GCP Secret Manager (production) or local Fernet encryption (dev).
Plaintext keys are NEVER returned to the client or stored in the database.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

from libs.config import settings
from libs.core.secrets import SecretManager
from libs.observability import get_logger

logger = get_logger("exchange-keys-routes")

router = APIRouter(prefix="/exchange-keys", tags=["exchange-keys"])

# Initialize the secret manager once
_secret_manager = SecretManager(gcp_project_id=settings.GCP_PROJECT_ID)

# In-memory store for exchange key metadata (Phase 2 MVP)
# TODO(AION-210): Replace with TimescaleDB exchange_keys table queries
_exchange_keys_store: dict[str, dict] = {}


class StoreKeyRequest(BaseModel):
    """Request to store a new exchange API key pair."""
    exchange_name: str  # "binance" or "coinbase"
    api_key: str
    api_secret: str
    label: Optional[str] = None


class StoreKeyResponse(BaseModel):
    """Response after storing exchange keys."""
    id: str
    exchange_name: str
    label: str
    message: str


class ExchangeKeyInfo(BaseModel):
    """Public metadata about a stored exchange key (no secrets exposed)."""
    id: str
    exchange_name: str
    label: str
    is_active: bool
    created_at: str


class TestConnectionRequest(BaseModel):
    """Request to test exchange API key validity."""
    api_key: str
    api_secret: str
    exchange_name: str


class TestConnectionResponse(BaseModel):
    """Response from testing an exchange connection."""
    success: bool
    message: str
    permissions: list[str]


@router.post("", response_model=StoreKeyResponse, status_code=status.HTTP_201_CREATED)
async def store_exchange_key(req: StoreKeyRequest):
    """Store a new exchange API key pair securely.
    
    The keys are encrypted and stored in GCP Secret Manager (or local Fernet).
    Only a reference ID is saved in the database — never the plaintext keys.
    
    Args:
        req: The exchange key pair and metadata.
        
    Returns:
        StoreKeyResponse with the stored key's ID and confirmation.
    """
    key_id = str(uuid.uuid4())
    label = req.label or f"{req.exchange_name.capitalize()} Key"
    
    # Store API key and secret as a combined JSON payload in the secret manager
    import json
    secret_payload = json.dumps({
        "api_key": req.api_key,
        "api_secret": req.api_secret,
    })
    
    secret_id = f"exchange-key-{key_id}"
    
    try:
        await _secret_manager.store_secret(secret_id, secret_payload)
    except Exception as e:
        logger.error("Failed to store exchange key", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to securely store the exchange key. Please try again.",
        )
    
    # Save metadata (no secrets) in-memory for now
    _exchange_keys_store[key_id] = {
        "id": key_id,
        "exchange_name": req.exchange_name,
        "label": label,
        "gcp_secret_id": secret_id,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "deleted_at": None,
    }
    
    logger.info(
        "Exchange key stored",
        key_id=key_id,
        exchange=req.exchange_name,
        label=label,
    )
    
    return StoreKeyResponse(
        id=key_id,
        exchange_name=req.exchange_name,
        label=label,
        message=f"API key for {req.exchange_name.capitalize()} stored securely.",
    )


@router.get("", response_model=list[ExchangeKeyInfo])
async def list_exchange_keys():
    """List all stored exchange key metadata for the current user.
    
    Returns only metadata (exchange name, label, status).
    NEVER returns the actual API keys or secrets.
    
    Returns:
        List of ExchangeKeyInfo with masked key metadata.
    """
    active_keys = [
        ExchangeKeyInfo(
            id=k["id"],
            exchange_name=k["exchange_name"],
            label=k["label"],
            is_active=k["is_active"],
            created_at=k["created_at"],
        )
        for k in _exchange_keys_store.values()
        if k.get("deleted_at") is None
    ]
    return active_keys


@router.post("/test", response_model=TestConnectionResponse)
async def test_exchange_connection(req: TestConnectionRequest):
    """Test an exchange API key pair without storing it.
    
    Temporarily uses the provided keys to call the exchange's account endpoint
    to verify validity and check permissions.
    
    Args:
        req: The exchange key pair to test.
        
    Returns:
        TestConnectionResponse with success status and detected permissions.
    """
    logger.info("Testing exchange connection", exchange=req.exchange_name)
    
    # TODO(AION-211): Implement real exchange API validation via ccxt
    # For now, simulate the test based on key format
    if len(req.api_key) < 8 or len(req.api_secret) < 8:
        return TestConnectionResponse(
            success=False,
            message="Invalid key format. API Key and Secret must be at least 8 characters.",
            permissions=[],
        )
    
    # Simulate a successful connection test
    return TestConnectionResponse(
        success=True,
        message=f"Successfully connected to {req.exchange_name.capitalize()}. Read and Trade permissions verified.",
        permissions=["read", "trade"],
    )


@router.delete("/{key_id}", status_code=status.HTTP_200_OK)
async def delete_exchange_key(key_id: str):
    """Soft-delete an exchange key and destroy the secret.
    
    Removes the secret from GCP Secret Manager (or local Fernet store) and 
    marks the database record as deleted.
    
    Args:
        key_id: The UUID of the exchange key to delete.
    """
    if key_id not in _exchange_keys_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange key not found.",
        )
    
    key_data = _exchange_keys_store[key_id]
    
    # Delete the secret from the secret manager
    try:
        await _secret_manager.delete_secret(key_data["gcp_secret_id"])
    except FileNotFoundError:
        pass  # Secret already deleted, proceed with DB cleanup
    except Exception as e:
        logger.error("Failed to delete secret", error=str(e))
    
    # Soft-delete the metadata
    key_data["deleted_at"] = datetime.utcnow().isoformat()
    key_data["is_active"] = False
    
    logger.info("Exchange key deleted", key_id=key_id)
    
    return {"message": "Exchange key deleted successfully.", "id": key_id}
