"""Tests for P36 odds import gate planner."""
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
    SEASON,
    P36_BLOCKED_APPROVAL_RECORD_INVALID,
    P36_BLOCKED_APPROVAL_RECORD_MISSING,
    P36_BLOCKED_CONTRACT_VIOLATION,
    P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH,
    P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
    P36_ODDS_APPROVAL_RECORD_READY,
    P36OddsApprovalValidationResult,
)
from wbc_backend.recommendation.p36_odds_import_gate_planner import (
    build_odds_import_gate_plan,
    determine_p36_gate,
    validate_p36_gate_plan,
    write_p36_outputs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_approval_result(
    status: str = APPROVAL_READY,
    internal_research_allowed: bool = True,
    allowed_use_valid: bool = True,
    approved_by_present: bool = True,
    approved_at_present: bool = True,
    source_file_path_present: bool = True,
    blocker_reason: str = "",
    missing_fields: tuple = (),
    redistribution_allowed: bool = False,
) -> P36OddsApprovalValidationResult:
    return P36OddsApprovalValidationResult(
        approval_status=status,
        approval_record_found=(status != APPROVAL_MISSING),
        all_required_fields_present=(len(missing_fields) == 0),
        internal_research_allowed=internal_research_allowed,
        allowed_use_valid=allowed_use_valid,
        approved_by_present=approved_by_present,
        approved_at_present=approved_at_present,
        source_file_path_present=source_file_path_present,
        paper_only=PAPER_ONLY,
        production_ready=PRODUCTION_READY,
        redistribution_allowed=redistribution_allowed,
        redistribution_risk_note="Raw odds must NEVER be committed." if not redistribution_allowed else "",
        blocker_reason=blocker_reason,
        missing_fields=missing_fields,
    )


def _make_manual_import_provided(valid: bool = True) -> dict:
    return {
        "file_provided": True,
        "schema_valid": valid,
        "coverage_valid": valid,
        "leakage_clean": valid,
        "overall_valid": valid,
        "status": "VALID" if valid else "INVALID",
        "issues": [] if valid else ["schema error"],
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "season": SEASON,
    }


def _make_manual_import_not_provided() -> dict:
    return {
        "file_provided": False,
        "status": "NO_FILE",
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "season": SEASON,
    }


# ---------------------------------------------------------------------------
# build_odds_import_gate_plan
# ---------------------------------------------------------------------------


def test_build_plan_missing_record():
    approval = _make_approval_result(status=APPROVAL_MISSING, internal_research_allowed=False)
    plan = build_odds_import_gate_plan(approval, None)
    assert plan["approval_status"] == APPROVAL_MISSING
    assert plan["paper_only"] is True
    assert plan["production_ready"] is False
    assert plan["season"] == SEASON


def test_build_plan_file_provided_reflected():
    approval = _make_approval_result(status=APPROVAL_READY)
    manual = _make_manual_import_provided(valid=True)
    plan = build_odds_import_gate_plan(approval, manual)
    assert plan["manual_import_file_provided"] is True
    assert plan["manual_import_overall_valid"] is True


def test_build_plan_no_file_provided():
    approval = _make_approval_result(status=APPROVAL_READY)
    plan = build_odds_import_gate_plan(approval, None)
    assert plan["manual_import_file_provided"] is False


# ---------------------------------------------------------------------------
# determine_p36_gate — gate decisions
# ---------------------------------------------------------------------------


def test_gate_missing_record():
    approval = _make_approval_result(status=APPROVAL_MISSING, internal_research_allowed=False)
    plan = build_odds_import_gate_plan(approval, None)
    gate = determine_p36_gate(plan)
    assert gate.gate == P36_BLOCKED_APPROVAL_RECORD_MISSING
    assert gate.raw_odds_commit_allowed is False


def test_gate_invalid_record():
    approval = _make_approval_result(
        status=APPROVAL_INVALID,
        internal_research_allowed=False,
        allowed_use_valid=False,
        blocker_reason="missing fields",
    )
    plan = build_odds_import_gate_plan(approval, None)
    gate = determine_p36_gate(plan)
    assert gate.gate == P36_BLOCKED_APPROVAL_RECORD_INVALID
    assert gate.raw_odds_commit_allowed is False


def test_gate_internal_research_not_allowed():
    approval = _make_approval_result(
        status=APPROVAL_BLOCKED_LICENSE,
        internal_research_allowed=False,
        allowed_use_valid=False,
    )
    plan = build_odds_import_gate_plan(approval, None)
    gate = determine_p36_gate(plan)
    assert gate.gate == P36_BLOCKED_LICENSE_NOT_ALLOWED_FOR_RESEARCH
    assert gate.raw_odds_commit_allowed is False


def test_gate_approval_valid_but_no_source():
    approval = _make_approval_result(status=APPROVAL_READY)
    plan = build_odds_import_gate_plan(approval, None)
    gate = determine_p36_gate(plan)
    assert gate.gate == P36_BLOCKED_ODDS_SOURCE_NOT_PROVIDED
    assert gate.raw_odds_commit_allowed is False


def test_gate_ready_when_all_valid():
    approval = _make_approval_result(status=APPROVAL_READY)
    manual = _make_manual_import_provided(valid=True)
    plan = build_odds_import_gate_plan(approval, manual)
    gate = determine_p36_gate(plan)
    assert gate.gate == P36_ODDS_APPROVAL_RECORD_READY
    assert gate.raw_odds_commit_allowed is False  # always False


def test_gate_contract_violation_production_ready():
    approval = _make_approval_result(status=APPROVAL_READY)
    manual = _make_manual_import_provided(valid=True)
    plan = build_odds_import_gate_plan(approval, manual)
    plan["production_ready"] = True  # inject violation
    gate = determine_p36_gate(plan)
    assert gate.gate == P36_BLOCKED_CONTRACT_VIOLATION


def test_gate_contract_violation_paper_only_false():
    approval = _make_approval_result(status=APPROVAL_READY)
    manual = _make_manual_import_provided(valid=True)
    plan = build_odds_import_gate_plan(approval, manual)
    plan["paper_only"] = False  # inject violation
    gate = determine_p36_gate(plan)
    assert gate.gate == P36_BLOCKED_CONTRACT_VIOLATION


def test_gate_raw_odds_commit_always_false_when_ready():
    """Even when gate=READY, raw_odds_commit_allowed must be False."""
    approval = _make_approval_result(status=APPROVAL_READY)
    manual = _make_manual_import_provided(valid=True)
    plan = build_odds_import_gate_plan(approval, manual)
    gate = determine_p36_gate(plan)
    assert gate.gate == P36_ODDS_APPROVAL_RECORD_READY
    assert gate.raw_odds_commit_allowed is False


# ---------------------------------------------------------------------------
# validate_p36_gate_plan
# ---------------------------------------------------------------------------


def test_validate_gate_plan_passes():
    approval = _make_approval_result(status=APPROVAL_READY)
    plan = build_odds_import_gate_plan(approval, None)
    assert validate_p36_gate_plan(plan) is True


def test_validate_gate_plan_fails_production_ready():
    approval = _make_approval_result(status=APPROVAL_READY)
    plan = build_odds_import_gate_plan(approval, None)
    plan["production_ready"] = True
    assert validate_p36_gate_plan(plan) is False


def test_validate_gate_plan_fails_paper_only_false():
    approval = _make_approval_result(status=APPROVAL_READY)
    plan = build_odds_import_gate_plan(approval, None)
    plan["paper_only"] = False
    assert validate_p36_gate_plan(plan) is False


def test_validate_gate_plan_fails_wrong_season():
    approval = _make_approval_result(status=APPROVAL_READY)
    plan = build_odds_import_gate_plan(approval, None)
    plan["season"] = 2023
    assert validate_p36_gate_plan(plan) is False


# ---------------------------------------------------------------------------
# write_p36_outputs
# ---------------------------------------------------------------------------


def _standard_schema_dict() -> dict:
    from wbc_backend.recommendation.p36_manual_odds_import_validator import (
        build_manual_odds_import_schema,
    )
    spec = build_manual_odds_import_schema()
    return {
        "required_columns": list(spec.required_columns),
        "forbidden_columns": list(spec.forbidden_columns),
        "allowed_market_types": list(spec.allowed_market_types),
        "p_market_range": list(spec.p_market_range),
        "odds_decimal_min": spec.odds_decimal_min,
        "paper_only": spec.paper_only,
        "production_ready": spec.production_ready,
        "notes": spec.notes,
        "season": spec.season,
    }


def test_write_p36_outputs_creates_all_6_files():
    approval = _make_approval_result(status=APPROVAL_MISSING, internal_research_allowed=False)
    plan = build_odds_import_gate_plan(approval, None)
    gate = determine_p36_gate(plan)
    schema = _standard_schema_dict()
    with tempfile.TemporaryDirectory() as tmp:
        written = write_p36_outputs(tmp, gate, approval, schema, None, plan)
        files = {os.path.basename(p) for p in written}
        for expected_file in (
            "odds_approval_validation.json",
            "manual_odds_import_schema.json",
            "manual_odds_import_validation.json",
            "odds_import_gate_plan.json",
            "odds_import_gate_plan.md",
            "p36_gate_result.json",
        ):
            assert expected_file in files, f"{expected_file} not written"


def test_write_p36_outputs_gate_result_has_correct_gate():
    approval = _make_approval_result(status=APPROVAL_MISSING, internal_research_allowed=False)
    plan = build_odds_import_gate_plan(approval, None)
    gate = determine_p36_gate(plan)
    schema = _standard_schema_dict()
    with tempfile.TemporaryDirectory() as tmp:
        write_p36_outputs(tmp, gate, approval, schema, None, plan)
        gate_path = os.path.join(tmp, "p36_gate_result.json")
        with open(gate_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["gate"] == P36_BLOCKED_APPROVAL_RECORD_MISSING
        assert data["raw_odds_commit_allowed"] is False
        assert data["paper_only"] is True
        assert data["production_ready"] is False


def test_write_p36_outputs_deterministic():
    approval = _make_approval_result(status=APPROVAL_MISSING, internal_research_allowed=False)
    plan = build_odds_import_gate_plan(approval, None)
    schema = _standard_schema_dict()
    exclude = frozenset({"generated_at", "output_dir", "artifacts"})
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        gate1 = determine_p36_gate(plan)
        write_p36_outputs(t1, gate1, approval, schema, None, dict(plan))
        gate2 = determine_p36_gate(plan)
        write_p36_outputs(t2, gate2, approval, schema, None, dict(plan))
        for fname in ("p36_gate_result.json",):
            with open(os.path.join(t1, fname), encoding="utf-8") as fh:
                d1 = {k: v for k, v in json.load(fh).items() if k not in exclude}
            with open(os.path.join(t2, fname), encoding="utf-8") as fh:
                d2 = {k: v for k, v in json.load(fh).items() if k not in exclude}
            assert d1 == d2, f"Non-determinism in {fname}"
