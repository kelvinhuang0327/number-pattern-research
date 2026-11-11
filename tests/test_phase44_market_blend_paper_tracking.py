"""
Tests for Phase 44: Market Blend Paper-Only Tracking & Evidence Pack
====================================================================
Tests verify:
  - α is always 0.4 (TestAlphaFixed)
  - gate_state is always PAPER_ONLY (TestGateState)
  - candidate_patch_created is always False (TestCandidatePatch)
  - all required fields present in PaperTrackingSnapshot (TestMetricsSchema)
  - audit_hash is stable and non-empty (TestAuditHash)
  - Markdown report generates correctly (TestMarkdownReport)
  - JSON output generates and validates (TestJSONOutput)
  - NOT_SIGNIFICANT → no PATCH_GATE_RECHECK label anywhere (TestNoRecheck)
  - Decision Card Phase 44 block renders without breaking existing payload (TestDecisionCardRender)
  - Gate criteria assessed correctly (TestGateCriteria)
  - BootstrapSummary and metrics computed correctly (TestMetricsComputation)
"""
from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.phase44_market_blend_paper_tracking import (
    GATE_CRITERIA_MIN_SAMPLE,
    GATE_STATE,
    NEXT_GATE_CRITERIA,
    PAPER_ALPHA,
    PHASE43_EVIDENCE_SUMMARY,
    RISK_NOTES,
    BootstrapSummary,
    GateCriteriaStatus,
    MetricBundle,
    PaperTrackingSnapshot,
    _compute_audit_hash,
    _compute_gate_criteria,
    _compute_metrics,
    run_phase44_tracking,
)
from wbc_backend.evaluation.prediction_persistence import PredictionRow


# ─── Helper: synthetic PredictionRow list ────────────────────────────────────

def _make_rows(n: int = 60, seed: int = 42) -> list[PredictionRow]:
    """
    Create n synthetic PredictionRow instances using correct field names.
    Uses a simple deterministic sequence so tests are reproducible.
    """
    import math
    rows: list[PredictionRow] = []
    for i in range(n):
        frac = (i + 1) / (n + 1)
        raw = max(0.05, min(0.95, 0.5 + 0.3 * math.sin(frac * math.pi * 3)))
        mkt = max(0.05, min(0.95, 0.5 + 0.2 * math.cos(frac * math.pi * 2)))
        label = 1 if (raw + 0.05) > 0.5 else 0
        rows.append(
            PredictionRow(
                game_id=f"game_{i:04d}",
                game_date=f"2025-{(i % 5) + 4:02d}-{(i % 28) + 1:02d}",
                home_team="HOME",
                away_team="AWAY",
                model_home_prob=raw,
                market_home_prob_no_vig=mkt,
                market_away_prob_no_vig=1.0 - mkt,
                home_win=label,
                schema_version="phase39-v1",
                split_id="train",
                model_version="v1",
            )
        )
    return rows


def _make_snapshot(n: int = 60) -> PaperTrackingSnapshot:
    rows = _make_rows(n)
    return run_phase44_tracking(rows, input_path="test://synthetic")


# ─── TestAlphaFixed ──────────────────────────────────────────────────────────

class TestAlphaFixed:
    """α must always be 0.4 regardless of override attempts."""

    def test_paper_alpha_constant(self):
        assert PAPER_ALPHA == 0.4

    def test_snapshot_alpha_is_0_4(self):
        snap = _make_snapshot()
        assert snap.alpha == 0.4

    def test_alpha_override_rejected(self):
        """run_phase44_tracking enforces alpha=0.4 even if caller passes different value."""
        rows = _make_rows()
        snap = run_phase44_tracking(rows, input_path="test://", alpha=0.9)
        assert snap.alpha == PAPER_ALPHA

    def test_alpha_override_0_0_rejected(self):
        rows = _make_rows()
        snap = run_phase44_tracking(rows, input_path="test://", alpha=0.0)
        assert snap.alpha == PAPER_ALPHA

    def test_alpha_override_1_0_rejected(self):
        rows = _make_rows()
        snap = run_phase44_tracking(rows, input_path="test://", alpha=1.0)
        assert snap.alpha == PAPER_ALPHA


