import os
import threading
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator, root_validator

from .enums import (
    EventType,
    HITLStatus,
    OrderSide,
    SignalDirection,
    ValidationCheck,
    ValidationMode,
    ValidationVerdict,
)
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


class OrderBookSnapshotEvent(BaseEvent):
    """Top-N levels of an exchange orderbook.

    bids/asks are price-sorted ([price, size] pairs):
      bids descending price (best bid first),
      asks ascending price (best ask first).
    Decimal values cross the wire as strings via msgpack default=str.
    """

    event_type: Literal[EventType.ORDERBOOK_SNAPSHOT] = EventType.ORDERBOOK_SNAPSHOT
    symbol: SymbolPair
    exchange: str
    bids: List[List[Decimal]]
    asks: List[List[Decimal]]


class TradeTickEvent(BaseEvent):
    """A single public trade printed on the exchange tape."""

    event_type: Literal[EventType.TRADE_TICK] = EventType.TRADE_TICK
    symbol: SymbolPair
    exchange: str
    side: Literal["bid", "ask"]
    price: Price
    size: Quantity
    trade_id: Optional[str] = None
    trade_ts_ms: int


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
    # When the user submits manually via POST /orders the api_gateway
    # pre-allocates the order_id so the HTTP response can return it before
    # the executor consumes the event. Strategy/validation publishers leave
    # it None and the executor mints one (uuid.uuid4) as before.
    order_id: Optional[UUID] = None
    # PR1 (real exchange close): when True this order FLATTENS an existing
    # position (reduce-only) rather than opening one. close_position_id links
    # the resulting fill back to the position being closed. A close is published
    # straight to stream:orders by the PositionCloseRequester/api_gateway,
    # bypassing the hot_path gate chain — a same-symbol order would otherwise be
    # blocked by ReentryGate. Defaults keep every existing open path unchanged.
    reduce_only: bool = False
    close_position_id: Optional[UUID] = None
    # Carried through so the close's audit row keeps the trigger distinction
    # (stop_loss / take_profit / time_exit / manual). None for opening orders.
    close_reason: Optional[str] = None


class OrderRejectedEvent(BaseEvent):
    event_type: Literal[EventType.ORDER_REJECTED] = EventType.ORDER_REJECTED
    profile_id: ProfileId
    symbol: SymbolPair
    reason: str
    # Echoed for the close path so the requester can correlate a rejected
    # reduce-only order back to the position and revert PENDING_CLOSE -> OPEN.
    order_id: Optional[UUID] = None
    reduce_only: bool = False
    close_position_id: Optional[UUID] = None


class OrderExecutedEvent(BaseEvent):
    event_type: Literal[EventType.ORDER_EXECUTED] = EventType.ORDER_EXECUTED
    order_id: UUID
    profile_id: ProfileId
    symbol: SymbolPair
    side: OrderSide
    fill_price: Price
    quantity: Quantity
    # PR1: set when this fill CLOSED a position. The pnl close consumer
    # finalises the DB close using fill_price as the authoritative exit price.
    reduce_only: bool = False
    close_position_id: Optional[UUID] = None
    close_reason: Optional[str] = None
    # PR5: adverse fill-vs-intended cost on this fill (signed; positive = cost).
    # Already reflected in realized_pnl via fill_price — carried for attribution.
    slippage_cost: Optional[Price] = None


class ValidationRequestEvent(BaseEvent):
    event_type: Literal[EventType.VALIDATION_PROCEED, EventType.VALIDATION_BLOCK] = (
        EventType.VALIDATION_PROCEED
    )
    profile_id: ProfileId
    symbol: SymbolPair
    check_type: ValidationCheck
    payload: Dict[str, Any]


class ValidationResponseEvent(BaseEvent):
    event_type: Literal[EventType.VALIDATION_PROCEED, EventType.VALIDATION_BLOCK] = (
        EventType.VALIDATION_PROCEED
    )
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
    net_pnl: Price = Field(
        description=(
            "PRE-tax net PnL (gross_pnl minus total fees). The publisher has "
            "always passed PnLSnapshot.net_pre_tax here — kept as-is for "
            "backward compatibility. Prefer net_pre_tax/net_post_tax."
        )
    )
    pct_return: Percentage
    # FE-W2: per-position identity + full fee/tax breakdown the dashboard
    # reads. Events are per-position — position_id is the consumer-side key.
    # Optional so payloads predating 2026-06 still validate.
    position_id: Optional[str] = None
    fees: Optional[Price] = None
    net_pre_tax: Optional[Price] = None
    net_post_tax: Optional[Price] = None
    tax_estimate: Optional[Price] = None


