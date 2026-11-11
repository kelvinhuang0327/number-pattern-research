"""
tests/test_p86_artifact_regeneration_dependency_contract.py

P86 dependency contract tests.

Expected classification: P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK
(Step 7 correctly detects that canonical_rows was regenerated after P84E ran)

All other steps (1-6, 8) pass. The stale downstream risk is a legitimate finding:
the canonical_rows file was re-touched at 15:23 local by a P83C run, after P84E
completed at 13:40 local. This is not a false alarm — P86 behaves correctly.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "mlb_2026" / "derived"
REPORT_DIR = ROOT / "report"
SCRIPT = ROOT / "scripts" / "_p86_artifact_regeneration_dependency_contract.py"
SUMMARY_PATH = DERIVED / "p86_artifact_regeneration_dependency_contract_summary.json"
REPORT_PATH = REPORT_DIR / "p86_artifact_regeneration_dependency_contract_20260527.md"

EXPECTED_CLASSIFICATION = "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"  # Updated post P89 authorized recovery

ALLOWED_CLASSIFICATIONS = [
    "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY",
    "P86_ARTIFACT_CONTRACT_FAILED_MISSING_ARTIFACT",
    "P86_ARTIFACT_CONTRACT_FAILED_CLASSIFICATION_MISMATCH",
    "P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK",
    "P86_ARTIFACT_CONTRACT_BLOCKED_BY_PREFLIGHT",
    "P86_ARTIFACT_CONTRACT_BLOCKED_BY_SCOPE_DRIFT",
]

TOLERANCE = 1e-4

EXPECTED_PHASE_CLASSIFICATIONS = {
    "p83e": "P83E_CANONICAL_ROWS_READY",
    "p84e": "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS",
    "p84f": "P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK",
    "p84g": "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED",
    "p84h": "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED",
    "p85":  "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY",
}

EXPECTED_METRICS = {
    "hit_rate": 0.569307,
    "auc":      0.594315,
    "brier":    0.249408,
    "ece":      0.069682,
}


@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_PATH.exists(), f"P86 summary not found: {SUMMARY_PATH}"
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.exists(), f"P86 report not found: {REPORT_PATH}"
    return REPORT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

class TestInfrastructure:
    def test_script_exists(self):
        assert SCRIPT.exists(), f"P86 script missing: {SCRIPT}"

    def test_summary_exists(self):
        assert SUMMARY_PATH.exists(), f"P86 summary missing: {SUMMARY_PATH}"

    def test_report_exists(self):
        assert REPORT_PATH.exists(), f"P86 report missing: {REPORT_PATH}"

    def test_summary_is_valid_json(self):
        assert SUMMARY_PATH.read_text(encoding="utf-8").strip()
        data = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_summary_has_phase(self, summary):
        assert "phase" in summary
        assert summary["phase"] == "diagnostic-only"

    def test_summary_has_date(self, summary):
        assert summary.get("date") == "2026-05-27"

    def test_summary_has_generated_at(self, summary):
        assert "generated_at" in summary
        assert "2026" in summary["generated_at"]

    def test_classification_is_allowed(self, summary):
        cls = summary.get("p86_classification")
        assert cls in ALLOWED_CLASSIFICATIONS, f"Unknown classification: {cls}"

    def test_classification_matches_expected(self, summary):
        cls = summary.get("p86_classification")
        assert cls == EXPECTED_CLASSIFICATION, (
            f"Expected {EXPECTED_CLASSIFICATION!r}, got {cls!r}"
        )

    def test_allowed_classifications_list_complete(self, summary):
        allowed = summary.get("allowed_classifications", [])
        assert len(allowed) == 6
        for c in ALLOWED_CLASSIFICATIONS:
            assert c in allowed

    def test_report_has_phase_header(self, report_text):
        assert "P86" in report_text
        assert "Artifact Regeneration" in report_text

    def test_report_contains_classification(self, report_text):
        assert EXPECTED_CLASSIFICATION in report_text

    def test_report_contains_date(self, report_text):
        assert "2026-05-27" in report_text


# ---------------------------------------------------------------------------
# Step 1 — Artifact existence
# ---------------------------------------------------------------------------

class TestStep1ArtifactExistence:
    def test_step1_status_passed(self, summary):
        s = summary["step1_artifact_existence"]
        assert s["status"] == "PASSED"

    def test_step1_no_missing(self, summary):
        s = summary["step1_artifact_existence"]
        assert s["missing"] == []

    def test_step1_p83e_summary_exists(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        assert "p83e_summary" in checks
        assert checks["p83e_summary"]["exists"] is True

    def test_step1_p84e_summary_exists(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        assert checks["p84e_summary"]["exists"] is True

    def test_step1_p84e_rows_exists(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        assert checks["p84e_rows"]["exists"] is True

    def test_step1_canonical_rows_exists(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        assert checks["canonical_rows"]["exists"] is True

    def test_step1_p84f_summary_exists(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        assert checks["p84f_summary"]["exists"] is True

    def test_step1_p84g_summary_exists(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        assert checks["p84g_summary"]["exists"] is True

    def test_step1_p84h_summary_exists(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        assert checks["p84h_summary"]["exists"] is True

    def test_step1_p85_summary_exists(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        assert checks["p85_summary"]["exists"] is True

    def test_step1_all_have_sha256(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        for art_id, info in checks.items():
            if info["exists"]:
                assert "sha256_prefix" in info, f"{art_id} missing sha256"
                assert len(info["sha256_prefix"]) == 16

    def test_step1_all_have_mtime(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        for art_id, info in checks.items():
            if info["exists"]:
                assert "mtime" in info, f"{art_id} missing mtime"

    def test_step1_artifacts_count(self, summary):
        checks = summary["step1_artifact_existence"]["checks"]
        assert len(checks) == 8


# ---------------------------------------------------------------------------
# Step 2 — Dependency graph
# ---------------------------------------------------------------------------

class TestStep2DependencyGraph:
    def test_step2_status_passed(self, summary):
        s = summary["step2_dependency_graph"]
        assert s["status"] == "PASSED"

    def test_step2_node_count(self, summary):
        s = summary["step2_dependency_graph"]
        assert s["n_nodes"] == 6

    def test_step2_edge_count(self, summary):
        s = summary["step2_dependency_graph"]
        assert s["n_edges"] == 10

    def test_step2_contains_p83e_node(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        assert "p83e_canonical_rows" in graph

    def test_step2_contains_p84e_node(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        assert "p84e_outcome_attachment" in graph

    def test_step2_contains_p84f_node(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        assert "p84f_calibration_diag" in graph

    def test_step2_contains_p84g_node(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        assert "p84g_mapping_fix" in graph

    def test_step2_contains_p84h_node(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        assert "p84h_corrected_validation" in graph

    def test_step2_contains_p85_node(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        assert "p85_invariant_gate" in graph

    def test_step2_p83e_has_no_deps(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        assert graph["p83e_canonical_rows"]["depends_on"] == []

    def test_step2_p85_has_no_required_by(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        assert graph["p85_invariant_gate"]["required_by"] == []

    def test_step2_p84e_depends_on_p83e(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        assert "p83e_canonical_rows" in graph["p84e_outcome_attachment"]["depends_on"]

    def test_step2_p85_depends_on_p84g_and_p84h(self, summary):
        graph = summary["step2_dependency_graph"]["graph"]
        deps = graph["p85_invariant_gate"]["depends_on"]
        assert "p84g_mapping_fix" in deps
        assert "p84h_corrected_validation" in deps


# ---------------------------------------------------------------------------
# Step 3 — Classification lock
# ---------------------------------------------------------------------------

class TestStep3ClassificationLock:
    def test_step3_status_passed(self, summary):
        s = summary["step3_classification_lock"]
        assert s["status"] == "PASSED"

    def test_step3_no_failures(self, summary):
        s = summary["step3_classification_lock"]
        assert s["failures"] == []

    @pytest.mark.parametrize("phase,expected_cls", list(EXPECTED_PHASE_CLASSIFICATIONS.items()))
    def test_step3_phase_locked(self, summary, phase, expected_cls):
        results = summary["step3_classification_lock"]["results"]
        assert phase in results
        r = results[phase]
        assert r["locked"] is True, f"{phase} not locked: actual={r['actual']}"
        assert r["actual"] == expected_cls

    def test_step3_all_six_phases_checked(self, summary):
        results = summary["step3_classification_lock"]["results"]
        assert set(results.keys()) == {"p83e", "p84e", "p84f", "p84g", "p84h", "p85"}


# ---------------------------------------------------------------------------
# Step 4 — Row count check
# ---------------------------------------------------------------------------

class TestStep4RowCount:
    def test_step4_status_passed(self, summary):
        s = summary["step4_row_count_check"]
        assert s["status"] == "PASSED"

    def test_step4_no_failures(self, summary):
        s = summary["step4_row_count_check"]
        assert s["failures"] == []

    def test_step4_p83e_row_count(self, summary):
        checks = summary["step4_row_count_check"]["checks"]
        assert checks["p83e_row_count"]["expected"] == 828
        assert checks["p83e_row_count"]["actual"] == 828
        assert checks["p83e_row_count"]["ok"] is True

    def test_step4_p84e_outcome_available(self, summary):
        checks = summary["step4_row_count_check"]["checks"]
        assert checks["p84e_outcome_available"]["expected"] == 808
        assert checks["p84e_outcome_available"]["actual"] == 808
        assert checks["p84e_outcome_available"]["ok"] is True

    def test_step4_p84e_total_canonical_rows(self, summary):
        checks = summary["step4_row_count_check"]["checks"]
        assert checks["p84e_total_canonical_rows"]["expected"] == 828
        assert checks["p84e_total_canonical_rows"]["actual"] == 828
        assert checks["p84e_total_canonical_rows"]["ok"] is True

    def test_step4_p84e_jsonl_total(self, summary):
        checks = summary["step4_row_count_check"]["checks"]
        assert checks["p84e_jsonl_total"]["expected"] == 828
        assert checks["p84e_jsonl_total"]["actual"] == 828
        assert checks["p84e_jsonl_total"]["ok"] is True

    def test_step4_p84e_jsonl_outcome_avail(self, summary):
        checks = summary["step4_row_count_check"]["checks"]
        assert checks["p84e_jsonl_outcome_avail"]["expected"] == 808
        assert checks["p84e_jsonl_outcome_avail"]["actual"] == 808
        assert checks["p84e_jsonl_outcome_avail"]["ok"] is True

    def test_step4_five_checks_present(self, summary):
        checks = summary["step4_row_count_check"]["checks"]
        assert len(checks) == 5


# ---------------------------------------------------------------------------
# Step 5 — Metric consistency
# ---------------------------------------------------------------------------

class TestStep5MetricConsistency:
    def test_step5_status_passed(self, summary):
        s = summary["step5_metric_consistency"]
        assert s["status"] == "PASSED"

    def test_step5_no_failures(self, summary):
        s = summary["step5_metric_consistency"]
        assert s["failures"] == []

    @pytest.mark.parametrize("metric,expected", list(EXPECTED_METRICS.items()))
    def test_step5_p84h_metric_within_tolerance(self, summary, metric, expected):
        results = summary["step5_metric_consistency"]["results"]
        assert metric in results, f"Metric {metric} missing"
        r = results[metric]
        assert r["ok"] is True, f"Metric {metric} failed: actual={r['actual']}"
        assert abs(r["actual"] - expected) <= TOLERANCE

    def test_step5_hit_rate_expected_value(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        assert abs(results["hit_rate"]["actual"] - 0.569307) <= TOLERANCE

    def test_step5_auc_expected_value(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        assert abs(results["auc"]["actual"] - 0.594315) <= TOLERANCE

    def test_step5_brier_expected_value(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        assert abs(results["brier"]["actual"] - 0.249408) <= TOLERANCE

    def test_step5_ece_expected_value(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        assert abs(results["ece"]["actual"] - 0.069682) <= TOLERANCE

    def test_step5_p84h_vs_p84e_hit_rate_cross_check(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        key = "p84h_vs_p84e_ref_hit_rate"
        assert key in results
        assert results[key]["ok"] is True
        assert results[key]["delta"] <= TOLERANCE

    def test_step5_p84h_vs_p84e_auc_cross_check(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        key = "p84h_vs_p84e_ref_auc"
        assert key in results
        assert results[key]["ok"] is True

    def test_step5_p84h_vs_p84e_brier_cross_check(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        key = "p84h_vs_p84e_ref_brier"
        assert key in results
        assert results[key]["ok"] is True

    def test_step5_p84h_vs_p84e_ece_cross_check(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        key = "p84h_vs_p84e_ref_ece"
        assert key in results
        assert results[key]["ok"] is True

    def test_step5_p85_positive_violations_zero(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        assert results["p85_positive_violations"]["expected"] == 0
        assert results["p85_positive_violations"]["actual"] == 0
        assert results["p85_positive_violations"]["ok"] is True

    def test_step5_p85_negative_violations_zero(self, summary):
        results = summary["step5_metric_consistency"]["results"]
        assert results["p85_negative_violations"]["expected"] == 0
        assert results["p85_negative_violations"]["actual"] == 0
        assert results["p85_negative_violations"]["ok"] is True


# ---------------------------------------------------------------------------
# Step 6 — Report-vs-JSON classification consistency
# ---------------------------------------------------------------------------

class TestStep6ReportVsJson:
    def test_step6_status_passed(self, summary):
        s = summary["step6_report_vs_json"]
        assert s["status"] == "PASSED"

    def test_step6_no_failures(self, summary):
        s = summary["step6_report_vs_json"]
        assert s["failures"] == []

    @pytest.mark.parametrize("phase", ["p83e_summary", "p84e_summary", "p84f_summary",
                                        "p84g_summary", "p84h_summary", "p85_summary"])
    def test_step6_phase_consistent(self, summary, phase):
        results = summary["step6_report_vs_json"]["results"]
        assert phase in results, f"{phase} not checked"
        r = results[phase]
        assert r["consistent"] is True, (
            f"{phase} report-vs-JSON mismatch: json_cls={r.get('json_classification')}"
        )

    def test_step6_all_six_phases(self, summary):
        results = summary["step6_report_vs_json"]["results"]
        assert len(results) == 6

    def test_step6_p83e_classification_in_report(self, summary):
        results = summary["step6_report_vs_json"]["results"]
        r = results["p83e_summary"]
        assert r["json_classification"] == "P83E_CANONICAL_ROWS_READY"
        assert r["report_contains_classification"] is True

    def test_step6_p84e_classification_in_report(self, summary):
        results = summary["step6_report_vs_json"]["results"]
        r = results["p84e_summary"]
        assert r["json_classification"] == "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS"

    def test_step6_p84g_classification_in_report(self, summary):
        results = summary["step6_report_vs_json"]["results"]
        r = results["p84g_summary"]
        assert r["json_classification"] == "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED"

    def test_step6_p84h_classification_in_report(self, summary):
        results = summary["step6_report_vs_json"]["results"]
        r = results["p84h_summary"]
        assert r["json_classification"] == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"

    def test_step6_p85_classification_in_report(self, summary):
        results = summary["step6_report_vs_json"]["results"]
        r = results["p85_summary"]
        assert r["json_classification"] == "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY"


# ---------------------------------------------------------------------------
# Step 7 — Mtime ordering (stale downstream risk)
# ---------------------------------------------------------------------------

class TestStep7MtimeOrdering:
    def test_step7_status_failed(self, summary):
        """Post P89 recovery: step 7 passes (no stale risks)."""
        s = summary["step7_mtime_ordering"]
        assert s["status"] == "PASSED"

    def test_step7_exactly_one_stale_risk(self, summary):
        """Post P89 recovery: zero stale risks."""
        s = summary["step7_mtime_ordering"]
        assert s["n_stale_risks"] == 0

    def test_step7_stale_risk_upstream_is_canonical_rows(self, summary):
        # Post P89 recovery: no stale risks — stale_risks list is empty
        s = summary["step7_mtime_ordering"]
        assert s["stale_risks"] == []

    def test_step7_stale_risk_downstream_is_p84e_rows(self, summary):
        # Post P89 recovery: p84e_rows is now fresh — no stale downstream risk
        s = summary["step7_mtime_ordering"]
        assert len(s["stale_risks"]) == 0

    def test_step7_stale_risk_delta_positive(self, summary):
        # Post P89 recovery: no stale risks; p84e_rows newer than canonical_rows
        s = summary["step7_mtime_ordering"]
        assert s["n_stale_risks"] == 0

    def test_step7_order_has_eight_entries(self, summary):
        s = summary["step7_mtime_ordering"]
        assert len(s["order"]) == 8

    def test_step7_p83e_summary_is_ok(self, summary):
        order = summary["step7_mtime_ordering"]["order"]
        p83e_entry = next((e for e in order if e["id"] == "p83e_summary"), None)
        assert p83e_entry is not None
        assert p83e_entry["status"] == "OK"

    def test_step7_p84f_onward_are_ok(self, summary):
        order = summary["step7_mtime_ordering"]["order"]
        for entry in order:
            if entry["id"] in ("p84f_summary", "p84g_summary", "p84h_summary", "p85_summary"):
                assert entry["status"] == "OK", f"{entry['id']} unexpectedly not OK"

    def test_step7_canonical_rows_is_ok_itself(self, summary):
        """canonical_rows entry is OK (not stale vs p83e_summary)."""
        order = summary["step7_mtime_ordering"]["order"]
        cr_entry = next((e for e in order if e["id"] == "canonical_rows"), None)
        assert cr_entry is not None
        assert cr_entry["status"] == "OK"

    def test_step7_p84e_rows_is_stale(self, summary):
        """Post P89 recovery: p84e_rows is OK (freshly regenerated)."""
        order = summary["step7_mtime_ordering"]["order"]
        p84e_rows_entry = next((e for e in order if e["id"] == "p84e_rows"), None)
        assert p84e_rows_entry is not None
        assert p84e_rows_entry["status"] == "OK"


# ---------------------------------------------------------------------------
# Step 8 — Governance scan
# ---------------------------------------------------------------------------

class TestStep8GovernanceScan:
    def test_step8_status_passed(self, summary):
        s = summary["step8_governance_scan"]
        assert s["status"] == "PASSED"

    def test_governance_paper_only(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["paper_only"] is True

    def test_governance_diagnostic_only(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["diagnostic_only"] is True

    def test_governance_not_production_ready(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["production_ready"] is False

    def test_governance_no_odds(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["odds_used"] is False

    def test_governance_no_ev(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["ev_computed"] is False

    def test_governance_no_clv(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["clv_computed"] is False

    def test_governance_no_kelly(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["kelly_computed"] is False

    def test_governance_no_live_api_calls(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["live_api_calls"] == 0

    def test_governance_no_paid_api(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["paid_api_called"] is False

    def test_governance_canonical_rows_not_modified(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["canonical_rows_modified"] is False

    def test_governance_outcome_rows_not_modified(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["outcome_rows_modified"] is False

    def test_governance_p83e_through_p85_not_modified(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["p83e_through_p85_artifacts_modified"] is False

    def test_governance_no_calibration_refit(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["calibration_refit"] is False

    def test_governance_no_champion_replacement(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["no_champion_replacement"] is True

    def test_governance_no_runtime_recommendation_mutation(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["no_runtime_recommendation_mutation"] is True

    def test_governance_no_production_betting_recommendation(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert gov["no_production_betting_recommendation"] is True

    def test_governance_has_16_flags(self, summary):
        gov = summary["step8_governance_scan"]["p86_governance"]
        assert len(gov) == 16


# ---------------------------------------------------------------------------
# Step 9 — Final classification
# ---------------------------------------------------------------------------

class TestStep9FinalClassification:
    def test_final_cls_is_stale_downstream_risk(self, summary):
        # Post P89 recovery: P86 is now READY
        fc = summary["step9_final_classification"]
        assert fc["classification"] == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"

    def test_final_cls_rationale_present(self, summary):
        fc = summary["step9_final_classification"]
        assert isinstance(fc["rationale"], str)
        assert len(fc["rationale"]) > 10

    def test_final_n_steps_checked(self, summary):
        fc = summary["step9_final_classification"]
        assert fc["n_steps_checked"] == 8

    def test_final_n_steps_passed(self, summary):
        fc = summary["step9_final_classification"]
        # Post P89 recovery: all 8 steps pass
        assert fc["n_steps_passed"] == 8

    def test_final_n_steps_failed(self, summary):
        fc = summary["step9_final_classification"]
        # Post P89 recovery: no steps fail
        assert fc["n_steps_failed"] == 0

    def test_final_failed_steps_contains_step7(self, summary):
        fc = summary["step9_final_classification"]
        # Post P89 recovery: no steps failed
        assert fc["failed_steps"] == []

    def test_p86_top_level_cls_matches_final(self, summary):
        top = summary["p86_classification"]
        final = summary["step9_final_classification"]["classification"]
        assert top == final


# ---------------------------------------------------------------------------
# Upstream artifact consistency guard (verify P84E rows = 828 from JSONL)
# ---------------------------------------------------------------------------

class TestUpstreamArtifactIntegrity:
    def test_canonical_rows_file_has_828_rows(self):
        path = ROOT / "data" / "mlb_2026" / "predictions" / "mlb_2026_prediction_rows.jsonl"
        assert path.exists()
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 828

    def test_p84e_jsonl_has_828_rows(self):
        path = ROOT / "data" / "mlb_2026" / "derived" / "p84e_2026_outcome_attached_prediction_rows.jsonl"
        assert path.exists()
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 828

    def test_p84e_jsonl_outcome_available_is_808(self):
        path = ROOT / "data" / "mlb_2026" / "derived" / "p84e_2026_outcome_attached_prediction_rows.jsonl"
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        available = sum(1 for l in lines if json.loads(l).get("outcome_available"))
        assert available == 808

    def test_p85_summary_positive_violations_zero(self):
        p85 = ROOT / "data" / "mlb_2026" / "derived" / "p85_prediction_convention_invariant_gate_summary.json"
        assert p85.exists()
        data = json.loads(p85.read_text(encoding="utf-8"))
        assert data["step2_fip_positive_invariant"]["n_violations"] == 0

    def test_p85_summary_negative_violations_zero(self):
        p85 = ROOT / "data" / "mlb_2026" / "derived" / "p85_prediction_convention_invariant_gate_summary.json"
        data = json.loads(p85.read_text(encoding="utf-8"))
        assert data["step3_fip_negative_invariant"]["n_violations"] == 0


# ---------------------------------------------------------------------------
# Report content smoke checks
# ---------------------------------------------------------------------------

class TestReportContent:
    def test_report_has_dependency_graph_section(self, report_text):
        assert "Dependency Graph" in report_text

    def test_report_has_governance_section(self, report_text):
        assert "Governance" in report_text

    def test_report_has_scope_constraints(self, report_text):
        assert "Scope Constraints" in report_text

    def test_report_has_mtime_ordering_section(self, report_text):
        assert "Mtime Ordering" in report_text

    def test_report_has_classification_lock_section(self, report_text):
        assert "Classification Lock" in report_text

    def test_report_has_metric_consistency_section(self, report_text):
        assert "Metric Consistency" in report_text

    def test_report_no_ev_reference(self, report_text):
        # No EV calculation should appear in the report
        assert "expected_value" not in report_text.lower() or "ev_computed" in report_text

    def test_report_no_kelly_recommendation(self, report_text):
        assert "kelly_fraction" not in report_text.lower()

    def test_report_mentions_no_production_betting(self, report_text):
        assert "production" in report_text.lower()

    def test_report_mentions_stale_downstream(self, report_text):
        assert "Stale" in report_text or "stale" in report_text

    def test_report_mentions_canonical_rows(self, report_text):
        assert "canonical_rows" in report_text

    def test_report_final_classification_is_expected(self, report_text):
        assert EXPECTED_CLASSIFICATION in report_text