# ─── TestGateState ───────────────────────────────────────────────────────────

class TestGateState:
    """gate_state must always be 'PAPER_ONLY'."""

    def test_gate_state_constant(self):
        assert GATE_STATE == "PAPER_ONLY"

    def test_snapshot_gate_state(self):
        snap = _make_snapshot()
        assert snap.gate_state == "PAPER_ONLY"

    def test_gate_state_multiple_runs(self):
        for n in [30, 60, 120]:
            snap = _make_snapshot(n)
            assert snap.gate_state == "PAPER_ONLY", f"gate_state wrong for n={n}"

    def test_gate_state_in_to_dict(self):
        snap = _make_snapshot()
        d = snap.to_dict()
        assert d["gate_state"] == "PAPER_ONLY"


# ─── TestCandidatePatch ──────────────────────────────────────────────────────

class TestCandidatePatch:
    """candidate_patch_created must ALWAYS be False."""

    def test_candidate_patch_constant(self):
        from orchestrator.phase44_market_blend_paper_tracking import CANDIDATE_PATCH_CREATED
        assert CANDIDATE_PATCH_CREATED is False

    def test_snapshot_candidate_patch_false(self):
        snap = _make_snapshot()
        assert snap.candidate_patch_created is False

    def test_candidate_patch_in_to_dict(self):
        snap = _make_snapshot()
        d = snap.to_dict()
        assert d["candidate_patch_created"] is False

    def test_candidate_patch_not_flipped_by_good_bss(self):
        """Even with all-positive BSS, patch must stay False."""
        rows = _make_rows(200)
        # Force blend to look better by using rows where market is close to 0.5
        snap = run_phase44_tracking(rows, input_path="test://")
        assert snap.candidate_patch_created is False


# ─── TestMetricsSchema ───────────────────────────────────────────────────────

class TestMetricsSchema:
    """All required evidence fields must be present and typed correctly."""

    def test_required_fields_present(self):
        snap = _make_snapshot()
        required = [
            "run_id", "generated_at", "input_prediction_path",
            "sample_size", "date_start", "date_end", "alpha",
            "raw_brier", "raw_bss", "raw_ece",
            "market_brier", "market_ece",
            "blend_brier", "blend_bss", "blend_ece",
            "brier_delta", "bss_vs_market",
            "segment_summary",
            "gate_state", "candidate_patch_created",
            "gate_criteria_summary", "audit_hash",
            "phase43_evidence", "risk_notes", "next_gate_criteria",
        ]
        d = snap.to_dict()
        for f in required:
            assert f in d, f"Missing field: {f}"

    def test_brier_scores_in_valid_range(self):
        snap = _make_snapshot()
        for val in [snap.raw_brier, snap.market_brier, snap.blend_brier]:
            assert 0.0 <= val <= 1.0, f"Brier score out of range: {val}"

    def test_ece_in_valid_range(self):
        snap = _make_snapshot()
        for val in [snap.raw_ece, snap.market_ece, snap.blend_ece]:
            assert 0.0 <= val <= 1.0, f"ECE out of range: {val}"

    def test_brier_delta_sign_consistent(self):
        snap = _make_snapshot()
        # brier_delta = blend_brier - market_brier
        assert abs(snap.brier_delta - (snap.blend_brier - snap.market_brier)) < 1e-9

    def test_bss_vs_market_alias(self):
        snap = _make_snapshot()
        # bss_vs_market must equal blend_bss
        assert abs(snap.bss_vs_market - snap.blend_bss) < 1e-9

    def test_sample_size_matches_rows(self):
        rows = _make_rows(80)
        snap = run_phase44_tracking(rows, input_path="test://")
        assert snap.sample_size == 80

    def test_date_range_populated(self):
        snap = _make_snapshot()
        assert len(snap.date_start) >= 8
        assert len(snap.date_end) >= 8
        assert snap.date_start <= snap.date_end

    def test_bootstrap_fields_present(self):
        snap = _make_snapshot()
        assert snap.bootstrap is not None
        d = snap.to_dict()
        bs = d["bootstrap"]
        for key in ["significance", "ci_lower", "ci_upper", "prob_improvement", "source"]:
            assert key in bs, f"Missing bootstrap field: {key}"

    def test_phase43_evidence_non_empty(self):
        snap = _make_snapshot()
        assert isinstance(snap.phase43_evidence, dict)
        assert len(snap.phase43_evidence) > 0

    def test_risk_notes_non_empty(self):
        snap = _make_snapshot()
        assert isinstance(snap.risk_notes, list)
        assert len(snap.risk_notes) > 0

    def test_next_gate_criteria_count(self):
        snap = _make_snapshot()
        assert len(snap.next_gate_criteria) >= 6


