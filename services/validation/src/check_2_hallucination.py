import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any
from .check_1_strategy import CheckResult
from libs.core.enums import ValidationVerdict

class HallucinationCheck:
    def __init__(self, validation_repo, market_repo):
        self._validation_repo = validation_repo
        self._market_repo = market_repo
        # Simplified memory tracker for LLM hits
        self._profile_hits: Dict[str, list] = {}

    def _get_hits(self, profile_id: str) -> list:
        if profile_id not in self._profile_hits:
            self._profile_hits[profile_id] = []
        return self._profile_hits[profile_id]

    async def check(self, profile_id: str, payload: Dict[str, Any]) -> CheckResult:
        if not payload.get("is_llm_sentiment", False):
            return CheckResult(passed=True)

        hits = self._get_hits(profile_id)

        # Determine success / fail of previous sentiment event vs actual market movement
        # over a 30-minute window following the sentiment signal.
        symbol = payload.get("symbol", "")
        sentiment_direction = payload.get("sentiment_direction", "BUY")  # BUY or SELL
        signal_time_str = payload.get("signal_timestamp")

        was_correct = True  # default to correct if we cannot verify
        if symbol and signal_time_str:
            try:
                signal_time = datetime.fromisoformat(signal_time_str)
                window_start = signal_time
                window_end = signal_time + timedelta(minutes=30)
                candles = await self._market_repo.get_candles_by_range(
                    symbol=symbol, timeframe="5m",
                    start=window_start, end=window_end
                )
                if candles and len(candles) >= 2:
                    price_at_signal = Decimal(str(candles[0]["close"]))
                    price_after = Decimal(str(candles[-1]["close"]))
                    actual_move = price_after - price_at_signal
                    # Check if sentiment direction matched actual price movement
                    if sentiment_direction == "BUY":
                        was_correct = actual_move >= 0
                    else:
                        was_correct = actual_move <= 0
            except Exception:
                # If market data unavailable, skip this check (fail-open)
                was_correct = True

        hits.append(was_correct)
        
        if len(hits) > 20: # keeping recent 20
            hits.pop(0)
            
        if len(hits) == 20:
            misaligned_pct = sum(not h for h in hits) / 20.0
            if misaligned_pct > 0.60:
                return CheckResult(passed=False, reason=f"LLM hallucination > 60% ({misaligned_pct*100:.1f}%)")
                
        return CheckResult(passed=True)
