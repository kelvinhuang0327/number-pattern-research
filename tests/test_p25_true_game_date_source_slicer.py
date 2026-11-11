"""
tests/test_p25_true_game_date_source_slicer.py

Tests for the P25 true game_date source slicer.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p25_true_date_source_contract import (
    TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH,
    TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID,
    TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS,
    TRUE_DATE_SLICE_EMPTY,
    TRUE_DATE_SLICE_READY,
)
from wbc_backend.recommendation.p25_true_game_date_source_slicer import (
    _is_excluded_path,
    discover_true_date_source_files,
    identify_game_date_column,
    identify_required_columns,
    slice_source_by_game_date,
    summarize_true_date_slice,
    validate_true_date_slice,
    write_true_date_slice,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_full_csv(tmp_path: Path, filename: str, rows: list[dict]) -> Path:
    """Write a CSV file to tmp_path and return its path."""
    df = pd.DataFrame(rows)
    p = tmp_path / filename
    df.to_csv(p, index=False)
    return p


def _full_row(game_id: str = "G001", game_date: str = "2025-05-08") -> dict:
    """Return a row with all required columns."""
    return {
        "game_id": game_id,
        "game_date": game_date,
        "y_true": 1,
        "p_oof": 0.62,
        "p_market": 0.55,
        "odds_decimal_home": 1.85,
        "odds_decimal_away": 2.10,
        "edge": 0.07,
    }


# ---------------------------------------------------------------------------
# identify_game_date_column
# ---------------------------------------------------------------------------


def test_identify_game_date_column_prefers_game_date():
    df = pd.DataFrame({"game_date": ["2025-05-08"], "date": ["2025-05-08"], "y_true": [1]})
    assert identify_game_date_column(df) == "game_date"


def test_identify_game_date_column_falls_back_to_date():
    df = pd.DataFrame({"date": ["2025-05-08"], "y_true": [1]})
    assert identify_game_date_column(df) == "date"


def test_identify_game_date_column_returns_none_if_missing():
    df = pd.DataFrame({"y_true": [1], "game_id": ["G1"]})
    assert identify_game_date_column(df) is None


# ---------------------------------------------------------------------------
# identify_required_columns
# ---------------------------------------------------------------------------


def test_identify_required_columns_all_present():
    df = pd.DataFrame([_full_row()])
    result = identify_required_columns(df)
    assert all(result.values()), f"Expected all True, got: {result}"


def test_identify_required_columns_missing_y_true():
    row = _full_row()
    row.pop("y_true")
    df = pd.DataFrame([row])
    result = identify_required_columns(df)
    assert result["y_true"] is False


def test_identify_required_columns_missing_p_oof():
    row = {k: v for k, v in _full_row().items() if k != "p_oof"}
    df = pd.DataFrame([row])
    result = identify_required_columns(df)
    assert result["p_model_or_p_oof"] is False


def test_identify_required_columns_missing_game_id():
    row = {k: v for k, v in _full_row().items() if k != "game_id"}
    df = pd.DataFrame([row])
    result = identify_required_columns(df)
    assert result["game_id"] is False


def test_identify_required_columns_accepts_odds_decimal_home():
    """odds_decimal_home should satisfy the odds requirement."""
    df = pd.DataFrame([_full_row()])  # has odds_decimal_home
    result = identify_required_columns(df)
    assert result["odds_column"] is True


# ---------------------------------------------------------------------------
# slice_source_by_game_date — only returns rows where game_date == target_date
# ---------------------------------------------------------------------------


def test_slice_returns_only_target_date_rows(tmp_path):
    rows = [
        _full_row("G001", "2025-05-08"),
        _full_row("G002", "2025-05-08"),
        _full_row("G003", "2025-05-09"),
        _full_row("G004", "2025-05-10"),
    ]
    src = _make_full_csv(tmp_path, "source.csv", rows)
    sliced = slice_source_by_game_date(src, "2025-05-08")
    assert sliced is not None
    assert len(sliced) == 2
    assert set(sliced["game_id"].tolist()) == {"G001", "G002"}


def test_slice_returns_empty_when_no_rows_for_date(tmp_path):
    rows = [_full_row("G001", "2025-05-08")]
    src = _make_full_csv(tmp_path, "source.csv", rows)
    sliced = slice_source_by_game_date(src, "2026-05-01")
    assert sliced is not None
    assert len(sliced) == 0


def test_slice_does_not_relabel_run_date_as_game_date(tmp_path):
    """If run_date != game_date, the slice should NOT relabel the rows."""
    rows = [
        {
            "game_id": "G001",
            "game_date": "2025-05-08",
            "run_date": "2026-05-01",  # intentional mismatch (P23 style)
            "y_true": 1,
            "p_oof": 0.6,
            "p_market": 0.5,
            "odds_decimal_home": 1.9,
        }
    ]
    src = _make_full_csv(tmp_path, "source.csv", rows)

    # Requesting 2026-05-01 (run_date) should return empty — game_date is 2025-05-08
    sliced_2026 = slice_source_by_game_date(src, "2026-05-01")
    assert sliced_2026 is not None
    assert len(sliced_2026) == 0, "Should not return rows just because run_date matches"

    # Requesting 2025-05-08 (game_date) should return the row
    sliced_2025 = slice_source_by_game_date(src, "2025-05-08")
    assert sliced_2025 is not None
    assert len(sliced_2025) == 1


def test_slice_returns_none_for_missing_file(tmp_path):
    sliced = slice_source_by_game_date(tmp_path / "nonexistent.csv", "2025-05-08")
    assert sliced is None


def test_slice_returns_none_for_no_date_column(tmp_path):
    df = pd.DataFrame([{"game_id": "G1", "y_true": 1}])
    src = tmp_path / "nodatecol.csv"
    df.to_csv(src, index=False)
    sliced = slice_source_by_game_date(src, "2025-05-08")
    assert sliced is None


# ---------------------------------------------------------------------------
# validate_true_date_slice
# ---------------------------------------------------------------------------


def test_validate_returns_ready_for_valid_slice(tmp_path):
    rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-08")]
    src = _make_full_csv(tmp_path, "src.csv", rows)
    sliced = slice_source_by_game_date(src, "2025-05-08")
    status, reason = validate_true_date_slice(sliced, "2025-05-08")
    assert status == TRUE_DATE_SLICE_READY
    assert reason == ""


def test_validate_returns_empty_for_empty_slice(tmp_path):
    rows = [_full_row("G001", "2025-05-08")]
    src = _make_full_csv(tmp_path, "src.csv", rows)
    sliced = slice_source_by_game_date(src, "2026-05-01")
    status, reason = validate_true_date_slice(sliced, "2026-05-01")
    assert status == TRUE_DATE_SLICE_EMPTY
    assert reason == ""


def test_validate_returns_empty_for_none():
    status, reason = validate_true_date_slice(None, "2025-05-08")
    assert status == TRUE_DATE_SLICE_EMPTY


def test_validate_detects_missing_required_columns(tmp_path):
    """A slice missing p_oof/p_model should be BLOCKED_MISSING_REQUIRED_COLUMNS."""
    rows = [{"game_id": "G1", "game_date": "2025-05-08", "y_true": 1, "p_market": 0.5}]
    src = _make_full_csv(tmp_path, "src.csv", rows)
    sliced = slice_source_by_game_date(src, "2025-05-08")
    status, reason = validate_true_date_slice(sliced, "2025-05-08")
    assert status == TRUE_DATE_SLICE_BLOCKED_MISSING_REQUIRED_COLUMNS
    assert "Missing" in reason


def test_validate_detects_duplicate_game_id(tmp_path):
    rows = [
        _full_row("G001", "2025-05-08"),
        _full_row("G001", "2025-05-08"),  # duplicate!
    ]
    src = _make_full_csv(tmp_path, "src.csv", rows)
    sliced = slice_source_by_game_date(src, "2025-05-08")
    status, reason = validate_true_date_slice(sliced, "2025-05-08")
    assert status == TRUE_DATE_SLICE_BLOCKED_DUPLICATE_GAME_ID
    assert "duplicate" in reason.lower()


def test_validate_detects_date_mismatch(tmp_path):
    """If slice contains rows with wrong game_date, it's a date mismatch."""
    rows = [
        {"game_id": "G1", "game_date": "2025-05-09", "y_true": 1,
         "p_oof": 0.6, "p_market": 0.5, "odds_decimal_home": 1.9},
    ]
    df = pd.DataFrame(rows)
    # Manually tamper: put a row from a different date in a slice for 2025-05-08
    status, reason = validate_true_date_slice(df, "2025-05-08")
    assert status == TRUE_DATE_SLICE_BLOCKED_DATE_MISMATCH


