"""Processor-level tests for the row-44 HITL async rework and the row-41
order-burst tripwire.

The critical property under test: the hot-path tick loop NEVER awaits a
human. A HITL-triggered signal is parked and the engine keeps processing
ticks (the blocking implementation froze a soak for ~13h); approval resumes
the remaining gate sequence; deny/timeout fail-safe reject.
"""

import asyncio
import contextlib
import json
import time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from libs.core.enums import SignalDirection
from libs.core.models import NormalisedTick, RiskLimits
from libs.core.schemas import AlertEvent, MarketTickEvent
from libs.indicators import create_indicator_set
from libs.messaging.channels import PUBSUB_HITL_PENDING, PUBSUB_SYSTEM_ALERTS
from services.hot_path.src.hitl_gate import HITLResolution
from services.hot_path.src.processor import HotPathProcessor, OrderBurstTripwire
from services.hot_path.src.risk_gate import RiskGateResult
from services.hot_path.src.state import ProfileState, ProfileStateCache
from services.hot_path.src.strategy_eval import EvaluatedIndicators, SignalResult
from services.strategy.src.compiler import CompiledRuleSet

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeRedis:
    def __init__(self):
        self._store = {}
        self._lists = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None):
        self._store[key] = value

    async def delete(self, key):
        self._store.pop(key, None)

    async def lpop(self, key):
        if key in self._lists and self._lists[key]:
            return self._lists[key].pop(0)
        return None

    async def lpush(self, key, value):
        self._lists.setdefault(key, []).insert(0, value)

    def pipeline(self, transaction=False):
        return FakePipeline(self._store)


class FakePipeline:
    def __init__(self, store):
        self._store = store
        self._commands = []

    def get(self, key):
        self._commands.append(key)
        return self

    async def execute(self):
        results = [self._store.get(k) for k in self._commands]
        self._commands = []
        return results


class FakeConsumer:
    """Yields scripted batches once, then empty batches forever."""

    def __init__(self, batches):
        self._batches = list(batches)
        self.acked = []

    async def consume(self, channel, group, consumer, count=100, block_ms=50):
        if self._batches:
            await asyncio.sleep(0)
            return self._batches.pop(0)
        await asyncio.sleep(0.005)
        return []

    async def ack(self, channel, group, ids):
        self.acked.extend(ids)


class FakePublisher:
    def __init__(self):
        self.published = []

    async def publish(self, channel, event, maxlen=None):
        self.published.append((channel, event))


class FakePubSub:
    def __init__(self):
        self.published = []

    async def publish(self, channel, event):
        self.published.append((channel, event))


class FakeValidationClient:
    """fast_gate passes (None response = no RED verdict)."""

    def __init__(self):
        self.requests = []

    async def fast_gate(self, request):
        self.requests.append(request)
        return None


class StubDampener:
    async def check(self, state, sig_res, tick, inds):
        return SimpleNamespace(proceed=True, confidence_multiplier=1.0)


# Scripted per-symbol signals: BTC/USDT is low-confidence (HITL triggers),
# ETH/USDT is high-confidence (no trigger).
_SYMBOL_CONFIDENCE = {"BTC/USDT": 0.3, "ETH/USDT": 0.9}


class StubEvaluator:
    @staticmethod
    def evaluate(state, tick):
        confidence = _SYMBOL_CONFIDENCE.get(tick.symbol, 0.9)
        sig = SignalResult(
            direction=SignalDirection.BUY, confidence=confidence, rule_matched=True
        )
        inds = EvaluatedIndicators(
            rsi=28.0, macd_line=0.5, signal_line=0.3, histogram=0.2, atr=500.0
        )
        return sig, inds


class StubAbstention:
    @staticmethod
    def check_with_reason(state, sig_res, tick, inds):
        return False, None


class StubRiskGate:
    @staticmethod
    def check(state, signal, tick):
        return RiskGateResult(blocked=False, suggested_quantity=Decimal("0.5"))


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _make_settings(hitl_enabled=True, hitl_timeout_s=60):
    return SimpleNamespace(
        TRADING_ENABLED=True,
        HITL_ENABLED=hitl_enabled,
        HITL_CONFIDENCE_THRESHOLD=0.5,
        HITL_SIZE_THRESHOLD_PCT=1e12,  # size trigger disabled for these tests
        HITL_TIMEOUT_S=hitl_timeout_s,
        CORRELATION_CLUSTERS={"BTC/USDT": "MAJORS", "ETH/USDT": "MAJORS"},
        PORTFOLIO_GROSS_BUDGET_USD=Decimal("100000000"),
        CORRELATION_CLUSTER_CAP_PCT=Decimal("1.0"),
    )


