# Exchange Adapters

## Purpose and Responsibility

The Exchange Adapters library provides a unified interface for communicating with cryptocurrency exchanges. It abstracts away exchange-specific API details behind a common `ExchangeAdapter` base class, normalises incoming tick data into a standard `NormalisedTick` model, and provides a rate limiter client for controlling API request frequency. Currently, Binance and Coinbase are supported via the CCXT Pro library.

## Public Interface

### Factory Function

```python
def get_adapter(exchange_name: str, api_key: str = "", secret: str = "",
                testnet: bool = True) -> ExchangeAdapter
```

Returns a `BinanceAdapter` or `CoinbaseAdapter` based on the exchange name. Raises `ValueError` for unsupported exchanges.

### `ExchangeAdapter` (Abstract Base)

```python
class ExchangeAdapter(ABC):
    name: ExchangeName
    is_connected: bool

    async def connect_websocket(self, symbols: List[SymbolPair],
                                 callback: Callable[[NormalisedTick], Coroutine]) -> None
    async def place_order(self, profile_id: ProfileId, symbol: SymbolPair,
                          side: OrderSide, qty: Quantity, price: Price) -> OrderResult
    async def get_balance(self, profile_id: ProfileId) -> Any
    async def cancel_order(self, order_id: str) -> None
    async def get_order_status(self, order_id: str) -> OrderStatus
    async def close(self) -> None
```

### `OrderResult`

```python
@dataclass
class OrderResult:
    order_id: str
    status: OrderStatus
    fill_price: Optional[Price] = None
    filled_quantity: Optional[Quantity] = None
```

### Normalisation Functions

```python
def normalise_binance_tick(raw: Dict[str, Any]) -> NormalisedTick
def normalise_coinbase_tick(raw: Dict[str, Any]) -> NormalisedTick
```

### `RateLimiterClient`

```python
@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_ms: Optional[int] = None

class RateLimiterClient:
    def __init__(self, redis_client: redis.Redis)
    async def check_and_reserve(self, exchange: ExchangeName,
                                 profile_id: ProfileId) -> RateLimitResult
```

## Internal Architecture

### Adapter Pattern

Both `BinanceAdapter` and `CoinbaseAdapter` follow an identical implementation pattern:

1. **Initialization** -- Creates a CCXT Pro exchange instance with the provided API credentials and enables sandbox mode if `testnet=True`. CCXT's built-in rate limiting is enabled (`enableRateLimit: True`).

2. **WebSocket Streaming** -- `connect_websocket()` runs a continuous loop calling `exchange.watch_tickers()` for the requested symbols. Each raw ticker is passed through the exchange-specific normaliser to produce a `NormalisedTick`, which is delivered to the callback.

3. **Reconnection** -- On `NetworkError`, the adapter retries with exponential backoff starting at 1 second and capping at 30 seconds. On `ExchangeClosedByUser`, the loop exits cleanly.

4. **Order Placement** -- Submits limit orders via `exchange.create_order()`. The CCXT response ID is captured, and the initial status is mapped to `OrderStatus.SUBMITTED`.

5. **Status Mapping** -- CCXT statuses are mapped to internal enums:
   - `open` -> `SUBMITTED`
   - `closed` -> `CONFIRMED`
   - `canceled` -> `CANCELLED`
   - `rejected` -> `REJECTED`
   - unknown -> `PENDING`

### Tick Normalisation

Both normaliser functions convert CCXT ticker dictionaries into `NormalisedTick` objects with:
- `symbol` -- from raw ticker
- `exchange` -- hardcoded string (`"BINANCE"` or `"COINBASE"`)
- `timestamp` -- raw timestamp multiplied by 1000 to produce microseconds
- `price` -- `Decimal` from `last` field
- `volume` -- `Decimal` from `baseVolume` field
- `bid`/`ask` -- Optional `Decimal` values, `None` if absent

### Rate Limiter

The `RateLimiterClient` is designed to enforce per-exchange, per-profile rate limits using a Redis sliding window. In the current implementation, it always returns `RateLimitResult(allowed=True)` as a placeholder. The key schema is `rate_limit:{exchange}:{profile_id}`.

## Dependencies

### Infrastructure Dependencies

- **CCXT Pro** -- Provides the underlying exchange API clients and WebSocket connections
- **Redis** -- Used by the rate limiter client for state tracking

### Library Dependencies

- `libs.core.types` -- `ExchangeName`, `ProfileId`, `SymbolPair`, `Quantity`, `Price`
- `libs.core.enums` -- `OrderSide`, `OrderStatus`
- `libs.core.models` -- `NormalisedTick`

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| `ccxt.NetworkError` during WebSocket | Exponential backoff reconnect (1s to 30s) |
| `ccxt.ExchangeClosedByUser` | Clean exit from WebSocket loop |
| Unexpected exception during WebSocket | Reconnect with backoff (same as NetworkError) |
| Unsupported exchange name | `ValueError` raised by `get_adapter()` |
| Missing bid/ask in raw tick | Normalised to `None` in `NormalisedTick` |

## Configuration

| Setting | Source | Default | Description |
|---------|--------|---------|-------------|
| `api_key` | Constructor parameter | `""` | Exchange API key |
| `secret` | Constructor parameter | `""` | Exchange API secret |
| `testnet` | Constructor parameter | `True` | Enable sandbox/testnet mode |
| Reconnect base delay | Hardcoded | `1.0s` | Initial backoff for reconnection |
| Reconnect max delay | Hardcoded | `30.0s` | Maximum backoff cap |
| CCXT rate limiting | Hardcoded | `True` | CCXT's built-in rate limiter |

## Known Issues and Technical Debt

1. **Rate limiter is a no-op** -- `RateLimiterClient.check_and_reserve()` always returns `allowed=True`. The sliding window logic referenced in the docstring is not implemented.

2. **Identical adapter implementations** -- `BinanceAdapter` and `CoinbaseAdapter` are near-identical copies differing only in the exchange class name and normaliser function. This should be refactored into a single generic CCXT adapter parameterised by exchange name.

3. **Print statements for logging** -- Both adapters use `print()` for error and reconnection messages instead of the platform's structured logging (`libs.observability.get_logger`).

4. **cancel_order signature mismatch** -- The base class defines `cancel_order(self, order_id: str)` but both implementations require an additional `symbol` parameter: `cancel_order(self, order_id: str, symbol: str)`. This breaks the abstract contract.

5. **get_order_status signature mismatch** -- Same issue as `cancel_order` -- implementations require a `symbol` parameter not present in the base class signature.

6. **No fill price on order placement** -- `place_order()` always returns `fill_price=None` in the `OrderResult`. Actual fill prices are not captured from the exchange response.

7. **Timestamp conversion may be inaccurate** -- The normaliser multiplies the raw CCXT timestamp by 1000, but CCXT already provides timestamps in milliseconds. The result would be in microseconds only if the source is milliseconds, which is exchange-dependent.

8. **No connection pooling** -- Each call to `get_adapter()` creates a new CCXT exchange instance. There is no caching or pooling of adapter connections across requests.
