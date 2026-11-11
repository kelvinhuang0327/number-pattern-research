"""Focused test suite for Big Lotto batch generation vertical.

Verifies:
1. count=1 returns a tuple of 1 canonical GenerateBetResult.
2. count=3 returns a tuple of 3 canonical GenerateBetResults in order.
3. Each bet in the batch contains 6 unique integers in range [1..49].
4. Non-existent strategy ID fails closed (InvalidStrategyError).
5. count=0 fails closed (InvalidBatchCountError).
6. Negative count fails closed (InvalidBatchCountError).
7. count > MAX_BATCH_SIZE (20) fails closed (InvalidBatchCountError).
8. Non-int count fails closed (InvalidBatchCountError).
9. bool count (True/False) fails closed (InvalidBatchCountError).
10. Adapter identity mismatch fails closed (InvalidStrategyError).
11. Mid-sequence strategy failure fails closed atomically (zero partial results).
12. Invalid single bet output makes entire batch fail closed.
13. Batch use case reuses canonical single-bet path (GenerateOneBetUseCase).
14. No conflict files imported at runtime.
15. No DB access during batch generation.
"""
import sys
import pytest
from unittest.mock import MagicMock, patch

from lottery.prediction.batch_generate import generate_bets
from lottery.prediction.generate import generate_one_bet
from lottery.prediction.domain.models import GenerateBatchRequest, GenerateBetResult, MAX_BATCH_SIZE
from lottery.prediction.domain.errors import (
    InvalidBatchCountError,
    InvalidStrategyError,
    InvalidOutputError,
    StrategyExecutionError,
)
from lottery.prediction.use_cases.generate_batch_use_case import GenerateBatchUseCase
from lottery.prediction.use_cases.generate_one_bet_use_case import GenerateOneBetUseCase

@pytest.fixture
def mock_history():
    history = []
    for i in range(1, 101):
        draw_num = f"{113000000 + i}"
        date_str = f"2025-01-{(i % 28) + 1:02d}"
        nums = [(i * 3 + j * 7) % 49 + 1 for j in range(6)]
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


def test_batch_generate_count_1(mock_history):
    results = generate_bets(strategy_id="biglotto_triple_strike", count=1, history=mock_history)

    assert isinstance(results, tuple)
    assert len(results) == 1
    res = results[0]
    assert isinstance(res, GenerateBetResult)
    assert res.strategy_id == "biglotto_triple_strike"
    assert len(res.numbers) == 6
    assert len(set(res.numbers)) == 6
    assert all(1 <= n <= 49 for n in res.numbers)


def test_batch_generate_count_3(mock_history):
    results = generate_bets(strategy_id="biglotto_triple_strike", count=3, history=mock_history)

    assert isinstance(results, tuple)
    assert len(results) == 3
    for res in results:
        assert isinstance(res, GenerateBetResult)
        assert res.strategy_id == "biglotto_triple_strike"
        assert len(res.numbers) == 6
        assert len(set(res.numbers)) == 6
        assert all(1 <= n <= 49 for n in res.numbers)


def test_batch_generate_max_allowed_count(mock_history):
    results = generate_bets(strategy_id="ts3_regime_3bet", count=MAX_BATCH_SIZE, history=mock_history)

    assert isinstance(results, tuple)
    assert len(results) == MAX_BATCH_SIZE
    for res in results:
        assert res.strategy_id == "ts3_regime_3bet"
        assert len(res.numbers) == 6


def test_batch_generate_count_zero_fails_closed(mock_history):
    with pytest.raises(InvalidBatchCountError) as exc_info:
        generate_bets(strategy_id="biglotto_triple_strike", count=0, history=mock_history)
    assert "count must be >= 1" in str(exc_info.value)


def test_batch_generate_negative_count_fails_closed(mock_history):
    with pytest.raises(InvalidBatchCountError) as exc_info:
        generate_bets(strategy_id="biglotto_triple_strike", count=-5, history=mock_history)
    assert "count must be >= 1" in str(exc_info.value)


def test_batch_generate_exceed_max_count_fails_closed(mock_history):
    with pytest.raises(InvalidBatchCountError) as exc_info:
        generate_bets(strategy_id="biglotto_triple_strike", count=MAX_BATCH_SIZE + 1, history=mock_history)
    assert "exceeds maximum allowed batch size" in str(exc_info.value)


