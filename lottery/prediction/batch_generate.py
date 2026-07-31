"""Public entrypoint for lottery prediction batch bet generation.

Vertical: lottery.prediction.batch_generate
Canonical Contract: Big Lotto batch bet generation reusing GenerateOneBetUseCase.
"""
from typing import Tuple, Optional, List
from lottery.prediction.domain.models import GenerateBatchRequest, GenerateBetResult
from lottery.prediction.use_cases.generate_batch_use_case import GenerateBatchUseCase

_batch_use_case = GenerateBatchUseCase()

def generate_bets(
    strategy_id: Optional[str] = None,
    count: Optional[int] = None,
    *,
    lottery_type: str = "BIG_LOTTO",
    history: Optional[List[dict]] = None,
    request: Optional[GenerateBatchRequest] = None,
) -> Tuple[GenerateBetResult, ...]:
    """
    Generate a batch of Big Lotto bets using the specified strategy identity.

    Can be called either with a GenerateBatchRequest object or keyword/positional arguments:
        generate_bets(strategy_id="biglotto_triple_strike", count=3, history=draw_history)
        generate_bets(request=my_batch_request)

    Parameters:
        strategy_id: Registered strategy identity string.
        count: Number of bets to generate (1 <= count <= 20).
        lottery_type: Lottery type string (default: "BIG_LOTTO").
        history: List of past draw dictionaries strictly before target draw.
        request: GenerateBatchRequest instance (optional).

    Returns:
        Tuple of GenerateBetResult objects containing 6 unique valid Big Lotto numbers [1..49].
    """
    if request is not None:
        return _batch_use_case.execute(request)

    if strategy_id is None or count is None:
        # Pass parameters to GenerateBatchRequest to trigger typed validation errors
        req = GenerateBatchRequest(
            strategy_id=strategy_id or "",
            count=count,  # type: ignore
            lottery_type=lottery_type,
            history=history or [],
        )
    else:
        req = GenerateBatchRequest(
            strategy_id=strategy_id,
            count=count,
            lottery_type=lottery_type,
            history=history or [],
        )

    return _batch_use_case.execute(req)
