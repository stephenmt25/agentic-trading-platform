import pytest
import numpy as np
from libs.indicators import RSICalculator, EMACalculator, MACDCalculator, ATRCalculator, SimpleRegimeClassifier

def test_rsi_calculator():
    rsi = RSICalculator(period=14)
    prices = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00
    ]
    vals = [rsi.update(p) for p in prices]
    
    # 14 values used to build average. The 15th returns the first RSI (approx 70.46)
    assert vals[13] is None # still filling the period
    assert vals[14] is not None
    assert isinstance(vals[14], float)

def test_macd_calculator():
    macd = MACDCalculator()
    prices = [10.0 + i * 0.1 for i in range(35)]
    vals = [macd.update(p) for p in prices]
    
    assert vals[25] is None # still filling slow EMA (26 periods)
    # The 26th period we start computing MACD line but signal EMA needs 9
    # The result becomes available down the line fully
    assert len(vals) == 35

def test_atr_calculator():
    atr = ATRCalculator(period=14)
    # simple test feeding identical H,L,C
    vals = [atr.update(10, 9, 9.5) for _ in range(15)]
    assert vals[13] is not None
    assert vals[14] is not None