class CircuitBreakerEvent(BaseEvent):
    event_type: Literal[EventType.CIRCUIT_BREAKER_TRIGGERED] = (
        EventType.CIRCUIT_BREAKER_TRIGGERED
    )
    profile_id: ProfileId
    reason: str


class AlertEvent(BaseEvent):
    event_type: Literal[
        EventType.ALERT_AMBER,
        EventType.ALERT_RED,
        EventType.SYSTEM_ALERT,
        EventType.REGIME_DISAGREEMENT,
    ]
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
    # Optional risk-limits update. Merges with stored values — only the keys
    # present in the payload overwrite. Validated by RiskLimitsPayload upstream.
    risk_limits: Optional[Dict[str, Any]] = None
    # Optional allocation_pct update (notional scale, 1.0 = $10k base).
    allocation_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class ProfileToggle(BaseModel):
    is_active: bool


class ProfileResponse(BaseModel):
    profile_id: str
    name: str
    is_active: bool
    # Was StrategyRulesInput — now a plain dict so the route can pre-clean it
    # (drop nulls + irrelevant fields based on shape) before returning. Keeping
    # the strict model would force Pydantic to serialise null direction/match_mode
    # for both-legs profiles, polluting the editor with phantom nulls.
    rules_json: Dict[str, Any] = Field(default_factory=dict)
    rules_json_canonical: Dict[str, Any] = Field(default_factory=dict)
    allocation_pct: Percentage
    risk_limits: Dict[str, Any] = Field(default_factory=dict)
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

# Walk-forward compute budget — single source of truth, shared with the
# worker-side parser (services/backtesting/src/walk_forward.py imports these).
# Without an upper bound an authenticated user can request e.g. train_bars=1
# over a year of 1m candles with a dense param_grid: ~n_bars windows x grid
# combinations, each a full engine pass, on a SINGLE serial worker — queue
# starvation. 500_000 bars ≈ one year of 1m candles.
WALK_FORWARD_MAX_BARS = 500_000
WALK_FORWARD_MAX_PARAM_COMBOS = 100

# EN-W2 exit-band sweep: the ONLY risk_limits keys the sweep machinery may
# vary. These are exactly the keys the shared exit policy
# (libs/core/exit_policy.thresholds_from_risk_limits) reads — sweeping any
# other risk_limits key (max_allocation_pct, circuit_breaker_*, ...) would be
# a silent no-op in the engines, so it is rejected loudly instead.
RISK_LIMITS_GRID_KEYS = frozenset(
    {"stop_loss_pct", "take_profit_pct", "max_holding_hours"}
)


def risk_limits_grid_combinations(risk_limits_grid: Optional[Dict[str, Any]]) -> int:
    """Validate a risk_limits_grid and return its cartesian cardinality.

    Shape: {stop_loss_pct|take_profit_pct|max_holding_hours: [positive
    numbers]}. Values may arrive as JSON numbers or numeric strings; they are
    str()-converted before Decimal at the merge site (Decimal contract), so
    only positivity/finiteness is checked here. None/empty contributes 1.
    """
    if not risk_limits_grid:
        return 1
    combos = 1
    for key, values in risk_limits_grid.items():
        if key not in RISK_LIMITS_GRID_KEYS:
            raise ValueError(
                f"risk_limits_grid key '{key}' is not sweepable; "
                f"allowed keys: {sorted(RISK_LIMITS_GRID_KEYS)}"
            )
        if not isinstance(values, list) or not values:
            raise ValueError(f"risk_limits_grid['{key}'] must be a non-empty list")
        for v in values:
            # bool is an int subclass — reject it explicitly.
            if isinstance(v, bool):
                raise ValueError(
                    f"risk_limits_grid['{key}'] values must be positive numbers"
                )
            try:
                d = Decimal(str(v))
            except (ArithmeticError, TypeError, ValueError):
                raise ValueError(
                    f"risk_limits_grid['{key}'] values must be positive numbers"
                )
            if not d.is_finite() or d <= 0:
                raise ValueError(
                    f"risk_limits_grid['{key}'] values must be positive numbers"
                )
        combos *= len(values)
    return combos


