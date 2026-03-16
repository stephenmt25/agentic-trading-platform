import asyncio
import json
from libs.storage.repositories import ValidationRepository
from libs.messaging import StreamPublisher

class LearningLoop:
    def __init__(self, validation_repo: ValidationRepository, publisher: StreamPublisher):
        self._validation_repo = validation_repo
        self._publisher = publisher

    async def run_hourly_scan(self, interval_seconds: int = 3600):
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                # Fetch recent red/amber events from the last hour across all check types
                from libs.core.enums import ValidationCheck
                events = []
                for check_type in ValidationCheck:
                    try:
                        records = await self._validation_repo.get_recent_events(check_type, hours=1)
                        for r in records:
                            row = dict(r) if not isinstance(r, dict) else r
                            verdict = row.get("verdict", "")
                            if verdict in ("RED", "AMBER"):
                                events.append(row)
                    except Exception:
                        continue
                
                for ev in events:
                    job_type = ""
                    # If drift RED -> "what if we halted"
                    if "Drift RED" in ev.get("reason", ""):
                        job_type = "what_if_halted"
                    # If hallucination -> "backtest with sentiment zeroed"
                    elif "Hallucination" in ev.get("reason", ""):
                        job_type = "zero_sentiment_backtest"
                    # If bias -> "backtest bias neutralised"
                    elif "Bias" in ev.get("reason", ""):
                        job_type = "neutral_bias_backtest"

                    if job_type:
                        payload = {
                            "source_event_id": ev.get("event_id"),
                            "profile_id": ev.get("profile_id"),
                            "job_type": job_type
                        }
                        # Write to auto_backtest_queue
                        await self._publisher.publish("auto_backtest_queue", payload)
            except Exception as e:
                # Log error
                pass
