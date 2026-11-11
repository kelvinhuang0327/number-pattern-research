"""Tests for P35 odds license provenance validator."""
import json
import os
import tempfile

import pandas as pd
import pytest

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    LICENSE_APPROVED_INTERNAL_RESEARCH,
    LICENSE_BLOCKED_NOT_APPROVED,
    ODDS_REQUIRED_COLUMNS,
    VALIDATION_BLOCKED_LICENSE,
    VALIDATION_READY_FOR_IMPLEMENTATION,
)
from wbc_backend.recommendation.p35_odds_license_provenance_validator import (
    REQUIRED_APPROVAL_FIELDS,
    build_odds_import_validation_plan,
    build_odds_license_checklist,
    load_p34_odds_options,
    summarize_odds_license_validation,
    validate_manual_odds_source_approval,
    validate_odds_import_schema_template,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_approval_record(overrides: dict | None = None) -> dict:
    record = {
        "provider_name": "sportsbookreviewsonline.com",
        "license_terms_summary": "Free historical data for internal research",
        "allowed_use": "internal_research",
        "redistribution_allowed": False,
        "attribution_required": True,
        "approved_by": "test_user",
        "approved_at": "2026-01-01T00:00:00Z",
    }
    if overrides:
        record.update(overrides)
    return record


def _make_p34_options_file(path: str, options: list) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"options": options}, fh)


def _make_odds_template_csv(path: str, columns: list) -> None:
    pd.DataFrame(columns=columns).to_csv(path, index=False)


# ---------------------------------------------------------------------------
# load_p34_odds_options
# ---------------------------------------------------------------------------


def test_load_p34_odds_options_empty_if_missing():
    result = load_p34_odds_options("/nonexistent/path/missing.json")
    assert result == []


def test_load_p34_odds_options_empty_if_empty_path():
    result = load_p34_odds_options("")
    assert result == []


def test_load_p34_odds_options_loads_valid_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "odds_options.json")
        options = [
            {"option_id": "odds_r01", "source_name": "sportsbookreviewsonline.com"},
            {"option_id": "odds_r02", "source_name": "The Odds API"},
        ]
        _make_p34_options_file(path, options)
        result = load_p34_odds_options(path)
    assert len(result) == 2
    assert result[0]["option_id"] == "odds_r01"


def test_load_p34_odds_options_empty_on_malformed_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "bad.json")
        with open(path, "w") as fh:
            fh.write("{not valid json")
        result = load_p4_odds_options = load_p34_odds_options(path)
    assert result == []


# ---------------------------------------------------------------------------
# build_odds_license_checklist
# ---------------------------------------------------------------------------


def test_build_odds_license_checklist_returns_list():
    result = build_odds_license_checklist([])
    assert isinstance(result, list)


def test_build_odds_license_checklist_at_least_10_items():
    result = build_odds_license_checklist([])
    assert len(result) >= 10


def test_build_odds_license_checklist_mentions_tos():
    result = build_odds_license_checklist([])
    joined = " ".join(result).lower()
    assert "tos" in joined or "terms" in joined


def test_build_odds_license_checklist_adds_source_specific_items():
    options = [{"option_id": "odds_r01", "source_name": "sportsbookreviewsonline.com"}]
    result = build_odds_license_checklist(options)
    joined = " ".join(result)
    assert "odds_r01" in joined or "manually" in joined.lower()


def test_build_odds_license_checklist_api_source_item():
    options = [{"option_id": "odds_r02", "source_name": "The Odds API"}]
    result = build_odds_license_checklist(options)
    joined = " ".join(result)
    assert "odds_r02" in joined or "subscription" in joined.lower()


# ---------------------------------------------------------------------------
# validate_manual_odds_source_approval
# ---------------------------------------------------------------------------


def test_validate_approval_blocked_if_no_path():
    approved, reason, record = validate_manual_odds_source_approval(None)
    assert approved is False
    assert "No approval record" in reason
    assert record == {}


def test_validate_approval_blocked_if_path_missing():
    approved, reason, record = validate_manual_odds_source_approval("/nonexistent/record.json")
    assert approved is False
    assert "No approval record" in reason or "not found" in reason.lower()


def test_validate_approval_blocked_if_missing_required_fields():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "approval_record.json")
        partial = {"provider_name": "test", "allowed_use": "internal_research"}
        with open(path, "w") as fh:
            json.dump(partial, fh)
        approved, reason, record = validate_manual_odds_source_approval(path)
    assert approved is False
    assert "missing" in reason.lower()


def test_validate_approval_blocked_if_wrong_allowed_use():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "approval_record.json")
        rec = _make_approval_record({"allowed_use": "commercial_betting"})
        with open(path, "w") as fh:
            json.dump(rec, fh)
        approved, reason, _ = validate_manual_odds_source_approval(path)
    assert approved is False
    assert "allowed_use" in reason or "commercial" in reason.lower()


def test_validate_approval_approved_if_valid():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "approval_record.json")
        rec = _make_approval_record()
        with open(path, "w") as fh:
            json.dump(rec, fh)
        approved, reason, record = validate_manual_odds_source_approval(path)
    assert approved is True
    assert "valid" in reason.lower() or "approved" in reason.lower()
    assert record["provider_name"] == "sportsbookreviewsonline.com"


