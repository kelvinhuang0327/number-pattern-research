"""Domain error hierarchy for lottery prediction vertical."""

class PredictionDomainError(Exception):
    """Base domain exception for prediction vertical failures."""
    pass

class InvalidStrategyError(PredictionDomainError):
    """Raised when requested strategy identity is unknown, non-ONLINE, or incompatible."""
    pass

class InvalidOutputError(PredictionDomainError):
    """Raised when strategy output violates domain contract (e.g. wrong count, out of range)."""
    pass

class StrategyExecutionError(PredictionDomainError):
    """Raised when strategy execution fails during runtime."""
    pass

class InvalidBatchCountError(PredictionDomainError):
    """Raised when batch count is invalid (non-int, bool, < 1, or > MAX_BATCH_SIZE)."""
    pass
