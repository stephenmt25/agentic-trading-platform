class PraxisBaseError(Exception):
    """Base exception for all praxis-trading errors."""
    pass

class ConfigurationError(PraxisBaseError):
    pass

class ExchangeError(PraxisBaseError):
    pass

class ExchangeRateLimitError(ExchangeError):
    pass

class ExchangeTimeoutError(ExchangeError):
    pass

class ValidationError(PraxisBaseError):
    pass

class CircuitBreakerTriggeredError(PraxisBaseError):
    pass

class BlacklistBlockedError(PraxisBaseError):
    pass

class RiskGateBlockedError(PraxisBaseError):
    pass

class OrderExecutionError(PraxisBaseError):
    pass

class ReconciliationDriftError(PraxisBaseError):
    pass

class SchemaVersionMismatchError(PraxisBaseError):
    pass
