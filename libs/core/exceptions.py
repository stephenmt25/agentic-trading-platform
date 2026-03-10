class AionBaseError(Exception):
    """Base exception for all aion-trading errors."""
    pass

class ConfigurationError(AionBaseError):
    pass

class ExchangeError(AionBaseError):
    pass

class ExchangeRateLimitError(ExchangeError):
    pass

class ExchangeTimeoutError(ExchangeError):
    pass

class ValidationError(AionBaseError):
    pass

class CircuitBreakerTriggeredError(AionBaseError):
    pass

class BlacklistBlockedError(AionBaseError):
    pass

class RiskGateBlockedError(AionBaseError):
    pass

class OrderExecutionError(AionBaseError):
    pass

class ReconciliationDriftError(AionBaseError):
    pass

class SchemaVersionMismatchError(AionBaseError):
    pass
