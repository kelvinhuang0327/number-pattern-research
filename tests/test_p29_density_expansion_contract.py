"""
tests/test_p29_density_expansion_contract.py

Unit tests for P29 frozen dataclasses and gate constants.
"""
import pytest

from wbc_backend.recommendation.p29_density_expansion_contract import (
    DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE,
    DENSITY_EXPANSION_NO_PATH_FOUND,
    DENSITY_EXPANSION_PLAN_FEASIBLE,
    DENSITY_EXPANSION_POLICY_PATH_RISKY,
    DENSITY_EXPANSION_SOURCE_PATH_FOUND,
    P29DensityDiagnosis,
    P29DensityExpansionGateResult,
    P29DensityExpansionPlan,
    P29PolicySensitivityCandidate,
    P29SourceCoverageCandidate,
    P29_BLOCKED_CONTRACT_VIOLATION,
    P29_BLOCKED_NO_SAFE_EXPANSION_PATH,
    P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
    P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT,
    P29_DENSITY_EXPANSION_PLAN_READY,
    P29_FAIL_INPUT_MISSING,
    P29_FAIL_NON_DETERMINISTIC,
    TARGET_ACTIVE_ENTRIES_DEFAULT,
)


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------


def test_gate_constants_are_strings() -> None:
    assert isinstance(P29_DENSITY_EXPANSION_PLAN_READY, str)
    assert isinstance(P29_BLOCKED_NO_SAFE_EXPANSION_PATH, str)
    assert isinstance(P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT, str)
    assert isinstance(P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY, str)
    assert isinstance(P29_BLOCKED_CONTRACT_VIOLATION, str)
    assert isinstance(P29_FAIL_INPUT_MISSING, str)
    assert isinstance(P29_FAIL_NON_DETERMINISTIC, str)


def test_gate_constants_unique() -> None:
    gates = [
        P29_DENSITY_EXPANSION_PLAN_READY,
        P29_BLOCKED_NO_SAFE_EXPANSION_PATH,
        P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT,
        P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
        P29_BLOCKED_CONTRACT_VIOLATION,
        P29_FAIL_INPUT_MISSING,
        P29_FAIL_NON_DETERMINISTIC,
    ]
    assert len(set(gates)) == len(gates)


def test_target_active_entries_default() -> None:
    assert TARGET_ACTIVE_ENTRIES_DEFAULT == 1500


def test_density_status_constants_distinct() -> None:
    statuses = [
        DENSITY_EXPANSION_PLAN_FEASIBLE,
        DENSITY_EXPANSION_SOURCE_PATH_FOUND,
        DENSITY_EXPANSION_POLICY_PATH_RISKY,
        DENSITY_EXPANSION_NO_PATH_FOUND,
        DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE,
    ]
    assert len(set(statuses)) == len(statuses)


# ---------------------------------------------------------------------------
# P29DensityDiagnosis
# ---------------------------------------------------------------------------


def _make_diagnosis(**kwargs) -> P29DensityDiagnosis:
    defaults = dict(
        current_active_entries=324,
        target_active_entries=1500,
        density_gap=1176,
        current_active_per_day=2.25,
        target_active_per_day=10.71,
        total_source_rows=1577,
        active_conversion_rate=0.2054,
        n_blocked_edge=907,
        n_blocked_odds=344,
        n_blocked_unknown=2,
        n_dates_zero_active=0,
        n_dates_sparse_active=50,
        primary_blocker="edge_threshold",
        diagnosis_note="Test note",
        paper_only=True,
        production_ready=False,
    )
    defaults.update(kwargs)
    return P29DensityDiagnosis(**defaults)


def test_density_diagnosis_valid() -> None:
    d = _make_diagnosis()
    assert d.current_active_entries == 324
    assert d.paper_only is True
    assert d.production_ready is False


def test_density_diagnosis_frozen() -> None:
    d = _make_diagnosis()
    with pytest.raises(Exception):
        d.current_active_entries = 500  # type: ignore[misc]


def test_density_diagnosis_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        _make_diagnosis(paper_only=False)


def test_density_diagnosis_rejects_production_ready_true() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        _make_diagnosis(production_ready=True)


# ---------------------------------------------------------------------------
# P29PolicySensitivityCandidate
# ---------------------------------------------------------------------------


def _make_policy_candidate(**kwargs) -> P29PolicySensitivityCandidate:
    defaults = dict(
        policy_id="e0p0300_s0p0025_k0p10_o3p00",
        edge_threshold=0.03,
        odds_decimal_max=3.00,
        max_stake_cap=0.0025,
        kelly_fraction=0.10,
        n_active_entries=800,
        active_entry_lift_vs_current=476,
        estimated_total_stake_units=2.5,
        hit_rate=0.52,
        roi_units=0.12,
        max_drawdown_pct=15.0,
        gate_reason_counts="{}",
        risk_flags="",
        is_deployment_ready=False,
        exploratory_only=True,
        paper_only=True,
        production_ready=False,
    )
    defaults.update(kwargs)
    return P29PolicySensitivityCandidate(**defaults)


