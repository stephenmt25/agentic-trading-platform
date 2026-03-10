from collections import defaultdict
import numpy as np
from typing import Dict, Any
from .check_1_strategy import CheckResult

class BiasCheck:
    def __init__(self):
        # Tracking counts of features (e.g. side, symbol) per profile
        self._tracking = defaultdict(lambda: {'count': 0, 'buys': 0, 'sells': 0})

    async def check(self, profile_id: str, payload: Dict[str, Any]) -> CheckResult:
        tracker = self._tracking[profile_id]
        
        side = payload.get("direction", "BUY")
        
        if side == "BUY":
            tracker['buys'] += 1
        else:
            tracker['sells'] += 1
            
        tracker['count'] += 1
        
        if tracker['count'] >= 100:
            buy_ratio = tracker['buys'] / tracker['count']
            
            # Simple binomial z-score (p=0.5 assumed for neutral baseline)
            z_score = abs(buy_ratio - 0.5) / np.sqrt((0.5 * 0.5) / tracker['count'])
            
            # Reset after check or rolling logic
            tracker['count'] = 0
            tracker['buys'] = 0
            tracker['sells'] = 0
            
            if z_score > 2.5:
                return CheckResult(passed=False, reason=f"Directional Bias detected (z={z_score:.2f})")
                
        return CheckResult(passed=True)
