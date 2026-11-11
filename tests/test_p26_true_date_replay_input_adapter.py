"""
tests/test_p26_true_date_replay_input_adapter.py

Unit tests for p26_true_date_replay_input_adapter.py.
Verifies:
  - load_true_date_slice returns None for missing files
  - validate_true_date_slice_for_replay blocks empty slices
  - validate_true_date_slice_for_replay blocks missing required columns
  - validate_true_date_slice_for_replay blocks wrong-date rows
  - validate_true_date_slice_for_replay returns READY for valid slices
  - convert_true_date_slice_to_replay_input renames 'date' -> 'game_date'
  - summarize_replay_input computes correct statistics
  - write_replay_input_for_date creates both output files
"""
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p26_true_date_replay_contract import (
    P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
    P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
    P26_DATE_REPLAY_READY,
)
from wbc_backend.recommendation.p26_true_date_replay_input_adapter import (
    convert_true_date_slice_to_replay_input,
    load_true_date_slice,
    summarize_replay_input,
    validate_true_date_slice_for_replay,
    write_replay_input_for_date,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_valid_slice(date: str = "2025-05-08") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ledger_id": ["L001", "L002"],
            "game_id": ["G001", "G002"],
            "date": [date, date],
            "side": ["HOME", "AWAY"],
            "p_model": [0.60, 0.55],
            "p_market": [0.52, 0.48],
            "edge": [0.08, 0.07],
            "odds_decimal": [1.90, 2.10],
            "paper_stake_units": [0.25, 0.25],
            "gate_decision": [
                "P16_6_ELIGIBLE_PAPER_RECOMMENDATION",
                "P16_6_ELIGIBLE_PAPER_RECOMMENDATION",
            ],
            "settlement_status": ["SETTLED_WIN", "SETTLED_LOSS"],
            "pnl_units": [0.2375, -0.25],
            "is_win": [True, False],
            "is_loss": [False, True],
            "is_push": [False, False],
            "y_true": [1, 0],
            "paper_only": [True, True],
            "production_ready": [False, False],
        }
    )


# ---------------------------------------------------------------------------
# load_true_date_slice
# ---------------------------------------------------------------------------


class TestLoadTrueDateSlice:
    def test_missing_file_returns_none(self):
        result = load_true_date_slice(Path("/nonexistent/path.csv"))
        assert result is None

    def test_valid_csv_loads(self, tmp_path: Path):
        df = _make_valid_slice()
        csv_path = tmp_path / "p15_true_date_input.csv"
        df.to_csv(csv_path, index=False)
        result = load_true_date_slice(csv_path)
        assert result is not None
        assert len(result) == 2


# ---------------------------------------------------------------------------
# validate_true_date_slice_for_replay
# ---------------------------------------------------------------------------


class TestValidateTrueDateSliceForReplay:
    def test_none_returns_blocked_no_slice(self):
        gate, reason = validate_true_date_slice_for_replay(None, "2025-05-08")
        assert gate == P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE
        assert "2025-05-08" in reason

    def test_empty_df_returns_blocked_no_slice(self):
        gate, reason = validate_true_date_slice_for_replay(
            pd.DataFrame(), "2025-05-08"
        )
        assert gate == P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE

    def test_missing_required_columns_blocked(self):
        df = _make_valid_slice()
        df = df.drop(columns=["game_id"])
        gate, reason = validate_true_date_slice_for_replay(df, "2025-05-08")
        assert gate == P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE
        assert "game_id" in reason

    def test_missing_date_column_blocked(self):
        df = _make_valid_slice()
        df = df.drop(columns=["date"])
        gate, reason = validate_true_date_slice_for_replay(df, "2025-05-08")
        assert gate == P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE
        assert "date" in reason.lower() or "game_date" in reason.lower()

    def test_missing_pred_column_blocked(self):
        df = _make_valid_slice()
        df = df.drop(columns=["p_model"])
        gate, reason = validate_true_date_slice_for_replay(df, "2025-05-08")
        assert gate == P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE
        assert "prediction" in reason.lower() or "p_model" in reason.lower() or "p_oof" in reason.lower()

    def test_wrong_date_rows_blocked(self):
        df = _make_valid_slice("2025-05-09")  # Wrong date
        gate, reason = validate_true_date_slice_for_replay(df, "2025-05-08")
        assert gate == P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE
        assert "2025-05-09" in reason

    def test_valid_slice_returns_ready(self):
        df = _make_valid_slice("2025-05-08")
        gate, reason = validate_true_date_slice_for_replay(df, "2025-05-08")
        assert gate == P26_DATE_REPLAY_READY
        assert reason == ""

    def test_game_date_column_accepted(self):
        df = _make_valid_slice()
        df = df.rename(columns={"date": "game_date"})
        gate, reason = validate_true_date_slice_for_replay(df, "2025-05-08")
        assert gate == P26_DATE_REPLAY_READY

    def test_p_oof_column_accepted_as_pred(self):
        df = _make_valid_slice()
        df = df.rename(columns={"p_model": "p_oof"})
        gate, reason = validate_true_date_slice_for_replay(df, "2025-05-08")
        assert gate == P26_DATE_REPLAY_READY


