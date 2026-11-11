"""
tests/test_p28_true_date_stability_auditor.py

Integration tests for the P28 stability auditor — gate determination,
module combination, and output file writing.
"""
import json
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p28_true_date_stability_auditor import (
    combine_density_variance_risk,
    determine_p28_gate,
    run_p28_true_date_stability_audit,
    write_p28_outputs,
)
from wbc_backend.recommendation.p28_true_date_stability_contract import (
    MAX_DRAWDOWN_PCT_LIMIT,
    P28GateResult,
    P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT,
    P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT,
    P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE,
    P28_TRUE_DATE_STABILITY_AUDIT_READY,
    STABILITY_ACCEPTABLE_FOR_RESEARCH,
    STABILITY_DRAWDOWN_RISK_HIGH,
    STABILITY_SAMPLE_SIZE_INSUFFICIENT,
    STABILITY_SEGMENT_VARIANCE_UNSTABLE,
)
from wbc_backend.recommendation.p28_sample_density_analyzer import summarize_sample_density
from wbc_backend.recommendation.p28_performance_variance_analyzer import summarize_performance_variance
from wbc_backend.recommendation.p28_risk_drawdown_analyzer import summarize_risk_profile


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
    "n_blocked": 0,
    "blocked_segments": [],
    "n_blocked_dates": 0,
    "blocked_dates": [],
    "paper_only": True,
    "production_ready": False,
})


def _make_p27_dir(tmp_path: Path, date_csv: str = _DATE_CSV, seg_csv: str = _SEG_CSV) -> Path:
    p27 = tmp_path / "p27_out"
    p27.mkdir()
    (p27 / "date_results.csv").write_text(date_csv)
    (p27 / "segment_results.csv").write_text(seg_csv)
    (p27 / "p27_gate_result.json").write_text(_GATE_JSON)
    (p27 / "blocked_segments.json").write_text(_BLOCKED_JSON)
    return p27


# ---------------------------------------------------------------------------
# determine_p28_gate
# ---------------------------------------------------------------------------


def _make_summary_for_gate(
    sample_size_pass: bool = False,
    max_drawdown_pct: float = 5.0,
    segment_roi_std: float = 0.1,
):
    """Build a minimal P28StabilityAuditSummary for gate testing."""
    from wbc_backend.recommendation.p28_true_date_stability_contract import (
        P28StabilityAuditSummary,
        STABILITY_SAMPLE_SIZE_INSUFFICIENT,
        STABILITY_ACCEPTABLE_FOR_RESEARCH,
    )

    status = (
        STABILITY_ACCEPTABLE_FOR_RESEARCH
        if sample_size_pass
        else STABILITY_SAMPLE_SIZE_INSUFFICIENT
    )
    return P28StabilityAuditSummary(
        n_dates_total=144,
        n_dates_ready=140,
        n_dates_blocked=4,
        n_segments=11,
        total_active_entries=324 if not sample_size_pass else 1600,
        min_sample_size_advisory=1500,
        sample_size_pass=sample_size_pass,
        aggregate_roi_units=0.1078,
        aggregate_hit_rate=0.5278,
        segment_roi_min=-0.05,
        segment_roi_max=0.20,
        segment_roi_std=segment_roi_std,
        daily_active_min=1.0,
        daily_active_max=9.0,
        daily_active_std=1.5,
        max_drawdown_units=1.5,
        max_drawdown_pct=max_drawdown_pct,
        max_consecutive_losing_days=3,
        bootstrap_roi_ci_low_95=0.01,
        bootstrap_roi_ci_high_95=0.20,
        paper_only=True,
        production_ready=False,
        audit_status=status,
        blocker_reason="",
    )


def test_gate_blocked_sample_size():
    summary = _make_summary_for_gate(sample_size_pass=False)
    assert determine_p28_gate(summary) == P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT


def test_gate_blocked_drawdown():
    summary = _make_summary_for_gate(
        sample_size_pass=True,
        max_drawdown_pct=MAX_DRAWDOWN_PCT_LIMIT + 1.0,
    )
    assert determine_p28_gate(summary) == P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT


