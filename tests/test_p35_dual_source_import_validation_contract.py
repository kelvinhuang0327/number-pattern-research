"""Tests for P35 dual source import validation contract."""
import pytest

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    ALL_FEASIBILITY_STATUSES,
    ALL_P35_GATES,
    ALL_VALIDATION_STATUSES,
    FEASIBILITY_BLOCKED_ADAPTER_MISSING,
    FEASIBILITY_BLOCKED_LEAKAGE_RISK,
    FEASIBILITY_BLOCKED_PIPELINE_MISSING,
    FEASIBILITY_READY,
    FEASIBILITY_REQUIRES_P36_IMPLEMENTATION,
    ODDS_REQUIRED_COLUMNS,
    PAPER_ONLY,
    PREDICTION_REQUIRED_COLUMNS,
    PRODUCTION_READY,
    P35_BLOCKED_CONTRACT_VIOLATION,
    P35_BLOCKED_FEATURE_PIPELINE_MISSING,
    P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED,
    P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
    P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE,
    P35_DUAL_SOURCE_IMPORT_VALIDATION_READY,
    P35_FAIL_INPUT_MISSING,
    P35_FAIL_NON_DETERMINISTIC,
    VALIDATION_BLOCKED_LEAKAGE_RISK,
    VALIDATION_BLOCKED_LICENSE,
    VALIDATION_BLOCKED_SCHEMA,
    VALIDATION_BLOCKED_SOURCE_MISSING,
    VALIDATION_READY_FOR_IMPLEMENTATION,
    VALIDATION_REQUIRES_MANUAL_APPROVAL,
    P35DualSourceValidationSummary,
    P35GateResult,
    P35OddsLicenseValidationResult,
    P35PredictionRebuildFeasibilityResult,
)


# ---------------------------------------------------------------------------
# Phase guards
# ---------------------------------------------------------------------------


def test_paper_only_is_true():
    assert PAPER_ONLY is True


def test_production_ready_is_false():
    assert PRODUCTION_READY is False


# ---------------------------------------------------------------------------
# ALL_P35_GATES
# ---------------------------------------------------------------------------


def test_all_p35_gates_length():
    assert len(ALL_P35_GATES) == 8


def test_all_p35_gates_contains_all_constants():
    expected = {
        P35_DUAL_SOURCE_IMPORT_VALIDATION_READY,
        P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED,
        P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
        P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE,
        P35_BLOCKED_FEATURE_PIPELINE_MISSING,
        P35_BLOCKED_CONTRACT_VIOLATION,
        P35_FAIL_INPUT_MISSING,
        P35_FAIL_NON_DETERMINISTIC,
    }
    assert set(ALL_P35_GATES) == expected


def test_all_p35_gates_unique():
    assert len(ALL_P35_GATES) == len(set(ALL_P35_GATES))


# ---------------------------------------------------------------------------
# ALL_VALIDATION_STATUSES
# ---------------------------------------------------------------------------


def test_all_validation_statuses_length():
    assert len(ALL_VALIDATION_STATUSES) == 6


def test_all_validation_statuses_contains_all():
    expected = {
        VALIDATION_READY_FOR_IMPLEMENTATION,
        VALIDATION_REQUIRES_MANUAL_APPROVAL,
        VALIDATION_BLOCKED_LICENSE,
        VALIDATION_BLOCKED_SOURCE_MISSING,
        VALIDATION_BLOCKED_SCHEMA,
        VALIDATION_BLOCKED_LEAKAGE_RISK,
    }
    assert set(ALL_VALIDATION_STATUSES) == expected


def test_all_validation_statuses_unique():
    assert len(ALL_VALIDATION_STATUSES) == len(set(ALL_VALIDATION_STATUSES))


# ---------------------------------------------------------------------------
# ALL_FEASIBILITY_STATUSES
# ---------------------------------------------------------------------------


def test_all_feasibility_statuses_length():
    assert len(ALL_FEASIBILITY_STATUSES) == 5


def test_all_feasibility_statuses_contains_all():
    expected = {
        FEASIBILITY_READY,
        FEASIBILITY_BLOCKED_PIPELINE_MISSING,
        FEASIBILITY_BLOCKED_LEAKAGE_RISK,
        FEASIBILITY_BLOCKED_ADAPTER_MISSING,
        FEASIBILITY_REQUIRES_P36_IMPLEMENTATION,
    }
    assert set(ALL_FEASIBILITY_STATUSES) == expected


def test_all_feasibility_statuses_unique():
    assert len(ALL_FEASIBILITY_STATUSES) == len(set(ALL_FEASIBILITY_STATUSES))


# ---------------------------------------------------------------------------
# Required columns
# ---------------------------------------------------------------------------


def test_odds_required_columns_length():
    assert len(ODDS_REQUIRED_COLUMNS) == 11


def test_prediction_required_columns_length():
    assert len(PREDICTION_REQUIRED_COLUMNS) == 9


