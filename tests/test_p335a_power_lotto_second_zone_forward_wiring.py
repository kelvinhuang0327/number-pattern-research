"""
test_p335a_power_lotto_second_zone_forward_wiring.py
====================================================
P335A — guard tests for the canonical POWER_LOTTO second-zone helper.

Proves that a future POWER_LOTTO row-builder wired through
``second_zone_predict()`` / ``assert_power_lotto_predicted_special()`` cannot
persist ``predicted_special = None`` for sufficient history — the exact
"Generation-B" regression that produced 27,104 historical NULL rows
(P333A / P334A read-only audits).

Pure unit tests: deterministic synthetic in-memory history only.
NO DB read/write, no backfill, no network, no prediction claim, no
recommended numbers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.power_lotto_second_zone import (  # noqa: E402
    MIN_HISTORY,
    SPECIAL_MAX,
    SPECIAL_MIN,
    InsufficientHistoryError,
    _frequency_fallback,
    assert_power_lotto_predicted_special,
    second_zone_predict,
)
from lottery_api.models import replay_strategy_registry as replay_registry  # noqa: E402
from lottery_api.models.replay_strategy_registry import (  # noqa: E402
    InsufficientHistory,
    get_adapter,
)


POWER_DESCRIPTOR_CASES = (
    (
        "power_precision_3bet",
        "威力彩 Precision 3注",
        "v0.1",
        3,
    ),
    (
        "power_orthogonal_5bet",
        "威力彩 Orthogonal 5注",
        "v0.1",
        5,
    ),
    (
        "fourier_rhythm_3bet",
        "威力彩 Fourier Rhythm 3注",
        "v0.1",
        3,
    ),
)


def _make_history(n: int) -> list:
    """Deterministic synthetic POWER_LOTTO draw history (no RNG).

    Each draw carries 6 distinct mains in [1,38], one special in [1,8], a draw
    id and a date — a fixed function of the index, so results are fully
    reproducible run-to-run.
    """
    history = []
    for i in range(n):
        base = (i * 7) % 33 + 1
        numbers = sorted({((base + k * 5 - 1) % 38) + 1 for k in range(6)})
        j = 1
        while len(numbers) < 6:  # deterministic fill on the rare collision
            numbers = sorted(set(numbers) | {((base + j) % 38) + 1})
            j += 1
        history.append(
            {
                "draw": str(100000 + i),
                "date": f"2026-01-{(i % 28) + 1:02d}",
                "numbers": numbers[:6],
                "special": (i % SPECIAL_MAX) + 1,  # cycles 1..8
            }
        )
    return history


class TestSecondZonePredict:
    def test_returns_non_null_int_in_range_for_sufficient_history(self):
        value = second_zone_predict(_make_history(MIN_HISTORY + 120))
        assert value is not None
        assert isinstance(value, int)
        assert SPECIAL_MIN <= value <= SPECIAL_MAX

    def test_deterministic_same_history_same_value(self):
        assert second_zone_predict(_make_history(200)) == second_zone_predict(
            _make_history(200)
        )

    def test_exactly_min_history_is_sufficient(self):
        value = second_zone_predict(_make_history(MIN_HISTORY))
        assert SPECIAL_MIN <= value <= SPECIAL_MAX

    @pytest.mark.parametrize("n", [0, 1, MIN_HISTORY - 1])
    def test_raises_on_insufficient_history(self, n):
        with pytest.raises(InsufficientHistoryError):
            second_zone_predict(_make_history(n))

    def test_raises_on_non_list(self):
        with pytest.raises(InsufficientHistoryError):
            second_zone_predict(None)  # type: ignore[arg-type]

    def test_falls_back_when_fused_model_raises(self, monkeypatch):
        """If the fused model cannot run, degrade to frequency — never NULL."""
        import lottery_api.models.special_predictor as sp_mod

        class _Boom:
            def __init__(self, *a, **k):
                raise RuntimeError("forced failure for test")

        monkeypatch.setattr(sp_mod, "PowerLottoSpecialPredictor", _Boom)
        value = second_zone_predict(_make_history(120))
        assert value is not None
        assert SPECIAL_MIN <= value <= SPECIAL_MAX

    def test_frequency_fallback_direct_in_range(self):
        value = _frequency_fallback(_make_history(60))
        assert SPECIAL_MIN <= value <= SPECIAL_MAX

    def test_frequency_fallback_empty_uses_fixed_prior(self):
        # No usable specials → fixed modal prior (2), never 0/None.
        assert _frequency_fallback([{"special": None}, {"numbers": [1, 2, 3]}]) == 2


class TestNullGuard:
    def _row(self, **over) -> dict:
        row = {"lottery_type": "POWER_LOTTO", "dry_run": 0, "predicted_special": 3}
        row.update(over)
        return row

    def test_passes_for_valid_production_row(self):
        assert assert_power_lotto_predicted_special(self._row(predicted_special=5)) is None

    def test_raises_on_null_predicted_special(self):
        with pytest.raises(ValueError):
            assert_power_lotto_predicted_special(self._row(predicted_special=None))

    @pytest.mark.parametrize("bad", [0, 9, -1, 100])
    def test_raises_on_out_of_range(self, bad):
        with pytest.raises(ValueError):
            assert_power_lotto_predicted_special(self._row(predicted_special=bad))

    def test_ignores_non_power_lotto_null(self):
        # DAILY_539 / BIG_LOTTO legitimately carry a NULL second zone.
        for lt in ("DAILY_539", "BIG_LOTTO"):
            assert (
                assert_power_lotto_predicted_special(
                    {"lottery_type": lt, "dry_run": 0, "predicted_special": None}
                )
                is None
            )

    def test_ignores_dry_run_rows(self):
        assert (
            assert_power_lotto_predicted_special(
                {"lottery_type": "POWER_LOTTO", "dry_run": 1, "predicted_special": None}
            )
            is None
        )


class TestForwardWiringPreventsNull:
    """End-to-end: the wiring pattern the fix mandates prevents the regression."""

    def test_rowbuilder_using_helper_is_never_null(self):
        history = _make_history(150)
        # Representative future POWER_LOTTO row-builder: obtains the second zone
        # from the canonical helper instead of hardcoding None (the Gen-B bug).
        row = {
            "strategy_id": "example_future_power_multibet",
            "lottery_type": "POWER_LOTTO",
            "target_draw": "115000053",
            "predicted_numbers": [1, 2, 3, 4, 5, 6],
            "predicted_special": second_zone_predict(history),  # <-- the wiring
            "dry_run": 0,
        }
        assert row["predicted_special"] is not None
        assert SPECIAL_MIN <= row["predicted_special"] <= SPECIAL_MAX
        # The guard passes for the wired row...
        assert assert_power_lotto_predicted_special(row) is None

    def test_old_generation_b_none_literal_now_fails_guard(self):
        # The exact Generation-B literal ("predicted_special": None) is now
        # caught by the guard instead of being silently persisted.
        with pytest.raises(ValueError):
            assert_power_lotto_predicted_special(
                {"lottery_type": "POWER_LOTTO", "dry_run": 0, "predicted_special": None}
            )


def _native_power_bets(strategy_id: str, history: list) -> list:
    """Call the descriptor's native generator without its DB/CLI entrypoint."""
    if strategy_id == "power_precision_3bet":
        from tools.predict_power_precision_3bet import generate_power_precision_3bet

        return generate_power_precision_3bet(history)
    if strategy_id == "power_orthogonal_5bet":
        from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet

        return generate_orthogonal_5bet(history)
    if strategy_id == "fourier_rhythm_3bet":
        from tools.power_fourier_rhythm import fourier_rhythm_predict

        return fourier_rhythm_predict(history, n_bets=3, window=500)
    raise AssertionError(f"Unhandled Power Lotto strategy: {strategy_id}")