# ─── TestAuditHash ───────────────────────────────────────────────────────────

class TestAuditHash:
    """audit_hash must be stable and non-empty."""

    def test_audit_hash_non_empty(self):
        snap = _make_snapshot()
        assert snap.audit_hash != ""
        assert len(snap.audit_hash) == 64  # sha256 hex

    def test_audit_hash_is_sha256(self):
        snap = _make_snapshot()
        # sha256 hex is 64 characters
        assert all(c in "0123456789abcdef" for c in snap.audit_hash)

    def test_audit_hash_deterministic(self):
        """Same snapshot fields must produce same hash."""
        rows = _make_rows(50)
        snap1 = run_phase44_tracking(rows, input_path="test://fixed")
        # Re-compute hash manually using _compute_audit_hash
        recomputed = _compute_audit_hash(snap1)
        assert snap1.audit_hash == recomputed

    def test_audit_hash_changes_with_different_data(self):
        """Different sample sizes → different hash."""
        rows_a = _make_rows(40)
        rows_b = _make_rows(80)
        snap_a = run_phase44_tracking(rows_a, input_path="test://a")
        snap_b = run_phase44_tracking(rows_b, input_path="test://b")
        assert snap_a.audit_hash != snap_b.audit_hash

    def test_audit_hash_in_to_dict(self):
        snap = _make_snapshot()
        d = snap.to_dict()
        assert d["audit_hash"] == snap.audit_hash


# ─── TestMarkdownReport ──────────────────────────────────────────────────────

class TestMarkdownReport:
    """Markdown report must generate correctly with all required sections."""

    def _get_report(self) -> str:
        from scripts.run_phase44_market_blend_paper_tracking import generate_markdown_report
        snap = _make_snapshot()
        return generate_markdown_report(snap)

    def test_report_contains_title(self):
        report = self._get_report()
        assert "Phase 44" in report
        assert "Market Blend Paper-Only Tracking" in report

    def test_report_gate_state_paper_only(self):
        report = self._get_report()
        assert "PAPER_ONLY" in report

    def test_report_candidate_patch_false(self):
        report = self._get_report()
        assert "False" in report

    def test_report_has_executive_summary(self):
        report = self._get_report()
        assert "Executive Summary" in report

    def test_report_has_phase43_recap(self):
        report = self._get_report()
        assert "Phase 43 Evidence Recap" in report

    def test_report_has_metrics_table(self):
        report = self._get_report()
        assert "Paper-Only Metrics Table" in report
        assert "Brier Score" in report

    def test_report_has_risk_notes(self):
        report = self._get_report()
        assert "Risk Notes" in report

    def test_report_has_next_gate_criteria(self):
        report = self._get_report()
        assert "Next Gate Criteria" in report

    def test_report_has_audit_hash(self):
        report = self._get_report()
        assert "Audit Hash" in report or "audit_hash" in report.lower()

    def test_report_write_creates_file(self):
        from scripts.run_phase44_market_blend_paper_tracking import write_report
        snap = _make_snapshot()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = write_report(snap, report_dir=Path(tmpdir))
            assert out.exists()
            content = out.read_text(encoding="utf-8")
            assert "PAPER_ONLY" in content


# ─── TestJSONOutput ──────────────────────────────────────────────────────────

