"""
P1.4 — ts3_regime_3bet Adapter Binding Resolution Tests
========================================================
Verifies that the P1.4 safe reconstruction of ts3_regime_3bet:
  1. Does NOT raise AdapterBindingPending (binding is resolved).
  2. Returns 6 valid BIG_LOTTO main numbers (range 1-49) when called with
     sufficient history.
  3. Registry entry exists with lifecycle=ONLINE and lottery_type=BIG_LOTTO.
  4. Adapter binding_status is BOUND (no longer PendingAdapter).

BIG_LOTTO rules (from codebase constants):
  - 6 main numbers from pool 1-49
  - special number in range 1-8 (not used in replay v0.1 — always None)

All existing 153 tests must remain PASS (see validation commands in mission doc).

Generated: 2026-05-15  |  Classification: P14_TS3_REGIME_ADAPTER_BINDING_READY
"""
import random
import pytest

from lottery_api.models.replay_strategy_registry import (
    AdapterBindingPending,
    InsufficientHistory,
    LifecycleNotExecutable,
    RejectPrediction,
    UnsupportedLotteryType,
    get_adapter,
    get_adapters_for_lottery,
    get_strategy_lifecycle_status,
    list_non_executable_strategy_ids,
)


# ─── Fixture helpers ──────────────────────────────────────────────────────────

def _make_big_lotto_history(n: int, seed: int = 42) -> list:
    """
    Generate synthetic BIG_LOTTO history with n draws.
    Each draw: {'numbers': sorted list of 6 distinct ints from 1-49,
                'special': int 1-8, 'draw': str draw number, 'date': str}
    """
    rng = random.Random(seed)
    history = []
    for i in range(n):
        nums = sorted(rng.sample(range(1, 50), 6))
        history.append({
            "numbers": nums,
            "special": rng.randint(1, 8),
            "draw": str(110000000 + i),
            "date": f"2025-01-{(i % 28) + 1:02d}",
        })
    return history


# ─── Registry and lifecycle tests ────────────────────────────────────────────

class TestTs3Regime3BetRegistryEntry:
    """Registry metadata assertions — independent of callable execution."""

    def test_strategy_exists_in_registry(self):
        adapter = get_adapter("ts3_regime_3bet")
        assert adapter is not None, "ts3_regime_3bet not found in _REGISTRY"

    def test_strategy_id_correct(self):
        adapter = get_adapter("ts3_regime_3bet")
        assert adapter.meta.strategy_id == "ts3_regime_3bet"

    def test_lifecycle_status_is_online(self):
        status = get_strategy_lifecycle_status("ts3_regime_3bet")
        assert status == "ONLINE", f"Expected ONLINE, got {status}"

    def test_lottery_type_is_big_lotto(self):
        adapter = get_adapter("ts3_regime_3bet")
        assert "BIG_LOTTO" in adapter.meta.supported_lottery_types

    def test_not_in_non_executable_list(self):
        non_exec = list_non_executable_strategy_ids()
        assert "ts3_regime_3bet" not in non_exec

    def test_appears_in_big_lotto_adapters(self):
        ids = {a.meta.strategy_id for a in get_adapters_for_lottery("BIG_LOTTO")}
        assert "ts3_regime_3bet" in ids

    def test_min_history_is_100(self):
        adapter = get_adapter("ts3_regime_3bet")
        assert adapter.meta.min_history == 100

    def test_strategy_version_is_v01(self):
        adapter = get_adapter("ts3_regime_3bet")
        assert adapter.meta.strategy_version == "v0.1"


# ─── Adapter binding tests ────────────────────────────────────────────────────

class TestTs3Regime3BetAdapterBinding:
    """Verify P1.4 binding is resolved — no AdapterBindingPending raised."""

    def test_adapter_not_pending(self):
        """After P1.4 binding, calling get_one_bet must not raise AdapterBindingPending."""
        adapter = get_adapter("ts3_regime_3bet")
        try:
            adapter.get_one_bet([], "BIG_LOTTO")
        except AdapterBindingPending as e:
            pytest.fail(
                f"ts3_regime_3bet still raises AdapterBindingPending after P1.4: {e}"
            )
        except Exception:
            pass  # InsufficientHistory or other non-binding error — OK

    def test_adapter_not_lifecycle_not_executable(self):
        """ONLINE strategy must not raise LifecycleNotExecutable."""
        adapter = get_adapter("ts3_regime_3bet")
        try:
            adapter.get_one_bet([], "BIG_LOTTO")
        except LifecycleNotExecutable as e:
            pytest.fail(
                f"ts3_regime_3bet (ONLINE) raised LifecycleNotExecutable: {e}"
            )
        except Exception:
            pass  # Other errors acceptable

    def test_insufficient_history_raises_insufficient_history(self):
        """Empty history must raise InsufficientHistory (not AdapterBindingPending)."""
        adapter = get_adapter("ts3_regime_3bet")
        with pytest.raises(InsufficientHistory):
            adapter.get_one_bet([], "BIG_LOTTO")

    def test_unsupported_lottery_type_raises_error(self):
        """Calling with DAILY_539 must raise UnsupportedLotteryType."""
        adapter = get_adapter("ts3_regime_3bet")
        with pytest.raises(UnsupportedLotteryType):
            adapter.get_one_bet(_make_big_lotto_history(200), "DAILY_539")


