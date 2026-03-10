from libs.core.schemas import ValidationRequestEvent, ValidationResponseEvent
from libs.core.enums import SignalDirection, ValidationVerdict, ValidationCheckType, ValidationMode
import time

def test_validation_schema_contract():
    req = ValidationRequestEvent(
        profile_id="p-123",
        symbol="BTC/USD",
        check_type=ValidationCheckType.STRATEGY,
        mode=ValidationMode.FAST_GATE,
        payload={"inds": {"rsi": 25.0, "macd": -10.5}, "direction": "BUY"},
        timestamp_us=int(time.time() * 1000000),
        source_service="hot-path"
    )
    
    encoded = req.model_dump_json()
    decoded_req = ValidationRequestEvent.model_validate_json(encoded)
    
    res = ValidationResponseEvent(
        event_id=decoded_req.event_id,
        timestamp_us=int(time.time() * 1000000),
        source_service="validation",
        verdict=ValidationVerdict.GREEN,
        check_type=ValidationCheckType.STRATEGY,
        mode=ValidationMode.FAST_GATE,
        response_time_ms=12.5
    )
    
    res_enc = res.model_dump_json()
    res_dec = ValidationResponseEvent.model_validate_json(res_enc)
    
    assert res_dec.verdict == ValidationVerdict.GREEN
    assert res_dec.response_time_ms == 12.5
