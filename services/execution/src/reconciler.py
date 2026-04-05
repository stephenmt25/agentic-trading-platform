import asyncio
import json
from collections import defaultdict
from decimal import Decimal
from datetime import datetime
from libs.exchange import get_adapter
from libs.core.secrets import SecretManager
from libs.core.schemas import AlertEvent
from libs.core.enums import EventType
from libs.messaging.channels import PUBSUB_SYSTEM_ALERTS
from libs.storage.repositories import PositionRepository, ProfileRepository
from libs.config import settings
from libs.observability import get_logger

logger = get_logger("execution.reconciler")


class BalanceReconciler:
    def __init__(self, position_repo: PositionRepository, profile_repo: ProfileRepository = None,
                 pubsub=None, secret_manager: SecretManager = None):
        self._position_repo = position_repo
        self._profile_repo = profile_repo
        self._pubsub = pubsub
        self._secret_manager = secret_manager or SecretManager(gcp_project_id=settings.GCP_PROJECT_ID)

    async def run_cron(self, interval_seconds: int = 300):
        """Runs every 5 minutes comparing exchange balances against DB ledger for drift > 0.1%"""
        logger.info("Starting BalanceReconciler 5-min cron")

        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await self._reconcile_all_profiles()
            except Exception as e:
                logger.error("Reconciler encountered error", error=str(e))

    async def _reconcile_all_profiles(self):
        """Iterate over active profiles and reconcile each against its exchange."""
        if not self._profile_repo:
            logger.warning("No profile_repo configured, skipping reconciliation")
            return

        profiles = await self._profile_repo.get_active_profiles()
        for profile in profiles:
            profile_id = str(profile.get("profile_id", ""))
            key_ref = profile.get("exchange_key_ref", "paper")
            if not profile_id or key_ref == "paper":
                continue

            try:
                await self._reconcile_profile(profile_id, key_ref)
            except Exception as e:
                logger.error("Reconciliation failed for profile", profile_id=profile_id, error=str(e))

    async def _reconcile_profile(self, profile_id: str, key_ref: str):
        """Compare exchange positions with DB positions for a single profile."""
        # Resolve exchange adapter
        exchange_name = "BINANCE"
        parts = key_ref.split("-")
        if len(parts) >= 3:
            exchange_name = parts[-2].upper()

        api_key = ""
        api_secret = ""
        try:
            creds_json = await self._secret_manager.get_secret(key_ref)
            creds = json.loads(creds_json)
            api_key = creds.get("apiKey", "")
            api_secret = creds.get("secret", "")
        except FileNotFoundError:
            logger.warning("Exchange keys not found for reconciliation", profile_id=profile_id)
            return

        testnet = settings.BINANCE_TESTNET if exchange_name == "BINANCE" else settings.COINBASE_SANDBOX
        adapter = get_adapter(exchange_name, api_key=api_key, secret=api_secret, testnet=testnet)

        try:
            # 1. Fetch balances from exchange
            exchange_balances = await adapter.get_balance(profile_id)
            # Normalize to {currency: total_amount} -- CCXT balance format
            exchange_totals: dict[str, Decimal] = {}
            if isinstance(exchange_balances, dict):
                for currency, info in exchange_balances.items():
                    if isinstance(info, dict) and "total" in info:
                        total = Decimal(str(info["total"] or 0))
                        if total > 0:
                            exchange_totals[currency] = total

            # 2. Fetch open positions from DB and aggregate by base currency
            open_positions = await self._position_repo.get_open_positions(profile_id)
            db_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
            for pos in open_positions:
                pos_dict = dict(pos) if not isinstance(pos, dict) else pos
                symbol = pos_dict.get("symbol", "")
                qty = Decimal(str(pos_dict.get("quantity", 0)))
                base = symbol.split("/")[0] if "/" in symbol else symbol
                side = pos_dict.get("side", "BUY")
                if side == "BUY":
                    db_totals[base] += qty
                else:
                    db_totals[base] -= qty

            # 3. Calculate drift for each currency with positions
            _ZERO = Decimal("0")
            _EPSILON = Decimal("1E-10")
            max_drift = _ZERO
            drift_details = {}
            for currency, db_qty in db_totals.items():
                exchange_qty = exchange_totals.get(currency, _ZERO)
                if abs(db_qty) < _EPSILON:
                    continue
                drift = abs(exchange_qty - db_qty) / abs(db_qty)
                drift_details[currency] = {"db": str(db_qty), "exchange": str(exchange_qty), "drift_pct": str(drift)}
                max_drift = max(max_drift, drift)

            # 4. Alert if drift exceeds threshold
            if max_drift > Decimal("0.001"):  # > 0.1%
                logger.critical(
                    "RECONCILIATION_DRIFT_ERROR: Variance > 0.1%",
                    profile_id=profile_id,
                    drift=max_drift,
                    details=drift_details,
                )
                # Publish system alert for trading halt consideration
                if self._pubsub:
                    alert = AlertEvent(
                        event_type=EventType.ALERT_RED,
                        timestamp_us=int(datetime.utcnow().timestamp() * 1_000_000),
                        source_service="reconciler",
                        message=f"Reconciliation drift {float(max_drift)*100:.2f}% for {profile_id}",
                        level="RED",
                        profile_id=profile_id,
                    )
                    await self._pubsub.publish(PUBSUB_SYSTEM_ALERTS, alert)
            else:
                logger.info("Reconciliation passed", profile_id=profile_id, max_drift=float(max_drift))
        finally:
            await adapter.close()
