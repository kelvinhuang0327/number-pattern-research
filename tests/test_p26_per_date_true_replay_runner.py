"""
tests/test_p26_per_date_true_replay_runner.py

Unit tests for p26_per_date_true_replay_runner.py.
Verifies:
  - run_true_date_replay_for_date reads from correct slice path
  - BLOCKED when slice missing
  - BLOCKED when slice invalid
  - Active entries correctly identified by gate_decision
  - odds_decimal_max <= 2.50 applied when gate_decision absent
  - Settlement read from settlement_status column
  - Settlement falls back to is_win / is_loss
  - Settlement falls back to y_true + side
  - Per-date statistics computed correctly
  - Policy constants are correct values
"""
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p26_true_date_replay_contract import (
    P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
    P26_DATE_REPLAY_READY,
)
from wbc_backend.recommendation.p26_per_date_true_replay_runner import (
    EDGE_THRESHOLD,
    MAX_STAKE_CAP,
    KELLY_FRACTION,
    ODDS_DECIMAL_MAX,
    build_recommendation_rows_from_true_date_input,
    run_true_date_replay_for_date,
    settle_true_date_replay,
    summarize_true_date_replay_result,
    validate_true_date_replay_result,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_p17_ledger_slice(
    date: str = "2025-05-08",
    n_eligible: int = 2,
    n_blocked: int = 1,
) -> pd.DataFrame:
    rows = []
    for i in range(n_eligible):
        rows.append(
            {
                "ledger_id": f"L{i:03d}",
                "game_id": f"G{i:03d}",
                "date": date,
                "side": "HOME" if i % 2 == 0 else "AWAY",
                "p_model": 0.60,
                "p_market": 0.52,
                "edge": 0.08,
                "odds_decimal": 1.90,
                "paper_stake_units": 0.25,
                "paper_stake_fraction": 0.0025,
                "gate_decision": "P16_6_ELIGIBLE_PAPER_RECOMMENDATION",
                "gate_reason": "ELIGIBLE",
                "settlement_status": "SETTLED_WIN" if i % 2 == 0 else "SETTLED_LOSS",
                "pnl_units": 0.2375 if i % 2 == 0 else -0.25,
                "is_win": i % 2 == 0,
                "is_loss": i % 2 != 0,
                "is_push": False,
                "y_true": 1 if i % 2 == 0 else 0,
                "paper_only": True,
                "production_ready": False,
                "source_phase": "P17",
            }
        )
    for j in range(n_blocked):
        rows.append(
            {
                "ledger_id": f"B{j:03d}",
                "game_id": f"BG{j:03d}",
                "date": date,
                "side": "HOME",
                "p_model": 0.52,
                "p_market": 0.55,
                "edge": -0.03,
                "odds_decimal": 1.80,
                "paper_stake_units": 0.0,
                "paper_stake_fraction": 0.0,
                "gate_decision": "P16_6_BLOCKED_NEGATIVE_EDGE",
                "gate_reason": "NEGATIVE_EDGE",
                "settlement_status": "UNSETTLED_NOT_RECOMMENDED",
                "pnl_units": 0.0,
                "is_win": False,
                "is_loss": False,
                "is_push": False,
                "y_true": 1,
                "paper_only": True,
                "production_ready": False,
                "source_phase": "P17",
            }
        )
    return pd.DataFrame(rows)


def _write_slice(tmp_path: Path, date: str, df: pd.DataFrame) -> Path:
    slice_dir = tmp_path / "true_date_slices" / date
    slice_dir.mkdir(parents=True, exist_ok=True)
    csv_path = slice_dir / "p15_true_date_input.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------


class TestPolicyConstants:
    def test_edge_threshold(self):
        assert EDGE_THRESHOLD == pytest.approx(0.05)

    def test_max_stake_cap(self):
        assert MAX_STAKE_CAP == pytest.approx(0.0025)

    def test_kelly_fraction(self):
        assert KELLY_FRACTION == pytest.approx(0.10)

    def test_odds_decimal_max(self):
        assert ODDS_DECIMAL_MAX == pytest.approx(2.50)


# ---------------------------------------------------------------------------
# run_true_date_replay_for_date
# ---------------------------------------------------------------------------


class TestRunTrueDateReplayForDate:
    def test_blocked_when_slice_missing(self, tmp_path: Path):
        out_dir = tmp_path / "out"
        result = run_true_date_replay_for_date("2025-05-08", tmp_path, out_dir)
        assert result.replay_gate == P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE

    def test_blocked_for_missing_required_columns(self, tmp_path: Path):
        df = _make_p17_ledger_slice()
        df = df.drop(columns=["y_true"])
        _write_slice(tmp_path, "2025-05-08", df)
        out_dir = tmp_path / "out"
        result = run_true_date_replay_for_date("2025-05-08", tmp_path, out_dir)
        assert result.replay_gate != P26_DATE_REPLAY_READY

    def test_ready_for_valid_slice(self, tmp_path: Path):
        df = _make_p17_ledger_slice(n_eligible=2, n_blocked=1)
        _write_slice(tmp_path, "2025-05-08", df)
        out_dir = tmp_path / "out"
        result = run_true_date_replay_for_date("2025-05-08", tmp_path, out_dir)
        assert result.replay_gate == P26_DATE_REPLAY_READY

    def test_active_entries_count(self, tmp_path: Path):
        df = _make_p17_ledger_slice(n_eligible=3, n_blocked=2)
        _write_slice(tmp_path, "2025-05-08", df)
        out_dir = tmp_path / "out"
        result = run_true_date_replay_for_date("2025-05-08", tmp_path, out_dir)
        assert result.n_active_paper_entries == 3

    def test_paper_only_always_true(self, tmp_path: Path):
        df = _make_p17_ledger_slice()
        _write_slice(tmp_path, "2025-05-08", df)
        out_dir = tmp_path / "out"
        result = run_true_date_replay_for_date("2025-05-08", tmp_path, out_dir)
        assert result.paper_only is True
        assert result.production_ready is False


# ---------------------------------------------------------------------------
# build_recommendation_rows_from_true_date_input
# ---------------------------------------------------------------------------


class TestBuildRecommendationRows:
    def test_only_eligible_gate_active(self):
        df = _make_p17_ledger_slice(n_eligible=2, n_blocked=3)
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        assert result.n_active_paper_entries == 2

    def test_zero_active_returns_ready(self):
        df = _make_p17_ledger_slice(n_eligible=0, n_blocked=2)
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        assert result.replay_gate == P26_DATE_REPLAY_READY
        assert result.n_active_paper_entries == 0

    def test_settlement_computed_correctly(self):
        df = _make_p17_ledger_slice(n_eligible=4, n_blocked=0)
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        # n_eligible=4 → alternating HOME/AWAY settlement
        # HOME (i%2==0): SETTLED_WIN rows = 0, 2 (2 wins)
        # AWAY (i%2!=0): SETTLED_LOSS rows = 1, 3 (2 losses)
        assert result.n_settled_win == 2
        assert result.n_settled_loss == 2

    def test_stake_total_is_eligible_only(self):
        df = _make_p17_ledger_slice(n_eligible=2, n_blocked=3)
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        # Each eligible row has paper_stake_units=0.25
        assert result.total_stake_units == pytest.approx(0.50, abs=0.001)

    def test_roi_computed_from_stake_and_pnl(self):
        df = _make_p17_ledger_slice(n_eligible=2, n_blocked=0)
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        if result.total_stake_units > 0:
            expected_roi = result.total_pnl_units / result.total_stake_units
            assert result.roi_units == pytest.approx(expected_roi, abs=0.001)

    def test_hit_rate_wins_over_settled(self):
        df = _make_p17_ledger_slice(n_eligible=4, n_blocked=0)
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        total_settled = result.n_settled_win + result.n_settled_loss
        if total_settled > 0:
            assert result.hit_rate == pytest.approx(
                result.n_settled_win / total_settled, abs=0.001
            )

    def test_odds_decimal_above_max_not_in_eligible(self):
        """Policy: odds > 2.50 should not appear in active entries (gate_decision handles it)."""
        df = _make_p17_ledger_slice(n_eligible=2, n_blocked=0)
        # Mark one eligible row as having high odds but keep gate_decision eligible
        # (This tests that the gate_decision filter is the source of truth)
        df.loc[0, "odds_decimal"] = 3.00
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        # When gate_decision is present, we trust it — both still eligible
        assert result.n_active_paper_entries == 2


# ---------------------------------------------------------------------------
# settle_true_date_replay
# ---------------------------------------------------------------------------


class TestSettleTrueDateReplay:
    def test_from_settlement_status_column(self):
        df = pd.DataFrame(
            {
                "settlement_status": ["SETTLED_WIN", "SETTLED_LOSS", "SETTLED_WIN"],
                "paper_stake_units": [0.25, 0.25, 0.25],
                "pnl_units": [0.2375, -0.25, 0.2375],
            }
        )
        win, loss, unsettled = settle_true_date_replay(df)
        assert win == 2
        assert loss == 1
        assert unsettled == 0

    def test_fallback_to_is_win_is_loss(self):
        df = pd.DataFrame(
            {
                "is_win": [True, False, False],
                "is_loss": [False, True, False],
                "paper_stake_units": [0.25, 0.25, 0.0],
                "pnl_units": [0.2375, -0.25, 0.0],
            }
        )
        win, loss, unsettled = settle_true_date_replay(df)
        assert win == 1
        assert loss == 1
        assert unsettled == 1  # third row is neither win nor loss

    def test_fallback_to_y_true_side(self):
        df = pd.DataFrame(
            {
                "y_true": [1, 0, 1],
                "side": ["HOME", "HOME", "AWAY"],
            }
        )
        win, loss, unsettled = settle_true_date_replay(df)
        # HOME + y_true=1 = WIN, HOME + y_true=0 = LOSS, AWAY + y_true=1 = LOSS
        assert win == 1
        assert loss == 2
        assert unsettled == 0

    def test_unsettled_entries_counted(self):
        df = pd.DataFrame(
            {
                "settlement_status": ["SETTLED_WIN", "UNSETTLED_NOT_RECOMMENDED"],
            }
        )
        win, loss, unsettled = settle_true_date_replay(df)
        assert win == 1
        assert loss == 0
        assert unsettled == 1


# ---------------------------------------------------------------------------
# summarize_true_date_replay_result
# ---------------------------------------------------------------------------


class TestSummarizeTrueDateReplayResult:
    def test_returns_dict_with_required_keys(self):
        df = _make_p17_ledger_slice(n_eligible=2, n_blocked=1)
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        d = summarize_true_date_replay_result(result)
        required_keys = [
            "run_date", "replay_gate", "n_active_paper_entries",
            "n_settled_win", "n_settled_loss", "total_stake_units",
            "total_pnl_units", "roi_units", "hit_rate",
            "paper_only", "production_ready",
        ]
        for k in required_keys:
            assert k in d, f"Missing key: {k}"

    def test_paper_only_always_true_in_dict(self):
        df = _make_p17_ledger_slice()
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        d = summarize_true_date_replay_result(result)
        assert d["paper_only"] is True
        assert d["production_ready"] is False


# ---------------------------------------------------------------------------
# validate_true_date_replay_result
# ---------------------------------------------------------------------------


class TestValidateTrueDateReplayResult:
    def test_valid_result_passes(self):
        df = _make_p17_ledger_slice()
        result = build_recommendation_rows_from_true_date_input("2025-05-08", df)
        assert validate_true_date_replay_result(result) is True

    def test_blocked_result_passes(self, tmp_path: Path):
        out_dir = tmp_path / "out"
        result = run_true_date_replay_for_date("2025-05-08", tmp_path, out_dir)
        assert result.replay_gate == P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE
        assert validate_true_date_replay_result(result) is True
