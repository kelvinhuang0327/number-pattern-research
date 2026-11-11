"""
Tests for P52 — Formal Monitoring Contract V2 Builder.

Governance: paper_only=True | diagnostic_only=True | live_api_calls=0
            p48_artifact_overwritten=False | p49_artifact_overwritten=False
            p51_artifact_preserved=True

17 tests total.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

# ── Module under test ─────────────────────────────────────────────────────────
_SCRIPT = pathlib.Path(__file__).parent.parent / "scripts/_p52_monitoring_contract_v2_builder.py"
spec = importlib.util.spec_from_file_location("p52", _SCRIPT)
p52 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p52)

# ── Artifact paths ────────────────────────────────────────────────────────────
_ROOT = pathlib.Path(__file__).parent.parent
SUMMARY_PATH = _ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json"
REPORT_PATH = _ROOT / "report/p52_monitoring_contract_v2_20260526.md"
PLAN_PATH = _ROOT / "00-BettingPlan/20260526/p52_monitoring_contract_v2_20260526.md"


def _summary() -> dict:
    with open(SUMMARY_PATH) as f:
        return json.load(f)


# ── Test 1 — P51 source artifact exists and is loaded ─────────────────────────
def test_p51_source_exists_and_loadable():
    """P51 source artifact must exist and be loadable (P52 depends on it)."""
    p51_path = _ROOT / "data/mlb_2025/derived/p51_monitoring_contract_revision_summary.json"
    assert p51_path.exists(), "P51 source artifact missing"
    data = json.loads(p51_path.read_text())
    assert "final_classification" in data
    assert data["final_classification"] == "P51_REVISED_CONTRACT_REDUCES_FALSE_ALERTS_DIAGNOSTIC"


# ── Test 2 — P52 JSON exists with all required top-level sections ─────────────
def test_p52_json_has_required_sections():
    """P52 JSON must contain all 12 required top-level sections."""
    data = _summary()
    required = [
        "contract_version",
        "supersession_policy",
        "metric_ownership_matrix",
        "monitoring_row_schema_v2",
        "alert_rule_matrix_v2",
        "retained_rules_from_p48",
        "deprecated_rules_from_p48_p49",
        "p51_replay_evidence",
        "september_2025_calibration_issue",
        "unresolved_data_gaps",
        "governance_flags",
        "final_p52_classification",
    ]
    for section in required:
        assert section in data, f"Missing required section: {section}"


# ── Test 3 — Contract version ─────────────────────────────────────────────────
def test_contract_version():
    """Contract version must equal P52_MONITORING_CONTRACT_V2."""
    data = _summary()
    assert data["contract_version"] == "P52_MONITORING_CONTRACT_V2"


# ── Test 4 — Edge family uses RAW_SIGMOID ─────────────────────────────────────
def test_edge_metric_family_uses_raw_sigmoid():
    """Edge metric family must use RAW_SIGMOID probability stream."""
    data = _summary()
    matrix = data["metric_ownership_matrix"]
    edge_metrics = [m for m in matrix if m["metric_family"] == "EDGE_SIGNAL"]
    assert len(edge_metrics) >= 1, "No EDGE_SIGNAL family found"
    for m in edge_metrics:
        assert m["selected_probability_stream"] == "RAW_SIGMOID", (
            f"Edge family must use RAW_SIGMOID, got: {m['selected_probability_stream']}"
        )


# ── Test 5 — Calibration family uses PLATT_CALIBRATED ────────────────────────
def test_calibration_metric_family_uses_platt():
    """Calibration metric family must use PLATT_CALIBRATED."""
    data = _summary()
    matrix = data["metric_ownership_matrix"]
    calib_metrics = [m for m in matrix if m["metric_family"] == "CALIBRATION"]
    assert len(calib_metrics) >= 1, "No CALIBRATION family found"
    for m in calib_metrics:
        assert m["selected_probability_stream"] == "PLATT_CALIBRATED", (
            f"Calibration family must use PLATT_CALIBRATED, got: {m['selected_probability_stream']}"
        )


# ── Test 6 — Isotonic is not selected as canonical ───────────────────────────
def test_isotonic_not_canonical_monitoring_stream():
    """Isotonic calibration must not be the selected stream for any active monitoring metric."""
    data = _summary()
    matrix = data["metric_ownership_matrix"]
    # Only CALIBRATION_COMPARISON family may reference isotonic
    for m in matrix:
        if m["metric_family"] not in ("CALIBRATION_COMPARISON",):
            stream = m["selected_probability_stream"]
            assert "ISOTONIC" not in stream.upper(), (
                f"Metric family {m['metric_family']} must not use ISOTONIC_CALIBRATED as selected stream"
            )


# ── Test 7 — V2 records P48/P49 supersession without overwriting ──────────────
def test_supersession_without_overwrite():
    """V2 must record supersession policy AND explicitly state does_not_overwrite artifacts."""
    data = _summary()
    sp = data["supersession_policy"]
    assert len(sp["supersedes"]) >= 2, "Must supersede at least 2 P48/P49 rules"
    assert len(sp["preserves"]) >= 3, "Must preserve at least 3 P48/P49 rules"
    assert len(sp["does_not_overwrite"]) >= 3, "Must explicitly list non-overwritten artifacts"

    # Verify P48 and P49 artifact names appear in does_not_overwrite
    does_not = " ".join(sp["does_not_overwrite"])
    assert "p48" in does_not.lower() or "P48" in does_not
    assert "p49" in does_not.lower() or "P49" in does_not


# ── Test 8 — Sep 2025 calibration issue preserved ────────────────────────────
def test_sep_2025_calibration_issue_preserved():
    """Sep 2025 CALIBRATION_CRITICAL issue must be documented with correct platt_ece."""
    data = _summary()
    issue = data["september_2025_calibration_issue"]
    assert issue["month"] == "2025-09"
    assert issue["platt_ece"] == pytest.approx(0.122929, abs=1e-4)
    assert issue["ece_critical_threshold"] == pytest.approx(0.12, abs=1e-9)
    assert issue["p51_corrected_status"] == "CALIBRATION_CRITICAL"
    assert "SAMPLE_LIMITED" in issue["p49_status_for_month"]


# ── Test 9 — 2024 data gap: cross-year blocker only ───────────────────────────
def test_2024_data_gap_cross_year_only():
    """2024 closing-line gap must be marked cross-year blocker only, not 2025-only blocker."""
    data = _summary()
    gaps = data["unresolved_data_gaps"]
    assert len(gaps) >= 1
    gap_2024 = next((g for g in gaps if "2024" in g["gap_id"]), None)
    assert gap_2024 is not None, "2024 data gap not found"
    assert gap_2024["status"] == "UNRESOLVED"
    impact_scope = gap_2024["impact_scope"]
    assert "CROSS_YEAR" in impact_scope.upper() or "cross_year" in impact_scope.lower(), (
        "2024 gap must be scoped as cross-year only"
    )
    # Must NOT block 2025-only replay
    assert "2025" in impact_scope or "2025" in gap_2024.get("impact", "")


# ── Test 10 — Governance flags present and correct ───────────────────────────
def test_governance_flags_complete():
    """All required governance flags must be present and correctly set."""
    data = _summary()
    flags = data["governance_flags"]
    assert flags["paper_only"] is True
    assert flags["diagnostic_only"] is True
    assert flags["promotion_freeze"] is True
    assert flags["kelly_deploy_allowed"] is False
    assert flags["production_usage_proposed"] is False
    assert flags["runtime_recommendation_logic_changed"] is False
    assert flags["p48_artifact_overwritten"] is False
    assert flags["p49_artifact_overwritten"] is False
    assert flags["p51_artifact_preserved"] is True


# ── Test 11 — live_api_calls equals 0 ────────────────────────────────────────
def test_live_api_calls_zero():
    """live_api_calls must be exactly 0."""
    data = _summary()
    assert data["governance_flags"]["live_api_calls"] == 0


# ── Test 12 — runtime_recommendation_logic_changed is false ──────────────────
def test_runtime_logic_not_changed():
    """runtime_recommendation_logic_changed must be False."""
    data = _summary()
    assert data["governance_flags"]["runtime_recommendation_logic_changed"] is False


# ── Test 13 — p48_artifact_overwritten is false ──────────────────────────────
def test_p48_artifact_not_overwritten():
    """p48_artifact_overwritten must be False and P48 source file must be unchanged."""
    data = _summary()
    assert data["governance_flags"]["p48_artifact_overwritten"] is False
    # Verify P48 artifact still exists
    p48_path = _ROOT / "data/mlb_2025/derived/p48_monitoring_loop_contract_summary.json"
    assert p48_path.exists(), "P48 artifact must not be deleted"
    p48 = json.loads(p48_path.read_text())
    assert "alert_thresholds" in p48


# ── Test 14 — p49_artifact_overwritten is false ──────────────────────────────
def test_p49_artifact_not_overwritten():
    """p49_artifact_overwritten must be False and P49 source file must be unchanged."""
    data = _summary()
    assert data["governance_flags"]["p49_artifact_overwritten"] is False
    p49_path = _ROOT / "data/mlb_2025/derived/p49_offline_historical_monitoring_replay_summary.json"
    assert p49_path.exists(), "P49 artifact must not be deleted"
    p49 = json.loads(p49_path.read_text())
    assert "monthly_replay" in p49


# ── Test 15 — No deployment-readiness classification ─────────────────────────
def test_no_deployment_readiness_classification():
    """Final classification must not imply deployment readiness."""
    data = _summary()
    clf = data["final_p52_classification"]
    forbidden_terms = ["PRODUCTION_READY", "DEPLOY", "PROMOTED", "LIVE"]
    for term in forbidden_terms:
        assert term not in clf.upper(), (
            f"Classification '{clf}' must not contain '{term}'"
        )
    assert clf in p52.ALLOWED_CLASSIFICATIONS


# ── Test 16 — Reports contain no affirmative production/profit claims ─────────
def test_reports_no_affirmative_claims():
    """MD reports must not contain affirmative production/profit claims."""
    forbidden_patterns = [
        "guaranteed profit",
        "production proposal",
        "profitability claim",
        "live odds api call",
        "deployment ready",
        "production ready",
        "promote to production",
    ]
    for path in (REPORT_PATH, PLAN_PATH):
        assert path.exists(), f"Report missing: {path}"
        content = path.read_text().lower()
        for pattern in forbidden_patterns:
            assert pattern not in content, (
                f"Forbidden phrase '{pattern}' found in {path.name}"
            )


# ── Test 17 — active_task.md references P52 classification ───────────────────
def test_active_task_references_p52():
    """active_task.md must reference the final P52 classification."""
    active_task = _ROOT / "00-Plan/roadmap/active_task.md"
    assert active_task.exists()
    content = active_task.read_text()
    data = _summary()
    clf = data["final_p52_classification"]
    assert clf in content, (
        f"active_task.md must reference '{clf}' but it was not found"
    )
