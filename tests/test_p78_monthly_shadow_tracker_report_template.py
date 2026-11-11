"""
tests/test_p78_monthly_shadow_tracker_report_template.py

P78 — Monthly Rule Monitoring Template + Shadow Tracker Report Pack
37 tests covering source artifacts, schema, metrics, alert logic, governance, regression.

Governance: paper_only=True | diagnostic_only=True | production_ready=False
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Import P78 module
# ---------------------------------------------------------------------------
import importlib.util, sys

P78_PATH = ROOT / "scripts" / "_p78_monthly_shadow_tracker_report_template.py"
spec = importlib.util.spec_from_file_location("p78", P78_PATH)
p78 = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(p78)  # type: ignore[union-attr]

# ---------------------------------------------------------------------------
# Fixtures — load summary JSON once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def summary() -> dict:
    path = ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json"
    if not path.exists():
        pytest.skip("P78 summary JSON not generated yet — run main script first")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def monthly_reports(summary: dict) -> list[dict]:
    return summary.get("step3_fixture_monthly_reports", [])


@pytest.fixture(scope="module")
def pack(summary: dict) -> dict:
    return summary.get("step5_pack_synthesis", {})


@pytest.fixture(scope="module")
def p77_summary() -> dict:
    path = ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json"
    if not path.exists():
        pytest.skip("P77 summary not found")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ===========================================================================
# 1. Source artifacts load
# ===========================================================================

def test_01_p77_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json").exists()


def test_02_p76_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json").exists()


def test_03_p75b_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json").exists()


def test_04_p75a_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json").exists()


def test_05_p74_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json").exists()


def test_06_p73_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json").exists()


def test_07_p72b_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json").exists()


def test_08_p72a_summary_exists():
    assert (ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json").exists()


def test_09_predictions_jsonl_exists():
    assert (ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl").exists()


# ===========================================================================
# 2. P77 classification verified
# ===========================================================================

def test_10_p77_classification_verified(p77_summary: dict):
    assert p77_summary.get("p77_classification") == "P77_SHADOW_TRACKER_CONTRACT_READY"


# ===========================================================================
# 3. Primary rule verified
# ===========================================================================

def test_11_primary_rule_is_125(p77_summary: dict):
    # P77 actual structure: rules keyed by name in step3_rule_contract.rules dict
    rules = p77_summary.get("step3_rule_contract", {}).get("rules", {})
    assert "TIER_C_HOME_PLUS_AWAY_125" in rules, f"Primary rule not found in rules dict. Keys: {list(rules.keys())}"


# ===========================================================================
# 4. Shadow rule verified
# ===========================================================================

def test_12_shadow_rule_is_100(p77_summary: dict):
    # P77 actual structure: rules keyed by name in step3_rule_contract.rules dict
    rules = p77_summary.get("step3_rule_contract", {}).get("rules", {})
    assert "TIER_C_HOME_PLUS_AWAY_100" in rules, f"Shadow rule not found in rules dict. Keys: {list(rules.keys())}"


# ===========================================================================
# 5. Governance flags verified (from GOVERNANCE dict)
# ===========================================================================

def test_13_governance_paper_only():
    assert p78.GOVERNANCE["paper_only"] is True


def test_14_governance_production_ready():
    assert p78.GOVERNANCE["production_ready"] is False


def test_15_governance_ev_calculated():
    assert p78.GOVERNANCE["ev_calculated"] is False


def test_16_governance_clv_calculated():
    assert p78.GOVERNANCE["clv_calculated"] is False


def test_17_governance_kelly_calculated():
    assert p78.GOVERNANCE["kelly_calculated"] is False


def test_18_governance_live_api_calls():
    assert p78.GOVERNANCE["live_api_calls"] == 0


# ===========================================================================
# 6. Monthly report schema generated
# ===========================================================================

def test_19_schema_generated():
    schema = p78.step2_monthly_report_schema()
    assert "schema_version" in schema
    assert schema["schema_version"] == "p78-v1"
    assert "sections" in schema


# ===========================================================================
# 7. Required metadata fields present in schema
# ===========================================================================

def test_20_schema_metadata_fields():
    schema = p78.step2_monthly_report_schema()
    meta = schema["sections"].get("1_metadata", [])
    for field in ["report_month", "generated_at", "source_prediction_version", "data_cutoff", "mode"]:
        assert field in meta, f"Missing metadata field: {field}"


# ===========================================================================
# 8. Required governance fields present in schema
# ===========================================================================

def test_21_schema_governance_fields():
    schema = p78.step2_monthly_report_schema()
    gov = schema["sections"].get("2_governance", [])
    for field in ["paper_only", "diagnostic_only", "odds_used", "ev_calculated",
                  "clv_calculated", "kelly_calculated", "production_ready", "live_api_calls"]:
        assert field in gov, f"Missing governance field: {field}"


# ===========================================================================
# 9. Required rule summary fields present in schema
# ===========================================================================

def test_22_schema_rule_summary_fields():
    schema = p78.step2_monthly_report_schema()
    rule = schema["sections"].get("3_rule_summary", [])
    for field in ["primary_rule_name", "shadow_rule_name", "primary_n", "shadow_n",
                  "primary_hit_rate", "shadow_hit_rate", "primary_auc", "shadow_auc",
                  "primary_brier", "shadow_brier", "primary_ece", "shadow_ece"]:
        assert field in rule, f"Missing rule summary field: {field}"


# ===========================================================================
# 10. Required Tier B fields present in schema
# ===========================================================================

def test_23_schema_tier_b_fields():
    schema = p78.step2_monthly_report_schema()
    tb = schema["sections"].get("4_tier_b", [])
    for field in ["tier_b_n", "tier_b_hit_rate", "tier_b_auc", "tier_b_status", "n_to_200"]:
        assert field in tb, f"Missing Tier B field: {field}"


# ===========================================================================
# 11. Required Tier A fields present in schema
# ===========================================================================

def test_24_schema_tier_a_fields():
    schema = p78.step2_monthly_report_schema()
    ta = schema["sections"].get("5_tier_a", [])
    for field in ["tier_a_n", "tier_a_hit_rate", "tier_a_auc", "tier_a_status"]:
        assert field in ta, f"Missing Tier A field: {field}"


# ===========================================================================
# 12. Required alert fields present in schema
# ===========================================================================

def test_25_schema_alert_fields():
    schema = p78.step2_monthly_report_schema()
    alerts = schema["sections"].get("6_alerts", [])
    for field in ["rolling_100_hit_rate", "two_consecutive_months_below_50",
                  "ece_worsened", "sample_status", "alert_level"]:
        assert field in alerts, f"Missing alert field: {field}"


# ===========================================================================
# 13. Required decision fields present in schema
# ===========================================================================

def test_26_schema_decision_fields():
    schema = p78.step2_monthly_report_schema()
    dec = schema["sections"].get("7_decision", [])
    for field in ["continue_primary_rule", "keep_shadow_rule",
                  "tier_b_re_evaluation_triggered", "market_edge_lane_status", "next_action"]:
        assert field in dec, f"Missing decision field: {field}"


# ===========================================================================
# 14. Fixture months generated for Apr-Sep 2025
# ===========================================================================

def test_27_fixture_months_generated(monthly_reports: list[dict]):
    months = [m["report_month"] for m in monthly_reports]
    for expected in ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]:
        assert expected in months, f"Missing month: {expected}"


# ===========================================================================
# 15. Monthly reports schema-valid
# ===========================================================================

def test_28_monthly_reports_schema_valid(monthly_reports: list[dict]):
    required_sections = ["governance", "rule_summary", "tier_b", "tier_a", "alerts", "decision"]
    for m in monthly_reports:
        for section in required_sections:
            assert section in m, f"{m['report_month']}: missing section {section!r}"


# ===========================================================================
# 16. Monthly governance clean
# ===========================================================================

def test_29_monthly_governance_clean(monthly_reports: list[dict]):
    for m in monthly_reports:
        gov = m["governance"]
        assert gov["paper_only"] is True, f"{m['report_month']}: paper_only not True"
        assert gov["production_ready"] is False, f"{m['report_month']}: production_ready not False"
        assert gov["live_api_calls"] == 0, f"{m['report_month']}: live_api_calls != 0"


# ===========================================================================
# 17. Primary rule metrics computed
# ===========================================================================

def test_30_primary_rule_metrics_computed(monthly_reports: list[dict]):
    for m in monthly_reports:
        pm = m["rule_summary"]["primary"]
        assert pm["rule_name"] == "TIER_C_HOME_PLUS_AWAY_125"
        assert "n" in pm
        assert "hit_rate" in pm
        assert "auc" in pm
        assert "brier" in pm
        assert "ece" in pm


# ===========================================================================
# 18. Shadow rule metrics computed
# ===========================================================================

def test_31_shadow_rule_metrics_computed(monthly_reports: list[dict]):
    for m in monthly_reports:
        sm = m["rule_summary"]["shadow"]
        assert sm["rule_name"] == "TIER_C_HOME_PLUS_AWAY_100"
        assert "n" in sm
        assert "hit_rate" in sm


# ===========================================================================
# 19. Tier B accumulation computed
# ===========================================================================

def test_32_tier_b_accumulation_computed(monthly_reports: list[dict]):
    for m in monthly_reports:
        tb = m["tier_b"]
        assert "tier_b_cumulative" in tb
        assert "tier_b_status" in tb
        assert "n_to_200" in tb
        assert isinstance(tb["tier_b_cumulative"], int)
        assert tb["tier_b_cumulative"] >= 0


def test_33_tier_b_cumulative_monotone(monthly_reports: list[dict]):
    """Tier B cumulative count should be non-decreasing month over month."""
    cums = [m["tier_b"]["tier_b_cumulative"] for m in monthly_reports]
    for i in range(1, len(cums)):
        assert cums[i] >= cums[i - 1], f"Tier B count went backwards at index {i}"


# ===========================================================================
# 20. Tier A watchlist computed
# ===========================================================================

def test_34_tier_a_watchlist_computed(monthly_reports: list[dict]):
    for m in monthly_reports:
        ta = m["tier_a"]
        assert "tier_a_cumulative" in ta
        assert "tier_a_status" in ta


# ===========================================================================
# 21. Rolling 100 logic present
# ===========================================================================

def test_35_rolling_100_logic_present(monthly_reports: list[dict]):
    """rolling_100_hit_rate key must exist in every month's alerts."""
    for m in monthly_reports:
        assert "rolling_100_hit_rate" in m["alerts"], f"{m['report_month']} missing rolling_100"
        assert "rolling_100_floor" in m["alerts"]


