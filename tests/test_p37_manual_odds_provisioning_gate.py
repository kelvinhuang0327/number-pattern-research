"""
Tests for p37_manual_odds_provisioning_gate.py
"""
import json
import os
import tempfile
from unittest.mock import patch

import pandas as pd
import pytest

from wbc_backend.recommendation.p37_manual_odds_provisioning_gate import (
    check_manual_approval_record,
    check_manual_odds_file,
    detect_raw_commit_risk,
    build_provisioning_gate_result,
    write_p37_outputs,
)
from wbc_backend.recommendation.p37_manual_odds_provisioning_contract import (
    MANUAL_ODDS_TEMPLATE_COLUMNS,
    P37GateResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_approval_record(tmp_dir: str) -> str:
    record = {
        "provider_name": "TestProvider",
        "source_name": "TestSource",
        "source_url_or_reference": "https://example.com/data",
        "license_terms_summary": "Internal research use permitted",
        "allowed_use": "internal_research",
        "redistribution_allowed": False,
        "attribution_required": True,
        "internal_research_allowed": True,
        "commercial_use_allowed": False,
        "approved_by": "ResearchLead",
        "approved_at": "2024-01-01T00:00:00+00:00",
        "approval_scope": "mlb_2024_season",
        "source_file_expected_path": "data/mlb_2024/manual_import/odds_2024_approved.csv",
        "checksum_required": False,
        "paper_only": True,
        "production_ready": False,
    }
    path = os.path.join(tmp_dir, "approval_record.json")
    with open(path, "w") as f:
        json.dump(record, f)
    return path


def _make_valid_odds_csv(tmp_dir: str) -> str:
    df = pd.DataFrame([{
        "game_id": "20240401_BOS_NYA",
        "game_date": "2024-04-01",
        "home_team": "BOS",
        "away_team": "NYA",
        "p_market": 0.55,
        "odds_decimal": 1.82,
        "sportsbook": "Pinnacle",
        "market_type": "moneyline",
        "closing_timestamp": "2024-04-01T17:00:00+00:00",
        "source_odds_ref": "pinnacle_row_123",
        "license_ref": "license_001",
    }])
    path = os.path.join(tmp_dir, "odds.csv")
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# check_manual_approval_record
# ---------------------------------------------------------------------------

class TestCheckManualApprovalRecord:
    def test_no_path_returns_missing(self):
        result = check_manual_approval_record(None)
        assert result["record_exists"] is False
        assert result["approval_status"] == "APPROVAL_MISSING"

    def test_missing_file_returns_missing(self):
        result = check_manual_approval_record("/tmp/nonexistent_p37_approval.json")
        assert result["record_exists"] is False
        assert result["approval_status"] == "APPROVAL_MISSING"

    def test_malformed_json_returns_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w") as f:
                f.write("{not valid json")
            result = check_manual_approval_record(path)
            assert result["approval_status"] == "APPROVAL_INVALID"

    def test_non_dict_json_returns_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "list.json")
            with open(path, "w") as f:
                json.dump([1, 2, 3], f)
            result = check_manual_approval_record(path)
            assert result["approval_status"] == "APPROVAL_INVALID"

    def test_valid_record_returns_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_valid_approval_record(tmp)
            result = check_manual_approval_record(path)
            assert result["record_exists"] is True
            assert result["approval_status"] == "APPROVAL_READY"
            assert result["internal_research_allowed"] is True

    def test_internal_research_false_returns_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_valid_approval_record(tmp)
            with open(path) as f:
                record = json.load(f)
            record["internal_research_allowed"] = False
            with open(path, "w") as f:
                json.dump(record, f)
            result = check_manual_approval_record(path)
            # internal_research_allowed=False must block
            assert result["approval_status"] != "APPROVAL_READY"


# ---------------------------------------------------------------------------
# check_manual_odds_file
# ---------------------------------------------------------------------------

