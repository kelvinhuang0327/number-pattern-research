"""
Tests for P58 — Monitoring Contract V2 Monthly Report Template.

21 tests:
T01  P57 source artifact exists and is loaded
T02  P58 JSON exists and contains all required top-level sections
T03  template_version equals P58_MONITORING_CONTRACT_V2_MONTHLY_REPORT_TEMPLATE_V1
T04  global_status section schema contains required fields
T05  band_annotations section schema contains P57 BandAnnotationRecord fields
T06  Sep 2025 example report exists
T07  Sep mid-band n=27 maps to BAND_SAMPLE_INSUFFICIENT
T08  Sep mid-band action remains TRACK_ONLY_NO_REFIT
T09  should_change_global_status equals False
T10  should_trigger_refit equals False
T11  should_change_thresholds equals False
T12  Global status is not derived from band annotation
T13  P52 thresholds changed flag equals False
T14  Platt constants modified flag equals False
T15  P52/P53/P54/P55/P56/P57 overwrite flags are False
T16  Governance flags exist and match required values
T17  live_api_calls equals 0
T18  runtime_recommendation_logic_changed equals False
T19  JSON output contains no deployment-readiness classification
T20  Reports contain no affirmative production or profit claims
T21  active_task.md references final P58 classification
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

P57_JSON = ROOT / "data/mlb_2025/derived/p57_monitoring_contract_v2_annotation_integration_summary.json"
P58_JSON = ROOT / "data/mlb_2025/derived/p58_monitoring_contract_v2_monthly_report_template_summary.json"
REPORT_MD = ROOT / "report/p58_monitoring_contract_v2_monthly_report_template_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p58_monitoring_contract_v2_monthly_report_template_20260526.md"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"

REQUIRED_TOP_LEVEL_KEYS = {
    "p58_phase",
    "run_date",
    "source_artifacts",
    "template_version",
    "monthly_report_schema",
    "global_status_section_schema",
    "band_annotations_section_schema",
    "sep_2025_example_report",
    "validation_rules",
    "invariants",
    "future_agent_usage_notes",
    "governance_flags",
    "final_p58_classification",
}

REQUIRED_GLOBAL_STATUS_FIELDS = {
    "report_month",
    "batch_n",
    "global_status",
    "global_alert_level",
    "global_alert_reasons",
    "edge_status",
    "calibration_status",
    "sample_status",
    "data_gap_status",
    "raw_edge_mean",
    "raw_edge_ci_low",
    "raw_edge_ci_high",
    "platt_ece",
    "platt_brier",
    "p52_thresholds_used",
    "source_trace",
}

REQUIRED_BAND_ANNOTATION_FIELDS = {
    "annotation_scope",
    "metric_family",
    "band_label",
    "band_n",
    "sample_tier",
    "annotation",
    "action",
    "evidence_strength",
    "platt_ece",
    "raw_ece",
    "ece_delta",
    "repeated_month_count",
    "cumulative_band_n",
    "future_evidence_required",
    "should_change_global_status",
    "should_trigger_refit",
    "should_change_thresholds",
    "carry_forward_status",
    "source_trace",
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
    assert P58_JSON.exists(), f"P58 JSON not found: {P58_JSON}"
    return json.loads(P58_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T01 — P57 source artifact exists and is loaded
# ---------------------------------------------------------------------------
def test_t01_p57_source_artifact_loaded(summary: dict) -> None:
    """P57 JSON must exist and be referenced in the P58 summary."""
    assert P57_JSON.exists(), f"P57 JSON not found: {P57_JSON}"

    sources = summary.get("source_artifacts", {})
    assert "p57" in sources, "source_artifacts must include p57 key"
    assert "p52" in sources, "source_artifacts must include p52 key"

    # P57 classification must be reflected in the example report carry-forward
    cf = (
        summary
        .get("sep_2025_example_report", {})
        .get("band_annotations", {})
        .get("records", [{}])[0]
    )
    trace = cf.get("source_trace", {})
    assert "p57" in trace.get("p57_reference", "").lower(), (
        "source_trace must reference p57 artifact"
    )


# ---------------------------------------------------------------------------
# T02 — P58 JSON exists and contains all required top-level sections
# ---------------------------------------------------------------------------
def test_t02_required_sections(summary: dict) -> None:
    """P58 JSON must contain all required top-level keys."""
    missing = REQUIRED_TOP_LEVEL_KEYS - set(summary.keys())
    assert not missing, f"P58 JSON missing top-level keys: {missing}"


# ---------------------------------------------------------------------------
# T03 — template_version
# ---------------------------------------------------------------------------
def test_t03_template_version(summary: dict) -> None:
    """template_version must equal the expected constant."""
    expected = "P58_MONITORING_CONTRACT_V2_MONTHLY_REPORT_TEMPLATE_V1"
    assert summary.get("template_version") == expected, (
        f"Expected template_version={expected}, got {summary.get('template_version')}"
    )
    # Also verify monthly_report_schema carries the version
    schema = summary.get("monthly_report_schema", {})
    assert schema.get("template_version") == expected


# ---------------------------------------------------------------------------
# T04 — global_status section schema contains required fields
# ---------------------------------------------------------------------------
def test_t04_global_status_schema_fields(summary: dict) -> None:
    """global_status_section_schema must define all required fields."""
    gs = summary.get("global_status_section_schema", {})
    assert gs, "global_status_section_schema is missing"

    fields = gs.get("required_fields", {})
    missing = REQUIRED_GLOBAL_STATUS_FIELDS - set(fields.keys())
    assert not missing, f"global_status schema missing fields: {missing}"

    # Each field must have type and description
    for name in REQUIRED_GLOBAL_STATUS_FIELDS:
        field_def = fields[name]
        assert "type" in field_def, f"global_status field '{name}' missing 'type'"
        assert "description" in field_def, f"global_status field '{name}' missing 'description'"

    # Must have rules
    rules = gs.get("rules", [])
    assert len(rules) >= 4, f"global_status schema must have >= 4 rules, got {len(rules)}"

    # Critical rule: global_status not modified by band annotations
    rules_text = " ".join(rules).lower()
    assert "band annotation" in rules_text or "band" in rules_text, (
        "global_status rules must mention band annotations"
    )
    assert "threshold" in rules_text, "global_status rules must mention thresholds"

    # sample_status must be separate field
    assert "sample_status" in fields, "global_status schema must include sample_status as separate field"
    assert "data_gap_status" in fields, "global_status schema must include data_gap_status"
    data_gap_desc = fields["data_gap_status"].get("description", "")
    assert "2024" in data_gap_desc or "cross-year" in data_gap_desc.lower(), (
        "data_gap_status description must mention 2024 cross-year limitation"
    )


# ---------------------------------------------------------------------------
# T05 — band_annotations section schema contains P57 BandAnnotationRecord fields
# ---------------------------------------------------------------------------
def test_t05_band_annotations_schema_fields(summary: dict) -> None:
    """band_annotations_section_schema must require all P57 BandAnnotationRecord fields."""
    ba = summary.get("band_annotations_section_schema", {})
    assert ba, "band_annotations_section_schema is missing"

    fields = set(ba.get("required_fields_per_record", []))
    missing = REQUIRED_BAND_ANNOTATION_FIELDS - fields
    assert not missing, f"band_annotations schema missing required fields: {missing}"

    # Section rules must be defined
    rules = ba.get("section_rules", [])
    assert len(rules) >= 5, f"band_annotations schema must have >= 5 section rules, got {len(rules)}"

    # Must include the required header statement rule
    rules_text = " ".join(rules).lower()
    assert "band annotations do not change global" in rules_text, (
        "A section rule must require the 'Band annotations do not change global P52 status.' header"
    )

    # n < 30 must map to BAND_SAMPLE_INSUFFICIENT
    tier_mapping = ba.get("sample_tier_mapping", {})
    assert tier_mapping.get("n_lt_30") == "BAND_SAMPLE_INSUFFICIENT", (
        "n_lt_30 must map to BAND_SAMPLE_INSUFFICIENT"
    )


# ---------------------------------------------------------------------------
# T06 — Sep 2025 example report exists
# ---------------------------------------------------------------------------
def test_t06_sep_2025_example_exists(summary: dict) -> None:
    """Sep 2025 example report must exist with required structure."""
    ex = summary.get("sep_2025_example_report", {})
    assert ex, "sep_2025_example_report is missing"
    assert ex.get("example_type") == "HISTORICAL_DIAGNOSTIC_EXAMPLE"
    assert ex.get("report_month") == "2025-09"

    # Must include the required diagnostic note
    note = ex.get("example_note", "")
    assert "diagnostic" in note.lower(), (
        "example_note must state this is diagnostic only"
    )
    assert "runtime" in note.lower() or "behavior" in note.lower(), (
        "example_note must state it does not modify runtime behavior"
    )

    # Both global_status and band_annotations must be present
    assert "global_status" in ex, "Sep example must include global_status section"
    assert "band_annotations" in ex, "Sep example must include band_annotations section"

    # band_annotations header
    ba_section = ex["band_annotations"]
    assert "Band annotations do not change global P52 status." in ba_section.get("section_header", ""), (
        "band_annotations section_header must contain required statement"
    )

    # Must have at least one record
    records = ba_section.get("records", [])
    assert len(records) >= 1, "Sep example must include at least one BandAnnotationRecord"


# ---------------------------------------------------------------------------
# T07 — n=27 maps to BAND_SAMPLE_INSUFFICIENT
# ---------------------------------------------------------------------------
def test_t07_n27_band_sample_insufficient(summary: dict) -> None:
    """Sep 2025 mid-band n=27 must be BAND_SAMPLE_INSUFFICIENT."""
    cf = (
        summary
        .get("sep_2025_example_report", {})
        .get("band_annotations", {})
        .get("records", [{}])[0]
    )
    assert cf.get("band_n") == 27, f"band_n expected 27, got {cf.get('band_n')}"
    assert cf.get("sample_tier") == "BAND_SAMPLE_INSUFFICIENT", (
        f"Expected BAND_SAMPLE_INSUFFICIENT, got {cf.get('sample_tier')}"
    )
    assert cf.get("cumulative_band_n") == 27


# ---------------------------------------------------------------------------
# T08 — Action remains TRACK_ONLY_NO_REFIT
# ---------------------------------------------------------------------------
def test_t08_action_track_only_no_refit(summary: dict) -> None:
    """Sep 2025 mid-band action must remain TRACK_ONLY_NO_REFIT."""
    cf = (
        summary
        .get("sep_2025_example_report", {})
        .get("band_annotations", {})
        .get("records", [{}])[0]
    )
    assert cf.get("action") == "TRACK_ONLY_NO_REFIT", (
        f"Expected TRACK_ONLY_NO_REFIT, got {cf.get('action')}"
    )
    assert cf.get("annotation") == "SAMPLE_SENSITIVE_BAND_ANOMALY"
    assert cf.get("carry_forward_status") == "ACTIVE_TRACK_ONLY"

    # Verify ECE values match P56/P57 findings
    assert abs(cf.get("platt_ece", 0) - 0.245988) < 1e-4, (
        f"platt_ece expected 0.245988, got {cf.get('platt_ece')}"
    )
    assert abs(cf.get("raw_ece", 0) - 0.165456) < 1e-4, (
        f"raw_ece expected 0.165456, got {cf.get('raw_ece')}"
    )
    assert abs(cf.get("ece_delta", 0) - 0.080532) < 1e-4, (
        f"ece_delta expected 0.080532, got {cf.get('ece_delta')}"
    )


# ---------------------------------------------------------------------------
# T09 — should_change_global_status equals False
# ---------------------------------------------------------------------------
def test_t09_no_global_status_change(summary: dict) -> None:
    """should_change_global_status must be False for Sep 2025 mid-band."""
    cf = (
        summary
        .get("sep_2025_example_report", {})
        .get("band_annotations", {})
        .get("records", [{}])[0]
    )
    assert cf.get("should_change_global_status") is False, (
        f"should_change_global_status must be False, got {cf.get('should_change_global_status')}"
    )

    # Validation rule VAL02 must enforce this
    val_rules = summary.get("validation_rules", {}).get("rules", [])
    val02 = next((r for r in val_rules if r.get("rule_id") == "VAL02"), None)
    assert val02 is not None, "VAL02 must exist"
    assert "should_change_global_status" in val02.get("rule", "").lower(), (
        "VAL02 must mention should_change_global_status"
    )


# ---------------------------------------------------------------------------
# T10 — should_trigger_refit equals False
# ---------------------------------------------------------------------------
def test_t10_no_trigger_refit(summary: dict) -> None:
    """should_trigger_refit must be False for the Sep 2025 mid-band record."""
    cf = (
        summary
        .get("sep_2025_example_report", {})
        .get("band_annotations", {})
        .get("records", [{}])[0]
    )
    assert cf.get("should_trigger_refit") is False, (
        f"should_trigger_refit must be False, got {cf.get('should_trigger_refit')}"
    )

    # Validation rule VAL03 must enforce this for n < 30
    val_rules = summary.get("validation_rules", {}).get("rules", [])
    val03 = next((r for r in val_rules if r.get("rule_id") == "VAL03"), None)
    assert val03 is not None, "VAL03 must exist"
    rule_text = val03.get("rule", "").lower()
    assert "refit" in rule_text and ("30" in rule_text or "n < 30" in rule_text), (
        "VAL03 must mention should_trigger_refit and n < 30"
    )


# ---------------------------------------------------------------------------
# T11 — should_change_thresholds equals False
# ---------------------------------------------------------------------------
def test_t11_no_threshold_change(summary: dict) -> None:
    """should_change_thresholds must be False for the Sep 2025 mid-band record."""
    cf = (
        summary
        .get("sep_2025_example_report", {})
        .get("band_annotations", {})
        .get("records", [{}])[0]
    )
    assert cf.get("should_change_thresholds") is False, (
        f"should_change_thresholds must be False, got {cf.get('should_change_thresholds')}"
    )

    # Validation rule VAL04 must enforce this
    val_rules = summary.get("validation_rules", {}).get("rules", [])
    val04 = next((r for r in val_rules if r.get("rule_id") == "VAL04"), None)
    assert val04 is not None, "VAL04 must exist"
    rule_text = val04.get("rule", "").lower()
    assert "should_change_thresholds" in rule_text, (
        "VAL04 must mention should_change_thresholds"
    )


# ---------------------------------------------------------------------------
# T12 — Global status is not derived from band annotation
# ---------------------------------------------------------------------------
def test_t12_global_status_independent_of_band_annotations(summary: dict) -> None:
    """Global status in example must not be influenced by band annotations."""
    ex = summary.get("sep_2025_example_report", {})
    gs = ex.get("global_status", {})
    ba = ex.get("band_annotations", {}).get("records", [{}])[0]

    # Global status is GREEN even though there's a band anomaly
    assert gs.get("global_alert_level") == "GREEN", (
        "Global alert level must be GREEN when no P52 threshold is exceeded"
    )
    assert gs.get("global_status") == "MONITORING_ACTIVE_DIAGNOSTIC", (
        "Global status must be MONITORING_ACTIVE_DIAGNOSTIC"
    )

    # Band record has anomaly but global status is not affected
    assert ba.get("annotation") == "SAMPLE_SENSITIVE_BAND_ANOMALY"
    assert ba.get("should_change_global_status") is False

    # VAL01 must exist and mention P52 thresholds
    val_rules = summary.get("validation_rules", {}).get("rules", [])
    val01 = next((r for r in val_rules if r.get("rule_id") == "VAL01"), None)
    assert val01 is not None, "VAL01 must exist"
    rule_text = (val01.get("rule", "") + val01.get("check", "")).lower()
    assert "p52" in rule_text and "threshold" in rule_text, (
        "VAL01 must mention P52 thresholds"
    )

    # global_status schema rules must explicitly say global_status controlled by P52 thresholds only
    gs_rules = summary.get("global_status_section_schema", {}).get("rules", [])
    gs_rules_text = " ".join(gs_rules).lower()
    assert "p52" in gs_rules_text and "threshold" in gs_rules_text, (
        "global_status section rules must mention P52 thresholds"
    )
    assert "band annotation" in gs_rules_text or "band" in gs_rules_text, (
        "global_status section rules must mention band annotation restriction"
    )


# ---------------------------------------------------------------------------
# T13 — P52 thresholds changed flag equals False
# ---------------------------------------------------------------------------
def test_t13_p52_thresholds_unchanged(summary: dict) -> None:
    """p52_thresholds_changed must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("p52_thresholds_changed") is False


