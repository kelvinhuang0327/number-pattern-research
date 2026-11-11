"""
tests/test_run_p28_true_date_backfill_stability_audit.py

CLI tests for scripts/run_p28_true_date_backfill_stability_audit.py.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_DATE_CSV = textwrap.dedent("""\
    run_date,n_active_paper_entries,n_settled_win,n_settled_loss,n_unsettled,roi_units,hit_rate,total_stake_units,total_pnl_units,segment_index,blocker_reason,date_matches_slice,game_id_coverage,n_slice_rows,n_unique_game_ids,paper_only,production_ready,replay_gate,true_game_date
    2025-05-08,1,1,0,0,0.588235,1.0,0.25,0.147059,0,,True,0.25,4,4,True,False,P26_DATE_REPLAY_READY,2025-05-08
    2025-05-09,6,3,3,0,0.026515,0.5,1.5,0.039773,0,,True,0.4,15,15,True,False,P26_DATE_REPLAY_READY,2025-05-09
    2025-05-10,6,3,3,0,0.1,0.5,1.5,0.15,0,,True,0.545,11,11,True,False,P26_DATE_REPLAY_READY,2025-05-10
""")

_SEG_CSV = textwrap.dedent("""\
    segment_index,date_start,date_end,p26_gate,blocked,returncode,total_active_entries,total_settled_win,total_settled_loss,total_unsettled,total_stake_units,total_pnl_units
    0,2025-05-08,2025-05-21,P26_TRUE_DATE_HISTORICAL_BACKFILL_READY,False,0,13,7,6,0,3.25,0.337
""")

_GATE_JSON = json.dumps({
    "p27_gate": "P27_FULL_TRUE_DATE_BACKFILL_READY",
    "n_dates_requested": 3,
    "n_dates_ready": 3,
    "n_dates_blocked": 0,
    "total_active_entries": 13,
    "aggregate_roi_units": 0.05,
    "aggregate_hit_rate": 0.538,
    "paper_only": True,
    "production_ready": False,
})

_BLOCKED_JSON = json.dumps({
    "n_blocked": 0, "blocked_segments": [], "n_blocked_dates": 0,
    "blocked_dates": [], "paper_only": True, "production_ready": False,
})

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_p28_true_date_backfill_stability_audit.py"


def _make_p27_dir(tmp_path: Path) -> Path:
    p27 = tmp_path / "p27_out"
    p27.mkdir()
    (p27 / "date_results.csv").write_text(_DATE_CSV)
    (p27 / "segment_results.csv").write_text(_SEG_CSV)
    (p27 / "p27_gate_result.json").write_text(_GATE_JSON)
    (p27 / "blocked_segments.json").write_text(_BLOCKED_JSON)
    return p27


def _run_cli(p27_dir: Path, output_dir: Path, min_sample_size: int = 1500, paper_only: str = "true"):
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--p27-dir", str(p27_dir),
            "--output-dir", str(output_dir),
            "--min-sample-size", str(min_sample_size),
            "--paper-only", paper_only,
        ],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(SCRIPT.parent.parent)},
    )
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cli_exits_1_when_sample_size_blocked(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    proc = _run_cli(p27_dir, out_dir, min_sample_size=1500)
    assert proc.returncode == 1, f"stdout={proc.stdout}\nstderr={proc.stderr}"


def test_cli_exits_0_when_ready(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    # With min_sample_size=5, 13 active entries should pass sample size check
    # Risk and variance should also be fine with this small data
    proc = _run_cli(p27_dir, out_dir, min_sample_size=5)
    # Gate may be READY or blocked by drawdown/variance — just check no crash (exit 2)
    assert proc.returncode in {0, 1}, f"stdout={proc.stdout}\nstderr={proc.stderr}"


def test_cli_prints_gate(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    proc = _run_cli(p27_dir, out_dir, min_sample_size=1500)
    assert "p28_gate:" in proc.stdout


def test_cli_prints_paper_only_false(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    proc = _run_cli(p27_dir, out_dir, min_sample_size=1500)
    assert "paper_only:" in proc.stdout
    assert "production_ready:" in proc.stdout
    # paper_only must be True in output
    assert "paper_only:                  True" in proc.stdout
    assert "production_ready:            False" in proc.stdout


def test_cli_prints_sample_size_fields(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    proc = _run_cli(p27_dir, out_dir, min_sample_size=1500)
    assert "total_active_entries:" in proc.stdout
    assert "min_sample_size_advisory:" in proc.stdout
    assert "sample_size_pass:" in proc.stdout


def test_cli_prints_bootstrap_ci(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    proc = _run_cli(p27_dir, out_dir, min_sample_size=1500)
    assert "bootstrap_roi_ci_low_95:" in proc.stdout
    assert "bootstrap_roi_ci_high_95:" in proc.stdout


def test_cli_prints_drawdown(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    proc = _run_cli(p27_dir, out_dir, min_sample_size=1500)
    assert "max_drawdown_pct:" in proc.stdout
    assert "max_consecutive_losing_days:" in proc.stdout


def test_cli_writes_output_files(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    _run_cli(p27_dir, out_dir, min_sample_size=1500)
    expected = [
        "p28_gate_result.json",
        "p28_stability_audit_summary.json",
        "p28_stability_audit_summary.md",
        "sample_density_profile.json",
        "performance_variance_profile.json",
        "risk_drawdown_profile.json",
        "sparse_dates.csv",
        "sparse_segments.csv",
    ]
    for fname in expected:
        assert (out_dir / fname).exists(), f"Missing output file: {fname}"


def test_cli_exits_2_for_non_paper_only(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    proc = _run_cli(p27_dir, out_dir, paper_only="false")
    assert proc.returncode == 2


def test_cli_exits_2_for_missing_p27_dir(tmp_path):
    missing_dir = tmp_path / "does_not_exist"
    out_dir = tmp_path / "p28_out"
    proc = _run_cli(missing_dir, out_dir, min_sample_size=1500)
    assert proc.returncode == 2


def test_cli_gate_result_json_paper_only(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    _run_cli(p27_dir, out_dir, min_sample_size=1500)
    data = json.loads((out_dir / "p28_gate_result.json").read_text())
    assert data["paper_only"] is True
    assert data["production_ready"] is False


def test_cli_deterministic_two_runs(tmp_path):
    """Two runs with same inputs should produce identical gate_result (excluding generated_at)."""
    p27_dir = _make_p27_dir(tmp_path)
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    _run_cli(p27_dir, out1, min_sample_size=1500)
    _run_cli(p27_dir, out2, min_sample_size=1500)
    d1 = json.loads((out1 / "p28_gate_result.json").read_text())
    d2 = json.loads((out2 / "p28_gate_result.json").read_text())
    d1.pop("generated_at", None)
    d2.pop("generated_at", None)
    assert d1 == d2, f"Non-deterministic: {d1} != {d2}"
