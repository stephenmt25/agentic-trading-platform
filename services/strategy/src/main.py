import asyncio
import json
from libs.config import settings
from libs.storage import ProfileRepository, MarketDataRepository, RedisClient, TimescaleClient
from libs.observability import get_logger

from .hydrator import IndicatorHydrator
from .rule_validator import RuleValidator
from .compiler import RuleCompiler

logger = get_logger("strategy")

POLL_INTERVAL_S = 60

redis_client = RedisClient.get_instance(settings.REDIS_URL).get_connection()
timescale_client = TimescaleClient(settings.DATABASE_URL)

profile_repo = ProfileRepository(timescale_client)
market_repo = MarketDataRepository(timescale_client)

hydrator = IndicatorHydrator(profile_repo, market_repo, redis_client)
validator = RuleValidator()
compiler = RuleCompiler()

# Track last-seen profile state to detect changes
_profile_hashes: dict[str, str] = {}


def _profile_hash(profile: dict) -> str:
    """Hash the fields that matter for rule compilation."""
    rules = profile.get("strategy_rules") or {}
    updated = profile.get("updated_at", "")
    return f"{json.dumps(rules, sort_keys=True)}|{updated}"


async def _compile_and_cache_profile(profile: dict) -> bool:
    """Validate, compile, and cache a single profile's rules. Returns True if cached."""
    profile_id = profile["profile_id"]
    rules = profile.get("strategy_rules")
    if not rules:
        return False

    result = validator.validate(rules)
    if not result.is_valid:
        logger.warning("Profile rules invalid", profile_id=str(profile_id), errors=result.errors)
        return False

    try:
        compiled = compiler.compile(rules)
    except ValueError as e:
        logger.warning("Profile rule compilation failed", profile_id=str(profile_id), error=str(e))
        return False

    # Store compiled rule set in Redis for hot-path consumption
    cache_key = f"strategy:compiled:{profile_id}"
    payload = json.dumps({
        "logic": compiled.logic,
        "direction": compiled.direction.value,
        "base_confidence": compiled.base_confidence,
        "conditions": compiled.conditions,
    })
    await redis_client.set(cache_key, payload, ex=300)  # 5-minute TTL, refreshed every 60s
    return True


async def hydration_task():
    logger.info("Initializing DB connections for hydrator")
    await timescale_client.init_pool()
    await hydrator.hydrate_all_profiles()


async def profile_poll_loop():
    """Poll profiles every 60s, re-validate and re-compile any that changed."""
    global _profile_hashes

    while True:
        try:
            profiles = await profile_repo.get_active_profiles()
            changed = 0
            removed = 0

            current_ids = set()
            for profile in profiles:
                pid = str(profile["profile_id"])
                current_ids.add(pid)
                h = _profile_hash(profile)

                if _profile_hashes.get(pid) == h:
                    continue  # No change

                if await _compile_and_cache_profile(profile):
                    changed += 1
                _profile_hashes[pid] = h

            # Clean up profiles that were deleted or deactivated
            stale_ids = set(_profile_hashes.keys()) - current_ids
            for pid in stale_ids:
                await redis_client.delete(f"strategy:compiled:{pid}")
                del _profile_hashes[pid]
                removed += 1

            if changed or removed:
                logger.info(
                    "Profile poll complete",
                    total=len(profiles),
                    changed=changed,
                    removed=removed,
                )
        except Exception as e:
            logger.error("Profile poll failed", error=str(e))

        await asyncio.sleep(POLL_INTERVAL_S)


async def main():
    logger.info("Starting Strategy Agent Service")
    await hydration_task()

    try:
        await profile_poll_loop()
    except asyncio.CancelledError:
        logger.info("Shutting down Strategy Agent")
    finally:
        await timescale_client.close()

if __name__ == "__main__":
    asyncio.run(main())
