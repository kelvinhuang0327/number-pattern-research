"""
tests/test_p24_backfill_stability_contract.py

Unit tests for p24_backfill_stability_contract.py.
"""
from __future__ import annotations

import pytest

from wbc_backend.recommendation.p24_backfill_stability_contract import (
    P24_BACKFILL_STABILITY_AUDIT_READY,
    P24_BLOCKED_DUPLICATE_SOURCE_REPLAY,
    P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES,
    P24_FAIL_INPUT_MISSING,
    P24_FAIL_NON_DETERMINISTIC,
    STABILITY_ACCEPTABLE,
    STABILITY_DUPLICATE_SOURCE_SUSPECTED,
    STABILITY_INSUFFICIENT_VARIANCE,
    STABILITY_SOURCE_INTEGRITY_BLOCKED,
    P24DatePerformanceProfile,
    P24DuplicateSourceFinding,
    P24SourceIntegrityProfile,
    P24StabilityAuditSummary,
    P24StabilityGateResult,
)


# ---------------------------------------------------------------------------
# Gate constant values
# ---------------------------------------------------------------------------


def test_gate_constants_are_strings():
    assert isinstance(P24_BACKFILL_STABILITY_AUDIT_READY, str)
    assert isinstance(P24_BLOCKED_DUPLICATE_SOURCE_REPLAY, str)
    assert isinstance(P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES, str)
    assert isinstance(P24_FAIL_INPUT_MISSING, str)
    assert isinstance(P24_FAIL_NON_DETERMINISTIC, str)


def test_gate_constants_distinct():
    gates = [
        P24_BACKFILL_STABILITY_AUDIT_READY,
        P24_BLOCKED_DUPLICATE_SOURCE_REPLAY,
        P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES,
        P24_FAIL_INPUT_MISSING,
        P24_FAIL_NON_DETERMINISTIC,
    ]
    assert len(set(gates)) == len(gates)


def test_audit_status_constants_distinct():
    statuses = [
        STABILITY_ACCEPTABLE,
        STABILITY_DUPLICATE_SOURCE_SUSPECTED,
        STABILITY_INSUFFICIENT_VARIANCE,
        STABILITY_SOURCE_INTEGRITY_BLOCKED,
    ]
    assert len(set(statuses)) == len(statuses)


# ---------------------------------------------------------------------------
# P24DatePerformanceProfile
# ---------------------------------------------------------------------------


def _make_date_profile(**overrides) -> P24DatePerformanceProfile:
    defaults = dict(
        run_date="2026-05-01",
        n_active_entries=100,
        n_settled_win=55,
        n_settled_loss=45,
        n_unsettled=0,
        total_stake_units=25.0,
        total_pnl_units=2.5,
        roi_units=0.10,
        hit_rate=0.55,
        game_id_coverage=1.0,
        source_hash_content="abc123",
        game_id_set_hash="def456",
        game_date_range_str="2026-05-01:2026-05-01",
        run_date_matches_game_date=True,
    )
    defaults.update(overrides)
    return P24DatePerformanceProfile(**defaults)


def test_date_profile_valid():
    p = _make_date_profile()
    assert p.paper_only is True
    assert p.production_ready is False
    assert p.run_date == "2026-05-01"


def test_date_profile_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_date_profile(paper_only=False)


def test_date_profile_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_date_profile(production_ready=True)


def test_date_profile_frozen():
    p = _make_date_profile()
    with pytest.raises(Exception):
        p.roi_units = 0.99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P24DuplicateSourceFinding
# ---------------------------------------------------------------------------


def _make_dup_finding(**overrides) -> P24DuplicateSourceFinding:
    defaults = dict(
        group_id=0,
        content_hash="a" * 64,
        game_id_set_hash="b" * 64,
        dates_in_group=("2026-05-01", "2026-05-02"),
        n_dates=2,
        representative_game_date_range="2025-05-08:2025-05-10",
        is_date_mismatch=True,
    )
    defaults.update(overrides)
    return P24DuplicateSourceFinding(**defaults)


def test_dup_finding_valid():
    f = _make_dup_finding()
    assert f.paper_only is True
    assert f.production_ready is False
    assert f.n_dates == 2


def test_dup_finding_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_dup_finding(paper_only=False)


def test_dup_finding_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_dup_finding(production_ready=True)


def test_dup_finding_frozen():
    f = _make_dup_finding()
    with pytest.raises(Exception):
        f.n_dates = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P24SourceIntegrityProfile