def test_validate_approval_blocked_on_malformed_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "bad.json")
        with open(path, "w") as fh:
            fh.write("{broken")
        approved, reason, record = validate_manual_odds_source_approval(path)
    assert approved is False
    assert record == {}


# ---------------------------------------------------------------------------
# validate_odds_import_schema_template
# ---------------------------------------------------------------------------


def test_validate_schema_fails_if_file_missing():
    valid, reason, missing = validate_odds_import_schema_template("/nonexistent/template.csv")
    assert valid is False
    assert len(missing) > 0


def test_validate_schema_fails_if_missing_columns():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "template.csv")
        partial_cols = ["game_id", "game_date"]  # only 2 of 11
        _make_odds_template_csv(path, partial_cols)
        valid, reason, missing = validate_odds_import_schema_template(path)
    assert valid is False
    assert len(missing) > 0


def test_validate_schema_passes_with_full_columns():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "template.csv")
        _make_odds_template_csv(path, list(ODDS_REQUIRED_COLUMNS))
        valid, reason, missing = validate_odds_import_schema_template(path)
    assert valid is True
    assert missing == []


def test_validate_schema_passes_with_extra_columns():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "template.csv")
        cols = list(ODDS_REQUIRED_COLUMNS) + ["extra_col", "another_col"]
        _make_odds_template_csv(path, cols)
        valid, reason, missing = validate_odds_import_schema_template(path)
    assert valid is True


# ---------------------------------------------------------------------------
# summarize_odds_license_validation
# ---------------------------------------------------------------------------


def test_summarize_blocked_without_approval():
    result = summarize_odds_license_validation(
        approval_approved=False,
        approval_reason="No approval record",
        schema_valid=True,
        schema_reason="ok",
        schema_missing_cols=[],
        checklist_items=["item1", "item2"],
        odds_options=[],
    )
    assert result.implementation_ready is False
    assert result.license_status == LICENSE_BLOCKED_NOT_APPROVED
    assert result.paper_only is True
    assert result.production_ready is False


def test_summarize_paper_only_enforced():
    result = summarize_odds_license_validation(
        approval_approved=True,
        approval_reason="valid",
        schema_valid=True,
        schema_reason="ok",
        schema_missing_cols=[],
        checklist_items=[],
        odds_options=[],
    )
    assert result.paper_only is True
    assert result.production_ready is False


def test_summarize_no_scraping_in_notes():
    result = summarize_odds_license_validation(
        approval_approved=False,
        approval_reason="No record",
        schema_valid=False,
        schema_reason="missing",
        schema_missing_cols=["game_id"],
        checklist_items=[],
        odds_options=[],
    )
    # Notes must warn against scraping, never suggest it
    notes_lower = result.notes.lower()
    assert "do not scrape" in notes_lower or "not scrape" in notes_lower


def test_summarize_approved_and_schema_valid_returns_ready():
    result = summarize_odds_license_validation(
        approval_approved=True,
        approval_reason="valid",
        schema_valid=True,
        schema_reason="ok",
        schema_missing_cols=[],
        checklist_items=["check1"],
        odds_options=[],
    )
    assert result.implementation_ready is True
    assert result.license_status == LICENSE_APPROVED_INTERNAL_RESEARCH


# ---------------------------------------------------------------------------
# build_odds_import_validation_plan
# ---------------------------------------------------------------------------


def test_build_plan_blocked_when_not_approved():
    from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
        P35OddsLicenseValidationResult,
    )
    blocked_result = P35OddsLicenseValidationResult(
        source_type="t",
        source_name="sportsbookreviewsonline.com",
        source_path_or_url="https://example.com",
        license_status=LICENSE_BLOCKED_NOT_APPROVED,
        provenance_status="external",
        schema_status="valid",
        leakage_risk="none",
        implementation_ready=False,
        blocker_reason="No approval",
    )
    plan = build_odds_import_validation_plan([], blocked_result)
    assert plan.approved is False
    assert plan.validation_status == VALIDATION_BLOCKED_LICENSE


def test_build_plan_ready_when_approved_and_schema_valid():
    from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
        P35OddsLicenseValidationResult,
    )
    approved_result = P35OddsLicenseValidationResult(
        source_type="t",
        source_name="sportsbookreviewsonline.com",
        source_path_or_url="https://example.com",
        license_status=LICENSE_APPROVED_INTERNAL_RESEARCH,
        provenance_status="external",
        schema_status="valid",
        leakage_risk="none",
        implementation_ready=True,
        blocker_reason="",
    )
    plan = build_odds_import_validation_plan([], approved_result)
    assert plan.approved is True
    assert plan.validation_status == VALIDATION_READY_FOR_IMPLEMENTATION


def test_build_plan_paper_only():
    from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
        P35OddsLicenseValidationResult,
    )
    result = P35OddsLicenseValidationResult(
        source_type="t",
        source_name="n",
        source_path_or_url="u",
        license_status=LICENSE_BLOCKED_NOT_APPROVED,
        provenance_status="p",
        schema_status="ok",
        leakage_risk="none",
        implementation_ready=False,
        blocker_reason="no",
    )
    plan = build_odds_import_validation_plan([], result)
    assert plan.paper_only is True
    assert plan.production_ready is False
