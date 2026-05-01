from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

from .enums import OrderSide, OrderStatus, PositionStatus
from .types import ExchangeName, Percentage, Price, ProfileId, Quantity, SymbolPair, Timestamp

@dataclass(frozen=True, slots=True)
class Tick:
    symbol: SymbolPair
    exchange: ExchangeName
    timestamp: Timestamp
    price: Price
    volume: Quantity

@dataclass(frozen=True, slots=True)
class NormalisedTick:
    symbol: SymbolPair
    exchange: ExchangeName
    timestamp: Timestamp
    price: Price
    volume: Quantity
    bid: Optional[Price] = None
    ask: Optional[Price] = None

@dataclass(frozen=True, slots=True)
class NormalisedCandle:
    symbol: SymbolPair
    exchange: ExchangeName
    timeframe: str            # e.g. "1m"
    bucket_ms: int            # start-of-bar in UTC ms since epoch
    open: Price
    high: Price
    low: Price
    close: Price
    volume: Quantity
    closed: bool              # True only after the bar has rolled over

@dataclass(frozen=True)
class Order:
    order_id: UUID
    profile_id: ProfileId
    symbol: SymbolPair
    side: OrderSide
    quantity: Quantity
    price: Price
    status: OrderStatus
    exchange: ExchangeName
    created_at: datetime
    filled_at: Optional[datetime] = None
    fill_price: Optional[Price] = None
    decision_event_id: Optional[UUID] = None

@dataclass(frozen=True)
class RiskLimits:
    max_drawdown_pct: Percentage
    stop_loss_pct: Percentage
    circuit_breaker_daily_loss_pct: Percentage
    max_allocation_pct: Percentage

@dataclass(frozen=True)
class TradingProfile:
    profile_id: ProfileId
    user_id: str
    name: str
    strategy_rules_json: str
    risk_limits: RiskLimits
    blacklist: tuple[str, ...]
    allocation_pct: Percentage
    jurisdiction: str
    exchange_key_ref: str
    is_active: bool

@dataclass(frozen=True)
class Position:
    position_id: UUID
    profile_id: ProfileId
    symbol: SymbolPair
    side: OrderSide
    entry_price: Price
    quantity: Quantity
    entry_fee: Decimal
    opened_at: datetime
    status: PositionStatus = PositionStatus.OPEN
    closed_at: Optional[datetime] = None
    exit_price: Optional[Price] = None
    order_id: Optional[UUID] = None
    decision_event_id: Optional[UUID] = None
