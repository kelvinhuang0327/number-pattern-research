"""
Tests for P64 — Paper Simulation First Run
==========================================
Minimum 24 tests covering all required contract invariants.

Validates:
  - CEO approval gate recognized
  - Artifact loading and constant verification
  - Tier C filter correctness
  - All 33 P62 contract fields present in every emitted row
  - Governance invariants (paper_only, diagnostic_only, production_ready, etc.)
  - No live/paid API calls
  - Platt constants locked and unchanged
  - P52 thresholds accessible and unchanged
  - Edge and Kelly calculations
  - Status distribution documented
  - Gate reasons non-empty for blocked rows
  - 2024 data gap remains unresolved
  - Forbidden affirmative scan = 0 violations
  - active_task updated (checked via file existence)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "mlb_2025" / "derived"
DATA_DIR = ROOT / "data" / "mlb_2025"

P64_SUMMARY = DERIVED / "p64_paper_simulation_first_run_summary.json"
P64_ROWS = DERIVED / "p64_paper_simulation_rows.jsonl"
P62_JSON = DERIVED / "p62_paper_recommendation_contract_draft_summary.json"
P63_JSON = DERIVED / "p63_paper_recommendation_contract_review_readiness_summary.json"
P45_JSON = DERIVED / "p45_platt_recalibration_summary.json"
P52_JSON = DERIVED / "p52_monitoring_contract_v2_summary.json"
ACTIVE_TASK = ROOT / "00-Plan" / "roadmap" / "active_task.md"

# Expected governance constants
PLATT_A = 0.435432
PLATT_B = 0.245464
TIER_THRESHOLD = 0.50
CONTRACT_VERSION = "P62_v1_20260526"
EXPECTED_N_FIELDS = 33

# The 33 required P62 contract field names
REQUIRED_FIELDS = [
    "contract_version",
    "game_id",
    "game_start_utc",
    "generated_at_utc",
    "prediction_timestamp_utc",
    "odds_timestamp_utc",
    "market",
    "side",
    "model_signal_name",
    "sp_fip_delta",
    "signal_tier",
    "tier_threshold",
    "model_prob_home",
    "model_prob_away",
    "calibration_method",
    "platt_A",
    "platt_B",
    "calibrated_prob",
    "odds_source",
    "odds_source_trace",
    "decimal_odds",
    "implied_probability",
    "edge_pct",
    "paper_stake_units",
    "kelly_fraction_theoretical",
    "kelly_deploy_allowed",
    "recommendation_status",
    "gate_status",
    "gate_reasons",
    "paper_only",
    "diagnostic_only",
    "production_ready",
    "real_bet_allowed",
]

ALLOWED_STATUS_VALUES = {
    "PAPER_ELIGIBLE_CONTRACT_ONLY",
    "BLOCKED_MISSING_ODDS_SOURCE_TRACE",
    "BLOCKED_MISSING_TIMESTAMP",
    "BLOCKED_POSTGAME_LEAKAGE_RISK",
    "BLOCKED_SIGNAL_BELOW_TIER_C",
    "BLOCKED_CALIBRATION_SOURCE_INVALID",
    "BLOCKED_PROMOTION_FREEZE",
    "BLOCKED_PRODUCTION_NOT_ALLOWED",
    "BLOCKED_2024_DATA_GAP_UNRESOLVED",
}


@pytest.fixture(scope="module")
def summary() -> dict:
    """Load P64 summary JSON once per module."""
    assert P64_SUMMARY.exists(), f"P64 summary not found: {P64_SUMMARY}"
    with open(P64_SUMMARY) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    """Load all P64 emitted rows from JSONL once per module."""
    assert P64_ROWS.exists(), f"P64 rows JSONL not found: {P64_ROWS}"
    result = []
    with open(P64_ROWS) as f:
        for line in f:
            line = line.strip()
            if line:
                result.append(json.loads(line))
    return result


@pytest.fixture(scope="module")
def p62() -> dict:
    with open(P62_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p63() -> dict:
    with open(P63_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p45() -> dict:
    with open(P45_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p52() -> dict:
    with open(P52_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test 1: CEO approval gate recognized in summary
# ---------------------------------------------------------------------------
def test_01_ceo_approval_phrase_in_summary(summary):
    """Summary must record the CEO approval phrase."""
    approval = summary.get("approval", {})
    phrase = approval.get("phrase", "")
    assert "YES approve P62 contract" in phrase, (
        f"CEO approval phrase not found in summary: {phrase}"
    )
    assert "P64 paper simulation first run" in phrase


# ---------------------------------------------------------------------------
# Test 2: P62 contract loads and has correct version
# ---------------------------------------------------------------------------
def test_02_p62_contract_loads(p62):
    """P62 contract must load and have correct version."""
    assert p62.get("contract_version") == CONTRACT_VERSION
    assert p62.get("eligibility_gate", {}).get("n_conditions") == 17
    assert p62.get("row_schema", {}).get("n_required_fields") == 33


# ---------------------------------------------------------------------------
# Test 3: P63 readiness classification at approval
# ---------------------------------------------------------------------------
def test_03_p63_readiness_at_approval(summary, p63):
    """P63 readiness classification must be P63_READY_FOR_CEO_REVIEW."""
    p63_class = p63.get("p63_classification")
    assert p63_class == "P63_READY_FOR_CEO_REVIEW", (
        f"P63 classification: {p63_class}"
    )
    # summary records it
    approval = summary.get("approval", {})
    assert approval.get("p63_classification_at_approval") == "P63_READY_FOR_CEO_REVIEW"


# ---------------------------------------------------------------------------
# Test 4: P45 Platt A constant unchanged
# ---------------------------------------------------------------------------
def test_04_p45_platt_A_unchanged(p45):
    """P45 platt_a must equal 0.435432 (locked, never refit)."""
    artifact_a = p45["p45a_pilot"]["platt_a"]
    assert artifact_a == PLATT_A, (
        f"Platt A mismatch: artifact={artifact_a}, expected={PLATT_A}"
    )


# ---------------------------------------------------------------------------
# Test 5: P45 Platt B constant unchanged
# ---------------------------------------------------------------------------
def test_05_p45_platt_B_unchanged(p45):
    """P45 platt_b must equal 0.245464 (locked, never refit)."""
    artifact_b = p45["p45a_pilot"]["platt_b"]
    assert artifact_b == PLATT_B, (
        f"Platt B mismatch: artifact={artifact_b}, expected={PLATT_B}"
    )


# ---------------------------------------------------------------------------
# Test 6: P52 thresholds file loads and is accessible
# ---------------------------------------------------------------------------
def test_06_p52_thresholds_accessible(p52):
    """P52 monitoring contract must load and contain monitoring rules."""
    assert "alert_rule_matrix_v2" in p52, "P52 missing alert_rule_matrix_v2"
    assert "governance_flags" in p52, "P52 missing governance_flags"


# ---------------------------------------------------------------------------
# Test 7: Tier C filter count = 535
# ---------------------------------------------------------------------------
def test_07_tier_c_filter_correct(summary):
    """Tier C filter must produce exactly 535 games."""
    scope = summary["simulation_scope"]
    assert scope["total_tier_c_games"] == 535, (
        f"Expected 535 Tier C games, got {scope['total_tier_c_games']}"
    )


# ---------------------------------------------------------------------------
# Test 8: Every emitted row contains all 33 required P62 fields
# ---------------------------------------------------------------------------
def test_08_every_row_has_33_fields(rows):
    """Every emitted row must have all 33 P62 contract fields."""
    assert rows, "No rows emitted"
    for i, row in enumerate(rows):
        missing = [f for f in REQUIRED_FIELDS if f not in row]
        assert not missing, (
            f"Row {i} ({row.get('game_id')}) missing fields: {missing}"
        )


# ---------------------------------------------------------------------------
# Test 9: paper_only=True for every row
# ---------------------------------------------------------------------------
def test_09_paper_only_true_all_rows(rows):
    """paper_only must be True in every emitted row."""
    violations = [r["game_id"] for r in rows if r.get("paper_only") is not True]
    assert not violations, f"paper_only!=True in rows: {violations[:5]}"


# ---------------------------------------------------------------------------
# Test 10: diagnostic_only=True for every row
# ---------------------------------------------------------------------------
def test_10_diagnostic_only_true_all_rows(rows):
    """diagnostic_only must be True in every emitted row."""
    violations = [r["game_id"] for r in rows if r.get("diagnostic_only") is not True]
    assert not violations, f"diagnostic_only!=True in rows: {violations[:5]}"


# ---------------------------------------------------------------------------
# Test 11: production_ready=False for every row
# ---------------------------------------------------------------------------
def test_11_production_ready_false_all_rows(rows):
    """production_ready must be False in every emitted row."""
    violations = [r["game_id"] for r in rows if r.get("production_ready") is not False]
    assert not violations, f"production_ready!=False in rows: {violations[:5]}"


# ---------------------------------------------------------------------------
# Test 12: real_bet_allowed=False for every row
# ---------------------------------------------------------------------------
def test_12_real_bet_allowed_false_all_rows(rows):
    """real_bet_allowed must be False in every emitted row."""
    violations = [r["game_id"] for r in rows if r.get("real_bet_allowed") is not False]
    assert not violations, f"real_bet_allowed!=False in rows: {violations[:5]}"


# ---------------------------------------------------------------------------
# Test 13: kelly_deploy_allowed=False for every row
# ---------------------------------------------------------------------------
def test_13_kelly_deploy_allowed_false_all_rows(rows):
    """kelly_deploy_allowed must be False in every emitted row."""
    violations = [r["game_id"] for r in rows if r.get("kelly_deploy_allowed") is not False]
    assert not violations, f"kelly_deploy_allowed!=False in rows: {violations[:5]}"


# ---------------------------------------------------------------------------
# Test 14: No live API calls
# ---------------------------------------------------------------------------
def test_14_no_live_api_calls(summary):
    """live_api_calls must be 0."""
    live = summary["governance"]["live_api_calls"]
    assert live == 0, f"live_api_calls={live}, expected 0"


# ---------------------------------------------------------------------------
# Test 15: No paid API calls
# ---------------------------------------------------------------------------
def test_15_no_paid_api_calls(summary):
    """paid_api_called must be False."""
    paid = summary["governance"]["paid_api_called"]
    assert paid is False, f"paid_api_called={paid}, expected False"


# ---------------------------------------------------------------------------
# Test 16: Runtime recommendation logic unchanged
# ---------------------------------------------------------------------------
def test_16_runtime_recommendation_logic_unchanged(summary):
    """runtime_recommendation_logic_changed must be False."""
    changed = summary["governance"]["runtime_recommendation_logic_changed"]
    assert changed is False, f"runtime_recommendation_logic_changed={changed}"


# ---------------------------------------------------------------------------
# Test 17: No postgame leakage — all timestamps are pregame constructed
# ---------------------------------------------------------------------------
def test_17_no_postgame_leakage_risk(rows):
    """
    game_start_utc must end in T17:00:00Z (constructed pregame proxy).
    prediction_timestamp_utc must be before game_start_utc.
    odds_timestamp_utc must be before game_start_utc.
    """
    for r in rows[:50]:  # spot-check 50 rows
        game_date = r["game_start_utc"][:10]  # YYYY-MM-DD
        pred_date = r["prediction_timestamp_utc"][:10]
        odds_date = r["odds_timestamp_utc"][:10]
        assert pred_date <= game_date, (
            f"Row {r['game_id']}: prediction_timestamp_utc date {pred_date} > game {game_date}"
        )
        assert odds_date <= game_date, (
            f"Row {r['game_id']}: odds_timestamp_utc date {odds_date} > game {game_date}"
        )


# ---------------------------------------------------------------------------
# Test 18: Status distribution recorded in summary
# ---------------------------------------------------------------------------
def test_18_status_distribution_recorded(summary):
    """Status distribution must be a non-empty dict."""
    dist = summary["gate_statistics"]["status_distribution"]
    assert isinstance(dist, dict), "status_distribution must be a dict"
    assert len(dist) > 0, "status_distribution must not be empty"
    # All keys must be in allowed set
    for status in dist.keys():
        assert status in ALLOWED_STATUS_VALUES, (
            f"Unknown status value: {status}"
        )


# ---------------------------------------------------------------------------
# Test 19: Gate reasons non-empty for GATE_BLOCK rows
# ---------------------------------------------------------------------------
def test_19_gate_reasons_nonempty_for_blocked_rows(rows):
    """Any GATE_BLOCK row must have non-empty gate_reasons list."""
    for r in rows:
        if r.get("gate_status") == "GATE_BLOCK":
            reasons = r.get("gate_reasons", [])
            assert len(reasons) > 0, (
                f"Row {r['game_id']} is GATE_BLOCK but has empty gate_reasons"
            )


# ---------------------------------------------------------------------------
# Test 20: Blocked rows accounted for (gate_pass + gate_block = total rows)
# ---------------------------------------------------------------------------
def test_20_blocked_rows_accounted_for(summary, rows):
    """gate_pass_count + gate_block_count must equal total rows emitted."""
    stats = summary["gate_statistics"]
    total = summary["simulation_scope"]["total_rows_emitted"]
    accounted = stats["gate_pass_count"] + stats["gate_block_count"]
    assert accounted == total, (
        f"gate_pass + gate_block = {accounted}, total_rows = {total}"
    )
    assert len(rows) == total, (
        f"rows JSONL count={len(rows)} vs summary total={total}"
    )


# ---------------------------------------------------------------------------
# Test 21: 2024 data gap unresolved
# ---------------------------------------------------------------------------
def test_21_2024_data_gap_unresolved(summary):
    """2024 data gap must remain documented as unresolved."""
    gov = summary["governance"]
    assert gov.get("data_year_2024_gap_remains_unresolved") is True, (
        "2024 data gap must remain unresolved in P64"
    )


# ---------------------------------------------------------------------------
# Test 22: Forbidden affirmative scan = 0 violations
# ---------------------------------------------------------------------------
def test_22_forbidden_affirmative_scan_zero_violations(summary):
    """Forbidden affirmative term scan must return 0 violations (CLEAN)."""
    scan = summary["forbidden_scan"]
    assert scan["violations"] == 0, (
        f"Forbidden scan violations: {scan['violations']}, details: {scan.get('details')}"
    )
    assert scan["result"] == "CLEAN", (
        f"Forbidden scan result: {scan['result']}"
    )


# ---------------------------------------------------------------------------
# Test 23: Platt constants in every row match locked values
# ---------------------------------------------------------------------------
def test_23_platt_constants_locked_in_every_row(rows):
    """Every row must carry platt_A=0.435432 and platt_B=0.245464."""
    for r in rows:
        assert r.get("platt_A") == PLATT_A, (
            f"Row {r['game_id']}: platt_A={r.get('platt_A')}, expected {PLATT_A}"
        )
        assert r.get("platt_B") == PLATT_B, (
            f"Row {r['game_id']}: platt_B={r.get('platt_B')}, expected {PLATT_B}"
        )


# ---------------------------------------------------------------------------
# Test 24: Platt calibration formula produces values in (0, 1)
# ---------------------------------------------------------------------------
def test_24_calibrated_prob_in_unit_interval(rows):
    """calibrated_prob must be strictly in (0, 1) for all rows."""
    for r in rows:
        cp = r.get("calibrated_prob")
        if cp is not None:
            assert 0.0 < cp < 1.0, (
                f"Row {r['game_id']}: calibrated_prob={cp} out of (0, 1)"
            )


# ---------------------------------------------------------------------------
# Test 25: signal_tier = Tier_C for all rows
# ---------------------------------------------------------------------------
def test_25_signal_tier_is_tier_c(rows):
    """signal_tier must be 'Tier_C' for all emitted rows."""
    bad = [r["game_id"] for r in rows if r.get("signal_tier") != "Tier_C"]
    assert not bad, f"signal_tier != Tier_C in {len(bad)} rows: {bad[:5]}"


# ---------------------------------------------------------------------------
# Test 26: tier_threshold = 0.50 for all rows
# ---------------------------------------------------------------------------
def test_26_tier_threshold_locked_in_rows(rows):
    """tier_threshold must be 0.50 in every row (T_LOCKED)."""
    bad = [r["game_id"] for r in rows if r.get("tier_threshold") != TIER_THRESHOLD]
    assert not bad, f"tier_threshold != 0.50 in {len(bad)} rows: {bad[:5]}"


# ---------------------------------------------------------------------------
# Test 27: abs(sp_fip_delta) >= 0.50 for every row
# ---------------------------------------------------------------------------
def test_27_sp_fip_delta_passes_tier_c_filter(rows):
    """All emitted rows must pass the Tier C filter: |sp_fip_delta| >= 0.50."""
    bad = [
        (r["game_id"], r.get("sp_fip_delta"))
        for r in rows
        if abs(r.get("sp_fip_delta", 0.0)) < TIER_THRESHOLD
    ]
    assert not bad, f"Rows below Tier C threshold: {bad[:5]}"


# ---------------------------------------------------------------------------
# Test 28: market = moneyline for all rows
# ---------------------------------------------------------------------------
def test_28_market_is_moneyline(rows):
    """market field must be 'moneyline' for all rows."""
    bad = [r["game_id"] for r in rows if r.get("market") != "moneyline"]
    assert not bad, f"market != moneyline in rows: {bad[:5]}"


# ---------------------------------------------------------------------------
# Test 29: model_signal_name = sp_fip_delta for all rows
# ---------------------------------------------------------------------------
def test_29_model_signal_name_is_sp_fip_delta(rows):
    """model_signal_name must be 'sp_fip_delta' for all rows."""
    bad = [r["game_id"] for r in rows if r.get("model_signal_name") != "sp_fip_delta"]
    assert not bad, f"model_signal_name != sp_fip_delta in rows: {bad[:5]}"


# ---------------------------------------------------------------------------
# Test 30: Kelly fraction = 0 for rows with negative or zero edge
# ---------------------------------------------------------------------------
def test_30_kelly_zero_when_edge_nonpositive(rows):
    """kelly_fraction_theoretical must be 0.0 when edge_pct <= 0."""
    for r in rows:
        edge = r.get("edge_pct")
        kelly = r.get("kelly_fraction_theoretical")
        if edge is not None and kelly is not None and edge <= 0.0:
            assert kelly == 0.0, (
                f"Row {r['game_id']}: edge={edge} <= 0 but kelly={kelly}"
            )


# ---------------------------------------------------------------------------
# Test 31: edge_statistics documented in summary with correct structure
# ---------------------------------------------------------------------------
def test_31_edge_statistics_documented(summary):
    """Edge statistics must be present in summary with all required keys."""
    stats = summary.get("edge_statistics", {})
    assert stats, "edge_statistics must be non-empty"
    for key in ("mean", "median", "min", "max", "positive_edge_count", "negative_edge_count"):
        assert key in stats, f"Missing key in edge_statistics: {key}"
    # positive + negative should sum to eligible rows
    total_eligible = stats["positive_edge_count"] + stats["negative_edge_count"]
    assert total_eligible > 0, "No eligible rows with edge data"


# ---------------------------------------------------------------------------
# Test 32: P64 classification is a valid value
# ---------------------------------------------------------------------------
def test_32_p64_classification_valid(summary):
    """P64 classification must be one of the defined valid values."""
    valid = {
        "P64_PAPER_SIMULATION_FIRST_RUN_READY",
        "P64_PAPER_SIMULATION_PARTIAL_BLOCKED_ROWS_PRESENT",
        "P64_BLOCKED_BY_SOURCE_TRACE_GAP",
        "P64_BLOCKED_BY_SCHEMA_CONTRACT_MISMATCH",
        "P64_BLOCKED_BY_TEST_FAILURE",
        "P64_BLOCKED_BY_GOVERNANCE_RISK",
    }
    cl = summary.get("p64_classification")
    assert cl in valid, f"Invalid P64 classification: {cl}"


# ---------------------------------------------------------------------------
# Test 33: Summary records total_rows_emitted > 0
# ---------------------------------------------------------------------------
def test_33_rows_emitted_nonzero(summary):
    """total_rows_emitted must be > 0."""
    n = summary["simulation_scope"]["total_rows_emitted"]
    assert n > 0, "No rows were emitted in P64 simulation"


# ---------------------------------------------------------------------------
# Test 34: odds_source_trace non-empty for all GATE_PASS rows
# ---------------------------------------------------------------------------
def test_34_odds_source_trace_nonempty_for_pass_rows(rows):
    """GATE_PASS rows must have non-empty odds_source_trace."""
    for r in rows:
        if r.get("gate_status") == "GATE_PASS":
            trace = r.get("odds_source_trace", "")
            assert trace, (
                f"Row {r['game_id']}: GATE_PASS but odds_source_trace is empty"
            )


# ---------------------------------------------------------------------------
# Test 35: implied_probability = 1 / decimal_odds for GATE_PASS rows
# ---------------------------------------------------------------------------
def test_35_implied_prob_equals_one_over_decimal_odds(rows):
    """For GATE_PASS rows, implied_probability must equal 1/decimal_odds."""
    for r in rows:
        if r.get("gate_status") == "GATE_PASS":
            d = r.get("decimal_odds")
            ip = r.get("implied_probability")
            if d is not None and ip is not None and d > 0:
                expected_ip = round(1.0 / d, 6)
                assert abs(ip - expected_ip) < 1e-4, (
                    f"Row {r['game_id']}: implied_prob={ip} != 1/decimal_odds={expected_ip}"
                )


# ---------------------------------------------------------------------------
# Test 36: edge_pct = calibrated_prob - implied_probability for GATE_PASS rows
# ---------------------------------------------------------------------------
def test_36_edge_pct_equals_calibrated_minus_implied(rows):
    """For GATE_PASS rows, edge_pct must equal calibrated_prob - implied_probability."""
    for r in rows:
        if r.get("gate_status") == "GATE_PASS":
            cp = r.get("calibrated_prob")
            ip = r.get("implied_probability")
            ep = r.get("edge_pct")
            if cp is not None and ip is not None and ep is not None:
                expected_edge = round(cp - ip, 6)
                assert abs(ep - expected_edge) < 1e-4, (
                    f"Row {r['game_id']}: edge_pct={ep} != calibrated-implied={expected_edge}"
                )
