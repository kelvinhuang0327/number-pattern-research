"""
tests/test_p79b_tier_b_vs_tier_c_comparison_harness.py

P79B — Tier B vs Tier C Comparison Harness Fixture Dry-Run
46+ tests covering: source artifacts, governance, schema, snapshot, metrics,
head-to-head, gate, classification, prompt, forbidden scan, regression.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def summary() -> dict:
    path = ROOT / "data/mlb_2025/derived/p79b_tier_b_vs_tier_c_comparison_harness_summary.json"
    assert path.exists(), f"Summary JSON missing: {path}"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def p79a_summary() -> dict:
    path = ROOT / "data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def report_text() -> str:
    path = ROOT / "report/p79b_tier_b_vs_tier_c_comparison_harness_20260526.md"
    assert path.exists(), f"Report missing: {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Import helpers from main script
# ---------------------------------------------------------------------------

import importlib.util
import sys

_script_path = ROOT / "scripts/_p79b_tier_b_vs_tier_c_comparison_harness.py"

_spec = importlib.util.spec_from_file_location("_p79b", _script_path)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

GOVERNANCE = _mod.GOVERNANCE
SNAPSHOT_ID = _mod.SNAPSHOT_ID
CUTOFF_MONTH = _mod.CUTOFF_MONTH
SNAPSHOT_MONTHS = _mod.SNAPSHOT_MONTHS
TIER_B_TRIGGER_N = _mod.TIER_B_TRIGGER_N
CANDIDATE_KEYS = _mod.CANDIDATE_KEYS
COMPARISON_SCHEMA_SECTIONS = _mod.COMPARISON_SCHEMA_SECTIONS
SOURCE_ARTIFACT_KEYS = _mod.SOURCE_ARTIFACT_KEYS
PATHS = _mod.PATHS

# helpers
_wilson_ci = _mod._wilson_ci
_compute_auc = _mod._compute_auc
_auc_ci = _mod._auc_ci
_compute_brier = _mod._compute_brier
_compute_log_loss = _mod._compute_log_loss
_compute_ece = _mod._compute_ece
_is_tier_b_row = _mod._is_tier_b_row
_is_primary_row = _mod._is_primary_row
_is_shadow_row = _mod._is_shadow_row
_is_baseline_row = _mod._is_baseline_row
_get_is_correct = _mod._get_is_correct
_get_pick_prob = _mod._get_pick_prob
_classify_stability = _mod._classify_stability
_concentration_risk = _mod._concentration_risk

# step functions
step1_verify_p79a = _mod.step1_verify_p79a
step2_comparison_schema = _mod.step2_comparison_schema
step8_forbidden_scan = _mod.step8_forbidden_scan

# ===========================================================================
# Tests 01–04: Source artifact existence
# ===========================================================================

@pytest.mark.parametrize("artifact_key", SOURCE_ARTIFACT_KEYS)
def test_01_source_artifacts_exist(artifact_key: str) -> None:
    """All 13 source artifacts must exist on disk."""
    path = PATHS[artifact_key]
    assert path.exists(), f"Missing source artifact: {artifact_key} → {path}"


# ===========================================================================
# Tests 02–04: P79A summary fields
# ===========================================================================

def test_02_p79a_classification(p79a_summary: dict) -> None:
    """P79A classification must be READY."""
    cls = p79a_summary.get("p79a_classification", "")
    assert cls == "P79A_TIER_B_TRIGGER_READINESS_CONTRACT_READY", f"Got: {cls}"


def test_03_p79a_frozen_snapshot_id(p79a_summary: dict) -> None:
    """P79A frozen snapshot_id must match expected."""
    sid = (
        p79a_summary
        .get("step6_fixture_validation", {})
        .get("frozen_package", {})
        .get("snapshot_id", "")
    )
    assert sid == SNAPSHOT_ID, f"Got: {sid!r}"


def test_04_p79a_trigger_n_gte_200(p79a_summary: dict) -> None:
    """P79A fixture trigger_n must be >= 200."""
    n = p79a_summary.get("step6_fixture_validation", {}).get("trigger_n", 0) or 0
    assert n >= TIER_B_TRIGGER_N, f"trigger_n={n} < {TIER_B_TRIGGER_N}"


# ===========================================================================
# Tests 05–06: Comparison harness schema
# ===========================================================================

def test_05_comparison_schema_generated() -> None:
    """step2_comparison_schema must return a non-empty dict."""
    schema = step2_comparison_schema()
    assert isinstance(schema, dict)
    assert len(schema) > 0


def test_06_required_top_level_sections() -> None:
    """All 10 required schema sections must be present."""
    schema = step2_comparison_schema()
    sections = schema.get("top_level_sections", [])
    for s in COMPARISON_SCHEMA_SECTIONS:
        assert s in sections, f"Missing section: {s}"
    assert len(sections) == 10


# ===========================================================================
# Tests 07–13: Governance fields in schema
# ===========================================================================

def test_07_governance_paper_only_true() -> None:
    schema = step2_comparison_schema()
    assert schema["governance_enforcement"]["paper_only"] is True


def test_08_governance_odds_used_false() -> None:
    schema = step2_comparison_schema()
    assert schema["governance_enforcement"]["odds_used"] is False


def test_09_governance_market_edge_evaluated_false() -> None:
    schema = step2_comparison_schema()
    assert schema["governance_enforcement"]["market_edge_evaluated"] is False


def test_10_governance_ev_calculated_false() -> None:
    schema = step2_comparison_schema()
    assert schema["governance_enforcement"]["ev_calculated"] is False


def test_11_governance_clv_calculated_false() -> None:
    schema = step2_comparison_schema()
    assert schema["governance_enforcement"]["clv_calculated"] is False


def test_12_governance_kelly_calculated_false() -> None:
    schema = step2_comparison_schema()
    assert schema["governance_enforcement"]["kelly_calculated"] is False


def test_13_governance_production_ready_false() -> None:
    schema = step2_comparison_schema()
    assert schema["governance_enforcement"]["production_ready"] is False


# ===========================================================================
# Tests 14–19: Fixture snapshot reconstruction
# ===========================================================================

def test_14_fixture_snapshot_reconstructed(summary: dict) -> None:
    """Fixture snapshot section must be present and non-empty."""
    s3 = summary.get("step3_source_snapshot", {})
    assert s3, "step3_source_snapshot missing"
    assert s3.get("total_snapshot_rows", 0) > 0


def test_15_fixture_cutoff_month(summary: dict) -> None:
    """Fixture cutoff month must be 2025-07."""
    s3 = summary.get("step3_source_snapshot", {})
    assert s3.get("cutoff_month") == CUTOFF_MONTH


def test_16_tier_b_candidate_n(summary: dict) -> None:
    """Tier B fixture n must be >= 200."""
    s3 = summary.get("step3_source_snapshot", {})
    n = s3.get("candidate_counts", {}).get("tier_b", 0)
    assert n >= TIER_B_TRIGGER_N, f"tier_b n={n} < {TIER_B_TRIGGER_N}"


def test_17_primary_125_candidate_exists(summary: dict) -> None:
    """Primary 125 candidate must have n > 0."""
    s3 = summary.get("step3_source_snapshot", {})
    n = s3.get("candidate_counts", {}).get("primary_125", 0)
    assert n > 0, f"primary_125 n={n}"


def test_18_shadow_100_candidate_exists(summary: dict) -> None:
    """Shadow 100 candidate must have n > 0."""
    s3 = summary.get("step3_source_snapshot", {})
    n = s3.get("candidate_counts", {}).get("shadow_100", 0)
    assert n > 0, f"shadow_100 n={n}"


def test_19_baseline_50_candidate_exists(summary: dict) -> None:
    """Baseline 50 candidate must have n > 0."""
    s3 = summary.get("step3_source_snapshot", {})
    n = s3.get("candidate_counts", {}).get("baseline_50", 0)
    assert n > 0, f"baseline_50 n={n}"


# ===========================================================================
# Tests 20–29: Candidate metrics
# ===========================================================================

def test_20_candidate_metrics_present(summary: dict) -> None:
    """All 4 candidate metric entries must exist."""
    s4 = summary.get("step4_candidate_metrics", {})
    for key in CANDIDATE_KEYS:
        assert key in s4, f"Missing candidate metrics for {key}"


def test_21_hit_rate_ci_computed(summary: dict) -> None:
    """hit_rate_ci_lower and hit_rate_ci_upper must be present for all candidates."""
    s4 = summary.get("step4_candidate_metrics", {})
    for key in CANDIDATE_KEYS:
        m = s4[key]
        assert "hit_rate_ci_lower" in m, f"{key}: missing hit_rate_ci_lower"
        assert "hit_rate_ci_upper" in m, f"{key}: missing hit_rate_ci_upper"
        if m.get("n", 0) > 0:
            assert m["hit_rate_ci_lower"] is not None
            assert m["hit_rate_ci_upper"] is not None


def test_22_auc_ci_computed(summary: dict) -> None:
    """AUC CIs must be present for candidates with n > 0."""
    s4 = summary.get("step4_candidate_metrics", {})
    for key in CANDIDATE_KEYS:
        m = s4[key]
        if m.get("n", 0) > 0:
            assert m.get("auc") is not None, f"{key}: AUC is None"
            assert "auc_ci_lower" in m, f"{key}: missing auc_ci_lower"
            assert "auc_ci_upper" in m, f"{key}: missing auc_ci_upper"


def test_23_brier_computed(summary: dict) -> None:
    """Brier score must be computed for all non-empty candidates."""
    s4 = summary.get("step4_candidate_metrics", {})
    for key in CANDIDATE_KEYS:
        m = s4[key]
        if m.get("n", 0) > 0:
            assert m.get("brier") is not None, f"{key}: brier is None"
            assert 0.0 <= m["brier"] <= 1.0, f"{key}: brier out of range"


def test_24_log_loss_computed(summary: dict) -> None:
    """Log-loss must be computed for all non-empty candidates."""
    s4 = summary.get("step4_candidate_metrics", {})
    for key in CANDIDATE_KEYS:
        m = s4[key]
        if m.get("n", 0) > 0:
            assert m.get("log_loss") is not None, f"{key}: log_loss is None"
            assert m["log_loss"] > 0.0, f"{key}: log_loss <= 0"


def test_25_ece_computed(summary: dict) -> None:
    """ECE must be computed for all non-empty candidates."""
    s4 = summary.get("step4_candidate_metrics", {})
    for key in CANDIDATE_KEYS:
        m = s4[key]
        if m.get("n", 0) > 0:
            assert m.get("ece") is not None, f"{key}: ece is None"
            assert 0.0 <= m["ece"] <= 1.0, f"{key}: ece out of range"


def test_26_monthly_stability_computed(summary: dict) -> None:
    """Monthly stability classification must be present."""
    s4 = summary.get("step4_candidate_metrics", {})
    valid_values = {"STRONG", "MODERATE", "WEAK", "INSUFFICIENT"}
    for key in CANDIDATE_KEYS:
        m = s4[key]
        if m.get("n", 0) > 0:
            stab = m.get("monthly_stability")
            assert stab in valid_values, f"{key}: stability={stab!r} not in {valid_values}"


def test_27_rolling_100_computed_when_n_permits(summary: dict) -> None:
    """Rolling 100 hit_rate must be computed when n >= 100."""
    s4 = summary.get("step4_candidate_metrics", {})
    for key in CANDIDATE_KEYS:
        m = s4[key]
        if m.get("n", 0) >= 100:
            r100 = m.get("rolling_100_hit_rate")
            assert r100 is not None, f"{key}: rolling_100_hit_rate is None (n={m['n']})"
            assert 0.0 <= r100 <= 1.0, f"{key}: rolling_100 out of range"


def test_28_home_away_split_computed(summary: dict) -> None:
    """Home/away n and hit_rates must be present."""
    s4 = summary.get("step4_candidate_metrics", {})
    for key in CANDIDATE_KEYS:
        m = s4[key]
        if m.get("n", 0) > 0:
            assert "n_home" in m, f"{key}: n_home missing"
            assert "n_away" in m, f"{key}: n_away missing"
            assert m["n_home"] + m["n_away"] == m["n"], (
                f"{key}: n_home+n_away != n"
            )


def test_29_concentration_risk_computed(summary: dict) -> None:
    """Concentration risk must be one of LOW/MODERATE/SEVERE/UNKNOWN."""
    s4 = summary.get("step4_candidate_metrics", {})
    valid = {"LOW", "MODERATE", "SEVERE", "UNKNOWN"}
    for key in CANDIDATE_KEYS:
        m = s4[key]
        if m.get("n", 0) > 0:
            cr = m.get("concentration_risk")
            assert cr in valid, f"{key}: concentration_risk={cr!r}"


# ===========================================================================
# Tests 30–32: Head-to-head comparison and gate
# ===========================================================================

def test_30_head_to_head_comparison_generated(summary: dict) -> None:
    """Head-to-head must have 3 comparisons (vs primary, shadow, baseline)."""
    s5 = summary.get("step5_head_to_head", {})
    comparisons = s5.get("comparisons", {})
    assert "vs_primary_125" in comparisons
    assert "vs_shadow_100" in comparisons
    assert "vs_baseline_50" in comparisons


def test_31_operational_research_gate_applied(summary: dict) -> None:
    """Operational research gate must have exactly 6 conditions."""
    s5 = summary.get("step5_head_to_head", {})
    gate = s5.get("operational_research_gate", {})
    conditions = gate.get("conditions", {})
    expected_conditions = {
        "n_gte_200", "performance_ok", "stability_ok",
        "ece_ok", "concentration_ok", "prediction_only",
    }
    assert set(conditions.keys()) == expected_conditions, (
        f"Unexpected gate conditions: {set(conditions.keys())}"
    )


def test_32_tier_b_cannot_become_production_ready(summary: dict) -> None:
    """tier_b_cannot_become_production_ready must be True."""
    s5 = summary.get("step5_head_to_head", {})
    assert s5.get("tier_b_cannot_become_production_ready") is True


# ===========================================================================
# Tests 33–35: Fixture classification and prompt
# ===========================================================================

def test_33_fixture_dry_run_classification_generated(summary: dict) -> None:
    """Fixture dry-run classification must be one of the expected values."""
    s6 = summary.get("step6_fixture_classification", {})
    valid = {
        "TIER_B_OUTPERFORMS_TIER_C_FIXTURE",
        "TIER_B_COMPETITIVE_WITH_TIER_C_FIXTURE",
        "TIER_B_RESEARCH_ONLY_FIXTURE",
        "TIER_B_UNDERPERFORMS_TIER_C_FIXTURE",
        "TIER_B_FIXTURE_INCONCLUSIVE",
    }
    cls = s6.get("fixture_dry_run_classification", "")
    assert cls in valid, f"Got: {cls!r}"


def test_34_fixture_result_not_2026_live_conclusion(summary: dict) -> None:
    """is_2026_live_conclusion must be False."""
    s6 = summary.get("step6_fixture_classification", {})
    assert s6.get("is_2026_live_conclusion") is False


def test_35_future_p79_prompt_generated(summary: dict) -> None:
    """Future P79 prompt must be a non-empty string."""
    s7 = summary.get("step7_future_p79_prompt", {})
    prompt = s7.get("prompt_text", "")
    assert isinstance(prompt, str) and len(prompt) > 100, "Prompt too short or missing"
    assert "P79" in prompt
    assert "STOP" in prompt
    assert "GOVERNANCE" in prompt.upper() or "governance" in prompt.lower()


# ===========================================================================
# Tests 36–40: Market-edge, odds, EV/CLV/Kelly, live_api, production
# ===========================================================================

def test_36_market_edge_lane_blocked(summary: dict) -> None:
    """market_edge_lane must be 'blocked'."""
    assert summary.get("market_edge_lane") == "blocked"
    s5 = summary.get("step5_head_to_head", {})
    assert s5.get("market_edge_lane") == "blocked"


def test_37_no_odds_required() -> None:
    """GOVERNANCE must confirm odds_used=False."""
    assert GOVERNANCE["odds_used"] is False
    assert GOVERNANCE["uses_historical_odds"] is False


def test_38_no_ev_clv_kelly() -> None:
    """GOVERNANCE must confirm no EV/CLV/Kelly computed."""
    assert GOVERNANCE["ev_calculated"] is False
    assert GOVERNANCE["clv_calculated"] is False
    assert GOVERNANCE["kelly_calculated"] is False
    assert GOVERNANCE["market_edge_evaluated"] is False


def test_39_live_api_calls_zero() -> None:
    """GOVERNANCE live_api_calls must be 0."""
    assert GOVERNANCE["live_api_calls"] == 0


def test_40_production_ready_false() -> None:
    """GOVERNANCE production_ready must be False."""
    assert GOVERNANCE["production_ready"] is False


# ===========================================================================
# Test 41: Forbidden scan
# ===========================================================================

def test_41_forbidden_scan_passes() -> None:
    """step8_forbidden_scan must return scan_passed=True, 0 violations."""
    result = step8_forbidden_scan()
    assert result["scan_passed"] is True, f"Violations: {result['violations']}"
    assert result["violations_count"] == 0


# ===========================================================================
# Test 42: JSON schema stability
# ===========================================================================

REQUIRED_TOP_LEVEL_KEYS = {
    "p79b_classification",
    "schema_version",
    "generated_at",
    "governance_snapshot",
    "source_artifacts_verified",
    "step1_p79a_verification",
    "step2_comparison_schema",
    "step3_source_snapshot",
    "step4_candidate_metrics",
    "step5_head_to_head",
    "step6_fixture_classification",
    "step7_future_p79_prompt",
    "step8_forbidden_scan",
    "market_edge_lane",
    "fixture_dry_run_classification",
    "fixture_is_2026_live_conclusion",
}


def test_42_json_schema_stable(summary: dict) -> None:
    """Summary JSON must have all 16 required top-level keys."""
    keys = set(summary.keys())
    missing = REQUIRED_TOP_LEVEL_KEYS - keys
    assert not missing, f"Missing top-level keys: {missing}"
    assert len(REQUIRED_TOP_LEVEL_KEYS) == 16


# ===========================================================================
# Tests 43–44: Report content
# ===========================================================================

def test_43_report_includes_candidate_metrics_table(report_text: str) -> None:
    """Report must include a candidate metrics table."""
    assert "Candidate Metrics Table" in report_text
    for key in CANDIDATE_KEYS:
        assert f"`{key}`" in report_text, f"Candidate {key} not in report metrics table"


def test_44_report_includes_future_p79_prompt(report_text: str) -> None:
    """Report must include the Future P79 Execution Prompt section."""
    assert "Future P79 Execution Prompt" in report_text
    assert "TRIGGER CONDITION" in report_text
    assert "STOP CONDITIONS" in report_text


# ===========================================================================
# Test 45: active_task.md updated
# ===========================================================================

def test_45_active_task_updated() -> None:
    """active_task.md must mention P79B."""
    path = ROOT / "00-Plan/roadmap/active_task.md"
    assert path.exists(), "active_task.md missing"
    content = path.read_text(encoding="utf-8")
    assert "P79B" in content, "active_task.md must mention P79B"


# ===========================================================================
# Test 46: P72A–P79B regression stub (validated by running full suite)
# ===========================================================================

def test_46_regression_prior_summaries_exist() -> None:
    """All P72A–P79A summary JSONs must still exist (regression guard)."""
    prior_summaries = [
        "p72a_odds_free_strategy_accuracy_backtest_summary.json",
        "p72b_objective_metric_contract_summary.json",
        "p73_tier_stability_and_sample_expansion_summary.json",
        "p74_tier_c_home_away_bias_correction_summary.json",
        "p75a_tier_c_corrected_rule_validator_summary.json",
        "p75b_calibration_diagnostics_corrected_tier_c_summary.json",
        "p76_corrected_tier_c_final_rule_selection_summary.json",
        "p77_prediction_only_shadow_tracker_contract_summary.json",
        "p78_monthly_shadow_tracker_report_template_summary.json",
        "p79a_tier_b_trigger_readiness_contract_summary.json",
    ]
    derived = ROOT / "data/mlb_2025/derived"
    for name in prior_summaries:
        assert (derived / name).exists(), f"Prior summary missing: {name}"


# ===========================================================================
# Unit tests for statistical helpers
# ===========================================================================

def test_wilson_ci_basic() -> None:
    lo, hi = _wilson_ci(100, 60)
    assert 0.50 < lo < 0.60
    assert 0.65 < hi < 0.75


def test_wilson_ci_zero_n() -> None:
    lo, hi = _wilson_ci(0, 0)
    assert lo == 0.0 and hi == 0.0


def test_compute_auc_perfect() -> None:
    scores = [0.9, 0.8, 0.3, 0.2]
    labels = [1, 1, 0, 0]
    auc = _compute_auc(scores, labels)
    assert auc == pytest.approx(1.0)


def test_compute_auc_no_positives() -> None:
    assert _compute_auc([0.5, 0.5], [0, 0]) is None


def test_auc_ci_range() -> None:
    lo, hi = _auc_ci(0.60, 50, 50)
    assert 0.0 < lo < 0.60 < hi < 1.0


def test_brier_perfect() -> None:
    b = _compute_brier([1.0, 1.0, 0.0, 0.0], [1, 1, 0, 0])
    assert b == pytest.approx(0.0)


def test_brier_empty() -> None:
    assert _compute_brier([], []) is None


def test_log_loss_perfect() -> None:
    ll = _compute_log_loss([1.0 - 1e-12, 1.0 - 1e-12], [1, 1])
    assert ll < 0.01


def test_ece_perfect_calibration() -> None:
    # 100 predictions all at 0.6 with 60 correct = perfect calibration
    probs = [0.6] * 100
    labels = [1] * 60 + [0] * 40
    ece = _compute_ece(probs, labels)
    assert ece is not None
    assert ece < 0.05


def test_is_tier_b_row() -> None:
    row = {"p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 0.35}, "model_home_prob": 0.6}
    assert _is_tier_b_row(row) is True


def test_is_not_tier_b_row_above_range() -> None:
    row = {"p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 0.60}, "model_home_prob": 0.6}
    assert _is_tier_b_row(row) is False


def test_is_not_tier_b_row_below_range() -> None:
    row = {"p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 0.10}, "model_home_prob": 0.6}
    assert _is_tier_b_row(row) is False


def test_is_not_tier_b_row_unavailable() -> None:
    row = {"p0_features": {"sp_fip_delta_available": False, "sp_fip_delta": 0.35}, "model_home_prob": 0.6}
    assert _is_tier_b_row(row) is False


def test_is_primary_row_home() -> None:
    row = {"p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 0.60}, "model_home_prob": 0.65}
    assert _is_primary_row(row) is True


def test_is_primary_row_away_passes() -> None:
    row = {"p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 1.30}, "model_home_prob": 0.35}
    assert _is_primary_row(row) is True


def test_is_primary_row_away_fails_threshold() -> None:
    # away pick with abs=1.10 < 1.25 → not in primary
    row = {"p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 1.10}, "model_home_prob": 0.35}
    assert _is_primary_row(row) is False


def test_is_shadow_row_away_passes() -> None:
    # away pick with abs=1.05 >= 1.00 → in shadow
    row = {"p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 1.05}, "model_home_prob": 0.40}
    assert _is_shadow_row(row) is True


def test_is_baseline_row() -> None:
    row = {"p0_features": {"sp_fip_delta_available": True, "sp_fip_delta": 0.51}, "model_home_prob": 0.60}
    assert _is_baseline_row(row) is True


def test_get_is_correct_home_right() -> None:
    row = {"home_win": 1, "model_home_prob": 0.7}
    assert _get_is_correct(row) == 1


def test_get_is_correct_home_wrong() -> None:
    row = {"home_win": 0, "model_home_prob": 0.7}
    assert _get_is_correct(row) == 0


def test_get_is_correct_away_right() -> None:
    row = {"home_win": 0, "model_home_prob": 0.3}
    assert _get_is_correct(row) == 1


def test_get_is_correct_missing_home_win() -> None:
    row = {"model_home_prob": 0.7}
    assert _get_is_correct(row) is None


def test_get_pick_prob_home() -> None:
    row = {"model_home_prob": 0.72}
    assert _get_pick_prob(row) == pytest.approx(0.72)


def test_get_pick_prob_away() -> None:
    row = {"model_home_prob": 0.35}
    assert _get_pick_prob(row) == pytest.approx(0.65)


def test_classify_stability_strong() -> None:
    hrs = [0.58, 0.60, 0.57, 0.62]
    ns = [60, 65, 60, 65]
    assert _classify_stability(hrs, ns) == "STRONG"


def test_classify_stability_moderate() -> None:
    hrs = [0.54, 0.53, 0.52, 0.50]
    ns = [60, 60, 60, 60]
    assert _classify_stability(hrs, ns) == "MODERATE"


def test_classify_stability_insufficient() -> None:
    hrs = [0.55, 0.60]
    ns = [50, 60]
    assert _classify_stability(hrs, ns) == "INSUFFICIENT"


def test_concentration_risk_severe() -> None:
    assert _concentration_risk(95, 5) == "SEVERE"


def test_concentration_risk_moderate() -> None:
    assert _concentration_risk(80, 20) == "MODERATE"


def test_concentration_risk_low() -> None:
    assert _concentration_risk(60, 40) == "LOW"


def test_step1_verify_p79a_returns_verified() -> None:
    """step1_verify_p79a must return verified=True in nominal run."""
    result = step1_verify_p79a()
    assert result["verified"] is True, f"Errors: {result.get('errors')}"


def test_p79b_classification_in_expected_set(summary: dict) -> None:
    """P79B final classification must be one of the 7 expected values."""
    valid = {
        "P79B_TIER_B_COMPARISON_HARNESS_READY",
        "P79B_TIER_B_FIXTURE_OUTPERFORMS_TIER_C",
        "P79B_TIER_B_FIXTURE_COMPETITIVE_WITH_TIER_C",
        "P79B_TIER_B_FIXTURE_RESEARCH_ONLY",
        "P79B_TIER_B_FIXTURE_UNDERPERFORMS_TIER_C",
        "P79B_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
        "P79B_FAILED_VALIDATION",
    }
    cls = summary.get("p79b_classification", "")
    assert cls in valid, f"Got: {cls!r}"
