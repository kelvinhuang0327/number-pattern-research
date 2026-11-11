"""
Tests for P84C — 2026 Canonical Prediction Partial Snapshot + Coverage Gap Audit
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True

Covers 45 test cases (T01–T45).
All tests read from pre-generated JSONL / JSON artifacts — no live API calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts._p84c_2026_partial_snapshot_coverage_audit import (
    ACTIVE_TASK_PATH,
    ALLOWED_CLASSIFICATIONS,
    FIP_PATH,
    GOVERNANCE,
    MODEL_PATH,
    OUTPUT_REPORT_PATH,
    OUTPUT_SUMMARY_PATH,
    P83E_SUMMARY_PATH,
    P84B_SUMMARY_PATH,
    PRED_PATH,
    REQUIRED_PRED_FIELDS,
    SCHEDULE_PATH,
    _load_jsonl,
    run,
    step1_verify_p84b_artifact,
    step2_validate_canonical_rows,
    step3_snapshot_metrics,
    step4_coverage_gap_audit,
    step5_remediation_path,
)


# ---------------------------------------------------------------------------
# Module-level fixture — runs once, produces all output artifacts
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p84c_result() -> dict:
    """Run P84C audit and return the result dict (idempotent)."""
    return run()


# ---------------------------------------------------------------------------
# T01 — P84B artifact loads
# ---------------------------------------------------------------------------

def test_t01_p84b_artifact_loads():
    """P84B summary JSON must exist and contain required keys."""
    assert P84B_SUMMARY_PATH.exists(), f"P84B summary not found: {P84B_SUMMARY_PATH}"
    d = json.loads(P84B_SUMMARY_PATH.read_text())
    assert "p84b_classification" in d
    assert "governance" in d
    assert "step2_schedule" in d
    assert "step3_pitcher_features" in d


# ---------------------------------------------------------------------------
# T02 — P84B classification verified
# ---------------------------------------------------------------------------

def test_t02_p84b_classification_verified():
    """step1_verify_p84b_artifact must confirm a valid P84B classification."""
    state = step1_verify_p84b_artifact()
    assert state["loaded"] is True
    assert state["ok"] is True
    assert state["p84b_classification"].startswith("P84B_"), (
        f"unexpected classification: {state['p84b_classification']!r}"
    )
    assert state["classification_ok"] is True


# ---------------------------------------------------------------------------
# T03 — P83E artifact loads
# ---------------------------------------------------------------------------

def test_t03_p83e_artifact_loads():
    """P83E summary JSON must exist and show CANONICAL_ROWS_READY."""
    assert P83E_SUMMARY_PATH.exists(), f"P83E summary not found: {P83E_SUMMARY_PATH}"
    d = json.loads(P83E_SUMMARY_PATH.read_text())
    assert "p83e_classification" in d
    assert d["p83e_classification"] == "P83E_CANONICAL_ROWS_READY"


# ---------------------------------------------------------------------------
# T04 — P83E canonical rows confirmed
# ---------------------------------------------------------------------------

def test_t04_p83e_canonical_rows_confirmed():
    """P83E summary must report rows_written=True and row_count > 0."""
    d = json.loads(P83E_SUMMARY_PATH.read_text())
    step6 = d.get("step6_canonical_rows", {})
    assert step6.get("rows_written") is True
    assert step6.get("row_count", 0) > 0


# ---------------------------------------------------------------------------
# T05 — Schedule JSONL exists
# ---------------------------------------------------------------------------

def test_t05_schedule_file_exists():
    """Schedule JSONL must exist and have rows."""
    assert SCHEDULE_PATH.exists(), f"Schedule file not found: {SCHEDULE_PATH}"
    rows = _load_jsonl(SCHEDULE_PATH)
    assert len(rows) > 0


# ---------------------------------------------------------------------------
# T06 — Predictions JSONL exists
# ---------------------------------------------------------------------------

def test_t06_predictions_file_exists():
    """Canonical prediction JSONL must exist and have rows."""
    assert PRED_PATH.exists(), f"Predictions file not found: {PRED_PATH}"
    rows = _load_jsonl(PRED_PATH)
    assert len(rows) > 0


# ---------------------------------------------------------------------------
# T07 — Required prediction fields present
# ---------------------------------------------------------------------------

def test_t07_required_prediction_fields():
    """Every canonical prediction row must have all REQUIRED_PRED_FIELDS."""
    rows = _load_jsonl(PRED_PATH)
    missing: list[str] = []
    for i, row in enumerate(rows):
        for field in REQUIRED_PRED_FIELDS:
            if field not in row:
                missing.append(f"row {i}: missing {field!r}")
    assert missing == [], f"Schema errors found: {missing[:5]}"


# ---------------------------------------------------------------------------
# T08 — No duplicate game_ids in prediction rows
# ---------------------------------------------------------------------------

def test_t08_no_duplicate_game_ids():
    """Canonical prediction rows must have unique game_id values."""
    rows = _load_jsonl(PRED_PATH)
    game_ids = [r["game_id"] for r in rows]
    duplicates = len(game_ids) - len(set(game_ids))
    assert duplicates == 0, f"{duplicates} duplicate game_ids found"


# ---------------------------------------------------------------------------
# T09 — Governance fields consistent in prediction rows
# ---------------------------------------------------------------------------

def test_t09_prediction_row_governance():
    """Every canonical row must have paper_only=True, diagnostic_only=True, production_ready=False."""
    rows = _load_jsonl(PRED_PATH)
    errors: list[str] = []
    for i, row in enumerate(rows):
        if row.get("paper_only") is not True:
            errors.append(f"row {i}: paper_only={row.get('paper_only')!r}")
        if row.get("diagnostic_only") is not True:
            errors.append(f"row {i}: diagnostic_only={row.get('diagnostic_only')!r}")
        if row.get("production_ready") is not False:
            errors.append(f"row {i}: production_ready={row.get('production_ready')!r}")
        if row.get("odds_used") is not False:
            errors.append(f"row {i}: odds_used={row.get('odds_used')!r}")
    assert errors == [], f"Governance errors: {errors[:5]}"


# ---------------------------------------------------------------------------
# T10 — abs_sp_fip_delta consistent
# ---------------------------------------------------------------------------

def test_t10_abs_sp_fip_delta_consistent():
    """abs_sp_fip_delta must equal abs(sp_fip_delta) for every row."""
    rows = _load_jsonl(PRED_PATH)
    errors: list[str] = []
    for i, row in enumerate(rows):
        expected = abs(row.get("sp_fip_delta", 0.0))
        actual   = row.get("abs_sp_fip_delta", 0.0)
        if abs(expected - actual) > 1e-6:
            errors.append(f"row {i}: expected {expected:.6f} got {actual:.6f}")
    assert errors == [], f"abs_sp_fip_delta mismatch: {errors[:5]}"


# ---------------------------------------------------------------------------
# T11 — model_probability in [0, 1]
# ---------------------------------------------------------------------------

def test_t11_model_probability_range():
    """All model_probability values must be in [0, 1]."""
    rows = _load_jsonl(PRED_PATH)
    bad = [
        (i, r["model_probability"])
        for i, r in enumerate(rows)
        if not (0 <= r.get("model_probability", -1) <= 1)
    ]
    assert bad == [], f"model_probability out of range: {bad[:5]}"


# ---------------------------------------------------------------------------
# T12 — predicted_side values are 'home' or 'away'
# ---------------------------------------------------------------------------

def test_t12_predicted_side_valid_values():
    """predicted_side must be 'home' or 'away' for every row."""
    rows = _load_jsonl(PRED_PATH)
    invalid = [
        (i, r["predicted_side"])
        for i, r in enumerate(rows)
        if r.get("predicted_side") not in ("home", "away")
    ]
    assert invalid == [], f"Invalid predicted_side values: {invalid[:5]}"


# ---------------------------------------------------------------------------
# T13 — season = 2026 for all rows
# ---------------------------------------------------------------------------

def test_t13_season_is_2026():
    """All canonical rows must have season=2026."""
    rows = _load_jsonl(PRED_PATH)
    wrong = [(i, r.get("season")) for i, r in enumerate(rows) if r.get("season") != 2026]
    assert wrong == [], f"Wrong season values: {wrong[:5]}"


# ---------------------------------------------------------------------------
# T14 — Rule flags are boolean
# ---------------------------------------------------------------------------

def test_t14_rule_flags_are_boolean():
    """rule_primary_125_flag, rule_shadow_100_flag, tier_b_candidate_flag, tier_a_watchlist_flag must be bool."""
    rows = _load_jsonl(PRED_PATH)
    flag_fields = [
        "rule_primary_125_flag",
        "rule_shadow_100_flag",
        "tier_b_candidate_flag",
        "tier_a_watchlist_flag",
    ]
    errors: list[str] = []
    for i, row in enumerate(rows):
        for f in flag_fields:
            val = row.get(f)
            if not isinstance(val, bool):
                errors.append(f"row {i}: {f}={val!r} (type {type(val).__name__})")
    assert errors == [], f"Non-bool flag values: {errors[:5]}"


# ---------------------------------------------------------------------------
# T15 — source_prediction_version correct
# ---------------------------------------------------------------------------

def test_t15_source_prediction_version():
    """All rows must have source_prediction_version='p84b_diagnostic_baseline_v1'."""
    rows = _load_jsonl(PRED_PATH)
    expected_version = "p84b_diagnostic_baseline_v1"
    wrong = [
        (i, r.get("source_prediction_version"))
        for i, r in enumerate(rows)
        if r.get("source_prediction_version") != expected_version
    ]
    assert wrong == [], f"Wrong version: {wrong[:5]}"


# ---------------------------------------------------------------------------
# T16 — total_canonical_rows = 828
# ---------------------------------------------------------------------------

def test_t16_total_canonical_rows(p84c_result):
    """Snapshot metrics must report total_canonical_rows=828."""
    step3 = p84c_result["step3_snapshot_metrics"]
    assert step3["total_canonical_rows"] == 828, (
        f"Expected 828, got {step3['total_canonical_rows']}"
    )


# ---------------------------------------------------------------------------
# T17 — schedule_coverage_rate ≈ 34.07%
# ---------------------------------------------------------------------------

def test_t17_schedule_coverage_rate(p84c_result):
    """Coverage rate must be 828/2430 ≈ 34.07%."""
    step4 = p84c_result["step4_coverage_gap_audit"]
    assert step4["schedule_total"] == 2430
    assert step4["canonical_rows"] == 828
    # Allow ±0.01% tolerance
    expected_pct = round(828 / 2430 * 100, 2)
    assert abs(step4["schedule_coverage_pct"] - expected_pct) < 0.02, (
        f"Expected ~{expected_pct}%, got {step4['schedule_coverage_pct']}%"
    )
    assert step4["coverage_below_50pct"] is True


# ---------------------------------------------------------------------------
# T18 — rows_by_month has March, April, May 2026
# ---------------------------------------------------------------------------

def test_t18_rows_by_month(p84c_result):
    """Monthly distribution must include 2026-03, 2026-04, 2026-05."""
    step3 = p84c_result["step3_snapshot_metrics"]
    monthly = step3["rows_by_month"]
    assert "2026-03" in monthly, "Missing 2026-03 in rows_by_month"
    assert "2026-04" in monthly, "Missing 2026-04 in rows_by_month"
    assert "2026-05" in monthly, "Missing 2026-05 in rows_by_month"
    total = sum(monthly.values())
    assert total == 828, f"Monthly total {total} != 828"


# ---------------------------------------------------------------------------
# T19 — primary_125_count > 0
# ---------------------------------------------------------------------------

def test_t19_primary_125_count(p84c_result):
    """At least one row must have rule_primary_125_flag=True."""
    step3 = p84c_result["step3_snapshot_metrics"]
    assert step3["primary_125_count"] > 0, "primary_125_count should be > 0"


# ---------------------------------------------------------------------------
# T20 — shadow_100_count > 0
# ---------------------------------------------------------------------------

def test_t20_shadow_100_count(p84c_result):
    """At least one row must have rule_shadow_100_flag=True."""
    step3 = p84c_result["step3_snapshot_metrics"]
    assert step3["shadow_100_count"] > 0, "shadow_100_count should be > 0"


# ---------------------------------------------------------------------------
# T21 — model_probability_distribution has required stats
# ---------------------------------------------------------------------------

def test_t21_model_probability_distribution(p84c_result):
    """model_probability_distribution must have min/max/mean/median/stdev."""
    step3 = p84c_result["step3_snapshot_metrics"]
    dist = step3["model_probability_distribution"]
    for stat in ("min", "max", "mean", "median", "stdev"):
        assert stat in dist, f"Missing stat: {stat!r}"
        assert isinstance(dist[stat], float), f"{stat} should be float"
    # Sanity: min <= mean <= max
    assert dist["min"] <= dist["mean"] <= dist["max"]
    # All probabilities in [0, 1]
    assert 0 <= dist["min"] <= 1
    assert 0 <= dist["max"] <= 1


# ---------------------------------------------------------------------------
# T22 — outcomes_available = False
# ---------------------------------------------------------------------------

def test_t22_outcomes_not_available(p84c_result):
    """outcomes_available must be False (no result data yet)."""
    step3 = p84c_result["step3_snapshot_metrics"]
    assert step3["outcomes_available"] is False


# ---------------------------------------------------------------------------
# T23 — actual_winner all None
# ---------------------------------------------------------------------------

def test_t23_actual_winner_all_none():
    """actual_winner field must be None for all 828 rows."""
    rows = _load_jsonl(PRED_PATH)
    non_none = [r.get("actual_winner") for r in rows if r.get("actual_winner") is not None]
    assert non_none == [], f"Expected all None, found {len(non_none)} non-None values"


# ---------------------------------------------------------------------------
# T24 — is_correct all None
# ---------------------------------------------------------------------------

def test_t24_is_correct_all_none():
    """is_correct field must be None for all rows."""
    rows = _load_jsonl(PRED_PATH)
    non_none = [r.get("is_correct") for r in rows if r.get("is_correct") is not None]
    assert non_none == [], f"Expected all None, found {len(non_none)} non-None values"


# ---------------------------------------------------------------------------
# T25 — Accuracy metrics blocked (hit_rate, AUC, Brier, ECE are None)
# ---------------------------------------------------------------------------

def test_t25_accuracy_metrics_blocked(p84c_result):
    """hit_rate, auc, brier_score, ece must be None — OUTCOMES_PENDING."""
    step3 = p84c_result["step3_snapshot_metrics"]
    for metric in ("hit_rate", "auc", "brier_score", "ece"):
        assert step3.get(metric) is None, (
            f"{metric} should be None (OUTCOMES_PENDING), got {step3.get(metric)!r}"
        )
    assert step3.get("accuracy_blocked_reason") == "OUTCOMES_PENDING"


# ---------------------------------------------------------------------------
# T26 — schedule_total = 2430
# ---------------------------------------------------------------------------

def test_t26_schedule_total(p84c_result):
    """Coverage gap audit must show schedule_total=2430."""
    step4 = p84c_result["step4_coverage_gap_audit"]
    assert step4["schedule_total"] == 2430


# ---------------------------------------------------------------------------
# T27 — fip_feature_ready + fip_feature_pending = 2430
# ---------------------------------------------------------------------------

def test_t27_fip_counts_sum_to_schedule(p84c_result):
    """FIP FEATURE_READY + FEATURE_PENDING must equal schedule_total (2430)."""
    step4 = p84c_result["step4_coverage_gap_audit"]
    total = step4["fip_feature_ready"] + step4["fip_feature_pending"]
    assert total == 2430, (
        f"FIP ready({step4['fip_feature_ready']}) + pending({step4['fip_feature_pending']}) = {total} != 2430"
    )


# ---------------------------------------------------------------------------
# T28 — model_derivable + model_pending = 2430
# ---------------------------------------------------------------------------

def test_t28_model_counts_sum_to_schedule(p84c_result):
    """Model DERIVABLE + MODEL_PENDING must equal schedule_total (2430)."""
    step4 = p84c_result["step4_coverage_gap_audit"]
    total = step4["model_derivable"] + step4["model_pending"]
    assert total == 2430, (
        f"Model derivable({step4['model_derivable']}) + pending({step4['model_pending']}) = {total} != 2430"
    )


# ---------------------------------------------------------------------------
# T29 — missing_schedule_to_fip = 1602
# ---------------------------------------------------------------------------

def test_t29_missing_schedule_to_fip(p84c_result):
    """1602 games must be missing from FIP FEATURE_READY coverage."""
    step4 = p84c_result["step4_coverage_gap_audit"]
    assert step4["missing_schedule_to_fip"] == 1602, (
        f"Expected 1602, got {step4['missing_schedule_to_fip']}"
    )


# ---------------------------------------------------------------------------
# T30 — missing_model_to_prediction = 0
# ---------------------------------------------------------------------------

def test_t30_missing_model_to_prediction(p84c_result):
    """All DERIVABLE model outputs must be represented in canonical predictions."""
    step4 = p84c_result["step4_coverage_gap_audit"]
    assert step4["missing_model_to_prediction"] == 0, (
        f"Expected 0 gap, got {step4['missing_model_to_prediction']}"
    )


# ---------------------------------------------------------------------------
# T31 — P84D recommendation present (coverage < 50%)
# ---------------------------------------------------------------------------

def test_t31_p84d_recommendation(p84c_result):
    """Step 5 must recommend P84D for pitcher coverage improvement."""
    step5 = p84c_result["step5_remediation_path"]
    recs = step5["recommendations"]
    phases = [r["phase"] for r in recs]
    assert "P84D" in phases, f"P84D not in recommendations: {phases}"
    p84d_rec = next(r for r in recs if r["phase"] == "P84D")
    assert "pitcher" in p84d_rec["recommendation"].lower() or "coverage" in p84d_rec["recommendation"].lower()


# ---------------------------------------------------------------------------
# T32 — P84E recommendation present (outcomes pending)
# ---------------------------------------------------------------------------

def test_t32_p84e_recommendation(p84c_result):
    """Step 5 must recommend P84E for outcome attachment."""
    step5 = p84c_result["step5_remediation_path"]
    recs = step5["recommendations"]
    phases = [r["phase"] for r in recs]
    assert "P84E" in phases, f"P84E not in recommendations: {phases}"
    p84e_rec = next(r for r in recs if r["phase"] == "P84E")
    assert "outcome" in p84e_rec["recommendation"].lower()


# ---------------------------------------------------------------------------
# T33 — paper_only = True in GOVERNANCE
# ---------------------------------------------------------------------------

def test_t33_governance_paper_only():
    """GOVERNANCE must have paper_only=True."""
    assert GOVERNANCE["paper_only"] is True


# ---------------------------------------------------------------------------
# T34 — diagnostic_only = True in GOVERNANCE
# ---------------------------------------------------------------------------

def test_t34_governance_diagnostic_only():
    """GOVERNANCE must have diagnostic_only=True."""
    assert GOVERNANCE["diagnostic_only"] is True


# ---------------------------------------------------------------------------
# T35 — production_ready = False in GOVERNANCE
# ---------------------------------------------------------------------------

def test_t35_governance_production_ready_false():
    """GOVERNANCE must have production_ready=False."""
    assert GOVERNANCE["production_ready"] is False


# ---------------------------------------------------------------------------
# T36 — live_api_calls = 0 in GOVERNANCE
# ---------------------------------------------------------------------------

def test_t36_governance_live_api_calls_zero():
    """GOVERNANCE must have live_api_calls=0."""
    assert GOVERNANCE["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# T37 — ev_calculated = False in GOVERNANCE
# ---------------------------------------------------------------------------

def test_t37_governance_no_ev():
    """GOVERNANCE must have ev_calculated=False."""
    assert GOVERNANCE["ev_calculated"] is False


# ---------------------------------------------------------------------------
# T38 — clv_calculated = False in GOVERNANCE
# ---------------------------------------------------------------------------

def test_t38_governance_no_clv():
    """GOVERNANCE must have clv_calculated=False."""
    assert GOVERNANCE["clv_calculated"] is False


# ---------------------------------------------------------------------------
# T39 — kelly_calculated = False in GOVERNANCE
# ---------------------------------------------------------------------------

def test_t39_governance_no_kelly():
    """GOVERNANCE must have kelly_calculated=False."""
    assert GOVERNANCE["kelly_calculated"] is False


# ---------------------------------------------------------------------------
# T40 — odds_used / uses_historical_odds = False in GOVERNANCE
# ---------------------------------------------------------------------------

def test_t40_governance_no_odds():
    """GOVERNANCE must have odds_used=False and uses_historical_odds=False."""
    assert GOVERNANCE["odds_used"] is False
    assert GOVERNANCE["uses_historical_odds"] is False
    assert GOVERNANCE["real_bet_allowed"] is False


# ---------------------------------------------------------------------------
# T41 — run() returns P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING
# ---------------------------------------------------------------------------

def test_t41_run_returns_correct_classification(p84c_result):
    """run() must return p84c_classification=P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING."""
    assert p84c_result["p84c_classification"] == "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING"
    assert p84c_result["p84c_classification"] in ALLOWED_CLASSIFICATIONS


# ---------------------------------------------------------------------------
# T42 — JSON summary written with correct structure
# ---------------------------------------------------------------------------

def test_t42_json_summary_written(p84c_result):
    """OUTPUT_SUMMARY_PATH must exist and contain all required top-level keys."""
    assert OUTPUT_SUMMARY_PATH.exists(), f"Summary not written: {OUTPUT_SUMMARY_PATH}"
    d = json.loads(OUTPUT_SUMMARY_PATH.read_text())
    required_keys = {
        "phase",
        "date",
        "generated_at",
        "p84c_classification",
        "allowed_classifications",
        "governance",
        "step1_p84b_verification",
        "step2_canonical_validation",
        "step3_snapshot_metrics",
        "step4_coverage_gap_audit",
        "step5_remediation_path",
        "forbidden_scan",
    }
    for k in required_keys:
        assert k in d, f"Missing top-level key: {k!r}"
    assert d["phase"] == "P84C"
    assert d["date"] == "2026-05-26"


# ---------------------------------------------------------------------------
# T43 — Report markdown written
# ---------------------------------------------------------------------------

def test_t43_report_written(p84c_result):
    """Markdown report must exist and contain key content."""
    assert OUTPUT_REPORT_PATH.exists(), f"Report not written: {OUTPUT_REPORT_PATH}"
    content = OUTPUT_REPORT_PATH.read_text()
    assert "P84C" in content
    assert "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING" in content
    assert "828" in content
    assert "34.07" in content
    assert "OUTCOMES_PENDING" in content
    assert "paper_only" in content


# ---------------------------------------------------------------------------
# T44 — active_task.md updated
# ---------------------------------------------------------------------------

def test_t44_active_task_updated(p84c_result):
    """active_task.md must reference P84C and P84B classifications."""
    assert ACTIVE_TASK_PATH.exists(), f"active_task.md not found: {ACTIVE_TASK_PATH}"
    content = ACTIVE_TASK_PATH.read_text()
    assert "P84C" in content, "active_task.md must mention P84C"
    assert "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING" in content, (
        "active_task.md must contain P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING"
    )
    assert "P84B_SCHEDULE_READY_PITCHER_MODEL_BLOCKED" in content, (
        "active_task.md must still reference P84B classification (history preserved)"
    )
    # All prior phases still preserved
    assert "P84A" in content
    assert "P83A" in content


# ---------------------------------------------------------------------------
# T45 — Regression: key modules importable
# ---------------------------------------------------------------------------

def test_t45_regression_key_modules_importable():
    """Regression: P72A–P84B key modules must remain importable."""
    from scripts._p84b_2026_public_stats_collector import (
        GOVERNANCE as G84B,
        ALLOWED_SOURCE_CLASSES,
    )
    assert G84B["paper_only"] is True
    assert "MLB_STATS_API_PUBLIC_SCHEDULE" in ALLOWED_SOURCE_CLASSES

    from scripts._p84a_2026_upstream_data_collector_contract import (
        GOVERNANCE as G84A,
    )
    assert G84A["paper_only"] is True
    assert G84A["production_ready"] is False

    from scripts._p83e_2026_canonical_prediction_row_producer import (
        GOVERNANCE as G83E,
        run_p83e_producer,
    )
    assert G83E["paper_only"] is True
    assert callable(run_p83e_producer)

    from scripts._p84c_2026_partial_snapshot_coverage_audit import (
        GOVERNANCE as G84C,
        ALLOWED_CLASSIFICATIONS as AC84C,
        run as run84c,
    )
    assert G84C["paper_only"] is True
    assert G84C["production_ready"] is False
    assert "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING" in AC84C
    assert callable(run84c)