# ---------------------------------------------------------------------------


def _make_source_profile(**overrides) -> P24SourceIntegrityProfile:
    defaults = dict(
        n_dates_audited=12,
        n_independent_source_dates=1,
        n_duplicate_source_groups=1,
        source_hash_unique_count=1,
        source_hash_duplicate_count=11,
        game_id_set_unique_count=1,
        all_dates_date_mismatch=True,
        any_date_date_mismatch=True,
        duplicate_findings=(),
        audit_status=STABILITY_SOURCE_INTEGRITY_BLOCKED,
        blocker_reason="12 dates share same source",
    )
    defaults.update(overrides)
    return P24SourceIntegrityProfile(**defaults)


def test_source_profile_valid():
    p = _make_source_profile()
    assert p.paper_only is True
    assert p.production_ready is False


def test_source_profile_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_source_profile(paper_only=False)


def test_source_profile_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_source_profile(production_ready=True)


# ---------------------------------------------------------------------------
# P24StabilityAuditSummary
# ---------------------------------------------------------------------------


def _make_summary(**overrides) -> P24StabilityAuditSummary:
    defaults = dict(
        date_start="2026-05-01",
        date_end="2026-05-12",
        n_dates_audited=12,
        n_independent_source_dates=0,
        n_duplicate_source_groups=1,
        aggregate_roi_units=0.1078,
        aggregate_hit_rate=0.5278,
        total_stake_units=972.0,
        total_pnl_units=104.76,
        roi_std_by_date=0.0,
        roi_min_by_date=0.1078,
        roi_max_by_date=0.1078,
        hit_rate_std_by_date=0.0,
        hit_rate_min_by_date=0.5278,
        hit_rate_max_by_date=0.5278,
        active_entry_std_by_date=0.0,
        active_entry_min_by_date=324,
        active_entry_max_by_date=324,
        source_hash_unique_count=1,
        source_hash_duplicate_count=11,
        all_dates_date_mismatch=True,
        audit_status=STABILITY_SOURCE_INTEGRITY_BLOCKED,
        blocker_reason="duplicate source",
    )
    defaults.update(overrides)
    return P24StabilityAuditSummary(**defaults)


def test_summary_valid():
    s = _make_summary()
    assert s.paper_only is True
    assert s.production_ready is False


def test_summary_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_summary(paper_only=False)


def test_summary_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_summary(production_ready=True)


def test_summary_frozen():
    s = _make_summary()
    with pytest.raises(Exception):
        s.aggregate_roi_units = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P24StabilityGateResult
# ---------------------------------------------------------------------------


def _make_gate_result(**overrides) -> P24StabilityGateResult:
    defaults = dict(
        p24_gate=P24_BLOCKED_DUPLICATE_SOURCE_REPLAY,
        audit_status=STABILITY_SOURCE_INTEGRITY_BLOCKED,
        date_start="2026-05-01",
        date_end="2026-05-12",
        n_dates_audited=12,
        n_independent_source_dates=0,
        n_duplicate_source_groups=1,
        source_hash_unique_count=1,
        source_hash_duplicate_count=11,
        roi_std_by_date=0.0,
        hit_rate_std_by_date=0.0,
        blocker_reason="duplicate source",
        recommended_next_action="Proceed to P25",
    )
    defaults.update(overrides)
    return P24StabilityGateResult(**defaults)


def test_gate_result_valid():
    g = _make_gate_result()
    assert g.paper_only is True
    assert g.production_ready is False
    assert g.p24_gate == P24_BLOCKED_DUPLICATE_SOURCE_REPLAY


def test_gate_result_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_gate_result(paper_only=False)


def test_gate_result_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_gate_result(production_ready=True)


def test_gate_result_frozen():
    g = _make_gate_result()
    with pytest.raises(Exception):
        g.p24_gate = "SOMETHING_ELSE"  # type: ignore[misc]


def test_gate_result_ready_variant():
    g = _make_gate_result(
        p24_gate=P24_BACKFILL_STABILITY_AUDIT_READY,
        audit_status=STABILITY_ACCEPTABLE,
        n_independent_source_dates=5,
        n_duplicate_source_groups=0,
        source_hash_duplicate_count=0,
        blocker_reason="",
    )
    assert g.p24_gate == P24_BACKFILL_STABILITY_AUDIT_READY
    assert g.blocker_reason == ""