def walk_forward_grid_combinations(
    param_grid: Optional[Dict[str, Any]],
    risk_limits_grid: Optional[Dict[str, Any]] = None,
) -> int:
    """Combined cartesian cardinality of a run_sweep-shaped param_grid and an
    optional risk_limits_grid (rule combos x exit-band combos).

    Raises ValueError when a param_grid value is not a non-empty list — the
    same shape run_sweep requires (itertools.product over the value lists) —
    or when risk_limits_grid fails risk_limits_grid_combinations validation.
    An absent/None grid contributes a factor of 1.
    """
    combos = 1
    if param_grid:
        for key, values in param_grid.items():
            if not isinstance(values, list) or not values:
                raise ValueError(
                    f"walk_forward param_grid['{key}'] must be a non-empty list"
                )
            combos *= len(values)
    return combos * risk_limits_grid_combinations(risk_limits_grid)


class BacktestRequest(BaseModel):
    symbol: str = Field(..., example="BTC/USDT")
    strategy_rules: "StrategyRulesInput"
    start_date: str = Field(..., example="2025-01-01T00:00:00")
    end_date: str = Field(..., example="2025-06-01T00:00:00")
    timeframe: Literal["1m", "5m", "15m", "1h", "1d"] = Field(default="1m")
    slippage_pct: Percentage = Field(default=Decimal("0.001"), ge=0, le=Decimal("0.05"))
    # EN-W1 exit fidelity: profile whose risk_limits drive the SL/TP/time-exit
    # policy in the sim. When profile_id is set and risk_limits omitted, the
    # gateway loads the profile's risk_limits before enqueueing.
    profile_id: Optional[str] = Field(default=None)
    # Explicit risk_limits override (RiskLimitsPayload shape: stop_loss_pct /
    # take_profit_pct / max_holding_hours ...). None → exit-policy defaults.
    risk_limits: Optional[Dict[str, Any]] = Field(default=None)
    # EN-W1 walk-forward config: {train_bars, test_bars, step_bars?,
    # param_grid?, risk_limits_grid?}.
    walk_forward: Optional[Dict[str, Any]] = Field(default=None)
    # EN-W2 exit-band sweep dimension: {stop_loss_pct|take_profit_pct|
    # max_holding_hours: [positive numbers]}. Only meaningful with a
    # walk_forward config (the queue serves no plain-sweep path); the
    # walk_forward dict may instead embed its own risk_limits_grid, which
    # wins over this top-level field.
    risk_limits_grid: Optional[Dict[str, List[Any]]] = Field(default=None)

    @model_validator(mode="after")
    def _validate_optional_payloads(self):
        if self.risk_limits is not None:
            # Raises pydantic.ValidationError (→ 422) on garbage shapes;
            # RiskLimitsPayload is defined later in this module, resolved at
            # call time.
            RiskLimitsPayload.model_validate(self.risk_limits)
        if self.risk_limits_grid is not None:
            # Validates allowed keys + positive-number values (raises → 422).
            risk_limits_grid_combinations(self.risk_limits_grid)
            if self.walk_forward is None:
                # A grid without walk_forward would be a silent no-op on the
                # worker (single engine run) — reject loudly at the edge.
                raise ValueError("risk_limits_grid requires a walk_forward config")
        if self.walk_forward is not None:
            for key in ("train_bars", "test_bars"):
                if not isinstance(self.walk_forward.get(key), int) or (
                    self.walk_forward[key] <= 0
                ):
                    raise ValueError(f"walk_forward.{key} must be a positive integer")
            # Compute budget (DoS guard): reject unbounded window/sweep
            # requests at the API edge (422); the worker-side parser
            # re-enforces the same caps as defence in depth.
            step = self.walk_forward.get("step_bars")
            if step is not None and (not isinstance(step, int) or step <= 0):
                raise ValueError("walk_forward.step_bars must be a positive integer")
            for key in ("train_bars", "test_bars", "step_bars"):
                val = self.walk_forward.get(key)
                if isinstance(val, int) and val > WALK_FORWARD_MAX_BARS:
                    raise ValueError(
                        f"walk_forward.{key} exceeds the maximum of "
                        f"{WALK_FORWARD_MAX_BARS} bars"
                    )
            grid = self.walk_forward.get("param_grid")
            if grid is not None and not isinstance(grid, dict):
                raise ValueError("walk_forward.param_grid must be a dict")
            wf_risk_grid = self.walk_forward.get("risk_limits_grid")
            if wf_risk_grid is not None and not isinstance(wf_risk_grid, dict):
                raise ValueError("walk_forward.risk_limits_grid must be a dict")
            # Embedded grid wins over the top-level field (mirrors the
            # worker-side resolution in services/backtesting job_runner).
            effective_risk_grid = (
                wf_risk_grid if wf_risk_grid is not None else self.risk_limits_grid
            )
            # Budget on the COMBINED cardinality (rule combos x exit-band
            # combos) — each pair is a full engine pass per window.
            combos = walk_forward_grid_combinations(grid, effective_risk_grid)
            if combos > WALK_FORWARD_MAX_PARAM_COMBOS:
                raise ValueError(
                    f"walk_forward param_grid x risk_limits_grid expands to "
                    f"{combos} combinations; maximum is "
                    f"{WALK_FORWARD_MAX_PARAM_COMBOS}"
                )
        return self


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
    "rsi",
    "macd.macd_line",
    "macd.signal_line",
    "macd.histogram",
    "atr",
    "adx",
    "bb.pct_b",
    "bb.bandwidth",
    "bb.upper",
    "bb.lower",
    "obv",
    "choppiness",
    "vwap",
    "keltner.upper",
    "keltner.middle",
    "keltner.lower",
    "rvol",
    "z_score",
    "hurst",
}
SUPPORTED_OPERATORS = {"LT", "GT", "LTE", "GTE", "EQ"}


