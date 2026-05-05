import uuid
from dataclasses import asdict
from decimal import Decimal
from typing import Dict, Any, Optional
from .state import ProfileStateCache
from .strategy_eval import StrategyEvaluator, SignalResult, EvaluatedIndicators
from .abstention import AbstentionChecker
from .regime_dampener import RegimeDampener
from .agent_modifier import AgentModifier
from .circuit_breaker import CircuitBreaker
from .blacklist import BlacklistChecker
from .risk_gate import RiskGate
from .hitl_gate import HITLGate
from .kill_switch import KillSwitch
from .validation_client import ValidationClient
from .decision_writer import DecisionTraceWriter

from libs.config import settings
from libs.core.enums import SignalDirection, EventType, ValidationCheck, ValidationVerdict, ValidationMode
from libs.core.models import NormalisedTick
from libs.core.schemas import MarketTickEvent, OrderApprovedEvent, ThresholdProximityEvent, ValidationRequestEvent
from libs.core.constants import THRESHOLD_PROXIMITY_BAND_PCT
from libs.messaging import StreamConsumer, StreamPublisher, PubSubBroadcaster
from libs.observability import get_logger, timer, MetricsCollector
from libs.observability.telemetry import TelemetryPublisher

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
        telemetry: TelemetryPublisher = None,
        decision_writer: Optional[DecisionTraceWriter] = None,
    ):
        self._state_cache = state_cache
        self._consumer = consumer
        self._publisher = publisher
        self._pubsub = pubsub
        self._validation_client = validation_client
        self._tick_channel = tick_channel
        self._orders_channel = orders_channel
        self._proximity_pubsub_channel = proximity_pubsub_channel

        self._redis = redis_client
        self._telemetry = telemetry
        self._decision_writer = decision_writer

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

            # Kill switch — checked once per batch, not per tick
            if self._redis and await KillSwitch.is_active(self._redis):
                message_ids_to_ack.extend(msg_id for msg_id, _ in events)
                if message_ids_to_ack:
                    await self._consumer.ack(self._tick_channel, group_name, message_ids_to_ack)
                continue

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

                if self._telemetry:
                    await self._telemetry.emit("input_received", {"symbol": event.symbol, "price": str(event.price), "exchange": event.exchange}, source_agent="ingestion")

                with timer("hot_path.tick_processing"):
                    # Master trading gate — skip all order logic when trading is disabled
                    if not settings.TRADING_ENABLED:
                        continue

                    # For each profile caching
                    for profile_state in self._state_cache.itervalues():
                        if not profile_state.is_active:
                            continue

                        # 1. Strategy Eval (with trace when writer is available)
                        strat_trace = None
                        eval_dict = None
                        if self._decision_writer:
                            trace_result = StrategyEvaluator.evaluate_with_trace(profile_state, tick)
                            if trace_result is None:
                                continue  # indicators still priming
                            sig_res, inds, strat_trace, eval_dict = trace_result
                        else:
                            eval_result = StrategyEvaluator.evaluate(profile_state, tick)
                            if eval_result is None:
                                continue
                            sig_res, inds = eval_result

                        # Build base trace dict (populated incrementally through gates)
                        trace: Dict[str, Any] = {}
                        if self._decision_writer:
                            trace = {
                                "event_id": uuid.uuid4(),
                                "profile_id": str(profile_state.profile_id),
                                "symbol": tick.symbol,
                                "input_price": tick.price,
                                "input_volume": tick.volume,
                                "indicators": {
                                    "rsi": round(inds.rsi, 4),
                                    "macd_line": round(inds.macd_line, 4),
                                    "signal_line": round(inds.signal_line, 4),
                                    "histogram": round(inds.histogram, 4),
                                    "atr": round(inds.atr, 4),
                                    "adx": round(inds.adx, 4) if inds.adx is not None else None,
                                    "bb_upper": round(inds.bb_upper, 4) if inds.bb_upper is not None else None,
                                    "bb_lower": round(inds.bb_lower, 4) if inds.bb_lower is not None else None,
                                    "bb_pct_b": round(inds.bb_pct_b, 4) if inds.bb_pct_b is not None else None,
                                    "obv": round(inds.obv, 2) if inds.obv is not None else None,
                                    "choppiness": round(inds.choppiness, 4) if inds.choppiness is not None else None,
                                },
                                "strategy": asdict(strat_trace) if strat_trace else {},
                                "regime": None,
                                "agents": None,
                                "gates": {},
                                "profile_rules": {
                                    "logic": profile_state.compiled_rules.logic,
                                    "direction": profile_state.compiled_rules.direction.value,
                                    "base_confidence": profile_state.compiled_rules.base_confidence,
                                    "conditions": profile_state.compiled_rules.conditions,
                                    "risk_limits": {
                                        "max_drawdown_pct": str(profile_state.risk_limits.max_drawdown_pct),
                                        "stop_loss_pct": str(profile_state.risk_limits.stop_loss_pct),
                                        "max_allocation_pct": str(profile_state.risk_limits.max_allocation_pct),
                                    },
                                },
                            }

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
                        abstain_blocked, abstain_reason = AbstentionChecker.check_with_reason(profile_state, sig_res, tick, inds)
                        if abstain_blocked:
                            logger.info("gate_block", gate="abstention", symbol=tick.symbol)
                            if self._decision_writer:
                                trace["outcome"] = "BLOCKED_ABSTENTION"
                                trace["gates"]["abstention"] = {"passed": False, "reason": abstain_reason}
                                await self._decision_writer.write(trace)
                            continue
                        if trace:
                            trace["gates"]["abstention"] = {"passed": True}

                        # 3. Regime Dampener (now async with dual-regime support)
                        damp_res = await self._regime_dampener.check(profile_state, sig_res, tick, inds)
                        if not damp_res.proceed:
                            logger.info("gate_block", gate="regime", symbol=tick.symbol)
                            if self._decision_writer:
                                trace["outcome"] = "BLOCKED_REGIME"
                                trace["regime"] = {
                                    "rule_based": getattr(damp_res, "rule_regime", None),
                                    "hmm": getattr(damp_res, "hmm_regime", None),
                                    "resolved": getattr(damp_res, "resolved_regime", None),
                                    "confidence_multiplier": damp_res.confidence_multiplier,
                                }
                                trace["gates"]["regime"] = {"passed": False}
                                await self._decision_writer.write(trace)
                            continue

                        # Apply confidence multiplier
                        sig_res = SignalResult(
                            direction=sig_res.direction,
                            confidence=sig_res.confidence * damp_res.confidence_multiplier,
                            rule_matched=sig_res.rule_matched
                        )
                        if trace:
                            trace["regime"] = {
                                "rule_based": getattr(damp_res, "rule_regime", None),
                                "hmm": getattr(damp_res, "hmm_regime", None),
                                "resolved": getattr(damp_res, "resolved_regime", None),
                                "confidence_multiplier": damp_res.confidence_multiplier,
                            }
                            trace["gates"]["regime"] = {"passed": True}

                        # 3a. Profile-level regime preference (C.4). If the
                        # profile declared preferred_regimes and the resolved
                        # live regime is not among them, short-circuit with a
                        # SHADOW decision so PR3 can compare would-be vs live
                        # performance. Skip when preferred_regimes is empty
                        # (regime-agnostic profile) or when the regime is
                        # unknown (don't shadow on missing data — that just
                        # means the dampener had nothing to resolve).
                        if profile_state.preferred_regimes and profile_state.regime is not None:
                            if profile_state.regime not in profile_state.preferred_regimes:
                                logger.info(
                                    "gate_block",
                                    gate="regime_mismatch",
                                    symbol=tick.symbol,
                                    profile_regimes=[r.value for r in profile_state.preferred_regimes],
                                    live_regime=profile_state.regime.value,
                                )
                                if self._decision_writer:
                                    trace["outcome"] = "BLOCKED_REGIME_MISMATCH"
                                    trace["shadow"] = True
                                    trace["gates"]["regime_mismatch"] = {
                                        "passed": False,
                                        "preferred": [r.value for r in profile_state.preferred_regimes],
                                        "actual": profile_state.regime.value,
                                    }
                                    await self._decision_writer.write(trace)
                                continue
                            if trace:
                                trace["gates"]["regime_mismatch"] = {"passed": True}

                        # 3b. Agent Modifier (TA + sentiment scores)
                        if self._agent_modifier:
                            if self._decision_writer:
                                agent_trace = await self._agent_modifier.apply_traced(tick.symbol, sig_res)
                                sig_res = agent_trace.signal
                                trace["agents"] = {
                                    **agent_trace.agents,
                                    "confidence_before": round(agent_trace.confidence_before, 6),
                                    "confidence_after": round(agent_trace.confidence_after, 6),
                                }
                            else:
                                sig_res = await self._agent_modifier.apply(tick.symbol, sig_res)

                        # Telemetry: decision trace after signal evaluation
                        if self._telemetry:
                            await self._telemetry.emit(
                                "decision_trace",
                                {
                                    "profile_id": str(profile_state.profile_id),
                                    "symbol": tick.symbol,
                                    "direction": sig_res.direction,
                                    "confidence": sig_res.confidence,
                                    "rule_matched": sig_res.rule_matched,
                                },
                                source_agent="ta_agent",
                                target_agent="validation",
                            )

                        # 4. Circuit Breaker
                        if CircuitBreaker.check(profile_state):
                            logger.info("gate_block", gate="circuit_breaker", symbol=tick.symbol)
                            if self._decision_writer:
                                trace["outcome"] = "BLOCKED_CIRCUIT_BREAKER"
                                trace["gates"]["circuit_breaker"] = {
                                    "passed": False,
                                    "daily_pnl_pct": str(getattr(profile_state, "daily_realised_pnl_pct", 0)),
                                    "threshold": str(profile_state.risk_limits.circuit_breaker_daily_loss_pct),
                                }
                                await self._decision_writer.write(trace)
                            continue
                        if trace:
                            trace["gates"]["circuit_breaker"] = {"passed": True}

                        # 5. Blacklist
                        if BlacklistChecker.check(profile_state, tick.symbol):
                            logger.info("gate_block", gate="blacklist", symbol=tick.symbol)
                            if self._decision_writer:
                                trace["outcome"] = "BLOCKED_BLACKLIST"
                                trace["gates"]["blacklist"] = {"passed": False}
                                await self._decision_writer.write(trace)
                            continue
                        if trace:
                            trace["gates"]["blacklist"] = {"passed": True}

                        # 6. Risk Gate (now returns RiskGateResult with dynamic sizing)
                        risk_result = RiskGate.check(profile_state, sig_res, tick)
                        if risk_result.blocked:
                            logger.info("gate_block", gate="risk_gate", symbol=tick.symbol, reason=risk_result.reason if hasattr(risk_result, 'reason') else "unknown")
                            if self._decision_writer:
                                trace["outcome"] = "BLOCKED_RISK"
                                trace["gates"]["risk_gate"] = {
                                    "passed": False,
                                    "reason": risk_result.reason,
                                    "allocation_pct": str(profile_state.current_allocation_pct),
                                    "drawdown_pct": str(profile_state.current_drawdown_pct),
                                }
                                await self._decision_writer.write(trace)
                            continue
                        if trace:
                            trace["gates"]["risk_gate"] = {
                                "passed": True,
                                "suggested_qty": str(risk_result.suggested_quantity),
                                "allocation_pct": str(profile_state.current_allocation_pct),
                                "drawdown_pct": str(profile_state.current_drawdown_pct),
                            }

                        # 6b. HITL Gate (between risk_gate and validation)
                        if self._hitl_gate:
                            hitl_result = await self._hitl_gate.check(
                                profile_state, sig_res, tick, inds, risk_result,
                            )
                            if hitl_result.blocked:
                                logger.info(f"HITL blocked trade for {profile_state.profile_id} - {hitl_result.reason}")
                                if self._decision_writer:
                                    trace["outcome"] = "BLOCKED_HITL"
                                    trace["gates"]["hitl"] = {"passed": False, "reason": hitl_result.reason}
                                    await self._decision_writer.write(trace)
                                continue
                            if trace:
                                trace["gates"]["hitl"] = {"passed": True, "triggered": False}

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
                            if self._decision_writer:
                                trace["outcome"] = "BLOCKED_VALIDATION"
                                trace["gates"]["validation"] = {
                                    "passed": False,
                                    "verdict": val_resp.verdict.value if val_resp.verdict else "RED",
                                    "reason": val_resp.reason,
                                }
                                await self._decision_writer.write(trace)
                            continue
                        if trace:
                            trace["gates"]["validation"] = {
                                "passed": True,
                                "verdict": val_resp.verdict.value if val_resp and val_resp.verdict else "GREEN",
                                "reason": val_resp.reason if val_resp else None,
                            }

                        # 8. Emit Order Approved (using dynamic quantity from RiskGate)
                        qty = risk_result.suggested_quantity
                        order_ev = OrderApprovedEvent(
                            profile_id=profile_state.profile_id,
                            symbol=tick.symbol,
                            side=SignalDirection(sig_res.direction),
                            quantity=qty,
                            price=tick.price,
                            decision_event_id=trace.get("event_id"),
                            timestamp_us=tick.timestamp,
                            source_service="hot-path"
                        )
                        await self._publisher.publish(self._orders_channel, order_ev)
                        MetricsCollector.increment_counter("orders.approved")

                        # Pre-bump open exposure so the next tick's RiskGate sees
                        # the projected commitment immediately. Without this,
                        # PnlSync's 5s reconciliation poll leaves a race window
                        # where multiple ticks in the same window all see
                        # exposure=0 and approve in parallel — the live failure
                        # mode that opened 3 ETH/USDT positions in 6 seconds
                        # past a $10k notional cap. The poll loop overwrites
                        # this value in seconds with the DB-derived ground
                        # truth, so over-counting is bounded to one poll cycle.
                        try:
                            projected_cost = Decimal(str(qty)) * Decimal(str(tick.price))
                            profile_state.open_exposure_dollars += projected_cost
                        except Exception:
                            logger.exception(
                                "Failed to pre-bump open_exposure_dollars",
                                profile_id=profile_state.profile_id,
                                symbol=tick.symbol,
                            )

                        # Write approved decision trace.
                        # Note: trade_decisions.order_id intentionally left NULL.
                        # The reverse link is canonical: orders.decision_event_id = trade_decisions.event_id.
                        if self._decision_writer:
                            trace["outcome"] = "APPROVED"
                            await self._decision_writer.write(trace)

                        # Telemetry: order approved emitted
                        if self._telemetry:
                            await self._telemetry.emit(
                                "output_emitted",
                                {
                                    "profile_id": str(profile_state.profile_id),
                                    "symbol": tick.symbol,
                                    "side": sig_res.direction,
                                    "quantity": str(qty),
                                    "price": str(tick.price),
                                },
                                target_agent="execution",
                            )

                message_ids_to_ack.append(msg_id)

            if message_ids_to_ack:
                await self._consumer.ack(self._tick_channel, group_name, message_ids_to_ack)
