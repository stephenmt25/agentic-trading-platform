from typing import Any, Dict, List, Optional, Literal
from uuid import UUID, uuid4
import os
import threading
from pydantic import BaseModel, Field, ConfigDict, root_validator

from .enums import EventType, OrderSide, OrderStatus, SignalDirection, ValidationCheck, ValidationMode, ValidationVerdict, HITLStatus
from .types import Percentage, Price, ProfileId, Quantity, SymbolPair, Timestamp


def _make_monotonic_id_factory():
    """Create a fast monotonic ID generator using process ID + counter.

    Produces valid UUID-shaped strings without syscalls.
    Format: 00000000-0000-4pid-8cnt-cntcntcntcnt
    """
    _pid = os.getpid() & 0xFFF
    _counter = 0
    _lock = threading.Lock()

    def _next_id() -> UUID:
        nonlocal _counter
        with _lock:
            _counter += 1
            c = _counter
        # Build a UUID from pid + counter deterministically
        high = (c >> 48) & 0xFFFFFFFF
        mid = (c >> 32) & 0xFFFF
        low = c & 0xFFFFFFFFFFFF
        hex_str = f"{high:08x}-{mid:04x}-4{_pid:03x}-8000-{low:012x}"
        return UUID(hex_str)

    return _next_id


_monotonic_id = _make_monotonic_id_factory()


class BaseEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=_monotonic_id)
    event_type: EventType
    timestamp_us: Timestamp
    source_service: str
    schema_version: int = 1

class MarketTickEvent(BaseEvent):
    event_type: Literal[EventType.MARKET_TICK] = EventType.MARKET_TICK
    symbol: SymbolPair
    exchange: str
    price: Price
    volume: Quantity

class SignalEvent(BaseEvent):
    event_type: Literal[EventType.SIGNAL_GENERATED] = EventType.SIGNAL_GENERATED
    profile_id: ProfileId
    symbol: SymbolPair
    direction: Literal["BUY", "SELL", "ABSTAIN"]
    confidence: Percentage

class OrderApprovedEvent(BaseEvent):
    event_type: Literal[EventType.ORDER_APPROVED] = EventType.ORDER_APPROVED
    profile_id: ProfileId
    symbol: SymbolPair
    side: OrderSide
    quantity: Quantity
    price: Price

class OrderRejectedEvent(BaseEvent):
    event_type: Literal[EventType.ORDER_REJECTED] = EventType.ORDER_REJECTED
    profile_id: ProfileId
    symbol: SymbolPair
    reason: str

class OrderExecutedEvent(BaseEvent):
    event_type: Literal[EventType.ORDER_EXECUTED] = EventType.ORDER_EXECUTED
    order_id: UUID
    profile_id: ProfileId
    symbol: SymbolPair
    side: OrderSide
    fill_price: Price
    quantity: Quantity

class ValidationRequestEvent(BaseEvent):
    event_type: Literal[EventType.VALIDATION_PROCEED, EventType.VALIDATION_BLOCK] = EventType.VALIDATION_PROCEED
    profile_id: ProfileId
    symbol: SymbolPair
    check_type: ValidationCheck
    payload: Dict[str, Any]

class ValidationResponseEvent(BaseEvent):
    event_type: Literal[EventType.VALIDATION_PROCEED, EventType.VALIDATION_BLOCK] = EventType.VALIDATION_PROCEED
    verdict: ValidationVerdict
    check_type: ValidationCheck
    mode: ValidationMode
    reason: Optional[str] = None
    response_time_ms: float

class PnlUpdateEvent(BaseEvent):
    event_type: Literal[EventType.PNL_UPDATE] = EventType.PNL_UPDATE
    profile_id: ProfileId
    symbol: SymbolPair
    gross_pnl: Price
    net_pnl: Price
    pct_return: Percentage

class CircuitBreakerEvent(BaseEvent):
    event_type: Literal[EventType.CIRCUIT_BREAKER_TRIGGERED] = EventType.CIRCUIT_BREAKER_TRIGGERED
    profile_id: ProfileId
    reason: str

class AlertEvent(BaseEvent):
    event_type: Literal[EventType.ALERT_AMBER, EventType.ALERT_RED, EventType.SYSTEM_ALERT, EventType.REGIME_DISAGREEMENT]
    message: str
    level: str
    profile_id: Optional[ProfileId] = None

class ThresholdProximityEvent(BaseEvent):
    event_type: Literal[EventType.THRESHOLD_PROXIMITY] = EventType.THRESHOLD_PROXIMITY
    profile_id: ProfileId
    symbol: SymbolPair
    indicator_name: str
    current_value: Price
    trigger_threshold: Price
    proximity_pct: Percentage


class HITLApprovalRequest(BaseEvent):
    event_type: Literal[EventType.HITL_PENDING] = EventType.HITL_PENDING
    profile_id: ProfileId
    symbol: SymbolPair
    side: OrderSide
    quantity: Quantity
    price: Price
    confidence: float
    trigger_reason: str
    agent_scores: Dict[str, Any] = Field(default_factory=dict)
    risk_metrics: Dict[str, Any] = Field(default_factory=dict)


class HITLApprovalResponse(BaseEvent):
    event_type: Literal[EventType.HITL_RESPONSE] = EventType.HITL_RESPONSE
    request_id: UUID
    status: HITLStatus
    reviewer: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# API Gateway — Profile Models
# ---------------------------------------------------------------------------

