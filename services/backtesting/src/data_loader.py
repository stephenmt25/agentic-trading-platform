from datetime import datetime
from typing import List, Dict, Any

class BacktestDataLoader:
    def __init__(self, market_repo, gcs_client=None):
        self._market_repo = market_repo
        self._gcs_client = gcs_client

    async def load(self, symbol: str, start: datetime, end: datetime, timeframe: str = "1m") -> List[Dict[str, Any]]:
        days_diff = (datetime.utcnow() - start).days

        # > 12 months = GCS Parquet
        if days_diff > 365 and self._gcs_client:
            # Load from parquet in GCS (mocked)
            return []

        # < 12 months from Timescale using date-range query
        return await self._market_repo.get_candles_by_range(symbol, timeframe, start, end)