class TestReplayAdapterPowerSecondZone:
    @pytest.mark.parametrize("strategy_id", [case[0] for case in POWER_DESCRIPTOR_CASES])
    def test_three_online_descriptors_forward_canonical_helper(
        self,
        monkeypatch,
        strategy_id,
    ):
        history = _make_history(120)
        expected_special = second_zone_predict(history)
        helper_calls = []

        def helper_spy(observed_history):
            helper_calls.append(observed_history)
            return second_zone_predict(observed_history)

        monkeypatch.setattr(
            replay_registry.power_lotto_second_zone,
            "second_zone_predict",
            helper_spy,
        )

        adapter = get_adapter(strategy_id)
        first_numbers, first_special = adapter.get_one_bet(history, "POWER_LOTTO")
        repeat_numbers, repeat_special = adapter.get_one_bet(history, "POWER_LOTTO")

        assert helper_calls == [history, history]
        assert first_special == expected_special == repeat_special
        assert isinstance(first_special, int)
        assert SPECIAL_MIN <= first_special <= SPECIAL_MAX
        assert first_numbers == repeat_numbers == sorted(first_numbers)
        assert len(first_numbers) == 6
        assert len(set(first_numbers)) == 6
        assert all(1 <= number <= 38 for number in first_numbers)

    @pytest.mark.parametrize("strategy_id", [case[0] for case in POWER_DESCRIPTOR_CASES])
    def test_helper_fail_closed_exception_is_not_replaced_with_none(
        self, monkeypatch, strategy_id
    ):
        history = _make_history(120)

        def fail_closed(_history):
            raise InsufficientHistoryError("canonical helper rejected history")

        monkeypatch.setattr(
            replay_registry.power_lotto_second_zone,
            "second_zone_predict",
            fail_closed,
        )

        with pytest.raises(InsufficientHistoryError, match="canonical helper rejected"):
            get_adapter(strategy_id).get_one_bet(history, "POWER_LOTTO")

    @pytest.mark.parametrize("strategy_id", [case[0] for case in POWER_DESCRIPTOR_CASES])
    def test_adapter_short_history_remains_fail_closed(self, strategy_id):
        with pytest.raises(InsufficientHistory):
            get_adapter(strategy_id).get_one_bet(
                _make_history(MIN_HISTORY - 1), "POWER_LOTTO"
            )


