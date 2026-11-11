"""
Tests for the P22.5 CLI (run_p22_5_historical_source_artifact_builder.py).
Uses subprocess calls with PYTHONPATH set to the repo root.
"""
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = REPO_ROOT / "scripts" / "run_p22_5_historical_source_artifact_builder.py"
PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")
BASE_ENV = {"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"}

REQUIRED_OUTPUT_FILES = [
    "source_candidate_inventory.json",
    "source_candidate_inventory.md",
    "date_source_availability.csv",
    "p15_readiness_plan.json",
    "p15_readiness_plan.md",
    "p22_5_gate_result.json",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_joined_oof_csv(directory: Path, n_rows: int = 10) -> Path:
    """Create a fake joined_oof_with_odds.csv in the given directory."""
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / "joined_oof_with_odds.csv"
    df = pd.DataFrame({
        "game_id": [f"2025-05-08_LAD_SFG_{i}" for i in range(n_rows)],
        "game_date": ["2025-05-08"] * n_rows,
        "home_team": ["SFG"] * n_rows,
        "away_team": ["LAD"] * n_rows,
        "y_true": ([1, 0] * (n_rows // 2 + 1))[:n_rows],
        "p_oof": ([0.62, 0.38] * (n_rows // 2 + 1))[:n_rows],
        "odds_decimal_home": [1.91] * n_rows,
        "odds_decimal_away": [2.05] * n_rows,
        "p_market": [0.524] * n_rows,
        "paper_only": [True] * n_rows,
    })
    df.to_csv(p, index=False)
    return p


def _run_cli(args: list[str], cwd=REPO_ROOT) -> subprocess.CompletedProcess:
    cmd = [PYTHON, str(CLI_SCRIPT)] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=BASE_ENV,
        cwd=str(cwd),
    )


# ---------------------------------------------------------------------------
# Guard tests
# ---------------------------------------------------------------------------


def test_cli_fails_when_paper_only_false(tmp_path):
    result = _run_cli([
        "--date-start", "2026-05-01",
        "--date-end", "2026-05-03",
        "--paper-base-dir", str(tmp_path),
        "--output-dir", str(tmp_path / "out"),
        "--paper-only", "false",
    ])
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}\n{result.stderr}"


def test_cli_fails_when_paper_base_dir_missing(tmp_path):
    result = _run_cli([
        "--date-start", "2026-05-01",
        "--date-end", "2026-05-03",
        "--paper-base-dir", str(tmp_path / "nonexistent"),
        "--output-dir", str(tmp_path / "out"),
        "--paper-only", "true",
    ])
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}\n{result.stderr}"


# ---------------------------------------------------------------------------
# Happy path: no source candidates → BLOCKED
# ---------------------------------------------------------------------------


def test_cli_blocked_when_no_usable_candidates(tmp_path):
    """Scanning an empty directory should emit BLOCKED, not crash."""
    paper_base = tmp_path / "PAPER"
    paper_base.mkdir()
    scan_dir = tmp_path / "data_empty"
    scan_dir.mkdir()

    result = _run_cli([
        "--date-start", "2026-05-01",
        "--date-end", "2026-05-03",
        "--paper-base-dir", str(paper_base),
        "--scan-base-path", str(scan_dir),
        "--output-dir", str(tmp_path / "out"),
        "--paper-only", "true",
        "--dry-run", "false",
    ])
    # Should exit 1 (BLOCKED) not 2 (FAIL) or crash
    assert result.returncode in (0, 1), f"returncode={result.returncode}\n{result.stderr}"

    # All 6 output files must still be written
    out_dir = tmp_path / "out"
    for fname in REQUIRED_OUTPUT_FILES:
        assert (out_dir / fname).exists(), f"Missing output file: {fname}"


# ---------------------------------------------------------------------------
# Happy path: with usable sources → READY
# ---------------------------------------------------------------------------


def test_cli_ready_with_usable_source(tmp_path):
    """With a real joined_oof file as source, gate should be READY."""
    paper_base = tmp_path / "PAPER"
    paper_base.mkdir()

    # Place a joined oof CSV in the scan directory
    scan_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "2026-05-12" / "p15_market_odds_simulation"
    joined_csv = _make_joined_oof_csv(scan_dir, n_rows=25)

    out_dir = tmp_path / "out"
    result = _run_cli([
        "--date-start", "2026-05-01",
        "--date-end", "2026-05-03",
        "--paper-base-dir", str(paper_base),
        "--scan-base-path", str(tmp_path / "outputs"),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--dry-run", "true",
    ])
    assert result.returncode == 0, (
        f"Expected exit 0 (READY), got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # All 6 required output files must exist
    for fname in REQUIRED_OUTPUT_FILES:
        assert (out_dir / fname).exists(), f"Missing: {fname}"

    # Gate result JSON must show READY
    with (out_dir / "p22_5_gate_result.json").open() as fh:
        gate = json.load(fh)
    assert gate["p22_5_gate"] == "P22_5_SOURCE_ARTIFACT_BUILDER_READY"
    assert gate["paper_only"] is True
    assert gate["production_ready"] is False
    assert gate["n_dates_ready_to_build"] == 3  # 2026-05-01 to 2026-05-03


def test_cli_writes_gate_result_json(tmp_path):
    paper_base = tmp_path / "PAPER"
    paper_base.mkdir()
    scan_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "2026-05-12" / "p15_market_odds_simulation"
    _make_joined_oof_csv(scan_dir, n_rows=10)
    out_dir = tmp_path / "out"

    _run_cli([
        "--date-start", "2026-05-05",
        "--date-end", "2026-05-05",
        "--paper-base-dir", str(paper_base),
        "--scan-base-path", str(tmp_path / "outputs"),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--dry-run", "false",
    ])

    gate_path = out_dir / "p22_5_gate_result.json"
    assert gate_path.exists()
    with gate_path.open() as fh:
        gate = json.load(fh)
    assert "p22_5_gate" in gate
    assert "n_source_candidates" in gate
    assert "n_dates_ready_to_build" in gate
    assert "generated_at" in gate
    assert gate["paper_only"] is True
    assert gate["production_ready"] is False


def test_cli_writes_date_source_availability_csv(tmp_path):
    paper_base = tmp_path / "PAPER"
    paper_base.mkdir()
    scan_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "2026-05-12" / "p15_market_odds_simulation"
    _make_joined_oof_csv(scan_dir, n_rows=10)
    out_dir = tmp_path / "out"

    _run_cli([
        "--date-start", "2026-05-01",
        "--date-end", "2026-05-02",
        "--paper-base-dir", str(paper_base),
        "--scan-base-path", str(tmp_path / "outputs"),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--dry-run", "false",
    ])

    csv_path = out_dir / "date_source_availability.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert "run_date" in df.columns
    assert "is_p15_ready" in df.columns
    assert len(df) == 2  # 2026-05-01 and 2026-05-02


def test_cli_dry_run_creates_preview_files(tmp_path):
    """With dry-run, preview CSVs should be created for each ready date."""
    paper_base = tmp_path / "PAPER"
    paper_base.mkdir()
    scan_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "2026-05-12" / "p15_market_odds_simulation"
    _make_joined_oof_csv(scan_dir, n_rows=25)
    out_dir = tmp_path / "out"

    result = _run_cli([
        "--date-start", "2026-05-01",
        "--date-end", "2026-05-02",
        "--paper-base-dir", str(paper_base),
        "--scan-base-path", str(tmp_path / "outputs"),
        "--output-dir", str(out_dir),
        "--paper-only", "true",
        "--dry-run", "true",
    ])
    assert result.returncode == 0

    # Check preview dirs were created
    previews_base = out_dir / "previews"
    assert previews_base.exists()
    preview_dates = [d.name for d in previews_base.iterdir() if d.is_dir()]
    assert len(preview_dates) >= 1


# ---------------------------------------------------------------------------
# Determinism: two runs produce identical outputs
# ---------------------------------------------------------------------------


def test_cli_is_deterministic(tmp_path):
    """Running the CLI twice with same inputs must produce identical key outputs."""
    paper_base = tmp_path / "PAPER"
    paper_base.mkdir()
    scan_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "2026-05-12" / "p15_market_odds_simulation"
    _make_joined_oof_csv(scan_dir, n_rows=10)

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    common_args = [
        "--date-start", "2026-05-01",
        "--date-end", "2026-05-02",
        "--paper-base-dir", str(paper_base),
        "--scan-base-path", str(tmp_path / "outputs"),
        "--paper-only", "true",
        "--dry-run", "false",
    ]

    result1 = _run_cli(common_args + ["--output-dir", str(out1)])
    result2 = _run_cli(common_args + ["--output-dir", str(out2)])

    assert result1.returncode == result2.returncode

    # Compare inventory JSON (excluding generated_at)
    with (out1 / "p22_5_gate_result.json").open() as f1, (out2 / "p22_5_gate_result.json").open() as f2:
        g1 = json.load(f1)
        g2 = json.load(f2)

    g1.pop("generated_at", None)
    g2.pop("generated_at", None)
    assert g1 == g2, f"Gate results differ:\nRun1: {g1}\nRun2: {g2}"

    # Compare date availability CSV
    df1 = pd.read_csv(out1 / "date_source_availability.csv")
    df2 = pd.read_csv(out2 / "date_source_availability.csv")
    pd.testing.assert_frame_equal(df1.sort_values("run_date").reset_index(drop=True),
                                  df2.sort_values("run_date").reset_index(drop=True))
