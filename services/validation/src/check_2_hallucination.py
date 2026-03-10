import asyncio
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
        
        # Determine success / fail of previous sentiment event vs market action 30mins
        # In this implementation, we simulate outcome logic.
        
        simulated_correct = True # Mocking the historic lookup
        hits.append(simulate_correct)
        
        if len(hits) > 20: # keeping recent 20
            hits.pop(0)
            
        if len(hits) == 20:
            misaligned_pct = sum(not h for h in hits) / 20.0
            if misaligned_pct > 0.60:
                return CheckResult(passed=False, reason=f"LLM hallucination > 60% ({misaligned_pct*100:.1f}%)")
                
        return CheckResult(passed=True)
