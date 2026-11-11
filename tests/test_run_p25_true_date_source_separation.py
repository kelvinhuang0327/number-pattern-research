"""
tests/test_run_p25_true_date_source_separation.py

CLI integration tests for run_p25_true_date_source_separation.py.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = str(REPO_ROOT / "scripts" / "run_p25_true_date_source_separation.py")
PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")

# Expected output filenames (6 total)
EXPECTED_OUTPUTS = [
    "true_date_source_separation_summary.json",
    "true_date_source_separation_summary.md",
    "date_slice_results.csv",
    "true_date_artifact_manifest.json",
    "recommended_backfill_range.json",
    "p25_gate_result.json",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, CLI, *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


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


def _make_scan_base(tmp_path: Path, rows: list[dict], subdir: str = "sources") -> Path:
    """Create a scan base directory with a source CSV containing given rows."""
    d = tmp_path / subdir
    d.mkdir(parents=True, exist_ok=True)
    src = d / "source.csv"
    pd.DataFrame(rows).to_csv(src, index=False)
    return tmp_path  # return the base, not the subdir


# ---------------------------------------------------------------------------
# Guard tests
# ---------------------------------------------------------------------------


class TestCLIGuards:
    def test_paper_only_false_exits_2(self, tmp_path):
        """--paper-only does not accept values other than 'true'."""
        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--scan-base-path", str(tmp_path),
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "false",
        )
        assert result.returncode == 2

    def test_missing_scan_base_exits_2(self, tmp_path):
        """Non-existent scan base path should cause exit 2."""
        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--scan-base-path", str(tmp_path / "nonexistent"),
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "true",
        )
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# Blocked path — 2026 range has no true rows (source is 2025-only)
# ---------------------------------------------------------------------------


class TestCLIBlockedPath:
    def test_2026_range_exits_1(self, tmp_path):
        """For 2026-05-01 to 2026-05-12 with 2025-only source, gate is BLOCKED."""
        rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-09")]
        scan_base = _make_scan_base(tmp_path, rows)
        out_dir = tmp_path / "out"

        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-03",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        assert result.returncode == 1

    def test_blocked_still_writes_6_files(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08")]
        scan_base = _make_scan_base(tmp_path, rows)
        out_dir = tmp_path / "out"

        _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-02",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )

        for fname in EXPECTED_OUTPUTS:
            assert (out_dir / fname).exists(), f"Missing output: {fname}"

    def test_gate_json_not_ready(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08")]
        scan_base = _make_scan_base(tmp_path, rows)
        out_dir = tmp_path / "out"

        _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-02",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )

        gate = json.loads((out_dir / "p25_gate_result.json").read_text())
        assert gate["p25_gate"] != "P25_TRUE_DATE_SOURCE_SEPARATION_READY"
        assert gate["paper_only"] is True
        assert gate["production_ready"] is False

    def test_recommended_backfill_is_detected_range(self, tmp_path):
        """When 2026 range is empty, recommended range should be the true source range."""
        rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-09")]
        scan_base = _make_scan_base(tmp_path, rows)
        out_dir = tmp_path / "out"

        _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-02",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )

        rec = json.loads((out_dir / "recommended_backfill_range.json").read_text())
        assert rec["recommended_backfill_date_start"] == "2025-05-08"
        assert rec["paper_only"] is True
        assert rec["production_ready"] is False

    def test_stdout_contains_production_ready_false(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08")]
        scan_base = _make_scan_base(tmp_path, rows)
        out_dir = tmp_path / "out"

        result = _run_cli(
            "--date-start", "2026-05-01",
            "--date-end", "2026-05-01",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        assert "production_ready" in result.stdout
        assert "False" in result.stdout


# ---------------------------------------------------------------------------
# Ready path — requesting true source dates
# ---------------------------------------------------------------------------


class TestCLIReadyPath:
    def test_true_date_range_exits_0(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-09")]
        scan_base = _make_scan_base(tmp_path, rows)
        out_dir = tmp_path / "out"

        result = _run_cli(
            "--date-start", "2025-05-08",
            "--date-end", "2025-05-09",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )
        assert result.returncode == 0

    def test_ready_gate_json_correct(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08")]
        scan_base = _make_scan_base(tmp_path, rows)
        out_dir = tmp_path / "out"

        _run_cli(
            "--date-start", "2025-05-08",
            "--date-end", "2025-05-08",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )

        gate = json.loads((out_dir / "p25_gate_result.json").read_text())
        assert gate["p25_gate"] == "P25_TRUE_DATE_SOURCE_SEPARATION_READY"
        assert gate["n_true_date_ready"] == 1
        assert gate["paper_only"] is True
        assert gate["production_ready"] is False

    def test_ready_writes_slice_csv_and_summary(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-08")]
        scan_base = _make_scan_base(tmp_path, rows)
        out_dir = tmp_path / "out"

        _run_cli(
            "--date-start", "2025-05-08",
            "--date-end", "2025-05-08",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )

        slice_csv = out_dir / "true_date_slices" / "2025-05-08" / "p15_true_date_input.csv"
        slice_json = out_dir / "true_date_slices" / "2025-05-08" / "p15_true_date_input_summary.json"
        assert slice_csv.exists()
        assert slice_json.exists()

        df = pd.read_csv(slice_csv)
        assert len(df) == 2

    def test_date_slice_csv_has_all_requested_dates(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-09")]
        scan_base = _make_scan_base(tmp_path, rows)
        out_dir = tmp_path / "out"

        _run_cli(
            "--date-start", "2025-05-08",
            "--date-end", "2025-05-09",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out_dir),
            "--paper-only", "true",
        )

        slice_results_path = out_dir / "date_slice_results.csv"
        with open(slice_results_path) as fh:
            reader = csv.DictReader(fh)
            rows_read = list(reader)
        dates = [r["run_date"] for r in rows_read]
        assert "2025-05-08" in dates
        assert "2025-05-09" in dates


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestCLIDeterminism:
    def test_gate_result_deterministic(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08")]
        scan_base = _make_scan_base(tmp_path, rows)

        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        _run_cli(
            "--date-start", "2025-05-08",
            "--date-end", "2025-05-08",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out1),
            "--paper-only", "true",
        )
        _run_cli(
            "--date-start", "2025-05-08",
            "--date-end", "2025-05-08",
            "--scan-base-path", str(scan_base / "sources"),
            "--output-dir", str(out2),
            "--paper-only", "true",
        )

        g1 = json.loads((out1 / "p25_gate_result.json").read_text())
        g2 = json.loads((out2 / "p25_gate_result.json").read_text())

        # Exclude generated_at from comparison
        for g in [g1, g2]:
            g.pop("generated_at", None)

        assert g1 == g2

    def test_date_slice_csv_deterministic(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08"), _full_row("G002", "2025-05-08")]
        scan_base = _make_scan_base(tmp_path, rows)

        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        for out in [out1, out2]:
            _run_cli(
                "--date-start", "2025-05-08",
                "--date-end", "2025-05-08",
                "--scan-base-path", str(scan_base / "sources"),
                "--output-dir", str(out),
                "--paper-only", "true",
            )

        csv1 = (out1 / "date_slice_results.csv").read_text()
        csv2 = (out2 / "date_slice_results.csv").read_text()
        assert csv1 == csv2

    def test_recommended_backfill_range_deterministic(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08")]
        scan_base = _make_scan_base(tmp_path, rows)

        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        for out in [out1, out2]:
            _run_cli(
                "--date-start", "2026-05-01",
                "--date-end", "2026-05-01",
                "--scan-base-path", str(scan_base / "sources"),
                "--output-dir", str(out),
                "--paper-only", "true",
            )

        rec1 = json.loads((out1 / "recommended_backfill_range.json").read_text())
        rec2 = json.loads((out2 / "recommended_backfill_range.json").read_text())

        for r in [rec1, rec2]:
            r.pop("generated_at", None)

        assert rec1 == rec2

    def test_manifest_deterministic(self, tmp_path):
        rows = [_full_row("G001", "2025-05-08")]
        scan_base = _make_scan_base(tmp_path, rows)

        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        for out in [out1, out2]:
            _run_cli(
                "--date-start", "2025-05-08",
                "--date-end", "2025-05-08",
                "--scan-base-path", str(scan_base / "sources"),
                "--output-dir", str(out),
                "--paper-only", "true",
            )

        m1 = json.loads((out1 / "true_date_artifact_manifest.json").read_text())
        m2 = json.loads((out2 / "true_date_artifact_manifest.json").read_text())

        for m in [m1, m2]:
            m.pop("generated_at", None)
            m.pop("output_dir", None)  # output_dir differs by design (different run dirs)

        assert m1 == m2
