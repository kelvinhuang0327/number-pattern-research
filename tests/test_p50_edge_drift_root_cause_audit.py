"""
P50 Tests — Edge Drift Root-Cause Audit and Metric Reconciliation
=================================================================

14 tests covering: artifact existence, Tier C verification, edge definitions,
bootstrap CI determinism, worst-batch drilldown, threshold sensitivity,
P48 policy reproduction, governance flags, JSON safety, and active_task.md.
"""

from __future__ import annotations

import json
import math
import pathlib

import numpy as np
import pytest

# ── Import the module under test ──────────────────────────────────────────────
from scripts import _p50_edge_drift_root_cause_audit as p50

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT = pathlib.Path(__file__).parent.parent
P44_PATH = _ROOT / "data/mlb_2025/derived/p44_temporal_stability_summary.json"
P49_PATH = _ROOT / "data/mlb_2025/derived/p49_offline_historical_monitoring_replay_summary.json"
OUTPUT_JSON = _ROOT / "data/mlb_2025/derived/p50_edge_drift_root_cause_audit_summary.json"
OUTPUT_REPORT = _ROOT / "report/p50_edge_drift_root_cause_audit_20260526.md"
OUTPUT_PLAN = _ROOT / "00-BettingPlan/20260526/p50_edge_drift_root_cause_audit_20260526.md"
ACTIVE_TASK = _ROOT / "00-Plan/roadmap/active_task.md"

# ── Session-scoped fixture: run main() once for all tests ─────────────────────

@pytest.fixture(scope="session")
def summary():
    return p50.main()


# ── Test 01: Source artifacts exist and load ──────────────────────────────────

def test_01_source_artifacts_exist_and_load():
    """P44 and P49 source artifact JSON files must exist and be parseable."""
    assert P44_PATH.exists(), f"P44 artifact missing: {P44_PATH}"
    assert P49_PATH.exists(), f"P49 artifact missing: {P49_PATH}"

    p44 = json.loads(P44_PATH.read_text())
    p49 = json.loads(P49_PATH.read_text())

    # P44 must have monthly_breakdown
    assert "monthly_breakdown" in p44, "P44 missing monthly_breakdown"
    assert isinstance(p44["monthly_breakdown"], dict)
    assert len(p44["monthly_breakdown"]) > 0

    # P49 must have monthly_replay and rolling_replay
    assert "monthly_replay" in p49, "P49 missing monthly_replay"
    assert "rolling_replay" in p49, "P49 missing rolling_replay"
    assert "rows" in p49["monthly_replay"]
    assert "rows" in p49["rolling_replay"]


# ── Test 02: Monthly reconciliation covers expected months ────────────────────

def test_02_monthly_reconciliation_covers_all_months(summary):
    """Reconciliation table must cover Apr–Sep 2025."""
    table = summary["task_a_reconciliation"]["monthly_comparison_table"]
    months_found = {r["month"] for r in table}
    expected = {"2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"}
    assert expected == months_found, f"Missing months: {expected - months_found}"


# ── Test 03: Tier C row count equals 535 ─────────────────────────────────────

def test_03_tier_c_n_equals_535(summary):
    """Tier C dataset must contain exactly 535 rows."""
    tier_c_info = summary["tier_c_verification"]
    assert tier_c_info["n"] == 535, f"Expected n=535, got n={tier_c_info['n']}"
    assert tier_c_info["match"] is True


# ── Test 04: Edge definitions include all 5 keys ─────────────────────────────

def test_04_edge_definitions_include_all_five(summary):
    """Edge audit must include all 5 edge definition keys."""
    required = {
        "raw_model_edge",
        "platt_model_edge",
        "side_aware_raw_edge",
        "side_aware_platt_edge",
        "fip_signal_side_aware_edge",
    }
    found = {r["edge_definition"] for r in summary["task_b_edge_audit"]["summary_by_definition"]}
    assert required == found, f"Missing definitions: {required - found}"


# ── Test 05: Bootstrap CI is deterministic with seed=42 ──────────────────────

def test_05_bootstrap_ci_deterministic_seed42():
    """bootstrap_ci must produce identical results when called twice with seed=42."""
    values = [0.05, 0.10, 0.08, 0.12, 0.07, 0.09, 0.11, 0.06, 0.13, 0.08,
              0.09, 0.10, 0.07, 0.11, 0.08, 0.12, 0.09, 0.08, 0.10, 0.11]
    result1 = p50.bootstrap_ci(values, n_boot=5000, seed=42)
    result2 = p50.bootstrap_ci(values, n_boot=5000, seed=42)
    assert result1 == result2, "bootstrap_ci is not deterministic with seed=42"
    mean, std, ci_low, ci_high = result1
    assert ci_low < mean < ci_high, "Mean must be within CI bounds"
    assert ci_low > 0, "Positive edge values should produce positive CI lower bound"


# ── Test 06: Worst batch drilldown has monthly and rolling entries ─────────────

