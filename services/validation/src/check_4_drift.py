from typing import Dict, Any
from .check_1_strategy import CheckResult

class DriftCheck:
    def __init__(self, pnl_repo):
        self._pnl_repo = pnl_repo

    async def check(self, profile_id: str, payload: Dict[str, Any]) -> CheckResult:
        # drift_halt_threshold = max(0.15, stop_loss_tolerance * drift_multiplier)
        # Default multiplier=3.0, window=7 days
        # Pass / Amber (within 50% of halt) / Red (at/above halt -> Trading Halt)
        
        # Mock values for Sharpe
        backtest_sharpe = 2.0
        live_sharpe = 1.5
        
        # We calculate % drop
        drop_pct = (backtest_sharpe - live_sharpe) / backtest_sharpe
        
        halt_threshold = 0.15 # 15% drop triggers red 
        amber_threshold = halt_threshold * 0.50 # 7.5% drop triggers amber
        
        if drop_pct >= halt_threshold:
            return CheckResult(passed=False, reason=f"Drift RED: Live Sharpe dropped {drop_pct*100:.1f}%, exceeding halt threshold of {halt_threshold*100:.1f}%")
        elif drop_pct >= amber_threshold:
            return CheckResult(passed=False, reason=f"Drift AMBER: Live Sharpe dropped {drop_pct*100:.1f}%")
            
        return CheckResult(passed=True)