class RuleCondition(BaseModel):
    indicator: str
    operator: str
    value: float

    @root_validator(pre=True)
    def check_support(cls, values):
        errors = []
        if values.get("indicator") not in SUPPORTED_INDICATORS:
            errors.append(f"Unsupported indicator: {values.get('indicator')}")
        if values.get("operator") not in SUPPORTED_OPERATORS:
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
        if values.get("logic") not in {"AND", "OR"}:
            raise ValueError("Logic must be AND or OR")
        if not (0.0 <= values.get("base_confidence", -1) <= 1.0):
            raise ValueError("base_confidence must be between 0 and 1")
        if not values.get("conditions"):
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
_INDICATOR_CANONICAL_TO_USER: Dict[str, str] = {
    v: k for k, v in _INDICATOR_USER_TO_CANONICAL.items()
}

_COMPARISON_TO_OPERATOR: Dict[str, str] = {
    "above": "GT",
    "below": "LT",
    "at_or_above": "GTE",
    "at_or_below": "LTE",
    "equals": "EQ",
}
_OPERATOR_TO_COMPARISON: Dict[str, str] = {
    v: k for k, v in _COMPARISON_TO_OPERATOR.items()
}

_DIRECTION_USER_TO_CANONICAL: Dict[str, str] = {"long": "BUY", "short": "SELL"}
_DIRECTION_CANONICAL_TO_USER: Dict[str, str] = {
    v: k for k, v in _DIRECTION_USER_TO_CANONICAL.items()
}

_MATCH_MODE_TO_LOGIC: Dict[str, str] = {"all": "AND", "any": "OR"}
_LOGIC_TO_MATCH_MODE: Dict[str, str] = {v: k for k, v in _MATCH_MODE_TO_LOGIC.items()}


class StrategySignal(BaseModel):
    indicator: Literal[
        "rsi",
        "atr",
        "macd_line",
        "macd_signal",
        "macd_histogram",
        "vwap",
        "keltner.upper",
        "keltner.middle",
        "keltner.lower",
        "rvol",
        "z_score",
        "hurst",
    ]
    comparison: Literal["above", "below", "at_or_above", "at_or_below", "equals"]
    threshold: float


_REGIME_NAMES = Literal[
    "TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND", "HIGH_VOLATILITY", "CRISIS"
]


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
        legacy_complete = (
            bool(self.signals)
            and self.direction is not None
            and self.match_mode is not None
        )
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


def _signals_to_canonical_conditions(
    signals: List[StrategySignal],
) -> List[Dict[str, Any]]:
    return [
        {
            "indicator": _INDICATOR_USER_TO_CANONICAL[s.indicator],
            "operator": _COMPARISON_TO_OPERATOR[s.comparison],
            "value": s.threshold,
        }
        for s in signals
    ]


