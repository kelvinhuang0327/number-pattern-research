#!/usr/bin/env python3
"""
Smoke test for coordinator-enabled prediction routes.

Run:
  PYTHONPATH=lottery_api python3 lottery_api/tools/smoke_test_coordinator_api.py
"""
import asyncio
from typing import Dict, List

from routes.prediction import (
    predict_coordinator_route,
    predict_from_backend,
    predict_from_backend_eval,
    predict_with_range,
)
from schemas import PredictFromBackendRequest, PredictWithRangeRequest


def _assert_numbers(numbers: List[int], expected_len: int, label: str):
    assert isinstance(numbers, list), f"{label}: numbers must be list"
    assert len(numbers) == expected_len, f"{label}: expected {expected_len} numbers, got {len(numbers)}"
    assert len(set(numbers)) == len(numbers), f"{label}: numbers contain duplicates"


def _assert_common_response(res: Dict, expected_len: int, label: str):
    assert isinstance(res, dict), f"{label}: response must be dict"
    assert "numbers" in res, f"{label}: missing numbers"
    assert "method" in res, f"{label}: missing method"
    _assert_numbers(res["numbers"], expected_len, label)


async def main():
    # Case 1: backend endpoint + alias POWER_BALL
    req_backend = PredictFromBackendRequest(
        lotteryType="POWER_BALL",
        modelType="coordinator_direct",
    )
    res_backend = await predict_from_backend(req_backend, coord_mode=None, coord_bets=2)
    _assert_common_response(res_backend, 6, "backend")
    assert "special" in res_backend, "backend: POWER_LOTTO should include special number"
    print("backend:", res_backend["method"], res_backend["numbers"], "special=", res_backend.get("special"))

    # Case 2: eval endpoint + alias DAILY_CASH_539
    req_eval = PredictFromBackendRequest(
        lotteryType="DAILY_CASH_539",
        modelType="coordinator_hybrid",
    )
    res_eval = await predict_from_backend_eval(
        req_eval,
        recent_count=300,
        coord_mode="hybrid",
        coord_bets=2,
    )
    _assert_common_response(res_eval, 5, "eval")
    print("eval:", res_eval["method"], res_eval["numbers"])

    # Case 3: range endpoint + canonical BIG_LOTTO
    req_range = PredictWithRangeRequest(
        lotteryType="BIG_LOTTO",
        modelType="coordinator",
        recentCount=500,
        coordMode="hybrid",
        coordBets=3,
    )
    res_range = await predict_with_range(req_range)
    _assert_common_response(res_range, 6, "range")
    print("range:", res_range["method"], res_range["numbers"])

    # Case 4: dedicated coordinator endpoint + lowercase alias
    res_coord = await predict_coordinator_route(
        lottery_type="power-ball",
        num_bets=2,
        mode="direct",
        recent_count=300,
    )
    _assert_common_response(res_coord, 6, "coordinator_route")
    assert isinstance(res_coord.get("bets"), list) and len(res_coord["bets"]) == 2, \
        "coordinator_route: expected 2 bets"
    print("coord_route:", res_coord["method"], res_coord["numbers"])

    print("OK: coordinator routes smoke test passed")


if __name__ == "__main__":
    asyncio.run(main())
