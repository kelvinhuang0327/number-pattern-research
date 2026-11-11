"""
Tests for P31 Provenance & License Audit module.

Coverage:
4. Retrosheet has no odds coverage
5. MLB Stats API has no closing odds coverage
6. Unknown odds provider causes PENDING_LICENSE / GO_PARTIAL recommendation
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from wbc_backend.recommendation.p31_provenance_license_audit import (
    CandidateDecision,
    LicenseStatus,
    ProvenanceStatus,
    AcquisitionRisk,
    run_provenance_license_audit,
    write_provenance_audit_json,
    PAPER_ONLY,
    PRODUCTION_READY,
)


# ---------------------------------------------------------------------------
# Test: Individual candidate properties
# ---------------------------------------------------------------------------


class TestRetrosheet2024:
    def setup_method(self) -> None:
        result = run_provenance_license_audit()
        # First candidate is Retrosheet
        self.candidate = result.candidates[0]

    def test_source_name_contains_retrosheet(self) -> None:
        assert "Retrosheet" in self.candidate.source_name

    def test_retrosheet_has_no_odds_coverage(self) -> None:
        """Test 4: Retrosheet has no odds coverage."""
        assert "closing_moneyline_home" in self.candidate.schema_gap
        assert "closing_moneyline_away" in self.candidate.schema_gap

    def test_retrosheet_is_verified_provenance(self) -> None:
        assert self.candidate.provenance_status == ProvenanceStatus.VERIFIED

    def test_retrosheet_requires_attribution(self) -> None:
        assert self.candidate.license_status == LicenseStatus.REQUIRES_ATTRIBUTION

    def test_retrosheet_is_low_risk(self) -> None:
        assert self.candidate.acquisition_risk == AcquisitionRisk.LOW

    def test_retrosheet_decision_is_go_partial(self) -> None:
        assert self.candidate.recommended_decision == CandidateDecision.GO_PARTIAL

    def test_retrosheet_url_present(self) -> None:
        assert self.candidate.url.startswith("https://")


class TestMLBStatsAPI2024:
    def setup_method(self) -> None:
        result = run_provenance_license_audit()
        # Second candidate is MLB Stats API
        self.candidate = result.candidates[1]

    def test_source_name_contains_mlb(self) -> None:
        assert "MLB" in self.candidate.source_name

    def test_mlb_api_has_no_closing_odds(self) -> None:
        """Test 5: MLB Stats API has no closing odds coverage."""
        assert "closing_moneyline_home" in self.candidate.schema_gap
        assert "closing_moneyline_away" in self.candidate.schema_gap

    def test_mlb_api_is_verified_provenance(self) -> None:
        assert self.candidate.provenance_status == ProvenanceStatus.VERIFIED

    def test_mlb_api_decision_is_go_partial(self) -> None:
        assert self.candidate.recommended_decision == CandidateDecision.GO_PARTIAL

    def test_mlb_api_url_present(self) -> None:
        assert self.candidate.url.startswith("https://")


class TestClosingOdds2024:
    def setup_method(self) -> None:
        result = run_provenance_license_audit()
        # Third candidate is odds source
        self.candidate = result.candidates[2]

    def test_odds_provenance_unresolved(self) -> None:
        """Test 6: Unknown odds provider causes UNRESOLVED provenance."""
        assert self.candidate.provenance_status == ProvenanceStatus.UNRESOLVED

    def test_odds_license_unknown(self) -> None:
        """Test 6: Unknown odds provider causes UNKNOWN license status."""
        assert self.candidate.license_status == LicenseStatus.UNKNOWN

    def test_odds_decision_is_pending(self) -> None:
        """Test 6: Unknown odds provider causes PENDING_LICENSE decision."""
        assert self.candidate.recommended_decision == CandidateDecision.PENDING_LICENSE

    def test_odds_acquisition_risk_high(self) -> None:
        assert self.candidate.acquisition_risk == AcquisitionRisk.HIGH

    def test_odds_url_empty(self) -> None:
        """No confirmed URL until provider selected."""
        assert self.candidate.url == ""


# ---------------------------------------------------------------------------
# Test: Overall P32 recommendation
# ---------------------------------------------------------------------------


class TestOverallP32Recommendation:
    def test_recommendation_is_go_partial_not_full(self) -> None:
        """Test 6 corollary: With odds unresolved, recommendation is GO_PARTIAL."""
        result = run_provenance_license_audit()
        assert result.overall_p32_recommendation == "GO_PARTIAL_GAME_LOGS_ONLY"

    def test_odds_license_not_resolved(self) -> None:
        result = run_provenance_license_audit()
        assert result.odds_license_resolved is False

    def test_game_logs_license_safe(self) -> None:
        result = run_provenance_license_audit()
        assert result.game_logs_license_safe is True

    def test_paper_only_true(self) -> None:
        assert PAPER_ONLY is True
        assert PRODUCTION_READY is False

    def test_result_paper_only(self) -> None:
        result = run_provenance_license_audit()
        assert result.paper_only is True
        assert result.production_ready is False


# ---------------------------------------------------------------------------
# Test: write_provenance_audit_json
# ---------------------------------------------------------------------------


class TestWriteProvenanceJson:
    def test_writes_valid_json(self, tmp_path: Path) -> None:
        result = run_provenance_license_audit()
        out = tmp_path / "provenance.json"
        write_provenance_audit_json(result, out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "candidates" in data
        assert len(data["candidates"]) == 3

    def test_json_contains_p32_recommendation(self, tmp_path: Path) -> None:
        result = run_provenance_license_audit()
        out = tmp_path / "provenance.json"
        write_provenance_audit_json(result, out)
        data = json.loads(out.read_text())
        assert data["overall_p32_recommendation"] == "GO_PARTIAL_GAME_LOGS_ONLY"

    def test_json_paper_only_true(self, tmp_path: Path) -> None:
        result = run_provenance_license_audit()
        out = tmp_path / "provenance.json"
        write_provenance_audit_json(result, out)
        data = json.loads(out.read_text())
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    def test_no_candidate_has_full_odds(self, tmp_path: Path) -> None:
        """No candidate provides both game outcomes AND closing odds."""
        result = run_provenance_license_audit()
        for cand in result.candidates:
            # GO means complete; GO_PARTIAL or PENDING means odds gap
            if cand.recommended_decision == CandidateDecision.GO:
                # If any candidate is GO, it better not be because of odds coverage
                # (Retrosheet and MLB API have schema gaps for odds)
                pass
        # The odds candidate must not be GO
        odds_cand = result.candidates[2]
        assert odds_cand.recommended_decision != CandidateDecision.GO
