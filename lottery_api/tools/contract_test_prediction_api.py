#!/usr/bin/env python3
"""
Staged contract regression tests for prediction APIs.

Run:
  PYTHONPATH=lottery_api python3 lottery_api/tools/contract_test_prediction_api.py
"""
import asyncio
import os
import sys

from fastapi import HTTPException

# Allow direct execution from project root without extra PYTHONPATH setup.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from routes.prediction import (
    generate_wheel,
    get_available_guarantees,
    predict_consecutive_539,
    predict_coordinator_route,
    predict_double_bet,
    predict_dual_bet_539,
    predict_enhanced,
    predict_enhanced_all,
    predict_entropy_8_bets_route,
    predict_expert_certified_route,
    predict_from_backend,
    predict_from_backend_eval,
    predict_hyper_precision_2bet,
    predict_optimal,
    predict_smart_multi_bet,
    predict_triple_bet_539,
    predict_with_range,
    predict_core_satellite_route,
    predict_zone_split_route,
)
from schemas import PredictFromBackendRequest, PredictWithRangeRequest


PICK_COUNTS = {
    "BIG_LOTTO": 6,
    "POWER_LOTTO": 6,
    "DAILY_539": 5,
}


def _assert_numbers(numbers, expected_len, label):
    assert isinstance(numbers, list), f"{label}: numbers must be list"
    assert len(numbers) == expected_len, f"{label}: expected {expected_len} numbers, got {len(numbers)}"
    assert len(set(numbers)) == len(numbers), f"{label}: numbers should be unique"


def _assert_core_fields(res, expected_len, label):
    assert isinstance(res, dict), f"{label}: response must be dict"
    for field in ("numbers", "confidence", "method"):
        assert field in res, f"{label}: missing field {field}"
    _assert_numbers(res["numbers"], expected_len, label)


def _assert_model_info(res, expected_bets, lottery_type, label):
    assert "modelInfo" in res, f"{label}: missing modelInfo"
    model_info = res["modelInfo"]
    assert isinstance(model_info, dict), f"{label}: modelInfo must be dict"
    assert "bets" in model_info, f"{label}: modelInfo missing bets"
    assert "analysis" in model_info, f"{label}: modelInfo missing analysis"
    bets = model_info["bets"]
    analysis = model_info["analysis"]
    assert isinstance(bets, list), f"{label}: modelInfo.bets must be list"
    assert len(bets) == expected_bets, f"{label}: expected {expected_bets} bets, got {len(bets)}"
    assert analysis.get("num_bets") == expected_bets, f"{label}: analysis.num_bets mismatch"
    assert analysis.get("lottery_type") == lottery_type, f"{label}: analysis.lottery_type mismatch"


def _assert_bets_payload(bets, expected_bets, expected_len, label):
    assert isinstance(bets, list), f"{label}: bets must be list"
    assert len(bets) == expected_bets, f"{label}: expected {expected_bets} bets"
    for i, bet in enumerate(bets, 1):
        assert isinstance(bet, dict), f"{label}: bet#{i} must be dict"
        assert "numbers" in bet, f"{label}: bet#{i} missing numbers"
        _assert_numbers(bet["numbers"], expected_len, f"{label}.bet{i}")


async def _phase1_coordinator_contracts():
    req = PredictFromBackendRequest(lotteryType="POWER_BALL", modelType="coordinator_direct")
    res = await predict_from_backend(req, coord_mode="direct", coord_bets=2)
    _assert_core_fields(res, PICK_COUNTS["POWER_LOTTO"], "phase1.backend_coordinator")
    _assert_model_info(res, expected_bets=2, lottery_type="POWER_LOTTO", label="phase1.backend_coordinator")
    assert "special" in res, "phase1.backend_coordinator: POWER_LOTTO should have special"

    req_eval = PredictFromBackendRequest(lotteryType="DAILY_CASH_539", modelType="coordinator_hybrid")
    res_eval = await predict_from_backend_eval(req_eval, recent_count=250, coord_mode="hybrid", coord_bets=2)
    _assert_core_fields(res_eval, PICK_COUNTS["DAILY_539"], "phase1.backend_eval")
    _assert_model_info(res_eval, expected_bets=2, lottery_type="DAILY_539", label="phase1.backend_eval")

    req_range = PredictWithRangeRequest(
        lotteryType="BIG_LOTTO",
        modelType="coordinator",
        recentCount=400,
        coordMode="direct",
        coordBets=4,
    )
    res_range = await predict_with_range(req_range)
    _assert_core_fields(res_range, PICK_COUNTS["BIG_LOTTO"], "phase1.range_coordinator")
    _assert_model_info(res_range, expected_bets=4, lottery_type="BIG_LOTTO", label="phase1.range_coordinator")

    res_coord = await predict_coordinator_route(
        lottery_type="power-ball",
        num_bets=3,
        mode="hybrid",
        recent_count=300,
    )
    _assert_core_fields(res_coord, PICK_COUNTS["POWER_LOTTO"], "phase1.dedicated_coordinator")
    assert "bets" in res_coord and isinstance(res_coord["bets"], list), "phase1.dedicated_coordinator: missing bets"
    assert "analysis" in res_coord and isinstance(res_coord["analysis"], dict), "phase1.dedicated_coordinator: missing analysis"
    assert len(res_coord["bets"]) == 3, "phase1.dedicated_coordinator: expected 3 bets"
    assert res_coord["analysis"].get("num_bets") == 3, "phase1.dedicated_coordinator: analysis.num_bets mismatch"

    try:
        await predict_from_backend(req, coord_mode="invalid-mode", coord_bets=2)
    except HTTPException as e:
        assert e.status_code == 400, "phase1.invalid_mode: should be 400"
    else:
        raise AssertionError("phase1.invalid_mode: expected HTTPException(400)")


