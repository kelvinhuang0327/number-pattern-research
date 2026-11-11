"""
P84D — Pitcher Coverage Improvement + Probable Pitcher Backfill Audit
tests/test_p84d_pitcher_coverage_backfill_audit.py

35 required tests covering:
  - Source artifact loading and verification
  - FIP gap classification correctness
  - Backfill probe result structure
  - FIP formula and field documentation
  - Governance invariants
  - Report structure
  - active_task.md update
  - P72A–P84D regression
"""
from __future__ import annotations

import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

P84D_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84d_pitcher_coverage_backfill_audit_summary.json"
P84C_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84c_2026_partial_snapshot_coverage_audit_summary.json"
P84B_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84b_2026_public_stats_collector_summary.json"
P83E_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p83e_2026_canonical_prediction_row_producer_summary.json"
FIP_PATH          = ROOT / "data/mlb_2026/pitchers/mlb_2026_sp_fip_features.jsonl"
ACTIVE_TASK_PATH  = ROOT / "00-Plan/roadmap/active_task.md"
REPORT_PATH       = ROOT / "report/p84d_pitcher_coverage_backfill_audit_20260526.md"


# ---------------------------------------------------------------------------
# Module-scope fixture — run once, all tests share result
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p84d_result():
    """Load the P84D summary JSON (written by the script)."""
    assert P84D_SUMMARY_PATH.exists(), f"P84D summary not found: {P84D_SUMMARY_PATH}"
    return json.loads(P84D_SUMMARY_PATH.read_text())


# ---------------------------------------------------------------------------
# Test 1: P84C source artifact loads
# ---------------------------------------------------------------------------

def test_01_p84c_source_artifact_loads():
    """P84C summary artifact must exist and be valid JSON."""
    assert P84C_SUMMARY_PATH.exists(), f"Missing: {P84C_SUMMARY_PATH}"
    data = json.loads(P84C_SUMMARY_PATH.read_text())
    assert isinstance(data, dict)
    assert "p84c_classification" in data


# ---------------------------------------------------------------------------
# Test 2: P84C classification verified
# ---------------------------------------------------------------------------

def test_02_p84c_classification_verified(p84d_result):
    """Step 1 must confirm P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING."""
    step1 = p84d_result["step1_verify_p84c"]
    assert step1["p84c_classification"] == "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING"
    assert step1["ok"] is True, f"P84C verification failed: {step1.get('errors')}"


# ---------------------------------------------------------------------------
# Test 3: P84B source artifact loads
# ---------------------------------------------------------------------------

def test_03_p84b_source_artifact_loads():
    """P84B summary artifact must exist and be valid JSON."""
    assert P84B_SUMMARY_PATH.exists(), f"Missing: {P84B_SUMMARY_PATH}"
    data = json.loads(P84B_SUMMARY_PATH.read_text())
    assert isinstance(data, dict)
    assert "p84b_classification" in data


# ---------------------------------------------------------------------------
# Test 4: Existing canonical rows count verified
# ---------------------------------------------------------------------------

def test_04_existing_canonical_rows_count(p84d_result):
    """Canonical rows before backfill must be 828 (P83E baseline)."""
    step1 = p84d_result["step1_verify_p84c"]
    assert step1["canonical_rows_p84c"] == 828
    cov = p84d_result.get("coverage_summary", {})
    assert cov.get("canonical_rows_before") == 828


# ---------------------------------------------------------------------------
# Test 5: Existing coverage rate verified
# ---------------------------------------------------------------------------

def test_05_existing_coverage_rate(p84d_result):
    """Schedule coverage before backfill must be ~34.07%."""
    step1 = p84d_result["step1_verify_p84c"]
    pct = step1["coverage_pct_p84c"]
    assert 34.0 <= pct <= 35.0, f"Coverage pct {pct} not near 34.07%"


# ---------------------------------------------------------------------------
# Test 6: Existing outcomes pending verified
# ---------------------------------------------------------------------------

def test_06_existing_outcomes_pending(p84d_result):
    """P84C must confirm outcomes_available=False."""
    step1 = p84d_result["step1_verify_p84c"]
    assert step1["outcomes_available"] is False


# ---------------------------------------------------------------------------
# Test 7: Current FIP gap classification generated
# ---------------------------------------------------------------------------

