"""
Tests for P56 — Sample-Sensitive Band Annotation Policy for Monitoring Contract V2.

17 tests:
T01  P55 source artifact exists and is loaded
T02  P56 JSON exists and contains all required top-level sections
T03  Sample size tiers include insufficient/watchlist/monitorable
T04  n=27 maps to BAND_SAMPLE_INSUFFICIENT
T05  P55 Sep mid-band maps to SAMPLE_SENSITIVE_BAND_ANOMALY
T06  Action is TRACK_ONLY_NO_REFIT
T07  Future evidence requirements include n>=30 and/or cumulative n>=100
T08  P52 compatibility statement exists with required content
T09  Governance flags exist and match required values
T10  live_api_calls == 0
T11  runtime_recommendation_logic_changed == False
T12  platt_constants_modified == False
T13  p52_thresholds_changed == False
T14  p52/p53/p54/p55 overwrite flags are False
T15  JSON output contains no deployment-readiness classification
T16  Reports contain no affirmative production or profit claims
T17  active_task.md references final P56 classification
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

P55_JSON = ROOT / "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json"
P56_JSON = ROOT / "data/mlb_2025/derived/p56_sample_sensitive_band_annotation_policy_summary.json"
REPORT_MD = ROOT / "report/p56_sample_sensitive_band_annotation_policy_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p56_sample_sensitive_band_annotation_policy_20260526.md"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"

REQUIRED_TOP_LEVEL_KEYS = {
    "p56_phase",
    "run_date",
    "source_artifacts",
    "p55_recap",
    "band_annotation_policy",
    "sample_size_tiers",
    "interpretation_rules",
    "p55_application",
    "p52_v2_compatibility",
    "data_gap_status",
    "final_p56_classification",
    "governance_flags",
}

FORBIDDEN_CLASSIFICATIONS = [
    "DEPLOYMENT_READY",
    "PRODUCTION_READY",
    "CHAMPION_PROMOTED",
    "KELLY_LIVE",
    "LIVE_BETTING_APPROVED",
]

FORBIDDEN_REPORT_PHRASES = [
    "guaranteed profit",
    "expected profit",
    "will profit",
    "deploy to production",
    "ready for live betting",
    "champion strategy activated",
    "kelly_deploy_allowed=True",
]


@pytest.fixture(scope="module")
def summary() -> dict:
    assert P56_JSON.exists(), f"P56 JSON not found: {P56_JSON}"
    return json.loads(P56_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T01 — P55 source artifact exists and is loaded
# ---------------------------------------------------------------------------
def test_t01_p55_source_artifact_loaded(summary: dict) -> None:
    """P55 JSON must exist and be referenced in the P56 summary."""
    assert P55_JSON.exists(), f"P55 JSON not found: {P55_JSON}"

    recap = summary.get("p55_recap", {})
    assert recap, "p56 summary must include p55_recap section"

    # Verify P55 key values are captured correctly
    assert recap.get("final_p55_classification") == "P55_INCONCLUSIVE_SAMPLE_LIMITED"
    assert recap.get("tier_c_n") == 535
    assert recap.get("sep_mid_band_n") == 27

    # Source artifacts section must reference P55
    sources = summary.get("source_artifacts", {})
    assert "p55" in sources, "source_artifacts must include p55 key"


# ---------------------------------------------------------------------------
# T02 — P56 JSON exists and contains all required top-level sections
# ---------------------------------------------------------------------------
def test_t02_required_sections(summary: dict) -> None:
    """P56 JSON must contain all required top-level sections."""
    missing = REQUIRED_TOP_LEVEL_KEYS - set(summary.keys())
    assert not missing, f"P56 JSON missing top-level keys: {missing}"


# ---------------------------------------------------------------------------
# T03 — Sample size tiers include insufficient/watchlist/monitorable
# ---------------------------------------------------------------------------
def test_t03_sample_size_tiers(summary: dict) -> None:
    """Sample size tiers must define all three required tiers."""
    tiers = summary.get("sample_size_tiers", {})
    assert tiers, "sample_size_tiers is missing or empty"

    required = {
        "BAND_SAMPLE_INSUFFICIENT",
        "BAND_SAMPLE_WATCHLIST",
        "BAND_SAMPLE_MONITORABLE",
    }
    missing = required - set(tiers.keys())
    assert not missing, f"sample_size_tiers missing: {missing}"

    # Each tier must have at minimum: condition, label, description, allowed_actions
    for tier_name in required:
        tier = tiers[tier_name]
        assert "condition" in tier, f"Tier {tier_name} missing 'condition'"
        assert "label" in tier, f"Tier {tier_name} missing 'label'"
        assert "allowed_actions" in tier, f"Tier {tier_name} missing 'allowed_actions'"


# ---------------------------------------------------------------------------
# T04 — n=27 maps to BAND_SAMPLE_INSUFFICIENT
# ---------------------------------------------------------------------------
def test_t04_n27_maps_to_insufficient(summary: dict) -> None:
    """P55 Sep mid-band (n=27) must map to BAND_SAMPLE_INSUFFICIENT."""
    app = summary.get("p55_application", {})
    assert app.get("n") == 27, f"p55_application.n expected 27, got {app.get('n')}"
    assert app.get("sample_tier") == "BAND_SAMPLE_INSUFFICIENT", (
        f"n=27 must map to BAND_SAMPLE_INSUFFICIENT, got {app.get('sample_tier')}"
    )


# ---------------------------------------------------------------------------
# T05 — P55 Sep mid-band maps to SAMPLE_SENSITIVE_BAND_ANOMALY
# ---------------------------------------------------------------------------
def test_t05_annotation_sample_sensitive(summary: dict) -> None:
    """P55 Sep mid-band must be annotated as SAMPLE_SENSITIVE_BAND_ANOMALY."""
    app = summary.get("p55_application", {})
    assert app.get("annotation") == "SAMPLE_SENSITIVE_BAND_ANOMALY", (
        f"Expected SAMPLE_SENSITIVE_BAND_ANOMALY, got {app.get('annotation')}"
    )

    # Band and month must be recorded
    assert app.get("band") == "1.00_1.25", f"Band mismatch: {app.get('band')}"
    assert "Sep" in str(app.get("month", "")), f"Month should reference Sep: {app.get('month')}"


# ---------------------------------------------------------------------------
# T06 — Action is TRACK_ONLY_NO_REFIT
# ---------------------------------------------------------------------------
def test_t06_action_track_only(summary: dict) -> None:
    """Action for Sep mid-band must be TRACK_ONLY_NO_REFIT."""
    app = summary.get("p55_application", {})
    assert app.get("action") == "TRACK_ONLY_NO_REFIT", (
        f"Expected TRACK_ONLY_NO_REFIT, got {app.get('action')}"
    )

    # Confirm BAND_SAMPLE_INSUFFICIENT tier allows only TRACK_ONLY_NO_REFIT
    tiers = summary.get("sample_size_tiers", {})
    insuf = tiers.get("BAND_SAMPLE_INSUFFICIENT", {})
    allowed = insuf.get("allowed_actions", [])
    assert "TRACK_ONLY_NO_REFIT" in allowed, (
        "BAND_SAMPLE_INSUFFICIENT tier must allow TRACK_ONLY_NO_REFIT"
    )
    # Must NOT allow TRIGGER_REFIT
    disallowed = insuf.get("disallowed_actions", [])
    assert "TRIGGER_REFIT" in disallowed, (
        "BAND_SAMPLE_INSUFFICIENT tier must explicitly disallow TRIGGER_REFIT"
    )


# ---------------------------------------------------------------------------
# T07 — Future evidence requirements include n>=30 and/or cumulative n>=100
# ---------------------------------------------------------------------------
def test_t07_future_evidence_requirements(summary: dict) -> None:
    """Future evidence requirements must include n>=30 and/or cumulative n>=100."""
    app = summary.get("p55_application", {})
    fe = app.get("required_future_evidence", {})
    assert fe, "required_future_evidence section is missing"

    criteria = fe.get("criteria", [])
    assert len(criteria) >= 2, f"Expected at least 2 future evidence criteria, got {len(criteria)}"

    # Check that n>=30 is mentioned somewhere in criteria
    all_text = " ".join(c.get("description", "") for c in criteria).lower()
    assert "n >= 30" in all_text or "n>=30" in all_text or "n ≥ 30" in all_text, (
        "Future evidence must reference n>=30 criterion"
    )

    # Check that n>=100 or cumulative n>=100 is mentioned
    assert "100" in all_text, (
        "Future evidence must reference cumulative n>=100 criterion"
    )

    # Refit trigger condition must be documented
    assert fe.get("refit_trigger_conditions"), "refit_trigger_conditions must be documented"
    trigger = fe["refit_trigger_conditions"].lower()
    assert "refit" in trigger, "refit_trigger_conditions must reference 'refit'"

    # Current status must say no refit warranted
    current = fe.get("current_status", "").lower()
    assert "not yet met" in current or "no refit" in current or "27" in current, (
        "current_status must reflect that evidence is not yet met for n=27"
    )


# ---------------------------------------------------------------------------
# T08 — P52 compatibility statement exists
# ---------------------------------------------------------------------------
def test_t08_p52_compatibility(summary: dict) -> None:
    """P52 V2 compatibility statement must exist and contain required content."""
    compat = summary.get("p52_v2_compatibility", {})
    assert compat, "p52_v2_compatibility section is missing"

    # Statement must say P56 does not supersede P52
    stmt = compat.get("statement", "")
    assert "not supersede" in stmt.lower() or "does not supersede" in stmt.lower(), (
        f"Compatibility statement must say P56 does not supersede P52: {stmt}"
    )

    # Must have details list
    details = compat.get("details", [])
    assert len(details) >= 5, f"Compatibility details must have >= 5 items, got {len(details)}"

    # Status fields
    assert compat.get("p52_threshold_status") == "UNCHANGED", (
        f"p52_threshold_status must be UNCHANGED, got {compat.get('p52_threshold_status')}"
    )
    assert compat.get("p52_artifact_status") == "PRESERVED"
    assert compat.get("p53_artifact_status") == "PRESERVED"
    assert compat.get("p54_artifact_status") == "PRESERVED"
    assert compat.get("p55_artifact_status") == "PRESERVED"

    # Platt constants mentioned
    platt_status = compat.get("platt_constants_status", "")
    assert "UNCHANGED" in platt_status or "unchanged" in platt_status.lower(), (
        f"platt_constants_status must indicate UNCHANGED: {platt_status}"
    )


# ---------------------------------------------------------------------------
# T09 — Governance flags exist and match required values
# ---------------------------------------------------------------------------
def test_t09_governance_flags(summary: dict) -> None:
    """All governance flags must be present and correct."""
    gov = summary.get("governance_flags", {})
    required = {
        "paper_only": True,
        "diagnostic_only": True,
        "promotion_freeze": True,
        "kelly_deploy_allowed": False,
        "live_api_calls": 0,
        "tsl_crawler_modified": False,
        "champion_strategy_changed": False,
        "production_usage_proposed": False,
        "runtime_recommendation_logic_changed": False,
        "platt_constants_modified": False,
        "p52_contract_overwritten": False,
        "p53_artifact_overwritten": False,
        "p54_artifact_overwritten": False,
        "p55_artifact_overwritten": False,
        "p52_thresholds_changed": False,
    }
    for key, expected in required.items():
        assert key in gov, f"governance_flags missing key: {key}"
        assert gov[key] == expected, (
            f"governance_flags.{key} expected {expected}, got {gov[key]}"
        )


# ---------------------------------------------------------------------------
# T10 — live_api_calls == 0
# ---------------------------------------------------------------------------
def test_t10_live_api_calls_zero(summary: dict) -> None:
    """live_api_calls must be exactly 0."""
    gov = summary.get("governance_flags", {})
    assert gov.get("live_api_calls") == 0, (
        f"live_api_calls must be 0, got {gov.get('live_api_calls')}"
    )


# ---------------------------------------------------------------------------
# T11 — runtime_recommendation_logic_changed == False
# ---------------------------------------------------------------------------
def test_t11_runtime_logic_unchanged(summary: dict) -> None:
    """runtime_recommendation_logic_changed must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("runtime_recommendation_logic_changed") is False