def test_batch_generate_non_int_count_fails_closed(mock_history):
    with pytest.raises(InvalidBatchCountError) as exc_info:
        generate_bets(strategy_id="biglotto_triple_strike", count=2.5, history=mock_history)  # type: ignore
    assert "count must be an integer" in str(exc_info.value)


def test_batch_generate_bool_count_fails_closed(mock_history):
    with pytest.raises(InvalidBatchCountError) as exc_info:
        generate_bets(strategy_id="biglotto_triple_strike", count=True, history=mock_history)  # type: ignore
    assert "count must be an integer" in str(exc_info.value)

    with pytest.raises(InvalidBatchCountError) as exc_info:
        generate_bets(strategy_id="biglotto_triple_strike", count=False, history=mock_history)  # type: ignore
    assert "count must be an integer" in str(exc_info.value)


def test_batch_generate_nonexistent_strategy_fails_closed(mock_history):
    with pytest.raises(InvalidStrategyError) as exc_info:
        generate_bets(strategy_id="nonexistent_strategy_xyz", count=3, history=mock_history)
    assert "Unknown strategy_id" in str(exc_info.value)


def test_batch_generate_reuses_single_bet_use_case(mock_history):
    mock_single_use_case = MagicMock(spec=GenerateOneBetUseCase)
    mock_result = GenerateBetResult(
        strategy_id="biglotto_triple_strike",
        lottery_type="BIG_LOTTO",
        numbers=[1, 2, 3, 4, 5, 6],
    )
    mock_single_use_case.execute.return_value = mock_result

    batch_use_case = GenerateBatchUseCase(single_bet_use_case=mock_single_use_case)
    req = GenerateBatchRequest(strategy_id="biglotto_triple_strike", count=4, history=mock_history)

    res = batch_use_case.execute(req)

    assert len(res) == 4
    assert mock_single_use_case.execute.call_count == 4


def test_batch_generate_mid_sequence_failure_fails_closed(mock_history):
    mock_single_use_case = MagicMock(spec=GenerateOneBetUseCase)
    mock_result = GenerateBetResult(
        strategy_id="biglotto_triple_strike",
        lottery_type="BIG_LOTTO",
        numbers=[1, 2, 3, 4, 5, 6],
    )
    # First 2 succeed, 3rd fails
    mock_single_use_case.execute.side_effect = [
        mock_result,
        mock_result,
        StrategyExecutionError("Mid-sequence strategy execution failure"),
    ]

    batch_use_case = GenerateBatchUseCase(single_bet_use_case=mock_single_use_case)
    req = GenerateBatchRequest(strategy_id="biglotto_triple_strike", count=5, history=mock_history)

    with pytest.raises(StrategyExecutionError) as exc_info:
        batch_use_case.execute(req)

    assert "Mid-sequence" in str(exc_info.value)
    # Verify exact call count before failure
    assert mock_single_use_case.execute.call_count == 3


def test_batch_generate_adapter_identity_mismatch_fails_closed(mock_history):
    with patch("lottery.prediction.use_cases.generate_one_bet_use_case.get_adapter") as mock_get_adapter:
        mock_adapter = MagicMock()
        mock_adapter.meta.strategy_id = "different_strategy_id"
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(InvalidStrategyError) as exc_info:
            generate_bets(strategy_id="biglotto_triple_strike", count=2, history=mock_history)
        assert "Adapter identity mismatch" in str(exc_info.value)


def test_batch_generate_invalid_single_result_fails_closed(mock_history):
    mock_single_use_case = MagicMock(spec=GenerateOneBetUseCase)
    mock_single_use_case.execute.side_effect = InvalidOutputError("Single bet numbers out of range")

    batch_use_case = GenerateBatchUseCase(single_bet_use_case=mock_single_use_case)
    req = GenerateBatchRequest(strategy_id="biglotto_triple_strike", count=3, history=mock_history)

    with pytest.raises(InvalidOutputError) as exc_info:
        batch_use_case.execute(req)
    assert "Single bet numbers out of range" in str(exc_info.value)


def test_batch_generate_no_db_access(mock_history):
    with patch("sqlite3.connect", side_effect=RuntimeError("DB access forbidden in batch generate vertical")):
        results = generate_bets(strategy_id="biglotto_triple_strike", count=3, history=mock_history)
        assert len(results) == 3


def test_batch_generate_no_conflict_files_imported():
    conflict_modules = [mod for mod in sys.modules if "__CONFLICT__" in mod]
    assert len(conflict_modules) == 0, f"Conflict modules loaded: {conflict_modules}"

