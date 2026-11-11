# P120 Legal Provider Authorization Checklist — Dedicated Test
# 驗證 checklist 結構、分類、blocker、治理、合約、禁止行為
import json
import pytest
from pathlib import Path

P120_PATH = "data/mlb_2026/derived/p120_legal_provider_authorization_checklist_summary.json"
P119_PATH = "data/mlb_2026/derived/p119_recommendation_row_gate_violation_fixture_summary.json"

REQUIRED_SECTIONS = [
    "checklist_metadata",
    "source_p119_gate_violation_reference",
    "source_p118_gate_reference",
    "authorization_scope",
    "legal_provider_authorization_requirements",
    "provider_contract_requirements",
    "data_license_requirements",
    "market_coverage_requirements",
    "odds_access_method_requirements",
    "source_trace_requirements",
    "audit_log_requirements",
    "data_retention_requirements",
    "security_and_secret_handling_requirements",
    "compliance_review_requirements",
    "blocked_until_authorized_items",
    "future_integration_gates",
    "allowed_future_actions",
    "prohibited_actions",
    "market_authorization_matrix",
    "blocker_category_coverage"
]

REQUIRED_MARKETS = [
    "moneyline_winner",
    "run_line_handicap",
    "total_runs_over_under",
    "first_five_innings_if_supported_later",
    "unsupported_market_placeholder"
]

REQUIRED_BLOCKERS = [
    "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
    "DATA_LICENSE_BLOCKER",
    "FORBIDDEN_SCRAPING_BLOCKER",
    "SOURCE_TRACE_BLOCKER",
    "AUDIT_LOG_BLOCKER",
    "SECRET_HANDLING_BLOCKER",
    "MARKET_COVERAGE_BLOCKER",
    "TIMESTAMP_FRESHNESS_BLOCKER",
    "DATA_RETENTION_POLICY_BLOCKER",
    "COMPLIANCE_REVIEW_BLOCKER",
    "EV_CLV_NOT_ALLOWED_BLOCKER",
    "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
    "GOVERNANCE_PRODUCTION_BLOCKER",
    "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
]

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def test_p119_summary_exists_and_classification():
    d = load_json(P119_PATH)
    assert d["violation_fixture_metadata"]["final_classification"] == "P119_GATE_VIOLATION_FIXTURE_READY_WITH_BLOCKERS"

def test_p120_summary_exists():
    assert Path(P120_PATH).exists(), "P120 summary JSON missing"
    d = load_json(P120_PATH)
    assert d["checklist_metadata"]["final_classification"].startswith("P120_LEGAL_PROVIDER_AUTHORIZATION_CHECKLIST")

def test_checklist_sections():
    d = load_json(P120_PATH)
    for k in REQUIRED_SECTIONS:
        assert k in d, f"Missing section: {k}"

def test_market_coverage():
    d = load_json(P120_PATH)
    matrix = d["market_authorization_matrix"]
    found = set(m["market_id"] for m in matrix)
    for m in REQUIRED_MARKETS:
        assert m in found, f"Missing market: {m}"

def test_blocker_category_coverage():
    d = load_json(P120_PATH)
    blockers = set(d["blocker_category_coverage"])
    for b in REQUIRED_BLOCKERS:
        assert b in blockers, f"Missing blocker: {b}"

def test_all_markets_blocked():
    d = load_json(P120_PATH)
    for m in d["market_authorization_matrix"]:
        assert m["authorization_status"] in ("BLOCKED", "NOT_AUTHORIZED"), f"Market {m['market_id']} not blocked"

def test_no_provider_approved():
    d = load_json(P120_PATH)
    for m in d["market_authorization_matrix"]:
        assert m["authorization_status"] != "APPROVED", f"Market {m['market_id']} should not be approved"

def test_scraping_blocked():
    d = load_json(P120_PATH)
    for m in d["market_authorization_matrix"]:
        assert "Scraping" in m["forbidden_access_methods"], f"Scraping not blocked for {m['market_id']}"

def test_no_credentials_or_secrets():
    d = load_json(P120_PATH)
    for v in d["security_and_secret_handling_requirements"]:
        assert "credentials" in v or "secrets" in v or "auth URLs" in v

def test_no_odds_or_recommendation_logic():
    d = load_json(P120_PATH)
    for m in d["market_authorization_matrix"]:
        assert m["prohibited_action"].find("odds") >= 0 or m["prohibited_action"].find("recommendation") >= 0

def test_governance_flags():
    d = load_json(P120_PATH)
    meta = d["checklist_metadata"]
    assert meta["final_classification"].startswith("P120_LEGAL_PROVIDER_AUTHORIZATION_CHECKLIST")

def test_final_classification_valid():
    d = load_json(P120_PATH)
    assert d["checklist_metadata"]["final_classification"] in [
        "P120_LEGAL_PROVIDER_AUTHORIZATION_CHECKLIST_READY_DIAGNOSTIC_ONLY",
        "P120_LEGAL_PROVIDER_AUTHORIZATION_CHECKLIST_READY_WITH_BLOCKERS",
        "P120_LEGAL_PROVIDER_AUTHORIZATION_CHECKLIST_BLOCKED_BY_MISSING_P119",
        "P120_LEGAL_PROVIDER_AUTHORIZATION_CHECKLIST_FAILED_VALIDATION"
    ]
