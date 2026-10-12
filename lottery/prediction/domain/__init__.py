"""Domain models and errors for prediction vertical."""
from lottery.prediction.domain.models import (
    GenerateBetRequest,
    GenerateBetResult,
    GenerateBatchRequest,
    MAX_BATCH_SIZE,
)
from lottery.prediction.domain.errors import (
    PredictionDomainError,
    InvalidStrategyError,
    InvalidOutputError,
    StrategyExecutionError,
    InvalidBatchCountError,
)

__all__ = [
    "GenerateBetRequest",
    "GenerateBetResult",
    "GenerateBatchRequest",
    "MAX_BATCH_SIZE",
    "PredictionDomainError",
    "InvalidStrategyError",
    "InvalidOutputError",
    "StrategyExecutionError",
    "InvalidBatchCountError",
]
