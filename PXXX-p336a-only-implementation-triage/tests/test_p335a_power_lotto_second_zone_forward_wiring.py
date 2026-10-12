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