class TestReplayAdapterNonPowerRegression:
    @pytest.mark.parametrize(
        ("strategy_id", "lottery_type", "pick", "pool"),
        (
            ("biglotto_triple_strike", "BIG_LOTTO", 6, 49),
            ("daily539_f4cold", "DAILY_539", 5, 39),
        ),
    )
    def test_non_power_special_and_main_numbers_are_unchanged(
        self, monkeypatch, strategy_id, lottery_type, pick, pool
    ):
        history = _make_history(120)
        adapter = get_adapter(strategy_id)
        expected_numbers = sorted(adapter._call_strategy(history, lottery_type))

        def unexpected_power_helper(_history):
            raise AssertionError("Power Lotto helper called for non-Power adapter")

        monkeypatch.setattr(
            replay_registry.power_lotto_second_zone,
            "second_zone_predict",
            unexpected_power_helper,
        )

        numbers, special = adapter.get_one_bet(history, lottery_type)

        assert numbers == expected_numbers
        assert len(numbers) == pick
        assert len(set(numbers)) == pick
        assert all(1 <= number <= pool for number in numbers)
        assert special is None


class TestRegistryMetadataInvariance:
    @pytest.mark.parametrize(
        ("strategy_id", "display_name", "version", "native_bet_count"),
        POWER_DESCRIPTOR_CASES,
    )
    def test_power_descriptor_metadata_and_native_bet_count_are_unchanged(
        self, strategy_id, display_name, version, native_bet_count
    ):
        adapter = get_adapter(strategy_id)
        assert adapter.meta.strategy_id == strategy_id
        assert adapter.meta.strategy_name == display_name
        assert adapter.meta.strategy_version == version
        assert adapter.meta.lifecycle_status == "ONLINE"
        assert adapter.meta.supported_lottery_types == ["POWER_LOTTO"]

        native_bets = _native_power_bets(strategy_id, _make_history(120))
        assert len(native_bets) == native_bet_count