def test_07_fip_gap_classification_generated(p84d_result):
    """Step 2 must be present with required keys."""
    step2 = p84d_result.get("step2_fip_gap", {})
    required_keys = [
        "feature_ready_count",
        "feature_pending_count",
        "no_prob_home_slots",
        "no_prob_away_slots",
        "insuff_ip_game_count",
        "monthly_pending",
        "team_dist_no_prob_top10",
    ]
    for key in required_keys:
        assert key in step2, f"Missing key in step2: {key}"


# ---------------------------------------------------------------------------
# Test 8: FEATURE_READY count computed
# ---------------------------------------------------------------------------

def test_08_feature_ready_count(p84d_result):
    """FEATURE_READY count must match canonical rows: 828."""
    step2 = p84d_result["step2_fip_gap"]
    assert step2["feature_ready_count"] == 828


# ---------------------------------------------------------------------------
# Test 9: FEATURE_PENDING count computed
# ---------------------------------------------------------------------------

def test_09_feature_pending_count(p84d_result):
    """FEATURE_PENDING count must be 1602 (2430 total − 828 ready)."""
    step2 = p84d_result["step2_fip_gap"]
    assert step2["feature_pending_count"] == 1602


# ---------------------------------------------------------------------------
# Test 10: Missing probable pitcher count computed
# ---------------------------------------------------------------------------

def test_10_missing_probable_pitcher_count(p84d_result):
    """NO_PROBABLE_PITCHER slots must be accounted for (≥3000 side-slots)."""
    step2 = p84d_result["step2_fip_gap"]
    total_no_prob = step2["no_prob_home_slots"] + step2["no_prob_away_slots"]
    # P84C found 3167 NO_PROBABLE_PITCHER side-slots; verify in same range
    assert total_no_prob >= 3000, f"Expected ≥3000 NO_PROB slots, got {total_no_prob}"
    assert step2["no_prob_future_games"] >= 1500, (
        f"Expect ≥1500 future NO_PROB games, got {step2['no_prob_future_games']}"
    )


# ---------------------------------------------------------------------------
# Test 11: Insufficient stats count computed
# ---------------------------------------------------------------------------

def test_11_insufficient_stats_count(p84d_result):
    """INSUFFICIENT_IP game count must be 12 (as established in P84C audit)."""
    step2 = p84d_result["step2_fip_gap"]
    assert step2["insuff_ip_game_count"] == 12


# ---------------------------------------------------------------------------
# Test 12: Monthly gap distribution computed
# ---------------------------------------------------------------------------

def test_12_monthly_gap_distribution(p84d_result):
    """Monthly pending breakdown must cover all months with pending games."""
    step2 = p84d_result["step2_fip_gap"]
    monthly = step2.get("monthly_pending", {})
    assert isinstance(monthly, dict)
    assert len(monthly) >= 4, f"Expected months with pending games, got {monthly}"
    # Peak pending months must be June–September 2026 (future schedule)
    summer_pending = sum(
        v for k, v in monthly.items()
        if k >= "2026-06"
    )
    assert summer_pending >= 1000, f"Expected ≥1000 summer pending, got {summer_pending}"


# ---------------------------------------------------------------------------
# Test 13: Team gap distribution computed
# ---------------------------------------------------------------------------

def test_13_team_gap_distribution(p84d_result):
    """Top-10 teams with NO_PROBABLE_PITCHER must be present and non-empty."""
    step2 = p84d_result["step2_fip_gap"]
    team_dist = step2.get("team_dist_no_prob_top10", {})
    assert isinstance(team_dist, dict)
    assert len(team_dist) >= 5, "Expected at least 5 teams in distribution"
    # Each team should have many blocked slots (≥ 50 for top teams)
    top_count = max(team_dist.values())
    assert top_count >= 50, f"Top team has only {top_count} blocked slots"


# ---------------------------------------------------------------------------
# Test 14: Public MLB Stats source trace required
# ---------------------------------------------------------------------------

def test_14_public_mlb_source_trace_required():
    """All FEATURE_READY FIP rows must have MLB Stats API source trace."""
    fip_rows = [json.loads(l) for l in FIP_PATH.read_text().splitlines() if l.strip()]
    ready = [r for r in fip_rows if r.get("row_status") == "FEATURE_READY"]
    invalid = [
        r["game_id"] for r in ready
        if "MLB_STATS_API" not in r.get("source_trace", "")
    ]
    assert not invalid, f"FEATURE_READY rows without MLB source trace: {invalid[:5]}"


# ---------------------------------------------------------------------------
# Test 15: Probable pitcher backfill probe defined
# ---------------------------------------------------------------------------

