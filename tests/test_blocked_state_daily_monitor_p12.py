"""Tests for P12-D blocked_state_daily_monitor."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_blocked_state_daily_monitor_p12 import (
    DEFAULT_OUTPUT_PATH,
    MIN_PAIR_COVERAGE_PCT,
    MIN_PAIRS_FOR_CLV,
    _assess_state,
    run_daily_monitor,
)
from wbc_backend.recommendation.blocked_state_governance import PaperOnlyViolationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_paths(tmp_path):
    """Return a dict of tmp paths for all state files."""
    return {
        "ceo": tmp_path / "ceo_decision.json",
        "api_key": tmp_path / "api_key_flag.json",
        "fwd": tmp_path / "fwd_readiness.json",
        "clv": tmp_path / "clv_status.json",
        "out": tmp_path / "output.json",
    }


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _fwd_data(pairs: int, coverage: float, status: str) -> dict:
    return {
        "pair_count": pairs,
        "pair_coverage_pct": coverage,
        "clv_readiness_status": status,
    }


def _clv_data(status: str, frozen: bool = True) -> dict:
    return {"current_clv_status": status, "promotion_frozen": frozen}


# ---------------------------------------------------------------------------
# TestNoCEODecision
# ---------------------------------------------------------------------------

class TestNoCEODecision:
    def test_no_ceo_decision_p13_blocked(self, tmp_paths):
        # No CEO file written
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["p13_allowed"] is False

    def test_no_ceo_decision_is_blocked(self, tmp_paths):
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["is_blocked"] is True

    def test_no_ceo_decision_primary_blocker(self, tmp_paths):
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["primary_blocker"] == "CEO_DECISION_PENDING"

    def test_no_ceo_decision_allowed_action_is_ceo_followup(self, tmp_paths):
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["allowed_next_action"] == "CEO_FOLLOWUP"


# ---------------------------------------------------------------------------
# TestCEOApprovedButNoAPIKey
# ---------------------------------------------------------------------------

class TestCEOApprovedButNoAPIKey:
    def test_ceo_approved_no_key_blocker(self, tmp_paths):
        _write(tmp_paths["ceo"], {"ceo_decision": "APPROVE_PATH_A_WITH_API_KEY"})
        # No API key file
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["primary_blocker"] == "API_KEY_MISSING"

    def test_ceo_approved_no_key_p13_blocked(self, tmp_paths):
        _write(tmp_paths["ceo"], {"ceo_decision": "APPROVE_PATH_A_WITH_API_KEY"})
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["p13_allowed"] is False

    def test_ceo_approved_with_key_not_api_key_blocked(self, tmp_paths):
        _write(tmp_paths["ceo"], {"ceo_decision": "APPROVE_PATH_A_WITH_API_KEY"})
        _write(tmp_paths["api_key"], {"api_key_available": True, "allow_sample_api_call": True})
        _write(tmp_paths["fwd"], _fwd_data(0, 0.0, "ACCUMULATION_INSUFFICIENT"))
        _write(tmp_paths["clv"], _clv_data("BLOCKED_NO_CLOSING_LINE"))
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        # API key is ready; blocker moves on to forward coverage
        assert result["primary_blocker"] != "API_KEY_MISSING"


# ---------------------------------------------------------------------------
# TestForwardPairsInsufficient
# ---------------------------------------------------------------------------

class TestForwardPairsInsufficient:
    def test_insufficient_pairs_coverage_blocked(self, tmp_paths):
        _write(tmp_paths["fwd"], _fwd_data(50, 40.0, "BLOCKED_LOW_COVERAGE"))
        _write(tmp_paths["clv"], _clv_data("BLOCKED_NO_CLOSING_LINE"))
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["p13_allowed"] is False

    def test_insufficient_pairs_forward_pairs_recorded(self, tmp_paths):
        _write(tmp_paths["fwd"], _fwd_data(50, 40.0, "BLOCKED_LOW_COVERAGE"))
        _write(tmp_paths["clv"], _clv_data("BLOCKED_NO_CLOSING_LINE"))
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["forward_pairs"] == 50

    def test_min_pairs_constant_value(self):
        assert MIN_PAIRS_FOR_CLV == 200

    def test_min_coverage_constant_value(self):
        assert MIN_PAIR_COVERAGE_PCT == 90.0


# ---------------------------------------------------------------------------
# TestCLVReadyCandidate
# ---------------------------------------------------------------------------

class TestCLVReadyCandidate:
    def test_clv_ready_candidate_p13_allowed(self, tmp_paths):
        _write(tmp_paths["ceo"], {"ceo_decision": "REJECT_PATH_A_USE_FORWARD_ONLY"})
        _write(tmp_paths["fwd"], _fwd_data(250, 96.0, "CLV_READY_CANDIDATE"))
        _write(tmp_paths["clv"], _clv_data("CLV_READY_CANDIDATE", frozen=False))
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["p13_allowed"] is True

    def test_clv_ready_candidate_not_blocked(self, tmp_paths):
        _write(tmp_paths["ceo"], {"ceo_decision": "REJECT_PATH_A_USE_FORWARD_ONLY"})
        _write(tmp_paths["fwd"], _fwd_data(250, 96.0, "CLV_READY_CANDIDATE"))
        _write(tmp_paths["clv"], _clv_data("CLV_READY_CANDIDATE", frozen=False))
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["is_blocked"] is False


# ---------------------------------------------------------------------------
# TestNoNetworkCall
# ---------------------------------------------------------------------------

class TestNoNetworkCall:
    def test_result_network_call_false(self, tmp_paths):
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["network_call"] is False

    def test_result_crawler_modified_false(self, tmp_paths):
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["crawler_modified"] is False

    def test_no_network_import_in_script(self):
        script = (
            Path(__file__).parent.parent
            / "scripts/run_blocked_state_daily_monitor_p12.py"
        ).read_text(encoding="utf-8")
        assert "import requests" not in script
        assert "import urllib" not in script
        assert "import socket" not in script
        assert "import tsl_crawler" not in script
        assert "from tsl_crawler" not in script


# ---------------------------------------------------------------------------
# TestPaperOnly
# ---------------------------------------------------------------------------

class TestPaperOnly:
    def test_paper_only_false_raises(self, tmp_paths):
        with pytest.raises(PaperOnlyViolationError):
            run_daily_monitor(
                ceo_decision_path=tmp_paths["ceo"],
                api_key_flag_path=tmp_paths["api_key"],
                forward_readiness_path=tmp_paths["fwd"],
                clv_status_path=tmp_paths["clv"],
                output_path=tmp_paths["out"],
                paper_only=False,
            )

    def test_result_paper_only_true(self, tmp_paths):
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["paper_only"] is True

    def test_champion_preserved(self, tmp_paths):
        result = run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert result["fixed_edge_5pct_champion_preserved"] is True


# ---------------------------------------------------------------------------
# TestOutputFile
# ---------------------------------------------------------------------------

class TestOutputFile:
    def test_output_json_written(self, tmp_paths):
        run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        assert tmp_paths["out"].exists()

    def test_output_has_required_keys(self, tmp_paths):
        run_daily_monitor(
            ceo_decision_path=tmp_paths["ceo"],
            api_key_flag_path=tmp_paths["api_key"],
            forward_readiness_path=tmp_paths["fwd"],
            clv_status_path=tmp_paths["clv"],
            output_path=tmp_paths["out"],
        )
        data = json.loads(tmp_paths["out"].read_text())
        required = {
            "paper_only", "network_call", "crawler_modified",
            "ceo_decision_status", "primary_blocker",
            "allowed_next_action", "forbidden_next_action",
            "p13_allowed", "is_blocked",
        }
        for key in required:
            assert key in data, f"Missing key: {key}"

    def test_p12_artifact_paper_only_if_exists(self):
        """If the real P12-D output exists, verify paper_only=true."""
        if not DEFAULT_OUTPUT_PATH.exists():
            pytest.skip("artifact not yet generated")
        data = json.loads(DEFAULT_OUTPUT_PATH.read_text())
        assert data.get("paper_only") is True