# ---------------------------------------------------------------------------
# convert_true_date_slice_to_replay_input
# ---------------------------------------------------------------------------


class TestConvertTrueDateSliceToReplayInput:
    def test_date_renamed_to_game_date(self):
        df = _make_valid_slice()
        assert "date" in df.columns
        assert "game_date" not in df.columns
        result = convert_true_date_slice_to_replay_input(df)
        assert "game_date" in result.columns
        assert "date" not in result.columns

    def test_game_date_unchanged_if_already_present(self):
        df = _make_valid_slice()
        df = df.rename(columns={"date": "game_date"})
        result = convert_true_date_slice_to_replay_input(df)
        assert "game_date" in result.columns

    def test_rows_unchanged(self):
        df = _make_valid_slice()
        result = convert_true_date_slice_to_replay_input(df)
        assert len(result) == len(df)

    def test_does_not_modify_source(self):
        df = _make_valid_slice()
        original_cols = list(df.columns)
        convert_true_date_slice_to_replay_input(df)
        assert list(df.columns) == original_cols


# ---------------------------------------------------------------------------
# summarize_replay_input
# ---------------------------------------------------------------------------


class TestSummarizeReplayInput:
    def test_empty_returns_zero_stats(self):
        s = summarize_replay_input(None, "2025-05-08")
        assert s["n_rows"] == 0
        assert s["n_active_entries"] == 0
        assert s["paper_only"] is True
        assert s["production_ready"] is False

    def test_valid_df_counts_active_entries(self):
        df = _make_valid_slice()
        s = summarize_replay_input(df, "2025-05-08")
        assert s["n_rows"] == 2
        assert s["n_active_entries"] == 2  # Both have eligible gate
        assert s["n_blocked_entries"] == 0

    def test_blocked_entries_counted(self):
        df = _make_valid_slice()
        df.loc[1, "gate_decision"] = "P16_6_BLOCKED_LOW_EDGE"
        s = summarize_replay_input(df, "2025-05-08")
        assert s["n_active_entries"] == 1
        assert s["n_blocked_entries"] == 1

    def test_total_stake_only_active(self):
        df = _make_valid_slice()
        df.loc[1, "gate_decision"] = "P16_6_BLOCKED_LOW_EDGE"
        s = summarize_replay_input(df, "2025-05-08")
        # Only first row is active (stake=0.25)
        assert s["total_stake_units"] == pytest.approx(0.25, abs=0.001)

    def test_content_hash_is_deterministic(self):
        df = _make_valid_slice()
        h1 = summarize_replay_input(df, "2025-05-08")["content_hash"]
        h2 = summarize_replay_input(df, "2025-05-08")["content_hash"]
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_paper_only_always_true(self):
        df = _make_valid_slice()
        s = summarize_replay_input(df, "2025-05-08")
        assert s["paper_only"] is True
        assert s["production_ready"] is False


# ---------------------------------------------------------------------------
# write_replay_input_for_date
# ---------------------------------------------------------------------------


class TestWriteReplayInputForDate:
    def test_writes_csv_and_summary(self, tmp_path: Path):
        df = _make_valid_slice()
        csv_path, summary_path = write_replay_input_for_date("2025-05-08", df, tmp_path)
        assert csv_path.exists()
        assert summary_path.exists()

    def test_csv_has_correct_rows(self, tmp_path: Path):
        df = _make_valid_slice()
        csv_path, _ = write_replay_input_for_date("2025-05-08", df, tmp_path)
        loaded = pd.read_csv(csv_path)
        assert len(loaded) == 2

    def test_summary_is_valid_json(self, tmp_path: Path):
        df = _make_valid_slice()
        _, summary_path = write_replay_input_for_date("2025-05-08", df, tmp_path)
        data = json.loads(summary_path.read_text())
        assert "n_rows" in data
        assert data["paper_only"] is True

    def test_output_in_correct_subdirectory(self, tmp_path: Path):
        df = _make_valid_slice()
        csv_path, _ = write_replay_input_for_date("2025-05-08", df, tmp_path)
        assert "2025-05-08" in str(csv_path)
        assert "p26_true_date_replay_input" in str(csv_path)