def _make_profile_state(profile_id="profile-1"):
    rules = CompiledRuleSet(
        logic="AND",
        direction=SignalDirection.BUY,
        base_confidence=0.85,
        conditions=[{"indicator": "rsi", "operator": "LT", "value": 30}],
    )
    limits = RiskLimits(
        max_drawdown_pct=Decimal("0.05"),
        stop_loss_pct=Decimal("0.02"),
        circuit_breaker_daily_loss_pct=Decimal("0.02"),
        max_allocation_pct=Decimal("0.10"),
    )
    return ProfileState(
        profile_id=profile_id,
        compiled_rules=rules,
        risk_limits=limits,
        blacklist=frozenset(),
        indicators=create_indicator_set(),
    )


def _tick_event(symbol, price="50000"):
    return MarketTickEvent(
        symbol=symbol,
        exchange="BINANCE",
        price=Decimal(price),
        volume=Decimal("1"),
        timestamp_us=int(time.time() * 1_000_000),  # fresh — passes stale guard
        source_service="test",
    )


def _make_processor(monkeypatch, batches, settings_ns):
    """Build a HotPathProcessor over fakes with deterministic stub gates.

    Real gates left in play: ReentryGate, CircuitBreaker, Blacklist,
    KillSwitch, portfolio gate, and the full HITLGate park/sweep machinery.
    """
    monkeypatch.setattr("services.hot_path.src.processor.settings", settings_ns)
    monkeypatch.setattr("services.hot_path.src.hitl_gate.settings", settings_ns)
    monkeypatch.setattr(
        "services.hot_path.src.processor.StrategyEvaluator", StubEvaluator
    )
    monkeypatch.setattr(
        "services.hot_path.src.processor.AbstentionChecker", StubAbstention
    )
    monkeypatch.setattr("services.hot_path.src.processor.RiskGate", StubRiskGate)

    redis = FakeRedis()
    consumer = FakeConsumer(batches)
    publisher = FakePublisher()
    pubsub = FakePubSub()
    validation = FakeValidationClient()
    state_cache = ProfileStateCache()
    state_cache.add(_make_profile_state())

    proc = HotPathProcessor(
        state_cache=state_cache,
        consumer=consumer,
        publisher=publisher,
        pubsub=pubsub,
        validation_client=validation,
        tick_channel="stream:market_data",
        orders_channel="stream:orders",
        proximity_pubsub_channel="pubsub:threshold_proximity",
        redis_client=redis,
        hitl_redis_client=None,
        telemetry=None,
        decision_writer=None,
    )
    proc._regime_dampener = StubDampener()
    proc._agent_modifier = None

    fakes = SimpleNamespace(
        redis=redis,
        consumer=consumer,
        publisher=publisher,
        pubsub=pubsub,
        validation=validation,
        state_cache=state_cache,
    )
    return proc, fakes


