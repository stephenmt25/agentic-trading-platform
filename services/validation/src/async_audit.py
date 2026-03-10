import asyncio
import time
from libs.messaging import StreamConsumer
from libs.storage.repositories import ValidationRepository
from libs.core.schemas import ValidationRequestEvent
from .check_2_hallucination import HallucinationCheck
from .check_3_bias import BiasCheck
from .check_4_drift import DriftCheck
from .check_5_escalation import EscalationCheck

class AsyncAuditHandler:
    def __init__(
        self,
        consumer: StreamConsumer,
        validation_repo: ValidationRepository,
        check2: HallucinationCheck,
        check3: BiasCheck,
        check4: DriftCheck,
        check5: EscalationCheck,
        channel: str
    ):
        self._consumer = consumer
        self._validation_repo = validation_repo
        self._check2 = check2
        self._check3 = check3
        self._check4 = check4
        self._check5 = check5
        self._channel = channel

    async def run(self):
        while True:
            events = await self._consumer.consume(self._channel, "async_val_group", "auditor_1", count=50)
            
            for msg_id, ev in events:
                if not ev or not isinstance(ev, ValidationRequestEvent):
                    continue
                    
                profile_id = ev.profile_id
                payload = ev.payload
                
                # Check 2
                res2 = await self._check2.check(profile_id, payload)
                if not res2.passed:
                    await self._check5.evaluate(profile_id, "check2_hallucination", {"reason": "AMBER " + str(res2.reason)})
                    
                # Check 3
                res3 = await self._check3.check(profile_id, payload)
                if not res3.passed:
                    await self._check5.evaluate(profile_id, "check3_bias", {"reason": "AMBER " + str(res3.reason)})
                    
                # Check 4
                res4 = await self._check4.check(profile_id, payload)
                if not res4.passed:
                    status = "RED" if "RED" in res4.reason else "AMBER"
                    await self._check5.evaluate(profile_id, "check4_drift", {"reason": f"{status} " + str(res4.reason)})
                    
                # Write to validation_events table
                await self._validation_repo.write_event(ev, {"res2": res2.passed, "res3": res3.passed, "res4": res4.passed})
                
            if events:
                await self._consumer.ack(self._channel, "async_val_group", [m for m, _ in events])