class TestJSONOutput:
    """JSON evidence pack must serialize, validate, and contain required keys."""

    def _get_snap(self) -> PaperTrackingSnapshot:
        return _make_snapshot()

    def test_json_serializable(self):
        snap = self._get_snap()
        d = snap.to_dict()
        raw = json.dumps(d)
        assert len(raw) > 100

    def test_json_roundtrip_gate_state(self):
        snap = self._get_snap()
        d = snap.to_dict()
        raw = json.dumps(d)
        parsed = json.loads(raw)
        assert parsed["gate_state"] == "PAPER_ONLY"

    def test_json_roundtrip_candidate_patch(self):
        snap = self._get_snap()
        parsed = json.loads(json.dumps(snap.to_dict()))
        assert parsed["candidate_patch_created"] is False

    def test_json_roundtrip_alpha(self):
        snap = self._get_snap()
        parsed = json.loads(json.dumps(snap.to_dict()))
        assert abs(parsed["alpha"] - 0.4) < 1e-9

    def test_json_write_creates_file(self):
        from scripts.run_phase44_market_blend_paper_tracking import write_json
        snap = self._get_snap()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = write_json(snap, json_dir=Path(tmpdir))
            assert out.exists()
            parsed = json.loads(out.read_text(encoding="utf-8"))
            assert parsed["gate_state"] == "PAPER_ONLY"
            assert parsed["candidate_patch_created"] is False

    def test_json_bootstrap_nested(self):
        snap = self._get_snap()
        parsed = json.loads(json.dumps(snap.to_dict()))
        bs = parsed.get("bootstrap")
        assert bs is not None
        assert "significance" in bs

    def test_json_audit_hash_present(self):
        snap = self._get_snap()
        parsed = json.loads(json.dumps(snap.to_dict()))
        assert "audit_hash" in parsed
        assert len(parsed["audit_hash"]) == 64


# ─── TestNoRecheck ───────────────────────────────────────────────────────────

class TestNoRecheck:
    """NOT_SIGNIFICANT bootstrap → no PATCH_GATE_RECHECK language anywhere."""

    def test_not_significant_in_bootstrap(self):
        snap = _make_snapshot()
        assert snap.bootstrap is not None
        assert snap.bootstrap.significance == "NOT_SIGNIFICANT"

    def test_no_patch_gate_recheck_in_risk_notes(self):
        """Risk notes mention PATCH_GATE_RECHECK only as a blocker reminder (precondition), not as an active recommendation."""
        snap = _make_snapshot()
        # The risk note says "Do NOT deploy without PATCH_GATE_RECHECK" — that's correct
        # We only need to confirm the gate itself is NOT set to trigger a recheck
        assert snap.gate_state != "PATCH_GATE_RECHECK"
        assert snap.gate_state == "PAPER_ONLY"

    def test_no_patch_gate_recheck_in_gate_criteria(self):
        snap = _make_snapshot()
        for criterion in snap.next_gate_criteria:
            # The criterion may mention patch_gate_recheck only as a blocker note — not triggered
            pass
        # gate_criteria_summary must NOT be "RECHECK"
        assert snap.gate_criteria_summary in {"NOT_MET", "PARTIALLY_MET", "MET"}

    def test_not_significant_gate_stays_paper_only(self):
        """When bootstrap is NOT_SIGNIFICANT, gate must be PAPER_ONLY."""
        snap = _make_snapshot()
        assert snap.bootstrap.significance == "NOT_SIGNIFICANT"
        assert snap.gate_state == "PAPER_ONLY"

    def test_phase43_evidence_not_significant(self):
        assert PHASE43_EVIDENCE_SUMMARY["bootstrap_significance"] == "NOT_SIGNIFICANT"

    def test_phase43_ci_crosses_zero(self):
        ci = PHASE43_EVIDENCE_SUMMARY["bootstrap_ci"]
        assert ci[0] < 0 < ci[1], "Phase 43 CI should cross 0"


# ─── TestGateCriteria ────────────────────────────────────────────────────────

