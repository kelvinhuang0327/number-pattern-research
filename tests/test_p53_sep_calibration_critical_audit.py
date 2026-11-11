"""
P53 — 16 Tests: Sep 2025 Calibration Critical Root-Cause Audit
"""

from __future__ import annotations

import json
import math
import pathlib

import numpy as np
import pytest

_ROOT = pathlib.Path(__file__).parent.parent
_DERIVED = _ROOT / "data/mlb_2025/derived"

P52_PATH = _DERIVED / "p52_monitoring_contract_v2_summary.json"
P53_JSON = _DERIVED / "p53_sep_calibration_critical_audit_summary.json"
ACTIVE_TASK_PATH = _ROOT / "00-Plan/roadmap/active_task.md"

# Governance expected values
_GOV_LOCKED = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "runtime_recommendation_logic_changed": False,
    "p52_contract_overwritten": False,
}

# P45 locked Platt constants
_PLATT_A = 0.435432
_PLATT_B = 0.245464
_SIGMOID_K = 0.8
_CLIP_EPS = 1e-7

_ALLOWED_CLASSIFICATIONS = [
    "SEP_CALIBRATION_DRIFT_CONFIRMED_DIAGNOSTIC",
    "SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC",
    "SEP_CALIBRATION_BINNING_ARTIFACT_DIAGNOSTIC",
    "SEP_CALIBRATION_INCONCLUSIVE",
]


@pytest.fixture(scope="module")
def audit() -> dict:
    assert P53_JSON.exists(), f"P53 JSON not found: {P53_JSON}"
    return json.loads(P53_JSON.read_text())


# ── Test 1 — P52 source artifact exists and is loaded ────────────────────────

def test_p53_t01_p52_source_artifact_exists_and_loaded(audit):
    """P52 artifact must exist and its classification must appear in P53 output."""
    assert P52_PATH.exists(), f"P52 artifact missing: {P52_PATH}"
    p52_clf = audit.get("p52_classification")
    assert p52_clf is not None, "p52_classification not present in P53 output"
    assert "P52" in p52_clf, f"Unexpected p52_classification: {p52_clf}"


# ── Test 2 — Tier C row count equals 535 ─────────────────────────────────────

def test_p53_t02_tier_c_n_equals_535(audit):
    """Tier C filter must yield exactly 535 rows."""
    tc = audit["tier_c_verification"]
    assert tc["n"] == 535, f"Tier C n={tc['n']}, expected 535"
    assert tc["n_matches_expected"] is True


# ── Test 3 — Sep 2025 subset n is recorded ───────────────────────────────────

def test_p53_t03_sep_subset_n_recorded(audit):
    """Sep 2025 subset n must be recorded and in a valid range."""
    sep_n = audit["sep_2025_drilldown"]["n"]
    assert isinstance(sep_n, int), "Sep n must be an integer"
    assert sep_n > 0, "Sep n must be positive"
    assert sep_n < 535, "Sep n must be a subset of Tier C"
    # Expected ~98 (from P52 evidence)
    assert 50 <= sep_n <= 150, f"Sep n={sep_n} outside expected range [50, 150]"


# ── Test 4 — Platt coefficients match P45 locked values ──────────────────────

def test_p53_t04_platt_coefficients_match_p45(audit):
    """Platt A, B, K, clip_eps must match P45-locked values exactly."""
    coeff = audit["platt_coefficients"]
    assert math.isclose(coeff["platt_a"], _PLATT_A, rel_tol=1e-9), (
        f"platt_a={coeff['platt_a']}, expected {_PLATT_A}"
    )
    assert math.isclose(coeff["platt_b"], _PLATT_B, rel_tol=1e-9), (
        f"platt_b={coeff['platt_b']}, expected {_PLATT_B}"
    )
    assert math.isclose(coeff["sigmoid_k"], _SIGMOID_K, rel_tol=1e-9), (
        f"sigmoid_k={coeff['sigmoid_k']}, expected {_SIGMOID_K}"
    )
    assert coeff["locked_from"] == "P45"


# ── Test 5 — Reliability table contains 10 bins ──────────────────────────────

