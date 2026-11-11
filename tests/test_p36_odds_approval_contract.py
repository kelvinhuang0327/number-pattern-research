"""Tests for P36 odds approval contract."""
import pytest

from wbc_backend.recommendation.p36_odds_approval_contract import (
    ALL_APPROVAL_STATUSES,
    ALL_P36_GATES,
    APPROVAL_BLOCKED_LICENSE,
    APPROVAL_BLOCKED_PROVENANCE,
    APPROVAL_INVALID,
    APPROVAL_MISSING,
    APPROVAL_READY,
    APPROVAL_REQUIRES_LEGAL_REVIEW,
    APPROVAL_RECORD_REQUIRED_FIELDS,
    FORBIDDEN_ODDS_COLUMNS,
    MANUAL_ODDS_REQUIRED_COLUMNS,
    PAPER_ONLY,
    PRODUCTION_READY,
    SEASON,
    P36_BLOCKED_APPROVAL_RECORD_INVALID,
    P36_BLOCKED_APPROVAL_RECORD_MISSING,
    P36_BLOCKED_CONTRACT_VIOLATION,
    P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH,
    P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
    P36_BLOCKED_REDISTRIBUTION_RISK,
    P36_FAIL_INPUT_MISSING,
    P36_FAIL_NON_DETERMINISTIC,
    P36_ODDS_APPROVAL_RECORD_READY,
    P36GateResult,
    P36ManualOddsImportSpec,
    P36OddsApprovalRecord,
    P36OddsApprovalValidationResult,
    P36OddsImportGateResult,
)


# ---------------------------------------------------------------------------
# Module-level guards
# ---------------------------------------------------------------------------


def test_paper_only_is_true():
    assert PAPER_ONLY is True


def test_production_ready_is_false():
    assert PRODUCTION_READY is False


def test_season_is_2024():
    assert SEASON == 2024


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------


def test_all_p36_gates_has_9_values():
    assert len(ALL_P36_GATES) == 9


def test_all_gate_values_are_strings():
    for g in ALL_P36_GATES:
        assert isinstance(g, str)


def test_gate_constants_in_all_p36_gates():
    for gate in (
        P36_ODDS_APPROVAL_RECORD_READY,
        P36_BLOCKED_APPROVAL_RECORD_MISSING,
        P36_BLOCKED_APPROVAL_RECORD_INVALID,
        P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH,
        P36_BLOCKED_REDISTRIBUTION_RISK,
        P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
        P36_BLOCKED_CONTRACT_VIOLATION,
        P36_FAIL_INPUT_MISSING,
        P36_FAIL_NON_DETERMINISTIC,
    ):
        assert gate in ALL_P36_GATES


# ---------------------------------------------------------------------------
# Approval status constants
# ---------------------------------------------------------------------------


def test_all_approval_statuses_has_6_values():
    assert len(ALL_APPROVAL_STATUSES) == 6


def test_approval_status_constants_in_all():
    for s in (
        APPROVAL_READY,
        APPROVAL_MISSING,
        APPROVAL_INVALID,
        APPROVAL_REQUIRES_LEGAL_REVIEW,
        APPROVAL_BLOCKED_LICENSE,
        APPROVAL_BLOCKED_PROVENANCE,
    ):
        assert s in ALL_APPROVAL_STATUSES


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


def test_approval_record_required_fields_has_16():
    assert len(APPROVAL_RECORD_REQUIRED_FIELDS) == 16


def test_approval_record_required_fields_include_key_fields():
    for f in (
        "provider_name",
        "approved_by",
        "approved_at",
        "internal_research_allowed",
        "paper_only",
        "production_ready",
        "source_file_expected_path",
    ):
        assert f in APPROVAL_RECORD_REQUIRED_FIELDS


def test_manual_odds_required_columns_has_11():
    assert len(MANUAL_ODDS_REQUIRED_COLUMNS) == 11


def test_manual_odds_required_columns_include_key_fields():
    for c in (
        "game_id",
        "game_date",
        "p_market",
        "odds_decimal",
        "license_ref",
        "source_odds_ref",
    ):
        assert c in MANUAL_ODDS_REQUIRED_COLUMNS


def test_forbidden_odds_columns_non_empty():
    assert len(FORBIDDEN_ODDS_COLUMNS) > 0


def test_y_true_in_forbidden_columns():
    assert "y_true" in FORBIDDEN_ODDS_COLUMNS


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


def test_p36_odds_approval_record_is_frozen():
    rec = P36OddsApprovalRecord(
        provider_name="test",
        source_name="test",
        source_url_or_reference="http://example.com",
        license_terms_summary="test",
        allowed_use="internal_research",
        redistribution_allowed=False,
        attribution_required=True,
        internal_research_allowed=True,
        commercial_use_allowed=False,
        approved_by="researcher",
        approved_at="2026-01-01",
        approval_scope="2024_season",
        source_file_expected_path="/tmp/odds.csv",
        checksum_required=False,
        paper_only=True,
        production_ready=False,
    )
    with pytest.raises((AttributeError, TypeError)):
        rec.paper_only = False  # type: ignore[misc]


def test_p36_odds_approval_validation_result_is_frozen():
    result = P36OddsApprovalValidationResult(
        approval_status=APPROVAL_MISSING,
        approval_record_found=False,
        all_required_fields_present=False,
        internal_research_allowed=False,
        allowed_use_valid=False,
        approved_by_present=False,
        approved_at_present=False,
        source_file_path_present=False,
        paper_only=True,
        production_ready=False,
        redistribution_allowed=False,
        redistribution_risk_note="",
        blocker_reason="no record",
        missing_fields=tuple(APPROVAL_RECORD_REQUIRED_FIELDS),
    )
    with pytest.raises((AttributeError, TypeError)):
        result.paper_only = False  # type: ignore[misc]


def test_p36_manual_odds_import_spec_is_frozen():
    spec = P36ManualOddsImportSpec(
        required_columns=MANUAL_ODDS_REQUIRED_COLUMNS,
        forbidden_columns=FORBIDDEN_ODDS_COLUMNS,
        allowed_market_types=("moneyline",),
        p_market_range=(0.0, 1.0),
        odds_decimal_min=1.0,
        paper_only=True,
        production_ready=False,
        notes="test",
    )
    with pytest.raises((AttributeError, TypeError)):
        spec.paper_only = False  # type: ignore[misc]


def test_p36_gate_result_is_mutable():
    gate = P36GateResult(
        gate=P36_BLOCKED_APPROVAL_RECORD_MISSING,
        approval_record_status=APPROVAL_MISSING,
        odds_source_status="unknown",
        internal_research_allowed=False,
        raw_odds_commit_allowed=False,
        blocker_reason="test",
        recommended_next_action="test",
        paper_only=True,
        production_ready=False,
        season=2024,
    )
    gate.generated_at = "2026-01-01T00:00:00Z"
    assert gate.generated_at == "2026-01-01T00:00:00Z"


def test_p36_gate_result_defaults():
    gate = P36GateResult(
        gate=P36_BLOCKED_APPROVAL_RECORD_MISSING,
        approval_record_status=APPROVAL_MISSING,
        odds_source_status="unknown",
        internal_research_allowed=False,
        raw_odds_commit_allowed=False,
        blocker_reason="",
        recommended_next_action="",
        paper_only=True,
        production_ready=False,
        season=2024,
    )
    assert gate.artifacts == []
    assert gate.next_phase == "P37_BUILD_2024_ODDS_IMPORT_ARTIFACT"
    assert gate.generated_at == ""