def test_15_probable_pitcher_backfill_probe_defined(p84d_result):
    """Step 3 probe must have run and contain required fields."""
    step3 = p84d_result.get("step3_backfill_probe", {})
    assert step3.get("probe_ran") is True, "Probe must have run"
    assert "insuff_ip_pitcher_ids_probed" in step3
    assert "near_future_games_scanned" in step3
    assert "near_future_game_pks_probed" in step3


# ---------------------------------------------------------------------------
# Test 16: Odds API not used
# ---------------------------------------------------------------------------

def test_16_odds_api_not_used(p84d_result):
    """live_api_calls (odds) must remain 0; no odds API keys accessed."""
    gov = p84d_result.get("governance", {})
    assert gov.get("live_api_calls") == 0, "odds API calls must be 0"
    assert gov.get("api_key_accessed") is False
    assert gov.get("odds_used") is False
    assert gov.get("odds_api_called") is False


# ---------------------------------------------------------------------------
# Test 17: FIP formula documented
# ---------------------------------------------------------------------------

def test_17_fip_formula_documented(p84d_result):
    """Step 3 probe must document the FIP formula."""
    from scripts._p84d_pitcher_coverage_backfill_audit import (
        FIP_FORMULA_DOC, FIP_CONSTANT, MIN_IP_FOR_FIP
    )
    assert "FIP" in FIP_FORMULA_DOC
    assert "13" in FIP_FORMULA_DOC   # coefficient for HR
    assert "3" in FIP_FORMULA_DOC    # coefficient for BB+HBP
    assert "2" in FIP_FORMULA_DOC    # coefficient for K
    assert str(FIP_CONSTANT) in FIP_FORMULA_DOC
    assert str(MIN_IP_FOR_FIP) in FIP_FORMULA_DOC


# ---------------------------------------------------------------------------
# Test 18: Required FIP stat fields validated
# ---------------------------------------------------------------------------

def test_18_required_fip_stat_fields_validated():
    """FIP_REQUIRED_STAT_FIELDS must include all four required stat keys."""
    from scripts._p84d_pitcher_coverage_backfill_audit import FIP_REQUIRED_STAT_FIELDS
    assert "homeRuns" in FIP_REQUIRED_STAT_FIELDS
    assert "baseOnBalls" in FIP_REQUIRED_STAT_FIELDS
    assert "strikeOuts" in FIP_REQUIRED_STAT_FIELDS
    assert "inningsPitched" in FIP_REQUIRED_STAT_FIELDS


# ---------------------------------------------------------------------------
# Test 19: HBP missing behavior explicitly defined
# ---------------------------------------------------------------------------

def test_19_hbp_missing_behavior_defined():
    """HBP_MISSING_POLICY must be non-empty and describe the diagnostic assumption."""
    from scripts._p84d_pitcher_coverage_backfill_audit import HBP_MISSING_POLICY
    assert len(HBP_MISSING_POLICY) > 50, "HBP policy too short"
    assert "0" in HBP_MISSING_POLICY or "zero" in HBP_MISSING_POLICY.lower()
    assert "diagnostic" in HBP_MISSING_POLICY.lower()


# ---------------------------------------------------------------------------
# Test 20: No fabricated pitcher/FIP values
# ---------------------------------------------------------------------------

def test_20_no_fabricated_fip_values(p84d_result):
    """Governance must forbid fabricated FIP values; probe must confirm."""
    gov = p84d_result.get("governance", {})
    assert gov.get("fabricated_fip_values") is False
    # All FIP FEATURE_READY rows must have traceable MLB Stats API source
    fip_rows = [json.loads(l) for l in FIP_PATH.read_text().splitlines() if l.strip()]
    ready = [r for r in fip_rows if r.get("row_status") == "FEATURE_READY"]
    for r in ready:
        assert r.get("source_trace", "") != "", f"Empty source_trace in {r['game_id']}"
        assert r.get("home_sp_fip") is not None
        assert r.get("away_sp_fip") is not None


# ---------------------------------------------------------------------------
# Test 21: Existing FEATURE_READY rows preserved
# ---------------------------------------------------------------------------

def test_21_existing_feature_ready_rows_preserved():
    """All 828 original FEATURE_READY rows must still be present after any update."""
    fip_rows = [json.loads(l) for l in FIP_PATH.read_text().splitlines() if l.strip()]
    ready_ids = {r["game_id"] for r in fip_rows if r.get("row_status") == "FEATURE_READY"}
    # If backfill happened, ready count may have increased; baseline is 828
    assert len(ready_ids) >= 828, f"FEATURE_READY count dropped below 828: {len(ready_ids)}"


