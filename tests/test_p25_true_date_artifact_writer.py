"""
tests/test_p25_true_date_artifact_writer.py

Tests for the P25 true-date artifact writer.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p25_true_date_source_contract import (
    TRUE_DATE_SLICE_EMPTY,
    TRUE_DATE_SLICE_READY,
    P25TrueDateArtifactManifest,
)
from wbc_backend.recommendation.p25_true_date_artifact_writer import (
    build_artifact_manifest,
    validate_written_artifacts,
    write_slice_manifest,
    write_true_date_artifacts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _full_row(game_id: str = "G001", game_date: str = "2025-05-08") -> dict:
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


def _make_source_csv(tmp_path: Path, name: str, rows: list[dict]) -> Path:
    p = tmp_path / name
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def _make_ready_result(run_date: str, source_path: str, n_rows: int = 4) -> dict:
    return {
        "run_date": run_date,
        "status": TRUE_DATE_SLICE_READY,
        "source_path": source_path,
        "n_rows": n_rows,
        "n_unique_game_ids": n_rows,
        "game_date_min": run_date,
        "game_date_max": run_date,
        "has_required_columns": True,
        "blocker_reason": "",
    }


def _make_empty_result(run_date: str) -> dict:
    return {
        "run_date": run_date,
        "status": TRUE_DATE_SLICE_EMPTY,
        "source_path": "",
        "n_rows": 0,
        "n_unique_game_ids": 0,
        "game_date_min": "",
        "game_date_max": "",
        "has_required_columns": False,
        "blocker_reason": "",
    }


# ---------------------------------------------------------------------------
# write_true_date_artifacts
# ---------------------------------------------------------------------------


def test_writes_only_for_ready_dates(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    rows_08 = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-08")]
    src = _make_source_csv(src_dir, "source.csv", rows_08)

    date_results = [
        _make_ready_result("2025-05-08", str(src), n_rows=2),
        _make_empty_result("2025-05-09"),
    ]

    out_dir = tmp_path / "output"
    manifest = write_true_date_artifacts(date_results, out_dir)

    assert isinstance(manifest, P25TrueDateArtifactManifest)
    assert "2025-05-08" in manifest.written_dates
    assert "2025-05-09" in manifest.skipped_dates
    assert manifest.total_rows_written == 2
    assert manifest.paper_only is True
    assert manifest.production_ready is False


def test_written_csv_has_correct_rows(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-08")]
    src = _make_source_csv(src_dir, "source.csv", rows)

    date_results = [_make_ready_result("2025-05-08", str(src), n_rows=2)]
    out_dir = tmp_path / "output"
    write_true_date_artifacts(date_results, out_dir)

    csv_path = out_dir / "true_date_slices" / "2025-05-08" / "p15_true_date_input.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) == 2


def test_written_summary_json_has_correct_fields(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    rows = [_full_row("G001", "2025-05-08")]
    src = _make_source_csv(src_dir, "source.csv", rows)

    date_results = [_make_ready_result("2025-05-08", str(src), n_rows=1)]
    out_dir = tmp_path / "output"
    write_true_date_artifacts(date_results, out_dir)

    json_path = out_dir / "true_date_slices" / "2025-05-08" / "p15_true_date_input_summary.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["paper_only"] is True
    assert data["production_ready"] is False
    assert data["n_rows"] == 1


def test_no_files_written_for_all_empty(tmp_path):
    date_results = [
        _make_empty_result("2026-05-01"),
        _make_empty_result("2026-05-02"),
    ]
    out_dir = tmp_path / "output"
    manifest = write_true_date_artifacts(date_results, out_dir)

    assert len(manifest.written_dates) == 0
    assert len(manifest.skipped_dates) == 2
    assert manifest.total_rows_written == 0


def test_manifest_is_frozen(tmp_path):
    src = _make_source_csv(tmp_path, "s.csv", [_full_row()])
    date_results = [_make_ready_result("2025-05-08", str(src))]
    out_dir = tmp_path / "out"
    manifest = write_true_date_artifacts(date_results, out_dir)
    with pytest.raises(Exception):
        manifest.total_rows_written = 999  # type: ignore


# ---------------------------------------------------------------------------
# validate_written_artifacts
# ---------------------------------------------------------------------------


def test_validate_returns_true_for_empty_output_dir(tmp_path):
    """If nothing was written, trivially valid."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert validate_written_artifacts(out_dir) is True


def test_validate_returns_true_when_both_files_exist(tmp_path):
    src = _make_source_csv(tmp_path, "s.csv", [_full_row()])
    date_results = [_make_ready_result("2025-05-08", str(src))]
    out_dir = tmp_path / "out"
    write_true_date_artifacts(date_results, out_dir)
    assert validate_written_artifacts(out_dir) is True


def test_validate_returns_false_when_summary_missing(tmp_path):
    """If CSV exists but summary JSON is missing, validation fails."""
    slices_dir = tmp_path / "true_date_slices" / "2025-05-08"
    slices_dir.mkdir(parents=True)
    # Write CSV but not JSON
    (slices_dir / "p15_true_date_input.csv").write_text("game_id\nG1")
    assert validate_written_artifacts(tmp_path) is False


# ---------------------------------------------------------------------------
# write_slice_manifest
# ---------------------------------------------------------------------------


def test_write_slice_manifest_creates_json(tmp_path):
    summary = {"target_date": "2025-05-08", "n_rows": 4, "paper_only": True, "production_ready": False}
    out_dir = tmp_path / "out"
    path = write_slice_manifest(summary, out_dir, "2025-05-08")
    assert path.exists()
    assert path.name == "p15_true_date_input_summary.json"
    data = json.loads(path.read_text())
    assert data["paper_only"] is True


# ---------------------------------------------------------------------------
# build_artifact_manifest (dry-run, no writes)
# ---------------------------------------------------------------------------


def test_build_manifest_correct_counts(tmp_path):
    src = _make_source_csv(tmp_path, "s.csv", [_full_row("G1"), _full_row("G2")])
    date_results = [
        _make_ready_result("2025-05-08", str(src), n_rows=2),
        _make_empty_result("2025-05-09"),
    ]
    out_dir = tmp_path / "out"
    manifest = build_artifact_manifest(date_results, out_dir)

    assert "2025-05-08" in manifest.written_dates
    assert "2025-05-09" in manifest.skipped_dates
    assert manifest.total_rows_written == 2
    assert manifest.paper_only is True
    assert manifest.production_ready is False


def test_build_manifest_is_frozen(tmp_path):
    date_results = [_make_empty_result("2025-05-08")]
    out_dir = tmp_path / "out"
    manifest = build_artifact_manifest(date_results, out_dir)
    with pytest.raises(Exception):
        manifest.total_rows_written = 99  # type: ignore
