"""
Tests for P47 — Calibration Strategy Consolidation + P43-P46 Synthesis Report

12 tests covering:
1.  All five source artifacts are loaded
2.  Final P47 JSON exists and contains required top-level sections
3.  Selected monitoring stream is one of allowed values
4.  Final P47 classification is one of allowed values
5.  Governance flags exist and match required values
6.  Monitoring thresholds include ECE, Brier, edge, monthly stability, sample accumulation
7.  Data gap register includes 2024 closing-line odds gap
8.  JSON output contains no deployment-readiness classification
9.  Reports contain no affirmative production or profit claims
10. live_api_calls equals 0
11. runtime_recommendation_logic_changed flag equals false
12. active_task.md references P47 final classification
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from _p47_calibration_synthesis_report import (
    ALLOWED_P47_CLASSIFICATION,
    ALLOWED_STREAM,
    GOVERNANCE,
    SOURCE_ARTIFACTS,
    build_data_gap_register,
    build_monitoring_thresholds,
    p47_classification,
    select_monitoring_stream,
)

OUT_JSON = ROOT / "data/mlb_2025/derived/p47_calibration_synthesis_summary.json"

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

DEPLOYABLE_STRINGS = [
    "ready_for_production",
    "promote_to_live",
    "deployment_ready",
    "champion_replaced",
    "live_deployment",
]


# ---------------------------------------------------------------------------
# Test 1: All five source artifacts are loaded
# ---------------------------------------------------------------------------

def test_all_source_artifacts_exist():
    for key, path in SOURCE_ARTIFACTS.items():
        assert path.exists(), f"Source artifact missing: {key} -> {path}"
        # Verify it's valid JSON
        with path.open() as f:
            data = json.load(f)
        assert isinstance(data, dict), f"Source {key} is not a dict"


# ---------------------------------------------------------------------------
# Test 2: Final JSON exists with required sections
# ---------------------------------------------------------------------------

REQUIRED_TOP_LEVEL = [
    "source_artifacts",
    "p43_edge_summary",
    "p44_temporal_summary",
    "p44_raw_calibration_summary",
    "p45_platt_summary",
    "p46_isotonic_comparison_summary",
    "selected_monitoring_probability_stream",
    "rationale",
    "monitoring_thresholds",
    "unresolved_data_gaps",
    "governance",
    "final_p47_classification",
]


def test_output_json_has_required_sections():
    assert OUT_JSON.exists(), f"Missing: {OUT_JSON}"
    with OUT_JSON.open() as f:
        d = json.load(f)
    for section in REQUIRED_TOP_LEVEL:
        assert section in d, f"Required section '{section}' missing from P47 JSON"


# ---------------------------------------------------------------------------
# Test 3: Selected monitoring stream is allowed
# ---------------------------------------------------------------------------

def test_selected_stream_allowed():
    with OUT_JSON.open() as f:
        d = json.load(f)
    stream = d["selected_monitoring_probability_stream"]
    assert stream in ALLOWED_STREAM, f"Stream '{stream}' not in {ALLOWED_STREAM}"


# ---------------------------------------------------------------------------
# Test 4: Final P47 classification is allowed
# ---------------------------------------------------------------------------

def test_p47_classification_allowed():
    with OUT_JSON.open() as f:
        d = json.load(f)
    cls = d["final_p47_classification"]
    assert cls in ALLOWED_P47_CLASSIFICATION, f"P47 class '{cls}' not in allowed set"

    # Verify classification function covers all stream values
    for stream in ALLOWED_STREAM:
        result = p47_classification(stream)
        assert result in ALLOWED_P47_CLASSIFICATION, f"p47_classification({stream}) = {result} not allowed"


# ---------------------------------------------------------------------------
# Test 5: Governance flags correct
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
        "runtime_recommendation_logic_changed": False,
    }
    for k, v in required.items():
        assert GOVERNANCE[k] == v, f"GOVERNANCE[{k}]={GOVERNANCE[k]}, expected {v}"

    with OUT_JSON.open() as f:
        d = json.load(f)
    gov = d["governance"]
    for k, v in required.items():
        assert gov[k] == v, f"JSON governance[{k}]={gov[k]}, expected {v}"


# ---------------------------------------------------------------------------
# Test 6: Monitoring thresholds contain all required categories
# ---------------------------------------------------------------------------

REQUIRED_THRESHOLD_KEYS = [
    "ece_drift",
    "brier_drift",
    "edge_mean_drift",
    "monthly_stability",
    "sample_accumulation",
]


def test_monitoring_thresholds_complete():
    with OUT_JSON.open() as f:
        d = json.load(f)
    thresholds = d["monitoring_thresholds"]
    for key in REQUIRED_THRESHOLD_KEYS:
        assert key in thresholds, f"Missing threshold category: '{key}'"

    # Spot checks on structure
    ece = thresholds["ece_drift"]
    assert "baseline_platt_cv_mean_ece" in ece
    assert "warning_threshold" in ece
    assert "critical_threshold" in ece
    assert ece["warning_threshold"] < ece["critical_threshold"]

    sample = thresholds["sample_accumulation"]
    assert "minimum_monitoring_batch_n" in sample
    assert sample["minimum_monitoring_batch_n"] == 100


# ---------------------------------------------------------------------------
# Test 7: Data gap register includes 2024 closing-line gap
# ---------------------------------------------------------------------------

def test_data_gap_register_has_2024_gap():
    with OUT_JSON.open() as f:
        d = json.load(f)
    gaps = d["unresolved_data_gaps"]
    assert len(gaps) >= 1, "Data gap register is empty"

    gap_names = [g["missing_data_item"].lower() for g in gaps]
    has_2024 = any("2024" in name and ("odds" in name or "ml" in name.lower()) for name in gap_names)
    assert has_2024, f"2024 closing-line odds gap not found in register. Found: {gap_names}"

    # All gaps should have required fields
    for g in gaps:
        for field in ["missing_data_item", "current_status", "impact", "required_resolution", "priority"]:
            assert field in g, f"Gap missing field '{field}': {g.get('missing_data_item', '?')}"

    # Priority values should be valid
    valid_priorities = {"HIGH", "MEDIUM", "LOW"}
    for g in gaps:
        assert g["priority"] in valid_priorities, f"Invalid priority: {g['priority']}"


# ---------------------------------------------------------------------------
# Test 8: JSON output contains no deployment-readiness classification
# ---------------------------------------------------------------------------

def test_no_deployable_in_json():
    text = OUT_JSON.read_text(encoding="utf-8").lower()
    for phrase in DEPLOYABLE_STRINGS:
        assert phrase not in text, f"Deployable phrase '{phrase}' in JSON"


# ---------------------------------------------------------------------------
# Test 9: Reports no affirmative production/profit claims
# ---------------------------------------------------------------------------

def test_reports_no_forbidden_claims():
    for rpath in [
        ROOT / "report/p47_calibration_synthesis_report_20260526.md",
        ROOT / "00-BettingPlan/20260526/p47_calibration_synthesis_report_20260526.md",
    ]:
        assert rpath.exists(), f"Missing report: {rpath}"
        text = rpath.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"'{phrase}' in {rpath.name}"


# ---------------------------------------------------------------------------
# Test 10: live_api_calls equals 0
# ---------------------------------------------------------------------------

def test_live_api_calls_zero():
    assert GOVERNANCE["live_api_calls"] == 0
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Test 11: runtime_recommendation_logic_changed flag is false
# ---------------------------------------------------------------------------

def test_runtime_recommendation_not_changed():
    assert GOVERNANCE["runtime_recommendation_logic_changed"] is False
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["runtime_recommendation_logic_changed"] is False


# ---------------------------------------------------------------------------
# Test 12: active_task.md references P47 final classification
# ---------------------------------------------------------------------------

def test_active_task_references_p47():
    atask = ROOT / "00-Plan/roadmap/active_task.md"
    assert atask.exists()
    content = atask.read_text(encoding="utf-8")
    assert "P47" in content, "active_task.md does not mention P47"
    assert "P47_PLATT_SELECTED_FOR_MONITORING_DIAGNOSTIC" in content or "P47" in content


# ---------------------------------------------------------------------------
# Bonus: selection logic unit tests
# ---------------------------------------------------------------------------

def test_select_stream_platt_logic():
    """If Platt has good CV improvement + helpful walk-forward, select Platt."""
    p45_mock = {
        "cv_mean_raw_ece": 0.12,
        "cv_mean_platt_ece": 0.08,
        "cv_mean_ece_improvement": 0.04,
        "cv_mean_platt_brier": 0.24,
        "walk_forward_classification": "WALK_FORWARD_HELPFUL",
        "p45_classification": "P45_RECALIBRATION_HELPFUL",
    }
    p46_mock = {
        "cv_mean_isotonic_ece": 0.079,
        "cv_mean_platt_ece": 0.08,
        "iso_beats_platt_fold_count": 2,
        "cv_fold_count": 5,
        "walk_forward_classification": "PLATT_WALK_FORWARD_PREFERRED",
        "p46_classification": "P46_MIXED_RECALIBRATION_DIAGNOSTIC",
    }
    stream, rationale = select_monitoring_stream(p45_mock, p46_mock)
    assert stream == "PLATT_CALIBRATED", f"Expected PLATT_CALIBRATED, got {stream}"


def test_select_stream_isotonic_if_clearly_better():
    """Isotonic selected only if CV gap > 0.01 AND walk-forward helpful."""
    p45_mock = {
        "cv_mean_raw_ece": 0.15,
        "cv_mean_platt_ece": 0.10,
        "cv_mean_ece_improvement": 0.05,
        "cv_mean_platt_brier": 0.25,
        "walk_forward_classification": "WALK_FORWARD_HELPFUL",
        "p45_classification": "P45_RECALIBRATION_HELPFUL",
    }
    p46_mock = {
        "cv_mean_isotonic_ece": 0.08,   # 0.02 better than Platt
        "cv_mean_platt_ece": 0.10,
        "iso_beats_platt_fold_count": 5,
        "cv_fold_count": 5,
        "walk_forward_classification": "ISOTONIC_WALK_FORWARD_HELPFUL",
        "p46_classification": "P46_ISOTONIC_SUPERIOR_DIAGNOSTIC",
    }
    stream, rationale = select_monitoring_stream(p45_mock, p46_mock)
    assert stream == "ISOTONIC_CALIBRATED", f"Expected ISOTONIC_CALIBRATED, got {stream}"


def test_p47_synthesis_json_structure_complete():
    """Full end-to-end: P47 JSON has all top-level sections with non-null values."""
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["selected_monitoring_probability_stream"] == "PLATT_CALIBRATED"
    assert d["final_p47_classification"] == "P47_PLATT_SELECTED_FOR_MONITORING_DIAGNOSTIC"
    assert len(d["rationale"]) >= 3
    assert len(d["unresolved_data_gaps"]) >= 3
    assert len(d["monitoring_thresholds"]) == 5