def test_policy_candidate_valid() -> None:
    c = _make_policy_candidate()
    assert c.exploratory_only is True
    assert c.is_deployment_ready is False
    assert c.paper_only is True


def test_policy_candidate_frozen() -> None:
    c = _make_policy_candidate()
    with pytest.raises(Exception):
        c.policy_id = "x"  # type: ignore[misc]


def test_policy_candidate_rejects_deployment_ready_true() -> None:
    with pytest.raises(ValueError, match="is_deployment_ready"):
        _make_policy_candidate(is_deployment_ready=True)


def test_policy_candidate_rejects_exploratory_only_false() -> None:
    with pytest.raises(ValueError, match="exploratory_only"):
        _make_policy_candidate(exploratory_only=False)


def test_policy_candidate_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        _make_policy_candidate(paper_only=False)


def test_policy_candidate_rejects_production_ready_true() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        _make_policy_candidate(production_ready=True)


# ---------------------------------------------------------------------------
# P29SourceCoverageCandidate
# ---------------------------------------------------------------------------


def _make_source_candidate(**kwargs) -> P29SourceCoverageCandidate:
    defaults = dict(
        source_path="/some/data/path.csv",
        source_type="additional_season",
        date_range_start="2024-04-01",
        date_range_end="2024-09-30",
        estimated_new_rows=500,
        has_required_columns=False,
        has_y_true=True,
        has_game_id=True,
        has_odds=True,
        coverage_note="Test source",
        is_safe_to_use=False,
        paper_only=True,
        production_ready=False,
    )
    defaults.update(kwargs)
    return P29SourceCoverageCandidate(**defaults)


def test_source_candidate_valid() -> None:
    c = _make_source_candidate()
    assert c.paper_only is True
    assert c.production_ready is False


def test_source_candidate_frozen() -> None:
    c = _make_source_candidate()
    with pytest.raises(Exception):
        c.source_path = "other"  # type: ignore[misc]


def test_source_candidate_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        _make_source_candidate(paper_only=False)


def test_source_candidate_rejects_production_ready_true() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        _make_source_candidate(production_ready=True)


# ---------------------------------------------------------------------------
# P29DensityExpansionPlan
# ---------------------------------------------------------------------------


def _make_plan(**kwargs) -> P29DensityExpansionPlan:
    defaults = dict(
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
        recommended_next_action="BLOCKED: see note",
        expansion_feasibility_note="Detailed note",
        paper_only=True,
        production_ready=False,
        audit_status=DENSITY_EXPANSION_POLICY_PATH_RISKY,
        p29_gate=P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
    )
    defaults.update(kwargs)
    return P29DensityExpansionPlan(**defaults)


def test_plan_valid() -> None:
    p = _make_plan()
    assert p.p29_gate == P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY
    assert p.paper_only is True
    assert p.production_ready is False


def test_plan_frozen() -> None:
    p = _make_plan()
    with pytest.raises(Exception):
        p.p29_gate = P29_DENSITY_EXPANSION_PLAN_READY  # type: ignore[misc]


def test_plan_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        _make_plan(paper_only=False)


def test_plan_rejects_production_ready_true() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        _make_plan(production_ready=True)


def test_plan_rejects_invalid_gate() -> None:
    with pytest.raises(ValueError, match="p29_gate"):
        _make_plan(p29_gate="INVALID_GATE_VALUE")


def test_plan_rejects_invalid_audit_status() -> None:
    with pytest.raises(ValueError, match="audit_status"):
        _make_plan(audit_status="INVALID_STATUS")


# ---------------------------------------------------------------------------
# P29DensityExpansionGateResult
# ---------------------------------------------------------------------------


def _make_gate_result(**kwargs) -> P29DensityExpansionGateResult:
    defaults = dict(
        p29_gate=P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
        current_active_entries=324,
        target_active_entries=1500,
        density_gap=1176,
        best_policy_candidate_active_entries=1575,
        source_expansion_estimated_entries=0,
        recommended_next_action="Acquire more data",
        audit_status=DENSITY_EXPANSION_POLICY_PATH_RISKY,
        blocker_reason=P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
        paper_only=True,
        production_ready=False,
    )
    defaults.update(kwargs)
    return P29DensityExpansionGateResult(**defaults)


def test_gate_result_valid() -> None:
    g = _make_gate_result()
    assert g.p29_gate == P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY
    assert g.paper_only is True
    assert g.production_ready is False


def test_gate_result_frozen() -> None:
    g = _make_gate_result()
    with pytest.raises(Exception):
        g.p29_gate = P29_DENSITY_EXPANSION_PLAN_READY  # type: ignore[misc]


def test_gate_result_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        _make_gate_result(paper_only=False)


def test_gate_result_rejects_production_ready_true() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        _make_gate_result(production_ready=True)


def test_gate_result_rejects_invalid_gate() -> None:
    with pytest.raises(ValueError, match="p29_gate"):
        _make_gate_result(p29_gate="RANDOM_GATE")


def test_gate_result_rejects_invalid_audit_status() -> None:
    with pytest.raises(ValueError, match="audit_status"):
        _make_gate_result(audit_status="RANDOM_STATUS")