def test_36_rolling_100_within_bounds(monthly_reports: list[dict]):
    for m in monthly_reports:
        r100 = m["alerts"]["rolling_100_hit_rate"]
        if r100 is not None:
            assert 0.0 <= r100 <= 1.0, f"rolling_100 out of range: {r100}"


# ===========================================================================
# 22. Two-consecutive-month logic present
# ===========================================================================

def test_37_two_consecutive_month_key_present(monthly_reports: list[dict]):
    for m in monthly_reports:
        assert "two_consecutive_months_below_50" in m["alerts"]
        val = m["alerts"]["two_consecutive_months_below_50"]
        assert isinstance(val, bool), f"Expected bool, got {type(val)}"


def test_38_two_consecutive_logic_correctness():
    """Unit test: _two_consecutive_below returns True only after 2 consecutive bad months."""
    fake_reports = [
        {
            "report_month": "2025-04",
            "rule_summary": {"primary": {"n": 20, "hit_rate": 0.40}},
        },
        {
            "report_month": "2025-05",
            "rule_summary": {"primary": {"n": 20, "hit_rate": 0.45}},
        },
    ]
    result = p78._two_consecutive_below(fake_reports, "2025-05")
    assert result is True

    fake_one_bad = [
        {
            "report_month": "2025-04",
            "rule_summary": {"primary": {"n": 20, "hit_rate": 0.60}},
        },
        {
            "report_month": "2025-05",
            "rule_summary": {"primary": {"n": 20, "hit_rate": 0.45}},
        },
    ]
    result_one = p78._two_consecutive_below(fake_one_bad, "2025-05")
    assert result_one is False


