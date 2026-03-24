# Technical Indicators

## Purpose and Responsibility

The Indicators library provides streaming, tick-by-tick implementations of standard technical analysis indicators used by the Hot-Path Processor for real-time strategy evaluation. Each indicator maintains internal state and updates incrementally with O(1) computation per tick, making them suitable for the low-latency hot path. The library includes 8 indicators: RSI, EMA, MACD, ATR, ADX, Bollinger Bands, OBV, Choppiness Index, plus a market regime classifier.

## Public Interface

### `IndicatorSet`

```python
class IndicatorSet:
    rsi: RSICalculator
    macd: MACDCalculator
    atr: ATRCalculator
    regime: SimpleRegimeClassifier
    adx: ADXCalculator          # Optional, default None
    bollinger: BollingerCalculator  # Optional, default None
    obv: OBVCalculator          # Optional, default None
    choppiness: ChoppinessCalculator  # Optional, default None

def create_indicator_set(profile_config: Dict[str, Any] = None) -> IndicatorSet
```

`create_indicator_set()` instantiates all 8 indicators with default parameters. New indicators default to `None` for backward compatibility when constructing `IndicatorSet` manually, but `create_indicator_set()` always populates them.

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

### `ADXCalculator`

```python
class ADXCalculator:
    def __init__(self, period: int = 14)
    def update(self, high: float, low: float, close: float) -> Optional[float]
```

Returns the Average Directional Index (0-100 scale). ADX > 25 indicates a strong trend; ADX < 20 indicates a weak/ranging market. Uses Wilder smoothing for +DI, -DI, and the ADX itself.

### `BollingerCalculator`

```python
class BollingerCalculator:
    def __init__(self, period: int = 20, num_std: float = 2.0)
    def update(self, close: float) -> Optional[BollingerResult]

@dataclass(frozen=True, slots=True)
class BollingerResult:
    upper: float
    middle: float
    lower: float
    bandwidth: float
    pct_b: float
```

Returns Bollinger Bands with SMA-based middle band. `pct_b` measures where price sits relative to the bands (0.0 = lower band, 1.0 = upper band). Values outside 0-1 indicate price beyond the bands. `bandwidth` is the band width relative to the middle band.

### `OBVCalculator`

```python
class OBVCalculator:
    def __init__(self)
    def update(self, close: float, volume: float) -> Optional[float]
```

Cumulative On-Balance Volume. Adds volume on up-closes, subtracts on down-closes. Used for volume-trend confirmation in the TA confluence scorer.

### `ChoppinessCalculator`

```python
class ChoppinessCalculator:
    def __init__(self, period: int = 14)
    def update(self, high: float, low: float, close: float) -> Optional[float]
```

Returns the Choppiness Index (0-100 scale). Values > 61.8 indicate choppy/ranging conditions; values < 38.2 indicate trending. Formula: `100 * LOG10(sum(TR) / (HH - LL)) / LOG10(period)`. Used as a regime filter in TA confluence scoring — high choppiness dampens signal conviction.

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
| ADX | 2 * `period` - 1 ticks (default 27) |
| Bollinger | `period` ticks (default 20) |
| OBV | 1 tick (returns `None` only on first bar) |
| Choppiness | `period` ticks (default 14) |
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

### ADX (Average Directional Index)

Uses Wilder smoothing on Directional Movement:

1. Computes +DM (up-move) and -DM (down-move) from consecutive high/low pairs.
2. Computes True Range (same as ATR).
3. Accumulates DM and TR for the first `period` bars (no smoothing).
4. After `period` bars, applies Wilder smoothing: `smoothed = smoothed - (smoothed / period) + current`.
5. +DI = 100 * smoothed_+DM / smoothed_TR, -DI = 100 * smoothed_-DM / smoothed_TR.
6. DX = 100 * |+DI - -DI| / (+DI + -DI).
7. First ADX = average of first `period` DX values.
8. After: `ADX = (prev_ADX * (period - 1) + DX) / period`.

### Bollinger Bands

SMA-based bands with configurable standard deviation width:

1. Maintains a ring buffer of `period` close prices.
2. Tracks running sum and sum-of-squares for O(1) mean and variance.
3. Middle band = SMA. Upper/lower = SMA +/- `num_std` * std_dev.
4. `bandwidth` = (upper - lower) / middle.
5. `pct_b` = (close - lower) / (upper - lower). Values outside [0, 1] mean price is beyond bands.

### OBV (On-Balance Volume)

Simple cumulative indicator:

1. First bar: OBV = volume, returns `None`.
2. Subsequent bars: if close > prev_close, OBV += volume; if close < prev_close, OBV -= volume; if equal, no change.
3. Returns running OBV total.

### Choppiness Index

Measures market directionality using ATR sum relative to price range:

