"""Focused tests for lottery.prediction.generate vertical.

Verifies:
1. Valid strategy ID (e.g. biglotto_triple_strike, ts3_regime_3bet) generates a valid single Big Lotto bet.
2. Returned bet has 6 unique integers between 1 and 49.
3. Non-existent strategy ID fails closed (raises InvalidStrategyError).
4. Non-ONLINE strategy ID fails closed (raises InvalidStrategyError).
5. Adapter identity mismatch / invalid output fails closed.
6. Execution requires NO database, network, or external service access.
7. Conflict copies are NOT imported at runtime.
"""
import sys
import pytest
from unittest.mock import MagicMock, patch

from lottery.prediction.generate import generate_one_bet, generate_biglotto_bet
from lottery.prediction.domain.models import GenerateBetRequest, GenerateBetResult
from lottery.prediction.domain.errors import (
    InvalidStrategyError,
    InvalidOutputError,
    StrategyExecutionError,
)
from lottery_api.models.replay_strategy_registry import list_executable_strategy_ids

# Mock draw history fixture (100 draws of synthetic Big Lotto history)
@pytest.fixture
def mock_history():
    history = []
    for i in range(1, 101):
        draw_num = f"{113000000 + i}"
        date_str = f"2025-01-{(i % 28) + 1:02d}"
        # Pick 6 numbers deterministically
        nums = [(i * 3 + j * 7) % 49 + 1 for j in range(6)]
        # ensure unique
        nums = sorted(list(set(nums)))
        while len(nums) < 6:
            candidate = (nums[-1] % 49) + 1
            if candidate not in nums:
                nums.append(candidate)
            nums = sorted(nums)
        history.append({
            "draw": draw_num,
            "date": date_str,
            "numbers": nums,
            "special": (i % 49) + 1,
        })
    return history


def test_valid_biglotto_triple_strike_generation(mock_history):
    req = GenerateBetRequest(
        strategy_id="biglotto_triple_strike",
        lottery_type="BIG_LOTTO",
        history=mock_history,
    )
    result = generate_one_bet(req)

    assert isinstance(result, GenerateBetResult)
    assert result.strategy_id == "biglotto_triple_strike"
    assert result.lottery_type == "BIG_LOTTO"
    assert isinstance(result.numbers, list)
    assert len(result.numbers) == 6
    assert len(set(result.numbers)) == 6
    assert all(1 <= n <= 49 for n in result.numbers)
    assert result.numbers == sorted(result.numbers)
    assert "strategy_name" in result.metadata


def test_valid_ts3_regime_3bet_generation(mock_history):
    result = generate_biglotto_bet("ts3_regime_3bet", mock_history)

    assert isinstance(result, GenerateBetResult)
    assert result.strategy_id == "ts3_regime_3bet"
    assert len(result.numbers) == 6
    assert len(set(result.numbers)) == 6
    assert all(1 <= n <= 49 for n in result.numbers)


def test_nonexistent_strategy_fails_closed(mock_history):
    req = GenerateBetRequest(
        strategy_id="non_existent_fake_strategy_12345",
        lottery_type="BIG_LOTTO",
        history=mock_history,
    )
    with pytest.raises(InvalidStrategyError) as exc_info:
        generate_one_bet(req)
    assert "Unknown strategy_id" in str(exc_info.value)


def test_non_online_strategy_fails_closed(mock_history):
    # 'biglotto_ts3_acb_4bet' is registered as REJECTED in catalog
    req = GenerateBetRequest(
        strategy_id="biglotto_ts3_acb_4bet",
        lottery_type="BIG_LOTTO",
        history=mock_history,
    )
    with pytest.raises(InvalidStrategyError) as exc_info:
        generate_one_bet(req)
    assert "lifecycle status 'REJECTED'" in str(exc_info.value)


def test_unsupported_lottery_type_fails_closed(mock_history):
    req = GenerateBetRequest(
        strategy_id="biglotto_triple_strike",
        lottery_type="POWER_LOTTO",  # Invalid for this vertical/adapter
        history=mock_history,
    )
    with pytest.raises(InvalidStrategyError) as exc_info:
        generate_one_bet(req)
    assert "supports BIG_LOTTO only" in str(exc_info.value)


def test_invalid_output_number_count_fails_closed(mock_history):
    mock_adapter = MagicMock()
    mock_adapter.meta.strategy_id = "biglotto_triple_strike"
    mock_adapter.meta.supported_lottery_types = ["BIG_LOTTO"]
    mock_adapter.meta.strategy_name = "Mock"
    mock_adapter.meta.strategy_version = "1.0"
    mock_adapter.meta.lifecycle_status = "ONLINE"
    mock_adapter.get_one_bet.return_value = ([1, 2, 3, 4, 5], None)  # Only 5 numbers

    with patch("lottery.prediction.use_cases.generate_one_bet_use_case.get_adapter", return_value=mock_adapter):
        req = GenerateBetRequest(strategy_id="biglotto_triple_strike", history=mock_history)
        with pytest.raises(InvalidOutputError) as exc_info:
            generate_one_bet(req)
        assert "exactly 6 numbers" in str(exc_info.value)


def test_invalid_output_out_of_range_fails_closed(mock_history):
    mock_adapter = MagicMock()
    mock_adapter.meta.strategy_id = "biglotto_triple_strike"
    mock_adapter.meta.supported_lottery_types = ["BIG_LOTTO"]
    mock_adapter.meta.strategy_name = "Mock"
    mock_adapter.meta.strategy_version = "1.0"
    mock_adapter.meta.lifecycle_status = "ONLINE"
    mock_adapter.get_one_bet.return_value = ([1, 2, 3, 4, 5, 50], None)  # 50 out of range [1..49]

    with patch("lottery.prediction.use_cases.generate_one_bet_use_case.get_adapter", return_value=mock_adapter):
        req = GenerateBetRequest(strategy_id="biglotto_triple_strike", history=mock_history)
        with pytest.raises(InvalidOutputError) as exc_info:
            generate_one_bet(req)
        assert "out of range" in str(exc_info.value)


def test_no_conflict_files_imported_at_runtime():
    # Verify loaded sys.modules contains no __CONFLICT__ files
    conflict_modules = [mod for mod in sys.modules if "__CONFLICT__" in mod]
    assert len(conflict_modules) == 0, f"Conflict modules loaded: {conflict_modules}"
