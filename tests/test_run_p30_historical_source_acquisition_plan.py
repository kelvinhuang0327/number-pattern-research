"""
tests/test_run_p30_historical_source_acquisition_plan.py

Integration tests for the P30 CLI script.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = "scripts/run_p30_historical_source_acquisition_plan.py"
REPO_ROOT = Path(__file__).parent.parent


def _run_cli(*extra_args, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    """Run the P30 CLI and return the completed process."""
    cmd = [
        sys.executable, str(REPO_ROOT / SCRIPT),
        "--paper-only", "true",
        *extra_args,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
    )


def _find_p29_plan() -> str:
    """Find the existing P29 gate result for use as --p29-plan."""
    p = (
        REPO_ROOT
        / "outputs/predictions/PAPER/backfill"
        / "p29_source_coverage_density_expansion_2025-05-08_2025-09-28"
        / "p29_gate_result.json"
    )
    if p.exists():
        return str(p)
    # Fallback: create a minimal P29 plan JSON in tmp
    return ""


# ---------------------------------------------------------------------------
# Validation failures (exit code 2)
# ---------------------------------------------------------------------------


def test_paper_only_false_exits_2(tmp_path):
    p29 = _find_p29_plan()
    result = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / SCRIPT),
            "--target-season", "2024",
            "--paper-only", "false",
            "--p29-plan", p29 or str(tmp_path / "dummy.json"),
            "--output-dir", str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 2
    assert "paper-only" in (result.stdout + result.stderr).lower() or "FAIL" in (result.stdout + result.stderr)


def test_missing_target_season_exits_2(tmp_path):
    p29 = _find_p29_plan() or str(tmp_path / "dummy.json")
    (tmp_path / "dummy.json").write_text('{"p29_gate": "P29_BLOCKED"}')
    result = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / SCRIPT),
            "--paper-only", "true",
            "--p29-plan", p29,
            "--output-dir", str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 2


def test_missing_p29_plan_arg_exits_2(tmp_path):
    result = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / SCRIPT),
            "--target-season", "2024",
            "--paper-only", "true",
            "--output-dir", str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Valid run (exit code 0 or 1)
# ---------------------------------------------------------------------------


@pytest.fixture
def p30_valid_run(tmp_path):
    """Run the CLI against a minimal temp dir and return the result."""
    # Write a minimal P29 gate result
    p29_path = tmp_path / "p29_gate_result.json"
    p29_path.write_text(
        json.dumps({
            "p29_gate": "P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT",
            "paper_only": True,
            "production_ready": False,
        }),
        encoding="utf-8",
    )

    # Write a minimal identity CSV source in data dir
    data_dir = tmp_path / "data" / "mlb_2024"
    data_dir.mkdir(parents=True)
    csv_path = data_dir / "test_identity.csv"
    csv_path.write_text(
        "Date,Away,Home,Away ML,Home ML\n2024-04-01,TeamA,TeamB,-150,+125\n" * 20,
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / SCRIPT),
            "--target-season", "2024",
            "--scan-base-path", str(tmp_path / "data"),
            "--paper-only", "true",
            "--p29-plan", str(p29_path),
            "--output-dir", str(out_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    return result, out_dir


def test_valid_run_exits_0_or_1(p30_valid_run):
    result, _ = p30_valid_run
    assert result.returncode in (0, 1), (
        f"Expected exit 0 or 1, got {result.returncode}\n"
        f"stdout: {result.stdout[:1000]}\nstderr: {result.stderr[:1000]}"
    )


def test_valid_run_prints_terminal_marker(p30_valid_run):
    result, _ = p30_valid_run
    combined = result.stdout + result.stderr
    assert (
        "P30_HISTORICAL_SOURCE_ACQUISITION_PLAN_READY" in combined
        or "P30_HISTORICAL_SOURCE_ACQUISITION_PLAN_BLOCKED" in combined
    ), f"No terminal marker found in output:\n{combined[:2000]}"


def test_valid_run_prints_paper_only_true(p30_valid_run):
    result, _ = p30_valid_run
    assert "paper_only" in result.stdout.lower()
    assert "true" in result.stdout.lower()


def test_valid_run_prints_production_ready_false(p30_valid_run):
    result, _ = p30_valid_run
    assert "production_ready" in result.stdout.lower()
    assert "false" in result.stdout.lower()


def test_valid_run_creates_gate_result_json(p30_valid_run):
    _, out_dir = p30_valid_run
    gate_file = out_dir / "p30_gate_result.json"
    assert gate_file.exists(), f"p30_gate_result.json not found in {out_dir}"


def test_valid_run_creates_source_inventory_json(p30_valid_run):
    _, out_dir = p30_valid_run
    assert (out_dir / "source_inventory.json").exists()


def test_valid_run_creates_source_inventory_md(p30_valid_run):
    _, out_dir = p30_valid_run
    assert (out_dir / "source_inventory.md").exists()


def test_valid_run_creates_required_artifact_specs_json(p30_valid_run):
    _, out_dir = p30_valid_run
    assert (out_dir / "required_artifact_specs.json").exists()


def test_valid_run_creates_schema_gap_report_json(p30_valid_run):
    _, out_dir = p30_valid_run
    assert (out_dir / "schema_gap_report.json").exists()


def test_valid_run_creates_source_acquisition_plan_json(p30_valid_run):
    _, out_dir = p30_valid_run
    assert (out_dir / "source_acquisition_plan.json").exists()


def test_valid_run_creates_source_acquisition_plan_md(p30_valid_run):
    _, out_dir = p30_valid_run
    assert (out_dir / "source_acquisition_plan.md").exists()


def test_valid_run_creates_dry_run_preview_summary_json(p30_valid_run):
    _, out_dir = p30_valid_run
    assert (out_dir / "dry_run_preview_summary.json").exists()


def test_valid_run_all_8_output_files_present(p30_valid_run):
    """Verify all 8 required output files are created."""
    _, out_dir = p30_valid_run
    expected = [
        "source_inventory.json",
        "source_inventory.md",
        "required_artifact_specs.json",
        "schema_gap_report.json",
        "source_acquisition_plan.json",
        "source_acquisition_plan.md",
        "dry_run_preview_summary.json",
        "p30_gate_result.json",
    ]
    for fname in expected:
        assert (out_dir / fname).exists(), f"Missing output file: {fname}"


def test_valid_run_gate_result_json_has_paper_only(p30_valid_run):
    _, out_dir = p30_valid_run
    data = json.loads((out_dir / "p30_gate_result.json").read_text())
    assert data.get("paper_only") is True
    assert data.get("production_ready") is False


def test_valid_run_gate_result_json_has_p30_gate(p30_valid_run):
    _, out_dir = p30_valid_run
    data = json.loads((out_dir / "p30_gate_result.json").read_text())
    assert "p30_gate" in data
    assert data["p30_gate"].startswith("P30_")


# ---------------------------------------------------------------------------
# Determinism check
# ---------------------------------------------------------------------------


def test_two_runs_produce_same_p30_gate(tmp_path):
    """Two independent runs on the same inputs must produce the same p30_gate."""
    p29_path = tmp_path / "p29_gate_result.json"
    p29_path.write_text(
        json.dumps({
            "p29_gate": "P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT",
            "paper_only": True,
            "production_ready": False,
        }),
        encoding="utf-8",
    )

    data_dir = tmp_path / "data" / "mlb_2024"
    data_dir.mkdir(parents=True)
    csv_path = data_dir / "test.csv"
    csv_path.write_text(
        "Date,Away,Home,Away ML,Home ML\n" + "2024-04-01,A,B,-150,+125\n" * 20,
        encoding="utf-8",
    )

    def _do_run(run_id: str) -> dict:
        out = tmp_path / f"det_run{run_id}"
        r = subprocess.run(
            [
                sys.executable, str(REPO_ROOT / SCRIPT),
                "--target-season", "2024",
                "--scan-base-path", str(tmp_path / "data"),
                "--paper-only", "true",
                "--p29-plan", str(p29_path),
                "--output-dir", str(out),
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
        )
        gate_file = out / "p30_gate_result.json"
        assert gate_file.exists(), f"gate result missing on run {run_id}"
        return json.loads(gate_file.read_text())

    run1 = _do_run("1")
    run2 = _do_run("2")

    assert run1["p30_gate"] == run2["p30_gate"], (
        f"Non-deterministic gate: run1={run1['p30_gate']}, run2={run2['p30_gate']}"
    )
    assert run1["n_source_candidates"] == run2["n_source_candidates"]
    assert run1["schema_gap_count"] == run2["schema_gap_count"]
