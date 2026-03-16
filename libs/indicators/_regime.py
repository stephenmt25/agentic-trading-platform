import numpy as np
from typing import Optional
from libs.core.enums import Regime

class SimpleRegimeClassifier:
    __slots__ = ('sma_period', 'vol_lookback', 'prices', 'atrs', 'price_count', 'atr_count', 'sum_price')

    def __init__(self, sma_period: int = 200, vol_lookback: int = 90):
        self.sma_period = sma_period
        self.vol_lookback = vol_lookback
        self.prices = np.zeros(sma_period, dtype=np.float64)
        self.atrs = np.zeros(vol_lookback, dtype=np.float64)
        self.price_count = 0
        self.atr_count = 0
        self.sum_price = 0.0

    def update(self, price: float, atr: float) -> Optional[Regime]:
        # Update SMA
        idx = self.price_count % self.sma_period
        old_price = self.prices[idx]
        self.prices[idx] = price
        self.sum_price = self.sum_price - old_price + price
        self.price_count += 1

        # Update ATR
        a_idx = self.atr_count % self.vol_lookback
        self.atrs[a_idx] = atr
        self.atr_count += 1

        if self.price_count < self.sma_period or self.atr_count < self.vol_lookback:
            return None

        sma = self.sum_price / self.sma_period
        
        # Calculate percentiles dynamically. 
        # Using numpy percentile on the pre-filled window
        p95_atr = np.percentile(self.atrs, 95)
        p75_atr = np.percentile(self.atrs, 75)
        p50_atr = np.percentile(self.atrs, 50)

        # Classify rules
        # CRISIS: vol > 95th pctl AND price < SMA > 10% (Price is 10% below SMA)
        # Assuming price < SMA * 0.90
        if atr > p95_atr and price < (sma * 0.90):
            return Regime.CRISIS
            
        if atr > p75_atr:
            return Regime.HIGH_VOLATILITY
            
        # RANGE_BOUND: within 2% of SMA, vol < 50th
        if abs(price - sma) / sma <= 0.02 and atr < p50_atr:
            return Regime.RANGE_BOUND
            
        if price > sma:
            return Regime.TRENDING_UP
            
        return Regime.TRENDING_DOWN
