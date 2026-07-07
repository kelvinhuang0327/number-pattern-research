"""
test_p336a_power_lotto_forward_row_generation_path.py
=====================================================
P336A — tests for the ONE forward POWER_LOTTO replay-row generation path
(``lottery_api.models.power_lotto_forward_replay_row``).

Proves the wired path:
  - produces a row with a NON-NULL, in-range ``predicted_special`` for
    sufficient history (sourced from the P335A helper), and
  - FAILS FAST (raises ``InsufficientHistoryError``) for insufficient history —
    it never silently defaults or returns a NULL-second-zone row, and
  - runs the P335A NULL guard at the output boundary, and
  - writes NO database.

Pure/isolated: deterministic synthetic in-memory history only. No DB
read/write, no network, no backfill, no prediction claim, no recommended
numbers, no betting advice.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.power_lotto_forward_replay_row import (  # noqa: E402
    FIRST_ZONE_PICK,
    FIRST_ZONE_POOL,
    SPECIAL_MAX,
    SPECIAL_MIN,
    InsufficientHistoryError,
    build_power_lotto_forward_replay_row,
)
from lottery_api.models.power_lotto_second_zone import (  # noqa: E402
    MIN_HISTORY,
    assert_power_lotto_predicted_special,
)


def _make_history(n: int) -> list:
    """Deterministic synthetic POWER_LOTTO draw history (no RNG).

    Same shape/pattern as the P335A helper suite: 6 distinct mains in [1,38],
    one special in [1,8], a draw id and date — a fixed function of the index, so
    results are fully reproducible run-to-run. Oldest-first (history[-1] newest).
    """
    history = []
    for i in range(n):
        base = (i * 7) % 33 + 1
        numbers = sorted({((base + k * 5 - 1) % FIRST_ZONE_POOL) + 1 for k in range(FIRST_ZONE_PICK)})
        j = 1
        while len(numbers) < FIRST_ZONE_PICK:  # deterministic fill on collision
            numbers = sorted(set(numbers) | {((base + j) % FIRST_ZONE_POOL) + 1})
            j += 1
        history.append(
            {
                "draw": str(100000 + i),
                "date": f"2026-01-{(i % 28) + 1:02d}",
                "numbers": numbers[:FIRST_ZONE_PICK],
                "special": (i % SPECIAL_MAX) + 1,  # cycles 1..8
            }
        )
    return history


# A fixed, valid first-zone bet used by the pure tests (no dependency on any
# first-zone predictor). The complete-path test below feeds a real one instead.
_FIXED_NUMBERS = [3, 11, 19, 25, 31, 38]


def _build(n_history: int = 150, **over):
    kwargs = dict(
        strategy_id="example_future_power_multibet",
        target_draw_id="115000053",
        history=_make_history(n_history),
        predicted_numbers=list(_FIXED_NUMBERS),
        strategy_name="威力彩 forward example",
        strategy_version="v0.1-p336a",
        target_draw_date="2026-07-04",
    )
    kwargs.update(over)
    return build_power_lotto_forward_replay_row(**kwargs)


class TestSufficientHistory:
    def test_predicted_special_non_null_in_range(self):
        row = _build(MIN_HISTORY + 120)
        assert row["predicted_special"] is not None
        assert isinstance(row["predicted_special"], int)
        assert SPECIAL_MIN <= row["predicted_special"] <= SPECIAL_MAX

    def test_exactly_min_history_is_sufficient(self):
        row = _build(MIN_HISTORY)
        assert row["predicted_special"] is not None
        assert SPECIAL_MIN <= row["predicted_special"] <= SPECIAL_MAX

    def test_prediction_fields_are_deterministic(self):
        a = _build(200)
        b = _build(200)
        assert a["predicted_special"] == b["predicted_special"]
        assert a["predicted_numbers"] == b["predicted_numbers"]

    def test_row_passes_the_null_guard(self):
        row = _build(150)
        # The builder already guards; re-running the guard must also pass.
        assert assert_power_lotto_predicted_special(row) is None

    def test_first_zone_is_sorted_distinct_in_range(self):
        row = _build(150)
        nums = row["predicted_numbers"]
        assert nums == sorted(nums)
        assert len(set(nums)) == FIRST_ZONE_PICK
        assert all(1 <= x <= FIRST_ZONE_POOL for x in nums)

    def test_forward_semantics_actuals_unknown_status_predicted(self):
        row = _build(150)
        assert row["replay_status"] == "PREDICTED"
        assert row["actual_numbers"] is None
        assert row["actual_special"] is None
        assert row["hit_numbers"] is None
        assert row["hit_count"] is None
        assert row["special_hit"] is None

    def test_row_has_canonical_keys(self):
        row = _build(150)
        for key in (
            "strategy_id", "lottery_type", "target_draw", "predicted_numbers",
            "predicted_special", "prediction_cutoff_date", "history_cutoff_draw",
            "replay_status", "dry_run",
        ):
            assert key in row, f"missing canonical key: {key}"
        assert row["lottery_type"] == "POWER_LOTTO"
        assert row["target_draw"] == "115000053"
        assert row["history_cutoff_draw"] == str(100000 + 150 - 1)


class TestInsufficientHistoryFailsFast:
    @pytest.mark.parametrize("n", [0, 1, MIN_HISTORY - 1])
    def test_raises_and_returns_no_row(self, n):
        # Fail-fast: the builder must RAISE rather than silently default to a
        # NULL/placeholder second zone. No row object is produced.
        with pytest.raises(InsufficientHistoryError):
            _build(n)

    def test_non_list_history_raises(self):
        with pytest.raises(InsufficientHistoryError):
            build_power_lotto_forward_replay_row(
                strategy_id="s",
                target_draw_id="1",
                history=None,  # type: ignore[arg-type]
                predicted_numbers=list(_FIXED_NUMBERS),
            )


class TestFirstZoneValidation:
    @pytest.mark.parametrize(
        "bad",
        [
            [1, 2, 3, 4, 5],            # too few
            [1, 2, 3, 4, 5, 6, 7],      # too many
            [1, 2, 3, 4, 5, 5],         # duplicate
            [0, 2, 3, 4, 5, 6],         # out of range (low)
            [1, 2, 3, 4, 5, 39],        # out of range (high)
        ],
    )
    def test_rejects_bad_first_zone(self, bad):
        with pytest.raises(ValueError):
            _build(150, predicted_numbers=bad)

    def test_rejects_non_list_first_zone(self):
        with pytest.raises(ValueError):
            _build(150, predicted_numbers="123456")  # type: ignore[arg-type]


class TestDryRunFlag:
    def test_dry_run_flag_recorded_as_int(self):
        assert _build(150, dry_run=False)["dry_run"] == 0
        assert _build(150, dry_run=True)["dry_run"] == 1

    def test_dry_run_row_still_has_real_second_zone(self):
        # Even when marked dry_run (guard would no-op), the builder still sources
        # a real, non-NULL second zone — it never fabricates NULL.
        row = _build(150, dry_run=True)
        assert row["predicted_special"] is not None
        assert SPECIAL_MIN <= row["predicted_special"] <= SPECIAL_MAX


class TestNoDbSideEffect:
    def test_build_writes_no_database(self, tmp_path, monkeypatch):
        # Run with CWD in an empty tmp dir; the builder must create no .db file.
        monkeypatch.chdir(tmp_path)
        _build(150)
        assert list(tmp_path.glob("**/*.db")) == []
        assert list(tmp_path.glob("**/*.sqlite")) == []


class TestCompletePathReusesExistingPredictor:
    """End-to-end: the complete live path = existing first-zone predictor +
    this builder + P335A helper/guard — produces a non-NULL second zone."""

    def test_wires_real_p47_first_zone_predictor(self):
        from lottery_api.models.p47_wave4_powerlotto_adapters import (
            predict_midfreq_fourier_mk_3bet_bet1,
        )

        history = _make_history(150)
        first_zone = predict_midfreq_fourier_mk_3bet_bet1(history)  # existing code
        row = build_power_lotto_forward_replay_row(
            strategy_id="midfreq_fourier_mk_3bet",
            target_draw_id="115000053",
            history=history,
            predicted_numbers=first_zone,
            strategy_name="威力彩 MidFreq+Fourier+Markov 3注",
            strategy_version="v0.1-p47",
        )
        assert row["predicted_special"] is not None
        assert SPECIAL_MIN <= row["predicted_special"] <= SPECIAL_MAX
        assert assert_power_lotto_predicted_special(row) is None
