"""
Tests for P51 — Monitoring Contract Revision Audit After P50 Stream Mismatch.

Governance: paper_only=True | diagnostic_only=True | live_api_calls=0
            p48_contract_overwritten=False | p49_artifact_overwritten=False

16 tests total.
"""

from __future__ import annotations

import json
import math
import pathlib

import pytest

# ── Module under test ─────────────────────────────────────────────────────────
import importlib.util
import sys

_SCRIPT = pathlib.Path(__file__).parent.parent / "scripts/_p51_monitoring_contract_revision_audit.py"
spec = importlib.util.spec_from_file_location("p51", _SCRIPT)
p51 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p51)

# ── Summary artifact path ─────────────────────────────────────────────────────
_ROOT = pathlib.Path(__file__).parent.parent
SUMMARY_PATH = _ROOT / "data/mlb_2025/derived/p51_monitoring_contract_revision_summary.json"


def _summary() -> dict:
    with open(SUMMARY_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test 1 — Governance flags
# ---------------------------------------------------------------------------
def test_governance_flags():
    """All P51 governance flags must be set correctly (no live calls, no deployments)."""
    flags = p51.GOVERNANCE_FLAGS
    assert flags["paper_only"] is True
    assert flags["diagnostic_only"] is True
    assert flags["promotion_freeze"] is True
    assert flags["kelly_deploy_allowed"] is False
    assert flags["live_api_calls"] == 0
    assert flags["p48_contract_overwritten"] is False
    assert flags["p49_artifact_overwritten"] is False


# ---------------------------------------------------------------------------
# Test 2 — Platt constants are locked from P45
# ---------------------------------------------------------------------------
def test_platt_constants_locked():
    """P45-locked Platt constants must not be changed."""
    assert p51.PLATT_A == pytest.approx(0.435432, abs=1e-6)
    assert p51.PLATT_B == pytest.approx(0.245464, abs=1e-6)
    assert p51.SIGMOID_K == pytest.approx(0.8, abs=1e-9)
    assert p51.CLIP_EPS == pytest.approx(1e-7, abs=1e-15)


# ---------------------------------------------------------------------------
# Test 3 — fip_signal_prob math
# ---------------------------------------------------------------------------
def test_fip_signal_prob_at_zero():
    """FIP signal prob at delta=0 must equal exactly 0.5."""
    assert p51.fip_signal_prob(0.0, k=1.0) == pytest.approx(0.5, abs=1e-9)


def test_fip_signal_prob_large_positive():
    """FIP signal prob saturates near 1.0 for very large delta."""
    assert p51.fip_signal_prob(20.0, k=1.0) > 0.999


def test_fip_signal_prob_symmetry():
    """FIP signal prob is symmetric: prob(x) + prob(-x) == 1."""
    for x in [0.3, 0.5, 1.0, 2.0]:
        assert p51.fip_signal_prob(x) + p51.fip_signal_prob(-x) == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Test 4 — platt_calibrate monotonicity
# ---------------------------------------------------------------------------
def test_platt_calibrate_monotone():
    """Platt calibration must be strictly monotone increasing on (0, 1)."""
    probs = [0.1, 0.3, 0.5, 0.7, 0.9]
    calibrated = [p51.platt_calibrate(p) for p in probs]
    for i in range(len(calibrated) - 1):
        assert calibrated[i] < calibrated[i + 1]


# ---------------------------------------------------------------------------
# Test 5 — Tier C n == 535 (identical to P50)
# ---------------------------------------------------------------------------
def test_tier_c_n_matches_p50():
    """Tier C must have exactly 535 records — identical to P50 build."""
    tier_c = p51.build_tier_c_for_revised_replay()
    assert len(tier_c) == 535, f"Expected 535, got {len(tier_c)}"


# ---------------------------------------------------------------------------
# Test 6 — Tier C filter criteria
# ---------------------------------------------------------------------------
def test_tier_c_filter_criteria():
    """All Tier C rows must pass: |sp_fip_delta|>=0.5, market in (0,1), home_win defined."""
    tier_c = p51.build_tier_c_for_revised_replay()
    for row in tier_c:
        assert abs(row["sp_fip_delta"]) >= 0.5
        assert 0 < row["market_home_prob_no_vig"] < 1
        assert row["home_win"] in (0, 1)


# ---------------------------------------------------------------------------
# Test 7 — _apply_revised_alert_rules: clean batch → MONITORING_OK
# ---------------------------------------------------------------------------
def test_alert_rules_clean_batch():
    """Good batch (n=120, strong positive edge, ECE ok) → MONITORING_OK."""
    result = p51._apply_revised_alert_rules(
        n=120,
        fip_edge_mean=0.14,
        fip_edge_ci_low=0.11,
        fip_edge_ci_high=0.17,
        platt_ece_val=0.05,
        platt_brier_val=0.24,
    )
    assert result["final_status"] == "MONITORING_OK"
    assert result["edge_status"] == "MONITORING_OK"
    assert result["calibration_status"] == "MONITORING_OK"


# ---------------------------------------------------------------------------
# Test 8 — _apply_revised_alert_rules: CI crosses zero → EDGE_DRIFT_CRITICAL
# ---------------------------------------------------------------------------
def test_alert_rules_edge_drift_critical():
    """CI_low <= 0 must trigger EDGE_DRIFT_CRITICAL regardless of ECE."""
    result = p51._apply_revised_alert_rules(
        n=120,
        fip_edge_mean=0.02,
        fip_edge_ci_low=-0.005,
        fip_edge_ci_high=0.04,
        platt_ece_val=0.05,
        platt_brier_val=0.24,
    )
    assert result["final_status"] == "EDGE_DRIFT_CRITICAL"
    assert result["edge_status"] == "EDGE_DRIFT_CRITICAL"


# ---------------------------------------------------------------------------
# Test 9 — _apply_revised_alert_rules: ECE critical
# ---------------------------------------------------------------------------
def test_alert_rules_calibration_critical():
    """platt_ece > 0.12 must trigger CALIBRATION_CRITICAL."""
    result = p51._apply_revised_alert_rules(
        n=120,
        fip_edge_mean=0.14,
        fip_edge_ci_low=0.11,
        fip_edge_ci_high=0.17,
        platt_ece_val=0.13,  # > ECE_CRIT=0.12
        platt_brier_val=0.24,
    )
    assert result["final_status"] == "CALIBRATION_CRITICAL"
    assert result["calibration_status"] == "CALIBRATION_CRITICAL"


# ---------------------------------------------------------------------------
# Test 10 — SAMPLE_LIMITED dominates WARNING but NOT CRITICAL
# ---------------------------------------------------------------------------
def test_sample_limited_does_not_dominate_critical():
    """n < 100 + CALIBRATION_CRITICAL → final must be CALIBRATION_CRITICAL, not SAMPLE_LIMITED."""
    result = p51._apply_revised_alert_rules(
        n=98,
        fip_edge_mean=0.14,
        fip_edge_ci_low=0.10,
        fip_edge_ci_high=0.18,
        platt_ece_val=0.13,  # CRITICAL
        platt_brier_val=0.24,
    )
    assert result["sample_status"] == "SAMPLE_LIMITED"
    assert result["calibration_status"] == "CALIBRATION_CRITICAL"
    assert result["final_status"] == "CALIBRATION_CRITICAL"


def test_sample_limited_dominates_warning():
    """n < 100 + edge WARNING → final must be SAMPLE_LIMITED."""
    result = p51._apply_revised_alert_rules(
        n=50,
        fip_edge_mean=0.05,  # < EDGE_WARN_MEAN=0.07 but CI doesn't cross zero
        fip_edge_ci_low=0.01,
        fip_edge_ci_high=0.09,
        platt_ece_val=0.05,
        platt_brier_val=0.24,
    )
    assert result["sample_status"] == "SAMPLE_LIMITED"
    assert result["final_status"] == "SAMPLE_LIMITED"


# ---------------------------------------------------------------------------
# Test 11 — bootstrap_ci deterministic with seed=42
# ---------------------------------------------------------------------------
def test_bootstrap_ci_deterministic():
    """bootstrap_ci must produce identical results with same seed (seed=42)."""
    values = [0.12, 0.14, 0.11, 0.13, 0.15] * 20
    ci1 = p51.bootstrap_ci(values, seed=42)
    ci2 = p51.bootstrap_ci(values, seed=42)
    assert ci1[0] == pytest.approx(ci2[0], abs=1e-9)
    assert ci1[1] == pytest.approx(ci2[1], abs=1e-9)


# ---------------------------------------------------------------------------
# Test 12 — Monthly replay: May/Jun changed from CRITICAL to OK
# ---------------------------------------------------------------------------
def test_monthly_may_june_critical_eliminated():
    """P49 May and Jun were EDGE_DRIFT_CRITICAL; under revised contract must be MONITORING_OK."""
    data = _summary()
    rows = {r["month"]: r for r in data["monthly_replay_under_revised_contract"]["rows"]}

    may = rows.get("2025-05")
    assert may is not None, "2025-05 missing from monthly replay"
    assert may["old_p49_status"] == "EDGE_DRIFT_CRITICAL"
    assert may["final_status"] == "MONITORING_OK"
    assert may["status_changed"] is True

    jun = rows.get("2025-06")
    assert jun is not None, "2025-06 missing from monthly replay"
    assert jun["old_p49_status"] == "EDGE_DRIFT_CRITICAL"
    assert jun["final_status"] == "MONITORING_OK"
    assert jun["status_changed"] is True


# ---------------------------------------------------------------------------
# Test 13 — Monthly replay: Sep reveals genuine CALIBRATION_CRITICAL
# ---------------------------------------------------------------------------
def test_monthly_sep_calibration_critical():
    """Sep 2025 (platt_ece>0.12, n=98) must show CALIBRATION_CRITICAL under revised contract."""
    data = _summary()
    rows = {r["month"]: r for r in data["monthly_replay_under_revised_contract"]["rows"]}
    sep = rows.get("2025-09")
    assert sep is not None, "2025-09 missing"
    assert sep["final_status"] == "CALIBRATION_CRITICAL"
    assert sep["platt_ece"] == pytest.approx(0.122929, abs=1e-4)


# ---------------------------------------------------------------------------
# Test 14 — Revised contract produces fewer net CRITICALs than P49
# ---------------------------------------------------------------------------
def test_revised_contract_fewer_monthly_criticals():
    """Monthly CRITICAL count under revised contract must be less than P49's count."""
    data = _summary()
    comparison = data["old_vs_new_status_comparison"]
    old_crit = comparison["monthly_old"]["critical"]
    new_crit = comparison["monthly_new"]["critical"]
    assert new_crit < old_crit, f"Expected fewer CRITICALs: old={old_crit}, new={new_crit}"


def test_revised_contract_fewer_rolling_criticals():
    """Rolling CRITICAL count under revised contract must be less than P49's count."""
    data = _summary()
    comparison = data["old_vs_new_status_comparison"]
    old_crit = comparison["rolling_old"]["critical"]
    new_crit = comparison["rolling_new"]["critical"]
    assert new_crit < old_crit, f"Expected fewer rolling CRITICALs: old={old_crit}, new={new_crit}"


# ---------------------------------------------------------------------------
# Test 15 — Final classification
# ---------------------------------------------------------------------------
def test_final_classification():
    """P51 must classify as P51_REVISED_CONTRACT_REDUCES_FALSE_ALERTS_DIAGNOSTIC."""
    data = _summary()
    assert data["final_classification"] == "P51_REVISED_CONTRACT_REDUCES_FALSE_ALERTS_DIAGNOSTIC"


# ---------------------------------------------------------------------------
# Test 16 — Metric ownership matrix structure
# ---------------------------------------------------------------------------
def test_metric_ownership_matrix_structure():
    """Metric ownership matrix must have 6 entries and correctly assign streams."""
    matrix = p51.build_metric_ownership_matrix()
    assert len(matrix) == 6

    families = {m["metric_family"] for m in matrix}
    assert "EDGE_SIGNAL" in families
    assert "CALIBRATION" in families
    assert "SAMPLE" in families
    assert "DATA_GAP" in families

    edge_metrics = [m for m in matrix if m["metric_family"] == "EDGE_SIGNAL"]
    assert all(m["selected_probability_stream"] == "PLATT_CALIBRATED" or
               "RAW_SIGMOID" in m["selected_probability_stream"]
               for m in edge_metrics), "Edge must use RAW_SIGMOID"

    calib_metrics = [m for m in matrix if m["metric_family"] == "CALIBRATION"]
    assert all(m["selected_probability_stream"] == "PLATT_CALIBRATED"
               for m in calib_metrics), "Calibration must use PLATT_CALIBRATED"
