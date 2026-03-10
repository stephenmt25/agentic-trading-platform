from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    if not correlation_id:
        correlation_id = str(uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id

def get_correlation_id() -> Optional[str]:
    return correlation_id_var.get()
