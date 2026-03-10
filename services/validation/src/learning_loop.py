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
                # Fetch recent red/amber events
                # events = await self._validation_repo.get_recent_escalations()
                events = [] # MOCK
                
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
