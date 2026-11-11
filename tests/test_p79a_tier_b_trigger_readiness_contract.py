"""
tests/test_p79a_tier_b_trigger_readiness_contract.py

P79A — Tier B Trigger Readiness + 2026 Live Data Intake Contract
39 tests covering source artifacts, intake contract, state machine,
comparison contract, fixture validation, governance, regression.

Governance: paper_only=True | diagnostic_only=True | production_ready=False
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Import P79A module
# ---------------------------------------------------------------------------

import importlib.util

P79A_PATH = ROOT / "scripts" / "_p79a_tier_b_trigger_readiness_contract.py"
spec = importlib.util.spec_from_file_location("p79a", P79A_PATH)
p79a = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(p79a)  # type: ignore[union-attr]

# ---------------------------------------------------------------------------
# Fixtures — load summary JSON once
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def summary() -> dict:
    path = ROOT / "data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json"
    if not path.exists():
        pytest.skip("P79A summary JSON not generated — run main script first")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def p78_summary() -> dict:
    path = ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json"
    if not path.exists():
        pytest.skip("P78 summary not found")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ===========================================================================
# 1. P78 source artifact loads
# ===========================================================================

def test_01_p78_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json").exists()


def test_02_p78_report_exists():
    assert (ROOT / "report/p78_monthly_shadow_tracker_report_template_20260526.md").exists()


def test_03_p78_script_exists():
    assert (ROOT / "scripts/_p78_monthly_shadow_tracker_report_template.py").exists()


def test_04_p77_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json").exists()


def test_05_predictions_jsonl_exists():
    assert (ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl").exists()


# ===========================================================================
# 2. P78 classification verified
# ===========================================================================

def test_06_p78_classification_verified(summary: dict):
    s1 = summary.get("step1_p78_verification", {})
    assert s1.get("verified") is True, f"P78 verification errors: {s1.get('errors')}"
    assert s1.get("classification") == "P78_MONTHLY_SHADOW_TRACKER_TEMPLATE_READY"


# ===========================================================================
# 3. P78 fixture months verified
# ===========================================================================

def test_07_p78_fixture_months_count(summary: dict):
    s1 = summary.get("step1_p78_verification", {})
    assert s1.get("fixture_months_count") == 6


# ===========================================================================
# 4. P78 governance clean verified
# ===========================================================================

def test_08_p78_governance_clean(summary: dict):
    s1 = summary.get("step1_p78_verification", {})
    assert s1.get("months_all_governance_clean") is True
    assert s1.get("months_all_schema_valid") is True


# ===========================================================================
# 5. 2026 intake row contract generated
# ===========================================================================

def test_09_intake_row_contract_generated(summary: dict):
    s2 = summary.get("step2_intake_row_contract", {})
    assert s2.get("contract_version") == "p79a-v1"
    assert s2.get("contract_name") == "2026_LIVE_TIER_B_INTAKE_ROW_CONTRACT"


# ===========================================================================
# 6. Required intake fields present (all 30)
# ===========================================================================

def test_10_required_intake_fields_present(summary: dict):
    s2 = summary.get("step2_intake_row_contract", {})
    fields = s2.get("required_fields", [])
    for required in p79a.INTAKE_ROW_FIELDS:
        assert required in fields, f"Missing intake field: {required}"
    assert s2.get("required_fields_count") == len(p79a.INTAKE_ROW_FIELDS)


# ===========================================================================
# 7–13. Governance enforcement checks
# ===========================================================================

def test_11_governance_enforcement_paper_only(summary: dict):
    gov = summary["step2_intake_row_contract"]["governance_enforcement"]
    assert gov["paper_only"] is True


def test_12_governance_enforcement_odds_used(summary: dict):
    gov = summary["step2_intake_row_contract"]["governance_enforcement"]
    assert gov["odds_used"] is False


def test_13_governance_enforcement_market_edge(summary: dict):
    gov = summary["step2_intake_row_contract"]["governance_enforcement"]
    assert gov["market_edge_evaluated"] is False


def test_14_governance_enforcement_ev(summary: dict):
    gov = summary["step2_intake_row_contract"]["governance_enforcement"]
    assert gov["ev_calculated"] is False


def test_15_governance_enforcement_clv(summary: dict):
    gov = summary["step2_intake_row_contract"]["governance_enforcement"]
    assert gov["clv_calculated"] is False


def test_16_governance_enforcement_kelly(summary: dict):
    gov = summary["step2_intake_row_contract"]["governance_enforcement"]
    assert gov["kelly_calculated"] is False


def test_17_governance_enforcement_production_ready(summary: dict):
    gov = summary["step2_intake_row_contract"]["governance_enforcement"]
    assert gov["production_ready"] is False


# ===========================================================================
# 14. Tier B candidate definition present
# ===========================================================================

def test_18_tier_b_candidate_definition_present(summary: dict):
    s2 = summary.get("step2_intake_row_contract", {})
    tbd = s2.get("tier_b_candidate_definition", {})
    assert "condition" in tbd
    assert tbd.get("prediction_only") is True
    assert tbd.get("odds_not_required") is True
    assert tbd.get("market_edge_not_included") is True


# ===========================================================================
# 15. Tier B trigger states defined
# ===========================================================================

def test_19_tier_b_trigger_states_defined(summary: dict):
    s3 = summary.get("step3_tier_b_trigger_states", {})
    states = s3.get("states", {})
    assert s3.get("trigger_n") == 200
    assert s3.get("state_count") == 6
    for expected_state in [
        "TIER_B_NOT_READY", "TIER_B_EARLY_OBSERVATION", "TIER_B_ACCUMULATING",
        "TIER_B_TRIGGER_READY", "TIER_B_TRIGGER_FROZEN", "TIER_B_REJECTED_FOR_STABILITY",
    ]:
        assert expected_state in states, f"Missing state: {expected_state}"


# ===========================================================================
# 16–19. State machine unit tests
# ===========================================================================

def test_20_state_not_ready():
    assert p79a._tier_b_state(0) == "TIER_B_NOT_READY"
    assert p79a._tier_b_state(49) == "TIER_B_NOT_READY"


def test_21_state_early_observation():
    assert p79a._tier_b_state(50) == "TIER_B_EARLY_OBSERVATION"
    assert p79a._tier_b_state(99) == "TIER_B_EARLY_OBSERVATION"


def test_22_state_accumulating():
    assert p79a._tier_b_state(100) == "TIER_B_ACCUMULATING"
    assert p79a._tier_b_state(199) == "TIER_B_ACCUMULATING"


def test_23_state_trigger_ready():
    assert p79a._tier_b_state(200) == "TIER_B_TRIGGER_READY"
    assert p79a._tier_b_state(500) == "TIER_B_TRIGGER_READY"


# ===========================================================================
# 20. Frozen snapshot package schema generated
# ===========================================================================

def test_24_frozen_snapshot_schema_generated(summary: dict):
    s5 = summary.get("step5_handoff_package_schema", {})
    assert s5.get("schema_name") == "P79_TRIGGER_HANDOFF_PACKAGE"
    assert s5.get("schema_version") == "p79a-v1"
    for field in p79a.HANDOFF_REQUIRED_FIELDS:
        assert field in s5.get("required_fields", []), f"Missing handoff field: {field}"


# ===========================================================================
# 21. Trigger handoff package generated (from fixture)
# ===========================================================================

def test_25_trigger_handoff_package_generated(summary: dict):
    s6 = summary.get("step6_fixture_validation", {})
    assert s6.get("trigger_fires") is True, "Fixture trigger should fire"
    frozen = s6.get("frozen_package")
    assert frozen is not None, "frozen_package must be generated"
    assert frozen.get("trigger_status") == "TIER_B_TRIGGER_FROZEN"


# ===========================================================================
# 22. P79 execution prompt generated
# ===========================================================================

def test_26_p79_execution_prompt_generated(summary: dict):
    frozen = summary["step6_fixture_validation"]["frozen_package"]
    prompt = frozen.get("recommended_p79_prompt", "")
    assert len(prompt) > 50, "P79 prompt should be non-trivial"
    assert "P79" in prompt
    assert "Tier B" in prompt
    assert "paper_only=True" in prompt
    assert "DEFERRED" in prompt or "deferred" in prompt.lower()


# ===========================================================================
# 23. Tier B vs Tier C comparison contract generated
# ===========================================================================

def test_27_comparison_contract_generated(summary: dict):
    s4 = summary.get("step4_comparison_contract", {})
    assert s4.get("contract_name") == "TIER_B_VS_TIER_C_COMPARISON_CONTRACT"
    comparators = s4.get("tier_c_comparators", [])
    names = [c["rule_name"] for c in comparators]
    assert "TIER_C_HOME_PLUS_AWAY_125" in names
    assert "TIER_C_HOME_PLUS_AWAY_100" in names


# ===========================================================================
# 24. Operational research gate defined
# ===========================================================================

def test_28_operational_research_gate_defined(summary: dict):
    gate = summary["step4_comparison_contract"].get("operational_gate", {})
    assert gate.get("gate_name") == "TIER_B_OPERATIONAL_RESEARCH_GATE"
    conditions = gate.get("conditions", [])
    assert len(conditions) >= 4, "At least 4 gate conditions required"
    # n >= 200 condition must be present
    assert any("200" in c for c in conditions), "n >= 200 condition must be in gate"


# ===========================================================================
# 25. Tier B cannot become production-ready in P79
# ===========================================================================

def test_29_tier_b_not_production_ready_in_p79(summary: dict):
    hard = summary["step4_comparison_contract"].get("hard_constraints", {})
    assert hard.get("tier_b_cannot_become_production_ready_in_p79") is True
    assert hard.get("market_edge_not_included_in_p79") is True
    assert hard.get("kelly_not_computed_in_p79") is True


# ===========================================================================
# 26. Fixture monthly cumulative Tier B n computed
# ===========================================================================

def test_30_fixture_monthly_cumulative_computed(summary: dict):
    s6 = summary.get("step6_fixture_validation", {})
    mp = s6.get("monthly_progression", [])
    assert len(mp) == 6, f"Expected 6 months, got {len(mp)}"
    months = [m["month"] for m in mp]
    for expected in p79a.FIXTURE_MONTHS:
        assert expected in months, f"Missing month {expected}"
    # Cumulative must be non-decreasing
    cums = [m["cumulative_tier_b_n"] for m in mp]
    for i in range(1, len(cums)):
        assert cums[i] >= cums[i - 1], f"Cumulative went backwards at index {i}"


# ===========================================================================
# 27. Fixture trigger fires at expected month (2025-07 or later)
# ===========================================================================

def test_31_fixture_trigger_fires_at_expected_month(summary: dict):
    s6 = summary.get("step6_fixture_validation", {})
    assert s6.get("trigger_fires") is True
    trigger_month = s6.get("trigger_month")
    assert trigger_month is not None
    trigger_n = s6.get("trigger_n")
    assert trigger_n is not None
    assert trigger_n >= 200, f"trigger_n={trigger_n} must be >= 200"
    # Must be within fixture period
    assert trigger_month in p79a.FIXTURE_MONTHS, f"Trigger month {trigger_month} not in fixture"


# ===========================================================================
# 28. Fixture frozen package has all required handoff fields
# ===========================================================================

def test_32_frozen_package_has_all_required_fields(summary: dict):
    frozen = summary["step6_fixture_validation"]["frozen_package"]
    for field in p79a.HANDOFF_REQUIRED_FIELDS:
        assert field in frozen, f"frozen_package missing field: {field}"


def test_33_frozen_package_governance_clean(summary: dict):
    frozen = summary["step6_fixture_validation"]["frozen_package"]
    gov = frozen.get("governance_snapshot", {})
    assert gov.get("paper_only") is True
    assert gov.get("production_ready") is False
    assert gov.get("odds_used") is False
    assert gov.get("market_edge_evaluated") is False
    assert gov.get("ev_calculated") is False
    assert gov.get("live_api_calls") == 0


# ===========================================================================
# 29. Market-edge remains blocked
# ===========================================================================

def test_34_market_edge_remains_blocked(summary: dict):
    assert summary.get("market_edge_lane") == "blocked"
    assert summary["step1_p78_verification"].get("market_edge_lane") == "blocked"
    frozen = summary["step6_fixture_validation"].get("frozen_package", {})
    reason = frozen.get("blocked_market_edge_reason", "")
    assert len(reason) > 10, "blocked_market_edge_reason must be non-trivial"


def test_35_comparison_contract_market_edge_blocked(summary: dict):
    s4 = summary.get("step4_comparison_contract", {})
    assert s4.get("market_edge_lane") == "blocked"


# ===========================================================================
# 30. No odds required
# ===========================================================================

def test_36_no_odds_required(summary: dict):
    tbd = summary["step2_intake_row_contract"]["tier_b_candidate_definition"]
    assert tbd.get("odds_not_required") is True


# ===========================================================================
# 31. No EV / CLV / Kelly calculated
# ===========================================================================

def test_37_no_ev_clv_kelly():
    assert p79a.GOVERNANCE["ev_calculated"] is False
    assert p79a.GOVERNANCE["clv_calculated"] is False
    assert p79a.GOVERNANCE["kelly_calculated"] is False
    assert p79a.GOVERNANCE["kelly_deploy_allowed"] is False


# ===========================================================================
# 32. live_api_calls=0
# ===========================================================================

def test_38_live_api_calls_zero():
    assert p79a.GOVERNANCE["live_api_calls"] == 0


# ===========================================================================
# 33. production_ready=False
# ===========================================================================

def test_39_production_ready_false():
    assert p79a.GOVERNANCE["production_ready"] is False


# ===========================================================================
# 34. Forbidden phrase scan passes
# ===========================================================================

def test_40_forbidden_scan_passes(summary: dict):
    scan = summary.get("step7_forbidden_scan", {})
    assert scan.get("scan_passed") is True, f"Violations: {scan.get('violations')}"
    assert scan.get("violations_count") == 0


# ===========================================================================
# 35. JSON schema stable (required top-level keys)
# ===========================================================================

def test_41_json_schema_stable(summary: dict):
    required_keys = [
        "p79a_classification",
        "schema_version",
        "generated_at",
        "governance_snapshot",
        "source_artifacts_verified",
        "step1_p78_verification",
        "step2_intake_row_contract",
        "step3_tier_b_trigger_states",
        "step4_comparison_contract",
        "step5_handoff_package_schema",
        "step6_fixture_validation",
        "step7_forbidden_scan",
        "step8_pack_synthesis",
        "market_edge_lane",
        "tier_b_trigger_n",
        "rules",
        "p79_recommendation",
    ]
    for key in required_keys:
        assert key in summary, f"Missing top-level key: {key}"


def test_42_schema_version_stable(summary: dict):
    assert summary.get("schema_version") == "p79a-v1"


# ===========================================================================
# 36. Report includes trigger transition table
# ===========================================================================

def test_43_report_includes_trigger_table():
    report_path = ROOT / "report/p79a_tier_b_trigger_readiness_contract_20260526.md"
    if not report_path.exists():
        pytest.skip("Report not generated yet")
    content = report_path.read_text(encoding="utf-8")
    assert "Monthly Tier B Accumulation" in content
    assert "2025-04" in content
    assert "2025-09" in content
    assert "Cumulative N" in content
    assert "State" in content


# ===========================================================================
# 37. Report includes handoff package schema
# ===========================================================================

def test_44_report_includes_handoff_schema():
    report_path = ROOT / "report/p79a_tier_b_trigger_readiness_contract_20260526.md"
    if not report_path.exists():
        pytest.skip("Report not generated yet")
    content = report_path.read_text(encoding="utf-8")
    assert "Frozen Trigger Handoff Package" in content
    assert "snapshot_id" in content
    assert "recommended_p79_prompt" in content


# ===========================================================================
# 38. active_task.md updated
# ===========================================================================

def test_45_active_task_updated():
    at_path = ROOT / "00-Plan/roadmap/active_task.md"
    assert at_path.exists()
    content = at_path.read_text(encoding="utf-8")
    assert "P79A" in content, "active_task.md must mention P79A"


# ===========================================================================
# 39. P79A classification is READY
# ===========================================================================

def test_46_p79a_classification_is_ready(summary: dict):
    cls = summary.get("p79a_classification", "")
    assert "P79A_TIER_B_TRIGGER_READINESS_CONTRACT_READY" in cls, f"Got: {cls!r}"


# ---------------------------------------------------------------------------
# Additional unit / integration tests
# ---------------------------------------------------------------------------

def test_47_state_machine_boundary_conditions():
    """Boundary conditions for state machine."""
    assert p79a._tier_b_state(0) == "TIER_B_NOT_READY"
    assert p79a._tier_b_state(49) == "TIER_B_NOT_READY"
    assert p79a._tier_b_state(50) == "TIER_B_EARLY_OBSERVATION"
    assert p79a._tier_b_state(99) == "TIER_B_EARLY_OBSERVATION"
    assert p79a._tier_b_state(100) == "TIER_B_ACCUMULATING"
    assert p79a._tier_b_state(199) == "TIER_B_ACCUMULATING"
    assert p79a._tier_b_state(200) == "TIER_B_TRIGGER_READY"
    assert p79a._tier_b_state(1000) == "TIER_B_TRIGGER_READY"


def test_48_is_tier_b_row_correct():
    """Tier B flag: abs_fip in [0.25, 0.50)."""
    def make_row(abs_fip: float) -> dict:
        return {
            "p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": abs_fip},
            "model_home_prob": 0.55,
        }

    assert p79a._is_tier_b_row(make_row(0.25)) is True
    assert p79a._is_tier_b_row(make_row(0.35)) is True
    assert p79a._is_tier_b_row(make_row(0.499)) is True
    assert p79a._is_tier_b_row(make_row(0.50)) is False  # >= 0.50 is NOT Tier B
    assert p79a._is_tier_b_row(make_row(0.24)) is False  # below threshold
    assert p79a._is_tier_b_row(make_row(1.50)) is False  # Tier A


def test_49_is_tier_b_row_fip_unavailable():
    row = {
        "p0_features": {"sp_fip_delta_available": False, "sp_fip_delta": 0.35},
    }
    assert p79a._is_tier_b_row(row) is False


def test_50_snapshot_hash_is_deterministic():
    h1 = p79a._generate_snapshot_hash(2025, "2025-07", 219)
    h2 = p79a._generate_snapshot_hash(2025, "2025-07", 219)
    assert h1 == h2
    assert len(h1) == 16


def test_51_snapshot_hash_changes_with_params():
    h1 = p79a._generate_snapshot_hash(2025, "2025-07", 219)
    h2 = p79a._generate_snapshot_hash(2025, "2025-08", 219)
    h3 = p79a._generate_snapshot_hash(2026, "2026-09", 220)
    assert h1 != h2
    assert h1 != h3


def test_52_snapshot_id_format():
    sid = p79a._generate_snapshot_id(2025, "2025-07")
    assert sid == "tier_b_snapshot_2025_202507"
    sid26 = p79a._generate_snapshot_id(2026, "2026-09")
    assert sid26 == "tier_b_snapshot_2026_202609"


def test_53_p79_prompt_contains_required_elements():
    prompt = p79a._generate_p79_prompt("2025-07", 219, 2025)
    assert "P79" in prompt
    assert "200" in prompt  # trigger threshold
    assert "2025-07" in prompt
    assert "219" in prompt
    assert "paper_only=True" in prompt
    assert "DEFERRED" in prompt or "deferred" in prompt.lower()


def test_54_fixture_trigger_state_monotone(summary: dict):
    """State transitions should never go backward."""
    mp = summary["step6_fixture_validation"]["monthly_progression"]
    assert summary["step6_fixture_validation"]["state_transitions_monotone"] is True
    state_order = {
        "TIER_B_NOT_READY": 0,
        "TIER_B_EARLY_OBSERVATION": 1,
        "TIER_B_ACCUMULATING": 2,
        "TIER_B_TRIGGER_READY": 3,
    }
    states = [m["trigger_state"] for m in mp]
    for i in range(1, len(states)):
        assert state_order[states[i]] >= state_order[states[i - 1]], (
            f"State went backward: {states[i - 1]} → {states[i]}"
        )


def test_55_comparison_contract_metrics_count(summary: dict):
    s4 = summary.get("step4_comparison_contract", {})
    assert s4.get("metrics_count") == len(p79a.COMPARISON_METRICS)
    assert s4.get("metrics_count") >= 18


def test_56_comparison_contract_stability_levels(summary: dict):
    s4 = summary.get("step4_comparison_contract", {})
    levels = s4.get("stability_levels", {})
    for level in ["STRONG", "MODERATE", "WEAK", "INSUFFICIENT"]:
        assert level in levels, f"Missing stability level: {level}"


def test_57_intake_field_count_is_30(summary: dict):
    s2 = summary.get("step2_intake_row_contract", {})
    assert s2.get("required_fields_count") == 30


def test_58_pack_synthesis_governance_clean(summary: dict):
    pack = summary.get("step8_pack_synthesis", {})
    assert pack.get("governance_clean") is True
    assert pack.get("market_edge_lane") == "blocked"
    assert pack.get("fixture_trigger_fires") is True


def test_59_pack_synthesis_classification(summary: dict):
    pack = summary.get("step8_pack_synthesis", {})
    assert "P79A_TIER_B_TRIGGER_READINESS_CONTRACT_READY" in pack.get("p79a_classification", "")


def test_60_source_artifacts_verified_count(summary: dict):
    arts = summary.get("source_artifacts_verified", [])
    assert len(arts) == len(p79a.SOURCE_ARTIFACT_KEYS), (
        f"Expected {len(p79a.SOURCE_ARTIFACT_KEYS)} artifacts, got {len(arts)}"
    )
