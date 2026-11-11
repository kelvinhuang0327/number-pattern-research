"""
tests/test_p28_true_date_stability_contract.py

Unit tests for P28 stability contract — gate constants, audit status constants,
and frozen dataclass enforcement.
"""
import pytest

from wbc_backend.recommendation.p28_true_date_stability_contract import (
    P28_TRUE_DATE_STABILITY_AUDIT_READY,
    P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT,
    P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE,
    P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT,
    P28_BLOCKED_CONTRACT_VIOLATION,
    P28_FAIL_INPUT_MISSING,
    P28_FAIL_NON_DETERMINISTIC,
    STABILITY_ACCEPTABLE_FOR_RESEARCH,
    STABILITY_SAMPLE_SIZE_INSUFFICIENT,
    STABILITY_SEGMENT_VARIANCE_UNSTABLE,
    STABILITY_DRAWDOWN_RISK_HIGH,
    STABILITY_REQUIRES_MORE_DATA,
    MIN_SAMPLE_SIZE_ADVISORY,
    MAX_DRAWDOWN_PCT_LIMIT,
    HIGH_LOSING_STREAK_DAYS,
    P28DateStabilityProfile,
    P28SegmentStabilityProfile,
    P28SampleDensityProfile,
    P28PerformanceVarianceProfile,
    P28RiskProfile,
    P28StabilityAuditSummary,
    P28GateResult,
)


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------


def test_gate_constants_are_strings():
    assert isinstance(P28_TRUE_DATE_STABILITY_AUDIT_READY, str)
    assert isinstance(P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT, str)
    assert isinstance(P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE, str)
    assert isinstance(P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT, str)
    assert isinstance(P28_BLOCKED_CONTRACT_VIOLATION, str)
    assert isinstance(P28_FAIL_INPUT_MISSING, str)
    assert isinstance(P28_FAIL_NON_DETERMINISTIC, str)


def test_gate_constants_distinct():
    gates = [
        P28_TRUE_DATE_STABILITY_AUDIT_READY,
        P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT,
        P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE,
        P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT,
        P28_BLOCKED_CONTRACT_VIOLATION,
        P28_FAIL_INPUT_MISSING,
        P28_FAIL_NON_DETERMINISTIC,
    ]
    assert len(set(gates)) == 7


def test_audit_status_constants_are_strings():
    assert isinstance(STABILITY_ACCEPTABLE_FOR_RESEARCH, str)
    assert isinstance(STABILITY_SAMPLE_SIZE_INSUFFICIENT, str)
    assert isinstance(STABILITY_SEGMENT_VARIANCE_UNSTABLE, str)
    assert isinstance(STABILITY_DRAWDOWN_RISK_HIGH, str)
    assert isinstance(STABILITY_REQUIRES_MORE_DATA, str)


def test_audit_status_constants_distinct():
    statuses = [
        STABILITY_ACCEPTABLE_FOR_RESEARCH,
        STABILITY_SAMPLE_SIZE_INSUFFICIENT,
        STABILITY_SEGMENT_VARIANCE_UNSTABLE,
        STABILITY_DRAWDOWN_RISK_HIGH,
        STABILITY_REQUIRES_MORE_DATA,
    ]
    assert len(set(statuses)) == 5


def test_threshold_values():
    assert MIN_SAMPLE_SIZE_ADVISORY == 1500
    assert MAX_DRAWDOWN_PCT_LIMIT == 25.0
    assert HIGH_LOSING_STREAK_DAYS == 7


# ---------------------------------------------------------------------------
# P28DateStabilityProfile
# ---------------------------------------------------------------------------


def _make_date_profile(**overrides):
    defaults = {
        "run_date": "2025-05-08",
        "n_active_paper_entries": 5,
        "n_settled_win": 3,
        "n_settled_loss": 2,
        "roi_units": 0.05,
        "hit_rate": 0.6,
        "total_stake_units": 1.25,
        "total_pnl_units": 0.0625,
        "is_sparse": False,
        "paper_only": True,
        "production_ready": False,
    }
    defaults.update(overrides)
    return P28DateStabilityProfile(**defaults)


def test_date_profile_valid():
    p = _make_date_profile()
    assert p.paper_only is True
    assert p.production_ready is False


def test_date_profile_frozen():
    p = _make_date_profile()
    with pytest.raises((AttributeError, TypeError)):
        p.run_date = "2025-05-09"  # type: ignore[misc]


def test_date_profile_paper_only_enforced():
    with pytest.raises(ValueError, match="paper_only"):
        _make_date_profile(paper_only=False)


def test_date_profile_production_ready_enforced():
    with pytest.raises(ValueError, match="production_ready"):
        _make_date_profile(production_ready=True)


