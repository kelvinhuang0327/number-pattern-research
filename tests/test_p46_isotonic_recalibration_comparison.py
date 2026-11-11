"""
Tests for P46 — Isotonic Regression Recalibration Comparison

14 tests covering:
1.  Tier C row count equals 535
2.  Train/test split deterministic with seed=42
3.  Isotonic calibrated probs within [0, 1]
4.  Isotonic mapping is monotonic non-decreasing
5.  ECE calculation correct on synthetic data
6.  Brier calculation correct on synthetic data
7.  5-fold output contains exactly 5 folds
8.  Walk-forward months are chronological
9.  Walk-forward uses only prior months for fitting
10. Governance flags exist and match required values
11. JSON output contains no deployment-readiness classification
12. Reports do not contain affirmative deployment/profit claims
13. live_api_calls equals 0
14. P46 final classification is one of the allowed diagnostic classifications
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from _p46_isotonic_recalibration_comparison import (
    ALLOWED_P46_CLASSIFICATIONS,
    GOVERNANCE,
    CalibRecord,
    apply_isotonic,
    compute_brier,
    compute_ece,
    fit_isotonic,
    five_fold_cv,
    load_tier_c_records,
    p46_final_classification,
    train_test_comparison,
    walk_forward_monthly,
)

OUT_JSON = ROOT / "data/mlb_2025/derived/p46_isotonic_recalibration_summary.json"

FORBIDDEN_PHRASES = [
    "guaranteed profit",
    "profitability claim",
    "production proposal",
    "ready_for_production",
    "promote_to_live",
    "deployment_ready",
    "recommend production",
    "escalate to live",
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_records(n: int = 150, seed: int = 42) -> list[CalibRecord]:
    import random
    rng = random.Random(seed)
    months = ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]
    records: list[CalibRecord] = []
    for i in range(n):
        delta = rng.uniform(0.5, 2.0) * (1 if rng.random() > 0.5 else -1)
        mp = 1.0 / (1.0 + math.exp(-0.8 * delta))
        win = 1 if rng.random() < mp else 0
        m = months[i % len(months)]
        records.append(CalibRecord(
            game_date=f"{m}-{(i % 28) + 1:02d}",
            month=m,
            model_prob=mp,
            actual_home_win=win,
        ))
    return records


# ---------------------------------------------------------------------------
# Test 1: Tier C row count equals 535
# ---------------------------------------------------------------------------

def test_tier_c_row_count():
    records, inv = load_tier_c_records()
    assert inv["tier_c_rows"] == 535, f"Expected 535, got {inv['tier_c_rows']}"
    assert len(records) == 535


# ---------------------------------------------------------------------------
# Test 2: Train/test split deterministic with seed=42
# ---------------------------------------------------------------------------

def test_train_test_split_deterministic():
    records = _make_records(200)
    r1 = train_test_comparison(records)
    r2 = train_test_comparison(records)
    assert r1["platt_a"] == r2["platt_a"]
    assert r1["isotonic_ece"] == r2["isotonic_ece"]
    assert r1["train_n"] == 160
    assert r1["test_n"] == 40


# ---------------------------------------------------------------------------
# Test 3: Isotonic calibrated probs within [0, 1]
# ---------------------------------------------------------------------------

def test_isotonic_probs_in_unit_interval():
    probs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    labels = [0, 0, 1, 0, 1, 1, 1, 1, 1]
    kp, kc = fit_isotonic(probs, labels)
    test_inputs = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 0.0, 1.0]
    calibrated = apply_isotonic(test_inputs, kp, kc)
    for p, cp in zip(test_inputs, calibrated):
        assert 0.0 <= cp <= 1.0, f"Calibrated prob {cp} out of [0,1] for input {p}"


# ---------------------------------------------------------------------------
# Test 4: Isotonic mapping is monotone non-decreasing
# ---------------------------------------------------------------------------

def test_isotonic_monotone():
    import random
    rng = random.Random(0)
    probs = sorted([rng.uniform(0.3, 0.9) for _ in range(100)])
    labels = [1 if rng.random() < p else 0 for p in probs]
    kp, kc = fit_isotonic(probs, labels)

    # Knot calibrated values must be non-decreasing
    for i in range(len(kc) - 1):
        assert kc[i] <= kc[i + 1] + 1e-10, f"Isotonic violation at knot {i}: {kc[i]} > {kc[i+1]}"

    # Apply to sorted test points → calibrated must be non-decreasing
    test_pts = [i / 100 for i in range(10, 100, 5)]
    cal = apply_isotonic(test_pts, kp, kc)
    for i in range(len(cal) - 1):
        assert cal[i] <= cal[i + 1] + 1e-10, f"Non-monotone at test point {i}: {cal[i]} > {cal[i+1]}"


# ---------------------------------------------------------------------------
# Test 5: ECE correct on synthetic data
# ---------------------------------------------------------------------------

def test_ece_synthetic():
    # All in [0.7, 0.8) bin, 20 samples, actual win rate = 1.0
    probs = [0.72] * 20
    labels = [1] * 20
    ece = compute_ece(probs, labels, n_bins=10, min_bin=5)
    expected = abs(0.72 - 1.0)
    assert abs(ece - expected) < 1e-4, f"ECE {ece} != expected {expected}"


# ---------------------------------------------------------------------------
# Test 6: Brier correct on synthetic data
# ---------------------------------------------------------------------------

def test_brier_synthetic():
    # (0.8-1)^2 + (0.3-0)^2 = 0.04 + 0.09 = 0.13, mean = 0.065
    probs = [0.8, 0.3]
    labels = [1, 0]
    brier = compute_brier(probs, labels)
    assert abs(brier - 0.065) < 1e-9, f"Brier {brier} != 0.065"


# ---------------------------------------------------------------------------
# Test 7: 5-fold contains exactly 5 folds
# ---------------------------------------------------------------------------

def test_five_fold_count():
    records = _make_records(200)
    result = five_fold_cv(records)
    assert len(result["folds"]) == 5
    assert [f["fold_id"] for f in result["folds"]] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Test 8: Walk-forward months are chronological
# ---------------------------------------------------------------------------

def test_walk_forward_chronological():
    records = _make_records(300)
    result = walk_forward_monthly(records)
    eval_months = [r["eval_month"] for r in result["walk_forward_results"]]
    assert eval_months == sorted(eval_months), f"Eval months not chronological: {eval_months}"


# ---------------------------------------------------------------------------
# Test 9: Walk-forward uses only prior months for fitting
# ---------------------------------------------------------------------------

def test_walk_forward_prior_months_only():
    records = _make_records(300)
    result = walk_forward_monthly(records)
    for entry in result["walk_forward_results"]:
        eval_m = entry["eval_month"]
        train_ms = entry["train_months"]
        assert eval_m not in train_ms, f"Eval month {eval_m} appears in train months"
        for tm in train_ms:
            assert tm < eval_m, f"Train month {tm} >= eval month {eval_m}"


# ---------------------------------------------------------------------------
# Test 10: Governance flags exist and match required values
# ---------------------------------------------------------------------------

def test_governance_flags():
    required = {
        "paper_only": True,
        "diagnostic_only": True,
        "promotion_freeze": True,
        "kelly_deploy_allowed": False,
        "live_api_calls": 0,
        "tsl_crawler_modified": False,
        "champion_strategy_changed": False,
        "production_usage_proposed": False,
    }
    for k, v in required.items():
        assert GOVERNANCE[k] == v, f"GOVERNANCE[{k}]={GOVERNANCE[k]}, expected {v}"

    with OUT_JSON.open() as f:
        d = json.load(f)
    gov = d["governance"]
    for k, v in required.items():
        assert gov[k] == v, f"JSON governance[{k}]={gov[k]}, expected {v}"


# ---------------------------------------------------------------------------
# Test 11: JSON output contains no deployment-readiness classification
# ---------------------------------------------------------------------------

DEPLOYABLE = ["ready_for_production", "promote_to_live", "deployment_ready", "champion_replaced"]


def test_no_deployable_in_json():
    text = OUT_JSON.read_text(encoding="utf-8").lower()
    for phrase in DEPLOYABLE:
        assert phrase not in text, f"'{phrase}' found in JSON output"


# ---------------------------------------------------------------------------
# Test 12: Reports no affirmative deployment/profit claims
# ---------------------------------------------------------------------------

def test_reports_no_deployment_claims():
    for rpath in [
        ROOT / "report/p46_isotonic_recalibration_comparison_20260526.md",
        ROOT / "00-BettingPlan/20260526/p46_isotonic_recalibration_comparison_20260526.md",
    ]:
        assert rpath.exists(), f"Missing: {rpath}"
        text = rpath.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"'{phrase}' in {rpath.name}"


# ---------------------------------------------------------------------------
# Test 13: live_api_calls equals 0
# ---------------------------------------------------------------------------

def test_live_api_calls_zero():
    assert GOVERNANCE["live_api_calls"] == 0
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Test 14: P46 classification is one of allowed set
# ---------------------------------------------------------------------------

def test_p46_classification_allowed():
    with OUT_JSON.open() as f:
        d = json.load(f)
    cls = d["p46_classification"]
    assert cls in ALLOWED_P46_CLASSIFICATIONS, f"P46 class '{cls}' not in allowed set"

    # Also verify the classification function enforces this
    for cv_cls in ["ISOTONIC_SUPERIOR", "ISOTONIC_COMPARABLE", "PLATT_PREFERRED"]:
        for wf_cls in ["ISOTONIC_WALK_FORWARD_HELPFUL", "PLATT_WALK_FORWARD_PREFERRED", "MIXED_RECALIBRATION_RESULT"]:
            result = p46_final_classification(cv_cls, wf_cls)
            assert result in ALLOWED_P46_CLASSIFICATIONS, f"Illegal classification: {result}"


# ---------------------------------------------------------------------------
# Bonus: real data output integrity checks
# ---------------------------------------------------------------------------

def test_real_output_structure():
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert "p46a_pilot" in d
    assert "p46b_cv" in d
    assert "p46c_walk_forward" in d
    assert "baselines" in d


def test_real_isotonic_knot_count_reasonable():
    with OUT_JSON.open() as f:
        d = json.load(f)
    knots = d["p46a_pilot"]["isotonic_knot_count"]
    # With ~428 training samples, a reasonable knot count is < 200
    assert 1 <= knots < 200, f"Suspicious knot count: {knots}"


def test_real_cv_has_five_folds():
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert len(d["p46b_cv"]["folds"]) == 5


def test_real_walk_forward_count():
    with OUT_JSON.open() as f:
        d = json.load(f)
    wf = d["p46c_walk_forward"]["walk_forward_results"]
    assert len(wf) == 5  # 6 months → 5 evaluations


def test_cal_probs_bounded_real():
    """Verify isotonic cal range in JSON is within valid bounds."""
    with OUT_JSON.open() as f:
        d = json.load(f)
    mn = d["p46a_pilot"]["isotonic_min_cal_prob"]
    mx = d["p46a_pilot"]["isotonic_max_cal_prob"]
    assert mn is not None and mx is not None
    assert 0.0 <= mn <= mx <= 1.0
