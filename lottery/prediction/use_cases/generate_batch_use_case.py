"""Application Use Case: Batch Bet Generation for Big Lotto."""
from typing import Tuple, Optional, List
import logging

from lottery.prediction.domain.models import (
    GenerateBatchRequest,
    GenerateBetRequest,
    GenerateBetResult,
    MAX_BATCH_SIZE,
)
from lottery.prediction.domain.errors import (
    InvalidBatchCountError,
    InvalidStrategyError,
    InvalidOutputError,
    StrategyExecutionError,
)
from lottery.prediction.use_cases.generate_one_bet_use_case import GenerateOneBetUseCase

logger = logging.getLogger(__name__)

class GenerateBatchUseCase:
    """
    Application use case for generating a batch of Big Lotto bets.
    Reuses GenerateOneBetUseCase strictly to maintain single-bet contract.

    Enforces:
      - Bounded count validation (1 <= count <= MAX_BATCH_SIZE=20)
      - Exact integer type checking (rejects bool, float, str)
      - Atomic fail-closed semantics (zero partial results returned on any error)
      - Immutable ordered tuple return
    """

    def __init__(self, single_bet_use_case: Optional[GenerateOneBetUseCase] = None):
        self._single_bet_use_case = single_bet_use_case or GenerateOneBetUseCase()

    def execute(self, request: GenerateBatchRequest) -> Tuple[GenerateBetResult, ...]:
        if not isinstance(request, GenerateBatchRequest):
            raise InvalidOutputError("Request must be an instance of GenerateBatchRequest")

        count = request.count
        # Strict int type checking (bool is a subclass of int in Python)
        if type(count) is not int or isinstance(count, bool):
            raise InvalidBatchCountError(f"count must be an integer, got {type(count).__name__} ({count!r})")

        if count < 1:
            raise InvalidBatchCountError(f"count must be >= 1, got {count}")

        if count > MAX_BATCH_SIZE:
            raise InvalidBatchCountError(
                f"count exceeds maximum allowed batch size of {MAX_BATCH_SIZE}, got {count}"
            )

        if not request.strategy_id or not isinstance(request.strategy_id, str):
            raise InvalidStrategyError("strategy_id must be a non-empty string")

        lottery_type = request.lottery_type or "BIG_LOTTO"

        # Generate exactly `count` bets reusing canonical single-bet use case
        results: List[GenerateBetResult] = []
        for i in range(count):
            single_req = GenerateBetRequest(
                strategy_id=request.strategy_id,
                lottery_type=lottery_type,
                history=request.history,
            )
            # Any failure here raises domain exception and fails closed immediately
            single_result = self._single_bet_use_case.execute(single_req)
            results.append(single_result)

        if len(results) != count:
            raise InvalidOutputError(f"Batch generation result count mismatch: expected {count}, got {len(results)}")

        return tuple(results)