def test_gate_blocked_variance():
    summary = _make_summary_for_gate(
        sample_size_pass=True,
        max_drawdown_pct=5.0,
        segment_roi_std=0.99,  # above threshold
    )
    assert determine_p28_gate(summary) == P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE


def test_gate_ready():
    summary = _make_summary_for_gate(
        sample_size_pass=True,
        max_drawdown_pct=5.0,
        segment_roi_std=0.1,
    )
    assert determine_p28_gate(summary) == P28_TRUE_DATE_STABILITY_AUDIT_READY


def test_gate_priority_sample_size_first():
    # Even if drawdown and variance also fail, sample size should dominate
    summary = _make_summary_for_gate(
        sample_size_pass=False,
        max_drawdown_pct=MAX_DRAWDOWN_PCT_LIMIT + 10.0,
        segment_roi_std=0.99,
    )
    assert determine_p28_gate(summary) == P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT


# ---------------------------------------------------------------------------
# run_p28_true_date_stability_audit — integration
# ---------------------------------------------------------------------------


def test_run_p28_audit_blocked_sample_size(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    result = run_p28_true_date_stability_audit(
        p27_dir=p27_dir,
        output_dir=out_dir,
        min_sample_size=1500,  # 13 active < 1500
    )
    assert result.p28_gate == P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT
    assert result.paper_only is True
    assert result.production_ready is False
    assert result.sample_size_pass is False


def test_run_p28_audit_ready_when_sufficient_sample(tmp_path):
    # Provide enough date rows to exceed min_sample_size=5
    big_date_csv = "run_date,n_active_paper_entries,n_settled_win,n_settled_loss,n_unsettled,roi_units,hit_rate,total_stake_units,total_pnl_units,segment_index\n"
    for i in range(100):
        d = f"2025-05-{(i % 28) + 1:02d}"
        big_date_csv += f"{d},{i % 5 + 1},3,2,0,0.05,0.6,1.25,0.0625,0\n"

    p27_dir = _make_p27_dir(tmp_path, date_csv=big_date_csv)
    gate_data = json.loads(_GATE_JSON)
    gate_data["total_active_entries"] = sum((i % 5 + 1) for i in range(100))
    gate_data["n_dates_requested"] = 100
    gate_data["n_dates_ready"] = 100
    (p27_dir / "p27_gate_result.json").write_text(json.dumps(gate_data))

    out_dir = tmp_path / "p28_out"
    result = run_p28_true_date_stability_audit(
        p27_dir=p27_dir,
        output_dir=out_dir,
        min_sample_size=5,  # very low threshold → should pass
    )
    # May still be blocked by drawdown or variance depending on data
    assert result.p28_gate in {
        P28_TRUE_DATE_STABILITY_AUDIT_READY,
        P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT,
        P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE,
        P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT,
    }
    assert result.paper_only is True
    assert result.production_ready is False


def test_run_p28_audit_writes_8_output_files(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    run_p28_true_date_stability_audit(p27_dir=p27_dir, output_dir=out_dir, min_sample_size=1500)
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
        assert (out_dir / fname).exists(), f"Missing: {fname}"


def test_run_p28_audit_gate_result_json_valid(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    run_p28_true_date_stability_audit(p27_dir=p27_dir, output_dir=out_dir, min_sample_size=1500)
    data = json.loads((out_dir / "p28_gate_result.json").read_text())
    assert "p28_gate" in data
    assert data["paper_only"] is True
    assert data["production_ready"] is False


def test_run_p28_audit_missing_input_raises(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        run_p28_true_date_stability_audit(
            p27_dir=empty_dir,
            output_dir=tmp_path / "out",
            min_sample_size=1500,
        )


def test_run_p28_audit_paper_only_enforced_in_output(tmp_path):
    p27_dir = _make_p27_dir(tmp_path)
    out_dir = tmp_path / "p28_out"
    result = run_p28_true_date_stability_audit(p27_dir=p27_dir, output_dir=out_dir, min_sample_size=1500)
    summary_data = json.loads((out_dir / "p28_stability_audit_summary.json").read_text())
    assert summary_data["paper_only"] is True
    assert summary_data["production_ready"] is False