async def _wait_for(predicate, timeout_s=2.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return predicate()


@contextlib.asynccontextmanager
async def _running(proc):
    task = asyncio.create_task(proc.run())
    try:
        yield task
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def _hitl_request(fakes):
    return next(ev for ch, ev in fakes.pubsub.published if ch == PUBSUB_HITL_PENDING)


async def _park_directly(proc, fakes, symbol="BTC/USDT"):
    """Park a low-confidence signal through the gate without running the
    loop; returns the ParkedSignal."""
    state = fakes.state_cache.get("profile-1")
    result = await proc._hitl_gate.check(
        state,
        SignalResult(direction=SignalDirection.BUY, confidence=0.3, rule_matched=True),
        NormalisedTick(
            symbol=symbol,
            exchange="BINANCE",
            timestamp=int(time.time() * 1_000_000),
            price=Decimal("50000"),
            volume=Decimal("1"),
        ),
        EvaluatedIndicators(
            rsi=28.0, macd_line=0.5, signal_line=0.3, histogram=0.2, atr=500.0
        ),
        RiskGateResult(blocked=False, suggested_quantity=Decimal("0.5")),
        trace={},
    )
    assert result.parked
    return next(iter(proc._hitl_gate._parked.values()))


# ---------------------------------------------------------------------------
# Row 44 — HITL async park/sweep at the processor level
# ---------------------------------------------------------------------------


class TestHITLAsyncProcessor:

    @pytest.mark.asyncio
    async def test_pending_park_tick_processing_continues(self, monkeypatch):
        """THE row-44 property: while a HITL-triggered signal is parked, the
        engine keeps consuming and trading other ticks instead of stalling."""
        batches = [
            [("1-0", _tick_event("BTC/USDT"))],  # parks (low confidence)
            [("2-0", _tick_event("ETH/USDT", "3500"))],  # must still trade
        ]
        proc, fakes = _make_processor(monkeypatch, batches, _make_settings())

        async with _running(proc):
            # ETH order published WHILE the BTC signal is still parked.
            assert await _wait_for(lambda: len(fakes.publisher.published) == 1)
            channel, eth_order = fakes.publisher.published[0]
            assert channel == "stream:orders"
            assert eth_order.symbol == "ETH/USDT"
            assert proc._hitl_gate.pending_count == 1
            # Both tick batches were acked — the loop never stalled.
            assert await _wait_for(lambda: set(fakes.consumer.acked) == {"1-0", "2-0"})

    @pytest.mark.asyncio
    async def test_approve_resume_publishes_parked_order(self, monkeypatch):
        """APPROVE resumes the remaining gate sequence (validation → publish)
        for the parked signal."""
        batches = [[("1-0", _tick_event("BTC/USDT"))]]
        proc, fakes = _make_processor(monkeypatch, batches, _make_settings())

        async with _running(proc):
            assert await _wait_for(lambda: proc._hitl_gate.pending_count == 1)
            request = _hitl_request(fakes)
            await fakes.redis.lpush(
                f"hitl:response:{request.event_id}",
                json.dumps({"status": "APPROVED", "reviewer": "test"}),
            )
            assert await _wait_for(lambda: len(fakes.publisher.published) == 1)
            _, order = fakes.publisher.published[0]
            assert order.symbol == "BTC/USDT"
            assert order.quantity == Decimal("0.5")
            assert order.side == SignalDirection.BUY
            assert proc._hitl_gate.pending_count == 0
            # Remaining gate sequence really ran: validation saw the request.
            assert len(fakes.validation.requests) == 1
            assert fakes.validation.requests[0].symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_deny_rejects_failsafe_no_order(self, monkeypatch):
        """DENY → fail-safe reject: parked signal resolves, no order ever
        reaches the stream."""
        batches = [[("1-0", _tick_event("BTC/USDT"))]]
        proc, fakes = _make_processor(monkeypatch, batches, _make_settings())

        async with _running(proc):
            assert await _wait_for(lambda: proc._hitl_gate.pending_count == 1)
            request = _hitl_request(fakes)
            await fakes.redis.lpush(
                f"hitl:response:{request.event_id}",
                json.dumps({"status": "REJECTED", "reason": "too risky"}),
            )
            assert await _wait_for(lambda: proc._hitl_gate.pending_count == 0)
            assert fakes.publisher.published == []
            assert fakes.validation.requests == []

    @pytest.mark.asyncio
    async def test_timeout_rejects_failsafe_no_order(self, monkeypatch):
        """No human response by the deadline → fail-safe reject."""
        batches = [[("1-0", _tick_event("BTC/USDT"))]]
        proc, fakes = _make_processor(
            monkeypatch, batches, _make_settings(hitl_timeout_s=0)
        )

        async with _running(proc):
            # Parked, then immediately timeout-rejected by the next sweep.
            assert await _wait_for(
                lambda: any(
                    ch == PUBSUB_HITL_PENDING for ch, _ in fakes.pubsub.published
                )
            )
            assert await _wait_for(lambda: proc._hitl_gate.pending_count == 0)
            assert fakes.publisher.published == []

    @pytest.mark.asyncio
    async def test_disabled_bypass_trades_straight_through(self, monkeypatch):
        """PRAXIS_HITL_ENABLED=false: low-confidence signal flows through the
        gate untouched — order published, no approval request emitted."""
        batches = [[("1-0", _tick_event("BTC/USDT"))]]
        proc, fakes = _make_processor(
            monkeypatch, batches, _make_settings(hitl_enabled=False)
        )

        async with _running(proc):
            assert await _wait_for(lambda: len(fakes.publisher.published) == 1)
            _, order = fakes.publisher.published[0]
            assert order.symbol == "BTC/USDT"
            assert proc._hitl_gate.pending_count == 0
            assert not any(
                ch == PUBSUB_HITL_PENDING for ch, _ in fakes.pubsub.published
            )

    @pytest.mark.asyncio
    async def test_resume_rechecks_kill_switch(self, monkeypatch):
        """An approval landing while the kill switch is active must NOT
        publish (fail-safe). Exercised directly against the resolution
        handler — the loop-level batch check normally skips the sweep while
        halted, this guards the activation race inside one iteration."""
        proc, fakes = _make_processor(monkeypatch, [], _make_settings())
        # Park via the gate directly, then halt trading.
        parked = await _park_directly(proc, fakes)
        await fakes.redis.set("praxis:kill_switch", "1")

        await proc._handle_hitl_resolution(HITLResolution(parked=parked, approved=True))
        assert fakes.publisher.published == []

    @pytest.mark.asyncio
    async def test_resume_rechecks_reentry(self, monkeypatch):
        """If a position opened on the symbol while the signal was parked,
        an approval must NOT pyramid a second one."""
        proc, fakes = _make_processor(monkeypatch, [], _make_settings())
        parked = await _park_directly(proc, fakes)
        state = fakes.state_cache.get("profile-1")
        state.open_position_symbols.add("BTC/USDT")  # position opened meanwhile

        await proc._handle_hitl_resolution(HITLResolution(parked=parked, approved=True))
        assert fakes.publisher.published == []


# ---------------------------------------------------------------------------
# Row 41 / D-K — order-burst tripwire window logic
# ---------------------------------------------------------------------------


class TestOrderBurstTripwire:

    def test_no_level_at_warn_threshold(self):
        """Exactly 10 orders in the window is NOT a breach (> 10 is)."""
        tw = OrderBurstTripwire()
        count = 0
        for i in range(10):
            count = tw.record("p1", now=100.0 + i * 0.1)
        assert count == 10
        assert tw.level(count) is None

    def test_warn_above_10(self):
        tw = OrderBurstTripwire()
        count = 0
        for i in range(11):
            count = tw.record("p1", now=100.0 + i * 0.1)
        assert count == 11
        assert tw.level(count) == "WARN"

    def test_no_critical_at_25(self):
        tw = OrderBurstTripwire()
        count = 0
        for i in range(25):
            count = tw.record("p1", now=100.0 + i * 0.1)
        assert count == 25
        assert tw.level(count) == "WARN"

    def test_critical_above_25(self):
        tw = OrderBurstTripwire()
        count = 0
        for i in range(26):
            count = tw.record("p1", now=100.0 + i * 0.1)
        assert count == 26
        assert tw.level(count) == "CRITICAL"

    def test_window_expiry_resets_count(self):
        """Orders older than the 60s rolling window are evicted."""
        tw = OrderBurstTripwire()
        for i in range(11):
            tw.record("p1", now=100.0 + i * 0.1)
        # 100s later: every prior publish has aged out.
        count = tw.record("p1", now=201.0)
        assert count == 1
        assert tw.level(count) is None

    def test_window_boundary_is_exclusive(self):
        """An entry exactly WINDOW_S old no longer counts."""
        tw = OrderBurstTripwire()
        tw.record("p1", now=100.0)
        count = tw.record("p1", now=160.0)  # cutoff = 100.0 → first evicted
        assert count == 1

    def test_profiles_are_isolated(self):
        tw = OrderBurstTripwire()
        for i in range(26):
            tw.record("p1", now=100.0 + i * 0.1)
        assert tw.record("p2", now=103.0) == 1

    def test_alert_cooldown(self):
        tw = OrderBurstTripwire()
        assert tw.should_alert("p1", now=100.0) is True
        assert tw.should_alert("p1", now=130.0) is False  # inside cooldown
        assert tw.should_alert("p1", now=161.0) is True  # cooldown elapsed
        assert tw.should_alert("p2", now=130.0) is True  # per-profile

    @pytest.mark.asyncio
    async def test_critical_publishes_one_system_alert(self, monkeypatch):
        """>25 orders in the window → exactly one AlertEvent on
        pubsub:system_alerts (cooldown suppresses repeats); no auto-halt
        (kill switch key untouched)."""
        proc, fakes = _make_processor(monkeypatch, [], _make_settings())

        for _ in range(24):
            await proc._order_tripwire_record("profile-1")
        # ≤25 so far → no alert yet (24 < WARN? no: 24 > 10 → WARN logs only)
        assert (
            sum(1 for ch, _ in fakes.pubsub.published if ch == PUBSUB_SYSTEM_ALERTS)
            == 0
        )

        for _ in range(3):
            await proc._order_tripwire_record("profile-1")
        alerts = [ev for ch, ev in fakes.pubsub.published if ch == PUBSUB_SYSTEM_ALERTS]
        assert len(alerts) == 1  # cooldown: one alert per window, not per order
        alert = alerts[0]
        assert isinstance(alert, AlertEvent)
        assert alert.level == "RED"
        assert alert.profile_id == "profile-1"
        assert alert.source_service == "hot-path"
        assert "order burst" in alert.message
        assert "no auto-halt" in alert.message.lower()
        # NO auto-halt: the kill switch key was never written.
        assert await fakes.redis.get("praxis:kill_switch") is None