def test_odds_required_columns_contains_game_id():
    assert "game_id" in ODDS_REQUIRED_COLUMNS


def test_prediction_required_columns_contains_p_oof():
    assert "p_oof" in PREDICTION_REQUIRED_COLUMNS


def test_prediction_required_columns_contains_generated_without_y_true():
    assert "generated_without_y_true" in PREDICTION_REQUIRED_COLUMNS


# ---------------------------------------------------------------------------
# P35OddsLicenseValidationResult
# ---------------------------------------------------------------------------


def test_odds_license_result_is_frozen():
    result = P35OddsLicenseValidationResult(
        source_type="t",
        source_name="n",
        source_path_or_url="u",
        license_status="blocked_not_approved",
        provenance_status="p",
        schema_status="ok",
        leakage_risk="none",
        implementation_ready=False,
        blocker_reason="no approval",
    )
    with pytest.raises((TypeError, AttributeError)):
        result.paper_only = False  # type: ignore[misc]


def test_odds_license_result_paper_only_default():
    result = P35OddsLicenseValidationResult(
        source_type="t",
        source_name="n",
        source_path_or_url="u",
        license_status="blocked_not_approved",
        provenance_status="p",
        schema_status="ok",
        leakage_risk="none",
        implementation_ready=False,
        blocker_reason="no approval",
    )
    assert result.paper_only is True
    assert result.production_ready is False


def test_odds_license_result_implementation_ready_is_bool():
    result = P35OddsLicenseValidationResult(
        source_type="t",
        source_name="n",
        source_path_or_url="u",
        license_status="blocked_not_approved",
        provenance_status="p",
        schema_status="ok",
        leakage_risk="none",
        implementation_ready=False,
        blocker_reason="no approval",
    )
    assert isinstance(result.implementation_ready, bool)


# ---------------------------------------------------------------------------
# P35PredictionRebuildFeasibilityResult
# ---------------------------------------------------------------------------


def test_prediction_feasibility_result_is_frozen():
    result = P35PredictionRebuildFeasibilityResult(
        feature_pipeline_found=True,
        model_training_found=True,
        oof_generation_found=True,
        leakage_guard_found=True,
        time_aware_split_found=True,
        adapter_for_2024_format_found=False,
        feasibility_status=FEASIBILITY_BLOCKED_ADAPTER_MISSING,
        blocker_reason="no adapter",
    )
    with pytest.raises((TypeError, AttributeError)):
        result.paper_only = False  # type: ignore[misc]


def test_prediction_feasibility_result_paper_only_default():
    result = P35PredictionRebuildFeasibilityResult(
        feature_pipeline_found=True,
        model_training_found=True,
        oof_generation_found=True,
        leakage_guard_found=True,
        time_aware_split_found=True,
        adapter_for_2024_format_found=False,
        feasibility_status=FEASIBILITY_BLOCKED_ADAPTER_MISSING,
        blocker_reason="no adapter",
    )
    assert result.paper_only is True
    assert result.production_ready is False
    assert result.season == 2024


# ---------------------------------------------------------------------------
# P35DualSourceValidationSummary (mutable)
# ---------------------------------------------------------------------------


def test_dual_source_summary_is_mutable():
    summary = P35DualSourceValidationSummary(
        odds_license_status="blocked_not_approved",
        odds_source_status="source_not_provided",
        prediction_feasibility_status=FEASIBILITY_BLOCKED_ADAPTER_MISSING,
        feature_pipeline_status="found",
        validator_specs_written=True,
        gate="PENDING",
    )
    summary.gate = P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED
    assert summary.gate == P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED


def test_dual_source_summary_paper_only_default():
    summary = P35DualSourceValidationSummary(
        odds_license_status="x",
        odds_source_status="y",
        prediction_feasibility_status="z",
        feature_pipeline_status="found",
        validator_specs_written=True,
        gate="",
    )
    assert summary.paper_only is True
    assert summary.production_ready is False
    assert summary.season == 2024


# ---------------------------------------------------------------------------
# P35GateResult (mutable)
# ---------------------------------------------------------------------------


def test_gate_result_defaults():
    gate = P35GateResult(
        gate=P35_DUAL_SOURCE_IMPORT_VALIDATION_READY,
        odds_license_status="approved_internal_research",
        odds_source_status="approved",
        prediction_feasibility_status=FEASIBILITY_REQUIRES_P36_IMPLEMENTATION,
        feature_pipeline_status="found",
        blocker_reason="",
        license_risk="",
    )
    assert gate.paper_only is True
    assert gate.production_ready is False
    assert gate.season == 2024


def test_gate_result_is_mutable():
    gate = P35GateResult(
        gate=P35_DUAL_SOURCE_IMPORT_VALIDATION_READY,
        odds_license_status="x",
        odds_source_status="y",
        prediction_feasibility_status="z",
        feature_pipeline_status="found",
        blocker_reason="",
        license_risk="",
    )
    gate.gate = P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED
    assert gate.gate == P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED
