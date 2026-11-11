"""
Tests for P45 — Platt Scaling Recalibration Pilot

12 deterministic tests covering:
1.  Tier C row count equals 535
2.  Train/test split is deterministic with seed=42
3.  Platt coefficients are finite numeric values
4.  Calibrated probabilities are always within [0, 1]
5.  ECE calculation correct on synthetic data
6.  Brier calculation correct on synthetic data
7.  5-fold output contains exactly 5 folds
8.  Walk-forward months are chronological / use only prior months
9.  Governance flags exist and match required values
10. JSON output contains no deployable classification
11. Reports do not claim production readiness
12. live_api_calls equals 0
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

from _p45_platt_recalibration_pilot import (
    CLIP_EPS,
    GOVERNANCE,
    CalibRecord,
    _logit,
    _platt_prob,
    compute_brier,
    compute_ece,
    fit_platt,
    five_fold_cv,
    load_tier_c_records,
    train_test_platt_pilot,
    walk_forward_monthly,
)

OUT_JSON = ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"

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
# Helper: synthetic records
# ---------------------------------------------------------------------------

def _make_calib_records(n: int = 100, seed: int = 42) -> list[CalibRecord]:
    import random
    rng = random.Random(seed)
    records = []
    months = ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]
    for i in range(n):
        delta = rng.uniform(0.5, 2.0) * (1 if rng.random() > 0.5 else -1)
        mp = 1.0 / (1.0 + math.exp(-0.8 * delta))
        win = 1 if rng.random() < mp else 0
        month = months[i % len(months)]
        records.append(CalibRecord(
            game_date=f"{month}-{(i % 28) + 1:02d}",
            month=month,
            model_prob=mp,
            actual_home_win=win,
        ))
    return records


# ---------------------------------------------------------------------------
# Test 1: Tier C row count equals 535
# ---------------------------------------------------------------------------

def test_tier_c_row_count():
    records, inv = load_tier_c_records()
    assert inv["phase56_tier_c_rows"] == 535, f"Expected 535, got {inv['phase56_tier_c_rows']}"
    assert len(records) == 535


# ---------------------------------------------------------------------------
# Test 2: Train/test split is deterministic with seed=42
# ---------------------------------------------------------------------------

def test_train_test_split_deterministic():
    records = _make_calib_records(200, seed=42)
    r1 = train_test_platt_pilot(records)
    r2 = train_test_platt_pilot(records)
    assert r1["platt_a"] == r2["platt_a"]
    assert r1["platt_b"] == r2["platt_b"]
    assert r1["raw_ece"] == r2["raw_ece"]
    assert r1["calibrated_ece"] == r2["calibrated_ece"]
    assert r1["train_n"] == 160  # 80% of 200
    assert r1["test_n"] == 40   # 20% of 200


# ---------------------------------------------------------------------------
# Test 3: Platt coefficients are finite numeric values
# ---------------------------------------------------------------------------

def test_platt_coefficients_finite():
    records = _make_calib_records(120, seed=0)
    probs = [r.model_prob for r in records]
    labels = [r.actual_home_win for r in records]
    a, b = fit_platt(probs, labels)
    assert math.isfinite(a), f"platt_a is not finite: {a}"
    assert math.isfinite(b), f"platt_b is not finite: {b}"


# ---------------------------------------------------------------------------
# Test 4: Calibrated probabilities are always within [0, 1]
# ---------------------------------------------------------------------------

def test_calibrated_probs_in_unit_interval():
    a, b = 0.8, 0.3
    test_probs = [0.1, 0.25, 0.5, 0.75, 0.9, 0.01, 0.99]
    for p in test_probs:
        cp = _platt_prob(p, a, b)
        assert 0.0 <= cp <= 1.0, f"Calibrated prob {cp} out of [0,1] for input {p}"

    # Edge cases near 0 and 1
    for p in [1e-8, 1.0 - 1e-8, 0.0001, 0.9999]:
        cp = _platt_prob(p, a, b)
        assert 0.0 <= cp <= 1.0, f"Edge case: {cp} out of [0,1] for input {p}"


# ---------------------------------------------------------------------------
# Test 5: ECE correct on synthetic data
# ---------------------------------------------------------------------------

def test_ece_synthetic():
    """
    Perfect calibration: all probs = 0.6, all win = 1.
    All in [0.6, 0.7) bin. predicted_mean = 0.6, actual = 1.0, gap = 0.4.
    ECE = 1.0 * 0.4 = 0.4.
    """
    n = 30
    probs = [0.62] * n
    labels = [1] * n
    ece = compute_ece(probs, labels, n_bins=10, min_bin=5)
    expected = abs(0.62 - 1.0)
    assert abs(ece - expected) < 1e-4, f"ECE {ece} != expected {expected}"


# ---------------------------------------------------------------------------
# Test 6: Brier calculation correct on synthetic data
# ---------------------------------------------------------------------------

def test_brier_synthetic():
    """
    probs=[0.8, 0.2], labels=[1, 0]
    Brier = ((0.8-1)^2 + (0.2-0)^2) / 2 = (0.04 + 0.04) / 2 = 0.04
    """
    probs = [0.8, 0.2]
    labels = [1, 0]
    brier = compute_brier(probs, labels)
    assert abs(brier - 0.04) < 1e-9, f"Brier {brier} != 0.04"


# ---------------------------------------------------------------------------
# Test 7: 5-fold output contains exactly 5 folds
# ---------------------------------------------------------------------------

def test_five_fold_count():
    records = _make_calib_records(200, seed=42)
    result = five_fold_cv(records)
    assert len(result["folds"]) == 5, f"Expected 5 folds, got {len(result['folds'])}"
    fold_ids = [f["fold_id"] for f in result["folds"]]
    assert fold_ids == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Test 8: Walk-forward uses only prior months for fitting
# ---------------------------------------------------------------------------

def test_walk_forward_uses_only_prior_months():
    records = _make_calib_records(300, seed=42)
    result = walk_forward_monthly(records)
    wf = result["walk_forward_results"]

    # Each eval_month must not appear in its own train_months
    for entry in wf:
        eval_m = entry["eval_month"]
        train_ms = entry["train_months"]
        assert eval_m not in train_ms, f"Eval month {eval_m} in train months {train_ms}"

    # Train months must all be strictly before eval_month
    for entry in wf:
        eval_m = entry["eval_month"]
        for tm in entry["train_months"]:
            assert tm < eval_m, f"Train month {tm} >= eval month {eval_m}"

    # Check chronological order: each entry's train_months is ordered
    for entry in wf:
        train_ms = entry["train_months"]
        assert train_ms == sorted(train_ms), f"Train months not sorted: {train_ms}"


# ---------------------------------------------------------------------------
# Test 9: Governance flags exist and match required values
# ---------------------------------------------------------------------------

def test_governance_flags_correct():
    assert GOVERNANCE["paper_only"] is True
    assert GOVERNANCE["diagnostic_only"] is True
    assert GOVERNANCE["promotion_freeze"] is True
    assert GOVERNANCE["kelly_deploy_allowed"] is False
    assert GOVERNANCE["live_api_calls"] == 0
    assert GOVERNANCE["tsl_crawler_modified"] is False
    assert GOVERNANCE["champion_strategy_changed"] is False

    assert OUT_JSON.exists(), f"Output JSON missing: {OUT_JSON}"
    with OUT_JSON.open() as f:
        d = json.load(f)
    gov = d["governance"]
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["promotion_freeze"] is True
    assert gov["kelly_deploy_allowed"] is False
    assert gov["tsl_crawler_modified"] is False
    assert gov["champion_strategy_changed"] is False


# ---------------------------------------------------------------------------
# Test 10: JSON output contains no deployable classification
# ---------------------------------------------------------------------------

DEPLOYABLE_STRINGS = [
    "ready_for_production",
    "promote_to_live",
    "deployment_ready",
    "champion_replaced",
    "live_deployment",
]


def test_no_deployable_classification_in_json():
    with OUT_JSON.open() as f:
        text = f.read().lower()
    for phrase in DEPLOYABLE_STRINGS:
        assert phrase not in text, f"Deployable phrase '{phrase}' in JSON output"


# ---------------------------------------------------------------------------
# Test 11: Reports do not claim production readiness
# ---------------------------------------------------------------------------

def test_reports_no_production_claims():
    for report_path in [
        ROOT / "report/p45_platt_recalibration_pilot_20260526.md",
        ROOT / "00-BettingPlan/20260526/p45_platt_recalibration_pilot_20260526.md",
    ]:
        assert report_path.exists(), f"Missing report: {report_path}"
        text = report_path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"Forbidden phrase '{phrase}' in {report_path.name}"


# ---------------------------------------------------------------------------
# Test 12: live_api_calls equals 0
# ---------------------------------------------------------------------------

def test_live_api_calls_zero():
    assert GOVERNANCE["live_api_calls"] == 0
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Bonus: real data output validation
# ---------------------------------------------------------------------------

def test_real_output_has_three_subsections():
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert "p45a_pilot" in d
    assert "p45b_cv" in d
    assert "p45c_walk_forward" in d


def test_real_platt_coefficients_reasonable():
    with OUT_JSON.open() as f:
        d = json.load(f)
    a = d["p45a_pilot"]["platt_a"]
    b = d["p45a_pilot"]["platt_b"]
    assert math.isfinite(a) and abs(a) < 10, f"platt_a suspicious: {a}"
    assert math.isfinite(b) and abs(b) < 10, f"platt_b suspicious: {b}"


def test_real_ece_improvement_positive():
    with OUT_JSON.open() as f:
        d = json.load(f)
    # Test split ECE improvement
    pilot = d["p45a_pilot"]
    assert pilot["calibrated_ece"] < pilot["raw_ece"], "Calibrated ECE should be < raw ECE on test split"
    # CV aggregate
    cv_agg = d["p45b_cv"]["aggregate"]
    assert cv_agg["mean_ece_improvement"] > 0, "CV mean ECE improvement should be positive"


def test_walk_forward_count():
    with OUT_JSON.open() as f:
        d = json.load(f)
    wf = d["p45c_walk_forward"]["walk_forward_results"]
    # 6 months → 5 walk-forward evaluations
    assert len(wf) == 5, f"Expected 5 WF entries, got {len(wf)}"