# ---------------------------------------------------------------------------
# write_true_date_slice
# ---------------------------------------------------------------------------


def test_write_true_date_slice_creates_file(tmp_path):
    rows = [_full_row("G001", "2025-05-08")]
    df = pd.DataFrame(rows)
    out_path = write_true_date_slice(df, tmp_path, "2025-05-08")
    assert out_path.exists()
    assert out_path.name == "p15_true_date_input.csv"
    written = pd.read_csv(out_path)
    assert len(written) == 1


def test_write_true_date_slice_path_structure(tmp_path):
    rows = [_full_row("G001", "2025-05-08")]
    df = pd.DataFrame(rows)
    out_path = write_true_date_slice(df, tmp_path, "2025-05-08")
    assert "true_date_slices" in str(out_path)
    assert "2025-05-08" in str(out_path)


# ---------------------------------------------------------------------------
# summarize_true_date_slice
# ---------------------------------------------------------------------------


def test_summarize_returns_zero_counts_for_empty():
    summary = summarize_true_date_slice(None, "2025-05-08")
    assert summary["n_rows"] == 0
    assert summary["n_unique_game_ids"] == 0


def test_summarize_correct_counts():
    rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-08")]
    df = pd.DataFrame(rows)
    summary = summarize_true_date_slice(df, "2025-05-08", "data/source.csv")
    assert summary["n_rows"] == 2
    assert summary["n_unique_game_ids"] == 2
    assert summary["game_date_min"] == "2025-05-08"
    assert summary["game_date_max"] == "2025-05-08"
    assert len(summary["content_hash"]) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# discover_true_date_source_files — excludes P23 materialized paths