async def _phase2_general_prediction_contracts():
    req_backend_opt = PredictFromBackendRequest(lotteryType="BIGLOTTO", modelType="backend_optimized")
    res_backend_opt = await predict_from_backend(req_backend_opt)
    _assert_core_fields(res_backend_opt, PICK_COUNTS["BIG_LOTTO"], "phase2.backend_optimized")

    req_eval_opt = PredictFromBackendRequest(lotteryType="POWER_LOTTO", modelType="backend_optimized")
    res_eval_opt = await predict_from_backend_eval(req_eval_opt, recent_count=220)
    _assert_core_fields(res_eval_opt, PICK_COUNTS["POWER_LOTTO"], "phase2.eval_backend_optimized")
    assert "dataRange" in res_eval_opt and isinstance(res_eval_opt["dataRange"], dict), \
        "phase2.eval_backend_optimized: missing dataRange"

    req_range_opt = PredictWithRangeRequest(
        lotteryType="DAILY_539",
        modelType="backend_optimized",
        recentCount=300,
    )
    res_range_opt = await predict_with_range(req_range_opt)
    _assert_core_fields(res_range_opt, PICK_COUNTS["DAILY_539"], "phase2.range_backend_optimized")

    req_optimal = PredictFromBackendRequest(lotteryType="DAILY_CASH_539", modelType="any")
    res_optimal = await predict_optimal(req_optimal)
    _assert_core_fields(res_optimal, PICK_COUNTS["DAILY_539"], "phase2.predict_optimal")
    assert "optimalConfig" in res_optimal and isinstance(res_optimal["optimalConfig"], dict), \
        "phase2.predict_optimal: missing optimalConfig"


async def _phase3_enhanced_and_multi_contracts():
    req_enhanced = PredictFromBackendRequest(lotteryType="BIG_LOTTO", modelType="ignored")
    res_enhanced = await predict_enhanced(req_enhanced)
    _assert_core_fields(res_enhanced, PICK_COUNTS["BIG_LOTTO"], "phase3.predict_enhanced")

    req_enhanced_all = PredictFromBackendRequest(lotteryType="POWER_BALL", modelType="ignored")
    res_enhanced_all = await predict_enhanced_all(req_enhanced_all)
    assert isinstance(res_enhanced_all, dict), "phase3.predict_enhanced_all: response must be dict"
    assert "predictions" in res_enhanced_all and isinstance(res_enhanced_all["predictions"], list), \
        "phase3.predict_enhanced_all: missing predictions"
    assert res_enhanced_all["totalMethods"] >= 1, "phase3.predict_enhanced_all: no method succeeded"
    for idx, item in enumerate(res_enhanced_all["predictions"], 1):
        assert "numbers" in item, f"phase3.predict_enhanced_all: item#{idx} missing numbers"
        _assert_numbers(item["numbers"], PICK_COUNTS["POWER_LOTTO"], f"phase3.predict_enhanced_all.item{idx}")

    req_multi = PredictFromBackendRequest(lotteryType="DAILY_539", modelType="ignored")
    res_multi = await predict_smart_multi_bet(req_multi, num_bets=4)
    assert "bets" in res_multi and isinstance(res_multi["bets"], list), "phase3.smart_multi: missing bets"
    assert res_multi.get("totalBets") == 4, "phase3.smart_multi: totalBets mismatch"
    _assert_bets_payload(res_multi["bets"], expected_bets=4, expected_len=PICK_COUNTS["DAILY_539"], label="phase3.smart_multi")