def _canonical_conditions_to_signals(
    conditions: List[Dict[str, Any]]
) -> List[StrategySignal]:
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
        primary_mode = (
            rules.match_mode_long if rules.entry_long else rules.match_mode_short
        )
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
            entry_long=(
                _canonical_conditions_to_signals(long_block["conditions"])
                if has_long
                else None
            ),
            match_mode_long=(
                _LOGIC_TO_MATCH_MODE[long_block["logic"]] if has_long else None
            ),
            entry_short=(
                _canonical_conditions_to_signals(short_block["conditions"])
                if has_short
                else None
            ),
            match_mode_short=(
                _LOGIC_TO_MATCH_MODE[short_block["logic"]] if has_short else None
            ),
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


class KillSwitchLogEntry(BaseModel):
    """One entry of the kill-switch activity log (praxis:kill_switch:log).

    Writers vary by era: KillSwitch.set_level writes `actor`, the legacy
    activate/deactivate paths wrote `activated_by`/`deactivated_by` — all
    three are declared explicitly so the response stays a WHITELIST.
    Deliberately NO extra="allow": the threat model assumes Redis content can
    be malformed/tampered, so unknown fields in the list entries must never
    pass through to clients (CWE-200). `timestamp` is epoch seconds
    (time.time()).
    """

    action: str = ""
    reason: Optional[str] = None
    actor: Optional[str] = None
    activated_by: Optional[str] = None
    deactivated_by: Optional[str] = None
    timestamp: Optional[float] = None


class KillSwitchStatusResponse(BaseModel):
    active: bool
    reason: Optional[str] = None
    activated_at: Optional[str] = None
    # PR3 tiered halt: NONE/STOP_OPENING/DE_RISK/NEUTRALIZE/FLATTEN. `active` stays
    # True for STOP_OPENING and above for backward compatibility. Defaulted (not
    # Optional) — FastAPI response_model filtering must never strip the tier
    # the FE-W1 graduated control reads (KillSwitch.status always returns it).
    level: str = "NONE"
    # Recent activity log (up to 10 entries) — KillSwitch.status returns it and
    # the FE renders it; without this field response_model filtering dropped it.
    recent_log: List[KillSwitchLogEntry] = Field(default_factory=list)


class KillSwitchToggleResponse(BaseModel):
    status: str
    reason: Optional[str] = None
    level: Optional[str] = None


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


# ---------------------------------------------------------------------------
# Phase D: Validated financial JSON structures (replacing raw json.loads)
# ---------------------------------------------------------------------------


class AgentScorePayload(BaseModel):
    """Validated agent score from Redis (ta, sentiment, debate).

    `source` identifies the producer / failure mode. Sentiment uses
    "cloud" / "local" / "cache" for healthy paths and "llm_error" / "fallback"
    for degraded paths — consumers must drop the latter to avoid feeding
    fake votes into the meta-learning loop.
    """

    score: float
    direction: Optional[str] = None
    confidence: Optional[float] = None
    regime: Optional[str] = None
    state_index: Optional[int] = None
    source: Optional[str] = None
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


# Risk-limit defaults. The SINGLE authority is `libs.config.settings`
# (registry row 67 / locked ruling D-D, 2026-06-13): the live ExitMonitor,
# the shared exit_policy, and both backtest engines already resolve missing
# keys from settings. This mapping is a str-encoded VIEW of those settings,
# kept for consumers that lift values straight into Decimal — do NOT hardcode
# numbers here, and do not add keys that settings does not define.
# Import is region-local so this lane's edits stay inside the
# RiskLimitsPayload/DEFAULT_RISK_LIMITS region (parallel-lane file ownership).
from libs.config import settings as _settings  # noqa: E402

DEFAULT_RISK_LIMITS: Dict[str, str] = {
    "max_drawdown_pct": str(_settings.DEFAULT_MAX_DRAWDOWN_PCT),
    "stop_loss_pct": str(_settings.DEFAULT_STOP_LOSS_PCT),
    "take_profit_pct": str(_settings.DEFAULT_TAKE_PROFIT_PCT),
    "max_holding_hours": str(_settings.DEFAULT_MAX_HOLDING_HOURS),
    "max_allocation_pct": str(_settings.DEFAULT_MAX_ALLOCATION_PCT),
    "circuit_breaker_daily_loss_pct": str(_settings.CIRCUIT_BREAKER_DAILY_LOSS_PCT),
}


