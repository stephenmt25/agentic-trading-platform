# Technical Indicators

## Purpose and Responsibility

The Indicators library provides streaming, tick-by-tick implementations of standard technical analysis indicators used by the Hot-Path Processor for real-time strategy evaluation. Each indicator maintains internal state and updates incrementally with O(1) computation per tick, making them suitable for the low-latency hot path. The library includes RSI, EMA, MACD, ATR, and a market regime classifier.

## Public Interface

### `IndicatorSet`

```python
class IndicatorSet:
    rsi: RSICalculator
    macd: MACDCalculator
    atr: ATRCalculator
    regime: SimpleRegimeClassifier

def create_indicator_set(profile_config: Dict[str, Any] = None) -> IndicatorSet
```

### `RSICalculator`

```python
class RSICalculator:
    def __init__(self, period: int = 14, window_size: int = 1000)
    def update(self, price: float) -> Optional[float]
```

### `EMACalculator`

```python
class EMACalculator:
    def __init__(self, period: int)
    def update(self, price: float) -> Optional[float]
```

### `MACDCalculator`

```python
class MACDCalculator:
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9)
    def update(self, price: float) -> Optional[MACDResult]

@dataclass(frozen=True, slots=True)
class MACDResult:
    macd_line: float
    signal_line: float
    histogram: float
```

### `ATRCalculator`

```python
class ATRCalculator:
    def __init__(self, period: int = 14)
    def update(self, high: float, low: float, close: float) -> Optional[float]
```

### `SimpleRegimeClassifier`

```python
class SimpleRegimeClassifier:
    def __init__(self, sma_period: int = 200, vol_lookback: int = 90)
    def update(self, price: float, atr: float) -> Optional[Regime]
```

Returns one of: `Regime.CRISIS`, `Regime.HIGH_VOLATILITY`, `Regime.RANGE_BOUND`, `Regime.TRENDING_UP`, `Regime.TRENDING_DOWN`.

## Internal Architecture

### Priming Behaviour

All indicators return `None` until they have received enough data points to produce a valid output. This priming period varies by indicator:

| Indicator | Priming Period |
|-----------|---------------|
| RSI | `period` ticks (default 14) |
| EMA | `period` ticks |
| MACD | `slow` + `signal` - 1 ticks (default 34) |
| ATR | `period` ticks (default 14) |
| Regime | max(`sma_period`, `vol_lookback`) ticks (default 200) |

### RSI (Relative Strength Index)

Uses Wilder's smoothing method with a circular buffer (`numpy.zeros` of `window_size`):

1. Tracks price changes as gains and losses.
2. During the priming phase, accumulates raw gain and loss sums.
3. At `count == period`, computes the initial average gain/loss by dividing accumulated sums.
4. After priming, applies exponential smoothing: `avg = (prev_avg * (period - 1) + current) / period`.
5. Computes RSI as `100 - (100 / (1 + RS))` where `RS = avg_gain / avg_loss`.
6. Returns `100.0` when `avg_loss == 0` (all gains).

### EMA (Exponential Moving Average)

Standard EMA with multiplier `2 / (period + 1)`:

1. Accumulates prices during priming.
2. At `count == period`, computes initial EMA as simple average of accumulated prices.
3. After priming: `ema = (price - ema) * multiplier + ema`.

### MACD (Moving Average Convergence Divergence)

Composed of three EMA calculators:

1. Fast EMA (default period 12) and slow EMA (default period 26) are updated with the price.
2. MACD line = fast EMA - slow EMA.
3. Signal line = EMA(MACD line, default period 9).
4. Histogram = MACD line - signal line.
5. Returns `None` until all three EMA components are primed.

### ATR (Average True Range)

Uses Wilder's smoothing on the True Range:

1. True Range = max(high - low, |high - prev_close|, |low - prev_close|).
2. First bar uses `high - low` only (no previous close available).
3. Accumulates TR during priming.
4. At `count == period`, initial ATR = sum(TR) / period.
5. After priming: `atr = (prev_atr * (period - 1) + tr) / period`.
6. Exposes `prev_close` as a public attribute for external use (the Hot-Path uses it for tick high/low estimation).

### Regime Classifier

Combines a 200-period SMA with ATR percentile analysis using numpy:

1. Maintains circular buffers for prices (SMA) and ATR values.
2. Computes ATR percentiles (50th, 75th, 95th) dynamically from the lookback window.
3. Classification rules (evaluated in order):
   - **CRISIS**: ATR > 95th percentile AND price < 90% of SMA
   - **HIGH_VOLATILITY**: ATR > 75th percentile
   - **RANGE_BOUND**: Price within 2% of SMA AND ATR < 50th percentile
   - **TRENDING_UP**: Price > SMA
   - **TRENDING_DOWN**: Default (price <= SMA)

## Dependencies

### Library Dependencies

- `numpy` -- Circular buffers and percentile computation (RSI, Regime Classifier)
- `libs.core.enums` -- `Regime` enum

## Error Handling

All indicators are designed to be exception-free under normal operation. They return `None` when insufficient data is available. There are no explicit error handling paths -- invalid inputs (e.g., negative prices, NaN) will propagate through calculations without guards.

## Configuration

| Parameter | Indicator | Default | Description |
|-----------|-----------|---------|-------------|
| `period` | RSI | `14` | Lookback period for RSI calculation |
| `window_size` | RSI | `1000` | Circular buffer size for price history |
| `period` | EMA | Required | EMA smoothing period |
| `fast` | MACD | `12` | Fast EMA period |
| `slow` | MACD | `26` | Slow EMA period |
| `signal` | MACD | `9` | Signal line EMA period |
| `period` | ATR | `14` | ATR smoothing period |
| `sma_period` | Regime | `200` | SMA lookback for trend detection |
| `vol_lookback` | Regime | `90` | ATR history window for percentile calculation |

Note: `create_indicator_set()` accepts a `profile_config` parameter but does not currently use it. All indicators are created with default parameters regardless of the profile configuration.

## Known Issues and Technical Debt

1. **profile_config is ignored** -- `create_indicator_set()` accepts a config parameter but always creates indicators with default periods. Custom indicator tuning per profile is not yet supported.

2. **No input validation** -- None of the calculators validate inputs. Passing `NaN`, `Inf`, or negative prices will produce incorrect results without any error.

3. **RSI window overflow** -- The RSI uses a circular buffer of `window_size=1000` entries. The `count` variable increments indefinitely but the buffer wraps correctly via modulo. However, the priming logic uses `count` as an absolute counter, which is correct but could be confusing for maintenance.

4. **Regime classifier uses numpy percentile on every tick** -- `np.percentile()` is called on the full ATR lookback window (90 values) on every update. While this is O(n log n) rather than O(1), the small window size makes it negligible in practice.

5. **ATR requires high/low/close** -- The Hot-Path must synthesize high/low values from tick data when bid/ask is not available, using a heuristic comparison with the previous close. This approximation degrades ATR accuracy compared to proper OHLC data.

6. **No thread safety** -- All calculators use mutable internal state with no locking. They are safe for single-threaded async use but not for concurrent access.

7. **Hardcoded regime thresholds** -- The regime classifier's threshold percentages (90% SMA for crisis, 2% SMA for range-bound) are hardcoded and not configurable.
