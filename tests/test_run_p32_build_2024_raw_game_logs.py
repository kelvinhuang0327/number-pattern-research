"""
Tests for P32 CLI — run_p32_build_2024_raw_game_logs.py

Coverage:
- CLI exits 1 with P32_BLOCKED_SOURCE_FILE_MISSING when source is missing
- gate JSON is written even when source is missing
- report is written even when source is missing
- report contains valid marker (P32_RAW_GAME_LOG_ARTIFACT_BLOCKED_SOURCE_MISSING)
- no production_ready=True in gate JSON
- deterministic blocker: run CLI twice, gate_result.json identical (excluding generated_at)
- With fixture source: test exit 0, test all artifacts written, test no odds/predictions
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")
CLI = str(REPO_ROOT / "scripts" / "run_p32_build_2024_raw_game_logs.py")

# Expected markers
BLOCKED_MARKER = "P32_RAW_GAME_LOG_ARTIFACT_BLOCKED_SOURCE_MISSING"
READY_MARKER = "P32_RAW_GAME_LOG_ARTIFACT_READY"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(source_path: str, output_dir: str, season: int = 2024) -> subprocess.CompletedProcess:
    """Run the P32 CLI and capture output."""
    return subprocess.run(
        [PYTHON, CLI,
         "--source-path", source_path,
         "--output-dir", output_dir,
         "--season", str(season),
         "--paper-only", "true"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _make_minimal_retrosheet_file(path: Path, n_rows: int = 10) -> None:
    """Write a minimal Retrosheet-format file (latin-1, no header)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(n_rows):
        day = 1 + i
        lines.append(
            f"202404{day:02d},0,Mon,BOS,AL,1,NYY,AL,1,{3+i},{5+i}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="latin-1")


def _gate_json_without_generated_at(gate_path: Path) -> dict:
    """Load gate JSON and remove non-deterministic keys (timestamps and absolute paths)."""
    data = json.loads(gate_path.read_text())
    data.pop("generated_at", None)
    data.pop("artifacts", None)    # absolute paths differ per output_dir
    data.pop("source_path", None)  # absolute path differs per tmp dir
    return data


# ---------------------------------------------------------------------------
# BLOCKED: source file missing
# ---------------------------------------------------------------------------


class TestCLIBlockedSourceMissing:
    def test_exit_code_1_when_source_missing(self, tmp_path: Path) -> None:
        result = _run_cli(
            source_path=str(tmp_path / "nonexistent_gl2024.txt"),
            output_dir=str(tmp_path / "output"),
        )
        assert result.returncode == 1, (
            f"Expected exit 1 (BLOCKED), got {result.returncode}. "
            f"stdout: {result.stdout[:500]}"
        )

    def test_gate_json_written_when_source_missing(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        _run_cli(
            source_path=str(tmp_path / "nonexistent_gl2024.txt"),
            output_dir=str(output_dir),
        )
        gate_json = output_dir / "p32_gate_result.json"
        assert gate_json.exists(), "gate_result.json must be written even if source is missing"

    def test_gate_is_blocked_source_file_missing(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        _run_cli(
            source_path=str(tmp_path / "nonexistent_gl2024.txt"),
            output_dir=str(output_dir),
        )
        gate_json = output_dir / "p32_gate_result.json"
        data = json.loads(gate_json.read_text())
        assert data["gate"] == "P32_BLOCKED_SOURCE_FILE_MISSING", data

    def test_no_production_ready_true_in_gate_json(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        _run_cli(
            source_path=str(tmp_path / "nonexistent_gl2024.txt"),
            output_dir=str(output_dir),
        )
        gate_json = output_dir / "p32_gate_result.json"
        data = json.loads(gate_json.read_text())
        assert data.get("production_ready") is not True

    def test_report_written_when_source_missing(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        _run_cli(
            source_path=str(tmp_path / "nonexistent_gl2024.txt"),
            output_dir=str(output_dir),
        )
        # Report is always written at the fixed path inside repo
        report_path = REPO_ROOT / "00-BettingPlan" / "20260513" / "p32_raw_game_log_artifact_report.md"
        assert report_path.exists(), "Report must be written even when source is missing"

    def test_report_contains_blocked_marker(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        _run_cli(
            source_path=str(tmp_path / "nonexistent_gl2024.txt"),
            output_dir=str(output_dir),
        )
        report_path = REPO_ROOT / "00-BettingPlan" / "20260513" / "p32_raw_game_log_artifact_report.md"
        text = report_path.read_text()
        assert BLOCKED_MARKER in text, f"Expected marker '{BLOCKED_MARKER}' in report"

    def test_paper_only_true_in_gate_json(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        _run_cli(
            source_path=str(tmp_path / "nonexistent_gl2024.txt"),
            output_dir=str(output_dir),
        )
        gate_json = output_dir / "p32_gate_result.json"
        data = json.loads(gate_json.read_text())
        assert data.get("paper_only") is True


# ---------------------------------------------------------------------------
# DETERMINISM: run twice with missing source, compare outputs
# ---------------------------------------------------------------------------


class TestCLIDeterminism:
    def test_gate_json_deterministic_across_two_runs(self, tmp_path: Path) -> None:
        """Run CLI twice with missing source; gate_result.json must be identical."""
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        missing = tmp_path / "nonexistent_gl2024.txt"

        _run_cli(source_path=str(missing), output_dir=str(out1))
        _run_cli(source_path=str(missing), output_dir=str(out2))

        d1 = _gate_json_without_generated_at(out1 / "p32_gate_result.json")
        d2 = _gate_json_without_generated_at(out2 / "p32_gate_result.json")

        assert d1 == d2, f"Non-deterministic: run1={d1}, run2={d2}"

    def test_gate_always_blocked_when_missing(self, tmp_path: Path) -> None:
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        missing = tmp_path / "nonexistent_gl2024.txt"

        _run_cli(source_path=str(missing), output_dir=str(out1))
        _run_cli(source_path=str(missing), output_dir=str(out2))

        for run in [out1, out2]:
            data = json.loads((run / "p32_gate_result.json").read_text())
            assert data["gate"] == "P32_BLOCKED_SOURCE_FILE_MISSING"


# ---------------------------------------------------------------------------
# READY: source fixture exists
# ---------------------------------------------------------------------------


class TestCLIWithFixtureSource:
    def test_exit_code_0_with_valid_source(self, tmp_path: Path) -> None:
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        result = _run_cli(
            source_path=str(source),
            output_dir=str(output_dir),
        )
        assert result.returncode == 0, (
            f"Expected exit 0 (READY), got {result.returncode}. "
            f"stdout: {result.stdout[:1000]}\nstderr: {result.stderr[:500]}"
        )

    def test_gate_is_ready_with_valid_source(self, tmp_path: Path) -> None:
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        _run_cli(source_path=str(source), output_dir=str(output_dir))
        gate_json = output_dir / "p32_gate_result.json"
        assert gate_json.exists()
        data = json.loads(gate_json.read_text())
        assert data["gate"] == "P32_RAW_GAME_LOG_ARTIFACT_READY"

    def test_identity_artifact_written(self, tmp_path: Path) -> None:
        from wbc_backend.recommendation.p32_raw_game_artifact_writer import IDENTITY_FILENAME
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        _run_cli(source_path=str(source), output_dir=str(output_dir))
        assert (output_dir / IDENTITY_FILENAME).exists()

    def test_outcomes_artifact_written(self, tmp_path: Path) -> None:
        from wbc_backend.recommendation.p32_raw_game_artifact_writer import OUTCOMES_FILENAME
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        _run_cli(source_path=str(source), output_dir=str(output_dir))
        assert (output_dir / OUTCOMES_FILENAME).exists()

    def test_joined_artifact_written(self, tmp_path: Path) -> None:
        from wbc_backend.recommendation.p32_raw_game_artifact_writer import JOINED_FILENAME
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        _run_cli(source_path=str(source), output_dir=str(output_dir))
        assert (output_dir / JOINED_FILENAME).exists()

    def test_provenance_json_written(self, tmp_path: Path) -> None:
        from wbc_backend.recommendation.p32_provenance_attribution import PROVENANCE_FILENAME
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        _run_cli(source_path=str(source), output_dir=str(output_dir))
        assert (output_dir / PROVENANCE_FILENAME).exists()

    def test_manifest_json_written(self, tmp_path: Path) -> None:
        from wbc_backend.recommendation.p32_raw_game_artifact_writer import MANIFEST_FILENAME
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        _run_cli(source_path=str(source), output_dir=str(output_dir))
        assert (output_dir / MANIFEST_FILENAME).exists()

    def test_no_odds_in_identity_artifact(self, tmp_path: Path) -> None:
        from wbc_backend.recommendation.p32_raw_game_artifact_writer import (
            IDENTITY_FILENAME,
            BLOCKED_COLUMNS,
        )
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        _run_cli(source_path=str(source), output_dir=str(output_dir))
        df = pd.read_csv(output_dir / IDENTITY_FILENAME)
        for col in BLOCKED_COLUMNS:
            assert col not in df.columns, f"Blocked column '{col}' found in identity artifact"

    def test_no_predictions_in_outcomes_artifact(self, tmp_path: Path) -> None:
        from wbc_backend.recommendation.p32_raw_game_artifact_writer import (
            OUTCOMES_FILENAME,
            BLOCKED_COLUMNS,
        )
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        _run_cli(source_path=str(source), output_dir=str(output_dir))
        df = pd.read_csv(output_dir / OUTCOMES_FILENAME)
        for col in BLOCKED_COLUMNS:
            assert col not in df.columns, f"Blocked column '{col}' found in outcomes artifact"

    def test_report_contains_ready_marker(self, tmp_path: Path) -> None:
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        output_dir = tmp_path / "output"
        _run_cli(source_path=str(source), output_dir=str(output_dir))
        report_path = REPO_ROOT / "00-BettingPlan" / "20260513" / "p32_raw_game_log_artifact_report.md"
        text = report_path.read_text()
        assert READY_MARKER in text

    def test_determinism_with_fixture_source(self, tmp_path: Path) -> None:
        """Run CLI twice with fixture source; gate_result.json must match (excl. generated_at)."""
        source = tmp_path / "gl2024.txt"
        _make_minimal_retrosheet_file(source, n_rows=10)
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        _run_cli(source_path=str(source), output_dir=str(out1))
        _run_cli(source_path=str(source), output_dir=str(out2))

        d1 = _gate_json_without_generated_at(out1 / "p32_gate_result.json")
        d2 = _gate_json_without_generated_at(out2 / "p32_gate_result.json")

        assert d1 == d2, f"Non-deterministic gate result: run1={d1}, run2={d2}"


# ---------------------------------------------------------------------------
# Regression: paper-only guard
# ---------------------------------------------------------------------------


class TestCLIPaperOnlyGuard:
    def test_paper_only_false_exits_nonzero(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [PYTHON, CLI,
             "--source-path", str(tmp_path / "missing.txt"),
             "--output-dir", str(tmp_path / "out"),
             "--season", "2024",
             "--paper-only", "false"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode != 0

    def test_wrong_season_exits_nonzero(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [PYTHON, CLI,
             "--source-path", str(tmp_path / "missing.txt"),
             "--output-dir", str(tmp_path / "out"),
             "--season", "2025",
             "--paper-only", "true"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode != 0