# ---------------------------------------------------------------------------
# T12 — platt_constants_modified == False
# ---------------------------------------------------------------------------
def test_t12_platt_constants_not_modified(summary: dict) -> None:
    """platt_constants_modified must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("platt_constants_modified") is False


# ---------------------------------------------------------------------------
# T13 — p52_thresholds_changed == False
# ---------------------------------------------------------------------------
def test_t13_p52_thresholds_unchanged(summary: dict) -> None:
    """p52_thresholds_changed must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("p52_thresholds_changed") is False, (
        f"p52_thresholds_changed must be False, got {gov.get('p52_thresholds_changed')}"
    )


# ---------------------------------------------------------------------------
# T14 — p52/p53/p54/p55 overwrite flags are False
# ---------------------------------------------------------------------------
def test_t14_no_artifact_overwrite(summary: dict) -> None:
    """No prior artifact must be overwritten."""
    gov = summary.get("governance_flags", {})
    for flag in ["p52_contract_overwritten", "p53_artifact_overwritten",
                 "p54_artifact_overwritten", "p55_artifact_overwritten"]:
        assert gov.get(flag) is False, f"{flag} must be False, got {gov.get(flag)}"

    # Verify the actual files still exist and are unmodified (readable)
    from datetime import datetime
    for json_path in [
        ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json",
        ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json",
        ROOT / "data/mlb_2025/derived/p54_sep_sp_fip_delta_feature_drift_audit_summary.json",
        ROOT / "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json",
    ]:
        assert json_path.exists(), f"Artifact was deleted or moved: {json_path.name}"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data, f"Artifact appears empty: {json_path.name}"


