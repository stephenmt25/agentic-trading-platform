import asyncio
import time
from libs.core.schemas import ValidationRequestEvent, ValidationResponseEvent
from libs.core.enums import ValidationVerdict, ValidationMode

from .check_1_strategy import StrategyRecheck
from .check_6_risk_level import RiskLevelRecheck
from libs.observability import get_logger

logger = get_logger("validation.fastgate")

class FastGateHandler:
    def __init__(self, check1: StrategyRecheck, check6: RiskLevelRecheck):
        self._check1 = check1
        self._check6 = check6

    async def handle(self, req: ValidationRequestEvent) -> ValidationResponseEvent:
        start = time.perf_counter()
        
        # Dispatched in parallel utilizing maximum 35ms bound
        task1 = asyncio.create_task(self._check1.check(req))
        task6 = asyncio.create_task(self._check6.check(req))
        
        res1, res6 = await asyncio.gather(task1, task6)
        
        duration_ms = (time.perf_counter() - start) * 1000
        
        verdict = ValidationVerdict.GREEN
        reason = None
        
        if not res1.passed:
            verdict = ValidationVerdict.RED
            reason = f"Check 1 Failed: {res1.reason}"
        elif not res6.passed:
            verdict = ValidationVerdict.RED
            reason = f"Check 6 Failed: {res6.reason}"
            
        if duration_ms > 35.0:
            logger.warning("Fast Gate deadline exceeded", duration_ms=duration_ms, event_id=str(req.event_id))

        return ValidationResponseEvent(
            event_id=req.event_id,
            timestamp_us=int(time.time() * 1000000),
            source_service="validation",
            verdict=verdict,
            check_type=req.check_type,
            mode=ValidationMode.FAST_GATE,
            reason=reason,
            response_time_ms=duration_ms
        )
