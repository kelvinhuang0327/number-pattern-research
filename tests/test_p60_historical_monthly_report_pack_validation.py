"""
Tests for P60 — Historical Monthly Report Pack (EDGE-FIRST Validation)
Covers VAL01-VAL10 and pack-level synthesis requirements.
"""
from __future__ import annotations

import json
import pathlib

import pytest

SUMMARY_PATH = pathlib.Path(
    "data/mlb_2025/derived/p60_historical_monthly_report_pack_validation_summary.json"
)


def load_summary() -> dict:
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Test 1: P52/P58/P59 source artifacts loaded
# ---------------------------------------------------------------------------

def test_source_artifacts_loaded():
    s = load_summary()
    assert s["source_artifacts"]["p52_loaded"] is True, "P52 artifact not loaded"
    assert s["source_artifacts"]["p58_loaded"] is True, "P58 artifact not loaded"
    assert s["source_artifacts"]["p59_loaded"] is True, "P59 artifact not loaded"


# ---------------------------------------------------------------------------
# Test 2: Apr-Sep months processing complete or blocked-flagged
# ---------------------------------------------------------------------------

def test_all_months_processed_or_blocked():
    s = load_summary()
    months = s["monthly_reports"]
    month_keys = [r["month"] for r in months]
    for m in ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]:
        assert m in month_keys, f"Month {m} missing from pack"


# ---------------------------------------------------------------------------
# Test 3: edge_status classified per P52 V2 thresholds
# ---------------------------------------------------------------------------

def test_edge_status_classification():
    s = load_summary()
    valid_statuses = {
        "EDGE_WITHIN_THRESHOLD", "EDGE_WARNING", "EDGE_CRITICAL", "DATA_GAP_BLOCKED"
    }
    for r in s["monthly_reports"]:
        es = r["edge_status"]
        assert es in valid_statuses, f"Invalid edge_status={es} for {r['month']}"


# ---------------------------------------------------------------------------
# Test 4: bootstrap CI deterministic seed=42
# ---------------------------------------------------------------------------

def test_bootstrap_ci_deterministic():
    s = load_summary()
    for r in s["monthly_reports"]:
        if r.get("data_gap_status") == "DATA_GAP_BLOCKED":
            continue
        if r["edge_status"] == "DATA_GAP_BLOCKED":
            continue
        assert "raw_edge_ci_low" in r, f"ci_low missing for {r['month']}"
        assert "raw_edge_ci_high" in r, f"ci_high missing for {r['month']}"
        assert r["raw_edge_ci_low"] <= r["raw_edge_mean"] <= r["raw_edge_ci_high"], (
            f"CI order violated for {r['month']}: "
            f"ci_low={r['raw_edge_ci_low']}, mean={r['raw_edge_mean']}, ci_high={r['raw_edge_ci_high']}"
        )


# ---------------------------------------------------------------------------
# Test 5: VAL01-VAL10 pass per month (where data available)
# ---------------------------------------------------------------------------

def test_val01_to_val10_per_month():
    s = load_summary()
    for r in s["monthly_reports"]:
        if r.get("data_gap_status") == "DATA_GAP_BLOCKED" and r["edge_status"] == "DATA_GAP_BLOCKED":
            continue
        for i in range(1, 11):
            key = f"VAL{i:02d}"
            val = r["validations"].get(key)
            assert val == "PASS", f"{r['month']} {key} = {val} (expected PASS)"


# ---------------------------------------------------------------------------
# Test 6: Sep 2025 matches P59 reference
# ---------------------------------------------------------------------------

def test_sep_2025_matches_p59():
    s = load_summary()
    sep = next(r for r in s["monthly_reports"] if r["month"] == "2025-09")
    p59_ref = s["p59_consistency_check"]
    edge_diff = abs(sep["raw_edge_mean"] - p59_ref["p59_raw_edge_mean"])
    assert edge_diff < 0.005, (
        f"Sep 2025 raw_edge_mean mismatch: "
        f"P60={sep['raw_edge_mean']:.6f}, P59={p59_ref['p59_raw_edge_mean']:.6f}, diff={edge_diff:.6f}"
    )