class ProfileCreate(BaseModel):
    name: str = Field(default="Untitled Profile", min_length=1, max_length=200)
    rules_json: Dict[str, Any] = Field(default_factory=dict)
    risk_limits: Dict[str, Any] = Field(default_factory=dict)
    allocation_pct: float = Field(default=1.0, ge=0.0, le=100.0)


class ProfileUpdate(BaseModel):
    rules_json: Dict[str, Any]
    is_active: bool = True


class ProfileToggle(BaseModel):
    is_active: bool


class ProfileResponse(BaseModel):
    profile_id: str
    name: str
    is_active: bool
    rules_json: Dict[str, Any]
    allocation_pct: float
    created_at: str
    deleted_at: Optional[str] = None


# ---------------------------------------------------------------------------
# API Gateway — Exchange Key Models
# ---------------------------------------------------------------------------

class ExchangeKeyCreate(BaseModel):
    exchange_id: str
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None


class ExchangeKeyTest(ExchangeKeyCreate):
    pass


class ExchangeKeyResponse(BaseModel):
    id: str
    exchange_name: str
    label: str
    is_active: bool
    created_at: str


# ---------------------------------------------------------------------------
# API Gateway — Auth Models
# ---------------------------------------------------------------------------

class OAuthCallbackRequest(BaseModel):
    """Payload sent from the NextAuth.js frontend after OAuth completion."""
    email: str
    name: str
    image: Optional[str] = None
    provider: str
    provider_account_id: str
    id_token: str


class AuthResponse(BaseModel):
    """JWT tokens returned to the frontend for API authentication."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    display_name: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    """Current user profile returned by /auth/me."""
    user_id: str
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    provider: str


# ---------------------------------------------------------------------------
# API Gateway — Backtest Models
# ---------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    symbol: str = Field(..., example="BTC/USDT")
    strategy_rules: dict = Field(..., example={
        "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
        "logic": "AND",
        "direction": "BUY",
        "base_confidence": 0.85,
    })
    start_date: str = Field(..., example="2025-01-01T00:00:00")
    end_date: str = Field(..., example="2025-06-01T00:00:00")
    slippage_pct: float = Field(default=0.001, ge=0.0, le=0.05)


class BacktestResponse(BaseModel):
    job_id: str
    status: str


# ---------------------------------------------------------------------------
# API Gateway — Agent & Risk Models
# ---------------------------------------------------------------------------

class AgentScore(BaseModel):
    symbol: str
    ta_score: Optional[float] = None
    sentiment_score: Optional[float] = None
    sentiment_confidence: Optional[float] = None
    sentiment_source: Optional[str] = None
    hmm_regime: Optional[str] = None
    hmm_state_index: Optional[int] = None


class RiskStatus(BaseModel):
    profile_id: str
    daily_pnl_pct: float = 0.0
    drawdown_pct: float = 0.0
    allocation_pct: float = 0.0
    circuit_breaker_threshold: Optional[float] = None


# ---------------------------------------------------------------------------
# API Gateway — Command Models
# ---------------------------------------------------------------------------

class CommandIntent(BaseModel):
    natural_language: str


# ---------------------------------------------------------------------------
# Service Models — Tax
# ---------------------------------------------------------------------------

class TaxRequest(BaseModel):
    holding_duration_days: int
    net_pnl: float
    tax_bracket: Optional[str] = None


# ---------------------------------------------------------------------------
# Service Models — Backtesting
# ---------------------------------------------------------------------------

class SweepRequest(BaseModel):
    symbol: str = "BTC/USDT"
    strategy_rules: Dict[str, Any]
    param_grid: Dict[str, List[Any]]
    slippage_pct: float = Field(default=0.001)
    start_date: str = ""
    end_date: str = ""


# ---------------------------------------------------------------------------
# Service Models — SLM Inference
# ---------------------------------------------------------------------------

class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: int = Field(default=256, ge=1, le=4096)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    stop: Optional[list[str]] = None


class CompletionResponse(BaseModel):
    text: str
    tokens_used: int
    latency_ms: float


class SentimentRequest(BaseModel):
    symbol: str
    headlines: list[str]


class SentimentResponse(BaseModel):
    score: float
    confidence: float
    latency_ms: float


# ---------------------------------------------------------------------------
# Validation & Configuration Models
# ---------------------------------------------------------------------------

SUPPORTED_INDICATORS = {'rsi', 'macd.macd_line', 'macd.signal_line', 'macd.histogram', 'atr'}
SUPPORTED_OPERATORS = {'LT', 'GT', 'LTE', 'GTE', 'EQ'}


class RuleCondition(BaseModel):
    indicator: str
    operator: str
    value: float

    @root_validator(pre=True)
    def check_support(cls, values):
        errors = []
        if values.get('indicator') not in SUPPORTED_INDICATORS:
            errors.append(f"Unsupported indicator: {values.get('indicator')}")
        if values.get('operator') not in SUPPORTED_OPERATORS:
            errors.append(f"Unsupported operator: {values.get('operator')}")
        if errors:
            raise ValueError(" | ".join(errors))
        return values


class RuleSchema(BaseModel):
    conditions: List[RuleCondition]
    logic: str
    direction: SignalDirection
    base_confidence: float

    @root_validator(pre=True)
    def check_logic(cls, values):
        if values.get('logic') not in {'AND', 'OR'}:
            raise ValueError("Logic must be AND or OR")
        if not (0.0 <= values.get('base_confidence', -1) <= 1.0):
            raise ValueError("base_confidence must be between 0 and 1")
        if not values.get('conditions'):
            raise ValueError("At least one condition required")
        return values


class QuotaConfig(BaseModel):
    limit: int
    window_sec: int
