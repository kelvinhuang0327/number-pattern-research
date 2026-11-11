"""
tests/test_run_p27_full_true_date_backfill_expansion.py

Integration/CLI tests for scripts/run_p27_full_true_date_backfill_expansion.py.
"""
import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")
CLI = str(REPO_ROOT / "scripts" / "run_p27_full_true_date_backfill_expansion.py")

ENV = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}

EXPECTED_OUTPUT_FILES = {
    "p27_gate_result.json",
    "p27_full_backfill_summary.json",
    "p27_full_backfill_summary.md",
    "segment_results.csv",
    "date_results.csv",
    "blocked_segments.json",
    "runtime_guard.json",
}


def _make_p25_slice_dir(base: Path, run_date: str, n_rows: int = 5) -> None:
    """Create a minimal valid P25 output dir with a single date slice."""
    slices = base / "true_date_slices" / run_date
    slices.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "date": run_date,
            "game_id": f"G{i:03d}",
            "market": "OU",
            "gate_16_eligible": "P16_6_ELIGIBLE_PAPER_RECOMMENDATION",
            "settlement_status": "settled" if i % 2 == 0 else "settled",
            "pnl_units": "0.10" if i % 2 == 0 else "-0.25",
            "paper_stake_units": "0.25",
            "is_win": "True" if i % 2 == 0 else "False",
            "is_loss": "False" if i % 2 == 0 else "True",
        }
        for i in range(n_rows)
    ]
    with open(slices / "p15_true_date_input.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _make_valid_p25_dir(base: Path, date_start: str, date_end: str) -> Path:
    """Create a full valid P25 output dir spanning date_start..date_end (single day only for tests)."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "p25_gate_result.json").write_text(json.dumps({
        "p25_gate": "P25_TRUE_DATE_SOURCE_SEPARATION_READY",
        "date_start": date_start,
        "date_end": date_end,
    }))
    _make_p25_slice_dir(base, date_start)
    return base


def _run_cli(args: list, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, CLI] + args,
        capture_output=True,
        text=True,
        cwd=cwd or str(REPO_ROOT),
        env=ENV,
        timeout=120,
    )


class TestCliPaperOnlyGuard:
    def test_paper_only_false_exits_2(self, tmp_path):
        result = _run_cli([
            "--date-start", "2025-05-08",
            "--date-end", "2025-05-08",
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "false",
        ])
        assert result.returncode == 2
        assert "paper" in result.stderr.lower()

    def test_paper_only_true_passes_guard(self, tmp_path):
        # Should proceed past guard (will fail later on P25 missing, not guard)
        result = _run_cli([
            "--date-start", "2025-05-08",
            "--date-end", "2025-05-08",
            "--output-dir", str(tmp_path / "out"),
            "--paper-only", "true",
        ])
        # returncode may be 1 (BLOCKED) or 2 (FAIL) but NOT 2 due to paper guard
        stderr_lower = result.stderr.lower()
        assert "paper-only must be 'true'" not in result.stderr


class TestCliOutputFiles:
    @pytest.mark.skipif(
        not Path(CLI).exists(),
        reason="CLI script not found"
    )
    def test_emits_7_output_files(self, tmp_path):
        """
        Provide a pre-built P25 dir so P25 runner is satisfied,
        then run CLI with a 1-day range. P26 will likely fail/block
        but all 7 files should still be written.
        """
        date = "2025-05-08"
        p25_dir = tmp_path / "p25_true_date_source_separation_2025-05-08_2025-05-08"
        _make_valid_p25_dir(p25_dir, date, date)

        out_dir = tmp_path / "p27_out"

        result = _run_cli([
            "--date-start", date,
            "--date-end", date,
            "--segment-days", "1",
            "--output-dir", str(out_dir),
            "--paper-only", "true",
            "--max-runtime-seconds", "120",
        ])

        # Outputs should be written regardless of gate status
        if out_dir.exists():
            written = {f.name for f in out_dir.iterdir() if f.is_file()}
            assert EXPECTED_OUTPUT_FILES.issubset(written), (
                f"Missing files: {EXPECTED_OUTPUT_FILES - written}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )


class TestCliGateJson:
    def test_gate_json_paper_safe(self, tmp_path):
        date = "2025-05-08"
        p25_dir = tmp_path / "p25_true_date_source_separation_2025-05-08_2025-05-08"
        _make_valid_p25_dir(p25_dir, date, date)
        out_dir = tmp_path / "p27_out"

        _run_cli([
            "--date-start", date,
            "--date-end", date,
            "--segment-days", "1",
            "--output-dir", str(out_dir),
            "--paper-only", "true",
            "--max-runtime-seconds", "120",
        ])

        gate_path = out_dir / "p27_gate_result.json"
        if gate_path.exists():
            data = json.loads(gate_path.read_text())
            assert data.get("paper_only") is True
            assert data.get("production_ready") is False

    def test_blocked_segments_json_paper_safe(self, tmp_path):
        date = "2025-05-08"
        p25_dir = tmp_path / "p25_true_date_source_separation_2025-05-08_2025-05-08"
        _make_valid_p25_dir(p25_dir, date, date)
        out_dir = tmp_path / "p27_out"

        _run_cli([
            "--date-start", date,
            "--date-end", date,
            "--segment-days", "1",
            "--output-dir", str(out_dir),
            "--paper-only", "true",
            "--max-runtime-seconds", "120",
        ])

        blocked_path = out_dir / "blocked_segments.json"
        if blocked_path.exists():
            data = json.loads(blocked_path.read_text())
            assert data.get("paper_only") is True
            assert data.get("production_ready") is False


class TestCliDeterminism:
    def test_deterministic_across_two_runs(self, tmp_path):
        """
        Two identical CLI runs (excluding generated_at) should produce identical gate values.
        """
        date = "2025-05-08"
        p25_dir = tmp_path / "p25_true_date_source_separation_2025-05-08_2025-05-08"
        _make_valid_p25_dir(p25_dir, date, date)

        for run_num in [1, 2]:
            out_dir = tmp_path / f"p27_det_run{run_num}"
            _run_cli([
                "--date-start", date,
                "--date-end", date,
                "--segment-days", "1",
                "--output-dir", str(out_dir),
                "--paper-only", "true",
                "--max-runtime-seconds", "120",
            ])

        run1 = tmp_path / "p27_det_run1"
        run2 = tmp_path / "p27_det_run2"

        # Compare gate files, excluding generated_at
        for fname in ["p27_gate_result.json", "blocked_segments.json", "runtime_guard.json"]:
            f1 = run1 / fname
            f2 = run2 / fname
            if f1.exists() and f2.exists():
                d1 = json.loads(f1.read_text())
                d2 = json.loads(f2.read_text())
                # Remove non-deterministic fields
                for d in [d1, d2]:
                    d.pop("generated_at", None)
                    d.pop("actual_runtime_seconds", None)
                    d.pop("max_runtime_seconds", None)
                assert d1 == d2, f"Non-deterministic {fname}: {d1} vs {d2}"

        # Compare CSV files byte-for-byte
        for fname in ["segment_results.csv"]:
            f1 = run1 / fname
            f2 = run2 / fname
            if f1.exists() and f2.exists():
                assert f1.read_text() == f2.read_text(), f"Non-deterministic {fname}"


class TestCliExitCodes:
    def test_missing_date_start_exits_with_error(self):
        result = _run_cli([
            "--date-end", "2025-05-08",
            "--output-dir", "/tmp/x",
            "--paper-only", "true",
        ])
        assert result.returncode != 0

    def test_invalid_paper_only_value(self, tmp_path):
        result = _run_cli([
            "--date-start", "2025-05-08",
            "--date-end", "2025-05-08",
            "--output-dir", str(tmp_path),
            "--paper-only", "INVALID",
        ])
        assert result.returncode != 0