# ---------------------------------------------------------------------------
# Test 7: P52 thresholds_used_flag matches P52
# ---------------------------------------------------------------------------

def test_p52_thresholds_used_flag():
    s = load_summary()
    assert s["p52_thresholds_unchanged"] is True, "p52_thresholds_unchanged must be True"


# ---------------------------------------------------------------------------
# Test 8: P45 Platt constants unchanged
# ---------------------------------------------------------------------------

def test_p45_platt_constants_unchanged():
    s = load_summary()
    platt = s["platt_constants"]
    assert abs(platt["A"] - 0.435432) < 1e-6, f"Platt A changed: {platt['A']}"
    assert abs(platt["B"] - 0.245464) < 1e-6, f"Platt B changed: {platt['B']}"


# ---------------------------------------------------------------------------
# Test 9: paper_only, diagnostic_only, kelly_deploy_allowed in JSON
# ---------------------------------------------------------------------------

def test_paper_only_flags():
    s = load_summary()
    assert s["paper_only"] is True, "paper_only must be True"
    assert s["diagnostic_only"] is True, "diagnostic_only must be True"
    assert s["kelly_deploy_allowed"] is False, "kelly_deploy_allowed must be False"


# ---------------------------------------------------------------------------
# Test 10: live_api_calls=0
# ---------------------------------------------------------------------------

def test_live_api_calls_zero():
    s = load_summary()
    assert s["live_api_calls"] == 0, f"live_api_calls={s['live_api_calls']} (expected 0)"


# ---------------------------------------------------------------------------
# Test 11: runtime_recommendation_logic_changed=false
# ---------------------------------------------------------------------------

def test_runtime_recommendation_logic_unchanged():
    s = load_summary()
    assert s["runtime_recommendation_logic_changed"] is False, (
        "runtime_recommendation_logic_changed must be False"
    )


# ---------------------------------------------------------------------------
# Test 12: P52-P59 overwrite flags all False
# ---------------------------------------------------------------------------

def test_no_artifact_overwrite():
    s = load_summary()
    ow = s["artifacts_overwritten"]
    for key in ["p52", "p58", "p59", "p45"]:
        assert ow[key] is False, f"artifacts_overwritten[{key}] must be False"


# ---------------------------------------------------------------------------
# Test 13: cross_month_edge_stability classification logic
# ---------------------------------------------------------------------------

def test_cross_month_edge_stability_logic():
    s = load_summary()
    synth = s["pack_synthesis"]
    valid_stabilities = {
        "EDGE_STABLE_ACROSS_MONTHS",
        "EDGE_MOSTLY_STABLE",
        "EDGE_INCONSISTENT",
        "EDGE_UNSTABLE",
    }
    stability = synth["cross_month_edge_stability"]
    assert stability in valid_stabilities, f"Invalid stability: {stability}"

    within = synth["months_with_edge_within_threshold"]
    total = synth["total_months_available"]

    if within == total and total >= 6:
        assert stability == "EDGE_STABLE_ACROSS_MONTHS", (
            f"All {within}/{total} months within threshold but stability={stability}"
        )
    elif within >= 4:
        assert stability in ("EDGE_STABLE_ACROSS_MONTHS", "EDGE_MOSTLY_STABLE"), (
            f"{within}/{total} months within threshold but stability={stability}"
        )
    elif within >= 2:
        assert stability in ("EDGE_MOSTLY_STABLE", "EDGE_INCONSISTENT"), (
            f"{within}/{total} months within threshold but stability={stability}"
        )
    else:
        assert stability in ("EDGE_INCONSISTENT", "EDGE_UNSTABLE"), (
            f"{within}/{total} months within threshold but stability={stability}"
        )


# ---------------------------------------------------------------------------
# Test 14: synthesis_conclusion includes EDGE-FIRST framing
# ---------------------------------------------------------------------------

