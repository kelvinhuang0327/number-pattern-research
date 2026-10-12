"""Public entrypoint for lottery prediction single bet generation.

Vertical: lottery.prediction.generate
Canonical Contract: Big Lotto single bet generation through canonical registry & adapter.
"""
from typing import List, Optional
from lottery.prediction.domain.models import GenerateBetRequest, GenerateBetResult
from lottery.prediction.use_cases.generate_one_bet_use_case import GenerateOneBetUseCase

_use_case = GenerateOneBetUseCase()

def generate_one_bet(request: GenerateBetRequest) -> GenerateBetResult:
    """
    Generate a single bet according to GenerateBetRequest.

    Parameters:
        request: GenerateBetRequest specifying strategy_id, lottery_type, and history slice.

    Returns:
        GenerateBetResult containing 6 unique valid Big Lotto numbers [1..49] and metadata.
    """
    return _use_case.execute(request)

def generate_biglotto_bet(strategy_id: str, history: Optional[List[dict]] = None) -> GenerateBetResult:
    """
    Convenience function to generate a single Big Lotto bet using a specified strategy.

    Parameters:
        strategy_id: Registered strategy identity (e.g. 'biglotto_triple_strike').
        history: List of past draw dictionaries strictly before target draw.

    Returns:
        GenerateBetResult containing 6 unique valid Big Lotto numbers [1..49] and metadata.
    """
    req = GenerateBetRequest(
        strategy_id=strategy_id,
        lottery_type="BIG_LOTTO",
        history=history or [],
    )
    return generate_one_bet(req)