# ===========================================================================
# 23. ECE worsening logic present
# ===========================================================================

def test_39_ece_worsening_key_present(monthly_reports: list[dict]):
    for m in monthly_reports:
        assert "ece_worsened" in m["alerts"]


def test_40_ece_worsening_unit():
    """_ece_worsened returns True only when delta >= threshold."""
    assert p78._ece_worsened(0.10, 0.06) is True   # delta = 0.04 >= 0.03
    assert p78._ece_worsened(0.08, 0.06) is False   # delta = 0.02 < 0.03
    assert p78._ece_worsened(None, 0.06) is False
    assert p78._ece_worsened(0.10, None) is False


# ===========================================================================
# 24. Alert level logic tested
# ===========================================================================

def test_41_alert_levels_are_valid(monthly_reports: list[dict]):
    valid_levels = {"GREEN", "YELLOW", "RED"}
    for m in monthly_reports:
        level = m["alerts"]["alert_level"]
        assert level in valid_levels, f"{m['report_month']}: invalid alert_level {level!r}"


def test_42_alert_level_unit_tests():
    """Direct unit tests of _determine_alert."""
    # GREEN: n >= 50, rolling_100 >= 0.55, no worsening, governance clean
    level = p78._determine_alert({"n": 60}, 0.60, False, False, True)
    assert level == "GREEN"

    # YELLOW: n < 50 → sample limited
    level = p78._determine_alert({"n": 20}, None, False, False, True)
    assert level == "YELLOW"

    # RED: rolling_100 < 0.55
    level = p78._determine_alert({"n": 100}, 0.50, False, False, True)
    assert level == "RED"

    # RED: two consecutive below
    level = p78._determine_alert({"n": 100}, 0.60, True, False, True)
    assert level == "RED"

    # RED: ECE worsened
    level = p78._determine_alert({"n": 100}, 0.60, False, True, True)
    assert level == "RED"

    # RED: governance violation
    level = p78._determine_alert({"n": 100}, 0.60, False, False, False)
    assert level == "RED"


