from typing import Dict, Any
from decimal import Decimal
from libs.core.models import NormalisedTick

def normalise_binance_tick(raw: Dict[str, Any]) -> NormalisedTick:
    return NormalisedTick(
        symbol=raw.get('symbol', 'UNKNOWN'),
        exchange='BINANCE',
        timestamp=int(raw.get('timestamp', 0) * 1000), # microseconds
        price=Decimal(str(raw.get('last', 0))),
        volume=Decimal(str(raw.get('baseVolume', 0))),
        bid=Decimal(str(raw.get('bid', 0))) if raw.get('bid') else None,
        ask=Decimal(str(raw.get('ask', 0))) if raw.get('ask') else None
    )

def normalise_coinbase_tick(raw: Dict[str, Any]) -> NormalisedTick:
    return NormalisedTick(
        symbol=raw.get('symbol', 'UNKNOWN'),
        exchange='COINBASE',
        timestamp=int(raw.get('timestamp', 0) * 1000), # microseconds
        price=Decimal(str(raw.get('last', 0))),
        volume=Decimal(str(raw.get('baseVolume', 0))),
        bid=Decimal(str(raw.get('bid', 0))) if raw.get('bid') else None,
        ask=Decimal(str(raw.get('ask', 0))) if raw.get('ask') else None
    )
