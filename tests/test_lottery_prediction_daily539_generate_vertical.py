"""Focused integration tests for Daily 539 single bet prediction vertical."""
import pytest
from unittest.mock import patch, MagicMock

import lottery.prediction.daily539 as daily539
from lottery.prediction.daily539.models import (
    Daily539GenerateBetRequest,
    Daily539GenerateBetResult,
)
from lottery.prediction.daily539.use_cases import Daily539GenerateOneBetUseCase
from lottery.prediction.domain.errors import (
    InvalidStrategyError,
    InvalidOutputError,
    StrategyExecutionError,
)

@pytest.fixture
def mock_history():
    """Returns a realistic mock history slice of 150 draws for Daily 539."""
    return [
        {
            "date": f"2025-01-{(i % 28) + 1:02d}",
            "draw": f"114000{i:03d}",
            "numbers": [(i + k) % 39 + 1 for k in range(5)],
        }
        for i in range(1, 151)
    ]

# 1. Valid Daily 539 strategy generates one bet
def test_valid_daily539_strategy_generates_one_bet(mock_history):
    res = daily539.generate_daily539_bet("daily539_f4cold", history=mock_history)
    assert isinstance(res, Daily539GenerateBetResult)
    assert res.strategy_id == "daily539_f4cold"
    assert res.lottery_type == "DAILY_539"
    assert res.special is None
    assert len(res.numbers) == 5

# 2. Exactly 5 numbers
def test_result_has_exactly_five_numbers(mock_history):
    res = daily539.generate_daily539_bet("daily539_markov_cold", history=mock_history)
    assert len(res.numbers) == 5

# 3. Numbers are true integers
def test_numbers_are_true_integers(mock_history):
    res = daily539.generate_daily539_bet("daily539_f4cold", history=mock_history)
    for num in res.numbers:
        assert type(num) is int
        assert not isinstance(num, bool)

# 4. Reject bool elements in numbers
def test_bool_elements_rejected():
    use_case = Daily539GenerateOneBetUseCase()
    with pytest.raises(InvalidOutputError):
        use_case._validate_daily539_numbers([1, 2, 3, 4, True], None, "test_strat")

# 5. Number range [1..39]
def test_numbers_within_valid_range_1_to_39(mock_history):
    res = daily539.generate_daily539_bet("daily539_f4cold", history=mock_history)
    for n in res.numbers:
        assert 1 <= n <= 39

# 6. Numbers are unique
def test_numbers_are_unique(mock_history):
    res = daily539.generate_daily539_bet("daily539_f4cold", history=mock_history)
    assert len(set(res.numbers)) == 5

# 7. Non-existent strategy ID fails closed
def test_nonexistent_strategy_id_fails_closed(mock_history):
    req = Daily539GenerateBetRequest(strategy_id="non_existent_539_strat", history=mock_history)
    with pytest.raises(InvalidStrategyError) as exc_info:
        daily539.generate_one_bet(req)
    assert "Unknown strategy_id" in str(exc_info.value)

# 8. Non-executable lifecycle fails closed (RETIRED / REJECTED)
def test_retired_strategy_lifecycle_fails_closed(mock_history):
    req = Daily539GenerateBetRequest(strategy_id="daily539_f4cold_5bet", history=mock_history)
    with pytest.raises(InvalidStrategyError) as exc_info:
        daily539.generate_one_bet(req)
    assert "lifecycle status" in str(exc_info.value)

# 9. Adapter identity mismatch fails closed
def test_adapter_identity_mismatch_fails_closed(mock_history):
    with patch("lottery.prediction.daily539.use_cases.get_adapter") as mock_get_adapter:
        mock_adapter = MagicMock()
        mock_adapter.meta.strategy_id = "mismatched_id"
        mock_get_adapter.return_value = mock_adapter

        req = Daily539GenerateBetRequest(strategy_id="daily539_f4cold", history=mock_history)
        with pytest.raises(InvalidStrategyError) as exc_info:
            daily539.generate_one_bet(req)
        assert "mismatch" in str(exc_info.value)

# 10. Four or six numbers fail closed
def test_incorrect_number_count_fails_closed(mock_history):
    mock_adapter = MagicMock()
    mock_adapter.meta.strategy_id = "daily539_f4cold"
    mock_adapter.meta.supported_lottery_types = ["DAILY_539"]
    mock_adapter.meta.strategy_name = "Mock"
    mock_adapter.meta.strategy_version = "1.0"
    mock_adapter.meta.lifecycle_status = "ONLINE"
    mock_adapter.get_one_bet.return_value = ([1, 2, 3, 4], None)  # 4 numbers

    with patch("lottery.prediction.daily539.use_cases.get_adapter", return_value=mock_adapter):
        req = Daily539GenerateBetRequest(strategy_id="daily539_f4cold", history=mock_history)
        with pytest.raises(InvalidOutputError) as exc_info:
            daily539.generate_one_bet(req)
        assert "exactly 5 numbers" in str(exc_info.value)

