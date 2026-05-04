from decimal import Decimal
from typing import Any, Dict, List, Optional, Literal
from uuid import UUID, uuid4
import os
import threading
from pydantic import BaseModel, Field, ConfigDict, model_validator, root_validator

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
    decision_event_id: Optional[UUID] = None

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
    rules_json: "StrategyRulesInput"
    risk_limits: Dict[str, Any] = Field(default_factory=dict)
    allocation_pct: float = Field(default=1.0, ge=0.0, le=100.0)


class ProfileUpdate(BaseModel):
    rules_json: "StrategyRulesInput"
    is_active: bool = True


class ProfileToggle(BaseModel):
    is_active: bool


class ProfileResponse(BaseModel):
    profile_id: str
    name: str
    is_active: bool
    rules_json: "StrategyRulesInput"
    rules_json_canonical: Dict[str, Any] = Field(default_factory=dict)
    allocation_pct: Percentage
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
    strategy_rules: "StrategyRulesInput"
    start_date: str = Field(..., example="2025-01-01T00:00:00")
    end_date: str = Field(..., example="2025-06-01T00:00:00")
    timeframe: Literal["1m", "5m", "15m", "1h", "1d"] = Field(default="1m")
    slippage_pct: Percentage = Field(default=Decimal("0.001"), ge=0, le=Decimal("0.05"))


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
    grammar: Optional[str] = None  # GBNF grammar to constrain output (llama.cpp only)


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

SUPPORTED_INDICATORS = {
    'rsi', 'macd.macd_line', 'macd.signal_line', 'macd.histogram', 'atr',
    'adx', 'bb.pct_b', 'bb.bandwidth', 'bb.upper', 'bb.lower', 'obv', 'choppiness',
    'vwap', 'keltner.upper', 'keltner.middle', 'keltner.lower',
    'rvol', 'z_score', 'hurst',
}
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


# ---------------------------------------------------------------------------
# Strategy Rules — User-facing schema + canonical transformer
# ---------------------------------------------------------------------------
# The user-facing shape uses trading vocabulary. The canonical shape (RuleSchema
# above) is what hot_path / RuleCompiler consume. The API gateway accepts
# StrategyRulesInput, transforms to canonical at write time, and reverses on read.

_INDICATOR_USER_TO_CANONICAL: Dict[str, str] = {
    "rsi": "rsi",
    "atr": "atr",
    "macd_line": "macd.macd_line",
    "macd_signal": "macd.signal_line",
    "macd_histogram": "macd.histogram",
    # C.2 additions — user-facing names match canonical names (with dots).
    "vwap": "vwap",
    "keltner.upper": "keltner.upper",
    "keltner.middle": "keltner.middle",
    "keltner.lower": "keltner.lower",
    "rvol": "rvol",
    "z_score": "z_score",
    "hurst": "hurst",
}
_INDICATOR_CANONICAL_TO_USER: Dict[str, str] = {v: k for k, v in _INDICATOR_USER_TO_CANONICAL.items()}

_COMPARISON_TO_OPERATOR: Dict[str, str] = {
    "above": "GT",
    "below": "LT",
    "at_or_above": "GTE",
    "at_or_below": "LTE",
    "equals": "EQ",
}
_OPERATOR_TO_COMPARISON: Dict[str, str] = {v: k for k, v in _COMPARISON_TO_OPERATOR.items()}

_DIRECTION_USER_TO_CANONICAL: Dict[str, str] = {"long": "BUY", "short": "SELL"}
_DIRECTION_CANONICAL_TO_USER: Dict[str, str] = {v: k for k, v in _DIRECTION_USER_TO_CANONICAL.items()}

_MATCH_MODE_TO_LOGIC: Dict[str, str] = {"all": "AND", "any": "OR"}
_LOGIC_TO_MATCH_MODE: Dict[str, str] = {v: k for k, v in _MATCH_MODE_TO_LOGIC.items()}


class StrategySignal(BaseModel):
    indicator: Literal[
        "rsi", "atr",
        "macd_line", "macd_signal", "macd_histogram",
        "vwap",
        "keltner.upper", "keltner.middle", "keltner.lower",
        "rvol", "z_score", "hurst",
    ]
    comparison: Literal["above", "below", "at_or_above", "at_or_below", "equals"]
    threshold: float


_REGIME_NAMES = Literal["TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND", "HIGH_VOLATILITY", "CRISIS"]