# ─── Output validity tests ────────────────────────────────────────────────────

class TestTs3Regime3BetOutputValidity:
    """Verify callable returns valid BIG_LOTTO bets with sufficient history."""

    def test_returns_tuple_of_two(self):
        """get_one_bet must return (numbers, special)."""
        adapter = get_adapter("ts3_regime_3bet")
        history = _make_big_lotto_history(200)
        result = adapter.get_one_bet(history, "BIG_LOTTO")
        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        assert len(result) == 2, f"Expected 2-tuple, got length {len(result)}"

    def test_numbers_is_list_of_six(self):
        """BIG_LOTTO bet must contain exactly 6 main numbers."""
        adapter = get_adapter("ts3_regime_3bet")
        history = _make_big_lotto_history(200)
        numbers, _ = adapter.get_one_bet(history, "BIG_LOTTO")
        assert isinstance(numbers, list), f"numbers must be list, got {type(numbers)}"
        assert len(numbers) == 6, f"Expected 6 numbers, got {len(numbers)}: {numbers}"

    def test_numbers_in_valid_range(self):
        """All main numbers must be in range 1-49."""
        adapter = get_adapter("ts3_regime_3bet")
        history = _make_big_lotto_history(200)
        numbers, _ = adapter.get_one_bet(history, "BIG_LOTTO")
        for n in numbers:
            assert 1 <= n <= 49, f"Number {n} out of range 1-49"

    def test_numbers_are_distinct(self):
        """All 6 main numbers must be distinct."""
        adapter = get_adapter("ts3_regime_3bet")
        history = _make_big_lotto_history(200)
        numbers, _ = adapter.get_one_bet(history, "BIG_LOTTO")
        assert len(set(numbers)) == 6, f"Duplicate numbers found: {numbers}"

    def test_special_is_none(self):
        """BIG_LOTTO special is always None in replay v0.1."""
        adapter = get_adapter("ts3_regime_3bet")
        history = _make_big_lotto_history(200)
        _, special = adapter.get_one_bet(history, "BIG_LOTTO")
        assert special is None, f"Expected special=None, got {special}"

    def test_numbers_are_sorted(self):
        """Returned numbers must be sorted ascending."""
        adapter = get_adapter("ts3_regime_3bet")
        history = _make_big_lotto_history(200)
        numbers, _ = adapter.get_one_bet(history, "BIG_LOTTO")
        assert numbers == sorted(numbers), f"Numbers not sorted: {numbers}"

    def test_deterministic_output_same_history(self):
        """Same history must produce the same bet (deterministic)."""
        adapter = get_adapter("ts3_regime_3bet")
        history = _make_big_lotto_history(200, seed=99)
        r1, _ = adapter.get_one_bet(history, "BIG_LOTTO")
        r2, _ = adapter.get_one_bet(history, "BIG_LOTTO")
        assert r1 == r2, f"Non-deterministic output: {r1} != {r2}"

    def test_minimum_history_boundary(self):
        """Exactly 100 draws must not raise InsufficientHistory."""
        adapter = get_adapter("ts3_regime_3bet")
        history = _make_big_lotto_history(100)
        try:
            numbers, special = adapter.get_one_bet(history, "BIG_LOTTO")
            assert len(numbers) == 6
        except InsufficientHistory:
            pytest.fail("100-draw history should be sufficient (min_history=100)")


# ─── Regression: AdapterBindingPending class still importable ─────────────────

class TestAdapterBindingPendingRetention:
    """AdapterBindingPending class must still be importable (import compatibility)."""

    def test_class_is_importable(self):
        """AdapterBindingPending must remain in the module for import compatibility."""
        from lottery_api.models.replay_strategy_registry import AdapterBindingPending
        assert AdapterBindingPending is not None

    def test_class_is_exception_subclass(self):
        from lottery_api.models.replay_strategy_registry import AdapterBindingPending
        assert issubclass(AdapterBindingPending, Exception)
