import time

from libs.core.enums import ValidationMode, ValidationVerdict
from libs.core.schemas import ValidationRequestEvent, ValidationResponseEvent
from libs.messaging import StreamConsumer
from libs.storage.repositories import ValidationRepository

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
        channel: str,
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
            events = await self._consumer.consume(
                self._channel, "async_val_group", "auditor_1", count=50
            )

            for msg_id, ev in events:
                if not ev or not isinstance(ev, ValidationRequestEvent):
                    continue

                t0 = time.monotonic()
                profile_id = ev.profile_id
                payload = ev.payload

                # Check 2
                res2 = await self._check2.check(profile_id, payload)
                if not res2.passed:
                    await self._check5.evaluate(
                        profile_id,
                        "check2_hallucination",
                        {"reason": "AMBER " + str(res2.reason)},
                    )

                # Check 3
                res3 = await self._check3.check(profile_id, payload)
                if not res3.passed:
                    await self._check5.evaluate(
                        profile_id,
                        "check3_bias",
                        {"reason": "AMBER " + str(res3.reason)},
                    )

                # Check 4
                res4 = await self._check4.check(profile_id, payload)
                if not res4.passed:
                    status = "RED" if "RED" in res4.reason else "AMBER"
                    await self._check5.evaluate(
                        profile_id,
                        "check4_drift",
                        {"reason": f"{status} " + str(res4.reason)},
                    )

                # Persist the async-audit outcome. ValidationMode.ASYNC_AUDIT
                # exists in the schema precisely for this path; mirror the
                # fast-gate's ValidationResponseEvent construction. Verdict is
                # GREEN only if all async checks passed, RED if drift (check 4)
                # flagged RED, else AMBER. event_id is carried from the request
                # for correlation (validation_events has no unique constraint on
                # event_id, so stream redelivery can't cause a PK conflict).
                if res2.passed and res3.passed and res4.passed:
                    verdict = ValidationVerdict.GREEN
                elif not res4.passed and "RED" in str(res4.reason):
                    verdict = ValidationVerdict.RED
                else:
                    verdict = ValidationVerdict.AMBER
                failed = []
                if not res2.passed:
                    failed.append(f"check2:{res2.reason}")
                if not res3.passed:
                    failed.append(f"check3:{res3.reason}")
                if not res4.passed:
                    failed.append(f"check4:{res4.reason}")
                audit_resp = ValidationResponseEvent(
                    event_id=ev.event_id,
                    timestamp_us=int(time.time() * 1000000),
                    source_service="validation",
                    verdict=verdict,
                    check_type=ev.check_type,
                    mode=ValidationMode.ASYNC_AUDIT,
                    reason="; ".join(failed) or None,
                    response_time_ms=(time.monotonic() - t0) * 1000.0,
                )
                await self._validation_repo.write_validation_event(
                    str(profile_id),
                    audit_resp,
                    {"res2": res2.passed, "res3": res3.passed, "res4": res4.passed},
                )

            if events:
                await self._consumer.ack(
                    self._channel, "async_val_group", [m for m, _ in events]
                )
