from libs.config import settings
print(f"HITL_ENABLED:              {settings.HITL_ENABLED}")
print(f"HITL_CONFIDENCE_THRESHOLD: {settings.HITL_CONFIDENCE_THRESHOLD}")
print(f"HITL_SIZE_THRESHOLD_PCT:   {settings.HITL_SIZE_THRESHOLD_PCT}")
print(f"HITL_TIMEOUT_S:            {settings.HITL_TIMEOUT_S}")
print(f"LLM_API_KEY (set):         {bool(settings.LLM_API_KEY)}")
