"""Fixtures for integration tests against REAL Redis + TimescaleDB.

Connection contract (CI job `test-integration` in .github/workflows/ci.yml):

    PRAXIS_REDIS_URL=redis://localhost:6380/1
    PRAXIS_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/praxis_test

Tests read connection info ONLY from those two environment variables (never
from libs.config settings — the .env defaults point at the LIVE paper-trading
soak substrate). When either var is unset the whole package skips cleanly, so
plain `pytest tests/unit` / collection-only runs are unaffected.

LOCAL SAFETY LATCH: the local stack runs a live soak on redis db 1
(localhost:6379) and database `praxis_trading`. Two guards make it impossible
to point these tests at it by accident:

  * Redis on port 6379 is refused unless the URL selects db 15 (the agreed
    local scratch db). CI's service container (port 6380) is unaffected.
  * The Postgres database name must contain "test" (CI uses `praxis_test`).

Local run recipe (mirrors CI):

    docker exec deploy-timescaledb-1 psql -U postgres \
        -c "CREATE DATABASE praxis_test"   # once
    PRAXIS_REDIS_URL=redis://:changeme_redis_dev@localhost:6379/15 \
    PRAXIS_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/praxis_test \
    poetry run pytest tests/integration -v

Schema: migrations/versions/*.sql are applied once per session (same
swallow-per-file semantics as scripts/migrate.py — the files are idempotent
via IF NOT EXISTS), then the tables these tests write are truncated so reruns
on a persistent local praxis_test start clean.
"""

import asyncio
import glob
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

REPO_ROOT = Path(__file__).resolve().parents[2]

REDIS_URL_ENV = "PRAXIS_REDIS_URL"
DATABASE_URL_ENV = "PRAXIS_DATABASE_URL"

# Well-known keys these tests touch (libs/messaging/channels.py +
# services/hot_path/src/kill_switch.py + the backtest queue contract).
_CONTRACT_KEYS = [
    "stream:orders",
    "stream:validation",
    "stream:validation_response",
    "auto_backtest_queue",
    "praxis:kill_switch",
    "praxis:kill_switch:log",
]
_CONTRACT_KEY_PATTERNS = [
    "validation:resp:*",
    "backtest:status:*",
    "fast_gate:chk1:*",
    "risk:allocation:*",
    "agent:position_scores:*",
]

# Tables the tests write to, truncated once per session (CASCADE covers the
# FK chain users -> trading_profiles -> orders/positions -> closed_trades).
_TRUNCATE_TABLES = [
    "users",
    "trading_profiles",
    "orders",
    "positions",
    "closed_trades",
    "backtest_results",
    "validation_events",
    "audit_log",
]


def _redis_url() -> str | None:
    return os.environ.get(REDIS_URL_ENV)


def _database_url() -> str | None:
    return os.environ.get(DATABASE_URL_ENV)


def _redis_unsafe_reason(url: str) -> str | None:
    """Refuse the live soak substrate: port 6379 is only allowed with db 15."""
    parsed = urlparse(url)
    port = parsed.port or 6379
    db = (parsed.path or "/0").lstrip("/") or "0"
    if port == 6379 and db != "15":
        return (
            f"{REDIS_URL_ENV} points at port 6379 db {db} — that is the LIVE "
            "paper-trading soak Redis. Local integration runs must use db 15 "
            "(redis://:<pw>@localhost:6379/15)."
        )
    return None


def _database_unsafe_reason(url: str) -> str | None:
    parsed = urlparse(url)
    dbname = (parsed.path or "/").lstrip("/")
    if "test" not in dbname:
        return (
            f"{DATABASE_URL_ENV} targets database {dbname!r} — integration "
            "tests only run against a *test* database (e.g. praxis_test)."
        )
    return None


def _skip_reason() -> str | None:
    redis_url = _redis_url()
    db_url = _database_url()
    if not redis_url or not db_url:
        return (
            f"integration substrate not configured ({REDIS_URL_ENV} / "
            f"{DATABASE_URL_ENV} unset)"
        )
    return _redis_unsafe_reason(redis_url) or _database_unsafe_reason(db_url)


async def _purge_redis(client) -> None:
    await client.delete(*_CONTRACT_KEYS)
    for pattern in _CONTRACT_KEY_PATTERNS:
        async for key in client.scan_iter(match=pattern, count=200):
            await client.delete(key)