class StrategyRulesInput(BaseModel):
    """User-facing strategy DSL. Validated, then transformed to the canonical
    RuleSchema shape consumed by hot_path.

    Two valid shapes:

    1. Legacy single-direction:  direction + match_mode + signals
    2. Both-legs (C.1):          entry_long and/or entry_short, with their own
                                 match_mode_long / match_mode_short

    `confidence` and `preferred_regimes` are shared. The shapes are mutually
    exclusive at the field level but a profile that provides ONLY entry_long
    (or ONLY entry_short) is still a valid both-legs profile — it just emits
    one direction and never the other.
    """
    # Legacy single-direction shape — every field optional now that both-legs
    # exists, but the validator below still requires *one* of the two shapes.
    direction: Optional[Literal["long", "short"]] = None
    match_mode: Optional[Literal["all", "any"]] = None
    signals: List[StrategySignal] = Field(default_factory=list)

    # Both-legs shape (C.1). Either or both may be set.
    entry_long: Optional[List[StrategySignal]] = None
    entry_short: Optional[List[StrategySignal]] = None
    match_mode_long: Optional[Literal["all", "any"]] = None
    match_mode_short: Optional[Literal["all", "any"]] = None

    # Shared
    confidence: float = Field(ge=0.0, le=1.0)
    # C.4: optional regime allowlist. Empty list = profile is regime-agnostic.
    # When set, the hot-path short-circuits with BLOCKED_REGIME_MISMATCH (and
    # shadow=true) whenever the resolved live regime is not in this list.
    preferred_regimes: List[_REGIME_NAMES] = Field(default_factory=list)

    @model_validator(mode="after")
    def _at_least_one_leg(self):
        legacy_complete = bool(self.signals) and self.direction is not None and self.match_mode is not None
        new_any_leg = bool(self.entry_long) or bool(self.entry_short)
        if not legacy_complete and not new_any_leg:
            raise ValueError(
                "Strategy rules must declare either legacy direction+match_mode+signals "
                "OR at least one of entry_long / entry_short."
            )
        # If both-legs shape is in use, each declared leg must have a match_mode.
        if self.entry_long and not self.match_mode_long:
            raise ValueError("entry_long requires match_mode_long")
        if self.entry_short and not self.match_mode_short:
            raise ValueError("entry_short requires match_mode_short")
        return self


def _signals_to_canonical_conditions(signals: List[StrategySignal]) -> List[Dict[str, Any]]:
    return [
        {
            "indicator": _INDICATOR_USER_TO_CANONICAL[s.indicator],
            "operator": _COMPARISON_TO_OPERATOR[s.comparison],
            "value": s.threshold,
        }
        for s in signals
    ]


def _canonical_conditions_to_signals(conditions: List[Dict[str, Any]]) -> List[StrategySignal]:
    return [
        StrategySignal(
            indicator=_INDICATOR_CANONICAL_TO_USER[c["indicator"]],
            comparison=_OPERATOR_TO_COMPARISON[c["operator"]],
            threshold=float(c["value"]),
        )
        for c in conditions
    ]


def strategy_rules_to_canonical(rules: StrategyRulesInput) -> Dict[str, Any]:
    """User-facing → canonical (what hot_path / RuleCompiler consume).

    Always emits the legacy keys (logic / direction / conditions) because the
    profile loader's required-keys check and the RuleCompiler both still rely
    on them. When both-legs is in use, those legacy keys are populated from
    the long leg if present, else the short leg — and a separate `entry_long`
    / `entry_short` block is added so the evaluator can see both legs.
    """
    use_both_legs = rules.entry_long is not None or rules.entry_short is not None

    if use_both_legs:
        primary_signals = rules.entry_long if rules.entry_long else rules.entry_short
        primary_mode = rules.match_mode_long if rules.entry_long else rules.match_mode_short
        primary_direction = "long" if rules.entry_long else "short"
        canonical: Dict[str, Any] = {
            "direction": _DIRECTION_USER_TO_CANONICAL[primary_direction],
            "logic": _MATCH_MODE_TO_LOGIC[primary_mode],
            "base_confidence": rules.confidence,
            "conditions": _signals_to_canonical_conditions(primary_signals),
        }
        if rules.entry_long:
            canonical["entry_long"] = {
                "logic": _MATCH_MODE_TO_LOGIC[rules.match_mode_long],
                "conditions": _signals_to_canonical_conditions(rules.entry_long),
            }
        if rules.entry_short:
            canonical["entry_short"] = {
                "logic": _MATCH_MODE_TO_LOGIC[rules.match_mode_short],
                "conditions": _signals_to_canonical_conditions(rules.entry_short),
            }
    else:
        canonical = {
            "direction": _DIRECTION_USER_TO_CANONICAL[rules.direction],
            "logic": _MATCH_MODE_TO_LOGIC[rules.match_mode],
            "base_confidence": rules.confidence,
            "conditions": _signals_to_canonical_conditions(rules.signals),
        }

    if rules.preferred_regimes:
        canonical["preferred_regimes"] = list(rules.preferred_regimes)
    return canonical


def strategy_rules_from_canonical(canonical: Dict[str, Any]) -> StrategyRulesInput:
    """Canonical → user-facing (for serializing back to the frontend).

    Detects the both-legs shape via the presence of `entry_long` or
    `entry_short` keys; otherwise produces the legacy single-direction form.
    """
    has_long = "entry_long" in canonical
    has_short = "entry_short" in canonical
    confidence = float(canonical["base_confidence"])
    preferred = list(canonical.get("preferred_regimes", []))

    if has_long or has_short:
        long_block = canonical.get("entry_long") or {}
        short_block = canonical.get("entry_short") or {}
        return StrategyRulesInput(
            direction=None,
            match_mode=None,
            signals=[],
            entry_long=_canonical_conditions_to_signals(long_block["conditions"]) if has_long else None,
            match_mode_long=_LOGIC_TO_MATCH_MODE[long_block["logic"]] if has_long else None,
            entry_short=_canonical_conditions_to_signals(short_block["conditions"]) if has_short else None,
            match_mode_short=_LOGIC_TO_MATCH_MODE[short_block["logic"]] if has_short else None,
            confidence=confidence,
            preferred_regimes=preferred,
        )

    # Legacy single-direction shape.
    return StrategyRulesInput(
        direction=_DIRECTION_CANONICAL_TO_USER[canonical["direction"]],
        match_mode=_LOGIC_TO_MATCH_MODE[canonical["logic"]],
        confidence=confidence,
        signals=_canonical_conditions_to_signals(canonical["conditions"]),
        preferred_regimes=preferred,
    )


# Resolve forward references on models declared above StrategyRulesInput.
ProfileCreate.model_rebuild()
ProfileUpdate.model_rebuild()
ProfileResponse.model_rebuild()
BacktestRequest.model_rebuild()


class QuotaConfig(BaseModel):
    limit: int
    window_sec: int


# ---------------------------------------------------------------------------
# Phase C response models — prevent internal column leakage
# ---------------------------------------------------------------------------

class KillSwitchStatusResponse(BaseModel):
    active: bool
    reason: Optional[str] = None
    activated_at: Optional[str] = None

class KillSwitchToggleResponse(BaseModel):
    status: str
    reason: Optional[str] = None

class ExchangeTestResponse(BaseModel):
    status: str
    message: str

class RiskCheckResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None

class TaxEstimateResponse(BaseModel):
    estimated_tax: Decimal
    effective_rate: Decimal
    classification: str

class SweepResultItem(BaseModel):
    model_config = ConfigDict(extra="allow")

class BacktestSweepResponse(BaseModel):
    job_id: str
    symbol: str
    num_combinations: int
    results: List[Any]


# ---------------------------------------------------------------------------
# Phase D: Validated financial JSON structures (replacing raw json.loads)
# ---------------------------------------------------------------------------

class AgentScorePayload(BaseModel):
    """Validated agent score from Redis (ta, sentiment, debate)."""
    score: float
    direction: Optional[str] = None
    confidence: Optional[float] = None
    regime: Optional[str] = None
    state_index: Optional[int] = None
    model_config = ConfigDict(extra="allow")


class DailyPnlPayload(BaseModel):
    """Validated daily PnL data from Redis."""
    total_pct: str  # stored as string Decimal

    def total_pct_decimal(self) -> Decimal:
        return Decimal(self.total_pct)


class DrawdownPayload(BaseModel):
    """Validated drawdown data from Redis."""
    drawdown_pct: str  # stored as string Decimal

    def drawdown_pct_decimal(self) -> Decimal:
        return Decimal(self.drawdown_pct)


class AllocationPayload(BaseModel):
    """Validated allocation data from Redis."""
    allocation_pct: str  # stored as string Decimal

    def allocation_pct_decimal(self) -> Decimal:
        return Decimal(self.allocation_pct)


# Single source of truth for risk-limits defaults. Stored as str so consumers
# can lift directly into Decimal without losing precision.
DEFAULT_RISK_LIMITS: Dict[str, str] = {
    "max_drawdown_pct": "0.10",
    "stop_loss_pct": "0.05",
    "take_profit_pct": "0.015",
    "max_holding_hours": "48.0",
    "max_allocation_pct": "1.0",
    "circuit_breaker_daily_loss_pct": "0.02",
}


class RiskLimitsPayload(BaseModel):
    """Validated risk limits JSON from profile. Defaults sourced from DEFAULT_RISK_LIMITS."""
    max_drawdown_pct: float = Field(default=float(DEFAULT_RISK_LIMITS["max_drawdown_pct"]))
    stop_loss_pct: float = Field(default=float(DEFAULT_RISK_LIMITS["stop_loss_pct"]))
    take_profit_pct: float = Field(default=float(DEFAULT_RISK_LIMITS["take_profit_pct"]))
    max_holding_hours: float = Field(default=float(DEFAULT_RISK_LIMITS["max_holding_hours"]))
    max_allocation_pct: float = Field(default=float(DEFAULT_RISK_LIMITS["max_allocation_pct"]))
    circuit_breaker_daily_loss_pct: float = Field(default=float(DEFAULT_RISK_LIMITS["circuit_breaker_daily_loss_pct"]))
    model_config = ConfigDict(extra="allow")