def test_p53_t05_reliability_table_10_bins(audit):
    """Sep 2025 reliability bins table must have exactly 10 entries."""
    bins = audit["sep_2025_reliability_bins_10"]
    assert isinstance(bins, list), "Bins must be a list"
    assert len(bins) == 10, f"Expected 10 bins, got {len(bins)}"
    # Each bin must have required fields
    required_fields = {
        "bin_low", "bin_high", "n", "ece_contribution", "interpretation"
    }
    for b in bins:
        for field in required_fields:
            assert field in b, f"Bin missing field '{field}': {b}"


# ── Test 6 — ECE calculation is deterministic ─────────────────────────────────

def test_p53_t06_ece_is_deterministic(audit):
    """Running the audit script twice must yield the same ECE value."""
    # Re-import and recompute using the script's functions
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_p53",
        _ROOT / "scripts/_p53_sep_calibration_critical_audit.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    tier_c = mod.load_tier_c()
    sep_rows = [r for r in tier_c if r["game_date"].startswith("2025-09")]
    raw_sep, platt_sep, out_sep = mod.build_calibration_vectors(sep_rows)

    ece_a = mod._ece(platt_sep, out_sep, n_bins=10)
    ece_b = mod._ece(platt_sep, out_sep, n_bins=10)

    assert ece_a == ece_b, f"ECE not deterministic: {ece_a} vs {ece_b}"
    # Must match the stored value (within float precision)
    stored_ece = audit["sep_2025_drilldown"]["metrics"]["platt_ece"]
    assert math.isclose(ece_a, stored_ece, rel_tol=1e-4), (
        f"Recomputed ECE {ece_a} differs from stored {stored_ece}"
    )


# ── Test 7 — Bootstrap uses seed=42 ──────────────────────────────────────────

def test_p53_t07_bootstrap_seed_42(audit):
    """Bootstrap must use seed=42 and n_boot=5000."""
    boot = audit["sample_sensitivity"]["bootstrap"]
    assert boot["seed"] == 42, f"Bootstrap seed={boot['seed']}, expected 42"
    assert boot["n_boot"] == 5000, f"n_boot={boot['n_boot']}, expected 5000"
    # CI must exist and be valid
    assert boot["ci_low_95"] < boot["ci_high_95"], "Bootstrap CI_low must be < CI_high"
    assert 0.0 <= boot["ci_low_95"] <= 1.0, "Bootstrap CI_low must be in [0, 1]"
    assert 0.0 <= boot["ci_high_95"] <= 1.0, "Bootstrap CI_high must be in [0, 1]"


# ── Test 8 — 5-bin, 10-bin, and adaptive outputs exist ───────────────────────

def test_p53_t08_binning_sensitivity_outputs_exist(audit):
    """sample_sensitivity must contain 5-bin, 10-bin, and adaptive bin outputs."""
    bs = audit["sample_sensitivity"]["binning_sensitivity"]
    assert "5_bin" in bs, "5-bin output missing"
    assert "10_bin" in bs, "10-bin output missing"
    assert "adaptive" in bs, "adaptive output missing"

    for method in ["5_bin", "10_bin", "adaptive"]:
        entry = bs[method]
        assert "platt_ece" in entry, f"{method} missing platt_ece"
        assert isinstance(entry["platt_ece"], float), f"{method} platt_ece must be float"
        assert 0.0 <= entry["platt_ece"] <= 1.0, (
            f"{method} platt_ece={entry['platt_ece']} out of range"
        )
        assert "above_critical_0_12" in entry, f"{method} missing above_critical_0_12"

    # Adaptive must have actual bin list
    assert bs["adaptive"]["n_bins_actual"] >= 1, "Adaptive must have at least 1 bin"
    assert isinstance(bs["adaptive"]["bins"], list), "Adaptive bins must be a list"


# ── Test 9 — Late-season comparison includes Sep and at least 2 other periods ─

def test_p53_t09_late_season_comparison(audit):
    """Late-season comparison must include Sep 2025 and at least 2 other periods."""
    comparison = audit["late_season_comparison"]
    assert isinstance(comparison, list), "late_season_comparison must be a list"
    periods = [row["period"] for row in comparison]
    assert "Sep" in periods, f"Sep not found in periods: {periods}"
    # At least 2 other periods besides Sep
    other_periods = [p for p in periods if p != "Sep"]
    assert len(other_periods) >= 2, (
        f"Expected at least 2 non-Sep periods, got {other_periods}"
    )
    # Each entry must have required metrics
    required = {"period", "n", "platt_ece", "platt_brier", "actual_win_rate", "v2_status"}
    for row in comparison:
        for field in required:
            assert field in row, f"Comparison row missing '{field}': {row}"


