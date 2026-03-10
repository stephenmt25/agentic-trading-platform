from dataclasses import dataclass
from typing import Optional

@dataclass
class CheckResult:
    passed: bool
    reason: Optional[str] = None

class StrategyRecheck:
    def __init__(self, market_repo, redis_client):
        self._market_repo = market_repo
        self._redis = redis_client

    async def check(self, request) -> CheckResult:
        # Check cache logic
        cache_key = f"fast_gate:chk1:{request.profile_id}:{request.symbol}"
        if await self._redis.exists(cache_key):
            cached = await self._redis.get(cache_key)
            if cached == b"PASS":
                return CheckResult(passed=True)
            return CheckResult(passed=False, reason="Cached failure")

        # Mock wide context evaluation (divergence > 25% = BLOCK)
        hot_rsi = request.payload.get("inds", {}).get("rsi", 50.0)
        
        # In a real environment we would fetch wider context from timescale here
        wide_rsi = hot_rsi * 1.05 # Mocked 5% divergence
        
        diff_pct = abs(wide_rsi - hot_rsi) / max(hot_rsi, 1.0)
        
        passed = diff_pct <= 0.25
        reason = f"RSI diverged by {diff_pct*100:.2f}%" if not passed else None
        
        # Cache for burst protection (sub-second)
        await self._redis.set(cache_key, "PASS" if passed else "FAIL", ex=1)
        
        return CheckResult(passed=passed, reason=reason)