# 11. Duplicate numbers fail closed
def test_duplicate_numbers_fail_closed(mock_history):
    mock_adapter = MagicMock()
    mock_adapter.meta.strategy_id = "daily539_f4cold"
    mock_adapter.meta.supported_lottery_types = ["DAILY_539"]
    mock_adapter.meta.strategy_name = "Mock"
    mock_adapter.meta.strategy_version = "1.0"
    mock_adapter.meta.lifecycle_status = "ONLINE"
    mock_adapter.get_one_bet.return_value = ([1, 2, 3, 4, 4], None)  # Duplicate 4

    with patch("lottery.prediction.daily539.use_cases.get_adapter", return_value=mock_adapter):
        req = Daily539GenerateBetRequest(strategy_id="daily539_f4cold", history=mock_history)
        with pytest.raises(InvalidOutputError) as exc_info:
            daily539.generate_one_bet(req)
        assert "duplicates" in str(exc_info.value)

# 12. Out of range number (0 or 40) fails closed
def test_out_of_range_number_fails_closed(mock_history):
    mock_adapter = MagicMock()
    mock_adapter.meta.strategy_id = "daily539_f4cold"
    mock_adapter.meta.supported_lottery_types = ["DAILY_539"]
    mock_adapter.meta.strategy_name = "Mock"
    mock_adapter.meta.strategy_version = "1.0"
    mock_adapter.meta.lifecycle_status = "ONLINE"
    mock_adapter.get_one_bet.return_value = ([0, 2, 3, 4, 5], None)  # 0 out of range

    with patch("lottery.prediction.daily539.use_cases.get_adapter", return_value=mock_adapter):
        req = Daily539GenerateBetRequest(strategy_id="daily539_f4cold", history=mock_history)
        with pytest.raises(InvalidOutputError) as exc_info:
            daily539.generate_one_bet(req)
        assert "out of range" in str(exc_info.value)

# 13. Special number present fails closed for Daily 539
def test_special_number_present_fails_closed(mock_history):
    mock_adapter = MagicMock()
    mock_adapter.meta.strategy_id = "daily539_f4cold"
    mock_adapter.meta.supported_lottery_types = ["DAILY_539"]
    mock_adapter.meta.strategy_name = "Mock"
    mock_adapter.meta.strategy_version = "1.0"
    mock_adapter.meta.lifecycle_status = "ONLINE"
    mock_adapter.get_one_bet.return_value = ([1, 2, 3, 4, 5], 6)  # Special number 6 present

    with patch("lottery.prediction.daily539.use_cases.get_adapter", return_value=mock_adapter):
        req = Daily539GenerateBetRequest(strategy_id="daily539_f4cold", history=mock_history)
        with pytest.raises(InvalidOutputError) as exc_info:
            daily539.generate_one_bet(req)
        assert "must not have special number" in str(exc_info.value)

# 14. Strategy exception converted to typed failure
def test_strategy_exception_converted_to_typed_error(mock_history):
    mock_adapter = MagicMock()
    mock_adapter.meta.strategy_id = "daily539_f4cold"
    mock_adapter.meta.supported_lottery_types = ["DAILY_539"]
    mock_adapter.meta.strategy_name = "Mock"
    mock_adapter.meta.strategy_version = "1.0"
    mock_adapter.meta.lifecycle_status = "ONLINE"
    mock_adapter.get_one_bet.side_effect = RuntimeError("Internal math failure")

    with patch("lottery.prediction.daily539.use_cases.get_adapter", return_value=mock_adapter):
        req = Daily539GenerateBetRequest(strategy_id="daily539_f4cold", history=mock_history)
        with pytest.raises(StrategyExecutionError) as exc_info:
            daily539.generate_one_bet(req)
        assert "Strategy execution error" in str(exc_info.value)

# 15. Public entrypoint calls use case and registry
def test_public_entrypoint_uses_registry(mock_history):
    with patch.object(Daily539GenerateOneBetUseCase, "execute", wraps=Daily539GenerateOneBetUseCase().execute) as mock_exec:
        res = daily539.generate_daily539_bet("daily539_f4cold", history=mock_history)
        assert mock_exec.call_count == 1
        assert res.strategy_id == "daily539_f4cold"

# 16. No conflict copy imported
def test_no_conflict_copy_imported():
    import sys
    for mod_name in sys.modules:
        assert "__CONFLICT__" not in mod_name

# 17. No DB access
def test_no_database_accessed(mock_history):
    with patch("sqlite3.connect", side_effect=AssertionError("DB connection prohibited")):
        res = daily539.generate_daily539_bet("daily539_f4cold", history=mock_history)
        assert len(res.numbers) == 5