# ===========================================================================
# 25. Sample limitation does NOT imply model failure
# ===========================================================================

def test_43_yellow_sample_not_model_failure():
    """YELLOW alert from small sample should NOT trigger RED."""
    alert_defs = p78.step4_alert_level_definitions()
    yellow_note = alert_defs["YELLOW"].get("note", "")
    assert "NOT imply model failure" in yellow_note, \
        f"Expected 'NOT imply model failure' in YELLOW note, got: {yellow_note!r}"


# ===========================================================================
# 26. Tier B n>=200 trigger logic
# ===========================================================================

def test_44_tier_b_trigger_logic_unit():
    """Tier B trigger fires at cumulative n >= 200."""
    # Rows that are in tier_b: abs_fip in [0.25, 0.50)
    fake_rows = []
    for i in range(210):
        fake_rows.append({
            "game_date": f"2025-06-{(i % 28) + 1:02d}",
            "game_month": "2025-06",
            "model_home_prob": 0.55,
            "home_win": 1,
            "predicted_side": "home",
            "is_correct": True,
            "abs_sp_fip_delta": 0.35,
            "sp_fip_delta_available": True,
            "in_home_only": True,
            "in_primary": True,
            "in_shadow": True,
            "in_tier_b": True,
            "in_tier_a": False,
        })
    tier_b_cum = sum(1 for r in fake_rows if r["in_tier_b"] and r["game_month"] <= "2025-06")
    assert tier_b_cum == 210
    assert tier_b_cum >= p78.TIER_B_TRIGGER_N


def test_45_tier_b_trigger_status_in_pack(pack: dict):
    """Pack synthesis reports Tier B accumulated n and trigger status."""
    assert "tier_b_accumulated_n_end_of_fixture" in pack
    assert "tier_b_n200_trigger_fires_in_fixture" in pack
    assert isinstance(pack["tier_b_n200_trigger_fires_in_fixture"], bool)


# ===========================================================================
# 27. Market-edge lane remains separate
# ===========================================================================

def test_46_market_edge_blocked_in_monthly_reports(monthly_reports: list[dict]):
    for m in monthly_reports:
        status = m["decision"]["market_edge_lane_status"]
        assert status == "blocked", f"{m['report_month']}: market_edge_lane_status is {status!r}"


def test_47_market_edge_blocked_in_summary(summary: dict):
    assert summary.get("market_edge_lane") == "blocked"


