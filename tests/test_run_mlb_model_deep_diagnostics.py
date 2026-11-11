"""
tests/test_run_mlb_model_deep_diagnostics.py

P8: Integration tests for scripts/run_mlb_model_deep_diagnostics.py
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _ROOT / ".venv" / "bin" / "python"
_SCRIPT = _ROOT / "scripts" / "run_mlb_model_deep_diagnostics.py"
_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable


# ─────────────────────────────────────────────────────────────────────────────
# § 0  Test fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.touch()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _make_model_row(
    *,
    date: str = "2025-05-01",
    home: str = "Los Angeles Dodgers",
    away: str = "San Francisco Giants",
    home_ml: int = -120,
    away_ml: int = 110,
    home_score: int = 5,
    away_score: int = 3,
    model_prob: float = 0.58,
    source: str = "real_model",
) -> dict:
    return {
        "Date": date,
        "Home": home,
        "Away": away,
        "Home ML": str(home_ml),
        "Away ML": str(away_ml),
        "Home Score": str(home_score),
        "Away Score": str(away_score),
        "Status": "Final",
        "model_prob_home": str(model_prob),
        "probability_source": source,
    }


def _make_oof_row(**kwargs) -> dict:
    row = _make_model_row(**kwargs)
    row["probability_source"] = "calibrated_model"
    return row


@pytest.fixture()
def paper_output_dir(tmp_path: Path) -> Path:
    """Return a temp dir that satisfies the PAPER output gate."""
    d = _ROOT / "outputs" / "predictions" / "PAPER" / "__pytest_p8_deep_diag__"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture()
def raw_csv(paper_output_dir: Path) -> Path:
    p = paper_output_dir / "raw_model.csv"
    rows = [
        _make_model_row(date=f"2025-05-{i+1:02d}", model_prob=0.52 + i * 0.01)
        for i in range(20)
    ]
    _write_csv(p, rows)
    return p


@pytest.fixture()
def oof_csv(paper_output_dir: Path) -> Path:
    p = paper_output_dir / "oof_model.csv"
    rows = [
        _make_oof_row(date=f"2025-05-{i+1:02d}", model_prob=0.52 + i * 0.005)
        for i in range(20)
    ]
    _write_csv(p, rows)
    return p


def _run_script(*args: str) -> subprocess.CompletedProcess:
    cmd = [_PYTHON, str(_SCRIPT)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Successful run
# ─────────────────────────────────────────────────────────────────────────────

class TestRunScriptSuccess:
    def test_exit_code_zero(self, raw_csv, oof_csv, paper_output_dir):
        result = _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
            "--top-n", "5",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_stdout_contains_bss(self, raw_csv, oof_csv, paper_output_dir):
        result = _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        assert result.returncode == 0
        assert "raw_bss=" in result.stdout
        assert "oof_bss=" in result.stdout

    def test_stdout_contains_join_risk(self, raw_csv, oof_csv, paper_output_dir):
        result = _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        assert "join_risk_level=" in result.stdout

    def test_output_files_created(self, raw_csv, oof_csv, paper_output_dir):
        _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        expected = [
            "model_deep_diagnostics_raw.json",
            "model_deep_diagnostics_oof.json",
            "model_join_integrity_audit.json",
            "model_worst_segments.json",
            "model_deep_diagnostics_summary.md",
        ]
        for name in expected:
            assert (paper_output_dir / name).exists(), f"{name} not found"

    def test_raw_json_valid(self, raw_csv, oof_csv, paper_output_dir):
        _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        raw_json_path = paper_output_dir / "model_deep_diagnostics_raw.json"
        with raw_json_path.open() as fh:
            data = json.load(fh)
        assert "row_count" in data
        assert "brier_skill_score" in data
        assert "orientation_diagnostics" in data

    def test_oof_json_valid(self, raw_csv, oof_csv, paper_output_dir):
        _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        oof_json_path = paper_output_dir / "model_deep_diagnostics_oof.json"
        with oof_json_path.open() as fh:
            data = json.load(fh)
        assert "segment_summary" in data
        assert "join_diagnostics" in data

    def test_join_audit_json_valid(self, raw_csv, oof_csv, paper_output_dir):
        _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        join_path = paper_output_dir / "model_join_integrity_audit.json"
        with join_path.open() as fh:
            data = json.load(fh)
        assert "risk_level" in data
        assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_worst_segments_json_valid(self, raw_csv, oof_csv, paper_output_dir):
        _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        worst_path = paper_output_dir / "model_worst_segments.json"
        with worst_path.open() as fh:
            data = json.load(fh)
        assert "worst_segments" in data
        assert isinstance(data["worst_segments"], list)

    def test_summary_md_valid(self, raw_csv, oof_csv, paper_output_dir):
        _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        md_path = paper_output_dir / "model_deep_diagnostics_summary.md"
        content = md_path.read_text(encoding="utf-8")
        assert "P8 Model Deep Diagnostics Summary" in content
        assert "Orientation Diagnostics" in content
        assert "Join Integrity Audit" in content


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Refusals
# ─────────────────────────────────────────────────────────────────────────────

class TestRunScriptRefusals:
    def test_missing_raw_input_exits_1(self, oof_csv, paper_output_dir):
        result = _run_script(
            "--raw-input-csv", "outputs/predictions/PAPER/__nonexistent__/raw.csv",
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        assert result.returncode == 1
        assert "REFUSED" in result.stderr or "not found" in result.stderr.lower()

    def test_missing_oof_input_exits_1(self, raw_csv, paper_output_dir):
        result = _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", "outputs/predictions/PAPER/__nonexistent__/oof.csv",
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        assert result.returncode == 1
        assert "REFUSED" in result.stderr

    def test_output_outside_paper_exits_2(self, raw_csv, oof_csv, tmp_path):
        result = _run_script(
            "--raw-input-csv", str(raw_csv.relative_to(_ROOT)),
            "--input-csv", str(oof_csv.relative_to(_ROOT)),
            "--output-dir", str(tmp_path),
        )
        assert result.returncode == 2
        assert "REFUSED" in result.stderr

    def test_no_model_source_exits_1(self, paper_output_dir):
        """CSV with unknown probability_source should be refused."""
        bad_csv = paper_output_dir / "bad_source.csv"
        rows = [
            {
                "Date": "2025-05-01",
                "Home": "Los Angeles Dodgers",
                "Away": "San Francisco Giants",
                "Home ML": "-110",
                "Away ML": "-110",
                "Home Score": "5",
                "Away Score": "3",
                "Status": "Final",
                "model_prob_home": "0.55",
                "probability_source": "unknown",
            }
        ]
        _write_csv(bad_csv, rows)
        result = _run_script(
            "--raw-input-csv", str(bad_csv.relative_to(_ROOT)),
            "--input-csv", str(bad_csv.relative_to(_ROOT)),
            "--output-dir", str(paper_output_dir.relative_to(_ROOT)),
        )
        assert result.returncode == 1
        assert "REFUSED" in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Defaults
# ─────────────────────────────────────────────────────────────────────────────

class TestRunScriptDefaultPaths:
    def test_default_paths_used_when_they_exist(self):
        """
        If both default CSVs exist (P5 and P7 artifacts), the script should
        run without explicit path flags.
        """
        raw_default = _ROOT / "outputs/predictions/PAPER/2026-05-11/mlb_odds_with_model_probabilities.csv"
        oof_default = _ROOT / "outputs/predictions/PAPER/2026-05-11/mlb_odds_with_oof_calibrated_probabilities.csv"
        if not raw_default.exists() or not oof_default.exists():
            pytest.skip("Default P5/P7 CSVs not present in this environment")
        result = subprocess.run(
            [_PYTHON, str(_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(_ROOT),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "raw_bss=" in result.stdout