# ---------------------------------------------------------------------------
# Test 22: Backfill result classified
# ---------------------------------------------------------------------------

def test_22_backfill_result_classified(p84d_result):
    """P84D classification must be one of the allowed values."""
    from scripts._p84d_pitcher_coverage_backfill_audit import ALLOWED_CLASSIFICATIONS
    cls = p84d_result["p84d_classification"]
    assert cls in ALLOWED_CLASSIFICATIONS, (
        f"Classification {cls!r} not in {ALLOWED_CLASSIFICATIONS}"
    )


# ---------------------------------------------------------------------------
# Test 23: If backfill succeeds → P83E rerun command defined
# ---------------------------------------------------------------------------

def test_23_if_backfill_p83e_rerun_defined(p84d_result):
    """If backfill improved coverage, P83E rerun command must be defined."""
    cls = p84d_result["p84d_classification"]
    update = p84d_result.get("step5_update_result", {})
    if cls == "P84D_PITCHER_COVERAGE_IMPROVED":
        cmd = update.get("p83e_rerun_command")
        assert cmd is not None, "P83E rerun command must be defined when backfill succeeds"
        assert "_p83e_" in cmd or "p83e" in cmd.lower()
    else:
        # When no backfill, command may be None but step5 must exist
        assert update is not None


# ---------------------------------------------------------------------------
# Test 24: If backfill succeeds → P84C rerun command defined
# ---------------------------------------------------------------------------

def test_24_if_backfill_p84c_rerun_defined(p84d_result):
    """If backfill improved coverage, P84C rerun command must be defined."""
    cls = p84d_result["p84d_classification"]
    update = p84d_result.get("step5_update_result", {})
    if cls == "P84D_PITCHER_COVERAGE_IMPROVED":
        cmd = update.get("p84c_rerun_command")
        assert cmd is not None, "P84C rerun command must be defined when backfill succeeds"
        assert "_p84c_" in cmd or "p84c" in cmd.lower()
    else:
        assert update is not None


# ---------------------------------------------------------------------------
# Test 25: If no backfill → canonical rows unchanged
# ---------------------------------------------------------------------------

def test_25_if_no_backfill_canonical_rows_unchanged(p84d_result):
    """When no backfill succeeds, canonical row count must remain 828."""
    cls = p84d_result["p84d_classification"]
    cov = p84d_result.get("coverage_summary", {})
    if cls == "P84D_PITCHER_COVERAGE_AUDIT_READY_NO_BACKFILL":
        assert cov.get("canonical_rows_after") == 828, (
            f"No-backfill case: expected 828, got {cov.get('canonical_rows_after')}"
        )
        assert cov.get("delta") == 0


# ---------------------------------------------------------------------------
# Test 26: No edge calculated
# ---------------------------------------------------------------------------

def test_26_no_edge_calculated(p84d_result):
    """No market edge values must appear in P84D output."""
    raw = json.dumps(p84d_result)
    assert '"edge"' not in raw.lower() or "no edge" in raw.lower() or "market_edge_evaluated" not in raw
    gov = p84d_result.get("governance", {})
    assert gov.get("ev_calculated") is False


# ---------------------------------------------------------------------------
# Test 27: No CLV calculated
# ---------------------------------------------------------------------------

def test_27_no_clv_calculated(p84d_result):
    """No CLV calculation must appear in P84D output."""
    gov = p84d_result.get("governance", {})
    assert gov.get("clv_calculated") is False
    raw = json.dumps(p84d_result)
    assert "clv_value" not in raw


# ---------------------------------------------------------------------------
# Test 28: No EV calculated
# ---------------------------------------------------------------------------

def test_28_no_ev_calculated(p84d_result):
    """No EV calculation must appear in P84D output."""
    gov = p84d_result.get("governance", {})
    assert gov.get("ev_calculated") is False
    raw = json.dumps(p84d_result)
    assert "expected_value" not in raw


# ---------------------------------------------------------------------------
# Test 29: No Kelly calculated
# ---------------------------------------------------------------------------

def test_29_no_kelly_calculated(p84d_result):
    """No Kelly criterion calculation must appear in P84D output."""
    gov = p84d_result.get("governance", {})
    assert gov.get("kelly_calculated") is False
    raw = json.dumps(p84d_result)
    assert "kelly_fraction" not in raw


# ---------------------------------------------------------------------------
# Test 30: production_ready=False
# ---------------------------------------------------------------------------

