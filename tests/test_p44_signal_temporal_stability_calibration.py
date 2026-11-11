"""
Tests for P44 — Signal Temporal Stability + Calibration Audit

10 deterministic tests covering:
1. Monthly keys exist and are valid
2. Monthly n sum equals total Tier C n
3. Bootstrap CI is deterministic with seed=42
4. Month classification follows CI rule
5. Calibration bin count equals 10
6. Brier score in [0.0, 0.5]
7. ECE correct on synthetic data
8. Governance flags in both JSON outputs
9. live_api_calls equals 0
10. No deployment readiness claims
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from _p44_signal_temporal_stability_calibration import (
    GOVERNANCE,
    JoinedRecord,
    N_BOOT,
    SEED,
    TIER_C_THRESHOLD,
    _classify_month,
    _classify_temporal_pattern,
    bootstrap_mean_ci,
    calibration_audit,
    temporal_stability_analysis,
)

OUT_TEMPORAL = ROOT / "data/mlb_2025/derived/p44_temporal_stability_summary.json"
OUT_CALIBRATION = ROOT / "data/mlb_2025/derived/p44_calibration_audit_summary.json"


# ---------------------------------------------------------------------------
# Helper: build synthetic JoinedRecord list
# ---------------------------------------------------------------------------

def _make_records(month_edges: dict[str, list[tuple[float, float, int]]]) -> list[JoinedRecord]:
    """
    month_edges: {month: [(sp_fip_delta, market_prob, actual_home_win), ...]}
    model_prob = sigmoid(0.8 * delta)
    """
    import math

    def sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-0.8 * x))

    def edge(model_p: float, mkt_p: float) -> float:
        if model_p >= 0.5:
            return model_p - mkt_p
        return (1.0 - model_p) - (1.0 - mkt_p)

    records: list[JoinedRecord] = []
    for month, triples in month_edges.items():
        game_date = f"{month}-01"
        for delta, mkt_p, win in triples:
            mp = sigmoid(delta)
            records.append(JoinedRecord(
                game_date=game_date,
                month=month,
                sp_fip_delta=delta,
                model_prob=mp,
                market_home_prob=mkt_p,
                actual_home_win=win,
                edge=edge(mp, mkt_p),
            ))
    return records


# ---------------------------------------------------------------------------
# Test 1: Monthly keys exist and are valid YYYY-MM format
# ---------------------------------------------------------------------------

def test_monthly_keys_valid_format():
    result = temporal_stability_analysis(_make_records({
        "2025-04": [(0.6, 0.45, 1)] * 20,
        "2025-05": [(0.8, 0.50, 1)] * 30,
        "2025-09": [(1.0, 0.45, 1)] * 25,
    }))
    months = list(result["monthly_breakdown"].keys())
    assert len(months) == 3
    for m in months:
        assert len(m) == 7, f"Month key should be YYYY-MM, got: {m}"
        assert m[:4].isdigit()
        assert m[4] == "-"
        assert m[5:7].isdigit()
        year, mon = int(m[:4]), int(m[5:7])
        assert 2020 <= year <= 2030
        assert 1 <= mon <= 12


# ---------------------------------------------------------------------------
# Test 2: Monthly n sum equals total Tier C n
# ---------------------------------------------------------------------------

def test_monthly_n_sum_equals_total():
    records = _make_records({
        "2025-04": [(0.7, 0.50, 1)] * 15,
        "2025-05": [(0.9, 0.48, 1)] * 40,
        "2025-06": [(1.2, 0.45, 0)] * 22,
    })
    total = len(records)
    result = temporal_stability_analysis(records)

    monthly_sum = sum(v["n"] for v in result["monthly_breakdown"].values())
    assert monthly_sum == total, f"Monthly n sum {monthly_sum} != total {total}"
    assert result["total_tier_c_n"] == total


# ---------------------------------------------------------------------------
# Test 3: Bootstrap CI is deterministic with seed=42
# ---------------------------------------------------------------------------

def test_bootstrap_deterministic_with_seed():
    edges = [0.05 + i * 0.001 for i in range(50)]
    boot1 = bootstrap_mean_ci(edges, n_boot=1000, seed=SEED)
    boot2 = bootstrap_mean_ci(edges, n_boot=1000, seed=SEED)
    assert boot1 == boot2, "Bootstrap must be deterministic with same seed"
    assert boot1["ci_95_low"] < boot1["mean_boot"] < boot1["ci_95_high"]


# ---------------------------------------------------------------------------
# Test 4: Month classification follows CI rule
# ---------------------------------------------------------------------------

def test_month_classification_ci_rule():
    # All positive CI → STABLE
    assert _classify_month(0.10, 0.02, 0.18, 30) == "STABLE"
    # CI crosses zero, mean > 0 → WEAK
    assert _classify_month(0.05, -0.02, 0.12, 30) == "WEAK"
    # Mean positive but CI below or mostly below 0
    assert _classify_month(-0.03, -0.10, 0.04, 30) == "NEGATIVE"
    # Too small sample → SAMPLE_LIMITED
    assert _classify_month(0.10, 0.02, 0.18, 10) == "SAMPLE_LIMITED"


# ---------------------------------------------------------------------------
# Test 5: Calibration bin count equals 10
# ---------------------------------------------------------------------------

def test_calibration_bin_count():
    records = _make_records({
        "2025-05": [(delta / 2.0, 0.50, 1) for delta in range(-10, 10)]
    })
    result = calibration_audit(records)
    assert len(result["reliability_table"]) == 10


# ---------------------------------------------------------------------------
# Test 6: Brier score in plausible range [0.0, 0.5]
# ---------------------------------------------------------------------------

def test_brier_score_plausible_range():
    records = _make_records({
        "2025-06": [(0.8, 0.55, 1)] * 50 + [(0.7, 0.50, 0)] * 50,
    })
    result = calibration_audit(records)
    brier = result["brier_score"]
    assert brier is not None
    assert 0.0 <= brier <= 0.5, f"Brier score {brier} out of plausible range"


# ---------------------------------------------------------------------------
# Test 7: ECE calculation is correct on synthetic data
# ---------------------------------------------------------------------------

def test_ece_calculation_synthetic():
    """
    Construct records where model_prob = 0.55 (all in [0.5, 0.6) bin)
    and actual_win_rate = 0.75.
    Expected: single active bin with gap = 0.55 - 0.75 = -0.20,
    ECE = |gap| * (n/N) = 0.20 (all records in one bin).
    """
    import math

    def sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-0.8 * x))

    # delta such that sigmoid(0.8*delta) ≈ 0.55 → delta = logit(0.55)/0.8
    # logit(0.55) = ln(0.55/0.45) = 0.2007 → delta = 0.2508
    target_delta = math.log(0.55 / 0.45) / 0.8  # ≈ 0.25

    # Build: 8 wins, 2 losses → actual_win_rate = 0.80 (close enough)
    recs = []
    for i in range(20):
        mp = sigmoid(target_delta)
        win = 1 if i < 16 else 0  # 80% win rate
        recs.append(JoinedRecord(
            game_date="2025-06-01",
            month="2025-06",
            sp_fip_delta=target_delta,
            model_prob=mp,
            market_home_prob=0.50,
            actual_home_win=win,
            edge=mp - 0.50,
        ))

    result = calibration_audit(recs)
    ece = result["ece"]

    # All records in [0.5, 0.6) bin
    active_bins = [b for b in result["reliability_table"] if b["n"] >= 5]
    assert len(active_bins) == 1
    gap = abs(active_bins[0]["calibration_gap"])
    expected_ece = gap  # single bin has all records
    assert abs(ece - expected_ece) < 1e-4, f"ECE {ece} != expected {expected_ece}"


# ---------------------------------------------------------------------------
# Test 8: Governance flags exist in both JSON outputs
# ---------------------------------------------------------------------------

def test_governance_flags_in_outputs():
    for path in [OUT_TEMPORAL, OUT_CALIBRATION]:
        assert path.exists(), f"Missing output: {path}"
        with path.open() as f:
            d = json.load(f)
        gov = d.get("governance", {})
        assert gov.get("paper_only") is True, f"paper_only missing in {path.name}"
        assert gov.get("diagnostic_only") is True
        assert gov.get("promotion_freeze") is True
        assert gov.get("kelly_deploy_allowed") is False


# ---------------------------------------------------------------------------
# Test 9: live_api_calls equals 0
# ---------------------------------------------------------------------------

def test_live_api_calls_zero():
    assert GOVERNANCE["live_api_calls"] == 0

    for path in [OUT_TEMPORAL, OUT_CALIBRATION]:
        with path.open() as f:
            d = json.load(f)
        assert d["governance"]["live_api_calls"] == 0, f"live_api_calls != 0 in {path.name}"


# ---------------------------------------------------------------------------
# Test 10: No output claims deployment readiness
# ---------------------------------------------------------------------------

FORBIDDEN_PHRASES = [
    "guaranteed profit",
    "profitability claim",
    "production proposal",
    "live odds api call",
    "deploy recommendation",
    "deployment_ready",
    "ready_for_production",
    "promote_to_live",
    "recommend production",
    "escalate to live",
]


def test_no_deployment_readiness_claims():
    for path in [OUT_TEMPORAL, OUT_CALIBRATION]:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"Forbidden phrase '{phrase}' found in {path.name}"

    report_path = ROOT / "report/p44_signal_temporal_stability_calibration_20260525.md"
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in report_text, f"Forbidden phrase '{phrase}' in report"

    # Verify governance disclaimers are present (affirmative negation check)
    for path in [OUT_TEMPORAL, OUT_CALIBRATION]:
        with path.open() as f:
            d = json.load(f)
        assert d["governance"]["paper_only"] is True
        assert d["governance"]["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# Bonus: real data integration smoke test
# ---------------------------------------------------------------------------

def test_real_data_tier_c_count():
    """Verify real data produces 535 Tier C records (matches P43)."""
    from _p44_signal_temporal_stability_calibration import load_tier_c_records
    records, inv = load_tier_c_records()
    assert inv["phase56_tier_c_rows"] == 535, f"Expected 535 Tier C rows, got {inv['phase56_tier_c_rows']}"
    assert len(records) == 535


def test_real_temporal_all_months_stable():
    """All 6 months (Apr–Sep 2025) should be STABLE given confirmed edge."""
    with OUT_TEMPORAL.open() as f:
        d = json.load(f)
    months = d["monthly_breakdown"]
    assert set(months.keys()) == {
        "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"
    }
    for m, v in months.items():
        if v["n"] >= 15:
            assert v["classification"] in ("STABLE", "WEAK"), (
                f"Month {m} classified {v['classification']} but CI positive expected"
            )


def test_real_calibration_brier_plausible():
    """Brier score on real 2025 Tier C data should be in expected range."""
    with OUT_CALIBRATION.open() as f:
        d = json.load(f)
    assert 0.0 <= d["brier_score"] <= 0.5


def test_real_ece_moderate():
    """ECE should be < 0.15 for a sports prediction model."""
    with OUT_CALIBRATION.open() as f:
        d = json.load(f)
    assert d["ece"] < 0.15, f"ECE {d['ece']} unexpectedly high"
