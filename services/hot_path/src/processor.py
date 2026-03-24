import asyncio
from typing import Dict, List, Any
from .state import ProfileStateCache
from .strategy_eval import StrategyEvaluator, SignalResult, EvaluatedIndicators
from .abstention import AbstentionChecker
from .regime_dampener import RegimeDampener
from .agent_modifier import AgentModifier
from .circuit_breaker import CircuitBreaker
from .blacklist import BlacklistChecker
from .risk_gate import RiskGate
from .hitl_gate import HITLGate
from .validation_client import ValidationClient

from libs.core.enums import SignalDirection, EventType, ValidationCheck, ValidationVerdict, ValidationMode
from libs.core.models import NormalisedTick
from libs.core.schemas import MarketTickEvent, OrderApprovedEvent, ThresholdProximityEvent, ValidationRequestEvent
from libs.core.constants import THRESHOLD_PROXIMITY_BAND_PCT
from libs.messaging import StreamConsumer, StreamPublisher, PubSubBroadcaster
from libs.observability import get_logger, timer, MetricsCollector

logger = get_logger("hot-path.processor")

class HotPathProcessor:
    def __init__(
        self,
        state_cache: ProfileStateCache,
        consumer: StreamConsumer,
        publisher: StreamPublisher,
        pubsub: PubSubBroadcaster,
        validation_client: ValidationClient,
        tick_channel: str,
        orders_channel: str,
        proximity_pubsub_channel: str,
        redis_client=None,
    ):
        self._state_cache = state_cache
        self._consumer = consumer
        self._publisher = publisher
        self._pubsub = pubsub
        self._validation_client = validation_client
        self._tick_channel = tick_channel
        self._orders_channel = orders_channel
        self._proximity_pubsub_channel = proximity_pubsub_channel

        # Sprint 9.4: Dual-regime dampener with Redis + pubsub
        self._regime_dampener = RegimeDampener(redis_client=redis_client, pubsub=pubsub)

        # Sprint 9.5: Agent modifier for TA + sentiment scores
        self._agent_modifier = AgentModifier(redis_client) if redis_client else None

        # Phase 3: HITL execution gate
        self._hitl_gate = HITLGate(redis_client, pubsub) if redis_client else None

    async def run(self):
        logger.info("HotPath Processor started consuming loop.")
        group_name = "hotpath_engine"

        while True:
            # Consume 100 max per heartbeat
            events = await self._consumer.consume(self._tick_channel, group_name, "processor_1", count=100, block_ms=50)

            message_ids_to_ack = []

            for msg_id, event in events:
                if not event or not isinstance(event, MarketTickEvent):
                    message_ids_to_ack.append(msg_id)
                    continue

                tick = NormalisedTick(
                    symbol=event.symbol,
                    exchange=event.exchange,
                    timestamp=event.timestamp_us,
                    price=event.price,
                    volume=event.volume,
                )

                with timer("hot_path.tick_processing"):
                    # For each profile caching
                    for profile_state in self._state_cache.itervalues():
                        if not profile_state.is_active:
                            continue

                        # 1. Strategy Eval
                        sig_res, inds = StrategyEvaluator.evaluate(profile_state, tick)

                        # 1b. Proximity check for pre-fetching
                        if not sig_res:
                            if 30 <= inds.rsi <= 30 * (1 + THRESHOLD_PROXIMITY_BAND_PCT):
                                prox_event = ThresholdProximityEvent(
                                    profile_id=profile_state.profile_id,
                                    symbol=tick.symbol,
                                    indicator_name="rsi",
                                    current_value=inds.rsi,
                                    trigger_threshold=30.0,
                                    proximity_pct=abs(inds.rsi - 30.0) / 30.0,
                                    timestamp_us=tick.timestamp,
                                    source_service="hot-path"
                                )
                                await self._pubsub.publish(self._proximity_pubsub_channel, prox_event)
                            continue

                        # 2. Abstention
                        if AbstentionChecker.check(profile_state, sig_res, tick, inds):
                            continue

                        # 3. Regime Dampener (now async with dual-regime support)
                        damp_res = await self._regime_dampener.check(profile_state, sig_res, tick, inds)
                        if not damp_res.proceed:
                            continue

                        # Apply confidence multiplier
                        sig_res = SignalResult(
                            direction=sig_res.direction,
                            confidence=sig_res.confidence * damp_res.confidence_multiplier,
                            rule_matched=sig_res.rule_matched
                        )

                        # 3b. Agent Modifier (TA + sentiment scores)
                        if self._agent_modifier:
                            sig_res = await self._agent_modifier.apply(tick.symbol, sig_res)

                        # 4. Circuit Breaker
                        if CircuitBreaker.check(profile_state):
                            continue

                        # 5. Blacklist
                        if BlacklistChecker.check(profile_state, tick.symbol):
                            continue

                        # 6. Risk Gate (now returns RiskGateResult with dynamic sizing)
                        risk_result = RiskGate.check(profile_state, sig_res, tick)
                        if risk_result.blocked:
                            continue

                        # 6b. HITL Gate (between risk_gate and validation)
                        if self._hitl_gate:
                            hitl_result = await self._hitl_gate.check(
                                profile_state, sig_res, tick, inds, risk_result,
                            )
                            if hitl_result.blocked:
                                logger.info(f"HITL blocked trade for {profile_state.profile_id} - {hitl_result.reason}")
                                continue

                        # 7. Validation Fast Gate
                        val_req = ValidationRequestEvent(
                            profile_id=profile_state.profile_id,
                            symbol=tick.symbol,
                            check_type=ValidationCheck.CHECK_1_STRATEGY,
                            payload={"confidence": sig_res.confidence, "inds": {
                                "rsi": inds.rsi, "macd": inds.macd_line, "atr": inds.atr
                            }},
                            timestamp_us=tick.timestamp,
                            source_service="hot-path"
                        )

                        val_resp = await self._validation_client.fast_gate(val_req)
                        if val_resp and val_resp.verdict == ValidationVerdict.RED:
                            logger.info(f"Validation blocked trade for {profile_state.profile_id} - {val_resp.reason}")
                            continue

                        # 8. Emit Order Approved (using dynamic quantity from RiskGate)
                        qty = risk_result.suggested_quantity
                        order_ev = OrderApprovedEvent(
                            profile_id=profile_state.profile_id,
                            symbol=tick.symbol,
                            side=SignalDirection(sig_res.direction),
                            quantity=qty,
                            price=tick.price,
                            timestamp_us=tick.timestamp,
                            source_service="hot-path"
                        )
                        await self._publisher.publish(self._orders_channel, order_ev)
                        MetricsCollector.increment_counter("orders.approved")

                message_ids_to_ack.append(msg_id)

            if message_ids_to_ack:
                await self._consumer.ack(self._tick_channel, group_name, message_ids_to_ack)