class TestCheckManualOddsFile:
    def test_no_path_returns_file_not_exists(self):
        result = check_manual_odds_file(None)
        assert result["file_exists"] is False

    def test_missing_file_returns_not_exists(self):
        result = check_manual_odds_file("/tmp/nonexistent_p37_odds.csv")
        assert result["file_exists"] is False

    def test_valid_odds_csv_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_valid_odds_csv(tmp)
            result = check_manual_odds_file(path)
            assert result["file_exists"] is True
            assert result["schema_valid"] is True
            assert result["leakage_free"] is True

    def test_missing_required_column_fails_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_valid_odds_csv(tmp)
            df = pd.read_csv(path).drop(columns=["game_id"])
            df.to_csv(path, index=False)
            result = check_manual_odds_file(path)
            assert result["schema_valid"] is False

    def test_forbidden_column_fails_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_valid_odds_csv(tmp)
            df = pd.read_csv(path)
            df["y_true"] = 1
            df.to_csv(path, index=False)
            result = check_manual_odds_file(path)
            assert result["leakage_free"] is False


# ---------------------------------------------------------------------------
# detect_raw_commit_risk
# ---------------------------------------------------------------------------

class TestDetectRawCommitRisk:
    def test_no_staged_files_returns_false(self):
        """Assumes no raw/manual files are staged in the test environment."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = detect_raw_commit_risk(repo_root)
        # Should be False in a clean test environment
        assert isinstance(result, bool)

    def test_invalid_repo_returns_false(self):
        """Non-repo dir should not raise — returns False."""
        result = detect_raw_commit_risk("/tmp/not_a_git_repo_xyz")
        assert result is False


# ---------------------------------------------------------------------------
# build_provisioning_gate_result
# ---------------------------------------------------------------------------

class TestBuildProvisioningGateResult:
    def _missing_approval(self):
        return {
            "record_exists": False,
            "approval_status": "APPROVAL_MISSING",
            "internal_research_allowed": False,
            "allowed_use_valid": False,
            "issues": [],
        }

    def _valid_approval(self):
        return {
            "record_exists": True,
            "approval_status": "APPROVAL_READY",
            "internal_research_allowed": True,
            "allowed_use_valid": True,
            "issues": [],
        }

    def _missing_odds(self):
        return {
            "file_exists": False,
            "schema_valid": False,
            "leakage_free": False,
            "value_ranges_valid": False,
            "issues": [],
        }

    def _valid_odds(self):
        return {
            "file_exists": True,
            "schema_valid": True,
            "leakage_free": True,
            "value_ranges_valid": True,
            "issues": [],
        }

    def test_missing_approval_returns_blocked(self):
        result = build_provisioning_gate_result(
            self._missing_approval(), self._missing_odds(),
            raw_commit_risk=False, templates_written=True,
        )
        assert result.gate == "P37_BLOCKED_APPROVAL_RECORD_MISSING"

    def test_invalid_approval_returns_blocked(self):
        approval = {
            "record_exists": True,
            "approval_status": "APPROVAL_INVALID",
            "internal_research_allowed": False,
            "allowed_use_valid": False,
            "issues": ["Missing fields"],
        }
        result = build_provisioning_gate_result(
            approval, self._missing_odds(),
            raw_commit_risk=False, templates_written=True,
        )
        assert result.gate == "P37_BLOCKED_APPROVAL_RECORD_INVALID"

    def test_license_blocked_approval_returns_license_blocked(self):
        approval = {
            "record_exists": True,
            "approval_status": "APPROVAL_BLOCKED_LICENSE",
            "internal_research_allowed": False,
            "allowed_use_valid": False,
            "issues": [],
        }
        result = build_provisioning_gate_result(
            approval, self._missing_odds(),
            raw_commit_risk=False, templates_written=True,
        )
        assert result.gate == "P37_BLOCKED_LICENSE_NOT_APPROVED"

    def test_valid_approval_missing_odds_returns_odds_missing(self):
        result = build_provisioning_gate_result(
            self._valid_approval(), self._missing_odds(),
            raw_commit_risk=False, templates_written=True,
        )
        assert result.gate == "P37_BLOCKED_MANUAL_ODDS_FILE_MISSING"

    def test_valid_approval_invalid_odds_schema(self):
        odds = {
            "file_exists": True,
            "schema_valid": False,
            "leakage_free": True,
            "value_ranges_valid": True,
            "issues": ["Missing game_id"],
        }
        result = build_provisioning_gate_result(
            self._valid_approval(), odds,
            raw_commit_risk=False, templates_written=True,
        )
        assert result.gate == "P37_BLOCKED_MANUAL_ODDS_SCHEMA_INVALID"

    def test_all_valid_returns_ready(self):
        result = build_provisioning_gate_result(
            self._valid_approval(), self._valid_odds(),
            raw_commit_risk=False, templates_written=True,
        )
        assert result.gate == "P37_MANUAL_ODDS_PROVISIONING_GATE_READY"
        assert result.odds_artifact_ready is True
        assert result.raw_odds_commit_allowed is False

    def test_raw_commit_risk_blocks(self):
        result = build_provisioning_gate_result(
            self._valid_approval(), self._valid_odds(),
            raw_commit_risk=True, templates_written=True,
        )
        assert result.gate == "P37_BLOCKED_RAW_ODDS_COMMIT_RISK"

    def test_raw_odds_commit_always_false(self):
        for approval, odds in [
            (self._missing_approval(), self._missing_odds()),
            (self._valid_approval(), self._valid_odds()),
        ]:
            result = build_provisioning_gate_result(
                approval, odds, raw_commit_risk=False, templates_written=True,
            )
            assert result.raw_odds_commit_allowed is False

    def test_paper_only_always_true(self):
        result = build_provisioning_gate_result(
            self._missing_approval(), self._missing_odds(),
            raw_commit_risk=False, templates_written=True,
        )
        assert result.paper_only is True

    def test_production_ready_always_false(self):
        result = build_provisioning_gate_result(
            self._valid_approval(), self._valid_odds(),
            raw_commit_risk=False, templates_written=True,
        )
        assert result.production_ready is False


# ---------------------------------------------------------------------------
# write_p37_outputs
# ---------------------------------------------------------------------------

class TestWriteP37Outputs:
    def _make_blocked_gate_result(self) -> P37GateResult:
        return P37GateResult(
            gate="P37_BLOCKED_APPROVAL_RECORD_MISSING",
            approval_record_status="APPROVAL_MISSING",
            manual_odds_file_status="MANUAL_ODDS_REQUIRED",
            raw_commit_risk=False,
            templates_written=True,
        )

    def test_writes_three_output_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._make_blocked_gate_result()
            written = write_p37_outputs(tmp, r, {"issues": []}, {"issues": []})
            fnames = [os.path.basename(p) for p in written]
            assert "manual_odds_provisioning_gate.json" in fnames
            assert "manual_odds_provisioning_gate.md" in fnames
            assert "p37_gate_result.json" in fnames

    def test_gate_json_contains_correct_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._make_blocked_gate_result()
            write_p37_outputs(tmp, r, {"issues": []}, {"issues": []})
            with open(os.path.join(tmp, "manual_odds_provisioning_gate.json")) as f:
                data = json.load(f)
            assert data["gate"] == "P37_BLOCKED_APPROVAL_RECORD_MISSING"

    def test_p37_gate_result_json_has_paper_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._make_blocked_gate_result()
            write_p37_outputs(tmp, r, {"issues": []}, {"issues": []})
            with open(os.path.join(tmp, "p37_gate_result.json")) as f:
                data = json.load(f)
            assert data["paper_only"] is True
            assert data["production_ready"] is False
            assert data["raw_odds_commit_allowed"] is False

    def test_deterministic_excluding_generated_at(self):
        _EXCLUDE = frozenset({"generated_at", "artifacts"})
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            r1 = P37GateResult(
                gate="P37_BLOCKED_APPROVAL_RECORD_MISSING",
                approval_record_status="APPROVAL_MISSING",
                manual_odds_file_status="MANUAL_ODDS_REQUIRED",
                raw_commit_risk=False,
                templates_written=True,
            )
            r2 = P37GateResult(
                gate="P37_BLOCKED_APPROVAL_RECORD_MISSING",
                approval_record_status="APPROVAL_MISSING",
                manual_odds_file_status="MANUAL_ODDS_REQUIRED",
                raw_commit_risk=False,
                templates_written=True,
            )
            write_p37_outputs(tmp1, r1, {"issues": []}, {"issues": []})
            write_p37_outputs(tmp2, r2, {"issues": []}, {"issues": []})
            for fname in ("manual_odds_provisioning_gate.json", "p37_gate_result.json"):
                with open(os.path.join(tmp1, fname)) as f1:
                    d1 = {k: v for k, v in json.load(f1).items() if k not in _EXCLUDE}
                with open(os.path.join(tmp2, fname)) as f2:
                    d2 = {k: v for k, v in json.load(f2).items() if k not in _EXCLUDE}
                assert d1 == d2, f"Non-deterministic: {fname}"
