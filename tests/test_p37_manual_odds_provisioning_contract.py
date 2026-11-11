"""
Tests for p37_manual_odds_provisioning_contract.py
"""
import pytest
from wbc_backend.recommendation.p37_manual_odds_provisioning_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    SEASON,
    ALL_P37_GATES,
    ALL_P37_STATUSES,
    APPROVAL_RECORD_TEMPLATE_FIELDS,
    MANUAL_ODDS_TEMPLATE_COLUMNS,
    P37_OUTPUT_FILES,
    P37ApprovalRecordTemplate,
    P37ManualOddsTemplate,
    P37ProvisioningChecklist,
    P37ManualOddsProvisioningGate,
    P37GateResult,
)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

class TestModuleGuards:
    def test_paper_only_is_true(self):
        assert PAPER_ONLY is True

    def test_production_ready_is_false(self):
        assert PRODUCTION_READY is False

    def test_season_is_2024(self):
        assert SEASON == 2024


class TestGateConstants:
    def test_all_p37_gates_count(self):
        assert len(ALL_P37_GATES) == 10

    def test_gate_ready_exists(self):
        assert "P37_MANUAL_ODDS_PROVISIONING_GATE_READY" in ALL_P37_GATES

    def test_gate_blocked_approval_missing(self):
        assert "P37_BLOCKED_APPROVAL_RECORD_MISSING" in ALL_P37_GATES

    def test_gate_blocked_approval_invalid(self):
        assert "P37_BLOCKED_APPROVAL_RECORD_INVALID" in ALL_P37_GATES

    def test_gate_blocked_license(self):
        assert "P37_BLOCKED_LICENSE_NOT_APPROVED" in ALL_P37_GATES

    def test_gate_blocked_odds_missing(self):
        assert "P37_BLOCKED_MANUAL_ODDS_FILE_MISSING" in ALL_P37_GATES

    def test_gate_blocked_schema(self):
        assert "P37_BLOCKED_MANUAL_ODDS_SCHEMA_INVALID" in ALL_P37_GATES

    def test_gate_blocked_raw_commit(self):
        assert "P37_BLOCKED_RAW_ODDS_COMMIT_RISK" in ALL_P37_GATES

    def test_gate_blocked_contract(self):
        assert "P37_BLOCKED_CONTRACT_VIOLATION" in ALL_P37_GATES

    def test_gate_fail_input(self):
        assert "P37_FAIL_INPUT_MISSING" in ALL_P37_GATES

    def test_gate_fail_determinism(self):
        assert "P37_FAIL_NON_DETERMINISTIC" in ALL_P37_GATES


class TestStatusConstants:
    def test_all_statuses_count(self):
        assert len(ALL_P37_STATUSES) == 8

    def test_template_ready_exists(self):
        assert "TEMPLATE_READY" in ALL_P37_STATUSES

    def test_approval_required_exists(self):
        assert "APPROVAL_REQUIRED" in ALL_P37_STATUSES

    def test_approval_valid_exists(self):
        assert "APPROVAL_VALID" in ALL_P37_STATUSES

    def test_approval_invalid_exists(self):
        assert "APPROVAL_INVALID" in ALL_P37_STATUSES

    def test_manual_odds_required_exists(self):
        assert "MANUAL_ODDS_REQUIRED" in ALL_P37_STATUSES

    def test_manual_odds_valid_exists(self):
        assert "MANUAL_ODDS_VALID" in ALL_P37_STATUSES

    def test_manual_odds_invalid_exists(self):
        assert "MANUAL_ODDS_INVALID" in ALL_P37_STATUSES

    def test_raw_commit_blocked_exists(self):
        assert "RAW_COMMIT_BLOCKED" in ALL_P37_STATUSES


class TestTemplateFields:
    def test_approval_record_template_fields_count(self):
        assert len(APPROVAL_RECORD_TEMPLATE_FIELDS) == 17

    def test_approval_required_fields_present(self):
        for f in [
            "provider_name", "source_name", "source_url_or_reference",
            "license_terms_summary", "allowed_use", "redistribution_allowed",
            "attribution_required", "internal_research_allowed", "commercial_use_allowed",
            "approved_by", "approved_at", "approval_scope", "source_file_expected_path",
            "checksum_required", "checksum_sha256", "paper_only", "production_ready",
        ]:
            assert f in APPROVAL_RECORD_TEMPLATE_FIELDS

    def test_manual_odds_columns_count(self):
        assert len(MANUAL_ODDS_TEMPLATE_COLUMNS) == 11

    def test_manual_odds_required_columns_present(self):
        for col in [
            "game_id", "game_date", "home_team", "away_team", "p_market",
            "odds_decimal", "sportsbook", "market_type", "closing_timestamp",
            "source_odds_ref", "license_ref",
        ]:
            assert col in MANUAL_ODDS_TEMPLATE_COLUMNS


