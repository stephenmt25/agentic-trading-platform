import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from libs.config import settings
from libs.core.agent_registry import AgentPerformanceTracker
from libs.core.enums import OrderSide, OrderStatus, PositionStatus
from libs.core.models import Order, Position
from libs.core.schemas import (
    AgentScorePayload,
    OrderApprovedEvent,
    OrderExecutedEvent,
    OrderRejectedEvent,
    RiskLimitsPayload,
)
from libs.core.secrets import SecretManager
from libs.exchange import get_adapter
from libs.messaging import StreamConsumer, StreamPublisher
from libs.messaging.channels import ORDERS_STREAM_MAXLEN
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher
from libs.storage.repositories import (
    AuditRepository,
    OrderRepository,
    PositionRepository,
    ProfileRepository,
)

from .ledger import OptimisticLedger

logger = get_logger("execution.executor")

# Exchange-specific taker fee rates
EXCHANGE_FEE_RATES = {
    "BINANCE": Decimal("0.001"),  # 0.10%
    "COINBASE": Decimal("0.006"),  # 0.60%
    "PAPER": Decimal(
        "0.001"
    ),  # 0.10% (matches Binance testnet for realistic simulation)
}
DEFAULT_FEE_RATE = Decimal("0.002")  # 0.20% conservative fallback

# Orders older than this are skipped on consume. Mirrors the stale-tick
# guard in services/hot_path/src/processor.py: a backlog of orders left
# behind in stream:orders from a previous session (e.g. a pyramid race
# that emitted hundreds of orders before being stopped) must not be
# drained on boot — the hot_path gates that approved them are stateful
# and don't apply to a stream replay. Cap matches MAX_TICK_AGE_S in
# processor.py at 60 s.
MAX_ORDER_AGE_S = 60.0