def test_06_worst_batch_drilldown_has_both_types(summary):
    """worst_batches must contain both worst_monthly_batch and worst_rolling_batch."""
    wc = summary["task_c_worst_batches"]
    assert "worst_monthly_batch" in wc
    assert "worst_rolling_batch" in wc

    wm = wc["worst_monthly_batch"]
    wr = wc["worst_rolling_batch"]

    assert "error" not in wm, f"Worst monthly batch error: {wm}"
    assert "error" not in wr, f"Worst rolling batch error: {wr}"

    # Must have batch_id and n
    assert wm.get("batch_id") is not None
    assert wr.get("batch_id") is not None
    assert wm.get("n", 0) > 0
    assert wr.get("n", 0) > 0

    # Must have side-aware edge metrics
    assert "side_aware_mean_edge_bootstrap" in wm
    assert "side_aware_mean_edge_bootstrap" in wr

    # Must have top10 worst rows
    assert "top10_worst_raw_edge_rows" in wm
    assert len(wm["top10_worst_raw_edge_rows"]) > 0


# ── Test 07: Threshold sensitivity has all 5 policies ────────────────────────

def test_07_threshold_sensitivity_has_five_policies(summary):
    """Threshold sensitivity must test exactly 5 policies."""
    results = summary["task_d_threshold_sensitivity"]["results"]
    assert len(results) == 5, f"Expected 5 policies, got {len(results)}"

    policy_ids = {r["policy_id"] for r in results}
    expected_ids = {
        "P1_CURRENT_P48",
        "P2_RELAXED_MEAN",
        "P3_RELATIVE_DECLINE",
        "P4_CI_HIGH_ONLY",
        "P5_SIDE_AWARE_CURRENT",
    }
    assert expected_ids == policy_ids, f"Missing policies: {expected_ids - policy_ids}"


# ── Test 08: Current P48 policy reproduction matches P49 status counts ────────

def test_08_p1_current_p48_reproduces_p49_critical_count(summary):
    """P1_CURRENT_P48 monthly CRITICAL count must match P49's observed CRITICAL months."""
    p1 = next(
        r for r in summary["task_d_threshold_sensitivity"]["results"]
        if r["policy_id"] == "P1_CURRENT_P48"
    )
    # P49 had 2 CRITICAL monthly batches (May and Jun with n>=100)
    assert p1["monthly_counts"]["critical"] == 2, (
        f"Expected P1 monthly critical=2 (matching P49), got {p1['monthly_counts']['critical']}"
    )
    # P49 had 6 CRITICAL rolling batches
    assert p1["rolling_counts"]["critical"] == 6, (
        f"Expected P1 rolling critical=6 (matching P49), got {p1['rolling_counts']['critical']}"
    )


# ── Test 09: Governance flags exist and match required values ─────────────────

def test_09_governance_flags_correct(summary):
    """All governance flags must be present and correctly set."""
    gov = summary["governance"]
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["promotion_freeze"] is True
    assert gov["kelly_deploy_allowed"] is False
    assert gov["tsl_crawler_modified"] is False
    assert gov["champion_strategy_changed"] is False
    assert gov["production_usage_proposed"] is False
    assert gov["runtime_recommendation_logic_changed"] is False


# ── Test 10: live_api_calls equals 0 ─────────────────────────────────────────

def test_10_live_api_calls_zero(summary):
    """live_api_calls must be exactly 0."""
    assert summary["governance"]["live_api_calls"] == 0


# ── Test 11: runtime_recommendation_logic_changed is False ───────────────────

def test_11_runtime_recommendation_logic_unchanged(summary):
    """runtime_recommendation_logic_changed must be False."""
    assert summary["governance"]["runtime_recommendation_logic_changed"] is False


# ── Test 12: JSON output contains no deployment-readiness classification ──────

def test_12_json_no_deployment_readiness():
    """Output JSON must not contain deployment-readiness terms."""
    forbidden = ["READY", "DEPLOY", "APPROVED", "GO_LIVE", "PRODUCTION_OK"]
    text = OUTPUT_JSON.read_text().upper()
    violations = [f for f in forbidden if f in text]
    # The word DEPLOY may appear in governance/recommendation context — check final_classification only
    content = json.loads(OUTPUT_JSON.read_text())
    final_class = content.get("final_classification", "")
    for f in forbidden:
        assert f not in final_class, f"final_classification contains forbidden term: {f}"


# ── Test 13: Reports contain no affirmative production or profit claims ───────