# ---------------------------------------------------------------------------
# T14 — Platt constants modified flag equals False
# ---------------------------------------------------------------------------
def test_t14_platt_constants_not_modified(summary: dict) -> None:
    """platt_constants_modified must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("platt_constants_modified") is False

    # Invariants must mention locked Platt constants
    inv_items = summary.get("invariants", {}).get("invariants", [])
    inv_text = " ".join(inv_items)
    assert "0.435432" in inv_text, "Invariants must mention Platt A constant"
    assert "0.245464" in inv_text, "Invariants must mention Platt B constant"


# ---------------------------------------------------------------------------
# T15 — P52/P53/P54/P55/P56/P57 overwrite flags are False
# ---------------------------------------------------------------------------
def test_t15_no_artifact_overwrite(summary: dict) -> None:
    """No prior artifact must be overwritten."""
    gov = summary.get("governance_flags", {})
    for flag in [
        "p52_contract_overwritten",
        "p53_artifact_overwritten",
        "p54_artifact_overwritten",
        "p55_artifact_overwritten",
        "p56_artifact_overwritten",
        "p57_artifact_overwritten",
    ]:
        assert gov.get(flag) is False, f"{flag} must be False, got {gov.get(flag)}"

    # Verify actual files still exist and are readable
    for json_path in [
        ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json",
        ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json",
        ROOT / "data/mlb_2025/derived/p54_sep_sp_fip_delta_feature_drift_audit_summary.json",
        ROOT / "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json",
        ROOT / "data/mlb_2025/derived/p56_sample_sensitive_band_annotation_policy_summary.json",
        ROOT / "data/mlb_2025/derived/p57_monitoring_contract_v2_annotation_integration_summary.json",
    ]:
        assert json_path.exists(), f"Artifact was deleted or moved: {json_path.name}"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data, f"Artifact appears empty: {json_path.name}"


# ---------------------------------------------------------------------------
# T16 — Governance flags exist and match required values
# ---------------------------------------------------------------------------
def test_t16_governance_flags(summary: dict) -> None:
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
        "p56_artifact_overwritten": False,
        "p57_artifact_overwritten": False,
        "p52_thresholds_changed": False,
    }
    for key, expected in required.items():
        assert key in gov, f"governance_flags missing key: {key}"
        assert gov[key] == expected, (
            f"governance_flags.{key} expected {expected}, got {gov[key]}"
        )


# ---------------------------------------------------------------------------
# T17 — live_api_calls equals 0
# ---------------------------------------------------------------------------
def test_t17_live_api_calls_zero(summary: dict) -> None:
    """live_api_calls must be exactly 0."""
    gov = summary.get("governance_flags", {})
    assert gov.get("live_api_calls") == 0


# ---------------------------------------------------------------------------
# T18 — runtime_recommendation_logic_changed equals False
# ---------------------------------------------------------------------------
def test_t18_runtime_logic_unchanged(summary: dict) -> None:
    """runtime_recommendation_logic_changed must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("runtime_recommendation_logic_changed") is False

    # Forbidden agent actions must include this constraint
    forbidden = summary.get("future_agent_usage_notes", {}).get("forbidden_agent_actions", [])
    forbidden_text = " ".join(forbidden).lower()
    assert "threshold" in forbidden_text, (
        "forbidden_agent_actions must mention threshold modification"
    )
    assert "refit" in forbidden_text, (
        "forbidden_agent_actions must mention refit restriction"
    )


