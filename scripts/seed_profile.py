"""Seed a test trading profile for paper trading.

Usage: poetry run python scripts/seed_profile.py
"""
import asyncio
import json
import os
import sys
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.config import settings
from libs.storage._timescale_client import TimescaleClient
from libs.storage.repositories.profile_repo import ProfileRepository


async def seed():
    client = TimescaleClient(settings.DATABASE_URL)
    await client.init_pool()
    repo = ProfileRepository(client)

    # Check if a profile already exists
    existing = await repo.get_active_profiles()
    if existing:
        print(f"Found {len(existing)} existing active profiles. Skipping seed.")
        for p in existing:
            print(f"  - {p['name']} (id={p['profile_id']})")
        await client.close()
        return

    # First we need a user. Check if one exists or create a test user.
    user_id = str(uuid.uuid4())

    # Insert a test user matching the schema:
    #   user_id UUID, email TEXT, hashed_password TEXT (nullable),
    #   jurisdiction TEXT (nullable), display_name VARCHAR(255) NOT NULL,
    #   provider VARCHAR(50) NOT NULL DEFAULT 'google', created_at, updated_at
    try:
        await client.execute(
            """INSERT INTO users (user_id, email, display_name, provider)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT DO NOTHING""",
            uuid.UUID(user_id), "test@praxis.dev", "Test Operator", "google"
        )
        print(f"Created test user: {user_id}")
    except Exception as e:
        print(f"User creation: {e}")
        # Try to get existing user
        row = await client.fetchrow("SELECT user_id FROM users LIMIT 1")
        if row:
            user_id = str(row["user_id"])
            print(f"Using existing user: {user_id}")
        else:
            print("No users found and couldn't create one. Aborting.")
            await client.close()
            return

    # Create the trading profile
    strategy_rules = {
        "direction": "BUY",
        "logic": "AND",
        "conditions": [
            {"indicator": "rsi", "operator": "LT", "value": 35},
        ]
    }

    risk_limits = {
        "max_allocation_pct": 0.5,
        "max_drawdown_pct": 0.10,
        "stop_loss_pct": 0.05,
        "circuit_breaker_daily_loss_pct": 0.02
    }

    profile = await repo.create_profile(
        user_id=user_id,
        name="Paper Trading - RSI Strategy",
        strategy_rules=strategy_rules,
        risk_limits=risk_limits,
        allocation_pct=1.0,
        exchange_key_ref="paper"
    )

    print(f"Created profile: {profile.get('name')} (id={profile.get('profile_id')})")
    print(f"Strategy: RSI < 35 -> BUY")
    print(f"Risk limits: {json.dumps(risk_limits, indent=2)}")

    await client.close()
    print("Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