async def _phase4_specialized_contracts():
    res_double = await predict_double_bet(lottery_type="power-lotto", mode="optimal")
    assert "bet1" in res_double and "bet2" in res_double, "phase4.double_bet: missing bet1/bet2"
    _assert_numbers(res_double["bet1"]["numbers"], PICK_COUNTS["POWER_LOTTO"], "phase4.double_bet.bet1")
    _assert_numbers(res_double["bet2"]["numbers"], PICK_COUNTS["POWER_LOTTO"], "phase4.double_bet.bet2")

    res_hyper = await predict_hyper_precision_2bet(lottery_type="BIG_LOTTO")
    assert "bets" in res_hyper and isinstance(res_hyper["bets"], list), "phase4.hyper: missing bets"
    assert len(res_hyper["bets"]) >= 1, "phase4.hyper: no bets returned"
    for i, bet in enumerate(res_hyper["bets"], 1):
        _assert_numbers(bet["numbers"], PICK_COUNTS["BIG_LOTTO"], f"phase4.hyper.bet{i}")

    req_entropy = PredictFromBackendRequest(lotteryType="BIG_LOTTO", modelType="ignored")
    res_entropy = await predict_entropy_8_bets_route(req_entropy)
    assert "bets" in res_entropy and isinstance(res_entropy["bets"], list), "phase4.entropy: missing bets"
    assert len(res_entropy["bets"]) == 8, "phase4.entropy: should return 8 bets"

    res_zone = await predict_zone_split_route(lottery_type="POWER_BALL", num_bets=3)
    assert "bets" in res_zone and isinstance(res_zone["bets"], list), "phase4.zone_split: missing bets"
    assert len(res_zone["bets"]) == 3, "phase4.zone_split: expected 3 bets"

    res_core_sat = await predict_core_satellite_route(lottery_type="BIGLOTTO", num_bets=3, core_size=2)
    assert "bets" in res_core_sat and isinstance(res_core_sat["bets"], list), "phase4.core_satellite: missing bets"
    assert len(res_core_sat["bets"]) == 3, "phase4.core_satellite: expected 3 bets"

    res_expert = await predict_expert_certified_route(lottery_type="POWER_LOTTO", num_bets=3)
    assert "bets" in res_expert and isinstance(res_expert["bets"], list), "phase4.expert: missing bets"
    assert len(res_expert["bets"]) == 3, "phase4.expert: expected 3 bets"


async def _phase5_539_and_wheel_contracts():
    res_dual_539 = await predict_dual_bet_539()
    assert "bets" in res_dual_539 and isinstance(res_dual_539["bets"], list), "phase5.dual_539: missing bets"
    assert res_dual_539.get("num_bets") == 2, "phase5.dual_539: num_bets should be 2"
    _assert_bets_payload(res_dual_539["bets"], expected_bets=2, expected_len=PICK_COUNTS["DAILY_539"], label="phase5.dual_539")

    res_triple_539 = await predict_triple_bet_539()
    assert "bets" in res_triple_539 and isinstance(res_triple_539["bets"], list), "phase5.triple_539: missing bets"
    assert res_triple_539.get("num_bets") == 3, "phase5.triple_539: num_bets should be 3"
    _assert_bets_payload(res_triple_539["bets"], expected_bets=3, expected_len=PICK_COUNTS["DAILY_539"], label="phase5.triple_539")

    res_consecutive = await predict_consecutive_539()
    _assert_core_fields(res_consecutive, PICK_COUNTS["DAILY_539"], "phase5.consecutive_539")

    pool = [1, 5, 7, 12, 15, 22, 28, 31, 35, 38]
    res_wheel = await generate_wheel(pool=pool, guarantee_t=3, condition_m=4)
    assert "tickets" in res_wheel and isinstance(res_wheel["tickets"], list), "phase5.wheel: missing tickets"
    assert res_wheel.get("pool_size") == len(pool), "phase5.wheel: pool_size mismatch"
    assert isinstance(res_wheel.get("ticket_count"), int) and res_wheel["ticket_count"] > 0, \
        "phase5.wheel: invalid ticket_count"

    res_guarantees = await get_available_guarantees(pool_size=10)
    assert "available_guarantees" in res_guarantees and isinstance(res_guarantees["available_guarantees"], list), \
        "phase5.wheel_guarantees: missing available_guarantees"


async def main():
    await _phase1_coordinator_contracts()
    print("OK: phase1 coordinator contracts passed")

    await _phase2_general_prediction_contracts()
    print("OK: phase2 general prediction contracts passed")

    await _phase3_enhanced_and_multi_contracts()
    print("OK: phase3 enhanced/multi contracts passed")

    await _phase4_specialized_contracts()
    print("OK: phase4 specialized contracts passed")

    await _phase5_539_and_wheel_contracts()
    print("OK: phase5 539/wheel contracts passed")

    print("OK: prediction API contract tests passed")


if __name__ == "__main__":
    asyncio.run(main())
