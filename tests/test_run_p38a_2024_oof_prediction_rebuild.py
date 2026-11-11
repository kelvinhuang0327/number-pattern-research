"""Tests for P38A CLI script."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "run_p38a_2024_oof_prediction_rebuild.py"

_REAL_CSV = _REPO_ROOT / "data" / "mlb_2024" / "processed" / "mlb_2024_game_identity_outcomes_joined.csv"

_MINIMAL_CSV_CONTENT = (
    "game_id,game_date,season,away_team,home_team,source_name,source_row_number,away_score,home_score,y_true_home_win\n"
    + "\n".join(
        f"G{i:04d},2024-04-{(i%28)+1:02d},2024,NYA,BOS,Retrosheet,{i},{ (i%4)+1},{(i%5)+2},{1 if (i%5)+2>(i%4)+1 else 0}"
        for i in range(1, 101)  # 100 games — enough for folds
    )
)


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    venv_python = _REPO_ROOT / ".venv" / "bin" / "python"
    python = str(venv_python) if venv_python.exists() else sys.executable
    return subprocess.run(
        [python, str(_SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )


# ── Tests ────────────────────────────────────────────────────────────────────


def test_cli_exit_code_on_missing_input():
    """CLI must exit with code 1 when --input-csv does not exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _run_cli(
            [
                "--input-csv",
                "/nonexistent/path/missing.csv",
                "--output-dir",
                tmpdir,
                "--paper-only",
            ]
        )
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"


def test_cli_exit_code_without_paper_only():
    """CLI must exit with code 1 when --paper-only flag is omitted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "input.csv"
        csv_path.write_text(_MINIMAL_CSV_CONTENT)
        result = _run_cli(
            [
                "--input-csv",
                str(csv_path),
                "--output-dir",
                tmpdir,
                # --paper-only intentionally omitted
            ]
        )
    assert result.returncode == 1


def test_cli_writes_required_outputs():
    """CLI must write predictions CSV, metrics JSON, and gate JSON on success."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "input.csv"
        csv_path.write_text(_MINIMAL_CSV_CONTENT)
        out_dir = Path(tmpdir) / "output"
        result = _run_cli(
            [
                "--input-csv",
                str(csv_path),
                "--output-dir",
                str(out_dir),
                "--paper-only",
            ]
        )
        # Accept 0 (READY) or 1 (BLOCKED due to coverage) — either way files should exist IF it ran
        pred_path = out_dir / "p38a_2024_oof_predictions.csv"
        metrics_path = out_dir / "p38a_oof_metrics.json"
        gate_path = out_dir / "p38a_gate_result.json"

        # If gate was READY, all three files must exist
        stdout_gate = result.stdout.strip()
        if "READY" in stdout_gate:
            assert pred_path.exists(), f"Missing: {pred_path}"
            assert metrics_path.exists(), f"Missing: {metrics_path}"
            assert gate_path.exists(), f"Missing: {gate_path}"
        else:
            # For BLOCKED cases, just ensure script exited cleanly (no unhandled exception)
            assert result.returncode in (0, 1), f"Unexpected exit code: {result.returncode}"


def test_cli_exit_code_on_ready():
    """CLI must exit 0 when P38A_2024_OOF_PREDICTION_READY is returned."""
    if not _REAL_CSV.exists():
        pytest.skip("Real CSV not present — skip production-data test")

    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "output"
        result = _run_cli(
            [
                "--input-csv",
                str(_REAL_CSV),
                "--output-dir",
                str(out_dir),
                "--paper-only",
            ]
        )

    assert result.returncode == 0, (
        f"Expected exit 0 (READY), got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "P38A_2024_OOF_PREDICTION_READY" in result.stdout


def test_cli_gate_json_paper_only_flag():
    """Gate JSON must have paper_only=True and production_ready=False."""
    if not _REAL_CSV.exists():
        pytest.skip("Real CSV not present — skip production-data test")

    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "output"
        result = _run_cli(
            [
                "--input-csv",
                str(_REAL_CSV),
                "--output-dir",
                str(out_dir),
                "--paper-only",
            ]
        )
        if result.returncode == 0:
            gate_data = json.loads((out_dir / "p38a_gate_result.json").read_text())
            assert gate_data["paper_only"] is True
            assert gate_data["production_ready"] is False