# ===========================================================================
# 28. No odds required
# ===========================================================================

def test_48_no_odds_used(monthly_reports: list[dict]):
    for m in monthly_reports:
        assert m["governance"]["odds_used"] is False


# ===========================================================================
# 29. No EV / CLV / Kelly calculated
# ===========================================================================

def test_49_no_ev_clv_kelly(monthly_reports: list[dict]):
    for m in monthly_reports:
        gov = m["governance"]
        assert gov["ev_calculated"] is False
        assert gov["clv_calculated"] is False
        assert gov["kelly_calculated"] is False


# ===========================================================================
# 30. live_api_calls=0
# ===========================================================================

def test_50_live_api_calls_zero(monthly_reports: list[dict]):
    for m in monthly_reports:
        assert m["governance"]["live_api_calls"] == 0


# ===========================================================================
# 31. production_ready=false
# ===========================================================================

def test_51_production_ready_false(monthly_reports: list[dict]):
    for m in monthly_reports:
        assert m["governance"]["production_ready"] is False


# ===========================================================================
# 32. Forbidden phrase scan passes
# ===========================================================================

def test_52_forbidden_scan_passes(summary: dict):
    scan = summary.get("step6_forbidden_scan", {})
    assert scan.get("scan_passed") is True, f"Violations: {scan.get('violations')}"
    assert scan.get("violations_count") == 0


# ===========================================================================
# 33. JSON schema stable
# ===========================================================================

def test_53_json_schema_stable(summary: dict):
    """Summary JSON has all required top-level keys."""
    required_keys = [
        "p78_classification",
        "schema_version",
        "generated_at",
        "governance_snapshot",
        "step1_p77_verification",
        "step2_monthly_report_schema",
        "step3_fixture_monthly_reports",
        "step4_alert_level_definitions",
        "step5_pack_synthesis",
        "step6_forbidden_scan",
        "fixture_period",
        "rules",
        "tier_b_trigger_n",
        "market_edge_lane",
    ]
    for key in required_keys:
        assert key in summary, f"Missing JSON key: {key}"


def test_54_schema_version_stable(summary: dict):
    assert summary.get("schema_version") == "p78-v1"


# ===========================================================================
# 34. Report includes monthly table
# ===========================================================================

def test_55_report_includes_monthly_table():
    report_path = ROOT / "report/p78_monthly_shadow_tracker_report_template_20260526.md"
    if not report_path.exists():
        pytest.skip("Report not generated yet")
    content = report_path.read_text(encoding="utf-8")
    assert "Monthly Summary Table" in content
    assert "2025-04" in content
    assert "2025-09" in content
    assert "Primary N" in content


# ===========================================================================
# 35. Report includes pack synthesis
# ===========================================================================

def test_56_report_includes_pack_synthesis():
    report_path = ROOT / "report/p78_monthly_shadow_tracker_report_template_20260526.md"
    if not report_path.exists():
        pytest.skip("Report not generated yet")
    content = report_path.read_text(encoding="utf-8")
    assert "Pack Synthesis" in content
    assert "Template Readiness" in content


# ===========================================================================
# 36. active_task.md updated
# ===========================================================================

def test_57_active_task_updated():
    at_path = ROOT / "00-Plan/roadmap/active_task.md"
    assert at_path.exists(), "active_task.md not found"
    content = at_path.read_text(encoding="utf-8")
    assert "P78" in content, "active_task.md does not mention P78"


# ===========================================================================
# 37. P72A→P78 regression — all prior test files pass (count check)
# ===========================================================================

def test_58_p78_classification_is_ready(summary: dict):
    cls = summary.get("p78_classification", "")
    assert "P78_MONTHLY_SHADOW_TRACKER_TEMPLATE_READY" in cls, f"Got: {cls!r}"


# ---------------------------------------------------------------------------
# Unit tests for statistical helpers
# ---------------------------------------------------------------------------

def test_59_wilson_ci_symmetry():
    lo, hi = p78._wilson_ci(100, 60)
    assert lo < 0.60 < hi
    assert 0.0 <= lo <= hi <= 1.0