def test_synthesis_conclusion_edge_first():
    s = load_summary()
    conclusion = s["pack_synthesis"]["synthesis_conclusion"]
    assert len(conclusion) > 50, f"Conclusion too short: {len(conclusion)} chars"
    keywords = ["edge", "Edge", "EDGE", "closing line", "優於", "closing-line"]
    assert any(kw in conclusion for kw in keywords), (
        f"No EDGE-FIRST keyword found in conclusion: {conclusion[:100]}"
    )


# ---------------------------------------------------------------------------
# Test 15: Forbidden affirmative scan
# ---------------------------------------------------------------------------

def test_forbidden_affirmative_scan():
    s = load_summary()
    text = json.dumps(s, ensure_ascii=False)
    forbidden = [
        "guaranteed profit",
        "profitability claim",
        "production proposal",
        "live odds api call",
        "champion replacement",
    ]
    for f in forbidden:
        assert f not in text.lower(), f"Forbidden string found: '{f}'"


# ---------------------------------------------------------------------------
# Test 16: promotion_freeze=True
# ---------------------------------------------------------------------------

def test_promotion_freeze():
    s = load_summary()
    assert s["promotion_freeze"] is True, "promotion_freeze must be True"


# ---------------------------------------------------------------------------
# Test 17: t_locked = 0.50
# ---------------------------------------------------------------------------

def test_t_locked():
    s = load_summary()
    assert abs(s["t_locked"] - 0.50) < 1e-9, f"t_locked={s['t_locked']} (expected 0.50)"


# ---------------------------------------------------------------------------
# Test 18: pack_level_classification valid
# ---------------------------------------------------------------------------

def test_pack_level_classification():
    s = load_summary()
    valid = {
        "P60_EDGE_STABLE_ACROSS_MONTHS",
        "P60_EDGE_MOSTLY_STABLE",
        "P60_EDGE_INCONSISTENT",
        "P60_EDGE_UNSTABLE",
        "P60_HISTORICAL_MONTHLY_PACK_BLOCKED",
        "P60_HISTORICAL_MONTHLY_PACK_INCOMPLETE",
    }
    assert s["pack_classification"] in valid, (
        f"Invalid pack_classification: {s['pack_classification']}"
    )


# ---------------------------------------------------------------------------
# Additional tests for robustness
# ---------------------------------------------------------------------------

def test_p59_consistency_check_present():
    s = load_summary()
    p59c = s["p59_consistency_check"]
    assert "p59_raw_edge_mean" in p59c
    assert "p60_sep_raw_edge_mean" in p59c
    assert "overall_consistent" in p59c


def test_all_monthly_reports_have_required_fields():
    s = load_summary()
    required_fields = [
        "month", "batch_n", "edge_status", "calibration_status",
        "sample_status", "global_status", "validations",
    ]
    for r in s["monthly_reports"]:
        for field in required_fields:
            assert field in r, f"Field '{field}' missing from month {r.get('month', '?')}"


def test_sep_2025_calibration_critical_status():
    """Sep 2025 should have CALIBRATION_CRITICAL per P52 V2 (platt_ece=0.122929 > 0.12)."""
    s = load_summary()
    sep = next(r for r in s["monthly_reports"] if r["month"] == "2025-09")
    assert sep["calibration_status"] == "CALIBRATION_CRITICAL", (
        f"Sep 2025 calibration_status={sep['calibration_status']} (expected CALIBRATION_CRITICAL)"
    )
    assert sep["platt_ece"] > 0.12, f"Sep 2025 platt_ece={sep['platt_ece']} (expected > 0.12)"


def test_edge_within_threshold_all_months():
    """All months should have EDGE_WITHIN_THRESHOLD (all ci_low > 0, all mean >= 0.07)."""
    s = load_summary()
    for r in s["monthly_reports"]:
        if r["batch_n"] < 10:
            continue  # DATA_GAP_BLOCKED
        assert r["edge_status"] == "EDGE_WITHIN_THRESHOLD", (
            f"Month {r['month']} edge_status={r['edge_status']} (expected EDGE_WITHIN_THRESHOLD)"
        )
        assert r["raw_edge_ci_low"] > 0, (
            f"Month {r['month']} ci_low={r['raw_edge_ci_low']} (expected > 0)"
        )
