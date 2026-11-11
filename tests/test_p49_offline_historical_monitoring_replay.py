"""
P49 Tests — Offline Historical Monitoring Replay Using P48 Contract

18 tests covering:
- Source artifact integrity
- P47 stream selection
- Tier C row count
- Platt coefficients
- Monthly replay ordering and coverage
- Rolling batch determinism
- Alert threshold behaviors (ECE, Brier, Edge)
- DATA_GAP_BLOCKED dominance
- Governance flags
- JSON and report content constraints
- active_task.md reference
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

# ── Module under test ──────────────────────────────────────────────────────────
from scripts import _p49_offline_historical_monitoring_replay as p49

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
P45_JSON = REPO_ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"
P47_JSON = REPO_ROOT / "data/mlb_2025/derived/p47_calibration_synthesis_summary.json"
P48_JSON = REPO_ROOT / "data/mlb_2025/derived/p48_monitoring_loop_contract_summary.json"
P49_JSON = REPO_ROOT / "data/mlb_2025/derived/p49_offline_historical_monitoring_replay_summary.json"
REPORT_MD = REPO_ROOT / "report/p49_offline_historical_monitoring_replay_20260526.md"
BETTING_PLAN_MD = REPO_ROOT / "00-BettingPlan/20260526/p49_offline_historical_monitoring_replay_20260526.md"
ACTIVE_TASK_MD = REPO_ROOT / "00-Plan/roadmap/active_task.md"


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def p49_summary():
    assert P49_JSON.exists(), "P49 JSON output must exist — run the script first"
    return json.loads(P49_JSON.read_text())


@pytest.fixture(scope="module")
def monthly_rows(p49_summary):
    return p49_summary["monthly_replay"]["rows"]


@pytest.fixture(scope="module")
def rolling_rows(p49_summary):
    return p49_summary["rolling_replay"]["rows"]


# ==============================================================================
# TEST 1 — P48 contract source artifact exists and loaded
# ==============================================================================

def test_01_p48_contract_artifact_exists():
    """P48 monitoring contract JSON artifact must exist."""
    assert P48_JSON.exists(), f"P48 artifact missing: {P48_JSON}"
    data = json.loads(P48_JSON.read_text())
    assert "governance" in data, "P48 artifact must contain governance block"
    assert "alert_thresholds" in data, "P48 artifact must contain alert_thresholds"


# ==============================================================================
# TEST 2 — P47 selected stream == PLATT_CALIBRATED
# ==============================================================================

def test_02_p47_selected_stream_is_platt_calibrated():
    """P47 synthesis must have selected PLATT_CALIBRATED as the monitoring stream."""
    assert P47_JSON.exists(), f"P47 artifact missing: {P47_JSON}"
    p47 = json.loads(P47_JSON.read_text())
    # P47 uses key 'selected_monitoring_probability_stream'
    found = (
        p47.get("selected_monitoring_probability_stream")
        or p47.get("selected_stream")
        or p47.get("recommendation", {}).get("selected_stream")
    )
    assert found == "PLATT_CALIBRATED", f"Expected PLATT_CALIBRATED, got: {found}"


# ==============================================================================
# TEST 3 — Tier C row count == 535
# ==============================================================================

def test_03_tier_c_row_count(p49_summary):
    """Tier C rebuilt row count must equal 535."""
    tier_v = p49_summary["tier_c_verification"]
    assert tier_v["tier_c_n"] == 535, f"Expected 535 Tier C rows, got {tier_v['tier_c_n']}"
    assert tier_v["match_expected"] is True


# ==============================================================================
# TEST 4 — Platt coefficients loaded from P45 and finite (a > 0, b > 0)
# ==============================================================================

def test_04_platt_coefficients_valid(p49_summary):
    """Platt coefficients must be loaded from P45 and satisfy a > 0, b > 0."""
    coeffs = p49_summary["platt_coefficients"]
    a = coeffs["platt_a"]
    b = coeffs["platt_b"]
    assert math.isfinite(a), f"platt_a must be finite, got {a}"
    assert math.isfinite(b), f"platt_b must be finite, got {b}"
    assert a > 0, f"platt_a must be > 0, got {a}"
    assert b > 0, f"platt_b must be > 0, got {b}"

    # Cross-reference against P45 source artifact
    p45 = json.loads(P45_JSON.read_text())
    p45_a = p45["p45a_pilot"]["platt_a"]
    p45_b = p45["p45a_pilot"]["platt_b"]
    assert abs(a - p45_a) < 1e-5, f"platt_a mismatch vs P45: P49={a}, P45={p45_a}"
    assert abs(b - p45_b) < 1e-5, f"platt_b mismatch vs P45: P49={b}, P45={p45_b}"


# ==============================================================================
# TEST 5 — Monthly replay rows are chronological (sorted by monthly_bucket)
# ==============================================================================

def test_05_monthly_replay_chronological(monthly_rows):
    """Monthly replay rows must be sorted by monthly_bucket ascending."""
    buckets = [r["monthly_bucket"] for r in monthly_rows]
    assert buckets == sorted(buckets), f"Monthly rows not chronological: {buckets}"


# ==============================================================================
# TEST 6 — Monthly replay covers Apr–Sep 2025 (all 6 months)
# ==============================================================================

def test_06_monthly_replay_covers_apr_sep(monthly_rows):
    """Monthly replay must cover all 6 months: Apr, May, Jun, Jul, Aug, Sep 2025."""
    buckets = [r["monthly_bucket"] for r in monthly_rows]
    expected = ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]
    for month in expected:
        assert month in buckets, f"Month {month} missing from monthly replay"


# ==============================================================================
# TEST 7 — Rolling batches use deterministic size=100 and step=50
# ==============================================================================

def test_07_rolling_batch_params(p49_summary, rolling_rows):
    """Rolling batch params must be batch_size=100, step=50; each batch has exactly 100 rows."""
    params = p49_summary["rolling_batch_params"]
    assert params["batch_size"] == 100, f"Expected batch_size=100, got {params['batch_size']}"
    assert params["step_size"] == 50, f"Expected step_size=50, got {params['step_size']}"

    for r in rolling_rows:
        assert r["batch_n"] == 100, f"Rolling batch {r['batch_id']} has n={r['batch_n']} != 100"


# ==============================================================================
# TEST 8 — No rolling batch n < 100 (partial batches omitted)
# ==============================================================================

def test_08_no_undersized_rolling_batches(rolling_rows):
    """All rolling batches must have n >= 100 (partial final batch is omitted)."""
    for r in rolling_rows:
        n = r["batch_n"]
        assert n >= 100, f"Rolling batch {r['batch_id']} has n={n} < 100 (should have been omitted)"


# ==============================================================================
# TEST 9 — ECE threshold warning/critical behavior (unit test)
# ==============================================================================

def test_09_ece_threshold_evaluate_behavior():
    """ECE thresholds must trigger warning/critical via evaluate_monitoring_row."""
    from scripts._p48_monitoring_loop_contract import evaluate_monitoring_row

    # ECE WARNING (0.10 < ece <= 0.12)
    r_warning = evaluate_monitoring_row(
        batch_n=150,
        probability_stream="PLATT_CALIBRATED",
        raw_ece=0.15,
        platt_ece=0.11,
        raw_brier=0.22,
        platt_brier=0.22,
        mean_edge=0.09,
        edge_ci_low=0.02,
        edge_ci_high=0.16,
    )
    assert r_warning["alert_level"] in ("WARNING", "CRITICAL"), (
        f"ECE=0.11 should produce WARNING or CRITICAL, got {r_warning['alert_level']}"
    )

    # ECE CRITICAL (ece > 0.12)
    r_critical = evaluate_monitoring_row(
        batch_n=150,
        probability_stream="PLATT_CALIBRATED",
        raw_ece=0.20,
        platt_ece=0.14,
        raw_brier=0.22,
        platt_brier=0.22,
        mean_edge=0.09,
        edge_ci_low=0.02,
        edge_ci_high=0.16,
    )
    assert r_critical["alert_level"] == "CRITICAL", (
        f"ECE=0.14 should produce CRITICAL, got {r_critical['alert_level']}"
    )


# ==============================================================================
# TEST 10 — Brier threshold warning/critical behavior (unit test)
# ==============================================================================

def test_10_brier_threshold_evaluate_behavior():
    """Brier thresholds must trigger warning/critical via evaluate_monitoring_row."""
    from scripts._p48_monitoring_loop_contract import evaluate_monitoring_row

    # Brier WARNING (0.25 < brier <= 0.27)
    r_warning = evaluate_monitoring_row(
        batch_n=150,
        probability_stream="PLATT_CALIBRATED",
        raw_ece=0.08,
        platt_ece=0.08,
        raw_brier=0.28,
        platt_brier=0.26,
        mean_edge=0.09,
        edge_ci_low=0.02,
        edge_ci_high=0.16,
    )
    assert r_warning["alert_level"] in ("WARNING", "CRITICAL"), (
        f"Brier=0.26 should produce WARNING or CRITICAL, got {r_warning['alert_level']}"
    )

    # Brier CRITICAL (brier > 0.27)
    r_critical = evaluate_monitoring_row(
        batch_n=150,
        probability_stream="PLATT_CALIBRATED",
        raw_ece=0.08,
        platt_ece=0.08,
        raw_brier=0.30,
        platt_brier=0.29,
        mean_edge=0.09,
        edge_ci_low=0.02,
        edge_ci_high=0.16,
    )
    assert r_critical["alert_level"] == "CRITICAL", (
        f"Brier=0.29 should produce CRITICAL, got {r_critical['alert_level']}"
    )


# ==============================================================================
# TEST 11 — Edge threshold warning/critical behavior (unit test)
# ==============================================================================

def test_11_edge_threshold_evaluate_behavior():
    """Edge thresholds must trigger warning/critical via evaluate_monitoring_row."""
    from scripts._p48_monitoring_loop_contract import evaluate_monitoring_row

    # Edge WARNING (mean_edge < 0.07)
    r_warning = evaluate_monitoring_row(
        batch_n=150,
        probability_stream="PLATT_CALIBRATED",
        raw_ece=0.08,
        platt_ece=0.08,
        raw_brier=0.22,
        platt_brier=0.22,
        mean_edge=0.05,      # below 0.07 warning threshold
        edge_ci_low=0.01,
        edge_ci_high=0.09,
    )
    assert r_warning["alert_level"] in ("WARNING", "CRITICAL"), (
        f"mean_edge=0.05 should produce WARNING or CRITICAL, got {r_warning['alert_level']}"
    )

    # Edge CRITICAL (CI crosses zero: ci_low <= 0)
    r_critical = evaluate_monitoring_row(
        batch_n=150,
        probability_stream="PLATT_CALIBRATED",
        raw_ece=0.08,
        platt_ece=0.08,
        raw_brier=0.22,
        platt_brier=0.22,
        mean_edge=0.03,
        edge_ci_low=-0.02,   # CI crosses zero → critical
        edge_ci_high=0.08,
    )
    assert r_critical["alert_level"] == "CRITICAL", (
        f"edge_ci_low=-0.02 should produce CRITICAL, got {r_critical['alert_level']}"
    )


# ==============================================================================
# TEST 12 — DATA_GAP_BLOCKED dominates all other alerts
# ==============================================================================

def test_12_data_gap_blocked_dominates():
    """DATA_GAP_BLOCKED must dominate SAMPLE_LIMITED and WARNING/CRITICAL alerts."""
    from scripts._p48_monitoring_loop_contract import evaluate_monitoring_row

    # Even with good ECE/Brier/Edge — if closing_line_source_missing → BLOCKED
    r = evaluate_monitoring_row(
        batch_n=150,
        probability_stream="PLATT_CALIBRATED",
        raw_ece=0.05,
        platt_ece=0.05,
        raw_brier=0.20,
        platt_brier=0.20,
        mean_edge=0.12,
        edge_ci_low=0.05,
        edge_ci_high=0.19,
        closing_line_source_missing=True,   # data gap
    )
    assert r["status"] == "DATA_GAP_BLOCKED", (
        f"DATA_GAP_BLOCKED must dominate but got status={r['status']}"
    )
    # P48 contract uses alert_level='BLOCKED' for DATA_GAP_BLOCKED (distinct from CRITICAL)
    assert r["alert_level"] in ("CRITICAL", "BLOCKED"), (
        f"DATA_GAP_BLOCKED must produce CRITICAL or BLOCKED alert level, got {r['alert_level']}"
    )

    # Also verify dominates even when n < 100 (sample limited) + closing_line_source_missing
    r2 = evaluate_monitoring_row(
        batch_n=50,
        probability_stream="PLATT_CALIBRATED",
        raw_ece=0.05,
        platt_ece=0.05,
        raw_brier=0.20,
        platt_brier=0.20,
        mean_edge=0.10,
        edge_ci_low=0.05,
        edge_ci_high=0.15,
        closing_line_source_missing=True,
    )
    assert r2["status"] == "DATA_GAP_BLOCKED", (
        f"DATA_GAP_BLOCKED must dominate SAMPLE_LIMITED but got status={r2['status']}"
    )


# ==============================================================================
# TEST 13 — Governance flags exist and match required values
# ==============================================================================

def test_13_governance_flags(p49_summary):
    """All required governance flags must exist and have correct values."""
    gov = p49_summary["governance"]

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
    }

    for key, expected_val in required.items():
        assert key in gov, f"Governance flag '{key}' missing"
        assert gov[key] == expected_val, (
            f"Governance '{key}' expected={expected_val}, got={gov[key]}"
        )


# ==============================================================================
# TEST 14 — live_api_calls == 0
# ==============================================================================

def test_14_live_api_calls_zero(p49_summary):
    """live_api_calls must be exactly 0."""
    gov = p49_summary["governance"]
    assert gov["live_api_calls"] == 0, f"live_api_calls must be 0, got {gov['live_api_calls']}"


# ==============================================================================
# TEST 15 — runtime_recommendation_logic_changed == False
# ==============================================================================

def test_15_runtime_recommendation_unchanged(p49_summary):
    """runtime_recommendation_logic_changed must be False."""
    gov = p49_summary["governance"]
    assert gov["runtime_recommendation_logic_changed"] is False, (
        "runtime_recommendation_logic_changed must be False"
    )


# ==============================================================================
# TEST 16 — JSON output contains no deployment-readiness classification
# ==============================================================================

def test_16_json_no_deployment_readiness():
    """P49 JSON must not contain any deployment-readiness classification."""
    content = P49_JSON.read_text().lower()
    forbidden_phrases = [
        "deployment_ready",
        "deploy_approved",
        "production_approved",
        "production_ready",
        "champion_replacement",
        "live_deploy",
        "approved_for_live",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in content, (
            f"Forbidden phrase '{phrase}' found in P49 JSON output"
        )


# ==============================================================================
# TEST 17 — Reports contain no affirmative production or profit claims
# ==============================================================================

def test_17_reports_no_production_profit_claims():
    """Both MD reports must not contain affirmative production or profit claims."""
    forbidden_patterns = [
        r"guaranteed profit",
        r"profitability claim",
        r"approved production proposal",
        r"live odds api call",
        r"approved for deployment",
        r"ready for production",
        r"will generate profit",
    ]
    for path in (REPORT_MD, BETTING_PLAN_MD):
        assert path.exists(), f"Report not found: {path}"
        content = path.read_text().lower()
        for pattern in forbidden_patterns:
            assert not re.search(pattern, content), (
                f"Forbidden phrase '{pattern}' found in {path.name}"
            )


# ==============================================================================
# TEST 18 — active_task.md references the final P49 classification
# ==============================================================================

def test_18_active_task_references_p49_classification():
    """active_task.md must reference the P49 final classification."""
    assert ACTIVE_TASK_MD.exists(), f"active_task.md not found: {ACTIVE_TASK_MD}"
    content = ACTIVE_TASK_MD.read_text()

    # Must contain P49 block
    assert "P49" in content, "active_task.md must contain P49 section"

    # Must contain the classification string
    classification = "P49_MONITORING_REPLAY_CRITICAL_DIAGNOSTIC"
    assert classification in content, (
        f"active_task.md must reference final classification '{classification}'"
    )