# ---------------------------------------------------------------------------
# T15 — JSON contains no deployment-readiness classification
# ---------------------------------------------------------------------------
def test_t15_no_deployment_classification(summary: dict) -> None:
    """Final P56 classification must not imply deployment readiness."""
    clf = summary.get("final_p56_classification", "")
    for forbidden in FORBIDDEN_CLASSIFICATIONS:
        assert forbidden not in clf, (
            f"Forbidden classification fragment '{forbidden}' found in '{clf}'"
        )
    # Classification must be one of the allowed P56 values
    allowed = {
        "P56_BAND_ANNOTATION_POLICY_READY_DIAGNOSTIC",
        "P56_BAND_ANNOTATION_POLICY_INCOMPLETE",
        "P56_BLOCKED_BY_SOURCE_MISSING",
    }
    assert clf in allowed, (
        f"Final classification '{clf}' is not in the allowed set: {allowed}"
    )


# ---------------------------------------------------------------------------
# T16 — Reports contain no affirmative production or profit claims
# ---------------------------------------------------------------------------
def test_t16_reports_no_production_claims() -> None:
    """Reports must not contain affirmative production or profit claims."""
    for report_path in [REPORT_MD, BETTING_PLAN_MD]:
        assert report_path.exists(), f"Report not found: {report_path}"
        text = report_path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_REPORT_PHRASES:
            assert phrase.lower() not in text, (
                f"Forbidden phrase '{phrase}' found in {report_path.name}"
            )


# ---------------------------------------------------------------------------
# T17 — active_task.md references final P56 classification
# ---------------------------------------------------------------------------
def test_t17_active_task_references_p56(summary: dict) -> None:
    """active_task.md must reference the final P56 classification."""
    assert ACTIVE_TASK_MD.exists(), f"active_task.md not found: {ACTIVE_TASK_MD}"
    content = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    clf = summary.get("final_p56_classification", "")
    assert clf in content, (
        f"active_task.md must reference '{clf}' but it was not found"
    )
    assert "P56" in content, "active_task.md must reference P56"
    # Verify P55 classification is still present (prepend pattern preserved history)
    assert "P55_INCONCLUSIVE_SAMPLE_LIMITED" in content, (
        "active_task.md must still reference P55 classification (history preserved)"
    )
