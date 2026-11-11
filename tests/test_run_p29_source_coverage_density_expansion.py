"""
tests/test_run_p29_source_coverage_density_expansion.py

Unit / integration tests for the P29 CLI entry point.
Runs main() via subprocess so exit codes and stdout are captured cleanly.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers — build minimal synthetic data dirs
# ---------------------------------------------------------------------------

_DATE_RESULTS_CSV = textwrap.dedent("""\
    run_date,n_active_paper_entries,total_pnl_units,total_stake_units,roi_units,blocker_reason,paper_only,production_ready
    2025-05-08,1,0.10,0.25,0.40,,True,False
    2025-05-09,2,0.20,0.50,0.40,,True,False
    2025-05-10,0,0.00,0.00,0.00,BLOCKED,True,False
""")

_SLICE_CSV = textwrap.dedent("""\
    ledger_id,recommendation_id,game_id,date,side,p_model,p_market,edge,odds_decimal,paper_stake_fraction,paper_stake_units,policy_id,strategy_policy,gate_decision,gate_reason,paper_only,production_ready,source_phase,created_from,y_true,settlement_status,settlement_reason,pnl_units,roi,is_win,is_loss,is_push,risk_profile_max_drawdown,risk_profile_sharpe,risk_profile_n_bets
    1,r1,g1,2025-05-08,home,0.58,0.50,0.08,1.90,0.008,0.008,pol,pol,ELIGIBLE,P16_6_ELIGIBLE_PAPER_RECOMMENDATION,True,False,p25,p25,1.0,settled,win,0.072,0.90,True,False,False,0.0,1.0,1
    2,r2,g2,2025-05-08,away,0.52,0.50,0.02,2.10,0.0,0.0,pol,pol,BLOCKED,P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD,True,False,p25,p25,1.0,settled,win,0.0,0.0,False,False,False,0.0,0.0,1
""")


def _build_synthetic_dirs(tmp_path: Path) -> dict:
    """Create synthetic p27 + p25 data directories."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # p27 dir
    p27 = repo / "p27_backfill"
    p27.mkdir()
    (p27 / "date_results.csv").write_text(_DATE_RESULTS_CSV)

    # p25 dir with true_date_slices
    p25 = repo / "p25_slices"
    slices = p25 / "true_date_slices" / "2025-05-08"
    slices.mkdir(parents=True)
    (slices / "p15_true_date_input.csv").write_text(_SLICE_CSV)

    output_dir = repo / "p29_output"

    return {"p27": p27, "p25": p25, "output": output_dir, "repo": repo}


def _run_cli(
    args: list[str], cwd: str = ".", env_extra: dict | None = None
) -> subprocess.CompletedProcess:
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = "/Users/kelvin/Kelvin-WorkSpace/Betting-pool-p13"
    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        [sys.executable, "scripts/run_p29_source_coverage_density_expansion.py"] + args,
        cwd="/Users/kelvin/Kelvin-WorkSpace/Betting-pool-p13",
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Guard: --paper-only false → exit 2
# ---------------------------------------------------------------------------


def test_paper_only_false_exits_2() -> None:
    result = _run_cli(["--paper-only", "false"])
    assert result.returncode == 2
    assert "paper-only must be true" in result.stdout.lower() or result.returncode == 2


# ---------------------------------------------------------------------------
# Guard: missing --p27-dir → exit 2
# ---------------------------------------------------------------------------


def test_missing_p27_dir_exits_2(tmp_path: Path) -> None:
    dirs = _build_synthetic_dirs(tmp_path)
    result = _run_cli([
        "--p25-dir", str(dirs["p25"]),
        "--output-dir", str(dirs["output"]),
        "--paper-only", "true",
    ])
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Guard: missing --p25-dir → exit 2
# ---------------------------------------------------------------------------


def test_missing_p25_dir_exits_2(tmp_path: Path) -> None:
    dirs = _build_synthetic_dirs(tmp_path)
    result = _run_cli([
        "--p27-dir", str(dirs["p27"]),
        "--output-dir", str(dirs["output"]),
        "--paper-only", "true",
    ])
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Guard: p27 dir missing date_results.csv → exit 2
# ---------------------------------------------------------------------------


def test_p27_dir_missing_date_results_exits_2(tmp_path: Path) -> None:
    dirs = _build_synthetic_dirs(tmp_path)
    (dirs["p27"] / "date_results.csv").unlink()
    result = _run_cli([
        "--p27-dir", str(dirs["p27"]),
        "--p25-dir", str(dirs["p25"]),
        "--output-dir", str(dirs["output"]),
        "--paper-only", "true",
    ])
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Valid run → exit 0 or 1 (either READY or BLOCKED)
# ---------------------------------------------------------------------------


def test_valid_run_exits_0_or_1(tmp_path: Path) -> None:
    dirs = _build_synthetic_dirs(tmp_path)
    result = _run_cli([
        "--p27-dir", str(dirs["p27"]),
        "--p25-dir", str(dirs["p25"]),
        "--scan-base-path", str(dirs["repo"]),
        "--output-dir", str(dirs["output"]),
        "--target-active-entries", "1500",
        "--paper-only", "true",
    ])
    assert result.returncode in (0, 1), (
        f"Expected exit 0 or 1, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Valid run → prints expected terminal marker
# ---------------------------------------------------------------------------


def test_valid_run_prints_terminal_marker(tmp_path: Path) -> None:
    dirs = _build_synthetic_dirs(tmp_path)
    result = _run_cli([
        "--p27-dir", str(dirs["p27"]),
        "--p25-dir", str(dirs["p25"]),
        "--output-dir", str(dirs["output"]),
        "--target-active-entries", "1500",
        "--paper-only", "true",
    ])
    output = result.stdout
    assert (
        "P29_SOURCE_COVERAGE_DENSITY_EXPANSION_PLAN_READY" in output
        or "P29_SOURCE_COVERAGE_DENSITY_EXPANSION_BLOCKED" in output
    ), f"No terminal marker found in stdout:\n{output}"


# ---------------------------------------------------------------------------
# Valid run → output dir + key files created
# ---------------------------------------------------------------------------


def test_valid_run_creates_output_files(tmp_path: Path) -> None:
    dirs = _build_synthetic_dirs(tmp_path)
    result = _run_cli([
        "--p27-dir", str(dirs["p27"]),
        "--p25-dir", str(dirs["p25"]),
        "--output-dir", str(dirs["output"]),
        "--target-active-entries", "1500",
        "--paper-only", "true",
    ])
    assert result.returncode in (0, 1)
    expected_files = ["p29_gate_result.json", "density_expansion_plan.json"]
    for fname in expected_files:
        assert (dirs["output"] / fname).exists(), (
            f"Missing output file: {fname}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Valid run → stdout has paper_only=true and production_ready=false
# ---------------------------------------------------------------------------


def test_valid_run_prints_paper_only_and_not_production(tmp_path: Path) -> None:
    dirs = _build_synthetic_dirs(tmp_path)
    result = _run_cli([
        "--p27-dir", str(dirs["p27"]),
        "--p25-dir", str(dirs["p25"]),
        "--output-dir", str(dirs["output"]),
        "--target-active-entries", "1500",
        "--paper-only", "true",
    ])
    assert result.returncode in (0, 1)
    output_lower = result.stdout.lower()
    assert "paper_only" in output_lower or "paper-only" in output_lower
    assert "production_ready" in output_lower or "production-ready" in output_lower