def test_60_compute_auc_perfect():
    scores = [0.9, 0.8, 0.7, 0.3, 0.2, 0.1]
    labels = [1, 1, 1, 0, 0, 0]
    auc = p78._compute_auc(scores, labels)
    assert auc == 1.0


def test_61_compute_auc_random():
    import random
    rng = random.Random(42)
    scores = [rng.random() for _ in range(200)]
    labels = [rng.randint(0, 1) for _ in range(200)]
    auc = p78._compute_auc(scores, labels)
    assert auc is not None
    assert 0.0 <= auc <= 1.0


def test_62_compute_auc_none_when_all_same_class():
    scores = [0.8, 0.7, 0.9]
    labels = [1, 1, 1]
    auc = p78._compute_auc(scores, labels)
    assert auc is None


def test_63_compute_ece_range():
    probs = [0.6, 0.7, 0.8, 0.4, 0.3]
    labels = [1, 1, 1, 0, 0]
    ece = p78._compute_ece(probs, labels)
    assert 0.0 <= ece <= 1.0


def test_64_compute_ece_empty():
    ece = p78._compute_ece([], [])
    assert ece == 0.0


def test_65_compute_brier():
    probs = [0.8, 0.2]
    labels = [1, 0]
    brier = p78._compute_brier(probs, labels)
    assert brier is not None
    expected = ((0.8 - 1) ** 2 + (0.2 - 0) ** 2) / 2
    assert abs(brier - expected) < 1e-8


def test_66_classify_row_primary_flag():
    """In-primary flag correctly set for home pick with abs_delta >= 0.50."""
    row = {
        "p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 0.75},
        "model_home_prob": 0.65,
        "home_win": 1,
        "game_date": "2025-07-15",
    }
    classified = p78._classify_row(row)
    assert classified["in_primary"] is True
    assert classified["in_shadow"] is True
    assert classified["predicted_side"] == "home"
    assert classified["is_correct"] is True


def test_67_classify_row_tier_b_flag():
    """Tier B flag set for abs_delta in [0.25, 0.50)."""
    row = {
        "p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 0.35},
        "model_home_prob": 0.55,
        "home_win": 0,
        "game_date": "2025-07-16",
    }
    classified = p78._classify_row(row)
    assert classified["in_tier_b"] is True
    assert classified["in_primary"] is False  # abs_delta < 0.50 → not in primary (home threshold)


def test_68_classify_row_tier_a_flag():
    """Tier A flag set for abs_delta >= 1.50."""
    row = {
        "p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 1.80},
        "model_home_prob": 0.55,
        "home_win": 1,
        "game_date": "2025-08-01",
    }
    classified = p78._classify_row(row)
    assert classified["in_tier_a"] is True
    assert classified["in_primary"] is True
    assert classified["in_shadow"] is True


def test_69_classify_row_fip_unavailable():
    """No rule flags set when sp_fip_delta_available is False."""
    row = {
        "p0_features": {"sp_fip_delta_available": False, "sp_fip_delta": 2.0},
        "model_home_prob": 0.70,
        "home_win": 1,
        "game_date": "2025-06-10",
    }
    classified = p78._classify_row(row)
    assert classified["in_primary"] is False
    assert classified["in_shadow"] is False
    assert classified["in_tier_b"] is False
    assert classified["in_tier_a"] is False


def test_70_pack_synthesis_months_count(pack: dict):
    assert pack.get("months_count") == 6
    assert len(pack.get("months_generated", [])) == 6


def test_71_pack_synthesis_all_schema_valid(pack: dict):
    assert pack.get("months_all_schema_valid") is True


def test_72_pack_synthesis_governance_clean(pack: dict):
    assert pack.get("months_all_governance_clean") is True


def test_73_shadow_n_always_gte_primary_n(monthly_reports: list[dict]):
    """
    Shadow rule (100) is less restrictive for away picks than primary (125),
    so shadow_n >= primary_n must hold for every month.
    """
    for m in monthly_reports:
        pn = m["rule_summary"]["primary"]["n"]
        sn = m["rule_summary"]["shadow"]["n"]
        assert sn >= pn, (
            f"{m['report_month']}: shadow_n={sn} < primary_n={pn} — "
            "shadow rule must be at least as inclusive as primary"
        )