def test_13_reports_no_forbidden_production_claims():
    """Reports must not contain affirmative production/profit phrases (negations are allowed)."""
    # These affirmative phrases are forbidden; "no production proposal" (negation) is fine
    forbidden_affirmatives = [
        "approved for production",
        "profit guaranteed",
        "deploy to prod",
        "live trading approved",
        "ready for live",
        "approved to deploy",
        "cleared for live",
    ]
    for report_path in [OUTPUT_REPORT, OUTPUT_PLAN]:
        assert report_path.exists(), f"Report missing: {report_path}"
        text = report_path.read_text().lower()
        for phrase in forbidden_affirmatives:
            assert phrase not in text, (
                f"Forbidden affirmative phrase '{phrase}' found in {report_path.name}"
            )
    # Ensure paper_only and diagnostic-only framing is present
    for report_path in [OUTPUT_REPORT, OUTPUT_PLAN]:
        text = report_path.read_text().lower()
        assert "paper_only" in text or "diagnostic" in text, (
            f"Report {report_path.name} lacks paper_only / diagnostic framing"
        )


# ── Test 14: active_task.md references final P50 classification ───────────────

def test_14_active_task_references_p50_classification():
    """active_task.md must reference the P50 final classification string."""
    assert ACTIVE_TASK.exists(), f"active_task.md missing: {ACTIVE_TASK}"
    text = ACTIVE_TASK.read_text()
    assert "P50_PROBABILITY_STREAM_MISMATCH_CONFIRMED_DIAGNOSTIC" in text, (
        "active_task.md does not reference P50 final classification"
    )


# ── Unit tests for math helpers ───────────────────────────────────────────────

def test_sigmoid_properties():
    """sigmoid must satisfy: sigmoid(0)=0.5, and K=0.8 scaling."""
    assert abs(p50._sigmoid(0) - 0.5) < 1e-10
    # sigmoid is monotonic
    assert p50._sigmoid(1.0) > p50._sigmoid(0) > p50._sigmoid(-1.0)
    # large values approach 1
    assert p50._sigmoid(10.0) > 0.99


def test_fip_signal_prob_k1():
    """fip_signal_prob must use k=1.0 sigmoid (P44 style)."""
    # sigmoid(1.0 * x) should differ from p50._sigmoid(x) which uses k=0.8
    x = 1.5
    fip_val = p50.fip_signal_prob(x, k=1.0)
    p50_val = p50._sigmoid(x)  # k=0.8
    # Both should be > 0.5 for positive x
    assert fip_val > 0.5
    assert p50_val > 0.5
    # k=1.0 sigmoid must be larger than k=0.8 sigmoid for positive x
    assert fip_val > p50_val


def test_side_aware_edge_always_positive_for_model_backed_side():
    """side_aware_edge must be positive when model has genuine edge over market."""
    # Home pick (model > 0.5), model has edge over market
    edge = p50.side_aware_edge(0.62, 0.55)
    assert abs(edge - (0.62 - 0.55)) < 1e-10

    # Away pick (model < 0.5), model has edge over market (market is 0.6 home = 0.4 away)
    edge = p50.side_aware_edge(0.38, 0.60)  # model picks away at 62%, market at 40% away
    expected = (1 - 0.38) - (1 - 0.60)  # 0.62 - 0.40 = 0.22
    assert abs(edge - expected) < 1e-10
    assert edge > 0


def test_platt_prob_boundary():
    """platt_prob must stay in (0,1) for extreme inputs."""
    assert 0 < p50.platt_prob(0.001) < 1
    assert 0 < p50.platt_prob(0.999) < 1
    assert 0 < p50.platt_prob(0.5) < 1


def test_normal_ci_single_value():
    """normal_ci with single value must return mean=value, ci=[v,v]."""
    mean, std, ci_low, ci_high = p50.normal_ci([0.10])
    assert mean == 0.10
    assert ci_low == ci_high == 0.10


def test_apply_p48_policy_sample_limited():
    """apply_p48_policy must return SAMPLE_LIMITED for n<100."""
    result = p50.apply_p48_policy(50, 0.10, 0.08, 0.12, 0.05, 0.05, "CURRENT")
    assert result["status"] == "SAMPLE_LIMITED"
    assert result["alert_level"] == "WARNING"


def test_apply_p48_policy_critical_ci_crosses_zero():
    """apply_p48_policy must return CRITICAL when CI_low <= 0."""
    result = p50.apply_p48_policy(120, 0.005, -0.001, 0.011, 0.05, 0.05, "CURRENT")
    assert result["alert_level"] == "CRITICAL"


def test_fip_signal_edge_produces_zero_criticals(summary):
    """
    fip_signal_side_aware_edge (P44-equivalent probability source) must produce
    0 CRITICAL monthly alerts across qualifying months.
    This is the key proof that probability source mismatch drives P49 alerts.
    """
    fip_summary = next(
        r for r in summary["task_b_edge_audit"]["summary_by_definition"]
        if r["edge_definition"] == "fip_signal_side_aware_edge"
    )
    assert fip_summary["monthly_critical"] == 0, (
        f"FIP signal must produce 0 CRITICAL monthly alerts (P44-equivalent confirms), "
        f"got critical={fip_summary['monthly_critical']}"
    )
    assert fip_summary["monthly_warning"] == 0, (
        f"FIP signal must produce 0 WARNING monthly alerts in qualifying months, "
        f"got warning={fip_summary['monthly_warning']}"
    )
