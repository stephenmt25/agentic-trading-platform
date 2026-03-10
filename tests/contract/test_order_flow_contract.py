from libs.core.schemas import MarketTickEvent, OrderApprovedEvent, OrderExecutedEvent, ValidationRequestEvent, ValidationResponseEvent
from libs.core.enums import SignalDirection, OrderStatus, ValidationVerdict, ValidationCheckType, ValidationMode
import time

def test_market_data_contract():
    # Producer: Ingestion Agent
    # Consumer: Hot-Path Strategy
    
    tick = MarketTickEvent(
        symbol="BTC/USD",
        price=50000.5,
        volume=1.5,
        timestamp_us=int(time.time() * 1000000),
        source_exchange="BINANCE"
    )
    
    # Contract constraint check
    encoded = tick.model_dump_json()
    decoded = MarketTickEvent.model_validate_json(encoded)
    
    assert decoded.symbol == "BTC/USD"
    assert type(decoded.price) == float
    
def test_order_flow_contract():
    # Producer: Hot-Path Processor -> OrderApprovedEvent
    # Consumer: Execution Agent -> OrderExecutedEvent -> Logger
    
    approved = OrderApprovedEvent(
        profile_id="p-123",
        symbol="BTC/USD",
        direction=SignalDirection.BUY,
        quantity=0.1,
        confidence=0.85,
        compiled_rule_id="r-abc",
        timestamp_us=int(time.time() * 1000000),
        source_service="hot-path"
    )
    
    # Simulate execution serialization
    approved_json = approved.model_dump_json()
    approved_decoded = OrderApprovedEvent.model_validate_json(approved_json)
    
    executed = OrderExecutedEvent(
        profile_id=approved_decoded.profile_id,
        symbol=approved_decoded.symbol,
        exchange_order_id="exc-101",
        status=OrderStatus.SUBMITTED,
        timestamp_us=int(time.time() * 1000000),
        source_service="execution",
        source_event_id=str(approved_decoded.event_id)
    )
    
    assert executed.status == OrderStatus.SUBMITTED
    assert executed.profile_id == "p-123"