# ---------------------------------------------------------------------------
# P28SegmentStabilityProfile
# ---------------------------------------------------------------------------


def _make_segment_profile(**overrides):
    defaults = {
        "segment_index": 0,
        "date_start": "2025-05-08",
        "date_end": "2025-05-21",
        "total_active_entries": 37,
        "total_settled_win": 17,
        "total_settled_loss": 20,
        "total_stake_units": 9.25,
        "total_pnl_units": -0.331,
        "roi_units": -0.0358,
        "hit_rate": 0.459,
        "is_sparse": False,
        "is_blocked": False,
        "paper_only": True,
        "production_ready": False,
    }
    defaults.update(overrides)
    return P28SegmentStabilityProfile(**defaults)


def test_segment_profile_valid():
    p = _make_segment_profile()
    assert p.paper_only is True
    assert p.production_ready is False


def test_segment_profile_frozen():
    p = _make_segment_profile()
    with pytest.raises((AttributeError, TypeError)):
        p.segment_index = 99  # type: ignore[misc]


def test_segment_profile_paper_only_enforced():
    with pytest.raises(ValueError, match="paper_only"):
        _make_segment_profile(paper_only=False)


def test_segment_profile_production_ready_enforced():
    with pytest.raises(ValueError, match="production_ready"):
        _make_segment_profile(production_ready=True)


# ---------------------------------------------------------------------------
# P28SampleDensityProfile
# ---------------------------------------------------------------------------


def _make_density_profile(**overrides):
    defaults = {
        "n_dates_total": 144,
        "n_dates_ready": 140,
        "n_dates_blocked": 4,
        "n_dates_sparse": 0,
        "n_segments": 11,
        "n_segments_sparse": 0,
        "total_active_entries": 324,
        "min_sample_size_advisory": 1500,
        "sample_size_pass": False,
        "daily_active_min": 1.0,
        "daily_active_max": 9.0,
        "daily_active_mean": 2.31,
        "daily_active_std": 1.5,
        "sparse_date_list": (),
        "sparse_segment_list": (),
        "paper_only": True,
        "production_ready": False,
    }
    defaults.update(overrides)
    return P28SampleDensityProfile(**defaults)


def test_density_profile_valid():
    p = _make_density_profile()
    assert p.sample_size_pass is False
    assert p.total_active_entries == 324


def test_density_profile_frozen():
    p = _make_density_profile()
    with pytest.raises((AttributeError, TypeError)):
        p.total_active_entries = 9999  # type: ignore[misc]


def test_density_profile_paper_only_enforced():
    with pytest.raises(ValueError, match="paper_only"):
        _make_density_profile(paper_only=False)


def test_density_profile_production_ready_enforced():
    with pytest.raises(ValueError, match="production_ready"):
        _make_density_profile(production_ready=True)


# ---------------------------------------------------------------------------
# P28RiskProfile
# ---------------------------------------------------------------------------


def _make_risk_profile(**overrides):
    defaults = {
        "max_drawdown_units": 1.5,
        "max_drawdown_pct": 15.0,
        "max_consecutive_losing_days": 3,
        "total_losing_days": 40,
        "total_winning_days": 70,
        "total_neutral_days": 30,
        "loss_cluster_summary": "3 clusters",
        "drawdown_exceeds_limit": False,
        "high_losing_streak": False,
        "paper_only": True,
        "production_ready": False,
    }
    defaults.update(overrides)
    return P28RiskProfile(**defaults)


def test_risk_profile_valid():
    p = _make_risk_profile()
    assert p.paper_only is True


def test_risk_profile_frozen():
    p = _make_risk_profile()
    with pytest.raises((AttributeError, TypeError)):
        p.max_drawdown_pct = 99.0  # type: ignore[misc]


def test_risk_profile_paper_only_enforced():
    with pytest.raises(ValueError, match="paper_only"):
        _make_risk_profile(paper_only=False)


def test_risk_profile_production_ready_enforced():
    with pytest.raises(ValueError, match="production_ready"):
        _make_risk_profile(production_ready=True)


# ---------------------------------------------------------------------------
# P28StabilityAuditSummary
# ---------------------------------------------------------------------------


