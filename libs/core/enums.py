from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    ROLLED_BACK = "ROLLED_BACK"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class EventType(str, Enum):
    MARKET_TICK = "MARKET_TICK"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    SIGNAL_ABSTAINED = "SIGNAL_ABSTAINED"
    ORDER_APPROVED = "ORDER_APPROVED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_EXECUTED = "ORDER_EXECUTED"
    ORDER_FAILED = "ORDER_FAILED"
    CIRCUIT_BREAKER_TRIGGERED = "CIRCUIT_BREAKER_TRIGGERED"
    BLACKLIST_BLOCKED = "BLACKLIST_BLOCKED"
    VALIDATION_PROCEED = "VALIDATION_PROCEED"
    VALIDATION_BLOCK = "VALIDATION_BLOCK"
    VALIDATION_TIMEOUT = "VALIDATION_TIMEOUT"
    REGIME_CHANGE = "REGIME_CHANGE"
    PNL_UPDATE = "PNL_UPDATE"
    ALERT_AMBER = "ALERT_AMBER"
    ALERT_RED = "ALERT_RED"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    THRESHOLD_PROXIMITY = "THRESHOLD_PROXIMITY"
    REGIME_DISAGREEMENT = "REGIME_DISAGREEMENT"
    HITL_PENDING = "HITL_PENDING"
    HITL_RESPONSE = "HITL_RESPONSE"
    ORDERBOOK_SNAPSHOT = "ORDERBOOK_SNAPSHOT"
    TRADE_TICK = "TRADE_TICK"


class Regime(str, Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGE_BOUND = "RANGE_BOUND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    CRISIS = "CRISIS"


class ValidationCheck(str, Enum):
    CHECK_1_STRATEGY = "CHECK_1_STRATEGY"
    CHECK_2_HALLUCINATION = "CHECK_2_HALLUCINATION"
    CHECK_3_BIAS = "CHECK_3_BIAS"
    CHECK_4_DRIFT = "CHECK_4_DRIFT"
    CHECK_5_ESCALATION = "CHECK_5_ESCALATION"
    CHECK_6_RISK_LEVEL = "CHECK_6_RISK_LEVEL"


class ValidationVerdict(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class ValidationMode(str, Enum):
    FAST_GATE = "FAST_GATE"
    ASYNC_AUDIT = "ASYNC_AUDIT"


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    ABSTAIN = "ABSTAIN"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    # In-flight close: a reduce-only close order has been published to the
    # exchange and we are awaiting its fill. The position is removed from
    # exit monitoring while in this state so it is not re-closed every tick.
    # Set by PositionCloseRequester (CAS from OPEN); cleared to CLOSED on fill
    # confirmation or reverted to OPEN on close-order rejection.
    PENDING_CLOSE = "PENDING_CLOSE"
    CLOSED = "CLOSED"


class HITLStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TradingMode(str, Enum):
    PAPER = "PAPER"
    TESTNET = "TESTNET"
    LIVE = "LIVE"
