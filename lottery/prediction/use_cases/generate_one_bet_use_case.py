"""Application Use Case: Single Bet Generation for Big Lotto."""
from typing import List, Dict, Any
import logging

from lottery.prediction.domain.models import GenerateBetRequest, GenerateBetResult
from lottery.prediction.domain.errors import (
    InvalidStrategyError,
    InvalidOutputError,
    StrategyExecutionError,
)
from lottery_api.models.replay_strategy_registry import (
    _REGISTRY,
    _ALL_ADAPTERS,
    get_adapter,
    get_strategy_lifecycle_status,
    UnsupportedLotteryType,
    InvalidOutput as RegistryInvalidOutput,
    InsufficientHistory,
    RejectPrediction,
    LifecycleNotExecutable,
)

logger = logging.getLogger(__name__)

class GenerateOneBetUseCase:
    """
    Canonical use case for Big Lotto single bet generation.
    Enforces strict product contract:
      - Uses registered strategy identity from canonical strategy catalog/registry
      - Executes through executable adapter
      - Enforces domain rules: 6 unique numbers, range [1..49] for BIG_LOTTO
      - Fails closed on unknown strategy, non-ONLINE status, adapter mismatch, or invalid output
    """

    def execute(self, request: GenerateBetRequest) -> GenerateBetResult:
        if not isinstance(request, GenerateBetRequest):
            raise InvalidOutputError("Request must be an instance of GenerateBetRequest")

        if not request.strategy_id or not isinstance(request.strategy_id, str):
            raise InvalidStrategyError("strategy_id must be a non-empty string")

        lottery_type = request.lottery_type or "BIG_LOTTO"
        if lottery_type != "BIG_LOTTO":
            raise InvalidStrategyError(f"Vertical currently supports BIG_LOTTO only, got {lottery_type}")

        # Check strategy registration & lifecycle status in canonical registry
        status = get_strategy_lifecycle_status(request.strategy_id)
        if status is None:
            raise InvalidStrategyError(f"Unknown strategy_id: {request.strategy_id!r}")
        if status != "ONLINE":
            raise InvalidStrategyError(
                f"Strategy {request.strategy_id!r} is in lifecycle status {status!r}, not eligible for execution"
            )

        # Get adapter from executable registry
        try:
            adapter = get_adapter(request.strategy_id)
        except KeyError:
            raise InvalidStrategyError(f"Strategy {request.strategy_id!r} not found in executable registry")

        # Identity mismatch safeguard
        if adapter.meta.strategy_id != request.strategy_id:
            raise InvalidStrategyError(
                f"Adapter identity mismatch: expected {request.strategy_id!r}, got {adapter.meta.strategy_id!r}"
            )

        # Supported lottery type safeguard
        if lottery_type not in adapter.meta.supported_lottery_types:
            raise InvalidStrategyError(
                f"Strategy {request.strategy_id!r} does not support lottery type {lottery_type}"
            )

        # Execute adapter
        try:
            numbers, special = adapter.get_one_bet(request.history, lottery_type)
        except (UnsupportedLotteryType, RegistryInvalidOutput, InsufficientHistory) as e:
            raise InvalidOutputError(f"Strategy output validation failed: {e}")
        except RejectPrediction as e:
            raise StrategyExecutionError(f"Strategy rejected prediction: {e}")
        except LifecycleNotExecutable as e:
            raise InvalidStrategyError(f"Strategy not executable: {e}")
        except Exception as e:
            raise StrategyExecutionError(f"Strategy execution error: {e}")

        # Strict domain contract verification
        self._validate_biglotto_numbers(numbers, request.strategy_id)

        return GenerateBetResult(
            strategy_id=request.strategy_id,
            lottery_type=lottery_type,
            numbers=numbers,
            special=special,
            metadata={
                "strategy_name": adapter.meta.strategy_name,
                "strategy_version": adapter.meta.strategy_version,
                "lifecycle_status": adapter.meta.lifecycle_status,
                "history_length": len(request.history),
            },
        )

    def _validate_biglotto_numbers(self, numbers: List[int], strategy_id: str) -> None:
        if not isinstance(numbers, list):
            raise InvalidOutputError(f"{strategy_id}: numbers must be a list")
        if len(numbers) != 6:
            raise InvalidOutputError(f"{strategy_id}: Big Lotto requires exactly 6 numbers, got {len(numbers)}")
        if not all(isinstance(n, int) and not isinstance(n, bool) for n in numbers):
            raise InvalidOutputError(f"{strategy_id}: all numbers must be integers")
        if not all(1 <= n <= 49 for n in numbers):
            raise InvalidOutputError(f"{strategy_id}: numbers out of range [1..49]: {numbers}")
        if len(set(numbers)) != 6:
            raise InvalidOutputError(f"{strategy_id}: numbers contain duplicates: {numbers}")
