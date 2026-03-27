# Storage and Repositories

## Purpose and Responsibility

The Storage library provides the data access layer for the Praxis Trading Platform. It manages connections to Redis (for caching, streams, and real-time state) and TimescaleDB (for persistent time-series and relational data), and exposes domain-specific repositories for orders, positions, PnL snapshots, and other entities. All database interactions across the platform flow through this library.

## Public Interface

### Database Clients

```python
class RedisClient:
    @classmethod
    def get_instance(cls, url: str) -> 'RedisClient'
    def get_connection(self) -> redis.Redis
    async def health_check(self) -> bool
    async def close(self) -> None

class TimescaleClient:
    def __init__(self, url: str)
    async def init_pool(self) -> None
    async def execute(self, query: str, *args) -> str
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]
    async def health_check(self) -> bool
    async def close(self) -> None
```

### Repositories

```python
class OrderRepository(BaseRepository):
    async def create_order(self, order: Order) -> None
    async def update_order_status(self, order_id: UUID, status: OrderStatus,
                                   fill_price=None, filled_at=None) -> None
    async def get_orders_for_user(self, user_id: str, profile_id=None, symbol=None,
                                   status=None, skip=0, limit=50) -> List[dict]
    async def get_order_for_user(self, order_id: UUID, user_id: str) -> Optional[dict]
    async def cancel_order_for_user(self, order_id: UUID, user_id: str) -> Optional[dict]
    async def get_orders_by_profile(self, profile_id: str) -> list
    async def get_order(self, order_id: UUID) -> Optional[dict]

class PositionRepository(BaseRepository):
    async def create_position(self, position: Position) -> None
    async def close_position(self, position_id: UUID, exit_price: Price) -> None
    async def get_open_positions(self, profile_id: ProfileId = None) -> List[Any]
    async def get_positions_for_symbol(self, symbol: SymbolPair) -> List[Any]

class PnlRepository(BaseRepository):
    async def write_snapshot(self, snapshot: Dict[str, Any]) -> None
    async def get_snapshots(self, profile_id: ProfileId,
                             start: datetime, end: datetime) -> List[Any]
    async def get_latest(self, profile_id: ProfileId) -> Optional[Any]
```

Additional repositories exported but defined in separate files: `AuditRepository`, `BacktestRepository`, `MarketDataRepository`, `ProfileRepository`, `ValidationRepository`.

## Internal Architecture

### RedisClient (Singleton)

`RedisClient` implements the singleton pattern. The `get_instance()` class method returns the shared instance, creating it on first call. Internally it uses a `ConnectionPool` with a maximum of 100 connections, initialised from the provided URL.

The raw `redis.Redis` client is accessed via `get_connection()` and used directly by all services for stream operations, pub/sub, caching, and Lua script execution.

### TimescaleClient (Connection Pool)

`TimescaleClient` wraps an `asyncpg` connection pool with:
- **Pool size**: 5 minimum, 20 maximum connections
- **Command timeout**: 5 seconds
- **Lazy initialisation**: The pool is created on the first call to `init_pool()`

The client exposes three query methods:
- `execute()` -- for INSERT/UPDATE/DELETE (returns status string)
- `fetch()` -- for SELECT returning multiple rows
- `fetchrow()` -- for SELECT returning a single row

All methods acquire a connection from the pool, execute the query, and release the connection automatically via `async with`.

### Repository Pattern

All repositories inherit from `BaseRepository` (not shown in the files read, but referenced by imports). Each repository encapsulates the SQL for a specific domain entity and depends on `TimescaleClient` for execution.

**OrderRepository** provides:
- CRUD operations for the `orders` table
- User-scoped queries that JOIN through `trading_profiles` for authorization
- Dynamic WHERE clause building with parameterised queries for filtering
- Cancellation that restricts to `PENDING` or `SUBMITTED` orders only

**PositionRepository** provides:
- Position creation with status tracking
- Position closing with exit price and timestamp
- Open position queries (optionally filtered by profile)
- Symbol-based position lookups

