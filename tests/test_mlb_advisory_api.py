"""Tests for MLB Advisory API (Paper-Only Handler).

Covers:
  - Safety constants and governance flags
  - Forbidden keys never returned
  - _governance_response() injects required governance flags
  - validate_api_response() passes for compliant responses
  - validate_api_response() catches missing / wrong governance flags
  - validate_api_response() catches forbidden keys
  - get_mlb_mvp_status() structure and live_source_ready=False
  - get_daily_advisory_report() returns unavailable when file missing
  - get_paper_ledger_summary() returns unavailable when file missing
  - get_postgame_review_report() returns unavailable when file missing
  - get_latest_daily_manifest() returns unavailable when dir empty
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import pytest

from orchestrator.mlb_advisory_api import (
    DIAGNOSTIC_ONLY,
    MODULE_VERSION,
    NO_AUTO_EXECUTION,
    NO_PROFIT_CLAIM,
    NO_REAL_BET,
    PAPER_ONLY,
    PRODUCTION_MODIFIED,
    _FORBIDDEN_RESPONSE_KEYS,
    _GOVERNANCE_FLAGS,
    _governance_response,
    _unavailable_response,
    get_daily_advisory_report,
    get_latest_daily_manifest,
    get_mlb_mvp_status,
    get_paper_ledger_summary,
    get_postgame_review_report,
    validate_api_response,
)


# ════════════════════════════════════════════════════════════════════════════
# Safety constants
# ════════════════════════════════════════════════════════════════════════════


class TestSafetyConstants:
    def test_production_modified_is_false(self) -> None:
        assert PRODUCTION_MODIFIED is False

    def test_no_real_bet_is_true(self) -> None:
        assert NO_REAL_BET is True

    def test_paper_only_is_true(self) -> None:
        assert PAPER_ONLY is True

    def test_no_profit_claim_is_true(self) -> None:
        assert NO_PROFIT_CLAIM is True

    def test_no_auto_execution_is_true(self) -> None:
        assert NO_AUTO_EXECUTION is True

    def test_diagnostic_only_is_true(self) -> None:
        assert DIAGNOSTIC_ONLY is True

    def test_module_version_set(self) -> None:
        assert MODULE_VERSION
        assert "mlb_advisory_api" in MODULE_VERSION


# ════════════════════════════════════════════════════════════════════════════
# Governance flags
# ════════════════════════════════════════════════════════════════════════════


class TestGovernanceFlags:
    def test_governance_flags_required_keys_present(self) -> None:
        """_GOVERNANCE_FLAGS must contain all required flags."""
        required = {
            "paper_only", "no_real_bet", "no_profit_claim",
            "no_auto_execution", "production_modified",
        }
        assert required.issubset(set(_GOVERNANCE_FLAGS.keys()))

    def test_governance_flags_values_correct(self) -> None:
        """Governance flags must have correct boolean values."""
        assert _GOVERNANCE_FLAGS["paper_only"] is True
        assert _GOVERNANCE_FLAGS["no_real_bet"] is True
        assert _GOVERNANCE_FLAGS["no_profit_claim"] is True
        assert _GOVERNANCE_FLAGS["no_auto_execution"] is True
        assert _GOVERNANCE_FLAGS["production_modified"] is False

    def test_governance_response_injects_flags(self) -> None:
        """_governance_response() must inject all governance flags."""
        response = _governance_response({"status": "ok", "data": 42})
        assert response["paper_only"] is True
        assert response["no_real_bet"] is True
        assert response["no_profit_claim"] is True
        assert response["no_auto_execution"] is True
        assert response["production_modified"] is False
        assert response["status"] == "ok"
        assert response["data"] == 42

    def test_governance_response_strips_forbidden_keys(self) -> None:
        """_governance_response() must remove any forbidden keys."""
        contaminated = {
            "status": "ok",
            "stake_sizing": {"home": 100},  # forbidden
            "real_bet_placement_instruction": "bet $100",  # forbidden
        }
        result = _governance_response(contaminated)
        assert "stake_sizing" not in result
        assert "real_bet_placement_instruction" not in result
        assert result["status"] == "ok"


# ════════════════════════════════════════════════════════════════════════════
# Forbidden keys
# ════════════════════════════════════════════════════════════════════════════


class TestForbiddenKeys:
    def test_forbidden_keys_set_non_empty(self) -> None:
        """_FORBIDDEN_RESPONSE_KEYS must be non-empty."""
        assert len(_FORBIDDEN_RESPONSE_KEYS) >= 4

    def test_forbidden_keys_includes_stake_sizing(self) -> None:
        assert "stake_sizing" in _FORBIDDEN_RESPONSE_KEYS

    def test_forbidden_keys_includes_bet_placement(self) -> None:
        assert "real_bet_placement_instruction" in _FORBIDDEN_RESPONSE_KEYS

    def test_forbidden_keys_includes_profit_wording(self) -> None:
        assert "guaranteed_profit_wording" in _FORBIDDEN_RESPONSE_KEYS

    def test_forbidden_keys_is_frozenset(self) -> None:
        assert isinstance(_FORBIDDEN_RESPONSE_KEYS, frozenset)


# ════════════════════════════════════════════════════════════════════════════
# validate_api_response
# ════════════════════════════════════════════════════════════════════════════


class TestValidateApiResponse:
    def test_valid_governance_compliant_response(self) -> None:
        """validate_api_response() must return no errors for a compliant response."""
        response = _governance_response({"status": "ok"})
        errors = validate_api_response(response)
        assert errors == []

    def test_missing_paper_only(self) -> None:
        """validate_api_response() must report missing paper_only key."""
        response = _governance_response({"status": "ok"})
        del response["paper_only"]
        errors = validate_api_response(response)
        assert any("paper_only" in e for e in errors)

    def test_missing_no_real_bet(self) -> None:
        """validate_api_response() must report missing no_real_bet key."""
        response = _governance_response({"status": "ok"})
        del response["no_real_bet"]
        errors = validate_api_response(response)
        assert any("no_real_bet" in e for e in errors)

    def test_false_governance_flag_caught(self) -> None:
        """validate_api_response() must report False governance flags."""
        response = _governance_response({"status": "ok"})
        response["paper_only"] = False  # invalid!
        errors = validate_api_response(response)
        assert any("paper_only" in e for e in errors)

    def test_forbidden_key_in_response_caught(self) -> None:
        """validate_api_response() must report forbidden keys."""
        response = _governance_response({"status": "ok"})
        response["stake_sizing"] = {"home": 100}  # forbidden injection
        errors = validate_api_response(response)
        assert any("stake_sizing" in e for e in errors)

    def test_multiple_missing_keys_all_reported(self) -> None:
        """validate_api_response() must report all missing required governance keys."""
        response: dict = {}  # completely empty
        errors = validate_api_response(response)
        # Must report at least paper_only, no_real_bet, no_profit_claim, no_auto_execution
        assert len(errors) >= 4


# ════════════════════════════════════════════════════════════════════════════
# get_mlb_mvp_status
# ════════════════════════════════════════════════════════════════════════════


class TestGetMlbMvpStatus:
    def test_returns_governance_compliant_response(self) -> None:
        """get_mlb_mvp_status() must return governance-compliant response."""
        status = get_mlb_mvp_status()
        errors = validate_api_response(status)
        assert errors == [], f"Governance errors: {errors}"

    def test_live_source_ready_is_false(self) -> None:
        """get_mlb_mvp_status() must return live_source_ready=False (no live API connected)."""
        status = get_mlb_mvp_status()
        assert status["live_source_ready"] is False

    def test_missing_live_sources_non_empty(self) -> None:
        """get_mlb_mvp_status() must list at least 3 missing live sources."""
        status = get_mlb_mvp_status()
        missing = status.get("missing_live_sources", [])
        assert len(missing) >= 3

    def test_completion_marker_present(self) -> None:
        """get_mlb_mvp_status() must include completion_marker."""
        status = get_mlb_mvp_status()
        assert "completion_marker" in status
        assert status["completion_marker"]

    def test_overall_gate_is_valid(self) -> None:
        """get_mlb_mvp_status() overall_gate must be a non-empty string."""
        status = get_mlb_mvp_status()
        assert "overall_gate" in status
        assert isinstance(status["overall_gate"], str)
        assert status["overall_gate"]

    def test_api_version_present(self) -> None:
        """get_mlb_mvp_status() must include api_version."""
        status = get_mlb_mvp_status()
        assert status.get("api_version") == MODULE_VERSION

    def test_no_stake_sizing_in_response(self) -> None:
        """get_mlb_mvp_status() must not contain stake_sizing."""
        status = get_mlb_mvp_status()
        assert "stake_sizing" not in status
        assert "real_bet_placement_instruction" not in status


# ════════════════════════════════════════════════════════════════════════════
# get_daily_advisory_report — file missing
# ════════════════════════════════════════════════════════════════════════════


class TestGetDailyAdvisoryReport:
    def test_returns_unavailable_when_missing(self) -> None:
        """get_daily_advisory_report() must return unavailable when report not found."""
        response = get_daily_advisory_report("1900-01-01")
        assert response["status"] == "unavailable"
        errors = validate_api_response(response)
        assert errors == []

    def test_unavailable_includes_date(self) -> None:
        """Unavailable response must echo the requested date."""
        response = get_daily_advisory_report("1900-01-01")
        assert response.get("date") == "1900-01-01"

    def test_governance_compliant_even_unavailable(self) -> None:
        """Even unavailable responses must be governance-compliant."""
        response = get_daily_advisory_report("1900-01-01")
        errors = validate_api_response(response)
        assert errors == []


# ════════════════════════════════════════════════════════════════════════════
# get_paper_ledger_summary — file missing
# ════════════════════════════════════════════════════════════════════════════


class TestGetPaperLedgerSummary:
    def test_returns_unavailable_when_missing(self, tmp_path: Any) -> None:
        """get_paper_ledger_summary() must return unavailable when ledger not found."""
        nonexistent = str(tmp_path / "no_ledger.jsonl")
        response = get_paper_ledger_summary(ledger_path=nonexistent)
        assert response["status"] == "unavailable"
        errors = validate_api_response(response)
        assert errors == []

    def test_ledger_summary_basic_parsing(self, tmp_path: Any) -> None:
        """get_paper_ledger_summary() must parse valid JSONL entries."""
        ledger = tmp_path / "ledger.jsonl"
        entries = [
            {"game_id": "g001", "game_date": "2025-07-01", "recommendation": "LEAN_HOME"},
            {"game_id": "g002", "game_date": "2025-07-01", "recommendation": "PASS"},
            {"game_id": "g003", "game_date": "2025-07-02", "recommendation": "LEAN_AWAY"},
        ]
        with open(ledger, "w", encoding="utf-8") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")

        response = get_paper_ledger_summary(ledger_path=str(ledger))
        assert response["status"] == "ok"
        assert response["total_ledger_entries"] == 3
        errors = validate_api_response(response)
        assert errors == []

    def test_ledger_summary_no_stake_sizing(self, tmp_path: Any) -> None:
        """Ledger summary must never include stake_sizing."""
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text(
            json.dumps({
                "game_id": "g001",
                "game_date": "2025-07-01",
                "recommendation": "LEAN_HOME",
                "stake_sizing": {"amount": 100},  # injected in source data
            }) + "\n",
            encoding="utf-8",
        )
        response = get_paper_ledger_summary(ledger_path=str(ledger))
        assert "stake_sizing" not in response


# ════════════════════════════════════════════════════════════════════════════
# get_postgame_review_report — file missing
# ════════════════════════════════════════════════════════════════════════════


class TestGetPostgameReviewReport:
    def test_returns_unavailable_when_missing(self) -> None:
        """get_postgame_review_report() must return unavailable when not found."""
        response = get_postgame_review_report("1900-01-01")
        assert response["status"] == "unavailable"
        errors = validate_api_response(response)
        assert errors == []


# ════════════════════════════════════════════════════════════════════════════
# get_latest_daily_manifest — no files
# ════════════════════════════════════════════════════════════════════════════


class TestGetLatestDailyManifest:
    def test_returns_unavailable_when_dir_empty(self, tmp_path: Any) -> None:
        """get_latest_daily_manifest() must return unavailable when no manifests found."""
        response = get_latest_daily_manifest(manifest_dir=str(tmp_path))
        assert response["status"] == "unavailable"
        errors = validate_api_response(response)
        assert errors == []

    def test_loads_manifest_by_date(self, tmp_path: Any) -> None:
        """get_latest_daily_manifest() must load a specific manifest by date."""
        manifest_data = {"gate": "MLB_SCHEDULER_API_MVP_READY", "run_date": "2025-07-01"}
        manifest_file = tmp_path / "mlb_daily_scheduler_manifest_20250701.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        # Patch to use tmp_path for the report directory
        import orchestrator.mlb_advisory_api as api_mod
        orig = api_mod.DEFAULT_REPORTS_DIR
        try:
            api_mod.DEFAULT_REPORTS_DIR = str(tmp_path)
            response = get_latest_daily_manifest(
                manifest_dir=str(tmp_path), date_str="2025-07-01"
            )
        finally:
            api_mod.DEFAULT_REPORTS_DIR = orig

        assert response["status"] == "ok"
        assert response["manifest"]["gate"] == "MLB_SCHEDULER_API_MVP_READY"
        errors = validate_api_response(response)
        assert errors == []


# ════════════════════════════════════════════════════════════════════════════
# _unavailable_response
# ════════════════════════════════════════════════════════════════════════════


class TestUnavailableResponse:
    def test_unavailable_response_governance_compliant(self) -> None:
        """_unavailable_response() must always be governance-compliant."""
        resp = _unavailable_response("test reason", "2025-07-01")
        errors = validate_api_response(resp)
        assert errors == []

    def test_unavailable_response_has_reason(self) -> None:
        resp = _unavailable_response("missing file")
        assert "missing file" in resp.get("reason", "")

    def test_unavailable_response_no_forbidden_keys(self) -> None:
        resp = _unavailable_response("test")
        for fk in _FORBIDDEN_RESPONSE_KEYS:
            assert fk not in resp
