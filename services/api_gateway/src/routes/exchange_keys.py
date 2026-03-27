from typing import List
from fastapi import APIRouter, Depends, HTTPException
import json
import ccxt.async_support as ccxt

from libs.core.schemas import ExchangeKeyCreate, ExchangeKeyTest, ExchangeKeyResponse
from libs.core.secrets import SecretManager
from libs.config import settings
from libs.observability import get_logger
from services.api_gateway.src.deps import get_timescale as get_db, get_current_user as require_user

logger = get_logger("exchange-keys")

router = APIRouter()

# Lazy-initialized secret manager
_secret_manager: SecretManager | None = None


def _get_secret_manager() -> SecretManager:
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager(gcp_project_id=settings.GCP_PROJECT_ID)
    return _secret_manager


@router.get("/", response_model=List[ExchangeKeyResponse])
async def list_exchange_keys(
    db=Depends(get_db),
    user_id: str = Depends(require_user)
):
    """List connected exchange keys for the current user."""
    query = """
        SELECT id, exchange_name, label, is_active, created_at
        FROM exchange_keys
        WHERE user_id = $1 AND deleted_at IS NULL
    """
    records = await db.fetch(query, user_id)
    return [
        {
            "id": str(r["id"]),
            "exchange_name": r["exchange_name"],
            "label": r["label"] or r["exchange_name"],
            "is_active": r["is_active"],
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
        "options": {"adjustForTimeDifference": True},
    }

    if data.exchange_id == "binance" and settings.BINANCE_TESTNET:
        exchange_params["options"]["defaultType"] = "spot"
        exchange = exchange_class(exchange_params)
        exchange.set_sandbox_mode(True)
    elif data.exchange_id == "coinbase" and settings.COINBASE_SANDBOX:
        exchange = exchange_class(exchange_params)
        exchange.set_sandbox_mode(True)
    else:
        exchange = exchange_class(exchange_params)

    try:
        await exchange.fetch_balance()

        # Verify withdrawal permissions are NOT enabled — PRAXIS should never have withdrawal access
        # Skip this check on testnet/sandbox — testnet keys always have full permissions
        is_sandbox = (
            (data.exchange_id == "binance" and settings.BINANCE_TESTNET) or
            (data.exchange_id == "coinbase" and settings.COINBASE_SANDBOX)
        )
        if not is_sandbox:
            has_withdraw = False
            try:
                permissions = getattr(exchange, 'has', {})
                if permissions.get('withdraw') or permissions.get('fetchWithdrawals'):
                    has_withdraw = True
            except Exception:
                pass

            if has_withdraw:
                logger.warning(
                    "Exchange key has withdrawal permissions — rejecting for safety",
                    exchange=data.exchange_id,
                )
                raise HTTPException(
                    status_code=422,
                    detail="API key has withdrawal permissions enabled. "
                           "For security, PRAXIS requires keys with ONLY trading and balance read permissions. "
                           "Please create a new API key with withdrawals disabled."
                )

        return {"status": "success", "message": "Connection verified successfully — no withdrawal permissions detected"}
    except HTTPException:
        raise
    except ccxt.AuthenticationError:
        raise HTTPException(status_code=422, detail="Exchange rejected the API key or secret")
    except Exception as e:
        logger.error("Exchange connection test failed", exchange=data.exchange_id, error=str(e))
        raise HTTPException(status_code=400, detail="Connection test failed. Check your credentials and try again.")
    finally:
        await exchange.close()


@router.post("/")
async def save_exchange_key(
    data: ExchangeKeyCreate,
    db=Depends(get_db),
    user_id: str = Depends(require_user)
):
    """Securely store an exchange key in Secret Manager and save reference to DB."""
    payload = {
        "apiKey": data.api_key,
        "secret": data.api_secret,
    }
    if data.passphrase:
        payload["password"] = data.passphrase

    secret_ref = f"usr-{user_id}-{data.exchange_id}-keys"

    try:
        secret_manager = _get_secret_manager()
        await secret_manager.store_secret(secret_ref, json.dumps(payload))
    except Exception as e:
        logger.error("Failed to store exchange secret", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail="Failed to store credentials securely")

    query = """
        INSERT INTO exchange_keys (user_id, exchange_name, gcp_secret_id, label)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, exchange_name, label)
        DO UPDATE SET gcp_secret_id = EXCLUDED.gcp_secret_id, deleted_at = NULL
        RETURNING id
    """
    row = await db.fetchrow(query, user_id, data.exchange_id, secret_ref, data.exchange_id)

    return {"status": "success", "id": str(row["id"]), "message": "Exchange keys securely stored"}


@router.delete("/{key_id}")
async def delete_exchange_key(
    key_id: str,
    db=Depends(get_db),
    user_id: str = Depends(require_user)
):
    """Destroy exchange key from Secret Manager and soft-delete from DB."""
    query = "SELECT gcp_secret_id FROM exchange_keys WHERE id = $1::uuid AND user_id = $2::uuid"
    record = await db.fetchrow(query, key_id, user_id)

    if not record:
        raise HTTPException(status_code=404, detail="Exchange key not found")

    secret_ref = record["gcp_secret_id"]

    try:
        secret_manager = _get_secret_manager()
        await secret_manager.delete_secret(secret_ref)
    except FileNotFoundError:
        pass  # Already deleted locally
    except Exception as e:
        logger.error("Failed to destroy exchange secret", error=str(e), key_id=key_id)
        raise HTTPException(status_code=500, detail="Failed to destroy credentials")

    delete_query = "UPDATE exchange_keys SET deleted_at = NOW() WHERE id = $1::uuid"
    await db.execute(delete_query, key_id)

    return {"status": "success", "message": "Exchange key permanently destroyed"}