async def _session_setup(redis_url: str, db_url: str) -> None:
    """Apply migrations, truncate test tables, purge contract Redis keys."""
    import asyncpg

    conn = await asyncpg.connect(db_url)
    try:
        for ext in ('"uuid-ossp"', "timescaledb"):
            try:
                await conn.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
            except Exception:
                pass  # timescale image pre-installs; mirror migrate.py tolerance
        for path in sorted(glob.glob(str(REPO_ROOT / "migrations/versions/*.sql"))):
            sql = Path(path).read_text(encoding="utf-8")
            try:
                await conn.execute(sql)
            except Exception:
                # Same semantics as scripts/migrate.py: per-file failures are
                # tolerated (files are IF NOT EXISTS-idempotent; data-fix
                # migrations may legitimately no-op/fail on an empty test db).
                pass
        await conn.execute(f"TRUNCATE TABLE {', '.join(_TRUNCATE_TABLES)} CASCADE")
    finally:
        await conn.close()

    client = aioredis.from_url(redis_url)
    try:
        await _purge_redis(client)
    finally:
        await client.aclose()


async def _session_teardown(redis_url: str) -> None:
    client = aioredis.from_url(redis_url)
    try:
        await _purge_redis(client)
    finally:
        await client.aclose()


@pytest.fixture(scope="session")
def integration_env():
    """Session gate: skip cleanly when no test substrate is configured, refuse
    the live substrate, and prepare schema/keys exactly once."""
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    redis_url = _redis_url()
    db_url = _database_url()
    asyncio.run(_session_setup(redis_url, db_url))
    yield {"redis_url": redis_url, "database_url": db_url}
    asyncio.run(_session_teardown(redis_url))


@pytest_asyncio.fixture
async def redis_client(integration_env):
    """Fresh real Redis client per test (function-scoped event loop), with the
    contract keys cleared before the test so stream offsets/groups are fresh."""
    client = aioredis.from_url(integration_env["redis_url"])
    await _purge_redis(client)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def db(integration_env):
    """Real TimescaleClient pool against the test database."""
    from libs.storage import TimescaleClient

    client = TimescaleClient(integration_env["database_url"])
    await client.init_pool()
    yield client
    await client.close()


@pytest_asyncio.fixture
async def seeded_profile(db):
    """A real users + trading_profiles pair (plus a second 'foreign' user for
    tenant-scoping tests). Fresh UUIDs per test; risk limits allow a small
    order (notional $10k @ allocation_pct=1.0, max_allocation_pct=0.25)."""
    from libs.storage.repositories import ProfileRepository

    user_id = uuid.uuid4()
    foreign_user_id = uuid.uuid4()
    suffix = uuid.uuid4().hex[:8]
    for uid, email in (
        (user_id, f"owner-{suffix}@test.praxis"),
        (foreign_user_id, f"foreign-{suffix}@test.praxis"),
    ):
        await db.execute(
            """
            INSERT INTO users (
                user_id, email, hashed_password, jurisdiction, display_name
            )
            VALUES ($1, $2, 'x', 'US', split_part($2, '@', 1))
            """,
            uid,
            email,
        )

    profile_repo = ProfileRepository(db)
    profile = await profile_repo.create_profile(
        user_id=str(user_id),
        name=f"integration-{suffix}",
        strategy_rules={
            "conditions": [{"indicator": "rsi", "operator": "<", "threshold": 30}],
            "action": "BUY",
        },
        risk_limits={
            "max_allocation_pct": 0.25,
            "stop_loss_pct": 0.05,
            "max_drawdown_pct": 0.10,
            "circuit_breaker_daily_loss_pct": 0.02,
        },
        allocation_pct=1.0,
        exchange_key_ref="paper",
    )
    return {
        "user_id": user_id,
        "foreign_user_id": foreign_user_id,
        "profile_id": profile["profile_id"],
        "profile": profile,
    }


def utc_now_us() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1_000_000)


async def wait_for(predicate, timeout_s: float = 10.0, interval_s: float = 0.05):
    """Poll an async predicate until truthy or timeout; returns its value."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while True:
        value = await predicate()
        if value:
            return value
        if asyncio.get_event_loop().time() >= deadline:
            raise AssertionError(f"condition not met within {timeout_s}s")
        await asyncio.sleep(interval_s)


def parse_json(raw) -> dict:
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    return json.loads(raw)