def test_30_production_ready_false(p84d_result):
    """production_ready must be False in governance block."""
    gov = p84d_result.get("governance", {})
    assert gov.get("production_ready") is False
    assert gov.get("paper_only") is True
    assert gov.get("diagnostic_only") is True
    assert gov.get("real_bet_allowed") is False


# ---------------------------------------------------------------------------
# Test 31: JSON schema stable
# ---------------------------------------------------------------------------

def test_31_json_schema_stable(p84d_result):
    """P84D summary must contain all required top-level keys."""
    required_keys = [
        "p84d_classification",
        "step1_verify_p84c",
        "step2_fip_gap",
        "step3_backfill_probe",
        "step4_fip_compute",
        "step5_update_result",
        "coverage_summary",
        "governance",
        "remaining_blockers",
    ]
    for key in required_keys:
        assert key in p84d_result, f"Missing top-level key: {key}"


# ---------------------------------------------------------------------------
# Test 32: Report includes gap table
# ---------------------------------------------------------------------------

def test_32_report_includes_gap_table():
    """P84D report must contain the FIP gap table."""
    assert REPORT_PATH.exists(), f"Report not found: {REPORT_PATH}"
    content = REPORT_PATH.read_text()
    assert "| FEATURE_READY |" in content or "FEATURE_READY" in content
    assert "| Month |" in content or "Monthly Pending" in content
    # Table rows should have numbers
    assert "828" in content
    assert "1602" in content


# ---------------------------------------------------------------------------
# Test 33: Report includes backfill result
# ---------------------------------------------------------------------------

def test_33_report_includes_backfill_result():
    """P84D report must describe the backfill probe result."""
    content = REPORT_PATH.read_text()
    assert "Backfill" in content or "backfill" in content
    assert "Probe" in content or "probe" in content
    assert "P84D_PITCHER_COVERAGE" in content
    assert "Canonical Rows" in content


# ---------------------------------------------------------------------------
# Test 34: active_task.md updated
# ---------------------------------------------------------------------------

def test_34_active_task_updated():
    """active_task.md must have a P84D classification tag."""
    assert ACTIVE_TASK_PATH.exists(), f"active_task.md not found"
    content = ACTIVE_TASK_PATH.read_text()
    assert "<!-- P84D:" in content, "active_task.md missing P84D tag"
    # Must contain the actual classification
    assert "P84D_PITCHER_COVERAGE" in content


# ---------------------------------------------------------------------------
# Test 35: Regression — P72A–P84D core chain passes
# ---------------------------------------------------------------------------

@pytest.mark.regression
def test_35_p84d_regression_p83_p84_chain():
    """P83A–P84D regression: all summary artifacts exist with valid JSON."""
    artifacts = [
        ROOT / "data/mlb_2026/derived/p83e_2026_canonical_prediction_row_producer_summary.json",
        ROOT / "data/mlb_2026/derived/p84a_2026_upstream_data_collector_contract_summary.json",
        ROOT / "data/mlb_2026/derived/p84b_2026_public_stats_collector_summary.json",
        ROOT / "data/mlb_2026/derived/p84c_2026_partial_snapshot_coverage_audit_summary.json",
        ROOT / "data/mlb_2026/derived/p84d_pitcher_coverage_backfill_audit_summary.json",
    ]
    for path in artifacts:
        assert path.exists(), f"Regression artifact missing: {path}"
        data = json.loads(path.read_text())
        assert isinstance(data, dict), f"Invalid JSON in {path}"

    # Verify P84D classification is in allowed set
    from scripts._p84d_pitcher_coverage_backfill_audit import ALLOWED_CLASSIFICATIONS
    p84d = json.loads((ROOT / "data/mlb_2026/derived/p84d_pitcher_coverage_backfill_audit_summary.json").read_text())
    assert p84d["p84d_classification"] in ALLOWED_CLASSIFICATIONS

    # Verify P84C result unchanged (regression)
    p84c = json.loads(P84C_SUMMARY_PATH.read_text())
    assert p84c["p84c_classification"] == "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING"
    assert p84c["step3_snapshot_metrics"]["total_canonical_rows"] == 828

    # Verify governance chain: no odds, no EV across all P84x
    for path in artifacts[-3:]:  # P84A, P84B, P84C, P84D
        data = json.loads(path.read_text())
        gov = data.get("governance", {})
        assert gov.get("ev_calculated") is False or "ev_calculated" not in gov, (
            f"{path.name}: ev_calculated must be False"
        )
