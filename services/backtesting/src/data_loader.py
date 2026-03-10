from datetime import datetime
from typing import List, Dict, Any

class BacktestDataLoader:
    def __init__(self, market_repo, gcs_client=None):
        self._market_repo = market_repo
        self._gcs_client = gcs_client
        
    async def load(self, symbol: str, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        # In a real system, calculate difference
        days_diff = (datetime.utcnow() - start).days
        
        # > 12 months = GCS Parquet
        if days_diff > 365 and self._gcs_client:
            # Load from parquet in GCS (mocked)
            return []
            
        # < 12 months from Timescale
        # For simplicity, returning mock query limits, but timescale uses timeframe
        return await self._market_repo.get_candles(symbol, timeframe="1m", limit=1000)
