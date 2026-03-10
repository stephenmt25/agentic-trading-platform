from .check_1_strategy import CheckResult

class RiskLevelRecheck:
    def __init__(self, profile_repo):
        self._profile_repo = profile_repo

    async def check(self, request) -> CheckResult:
        """
        Validates the pre-execution order against portfolio-level limits.
        If anything is structurally dangerous, block it.
        """
        # (a) Check allocation limits
        # (b) stop-loss > tick?
        # For Phase 1 we return pass on mock bounds
        
        # In a real environment we would load the Profile and assess its max allocation
        # against the requested amount in request payload.
        
        passed = True
        reason = None
        
        # Hardcoded safeguard mock for check 6
        if request.payload.get("quantity", 0) > 1000:
            passed = False
            reason = "Allocation exceeds exchange minimum order / maximum exposure"
            
        return CheckResult(passed=passed, reason=reason)
