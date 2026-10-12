"""Public entrypoint for Daily 539 prediction single bet generation.

Vertical: lottery.prediction.daily539
Canonical Contract: Daily 539 single bet generation through canonical registry & adapter.
"""
from typing import List, Optional
from lottery.prediction.daily539.models import Daily539GenerateBetRequest, Daily539GenerateBetResult
from lottery.prediction.daily539.use_cases import Daily539GenerateOneBetUseCase

_use_case = Daily539GenerateOneBetUseCase()

def generate_one_bet(request: Daily539GenerateBetRequest) -> Daily539GenerateBetResult:
    """
    Generate a single bet according to Daily539GenerateBetRequest.

    Parameters:
        request: Daily539GenerateBetRequest specifying strategy_id, lottery_type, and history slice.

    Returns:
        Daily539GenerateBetResult containing 5 unique valid Daily 539 numbers [1..39] and metadata.
    """
    return _use_case.execute(request)

def generate_daily539_bet(strategy_id: str, history: Optional[List[dict]] = None) -> Daily539GenerateBetResult:
    """
    Convenience function to generate a single Daily 539 bet using a specified strategy.

    Parameters:
        strategy_id: Registered strategy identity (e.g. 'daily539_f4cold').
        history: List of past draw dictionaries strictly before target draw.

    Returns:
        Daily539GenerateBetResult containing 5 unique valid Daily 539 numbers [1..39] and metadata.
    """
    req = Daily539GenerateBetRequest(
        strategy_id=strategy_id,
        lottery_type="DAILY_539",
        history=history or [],
    )
    return generate_one_bet(req)