**PnlRepository** provides:
- PnL snapshot persistence to the `pnl_snapshots` table
- Time-range queries for historical PnL data
- Latest snapshot retrieval per profile

### Database Schema (Inferred)

**orders table**:
`order_id`, `profile_id`, `symbol`, `side`, `quantity`, `price`, `status`, `exchange`, `created_at`, `fill_price`, `filled_at`

**positions table**:
`position_id`, `profile_id`, `symbol`, `side`, `entry_price`, `quantity`, `entry_fee`, `opened_at`, `status`, `closed_at`, `exit_price`

**pnl_snapshots table**:
`profile_id`, `symbol`, `gross_pnl`, `net_pnl_pre_tax`, `net_pnl_post_tax`, `total_fees`, `estimated_tax`, `cost_basis`, `pct_return`, `snapshot_at`

## Dependencies

### Infrastructure Dependencies

- **Redis** (`redis.asyncio`) -- Connection pooling, all Redis operations
- **TimescaleDB** (`asyncpg`) -- PostgreSQL/TimescaleDB connection pooling and queries

### Library Dependencies

- `libs.core.models` -- `Order`, `Position` domain models
- `libs.core.enums` -- `OrderStatus`, `PositionStatus`, `OrderSide`
- `libs.core.types` -- `Price`, `ProfileId`, `SymbolPair`

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Pool not initialised (TimescaleDB) | `RuntimeError("Pool not initialized")` raised |
| Redis health check failure | Returns `False` |
| TimescaleDB health check failure | Returns `False` |
| Connection pool exhaustion | `asyncpg` will queue requests; 5s command timeout applies |
| Query error in repository | Exception propagates to caller (no internal catch) |

## Configuration

| Setting | Source | Default | Description |
|---------|--------|---------|-------------|
| `REDIS_URL` | Constructor / `settings` | -- | Redis connection string |
| `DATABASE_URL` | Constructor / `settings` | -- | TimescaleDB/PostgreSQL connection string |
| Redis max connections | Hardcoded | `100` | Connection pool upper bound |
| TimescaleDB min pool size | Hardcoded | `5` | Minimum idle connections |
| TimescaleDB max pool size | Hardcoded | `20` | Maximum connections |
| TimescaleDB command timeout | Hardcoded | `5.0s` | Query timeout |

## Known Issues and Technical Debt

1. **RedisClient singleton is not async-safe** -- The `get_instance()` class method is not protected against concurrent async access. If two coroutines call it simultaneously before the instance exists, two instances could be created.

2. **No connection health monitoring** -- Neither client implements automatic reconnection or pool health monitoring. If Redis or TimescaleDB goes down, operations will fail until the service is restarted.

3. **Pool configuration is hardcoded** -- Redis max connections (100) and TimescaleDB pool sizes (5-20) are not configurable via settings. Different services have different connection requirements.

4. **OrderRepository builds dynamic SQL** -- `get_orders_for_user()` constructs WHERE clauses dynamically using f-strings for column names and parameter indices. While parameterised values prevent SQL injection, the pattern is fragile and error-prone.

5. **No transaction support** -- Repositories execute individual queries without transaction boundaries. Multi-step operations (e.g., creating an order and updating position) are not atomic at the database level.

6. **Return types are inconsistent** -- Some methods return domain models, others return `dict` (from `asyncpg.Record`), and others return raw `asyncpg.Record` lists. There is no consistent serialisation boundary.

7. **PositionRepository.close_position uses timezone-aware datetime** -- It uses `datetime.now(timezone.utc)`, while other parts of the codebase use `datetime.utcnow()`. This inconsistency can cause comparison issues.

8. **PnlRepository.write_snapshot expects a dict** -- Unlike `OrderRepository` and `PositionRepository` which accept domain model objects, `PnlRepository` expects a raw dictionary. This breaks the repository pattern consistency.