# ---------------------------------------------------------------------------
# T19 — JSON output contains no deployment-readiness classification
# ---------------------------------------------------------------------------
def test_t19_no_deployment_classification(summary: dict) -> None:
    """Final P58 classification must not imply deployment readiness."""
    clf = summary.get("final_p58_classification", "")
    for forbidden in FORBIDDEN_CLASSIFICATIONS:
        assert forbidden not in clf, (
            f"Forbidden classification fragment '{forbidden}' found in '{clf}'"
        )
    allowed = {
        "P58_MONTHLY_REPORT_TEMPLATE_READY_DIAGNOSTIC",
        "P58_MONTHLY_REPORT_TEMPLATE_INCOMPLETE",
        "P58_BLOCKED_BY_SOURCE_MISSING",
    }
    assert clf in allowed, (
        f"Final classification '{clf}' is not in the allowed set: {allowed}"
    )


# ---------------------------------------------------------------------------
# T20 — Reports contain no affirmative production or profit claims
# ---------------------------------------------------------------------------
def test_t20_reports_no_production_claims() -> None:
    """Reports must not contain affirmative production or profit claims."""
    for report_path in [REPORT_MD, BETTING_PLAN_MD]:
        assert report_path.exists(), f"Report not found: {report_path}"
        text = report_path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_REPORT_PHRASES:
            assert phrase.lower() not in text, (
                f"Forbidden phrase '{phrase}' found in {report_path.name}"
            )


# ---------------------------------------------------------------------------
# T21 — active_task.md references final P58 classification
# ---------------------------------------------------------------------------
def test_t21_active_task_references_p58(summary: dict) -> None:
    """active_task.md must reference the final P58 classification."""
    assert ACTIVE_TASK_MD.exists(), f"active_task.md not found: {ACTIVE_TASK_MD}"
    content = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    clf = summary.get("final_p58_classification", "")
    assert clf in content, (
        f"active_task.md must reference '{clf}' but it was not found"
    )
    assert "P58" in content, "active_task.md must reference P58"
    # Verify prior history is preserved (prepend pattern)
    assert "P57_ANNOTATION_INTEGRATION_READY_DIAGNOSTIC" in content, (
        "active_task.md must still reference P57 classification (history preserved)"
    )
    assert "P56_BAND_ANNOTATION_POLICY_READY_DIAGNOSTIC" in content, (
        "active_task.md must still reference P56 classification (history preserved)"
    )
