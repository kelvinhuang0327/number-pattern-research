"""Tests for P36 odds approval record validator."""
import json
import os
import tempfile

import pytest

from wbc_backend.recommendation.p36_odds_approval_contract import (
    APPROVAL_BLOCKED_LICENSE,
    APPROVAL_BLOCKED_PROVENANCE,
    APPROVAL_INVALID,
    APPROVAL_MISSING,
    APPROVAL_READY,
    APPROVAL_RECORD_REQUIRED_FIELDS,
    PAPER_ONLY,
    PRODUCTION_READY,
)
from wbc_backend.recommendation.p36_odds_approval_record_validator import (
    load_approval_record,
    summarize_approval_validation,
    validate_allowed_use,
    validate_approval_record,
    validate_redistribution_policy,
    validate_required_approver,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_RECORD = {
    "provider_name": "SBR",
    "source_name": "sportsbookreviewsonline.com",
    "source_url_or_reference": "https://www.sportsbookreviewsonline.com/",
    "license_terms_summary": "Free for personal/research use; no redistribution.",
    "allowed_use": "internal_research",
    "redistribution_allowed": False,
    "attribution_required": True,
    "internal_research_allowed": True,
    "commercial_use_allowed": False,
    "approved_by": "researcher_01",
    "approved_at": "2026-05-01",
    "approval_scope": "2024_season_historical",
    "source_file_expected_path": "data/mlb_2024/manual_import/odds_2024_approved.csv",
    "checksum_required": False,
    "paper_only": True,
    "production_ready": False,
}


def _write_approval_record(tmp_dir: str, record: dict) -> str:
    path = os.path.join(tmp_dir, "approval_record.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh)
    return path


# ---------------------------------------------------------------------------
# load_approval_record
# ---------------------------------------------------------------------------


def test_load_approval_record_none_returns_none():
    assert load_approval_record(None) is None


def test_load_approval_record_missing_file_returns_none():
    assert load_approval_record("/nonexistent/path/approval.json") is None


def test_load_approval_record_valid_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_approval_record(tmp, _VALID_RECORD)
        result = load_approval_record(path)
    assert isinstance(result, dict)
    assert result["provider_name"] == "SBR"


def test_load_approval_record_malformed_json_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "bad.json")
        with open(path, "w") as fh:
            fh.write("{not valid json}")
        result = load_approval_record(path)
    assert result is None


def test_load_approval_record_non_dict_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "list.json")
        with open(path, "w") as fh:
            json.dump([1, 2, 3], fh)
        result = load_approval_record(path)
    assert result is None


# ---------------------------------------------------------------------------
# validate_approval_record
# ---------------------------------------------------------------------------


def test_validate_approval_record_none_returns_invalid():
    valid, reason, missing = validate_approval_record(None)
    assert valid is False
    assert len(missing) == len(APPROVAL_RECORD_REQUIRED_FIELDS)


def test_validate_approval_record_complete_passes():
    valid, reason, missing = validate_approval_record(_VALID_RECORD)
    assert valid is True
    assert missing == []


def test_validate_approval_record_missing_fields():
    partial = {k: v for k, v in _VALID_RECORD.items() if k not in ("approved_by", "approved_at")}
    valid, reason, missing = validate_approval_record(partial)
    assert valid is False
    assert "approved_by" in missing
    assert "approved_at" in missing


# ---------------------------------------------------------------------------
# validate_allowed_use
# ---------------------------------------------------------------------------


def test_validate_allowed_use_internal_research_passes():
    valid, reason = validate_allowed_use({"allowed_use": "internal_research"})
    assert valid is True


def test_validate_allowed_use_research_passes():
    valid, reason = validate_allowed_use({"allowed_use": "research"})
    assert valid is True


def test_validate_allowed_use_commercial_fails():
    valid, reason = validate_allowed_use({"allowed_use": "commercial"})
    assert valid is False


def test_validate_allowed_use_empty_fails():
    valid, reason = validate_allowed_use({"allowed_use": ""})
    assert valid is False


# ---------------------------------------------------------------------------
# validate_redistribution_policy
# ---------------------------------------------------------------------------


def test_redistribution_false_surfaces_risk():
    allowed, note = validate_redistribution_policy({"redistribution_allowed": False})
    assert allowed is False
    assert "must NEVER be committed" in note