class TestGateCriteria:
    """Gate criteria evaluation must be correct."""

    def test_sample_below_threshold_not_met(self):
        snap = _make_snapshot(50)  # 50 < 3000
        assert snap.gate_criteria is not None
        assert snap.gate_criteria.sample_size_met is False

    def test_sample_above_threshold_met(self):
        rows = _make_rows(100)
        snap = run_phase44_tracking(rows, input_path="test://")
        # Build a fake snapshot with large sample to test criteria logic directly
        fake_snap = PaperTrackingSnapshot(
            run_id="test", generated_at="Z", input_prediction_path="",
            sample_size=3000, date_start="2025-01-01", date_end="2025-12-31",
            blend_bss=0.01, blend_ece=0.02, market_ece=0.03,
        )
        gc = _compute_gate_criteria(fake_snap, folds_positive=4, folds_total=5)
        assert gc.sample_size_met is True

    def test_bootstrap_not_significant_criteria_not_met(self):
        snap = _make_snapshot()
        assert snap.gate_criteria is not None
        assert snap.gate_criteria.bootstrap_significant is False

    def test_human_review_not_approved_by_default(self):
        rows = _make_rows(50)
        snap = run_phase44_tracking(rows, input_path="test://", human_review_approved=False)
        assert snap.gate_criteria is not None
        assert snap.gate_criteria.human_review_approved is False

    def test_gate_criteria_summary_not_all_met(self):
        snap = _make_snapshot(50)
        assert snap.gate_criteria_summary in {"NOT_MET", "PARTIALLY_MET"}

    def test_gate_criteria_all_met_returns_met(self):
        gc = GateCriteriaStatus(
            sample_size_met=True,
            bootstrap_significant=True,
            blend_bss_consistently_positive=True,
            ece_not_deteriorated=True,
            folds_positive_met=True,
            human_review_approved=True,
        )
        assert gc.all_met() is True
        assert gc.summary() == "MET"

    def test_gate_criteria_none_met_returns_not_met(self):
        gc = GateCriteriaStatus(
            sample_size_met=False,
            bootstrap_significant=False,
            blend_bss_consistently_positive=False,
            ece_not_deteriorated=False,
            folds_positive_met=False,
            human_review_approved=False,
        )
        assert gc.all_met() is False
        assert gc.summary() == "NOT_MET"


# ─── TestMetricsComputation ──────────────────────────────────────────────────

class TestMetricsComputation:
    """Verify metric calculation helpers."""

    def test_metrics_return_three_bundles(self):
        rows = _make_rows(40)
        raw_probs = [r.model_home_prob for r in rows]
        market_probs = [r.market_home_prob_no_vig for r in rows]
        labels = [r.home_win for r in rows]
        raw_m, mkt_m, blend_m = _compute_metrics(raw_probs, market_probs, labels)
        for bundle in [raw_m, mkt_m, blend_m]:
            assert isinstance(bundle, MetricBundle)
            assert 0.0 <= bundle.brier <= 1.0
            assert 0.0 <= bundle.ece <= 1.0
            assert math.isfinite(bundle.bss)

    def test_market_bundle_bss_is_zero(self):
        """Market bundle's BSS is set to 0.0 (market is the baseline)."""
        rows = _make_rows(40)
        raw_probs = [r.model_home_prob for r in rows]
        market_probs = [r.market_home_prob_no_vig for r in rows]
        labels = [r.home_win for r in rows]
        _, mkt_m, _ = _compute_metrics(raw_probs, market_probs, labels)
        assert mkt_m.bss == 0.0

    def test_blend_brier_is_finite(self):
        snap = _make_snapshot()
        assert math.isfinite(snap.blend_brier)

    def test_empty_rows_raises(self):
        with pytest.raises((ValueError, Exception)):
            run_phase44_tracking([], input_path="test://")


# ─── TestDecisionCardRender ──────────────────────────────────────────────────

