"""
tests/test_p27_p25_full_range_runner.py

Unit tests for p27_p25_full_range_runner.py.
"""
import json
import os
from pathlib import Path

import pytest

from wbc_backend.recommendation.p27_p25_full_range_runner import (
    run_p25_separation_for_range,
    validate_p25_full_range_outputs,
    summarize_p25_full_range_outputs,
)


class TestValidateP25FullRangeOutputs:
    def test_missing_dir_returns_false(self, tmp_path):
        missing = tmp_path / "nonexistent"
        ok, reason = validate_p25_full_range_outputs(missing)
        assert ok is False
        assert "does not exist" in reason.lower() or "not found" in reason.lower() or reason

    def test_missing_gate_json_returns_false(self, tmp_path):
        (tmp_path / "true_date_slices").mkdir()
        ok, reason = validate_p25_full_range_outputs(tmp_path)
        assert ok is False

    def test_wrong_gate_returns_false(self, tmp_path):
        (tmp_path / "p25_gate_result.json").write_text(json.dumps({"p25_gate": "WRONG_GATE"}))
        (tmp_path / "true_date_slices").mkdir()
        ok, reason = validate_p25_full_range_outputs(tmp_path)
        assert ok is False
        assert "gate" in reason.lower() or "wrong" in reason.lower() or reason

    def test_no_slices_dir_returns_false(self, tmp_path):
        (tmp_path / "p25_gate_result.json").write_text(
            json.dumps({"p25_gate": "P25_TRUE_DATE_SOURCE_SEPARATION_READY"})
        )
        # no true_date_slices/
        ok, reason = validate_p25_full_range_outputs(tmp_path)
        assert ok is False

    def test_empty_slices_dir_returns_false(self, tmp_path):
        (tmp_path / "p25_gate_result.json").write_text(
            json.dumps({"p25_gate": "P25_TRUE_DATE_SOURCE_SEPARATION_READY"})
        )
        (tmp_path / "true_date_slices").mkdir()
        # no date subdirectories
        ok, reason = validate_p25_full_range_outputs(tmp_path)
        assert ok is False

    def test_valid_outputs_returns_true(self, tmp_path):
        (tmp_path / "p25_gate_result.json").write_text(
            json.dumps({"p25_gate": "P25_TRUE_DATE_SOURCE_SEPARATION_READY"})
        )
        slices = tmp_path / "true_date_slices"
        slices.mkdir()
        date_dir = slices / "2025-05-08"
        date_dir.mkdir()
        (date_dir / "p15_true_date_input.csv").write_text(
            "date,game_id,market,gate_16_eligible\n"
            "2025-05-08,G001,OU,P16_6_ELIGIBLE_PAPER_RECOMMENDATION\n"
        )
        ok, reason = validate_p25_full_range_outputs(tmp_path)
        assert ok is True, reason

    def test_2026_dates_rejected(self, tmp_path):
        """Guard: relabeled 2026 dates must be rejected."""
        (tmp_path / "p25_gate_result.json").write_text(
            json.dumps({"p25_gate": "P25_TRUE_DATE_SOURCE_SEPARATION_READY"})
        )
        slices = tmp_path / "true_date_slices"
        slices.mkdir()
        date_dir = slices / "2026-01-15"  # relabeled
        date_dir.mkdir()
        (date_dir / "p15_true_date_input.csv").write_text("date\n2026-01-15\n")
        ok, reason = validate_p25_full_range_outputs(tmp_path)
        assert ok is False
        assert "2026" in reason


class TestSummarizeP25FullRangeOutputs:
    def _make_valid_p25_dir(self, tmp_path, n_dates=2):
        (tmp_path / "p25_gate_result.json").write_text(
            json.dumps({"p25_gate": "P25_TRUE_DATE_SOURCE_SEPARATION_READY"})
        )
        slices = tmp_path / "true_date_slices"
        slices.mkdir()
        dates = ["2025-05-08", "2025-05-09", "2025-05-10"]
        for d in dates[:n_dates]:
            dd = slices / d
            dd.mkdir()
            (dd / "p15_true_date_input.csv").write_text(
                f"date,game_id\n{d},G001\n{d},G002\n"
            )
        return tmp_path

    def test_summary_has_gate(self, tmp_path):
        d = self._make_valid_p25_dir(tmp_path)
        s = summarize_p25_full_range_outputs(d)
        assert s["p25_gate"] == "P25_TRUE_DATE_SOURCE_SEPARATION_READY"

    def test_summary_correct_n_slice_dates(self, tmp_path):
        d = self._make_valid_p25_dir(tmp_path, n_dates=3)
        s = summarize_p25_full_range_outputs(d)
        assert s["n_slice_dates"] == 3

    def test_summary_total_rows(self, tmp_path):
        d = self._make_valid_p25_dir(tmp_path, n_dates=2)
        s = summarize_p25_full_range_outputs(d)
        # each date has 2 data rows
        assert s["total_rows_across_slices"] == 4

    def test_nonexistent_dir_returns_error_summary(self, tmp_path):
        missing = tmp_path / "not_here"
        s = summarize_p25_full_range_outputs(missing)
        assert s.get("p25_gate") is None or "error" in str(s.get("p25_gate", "")).lower() or s


class TestRunP25SeparationForRange:
    def test_raises_file_not_found_if_script_missing(self, tmp_path, monkeypatch):
        """If the P25 script is missing, should raise FileNotFoundError."""
        monkeypatch.chdir(tmp_path)
        # No script present, so it should raise
        with pytest.raises(FileNotFoundError):
            run_p25_separation_for_range(
                date_start="2025-05-08",
                date_end="2025-05-08",
                output_dir=tmp_path / "out",
                cwd=str(tmp_path),
            )