# ---------------------------------------------------------------------------


def test_discover_excludes_p23_materialized(tmp_path):
    """Files under p23_historical_replay/p15_materialized/ must be excluded."""
    # Create a legit source
    legit_dir = tmp_path / "legit"
    legit_dir.mkdir()
    legit_csv = legit_dir / "joined.csv"
    rows = [_full_row("G1", "2025-05-08")]
    pd.DataFrame(rows).to_csv(legit_csv, index=False)

    # Create a P23 materialized file (should be excluded)
    mat_dir = tmp_path / "2026-05-01" / "p23_historical_replay" / "p15_materialized"
    mat_dir.mkdir(parents=True)
    mat_csv = mat_dir / "joined_oof_with_odds.csv"
    pd.DataFrame(rows).to_csv(mat_csv, index=False)

    found = discover_true_date_source_files([str(tmp_path)])
    found_strs = [str(f) for f in found]

    assert str(legit_csv) in found_strs, "Legit source should be found"
    assert str(mat_csv) not in found_strs, "P23 materialized should be excluded"


def test_discover_returns_empty_for_no_valid_csv(tmp_path):
    """No CSVs with required columns → empty list."""
    # CSV without game_id/y_true
    p = tmp_path / "bad.csv"
    pd.DataFrame([{"a": 1, "b": 2}]).to_csv(p, index=False)
    found = discover_true_date_source_files([str(tmp_path)])
    assert found == []


def test_is_excluded_path_for_p23():
    p = Path("outputs/predictions/PAPER/2026-05-01/p23_historical_replay/p15_materialized/file.csv")
    assert _is_excluded_path(p) is True


def test_is_excluded_path_for_legit():
    p = Path("outputs/predictions/PAPER/2026-05-12/p15_market_odds_simulation/joined_oof_with_odds.csv")
    assert _is_excluded_path(p) is False
