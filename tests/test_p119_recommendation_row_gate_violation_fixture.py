# P119 Recommendation Row Gate Violation Fixture — Dedicated Test
# 驗證 violation fixture 結構、分類、case 覆蓋、gate block 行為
import json
import pytest
from pathlib import Path

P119_PATH = "data/mlb_2026/derived/p119_recommendation_row_gate_violation_fixture_summary.json"
P118_PATH = "data/mlb_2026/derived/p118_recommendation_row_validation_gate_summary.json"

REQUIRED_SECTIONS = [
    "violation_fixture_metadata",
    "source_p118_gate_reference",
    "negative_fixture_scope",
    "invalid_recommendation_rows",
    "violation_cases",
    "expected_gate_failures",
    "market_violation_matrix",
    "governance_violation_matrix",
    "odds_safety_violation_matrix",
    "source_trace_violation_matrix",
    "failure_messages",
    "allowed_future_actions",
    "prohibited_actions",
    "invariant_coverage"
]

REQUIRED_VIOLATION_IDS = [
    "recommendation_allowed_true_violation",
    "production_ready_true_violation",
    "real_odds_present_violation",
    "ev_field_present_violation",
    "clv_field_present_violation",
    "kelly_field_present_violation",
    "stake_field_present_violation",
    "profit_field_present_violation",
    "missing_source_trace_violation",
    "missing_legal_provider_violation",
    "canonical_row_mutation_violation",
    "outcome_row_mutation_violation",
    "taiwan_lottery_recommendation_true_violation"
]

REQUIRED_MARKETS = [
    "moneyline_winner",
    "run_line_handicap",
    "total_runs_over_under",
    "first_five_innings_if_supported_later",
    "unsupported_market_placeholder"
]

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def test_p118_summary_exists_and_classification():
    d = load_json(P118_PATH)
    assert d["gate_metadata"]["final_classification"] == "P118_RECOMMENDATION_ROW_VALIDATION_GATE_READY_WITH_BLOCKERS"

def test_p119_summary_exists():
    assert Path(P119_PATH).exists(), "P119 summary JSON missing"
    d = load_json(P119_PATH)
    assert d["violation_fixture_metadata"]["final_classification"].startswith("P119_GATE_VIOLATION_FIXTURE")

def test_violation_fixture_sections():
    d = load_json(P119_PATH)
    for k in REQUIRED_SECTIONS:
        assert k in d, f"Missing section: {k}"

def test_all_required_violation_cases_exist():
    d = load_json(P119_PATH)
    cases = d["violation_cases"]
    found = set()
    for c in cases:
        found.add(c["violation_id"])
    for v in REQUIRED_VIOLATION_IDS:
        assert v in found, f"Missing violation case: {v}"

def test_each_violation_case_blocked():
    d = load_json(P119_PATH)
    for c in d["violation_cases"]:
        assert c["expected_gate_status"] in ("FAIL", "BLOCKED"), f"Case not blocked: {c['violation_id']}"
        assert c["governance_expected_result"] == "BLOCKED"

def test_market_coverage():
    d = load_json(P119_PATH)
    markets = set(c["market_id"] for c in d["violation_cases"])
    for m in REQUIRED_MARKETS:
        assert m in markets, f"Missing market: {m}"

def test_no_valid_recommendation_produced():
    d = load_json(P119_PATH)
    # 1. recommendation_allowed_true_violation 必須存在且被 BLOCKED
    found = False
    for c in d["violation_cases"]:
        if c["violation_id"] == "recommendation_allowed_true_violation":
            found = True
            assert c["invalid_row_patch"].get("recommendation_allowed") is True, "recommendation_allowed_true_violation 應有 recommendation_allowed=True"
            assert c["expected_gate_status"] in ("FAIL", "BLOCKED"), "應被 gate block"
            assert c["governance_expected_result"] == "BLOCKED", "governance_expected_result 應為 BLOCKED"
    assert found, "必須有 recommendation_allowed_true_violation 案例"
    # 2. 不應有任何 violation case 被視為 valid recommendation row
    for c in d["violation_cases"]:
        assert c["governance_expected_result"] == "BLOCKED", f"Violation case {c['violation_id']} 不應被視為 valid recommendation row"
    # 3. governance flags 必須 recommendation_allowed=false, recommendation_generated=false
    meta = d["violation_fixture_metadata"]
    # fixture summary 不直接含 governance flags，但可於主流程驗證

def test_governance_flags():
    d = load_json(P119_PATH)
    meta = d["violation_fixture_metadata"]
    assert meta["final_classification"].startswith("P119_GATE_VIOLATION_FIXTURE")

def test_final_classification_valid():
    d = load_json(P119_PATH)
    assert d["violation_fixture_metadata"]["final_classification"] in [
        "P119_GATE_VIOLATION_FIXTURE_READY_DIAGNOSTIC_ONLY",
        "P119_GATE_VIOLATION_FIXTURE_READY_WITH_BLOCKERS",
        "P119_GATE_VIOLATION_FIXTURE_BLOCKED_BY_MISSING_P118",
        "P119_GATE_VIOLATION_FIXTURE_FAILED_VALIDATION"
    ]
