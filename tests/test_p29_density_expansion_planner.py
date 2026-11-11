"""
tests/test_p29_density_expansion_planner.py

Unit tests for P29 density expansion planner — gate logic, plan building,
validation, and output file writer.
"""
import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from wbc_backend.recommendation.p29_density_expansion_contract import (
    DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE,
    DENSITY_EXPANSION_PLAN_FEASIBLE,
    DENSITY_EXPANSION_POLICY_PATH_RISKY,
    DENSITY_EXPANSION_SOURCE_PATH_FOUND,
    P29DensityDiagnosis,
    P29DensityExpansionGateResult,
    P29DensityExpansionPlan,
    P29PolicySensitivityCandidate,
    P29SourceCoverageCandidate,
    P29_BLOCKED_NO_SAFE_EXPANSION_PATH,
    P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
    P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT,
    P29_DENSITY_EXPANSION_PLAN_READY,
)
from wbc_backend.recommendation.p29_density_expansion_planner import (
    build_density_expansion_plan,
    build_gate_result,
    determine_p29_gate,
    validate_density_expansion_plan,
    write_p29_outputs,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_diagnosis(
    current: int = 324,
    target: int = 1500,
    n_blocked_edge: int = 907,
    n_blocked_odds: int = 344,
) -> P29DensityDiagnosis:
    return P29DensityDiagnosis(
        current_active_entries=current,
        target_active_entries=target,
        density_gap=max(0, target - current),
        current_active_per_day=2.25,
        target_active_per_day=10.71,
        total_source_rows=1577,
        active_conversion_rate=round(current / 1577, 4),
        n_blocked_edge=n_blocked_edge,
        n_blocked_odds=n_blocked_odds,
        n_blocked_unknown=2,
        n_dates_zero_active=5,
        n_dates_sparse_active=30,
        primary_blocker="edge_threshold",
        diagnosis_note="Test diagnosis",
        paper_only=True,
        production_ready=False,
    )


def _make_policy_candidate(n_active: int, has_risk: bool = True) -> P29PolicySensitivityCandidate:
    return P29PolicySensitivityCandidate(
        policy_id=f"e0p0200_s0p0025_k0p10_oinf_{n_active}",
        edge_threshold=0.02,
        odds_decimal_max=999.0,
        max_stake_cap=0.0025,
        kelly_fraction=0.10,
        n_active_entries=n_active,
        active_entry_lift_vs_current=n_active - 324,
        estimated_total_stake_units=2.5,
        hit_rate=0.52,
        roi_units=0.05,
        max_drawdown_pct=120.0 if has_risk else 10.0,
        gate_reason_counts="{}",
        risk_flags="LOW_EDGE_THRESHOLD,HIGH_DRAWDOWN" if has_risk else "",
        is_deployment_ready=False,
        exploratory_only=True,
        paper_only=True,
        production_ready=False,
    )


def _make_source_candidate(is_safe: bool = False, rows: int = 0) -> P29SourceCoverageCandidate:
    return P29SourceCoverageCandidate(
        source_path="/some/data.csv",
        source_type="additional_season",
        date_range_start="",
        date_range_end="",
        estimated_new_rows=rows,
        has_required_columns=is_safe,
        has_y_true=True,
        has_game_id=True,
        has_odds=True,
        coverage_note="Test candidate",
        is_safe_to_use=is_safe,
        paper_only=True,
        production_ready=False,
    )


def _make_source_summary(safe: int = 0, estimated_new: int = 0) -> Dict[str, Any]:
    return {
        "n_candidates_scanned": safe + 1,
        "n_candidates_safe": safe,
        "n_candidates_schema_compatible": 0,
        "total_estimated_new_rows_from_safe": estimated_new,
        "source_expansion_feasible": safe > 0,
        "recommendation": "Test recommendation",
    }


def _make_source_estimate(safe_rows: int = 0) -> Dict[str, Any]:
    return {
        "estimated_new_rows_safe": safe_rows,
        "estimated_new_active_entries_safe": int(safe_rows * 0.205),
        "estimated_new_rows_schema_compatible": 0,
        "estimated_new_active_entries_schema_compatible": 0,
        "conversion_rate_assumed": 0.205,
        "note": "Test estimate",
    }


# ---------------------------------------------------------------------------
# determine_p29_gate — via P29DensityExpansionPlan
# ---------------------------------------------------------------------------


def _make_plan_for_gate(
    n_source_safe: int,
    source_estimated: int,
    best_policy_active: int,
    audit_status: str,
    target: int = 1500,
) -> P29DensityExpansionPlan:
    return P29DensityExpansionPlan(
        current_active_entries=324,
        target_active_entries=target,
        density_gap=max(0, target - 324),
        current_active_per_day=2.25,
        target_active_per_day=10.71,
        available_true_date_rows=1577,
        current_policy_id="e0p0500_s0p0025_k0p10_o2p50",
        policy_thresholds_tested=32,
        best_policy_candidate_id="e0p0200_s0p0025_k0p10_oinf",
        best_policy_candidate_active_entries=best_policy_active,
        source_expansion_estimated_entries=source_estimated,
        n_source_candidates_found=n_source_safe,
        n_source_candidates_safe=n_source_safe,
        recommended_next_action="test",
        expansion_feasibility_note="test",
        paper_only=True,
        production_ready=False,
        audit_status=audit_status,
        p29_gate=P29_BLOCKED_NO_SAFE_EXPANSION_PATH,  # placeholder for gate tests
    )


def test_gate_source_expansion_ready() -> None:
    plan = _make_plan_for_gate(
        n_source_safe=2,
        source_estimated=2000,
        best_policy_active=1575,
        audit_status=DENSITY_EXPANSION_SOURCE_PATH_FOUND,
    )
    gate = determine_p29_gate(plan)
    assert gate == P29_DENSITY_EXPANSION_PLAN_READY


def test_gate_policy_risky() -> None:
    plan = _make_plan_for_gate(
        n_source_safe=0,
        source_estimated=0,
        best_policy_active=1575,
        audit_status=DENSITY_EXPANSION_POLICY_PATH_RISKY,
    )
    gate = determine_p29_gate(plan)
    assert gate == P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY


def test_gate_source_insufficient() -> None:
    plan = _make_plan_for_gate(
        n_source_safe=0,
        source_estimated=0,
        best_policy_active=900,  # below target
        audit_status=DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE,
    )
    gate = determine_p29_gate(plan)
    assert gate == P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT


def test_gate_no_safe_path() -> None:
    plan = _make_plan_for_gate(
        n_source_safe=0,
        source_estimated=0,
        best_policy_active=800,
        audit_status=DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE,
    )
    gate = determine_p29_gate(plan)
    # Could be SOURCE_INSUFFICIENT or NO_SAFE since no source and no policy
    assert gate in (P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT, P29_BLOCKED_NO_SAFE_EXPANSION_PATH)


# ---------------------------------------------------------------------------
# build_density_expansion_plan
# ---------------------------------------------------------------------------


def test_build_plan_blocked_policy_risky() -> None:
    diagnosis = _make_diagnosis()
    policy_candidates = [_make_policy_candidate(1575, has_risk=True)]
    source_candidates = []
    summary = _make_source_summary(safe=0)
    estimate = _make_source_estimate(safe_rows=0)
    plan = build_density_expansion_plan(
        diagnosis, policy_candidates, source_candidates, summary, estimate
    )
    assert plan.paper_only is True
    assert plan.production_ready is False
    assert plan.p29_gate in (
        P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
        P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT,
        P29_BLOCKED_NO_SAFE_EXPANSION_PATH,
    )
    assert plan.best_policy_candidate_active_entries == 1575


def test_build_plan_no_candidates() -> None:
    diagnosis = _make_diagnosis()
    plan = build_density_expansion_plan(diagnosis, [], [], _make_source_summary(), _make_source_estimate())
    assert plan.policy_thresholds_tested == 0
    assert plan.best_policy_candidate_id == "N/A"


def test_build_plan_paper_only_enforced() -> None:
    plan = build_density_expansion_plan(
        _make_diagnosis(), [], [], _make_source_summary(), _make_source_estimate()
    )
    assert plan.paper_only is True
    assert plan.production_ready is False


# ---------------------------------------------------------------------------
# validate_density_expansion_plan
# ---------------------------------------------------------------------------


def _make_valid_plan() -> P29DensityExpansionPlan:
    return P29DensityExpansionPlan(
        current_active_entries=324,
        target_active_entries=1500,
        density_gap=1176,
        current_active_per_day=2.25,
        target_active_per_day=10.71,
        available_true_date_rows=1577,
        current_policy_id="e0p0500_s0p0025_k0p10_o2p50",
        policy_thresholds_tested=32,
        best_policy_candidate_id="e0p0200_s0p0025_k0p10_oinf",
        best_policy_candidate_active_entries=1575,
        source_expansion_estimated_entries=0,
        n_source_candidates_found=3,
        n_source_candidates_safe=0,
        recommended_next_action="BLOCKED",
        expansion_feasibility_note="Note",
        paper_only=True,
        production_ready=False,
        audit_status=DENSITY_EXPANSION_POLICY_PATH_RISKY,
        p29_gate=P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
    )


def test_validate_plan_passes() -> None:
    plan = _make_valid_plan()
    assert validate_density_expansion_plan(plan) is True


def test_validate_plan_wrong_gap() -> None:
    plan = _make_valid_plan()
    # density_gap = 1176, but let's make a wrong version
    # Cannot modify frozen, so build a new one with mismatched gap
    bad_plan = P29DensityExpansionPlan(
        current_active_entries=plan.current_active_entries,
        target_active_entries=plan.target_active_entries,
        density_gap=999,  # wrong
        current_active_per_day=plan.current_active_per_day,
        target_active_per_day=plan.target_active_per_day,
        available_true_date_rows=plan.available_true_date_rows,
        current_policy_id=plan.current_policy_id,
        policy_thresholds_tested=plan.policy_thresholds_tested,
        best_policy_candidate_id=plan.best_policy_candidate_id,
        best_policy_candidate_active_entries=plan.best_policy_candidate_active_entries,
        source_expansion_estimated_entries=plan.source_expansion_estimated_entries,
        n_source_candidates_found=plan.n_source_candidates_found,
        n_source_candidates_safe=plan.n_source_candidates_safe,
        recommended_next_action=plan.recommended_next_action,
        expansion_feasibility_note=plan.expansion_feasibility_note,
        paper_only=True,
        production_ready=False,
        audit_status=plan.audit_status,
        p29_gate=plan.p29_gate,
    )
    with pytest.raises(ValueError, match="density_gap"):
        validate_density_expansion_plan(bad_plan)


# ---------------------------------------------------------------------------
# build_gate_result
# ---------------------------------------------------------------------------


def test_build_gate_result_basic() -> None:
    plan = _make_valid_plan()
    gr = build_gate_result(plan)
    assert isinstance(gr, P29DensityExpansionGateResult)
    assert gr.p29_gate == plan.p29_gate
    assert gr.paper_only is True
    assert gr.production_ready is False


# ---------------------------------------------------------------------------
# write_p29_outputs
# ---------------------------------------------------------------------------


def test_write_p29_outputs_creates_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "p29_out"
    plan = _make_valid_plan()
    gr = build_gate_result(plan)
    diagnosis = _make_diagnosis()
    write_p29_outputs(
        output_dir=output_dir,
        gate_result=gr,
        diagnosis=diagnosis,
        policy_candidates=[_make_policy_candidate(1575)],
        policy_summary={"n_candidates_tested": 1, "best_candidate_n_active": 1575},
        source_candidates=[_make_source_candidate()],
        source_summary=_make_source_summary(),
        source_estimate=_make_source_estimate(),
        plan=plan,
    )
    expected_files = [
        "density_diagnosis.json",
        "density_diagnosis.md",
        "policy_sensitivity_results.csv",
        "policy_sensitivity_summary.json",
        "source_coverage_expansion.json",
        "source_coverage_expansion.md",
        "density_expansion_plan.json",
        "p29_gate_result.json",
    ]
    for fname in expected_files:
        assert (output_dir / fname).exists(), f"Missing file: {fname}"


def test_write_p29_outputs_gate_result_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "p29_out"
    plan = _make_valid_plan()
    gr = build_gate_result(plan)
    diagnosis = _make_diagnosis()
    write_p29_outputs(
        output_dir=output_dir,
        gate_result=gr,
        diagnosis=diagnosis,
        policy_candidates=[],
        policy_summary={},
        source_candidates=[],
        source_summary=_make_source_summary(),
        source_estimate=_make_source_estimate(),
        plan=plan,
    )
    gate_data = json.loads((output_dir / "p29_gate_result.json").read_text())
    assert gate_data["p29_gate"] == P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY
    assert gate_data["paper_only"] is True
    assert gate_data["production_ready"] is False


def test_write_p29_outputs_policy_csv_has_rows(tmp_path: Path) -> None:
    output_dir = tmp_path / "p29_out"
    plan = _make_valid_plan()
    gr = build_gate_result(plan)
    diagnosis = _make_diagnosis()
    write_p29_outputs(
        output_dir=output_dir,
        gate_result=gr,
        diagnosis=diagnosis,
        policy_candidates=[_make_policy_candidate(1575), _make_policy_candidate(800, has_risk=False)],
        policy_summary={},
        source_candidates=[],
        source_summary=_make_source_summary(),
        source_estimate=_make_source_estimate(),
        plan=plan,
    )
    df = pd.read_csv(output_dir / "policy_sensitivity_results.csv")
    assert len(df) == 2
    assert "policy_id" in df.columns
    assert "n_active_entries" in df.columns
