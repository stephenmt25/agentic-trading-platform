import json
from dataclasses import dataclass
from typing import Optional
from libs.core.enums import Regime, EventType
from libs.core.models import NormalisedTick
from libs.core.schemas import AlertEvent
from libs.observability import get_logger
from .state import ProfileState
from .strategy_eval import SignalResult, EvaluatedIndicators
import time

logger = get_logger("hot-path.regime-dampener")

# Regime severity for conservative resolution (higher = more conservative)
_REGIME_SEVERITY = {
    Regime.RANGE_BOUND: 0,
    Regime.TRENDING_UP: 1,
    Regime.TRENDING_DOWN: 2,
    Regime.HIGH_VOLATILITY: 3,
    Regime.CRISIS: 4,
}


@dataclass(frozen=True, slots=True)
class DampenerResult:
    proceed: bool
    confidence_multiplier: float


class RegimeDampener:
    _REGIME_CACHE_TTL_S = 1.0  # Cache HMM regime for 1 second

    def __init__(self, redis_client=None, pubsub=None):
        self._redis = redis_client
        self._pubsub = pubsub
        self._regime_cache: dict = {}  # symbol -> (regime, timestamp)

    async def check(
        self, state: ProfileState, signal: SignalResult, tick: NormalisedTick, inds: EvaluatedIndicators
    ) -> DampenerResult:
        price = float(tick.price)  # float-ok: indicator library requires float

        # 1. Rule-based regime from existing indicator
        rule_regime = state.indicators.regime.update(price, inds.atr)
        state.regime = rule_regime

        # 2. Read HMM regime from Redis (if available)
        hmm_regime = await self._read_hmm_regime(tick.symbol)

        # 3. Resolve dual regime
        resolved = self._resolve_regimes(rule_regime, hmm_regime)

        # 4. Disagreement detection
        if rule_regime and hmm_regime and rule_regime != hmm_regime:
            await self._emit_disagreement_alert(state, tick, rule_regime, hmm_regime)

        state.regime = resolved

        if resolved == Regime.CRISIS:
            return DampenerResult(proceed=False, confidence_multiplier=0.0)

        if resolved == Regime.HIGH_VOLATILITY:
            return DampenerResult(proceed=True, confidence_multiplier=0.7)

        return DampenerResult(proceed=True, confidence_multiplier=1.0)

    async def _read_hmm_regime(self, symbol: str) -> Optional[Regime]:
        if not self._redis:
            return None

        # Check in-process cache first (1s TTL)
        cached = self._regime_cache.get(symbol)
        if cached is not None:
            regime, cached_at = cached
            if (time.monotonic() - cached_at) < self._REGIME_CACHE_TTL_S:
                return regime

        try:
            raw = await self._redis.get(f"agent:regime_hmm:{symbol}")
            if raw:
                data = json.loads(raw)
                regime = Regime(data["regime"])
                self._regime_cache[symbol] = (regime, time.monotonic())
                return regime
        except Exception:
            pass
        self._regime_cache[symbol] = (None, time.monotonic())
        return None

    def _resolve_regimes(self, rule_regime: Optional[Regime], hmm_regime: Optional[Regime]) -> Optional[Regime]:
        """Resolve dual regime: CRISIS wins, otherwise use the more conservative."""
        if rule_regime is None and hmm_regime is None:
            return None
        if rule_regime is None:
            return hmm_regime
        if hmm_regime is None:
            return rule_regime

        # Either says CRISIS → use CRISIS
        if rule_regime == Regime.CRISIS or hmm_regime == Regime.CRISIS:
            return Regime.CRISIS

        # Use the more conservative (higher severity) assessment
        if _REGIME_SEVERITY.get(hmm_regime, 0) > _REGIME_SEVERITY.get(rule_regime, 0):
            return hmm_regime
        return rule_regime

    async def _emit_disagreement_alert(
        self, state: ProfileState, tick: NormalisedTick, rule_regime: Regime, hmm_regime: Regime
    ):
        if not self._pubsub:
            return
        try:
            alert = AlertEvent(
                event_type=EventType.REGIME_DISAGREEMENT,
                message=f"Regime disagreement for {tick.symbol}: rule-based={rule_regime.value}, HMM={hmm_regime.value}",
                level="AMBER",
                profile_id=state.profile_id,
                timestamp_us=tick.timestamp,
                source_service="hot-path",
            )
            from libs.messaging.channels import PUBSUB_ALERTS
            await self._pubsub.publish(PUBSUB_ALERTS, alert)
            logger.info(
                "Regime disagreement alert",
                symbol=tick.symbol,
                rule=rule_regime.value,
                hmm=hmm_regime.value,
            )
        except Exception as e:
            logger.error("Failed to emit regime disagreement alert", error=str(e))
