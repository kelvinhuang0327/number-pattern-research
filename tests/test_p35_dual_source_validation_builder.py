"""Tests for P35 dual source validation builder."""
import json
import os
import tempfile

import pytest

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    FEASIBILITY_BLOCKED_ADAPTER_MISSING,
    FEASIBILITY_BLOCKED_PIPELINE_MISSING,
    FEASIBILITY_REQUIRES_P36_IMPLEMENTATION,
    LICENSE_APPROVED_INTERNAL_RESEARCH,
    LICENSE_BLOCKED_NOT_APPROVED,
    P35_BLOCKED_CONTRACT_VIOLATION,
    P35_BLOCKED_FEATURE_PIPELINE_MISSING,
    P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED,
    P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE,
    P35_DUAL_SOURCE_IMPORT_VALIDATION_READY,
    VALIDATION_READY_FOR_IMPLEMENTATION,
    P35DualSourceValidationSummary,
    P35GateResult,
    P35OddsLicenseValidationResult,
    P35PredictionRebuildFeasibilityResult,
)
from wbc_backend.recommendation.p35_dual_source_validation_builder import (
    build_dual_source_validation_summary,
    determine_p35_gate,
    validate_p35_summary,
    write_p35_outputs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_odds_blocked() -> P35OddsLicenseValidationResult:
    return P35OddsLicenseValidationResult(
        source_type="licensed_export",
        source_name="sportsbookreviewsonline.com",
        source_path_or_url="https://example.com",
        license_status=LICENSE_BLOCKED_NOT_APPROVED,
        provenance_status="external_public_archive",
        schema_status="valid",
        leakage_risk="none",
        implementation_ready=False,
        blocker_reason="No approval record",
        paper_only=True,
        production_ready=False,
        season=2024,
        checklist_items=("check1",),
        approval_record_found=False,
        notes="Do NOT scrape odds.",
    )


def _make_odds_approved() -> P35OddsLicenseValidationResult:
    return P35OddsLicenseValidationResult(
        source_type="licensed_export",
        source_name="sportsbookreviewsonline.com",
        source_path_or_url="https://example.com",
        license_status=LICENSE_APPROVED_INTERNAL_RESEARCH,
        provenance_status="external_public_archive",
        schema_status="valid",
        leakage_risk="none",
        implementation_ready=True,
        blocker_reason="",
        paper_only=True,
        production_ready=False,
        season=2024,
        checklist_items=(),
        approval_record_found=True,
        notes="Do NOT scrape odds.",
    )


def _make_pred_adapter_missing() -> P35PredictionRebuildFeasibilityResult:
    return P35PredictionRebuildFeasibilityResult(
        feature_pipeline_found=True,
        model_training_found=True,
        oof_generation_found=True,
        leakage_guard_found=True,
        time_aware_split_found=True,
        adapter_for_2024_format_found=False,
        feasibility_status=FEASIBILITY_BLOCKED_ADAPTER_MISSING,
        blocker_reason="No 2024 adapter",
    )


def _make_pred_pipeline_missing() -> P35PredictionRebuildFeasibilityResult:
    return P35PredictionRebuildFeasibilityResult(
        feature_pipeline_found=False,
        model_training_found=False,
        oof_generation_found=False,
        leakage_guard_found=False,
        time_aware_split_found=False,
        adapter_for_2024_format_found=False,
        feasibility_status=FEASIBILITY_BLOCKED_PIPELINE_MISSING,
        blocker_reason="No pipeline found",
    )


def _make_pred_ready() -> P35PredictionRebuildFeasibilityResult:
    return P35PredictionRebuildFeasibilityResult(
        feature_pipeline_found=True,
        model_training_found=True,
        oof_generation_found=True,
        leakage_guard_found=True,
        time_aware_split_found=True,
        adapter_for_2024_format_found=True,
        feasibility_status=FEASIBILITY_REQUIRES_P36_IMPLEMENTATION,
        blocker_reason="",
    )


# ---------------------------------------------------------------------------
# determine_p35_gate — blocked odds license
# ---------------------------------------------------------------------------


def test_gate_blocked_odds_license_not_approved():
    odds = _make_odds_blocked()
    pred = _make_pred_adapter_missing()
    summary = build_dual_source_validation_summary(odds, pred, True)
    gate = determine_p35_gate(summary)
    assert gate.gate == P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED


# ---------------------------------------------------------------------------
# determine_p35_gate — contract violation
# ---------------------------------------------------------------------------


def test_gate_blocked_contract_violation_if_production_ready():
    summary = P35DualSourceValidationSummary(
        odds_license_status="x",
        odds_source_status="y",
        prediction_feasibility_status="z",
        feature_pipeline_status="found",
        validator_specs_written=True,
        gate="",
        production_ready=True,
    )
    gate = determine_p35_gate(summary)
    assert gate.gate == P35_BLOCKED_CONTRACT_VIOLATION


def test_gate_blocked_contract_violation_if_paper_only_false():
    summary = P35DualSourceValidationSummary(
        odds_license_status="x",
        odds_source_status="y",
        prediction_feasibility_status="z",
        feature_pipeline_status="found",
        validator_specs_written=True,
        gate="",
        paper_only=False,
    )
    gate = determine_p35_gate(summary)
    assert gate.gate == P35_BLOCKED_CONTRACT_VIOLATION


# ---------------------------------------------------------------------------
# determine_p35_gate — feature pipeline missing
# ---------------------------------------------------------------------------


def test_gate_blocked_feature_pipeline_missing():
    odds = _make_odds_approved()
    pred = _make_pred_pipeline_missing()
    summary = build_dual_source_validation_summary(odds, pred, True)
    gate = determine_p35_gate(summary)
    assert gate.gate == P35_BLOCKED_FEATURE_PIPELINE_MISSING


# ---------------------------------------------------------------------------
# determine_p35_gate — ready
# ---------------------------------------------------------------------------


def test_gate_ready_when_all_unblocked():
    odds = _make_odds_approved()
    pred = _make_pred_ready()
    summary = build_dual_source_validation_summary(odds, pred, True)
    gate = determine_p35_gate(summary)
    assert gate.gate == P35_DUAL_SOURCE_IMPORT_VALIDATION_READY


# ---------------------------------------------------------------------------
# validate_p35_summary
# ---------------------------------------------------------------------------


def test_validate_summary_false_if_production_ready():
    summary = P35DualSourceValidationSummary(
        odds_license_status="x",
        odds_source_status="y",
        prediction_feasibility_status="z",
        feature_pipeline_status="found",
        validator_specs_written=True,
        gate="",
        production_ready=True,
    )
    assert validate_p35_summary(summary) is False


def test_validate_summary_false_if_paper_only_false():
    summary = P35DualSourceValidationSummary(
        odds_license_status="x",
        odds_source_status="y",
        prediction_feasibility_status="z",
        feature_pipeline_status="found",
        validator_specs_written=True,
        gate="",
        paper_only=False,
    )
    assert validate_p35_summary(summary) is False


def test_validate_summary_false_if_wrong_season():
    summary = P35DualSourceValidationSummary(
        odds_license_status="x",
        odds_source_status="y",
        prediction_feasibility_status="z",
        feature_pipeline_status="found",
        validator_specs_written=True,
        gate="",
        season=2025,
    )
    assert validate_p35_summary(summary) is False


def test_validate_summary_true_for_valid_summary():
    odds = _make_odds_blocked()
    pred = _make_pred_adapter_missing()
    summary = build_dual_source_validation_summary(odds, pred, True)
    assert validate_p35_summary(summary) is True


# ---------------------------------------------------------------------------
# write_p35_outputs
# ---------------------------------------------------------------------------


def test_write_p35_outputs_writes_five_expected_files():
    odds = _make_odds_blocked()
    pred = _make_pred_adapter_missing()
    summary = build_dual_source_validation_summary(odds, pred, True)
    gate = determine_p35_gate(summary)

    with tempfile.TemporaryDirectory() as tmp:
        written = write_p35_outputs(tmp, summary, gate, odds, pred, [])
        written_basenames = {os.path.basename(p) for p in written}
        for expected in (
            "odds_license_validation.json",
            "prediction_rebuild_feasibility.json",
            "dual_source_validation_summary.json",
            "dual_source_validation_summary.md",
            "p35_gate_result.json",
        ):
            assert expected in written_basenames, f"Missing: {expected}"


def test_write_p35_outputs_gate_result_has_correct_gate():
    odds = _make_odds_blocked()
    pred = _make_pred_adapter_missing()
    summary = build_dual_source_validation_summary(odds, pred, True)
    gate = determine_p35_gate(summary)

    with tempfile.TemporaryDirectory() as tmp:
        write_p35_outputs(tmp, summary, gate, odds, pred, [])
        gate_path = os.path.join(tmp, "p35_gate_result.json")
        with open(gate_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["gate"] == P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED


def test_write_p35_outputs_deterministic():
    """Two writes with same inputs (excluding generated_at/output_dir) must match."""
    odds = _make_odds_blocked()
    pred = _make_pred_adapter_missing()
    summary = build_dual_source_validation_summary(odds, pred, True)
    gate = determine_p35_gate(summary)

    with tempfile.TemporaryDirectory() as tmp1:
        write_p35_outputs(tmp1, summary, gate, odds, pred, [])
        with open(os.path.join(tmp1, "p35_gate_result.json"), encoding="utf-8") as fh:
            d1 = json.load(fh)

    with tempfile.TemporaryDirectory() as tmp2:
        write_p35_outputs(tmp2, summary, gate, odds, pred, [])
        with open(os.path.join(tmp2, "p35_gate_result.json"), encoding="utf-8") as fh:
            d2 = json.load(fh)

    exclude = {"generated_at", "output_dir", "artifacts"}
    for k in set(d1) | set(d2):
        if k in exclude:
            continue
        assert d1.get(k) == d2.get(k), f"Determinism failure at key={k}: {d1.get(k)} vs {d2.get(k)}"