class RiskLimitsPayload(BaseModel):
    """Validated risk limits JSON from a profile (also the BacktestRequest
    risk_limits override shape). Defaults source from settings via
    DEFAULT_RISK_LIMITS — settings is the single authority (ruling D-D).

    Domain bounds (registry row 66 / ruling D-E): pcts in (0, 1], hours > 0.
    Every existing trading_profiles.risk_limits row was verified in-bounds
    before tightening (2026-06-13: 9/9 rows pass). Floats here are the
    documented JSON-boundary convention — downstream consumers convert to
    Decimal at the calculation site (see exit_policy.thresholds_from_risk_limits).
    """

    max_drawdown_pct: float = Field(
        default=float(DEFAULT_RISK_LIMITS["max_drawdown_pct"]), gt=0, le=1  # float-ok
    )
    stop_loss_pct: float = Field(
        default=float(DEFAULT_RISK_LIMITS["stop_loss_pct"]), gt=0, le=1  # float-ok
    )
    take_profit_pct: float = Field(
        default=float(DEFAULT_RISK_LIMITS["take_profit_pct"]), gt=0, le=1  # float-ok
    )
    max_holding_hours: float = Field(
        default=float(DEFAULT_RISK_LIMITS["max_holding_hours"]), gt=0  # float-ok
    )
    max_allocation_pct: float = Field(
        default=float(DEFAULT_RISK_LIMITS["max_allocation_pct"]), gt=0, le=1  # float-ok
    )
    circuit_breaker_daily_loss_pct: float = Field(
        default=float(  # float-ok: JSON-boundary payload convention
            DEFAULT_RISK_LIMITS["circuit_breaker_daily_loss_pct"]
        ),
        gt=0,
        le=1,
    )
    # extra="allow" dropped per ruling D-E — unknown keys are now ignored
    # (Pydantic default) instead of being carried as untyped extras.


# Sensible defaults for user-level risk caps; expressed in the same units as the
# editable form on /settings/risk. Floats at the API boundary follow the same
# convention as RiskLimitsPayload — downstream consumers convert to Decimal at
# the calculation site.
DEFAULT_USER_RISK_DEFAULTS: Dict[str, float] = {
    "max_position_size_pct": 0.10,  # 10% of free capital × confidence
    "max_leverage": 1.0,  # spot-only by default
    "max_daily_loss_pct": 0.02,  # 2% halts new orders for the day
    "rate_limit_orders_per_min": 30,  # sliding-window cap
    "auto_pause_drawdown_pct": 0.05,  # 5% drawdown trip
}


class UserRiskDefaultsPayload(BaseModel):
    """User-level risk caps that apply when a profile doesn't override them.

    Scope: persisted defaults for *new* profiles. Recompile fan-out to running
    profiles is a separate project. See migration 021_user_risk_defaults.sql
    and `docs/design/05-surface-specs/06-profiles-settings.md` §5.
    """

    max_position_size_pct: float = Field(
        default=DEFAULT_USER_RISK_DEFAULTS["max_position_size_pct"],
        ge=0.0,
        le=1.0,
        description="Per-trade cap as fraction of free capital (0.10 = 10%).",
    )
    max_leverage: float = Field(
        default=DEFAULT_USER_RISK_DEFAULTS["max_leverage"],
        ge=1.0,
        le=20.0,
        description="Hard ceiling on notional / margin per position.",
    )
    max_daily_loss_pct: float = Field(
        default=DEFAULT_USER_RISK_DEFAULTS["max_daily_loss_pct"],
        ge=0.0,
        le=1.0,
        description="Halts new orders for the day once breached.",
    )
    rate_limit_orders_per_min: int = Field(
        default=DEFAULT_USER_RISK_DEFAULTS["rate_limit_orders_per_min"],
        ge=1,
        le=600,
        description="Sliding-window cap enforced by rate_limiter service.",
    )
    auto_pause_drawdown_pct: float = Field(
        default=DEFAULT_USER_RISK_DEFAULTS["auto_pause_drawdown_pct"],
        ge=0.0,
        le=1.0,
        description="Drawdown threshold that auto-pauses the affected profile.",
    )
    model_config = ConfigDict(extra="forbid")


class UserRiskDefaultsResponse(BaseModel):
    """GET /risk-defaults response."""

    defaults: UserRiskDefaultsPayload
    updated_at: Optional[str] = (
        None  # ISO8601; null if never saved (defaults returned).
    )
    applies_to: Literal["new_profiles_only"] = (
        "new_profiles_only"  # Honest scope tag for the FE banner.
    )