def _make_audit_summary(**overrides):
    defaults = {
        "n_dates_total": 144,
        "n_dates_ready": 140,
        "n_dates_blocked": 4,
        "n_segments": 11,
        "total_active_entries": 324,
        "min_sample_size_advisory": 1500,
        "sample_size_pass": False,
        "aggregate_roi_units": 0.1078,
        "aggregate_hit_rate": 0.5278,
        "segment_roi_min": -0.0535,
        "segment_roi_max": 0.2270,
        "segment_roi_std": 0.1234,
        "daily_active_min": 1.0,
        "daily_active_max": 9.0,
        "daily_active_std": 1.5,
        "max_drawdown_units": 1.5,
        "max_drawdown_pct": 15.0,
        "max_consecutive_losing_days": 3,
        "bootstrap_roi_ci_low_95": 0.01,
        "bootstrap_roi_ci_high_95": 0.20,
        "paper_only": True,
        "production_ready": False,
        "audit_status": STABILITY_SAMPLE_SIZE_INSUFFICIENT,
        "blocker_reason": "total_active_entries=324 < min_sample_size_advisory=1500",
    }
    defaults.update(overrides)
    return P28StabilityAuditSummary(**defaults)


def test_audit_summary_valid():
    s = _make_audit_summary()
    assert s.paper_only is True
    assert s.production_ready is False


def test_audit_summary_frozen():
    s = _make_audit_summary()
    with pytest.raises((AttributeError, TypeError)):
        s.n_dates_total = 999  # type: ignore[misc]


def test_audit_summary_paper_only_enforced():
    with pytest.raises(ValueError, match="paper_only"):
        _make_audit_summary(paper_only=False)


def test_audit_summary_production_ready_enforced():
    with pytest.raises(ValueError, match="production_ready"):
        _make_audit_summary(production_ready=True)


def test_audit_summary_invalid_status():
    with pytest.raises(ValueError, match="audit_status"):
        _make_audit_summary(audit_status="UNKNOWN_STATUS")


# ---------------------------------------------------------------------------
# P28GateResult
# ---------------------------------------------------------------------------


def _make_gate_result(**overrides):
    defaults = {
        "p28_gate": P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT,
        "n_dates_total": 144,
        "n_dates_ready": 140,
        "n_dates_blocked": 4,
        "n_segments": 11,
        "total_active_entries": 324,
        "min_sample_size_advisory": 1500,
        "sample_size_pass": False,
        "aggregate_roi_units": 0.1078,
        "aggregate_hit_rate": 0.5278,
        "segment_roi_std": 0.1234,
        "daily_active_std": 1.5,
        "max_drawdown_units": 1.5,
        "max_drawdown_pct": 15.0,
        "max_consecutive_losing_days": 3,
        "bootstrap_roi_ci_low_95": 0.01,
        "bootstrap_roi_ci_high_95": 0.20,
        "paper_only": True,
        "production_ready": False,
        "audit_status": STABILITY_SAMPLE_SIZE_INSUFFICIENT,
        "blocker_reason": "total_active_entries=324 < min_sample_size_advisory=1500",
        "generated_at": "2026-05-12T00:00:00+00:00",
    }
    defaults.update(overrides)
    return P28GateResult(**defaults)


def test_gate_result_valid():
    r = _make_gate_result()
    assert r.p28_gate == P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT
    assert r.paper_only is True
    assert r.production_ready is False


def test_gate_result_frozen():
    r = _make_gate_result()
    with pytest.raises((AttributeError, TypeError)):
        r.p28_gate = "SOMETHING"  # type: ignore[misc]


def test_gate_result_paper_only_enforced():
    with pytest.raises(ValueError, match="paper_only"):
        _make_gate_result(paper_only=False)


def test_gate_result_production_ready_enforced():
    with pytest.raises(ValueError, match="production_ready"):
        _make_gate_result(production_ready=True)


def test_gate_result_invalid_gate():
    with pytest.raises(ValueError, match="gate"):
        _make_gate_result(p28_gate="P28_BOGUS")


def test_gate_result_invalid_audit_status():
    with pytest.raises(ValueError, match="audit_status"):
        _make_gate_result(audit_status="BOGUS_STATUS")


def test_gate_result_all_valid_gates():
    valid_gates = [
        (P28_TRUE_DATE_STABILITY_AUDIT_READY, STABILITY_ACCEPTABLE_FOR_RESEARCH),
        (P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT, STABILITY_SAMPLE_SIZE_INSUFFICIENT),
        (P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE, STABILITY_SEGMENT_VARIANCE_UNSTABLE),
        (P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT, STABILITY_DRAWDOWN_RISK_HIGH),
        (P28_BLOCKED_CONTRACT_VIOLATION, STABILITY_SAMPLE_SIZE_INSUFFICIENT),
        (P28_FAIL_INPUT_MISSING, STABILITY_SAMPLE_SIZE_INSUFFICIENT),
        (P28_FAIL_NON_DETERMINISTIC, STABILITY_SAMPLE_SIZE_INSUFFICIENT),
    ]
    for gate, status in valid_gates:
        r = _make_gate_result(p28_gate=gate, audit_status=status)
        assert r.p28_gate == gate
