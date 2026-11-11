"""
tests/test_run_mlb_strategy_simulation_spine.py

Smoke tests for the CLI entrypoint.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "scripts" / "run_mlb_strategy_simulation_spine.py"
_VENV_PYTHON = _ROOT / ".venv" / "bin" / "python"
_DEFAULT_CSV = _ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"

# Use the venv python if available, otherwise the current interpreter
_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable


def _run_script(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_PYTHON, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
    )


# ── Tests: CLI smoke ──────────────────────────────────────────────────────────

class TestCLISmoke:
    def test_cli_runs_successfully_with_default_csv(self, tmp_path):
        """CLI runs end-to-end with the real default CSV."""
        if not _DEFAULT_CSV.exists():
            pytest.skip("Default CSV not available")
        out_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "test-run"
        result = _run_script(
            "--date-start", "2025-03-01",
            "--date-end", "2025-06-30",
            "--strategy-name", "test_cli_smoke",
            "--edge-threshold", "0.01",
            "--kelly-cap", "0.05",
            "--output-dir", str(out_dir),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_cli_writes_under_paper_path(self, tmp_path):
        """Output files are written under outputs/simulation/PAPER/."""
        if not _DEFAULT_CSV.exists():
            pytest.skip("Default CSV not available")
        out_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "smoke-test"
        _run_script(
            "--date-start", "2025-03-01",
            "--date-end", "2025-06-30",
            "--strategy-name", "test_paper_path",
            "--output-dir", str(out_dir),
        )
        # At least one .jsonl file should exist
        jsonl_files = list(out_dir.glob("*.jsonl"))
        assert len(jsonl_files) >= 1, f"No JSONL output in {out_dir}"

    def test_cli_output_jsonl_is_valid(self, tmp_path):
        """The JSONL output is valid JSON with required fields."""
        if not _DEFAULT_CSV.exists():
            pytest.skip("Default CSV not available")
        out_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "json-check"
        _run_script(
            "--date-start", "2025-03-01",
            "--date-end", "2025-06-30",
            "--strategy-name", "test_json_valid",
            "--output-dir", str(out_dir),
        )
        jsonl_files = list(out_dir.glob("*.jsonl"))
        if not jsonl_files:
            pytest.skip("No output file (may be no qualifying rows in date range)")
        content = jsonl_files[0].read_text(encoding="utf-8").strip()
        parsed = json.loads(content)
        assert "simulation_id" in parsed
        assert "gate_status" in parsed
        assert parsed["paper_only"] is True

    def test_cli_md_report_written(self, tmp_path):
        """A Markdown summary report is written alongside the JSONL."""
        if not _DEFAULT_CSV.exists():
            pytest.skip("Default CSV not available")
        out_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "md-check"
        _run_script(
            "--date-start", "2025-03-01",
            "--date-end", "2025-06-30",
            "--strategy-name", "test_md_report",
            "--output-dir", str(out_dir),
        )
        md_files = list(out_dir.glob("*_report.md"))
        assert len(md_files) >= 1, f"No Markdown report in {out_dir}"

    def test_cli_refuses_missing_input_csv(self, tmp_path):
        """CLI exits with non-zero code if input CSV does not exist."""
        out_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "refuse-test"
        result = _run_script(
            "--input-csv", "/nonexistent/path/does_not_exist.csv",
            "--output-dir", str(out_dir),
        )
        assert result.returncode != 0
        assert "REFUSED" in result.stderr or "does not exist" in result.stderr

    def test_cli_refuses_output_outside_paper_zone(self, tmp_path):
        """CLI exits with non-zero code if output dir is outside PAPER zone."""
        if not _DEFAULT_CSV.exists():
            pytest.skip("Default CSV not available")
        bad_output = tmp_path / "outputs" / "production" / "bets"
        result = _run_script(
            "--date-start", "2025-03-01",
            "--date-end", "2025-06-30",
            "--output-dir", str(bad_output),
        )
        assert result.returncode != 0
        assert "REFUSED" in result.stderr

    def test_cli_one_line_summary_printed(self, tmp_path):
        """CLI prints one-line summary with expected fields."""
        if not _DEFAULT_CSV.exists():
            pytest.skip("Default CSV not available")
        out_dir = tmp_path / "outputs" / "simulation" / "PAPER" / "summary-test"
        result = _run_script(
            "--date-start", "2025-03-01",
            "--date-end", "2025-06-30",
            "--strategy-name", "test_summary",
            "--output-dir", str(out_dir),
        )
        assert result.returncode == 0
        stdout = result.stdout
        # One-line summary contains expected keywords
        assert "PAPER-SIM" in stdout
        assert "gate=" in stdout
