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

        # Fetch hot RSI from the request payload (computed by strategy on latest tick)
        hot_rsi = request.payload.get("inds", {}).get("rsi", 50.0)

        # Fetch wider context window from TimescaleDB to compute an independent RSI
        try:
            candles = await self._market_repo.get_candles(
                symbol=request.symbol, timeframe="5m", limit=20
            )
            if candles and len(candles) >= 14:
                closes = [float(c["close"]) for c in candles]
                wide_rsi = self._compute_rsi(closes, period=14)
            else:
                # Not enough data for independent RSI, trust hot value
                wide_rsi = hot_rsi
        except Exception:
            # If DB is unreachable, fall back to hot value (fail-open for fast gate)
            wide_rsi = hot_rsi

        diff_pct = abs(wide_rsi - hot_rsi) / max(hot_rsi, 1.0)

        passed = diff_pct <= 0.25
        reason = f"RSI diverged by {diff_pct*100:.2f}% (hot={hot_rsi:.1f}, wide={wide_rsi:.1f})" if not passed else None
        
        # Cache for burst protection (sub-second)
        await self._redis.set(cache_key, "PASS" if passed else "FAIL", ex=1)

        return CheckResult(passed=passed, reason=reason)

    @staticmethod
    def _compute_rsi(closes: list, period: int = 14) -> float:
        """Compute RSI from a list of closing prices using Wilder's smoothing."""
        if len(closes) < period + 1:
            return 50.0  # neutral fallback
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0.0 for d in deltas[:period]]
        losses = [-d if d < 0 else 0.0 for d in deltas[:period]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        for d in deltas[period:]:
            g = d if d > 0 else 0.0
            l = -d if d < 0 else 0.0
            avg_gain = (avg_gain * (period - 1) + g) / period
            avg_loss = (avg_loss * (period - 1) + l) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