class OrderExecutor:
    def __init__(
        self,
        publisher: StreamPublisher,
        consumer: StreamConsumer,
        order_repo: OrderRepository,
        position_repo: PositionRepository,
        audit_repo: AuditRepository,
        ledger: OptimisticLedger,
        orders_channel: str,
        profile_repo: ProfileRepository = None,
        secret_manager: SecretManager = None,
        redis_client=None,
        telemetry: TelemetryPublisher = None,
    ):
        self._publisher = publisher
        self._consumer = consumer
        self._order_repo = order_repo
        self._position_repo = position_repo
        self._audit_repo = audit_repo
        self._ledger = ledger
        self._channel = orders_channel
        self._profile_repo = profile_repo
        self._secret_manager = secret_manager or SecretManager(
            gcp_project_id=settings.GCP_PROJECT_ID
        )
        self._redis_client = redis_client
        self._telemetry = telemetry

    async def _resolve_adapter(self, profile_id: str):
        """Load the user's exchange keys from SecretManager and return the correct adapter."""
        # Paper trading mode — bypass all exchange credential logic
        if settings.PAPER_TRADING_MODE:
            logger.info("paper_mode_active", profile_id=profile_id)
            return get_adapter("PAPER"), "PAPER"

        exchange_name = "BINANCE"  # default
        api_key = ""
        api_secret = ""
        testnet = settings.BINANCE_TESTNET

        if self._profile_repo:
            try:
                profile = await self._profile_repo.get_profile(profile_id)
                if profile:
                    key_ref = profile.get("exchange_key_ref", "paper")
                    if key_ref and key_ref != "paper":
                        # Derive exchange name from the key_ref convention: usr-{uid}-{exchange}-keys
                        parts = key_ref.split("-")
                        if len(parts) >= 3:
                            exchange_name = parts[-2].upper()
                        try:
                            creds_json = await self._secret_manager.get_secret(key_ref)
                            creds = json.loads(creds_json)
                            api_key = creds.get("apiKey", "")
                            api_secret = creds.get("secret", "")
                        except FileNotFoundError:
                            logger.warning(
                                "Exchange keys not found, falling back to testnet",
                                profile_id=profile_id,
                            )
                        except Exception as e:
                            logger.error(
                                "Failed to load exchange keys",
                                error=str(e),
                                profile_id=profile_id,
                            )
            except Exception as e:
                logger.error(
                    "Failed to load profile for adapter resolution", error=str(e)
                )

        if exchange_name == "COINBASE":
            testnet = settings.COINBASE_SANDBOX

        return (
            get_adapter(
                exchange_name, api_key=api_key, secret=api_secret, testnet=testnet
            ),
            exchange_name,
        )

    async def _record_agent_scores(self, symbol: str, position_id: str, side: str):
        """Snapshot current agent scores + regime from Redis and record for weight feedback.

        Stored payload shape: {"agents": {...}, "regime": "..."}.
        Older positions (pre-PR1) stored just the agents dict at the top level;
        PositionCloser._get_position_snapshot handles both shapes.
        """
        try:
            pipe = self._redis_client.pipeline(transaction=False)
            pipe.get(f"agent:ta_score:{symbol}")
            pipe.get(f"agent:sentiment:{symbol}")
            pipe.get(f"agent:debate:{symbol}")
            pipe.get(f"regime:{symbol}")
            ta_raw, sent_raw, debate_raw, regime_raw = await pipe.execute()

            agents = {}
            direction = side if isinstance(side, str) else side.value

            # Defence in depth: even though sentiment/debate now skip the
            # Redis write on LLM failure (services/sentiment/src/main.py and
            # services/debate/src/main.py), we still filter here so a
            # regression upstream can't poison the meta-learning loop.
            _DEGRADED_SOURCES = {"llm_error", "fallback"}

            if ta_raw:
                data = AgentScorePayload.model_validate_json(ta_raw)
                agents["ta"] = {
                    "direction": direction,
                    "score": float(data.score),
                }  # float-ok: ML score
            if sent_raw:
                data = AgentScorePayload.model_validate_json(sent_raw)
                if data.source not in _DEGRADED_SOURCES:
                    agents["sentiment"] = {
                        "direction": direction,
                        "score": float(data.score),
                    }  # float-ok: ML score
            if debate_raw:
                data = AgentScorePayload.model_validate_json(debate_raw)
                if data.source not in _DEGRADED_SOURCES:
                    agents["debate"] = {
                        "direction": direction,
                        "score": float(data.score),
                    }  # float-ok: ML score

            regime = None
            if regime_raw:
                regime = (
                    regime_raw.decode()
                    if isinstance(regime_raw, bytes)
                    else str(regime_raw)
                )

            if agents:
                tracker = AgentPerformanceTracker(self._redis_client)
                await tracker.record_agent_scores(symbol, agents)

                # Cache snapshot for this position (used on close to populate closed_trades)
                await self._redis_client.set(
                    f"agent:position_scores:{position_id}",
                    json.dumps({"agents": agents, "regime": regime}),
                    ex=86400 * 7,  # 7 day TTL
                )
        except Exception as e:
            logger.warning("Failed to record agent scores", error=str(e), symbol=symbol)

    async def _protective_stop_pct(self, profile_id: str) -> Optional[Decimal]:
        """Read the profile's configured stop_loss_pct (Decimal) for the
        protective stop. Returns None when unavailable / not explicitly set."""
        if self._profile_repo is None:
            return None
        try:
            profile = await self._profile_repo.get_profile(profile_id)
            if not profile:
                return None
            raw = profile.get("risk_limits", "{}")
            if isinstance(raw, str):
                raw = json.loads(raw) if raw else {}
            if not isinstance(raw, dict) or "stop_loss_pct" not in raw:
                return None
            rl = RiskLimitsPayload.model_validate(raw)
            return Decimal(str(rl.stop_loss_pct)) if rl.stop_loss_pct else None
        except Exception as e:
            logger.warning(
                "protective_stop_pct_lookup_failed", error=str(e), profile_id=profile_id
            )
            return None

    async def _maybe_place_protective_stop(
        self, adapter, position: Position, fill_price: Decimal, exchange_name: str
    ):
        """Best-effort exchange-resident reduce-only stop placed at open. Any
        failure is logged and swallowed — the software stop (ExitMonitor) remains
        the primary protection, so this must never roll back or block an open.
        Gated by the caller on settings.PROTECTIVE_STOP_ENABLED."""
        try:
            stop_pct = await self._protective_stop_pct(str(position.profile_id))
            if stop_pct is None or stop_pct <= Decimal("0"):
                return
            # Closing side is opposite the position; stop sits beyond entry on
            # the loss side (below for a long, above for a short).
            if position.side == OrderSide.BUY:
                close_side = OrderSide.SELL
                stop_price = fill_price * (Decimal("1") - stop_pct)
            else:
                close_side = OrderSide.BUY
                stop_price = fill_price * (Decimal("1") + stop_pct)
            res = await adapter.place_protective_order(
                position.profile_id,
                position.symbol,
                close_side,
                position.quantity,
                stop_price,
            )
            if res is not None and getattr(res, "order_id", None):
                await self._position_repo.set_protective_order_id(
                    position.position_id, str(res.order_id)
                )
                logger.info(
                    "protective_stop_placed",
                    position_id=str(position.position_id),
                    stop_price=str(stop_price),
                    order_id=str(res.order_id),
                )
        except Exception as e:
            logger.warning(
                "protective_stop_failed", error=str(e), symbol=position.symbol
            )

    def __post_init_supervisor__(self):
        # Updated every consume cycle. main.py's stall watchdog reads this to
        # detect a hung consume loop (a stuck await stops it advancing).
        if not hasattr(self, "last_progress_mono"):
            self.last_progress_mono = time.monotonic()

    async def run(self):
        """Supervisor: keep the consume/process loop alive across transient
        failures. An unhandled exception inside _run_loop — e.g. a Redis
        TimeoutError when the server briefly stalls — would otherwise end the
        executor task and kill order processing silently while leaving the
        FastAPI process alive (and the 5-min reconciler cron still ticking),
        making the failure invisible. Mirrors HotPathProcessor.run() in
        services/hot_path/src/processor.py."""
        self.__post_init_supervisor__()
        while True:
            try:
                await self._run_loop()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("executor loop crashed — restarting", error=str(exc))
                await asyncio.sleep(1)

    async def _run_loop(self):
        logger.info("OrderExecutor starting loop")

        while True:
            # Marks the loop as iterating — the stall watchdog reads this.
            self.last_progress_mono = time.monotonic()

            # A transient Redis hiccup — e.g. the server briefly unresponsive
            # while it replays its AOF at boot — raises here. Catch it: log,
            # back off, and retry the loop, rather than killing the executor
            # task silently and wedging order processing.
            try:
                events = await self._consumer.consume(
                    self._channel, "executor_group", "executor_1", count=10
                )
            except Exception as exc:
                logger.error("consume failed — retrying", error=str(exc))
                await asyncio.sleep(1)
                continue

            for msg_id, ev in events:
                if not ev or not isinstance(ev, OrderApprovedEvent):
                    continue

                # Stale-order guard. The batch ack at the end of the loop
                # covers this msg_id, so a `continue` here drops the order
                # quietly and permanently. See MAX_ORDER_AGE_S comment.
                order_age_s = (time.time() * 1_000_000 - ev.timestamp_us) / 1_000_000
                if order_age_s > MAX_ORDER_AGE_S:
                    logger.warning(
                        "stale_order_skipped",
                        order_age_s=round(order_age_s, 1),
                        profile_id=str(ev.profile_id),
                        symbol=ev.symbol,
                    )
                    continue

                # A reduce-only CLOSE is exempt from the trading-enabled gate: a
                # close reduces risk and must never be blocked from flattening a
                # live position. Only opening orders are gated.
                if not settings.TRADING_ENABLED and not ev.reduce_only:
                    logger.warning(
                        "TRADING_ENABLED=false, rejecting order",
                        profile_id=str(ev.profile_id),
                        symbol=ev.symbol,
                    )
                    fail_ev = OrderRejectedEvent(
                        profile_id=ev.profile_id,
                        symbol=ev.symbol,
                        reason="Trading disabled (TRADING_ENABLED=false)",
                        timestamp_us=int(
                            datetime.now(timezone.utc).timestamp() * 1000000
                        ),
                        source_service="execution",
                    )
                    await self._publisher.publish(
                        self._channel, fail_ev, maxlen=ORDERS_STREAM_MAXLEN
                    )
                    continue

                if self._telemetry:
                    await self._telemetry.emit(
                        "input_received",
                        {
                            "symbol": ev.symbol,
                            "side": str(ev.side),
                            "message_type": "order_approved",
                        },
                        source_agent="hot_path",
                    )

                # Honor a pre-allocated order_id from the api_gateway (manual /orders
                # submission) so the HTTP response and the persisted Order row share
                # the same id. Strategy/validation publishers leave it None.
                order_id = ev.order_id if ev.order_id else uuid.uuid4()

                # 1. Resolve exchange adapter using profile's stored keys
                adapter, exchange_name = await self._resolve_adapter(str(ev.profile_id))
                fee_rate = EXCHANGE_FEE_RATES.get(exchange_name, DEFAULT_FEE_RATE)

                # 2. Write to orders table optimistically
                order = Order(
                    order_id=order_id,
                    profile_id=ev.profile_id,
                    symbol=ev.symbol,
                    side=ev.side,
                    quantity=ev.quantity,
                    price=ev.price,
                    status=OrderStatus.PENDING,
                    exchange=exchange_name,
                    created_at=datetime.now(timezone.utc),
                    decision_event_id=ev.decision_event_id,
                    reduce_only=ev.reduce_only,
                )

                await self._order_repo.create_order(order)

                # 3. Optimistic ledger submit — check result
                submitted = await self._ledger.submit(order_id)
                if not submitted:
                    logger.error(
                        "Ledger submit failed, skipping order", order_id=str(order_id)
                    )
                    await self._audit_repo.write_audit_event(
                        ev, {"action": "SUBMIT_FAILED", "order_id": str(order_id)}
                    )
                    continue

                await self._audit_repo.write_audit_event(
                    ev, {"action": "Optimistic SUBMITTED", "order_id": str(order_id)}
                )

                # Telemetry: order placed
                if self._telemetry:
                    await self._telemetry.emit(
                        "output_emitted",
                        {
                            "order_id": str(order_id),
                            "status": "SUBMITTED",
                            "symbol": ev.symbol,
                        },
                    )

                try:
                    # 4. Execute on exchange. reduce_only flags a position-close
                    # (flatten) order — see OrderApprovedEvent / PositionCloseRequester.
                    res = await adapter.place_order(
                        ev.profile_id,
                        ev.symbol,
                        ev.side,
                        ev.quantity,
                        ev.price,
                        reduce_only=ev.reduce_only,
                    )

                    if (
                        res.status == OrderStatus.SUBMITTED
                        or res.status == OrderStatus.CONFIRMED
                    ):
                        fill_price = res.fill_price if res.fill_price else ev.price

                        # 5. Confirm in ledger — check result. For a reduce-only
                        # CLOSE we deliberately skip the allocation increment (no
                        # profile_id/quantity passed): a close REDUCES exposure, so
                        # adding its quantity to allocated_qty would be wrong.
                        # (Decrement-on-close is a separate follow-up.)
                        if ev.reduce_only:
                            confirmed = await self._ledger.confirm(
                                order_id, fill_price=fill_price
                            )
                        else:
                            confirmed = await self._ledger.confirm(
                                order_id,
                                fill_price=fill_price,
                                profile_id=str(ev.profile_id),
                                quantity=ev.quantity,
                            )
                        if not confirmed:
                            logger.error(
                                "Ledger confirm failed after exchange success",
                                order_id=str(order_id),
                            )
                            await self._ledger.rollback(
                                order_id, reason="Ledger confirm failed post-exchange"
                            )
                            raise ValueError(
                                "Ledger confirmation failed after exchange accepted order"
                            )

                        if not ev.reduce_only:
                            # 6. OPEN: create the Position immediately after
                            # confirmation and snapshot agent scores (unchanged).
                            pos_id = uuid.uuid4()
                            entry_fee = fee_rate * ev.quantity * fill_price
                            pos = Position(
                                position_id=pos_id,
                                profile_id=ev.profile_id,
                                symbol=ev.symbol,
                                side=ev.side,
                                entry_price=fill_price,
                                quantity=ev.quantity,
                                entry_fee=entry_fee,
                                opened_at=datetime.now(timezone.utc),
                                status=PositionStatus.OPEN,
                                order_id=order_id,
                                decision_event_id=ev.decision_event_id,
                            )
                            await self._position_repo.create_position(pos)

                            # 6b. Snapshot agent scores at execution for weight feedback
                            if self._redis_client:
                                await self._record_agent_scores(
                                    ev.symbol, str(pos_id), ev.side
                                )

                            # 6c. Optional exchange-resident protective stop
                            # (defense-in-depth; default off). Best-effort — a
                            # failure here must never affect the open.
                            if settings.PROTECTIVE_STOP_ENABLED:
                                await self._maybe_place_protective_stop(
                                    adapter, pos, fill_price, exchange_name
                                )
                        # else CLOSE: do NOT create a Position row — the pnl close
                        # consumer finalises the DB close on the executed event below,
                        # using the real exchange fill_price as the exit price.

                        # 7. Emit executed event. reduce_only + close_position_id are
                        # echoed so the pnl close consumer can correlate the fill to
                        # the position being closed.
                        executed_ev = OrderExecutedEvent(
                            order_id=order_id,
                            profile_id=ev.profile_id,
                            symbol=ev.symbol,
                            side=ev.side,
                            fill_price=fill_price,
                            quantity=ev.quantity,
                            reduce_only=ev.reduce_only,
                            close_position_id=ev.close_position_id,
                            close_reason=ev.close_reason,
                            timestamp_us=int(
                                datetime.now(timezone.utc).timestamp() * 1000000
                            ),
                            source_service="execution",
                        )
                        await self._publisher.publish(
                            self._channel, executed_ev, maxlen=ORDERS_STREAM_MAXLEN
                        )

                        # Telemetry: order filled
                        if self._telemetry:
                            await self._telemetry.emit(
                                "output_emitted",
                                {
                                    "order_id": str(order_id),
                                    "fill_price": str(fill_price),
                                    "symbol": ev.symbol,
                                },
                            )

                    else:
                        raise ValueError(
                            f"Exchange returned unexpected status: {res.status}"
                        )

                except Exception as e:
                    rolled_back = await self._ledger.rollback(order_id, reason=str(e))
                    if not rolled_back:
                        logger.critical(
                            "Ledger rollback ALSO failed — manual intervention required",
                            order_id=str(order_id),
                            error=str(e),
                        )
                    await self._audit_repo.write_audit_event(
                        ev,
                        {
                            "action": "ROLLED_BACK",
                            "reason": str(e),
                            "order_id": str(order_id),
                        },
                    )

                    fail_ev = OrderRejectedEvent(
                        profile_id=ev.profile_id,
                        symbol=ev.symbol,
                        reason=f"Execution Failed: {e}",
                        order_id=order_id,
                        reduce_only=ev.reduce_only,
                        close_position_id=ev.close_position_id,
                        timestamp_us=int(
                            datetime.now(timezone.utc).timestamp() * 1000000
                        ),
                        source_service="execution",
                    )
                    await self._publisher.publish(
                        self._channel, fail_ev, maxlen=ORDERS_STREAM_MAXLEN
                    )
                finally:
                    # Close adapter to free resources (each order gets its own adapter)
                    try:
                        await adapter.close()
                    except Exception:
                        pass

            if events:
                await self._consumer.ack(
                    self._channel, "executor_group", [m for m, _ in events]
                )