class TestOutputFiles:
    def test_output_files_count(self):
        assert len(P37_OUTPUT_FILES) == 7

    def test_template_json_in_outputs(self):
        assert "odds_approval_record_TEMPLATE.json" in P37_OUTPUT_FILES

    def test_instructions_in_outputs(self):
        assert "odds_approval_record_INSTRUCTIONS.md" in P37_OUTPUT_FILES

    def test_csv_template_in_outputs(self):
        assert "odds_2024_approved_TEMPLATE.csv" in P37_OUTPUT_FILES

    def test_column_guide_in_outputs(self):
        assert "odds_2024_approved_COLUMN_GUIDE.md" in P37_OUTPUT_FILES

    def test_gate_json_in_outputs(self):
        assert "manual_odds_provisioning_gate.json" in P37_OUTPUT_FILES

    def test_gate_md_in_outputs(self):
        assert "manual_odds_provisioning_gate.md" in P37_OUTPUT_FILES

    def test_gate_result_in_outputs(self):
        assert "p37_gate_result.json" in P37_OUTPUT_FILES


class TestDataclasses:
    def test_p37_approval_record_template_frozen(self):
        t = P37ApprovalRecordTemplate(
            provider_name="X", source_name="Y", source_url_or_reference="Z",
            license_terms_summary="L", allowed_use="internal_research",
            redistribution_allowed=False, attribution_required=True,
            internal_research_allowed=True, commercial_use_allowed=False,
            approved_by="A", approved_at="2024-01-01T00:00:00+00:00",
            approval_scope="mlb_2024_season",
            source_file_expected_path="data/mlb_2024/manual_import/odds.csv",
            checksum_required=True, checksum_sha256="abc123",
            paper_only=True, production_ready=False,
        )
        with pytest.raises(Exception):
            t.provider_name = "changed"  # type: ignore[misc]

    def test_p37_gate_result_mutable(self):
        r = P37GateResult(
            gate="P37_BLOCKED_APPROVAL_RECORD_MISSING",
            approval_record_status="APPROVAL_MISSING",
            manual_odds_file_status="MANUAL_ODDS_REQUIRED",
            raw_commit_risk=False,
            templates_written=True,
        )
        r.blocker_reason = "test"
        assert r.blocker_reason == "test"

    def test_p37_gate_result_defaults(self):
        r = P37GateResult(
            gate="P37_BLOCKED_APPROVAL_RECORD_MISSING",
            approval_record_status="APPROVAL_MISSING",
            manual_odds_file_status="MANUAL_ODDS_REQUIRED",
            raw_commit_risk=False,
            templates_written=True,
        )
        assert r.paper_only is True
        assert r.production_ready is False
        assert r.raw_odds_commit_allowed is False
        assert r.approval_record_commit_allowed is False
        assert r.odds_artifact_ready is False
        assert r.artifacts == []
        assert r.season == 2024
        assert r.next_phase == "P38_BUILD_2024_LICENSED_ODDS_IMPORT_ARTIFACT"
        assert r.generated_at == ""

    def test_contract_rejects_production_ready_true(self):
        """Gate result with production_ready=True is structurally constructible
        but the gate checker must block it — verified in gate tests."""
        r = P37GateResult(
            gate="P37_BLOCKED_CONTRACT_VIOLATION",
            approval_record_status="APPROVAL_INVALID",
            manual_odds_file_status="MANUAL_ODDS_INVALID",
            raw_commit_risk=False,
            templates_written=False,
            production_ready=True,  # flagged as violation
        )
        assert r.production_ready is True  # stored, but gate will block

    def test_contract_rejects_paper_only_false(self):
        r = P37GateResult(
            gate="P37_BLOCKED_CONTRACT_VIOLATION",
            approval_record_status="APPROVAL_INVALID",
            manual_odds_file_status="MANUAL_ODDS_INVALID",
            raw_commit_risk=False,
            templates_written=False,
            paper_only=False,  # flagged as violation
        )
        assert r.paper_only is False  # stored, but gate will block