def test_redistribution_true_no_risk():
    allowed, note = validate_redistribution_policy({"redistribution_allowed": True})
    assert allowed is True


# ---------------------------------------------------------------------------
# validate_required_approver
# ---------------------------------------------------------------------------


def test_validate_approver_all_present():
    valid, reason = validate_required_approver(_VALID_RECORD)
    assert valid is True


def test_validate_approver_missing_approved_by():
    record = dict(_VALID_RECORD, approved_by="")
    valid, reason = validate_required_approver(record)
    assert valid is False
    assert "approved_by" in reason


def test_validate_approver_missing_approved_at():
    record = dict(_VALID_RECORD, approved_at="")
    valid, reason = validate_required_approver(record)
    assert valid is False
    assert "approved_at" in reason


def test_validate_approver_missing_source_path():
    record = dict(_VALID_RECORD, source_file_expected_path="")
    valid, reason = validate_required_approver(record)
    assert valid is False
    assert "source_file_expected_path" in reason


# ---------------------------------------------------------------------------
# summarize_approval_validation — APPROVAL_MISSING
# ---------------------------------------------------------------------------


def test_summarize_missing_record_returns_missing():
    result = summarize_approval_validation(None)
    assert result.approval_status == APPROVAL_MISSING
    assert result.approval_record_found is False
    assert result.paper_only is True
    assert result.production_ready is False


# ---------------------------------------------------------------------------
# summarize_approval_validation — APPROVAL_INVALID
# ---------------------------------------------------------------------------


def test_summarize_missing_approved_by_returns_invalid():
    record = dict(_VALID_RECORD, approved_by="")
    result = summarize_approval_validation(record)
    assert result.approval_status == APPROVAL_INVALID


def test_summarize_missing_fields_returns_invalid():
    record = {k: v for k, v in _VALID_RECORD.items() if k != "approved_by"}
    result = summarize_approval_validation(record)
    assert result.approval_status == APPROVAL_INVALID


# ---------------------------------------------------------------------------
# summarize_approval_validation — APPROVAL_BLOCKED_LICENSE
# ---------------------------------------------------------------------------


def test_summarize_internal_research_false_returns_blocked():
    record = dict(_VALID_RECORD, internal_research_allowed=False)
    result = summarize_approval_validation(record)
    assert result.approval_status == APPROVAL_BLOCKED_LICENSE
    assert result.internal_research_allowed is False


def test_summarize_wrong_allowed_use_returns_blocked():
    record = dict(_VALID_RECORD, allowed_use="commercial")
    result = summarize_approval_validation(record)
    assert result.approval_status == APPROVAL_BLOCKED_LICENSE


# ---------------------------------------------------------------------------
# summarize_approval_validation — APPROVAL_BLOCKED_PROVENANCE
# ---------------------------------------------------------------------------


def test_summarize_paper_only_false_in_record_returns_blocked_provenance():
    record = dict(_VALID_RECORD, paper_only=False)
    result = summarize_approval_validation(record)
    assert result.approval_status == APPROVAL_BLOCKED_PROVENANCE


def test_summarize_production_ready_true_in_record_returns_blocked_provenance():
    record = dict(_VALID_RECORD, production_ready=True)
    result = summarize_approval_validation(record)
    assert result.approval_status == APPROVAL_BLOCKED_PROVENANCE


# ---------------------------------------------------------------------------
# summarize_approval_validation — APPROVAL_READY
# ---------------------------------------------------------------------------


def test_summarize_valid_record_returns_ready():
    result = summarize_approval_validation(_VALID_RECORD)
    assert result.approval_status == APPROVAL_READY
    assert result.internal_research_allowed is True
    assert result.paper_only is True
    assert result.production_ready is False


def test_summarize_paper_only_always_enforced():
    """Module-level PAPER_ONLY=True must always appear in result regardless of record."""
    record = dict(_VALID_RECORD, paper_only=False)  # record says False
    result = summarize_approval_validation(record)
    # Module level forces True
    assert result.paper_only is True


def test_summarize_production_ready_always_false():
    """Module-level PRODUCTION_READY=False must appear in result regardless of record."""
    result = summarize_approval_validation(_VALID_RECORD)
    assert result.production_ready is False