1. Maintains rolling buffers of True Range, highs, and lows over `period` bars.
2. `CHOP = 100 * LOG10(sum(TR) / (highest_high - lowest_low)) / LOG10(period)`.
3. Clamped to [0, 100].
4. High values (> 61.8) = choppy/consolidating; low values (< 38.2) = trending.

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
| `period` | ADX | `14` | Wilder smoothing and DX averaging period |
| `period` | Bollinger | `20` | SMA period for middle band |
| `num_std` | Bollinger | `2.0` | Standard deviation multiplier for upper/lower bands |
| (none) | OBV | -- | Cumulative, no configurable parameters |
| `period` | Choppiness | `14` | Rolling window for TR sum and high/low range |
| `sma_period` | Regime | `200` | SMA lookback for trend detection |
| `vol_lookback` | Regime | `90` | ATR history window for percentile calculation |

Note: `create_indicator_set()` accepts a `profile_config` parameter but does not currently use it. All indicators are created with default parameters regardless of the profile configuration.

## TA Confluence Integration

The TA Confluence Scorer (`services/ta_agent/src/confluence.py`) uses indicators across 4 timeframes (1m, 5m, 15m, 1h) with weighted averaging [0.1, 0.2, 0.3, 0.4]:

| Signal Dimension | Source | Range | Contribution |
|---|---|---|---|
| RSI | `(50 - rsi) / 50` | [-1, 1] | Equal weight with MACD (or 1/3 when Bollinger available) |
| MACD | Histogram normalized by MACD line | [-1, 1] | Equal weight with RSI |
| Bollinger %B | `1 - 2 * pct_b` | [-1, 1] | 3rd dimension when primed (makes score avg of 3) |
| ADX | Trend-strength multiplier on 1h | 0.7x - 1.3x | ADX > 25 amplifies; ADX < 20 dampens |
| Choppiness | Regime filter on 1h | 0.5x - 1.0x | Chop > 61.8 dampens conviction linearly |

The final score is clamped to [-1.0, 1.0] and written to `agent:ta_score:{symbol}` in Redis.

### Strategy Rule Keys

The strategy compiler evaluates rules against any of these indicator keys in the `eval_dict`:

| Key | Description | Source |
|-----|-------------|--------|
| `rsi` | RSI value (0-100) | RSICalculator |
| `macd.macd_line` | MACD line value | MACDCalculator |
| `macd.signal_line` | Signal line value | MACDCalculator |
| `macd.histogram` | MACD histogram | MACDCalculator |
| `atr` | Average True Range | ATRCalculator |
| `adx` | ADX value (0-100) | ADXCalculator |
| `bb.pct_b` | Bollinger %B (0-1 typical) | BollingerCalculator |
| `bb.bandwidth` | Bollinger bandwidth | BollingerCalculator |
| `bb.upper` | Upper Bollinger Band | BollingerCalculator |
| `bb.lower` | Lower Bollinger Band | BollingerCalculator |
| `obv` | On-Balance Volume (cumulative) | OBVCalculator |
| `choppiness` | Choppiness Index (0-100) | ChoppinessCalculator |

Example strategy rule using new indicators:
```json
{
  "conditions": [
    {"indicator": "rsi", "operator": "LT", "value": 30},
    {"indicator": "bb.pct_b", "operator": "LT", "value": 0.2},
    {"indicator": "adx", "operator": "GT", "value": 25}
  ],
  "logic": "AND",
  "direction": "BUY",
  "base_confidence": 0.85
}
```

## Known Issues and Technical Debt

1. **profile_config is ignored** -- `create_indicator_set()` accepts a config parameter but always creates indicators with default periods. Custom indicator tuning per profile is not yet supported.

2. **No input validation** -- None of the calculators validate inputs. Passing `NaN`, `Inf`, or negative prices will produce incorrect results without any error.

3. **RSI window overflow** -- The RSI uses a circular buffer of `window_size=1000` entries. The `count` variable increments indefinitely but the buffer wraps correctly via modulo. However, the priming logic uses `count` as an absolute counter, which is correct but could be confusing for maintenance.

4. **Regime classifier uses numpy percentile on every tick** -- `np.percentile()` is called on the full ATR lookback window (90 values) on every update. While this is O(n log n) rather than O(1), the small window size makes it negligible in practice.

5. **ATR requires high/low/close** -- The Hot-Path must synthesize high/low values from tick data when bid/ask is not available, using a heuristic comparison with the previous close. This approximation degrades ATR accuracy compared to proper OHLC data.

6. **No thread safety** -- All calculators use mutable internal state with no locking. They are safe for single-threaded async use but not for concurrent access.

7. **Hardcoded regime thresholds** -- The regime classifier's threshold percentages (90% SMA for crisis, 2% SMA for range-bound) are hardcoded and not configurable.