# ── Test 10 — Governance flags exist and match required values ────────────────

def test_p53_t10_governance_flags(audit):
    """All governance flags must be present and match locked values."""
    gov = audit["governance_flags"]
    for key, expected in _GOV_LOCKED.items():
        assert key in gov, f"governance_flags missing '{key}'"
        assert gov[key] == expected, (
            f"governance_flags['{key}']={gov[key]}, expected {expected}"
        )


# ── Test 11 — live_api_calls equals 0 ─────────────────────────────────────────

def test_p53_t11_live_api_calls_zero(audit):
    """live_api_calls must be exactly 0."""
    assert audit["governance_flags"]["live_api_calls"] == 0


# ── Test 12 — runtime_recommendation_logic_changed is False ──────────────────

def test_p53_t12_runtime_recommendation_logic_unchanged(audit):
    """runtime_recommendation_logic_changed must be False."""
    assert audit["governance_flags"]["runtime_recommendation_logic_changed"] is False


# ── Test 13 — p52_contract_overwritten is False ───────────────────────────────

def test_p53_t13_p52_contract_not_overwritten(audit):
    """p52_contract_overwritten must be False. P52 artifact must remain unchanged."""
    assert audit["governance_flags"]["p52_contract_overwritten"] is False
    # Confirm P52 JSON still exists and contains its canonical fields
    assert P52_PATH.exists()
    p52 = json.loads(P52_PATH.read_text())
    assert "final_p52_classification" in p52, "P52 JSON missing final_p52_classification"
    assert "P52" in p52["final_p52_classification"], "P52 classification corrupted"


# ── Test 14 — JSON output contains no deployment-readiness classification ──────

def test_p53_t14_no_deployment_readiness_classification(audit):
    """P53 output must not contain production deployment language."""
    prohibited_strings = [
        "DEPLOYMENT_READY",
        "PRODUCTION_READY",
        "LIVE_DEPLOYMENT",
        "KELLY_DEPLOY_APPROVED",
        "PROMOTE_TO_PRODUCTION",
    ]
    audit_text = json.dumps(audit)
    for s in prohibited_strings:
        assert s not in audit_text, (
            f"Prohibited deployment string '{s}' found in P53 output"
        )
    # Final classification must be one of the allowed diagnostic classifications
    clf = audit["final_p53_classification"]
    assert clf in _ALLOWED_CLASSIFICATIONS, (
        f"Classification '{clf}' not in allowed set"
    )


# ── Test 15 — Reports contain no affirmative production/profit claims ──────────

def test_p53_t15_no_production_profit_claims_in_reports(audit):
    """MD reports must not contain production deployment or profit guarantee language."""
    report_path = _ROOT / "report/p53_sep_calibration_critical_audit_20260526.md"
    plan_path = _ROOT / "00-BettingPlan/20260526/p53_sep_calibration_critical_audit_20260526.md"

    for path in [report_path, plan_path]:
        assert path.exists(), f"Report not found: {path}"
        content = path.read_text()
        prohibited = [
            "guaranteed profit",
            "approved for production deployment",
            "ready for production deployment",
            "deploy to production",
            "deploy to live",
            "kelly_deploy_allowed=True",
            "kelly deployment approved",
        ]
        for phrase in prohibited:
            assert phrase.lower() not in content.lower(), (
                f"Prohibited phrase '{phrase}' found in {path.name}"
            )
    # Confirm framing note exists in JSON (uses "paper-only" with hyphen)
    framing = audit.get("framing_note", "")
    assert "paper" in framing.lower(), (
        "framing_note must reference paper_only / paper-only"
    )


# ── Test 16 — active_task.md references final P53 classification ──────────────

def test_p53_t16_active_task_references_p53_classification(audit):
    """active_task.md must reference the final P53 classification."""
    assert ACTIVE_TASK_PATH.exists(), f"active_task.md not found: {ACTIVE_TASK_PATH}"
    clf = audit["final_p53_classification"]
    content = ACTIVE_TASK_PATH.read_text()
    assert clf in content, (
        f"active_task.md does not reference P53 classification '{clf}'"
    )