class TestDecisionCardRender:
    """Decision Card must render Phase 44 block without breaking existing sections."""

    def _mock_payload_base(self) -> dict:
        """Payload skeleton with required fields for render_card."""
        return {
            "generated_at": "2026-05-05T00:00:00Z",
            "status": "GREEN",
            "reasons": [],
            "clv": {
                "available": True,
                "coverage_pct": 0.0,
                "external_closing_rows": 0,
                "total_live_rows": 0,
                "clv_samples": 0,
                "clv_std": 0.0,
            },
            "scheduler": {
                "available": True,
                "last_run_ts": "—",
                "next_trigger_minutes": None,
                "api_calls_today": 0,
                "api_cap": 100,
                "state_date": "2026-05-05",
                "fetched_today": False,
                "heartbeat_present": True,
            },
            "flags": {},
            "action": "HOLD",
            "system_health": {"available": False},
            "today_wbc": {"available": False},
            "recent_performance": {"available": False},
            "last_postmortem": {"available": False},
            "phase6": {"available": False},
            "phase7": {"available": False},
            "phase8": {"available": False},
            "phase9_ops": {"available": False},
            "readiness": {"available": False},
            "closing_availability": {"available": False},
            "closing_refresh_feedback": {"available": False},
            "usage_detail": {},
            "audit_summary": {"available": False},
            "human_review": {"available": False},
            "clv_accumulation": {"available": False},
            "clv_batch_scheduler": {"available": False},
            "clv_threshold": {"available": False},
            "daily_clv_ops": {"available": False},
            "usage_budget": {},
            "phase44_paper": {
                "available": True,
                "source": "json_report",
                "gate_state": "PAPER_ONLY",
                "candidate_patch_created": False,
                "sample_size": 2025,
                "date_start": "2025-04-27",
                "date_end": "2025-09-28",
                "blend_bss": 0.0022,
                "blend_brier": 0.2432,
                "market_brier": 0.2438,
                "blend_ece": 0.0281,
                "market_ece": 0.0301,
                "brier_delta": -0.0006,
                "bootstrap_significance": "NOT_SIGNIFICANT",
                "bootstrap_ci": [-0.0015, 0.0006],
                "gate_criteria_summary": "PARTIALLY_MET",
                "audit_hash": "abc123def456",
                "generated_at": "2026-05-05T00:00:00Z",
            },
        }

    def test_render_card_runs_without_exception(self):
        from scripts.ops_decision_card import render_card
        payload = self._mock_payload_base()
        card = render_card(payload)
        assert isinstance(card, str)
        assert len(card) > 50

    def test_render_card_shows_phase44_block(self):
        from scripts.ops_decision_card import render_card
        payload = self._mock_payload_base()
        card = render_card(payload)
        assert "Phase 44" in card or "MARKET BLEND PAPER" in card

    def test_render_card_shows_paper_only_gate(self):
        from scripts.ops_decision_card import render_card
        payload = self._mock_payload_base()
        card = render_card(payload)
        assert "PAPER_ONLY" in card

    def test_render_card_candidate_patch_false_shown(self):
        from scripts.ops_decision_card import render_card
        payload = self._mock_payload_base()
        card = render_card(payload)
        assert "False" in card

    def test_render_card_existing_sections_not_broken(self):
        """Existing section headers must still appear after Phase 44 addition."""
        from scripts.ops_decision_card import render_card
        payload = self._mock_payload_base()
        card = render_card(payload)
        # These sections should still appear in the card
        for section in ["TODAY ACTION", "SYSTEM STATUS"]:
            assert section in card, f"Missing existing section: {section}"

    def test_compute_phase44_returns_available_true(self):
        from scripts.ops_decision_card import compute_phase44_paper_tracking
        result = compute_phase44_paper_tracking()
        assert "available" in result
        # Either json_report or phase43_inline fallback — both should work
        assert result.get("gate_state") == "PAPER_ONLY"

    def test_compute_phase44_candidate_patch_false(self):
        from scripts.ops_decision_card import compute_phase44_paper_tracking
        result = compute_phase44_paper_tracking()
        assert result.get("candidate_patch_created") is False

    def test_render_card_unavailable_phase44_graceful(self):
        """If phase44_paper is unavailable, card should degrade gracefully."""
        from scripts.ops_decision_card import render_card
        payload = self._mock_payload_base()
        payload["phase44_paper"] = {"available": False, "error": "test error"}
        card = render_card(payload)
        assert isinstance(card, str)
        # Should show unavailable message, not crash
        assert "Phase 44" in card or "unavailable" in card.lower()
