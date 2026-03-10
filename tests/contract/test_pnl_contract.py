from libs.core.schemas import PnlUpdateEvent
import time

def test_pnl_schema_contract():
    # Verify Decimals constraint instead of floats where required implicitly
    # Pydantic handles floats intrinsically, we ensure serialization preserves JSON accuracy
    
    ev = PnlUpdateEvent(
        profile_id="p-100",
        position_id="pos-x",
        symbol="ETH/USD",
        net_post_tax=120.50,
        net_pre_tax=150.00,
        roi_pct=0.15,
        timestamp_us=int(time.time() * 1000000),
        source_service="pnl"
    )
    
    enc = ev.model_dump_json()
    dec = PnlUpdateEvent.model_validate_json(enc)
    
    assert dec.profile_id == "p-100"
    assert dec.net_post_tax == 120.50
    assert dec.roi_pct == 0.15
