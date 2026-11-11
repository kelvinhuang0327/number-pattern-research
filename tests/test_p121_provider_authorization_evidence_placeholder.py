# P121 Provider Authorization Evidence Placeholder — Dedicated Test
# 驗證 placeholder 結構、evidence schema、blocker、治理、禁止行為
import json
import pytest
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P120_PATH = "data/mlb_2026/derived/p120_legal_provider_authorization_checklist_summary.json"

REQUIRED_SECTIONS = [
    "placeholder_metadata",
    "source_p120_checklist_reference",
    "authorization_evidence_scope",
    "provider_authorization_evidence_placeholder",
    "evidence_schema",
    "required_future_evidence_fields",
    "forbidden_evidence_fields",
    "provider_status_matrix",
    "market_authorization_matrix",
    "evidence_validation_rules",
    "audit_review_requirements",
    "secret_handling_rules",
    "blocked_until_evidence_items",
    "future_integration_gates",
    "allowed_future_actions",
    "prohibited_actions",
    "blocker_category_coverage",
    "governance_flags"
]

REQUIRED_MARKETS = [
    "moneyline_winner",
    "run_line_handicap",
    "total_runs_over_under",
    "first_five_innings_if_supported_later",
    "unsupported_market_placeholder"
]

REQUIRED_BLOCKERS = [
    "PROVIDER_AUTHORIZATION_EVIDENCE_MISSING",
    "SIGNED_CONTRACT_MISSING",
    "DATA_LICENSE_MISSING",
    "COMPLIANCE_REVIEW_MISSING",
    "SECURITY_REVIEW_MISSING",
    "SOURCE_TRACE_REQUIREMENT_MISSING",
    "AUDIT_REFERENCE_MISSING",
    "SECRET_HANDLING_BLOCKER",
    "FORBIDDEN_CREDENTIAL_STORAGE_BLOCKER",
    "FORBIDDEN_SCRAPING_BLOCKER",
    "EV_CLV_NOT_ALLOWED_BLOCKER",
    "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
    "GOVERNANCE_PRODUCTION_BLOCKER",
    "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
]

REQUIRED_EVIDENCE_FIELDS = [
    "provider_name_placeholder",
    "provider_contract_status",
    "legal_usage_scope",
    "license_status",
    "authorized_markets",
    "authorized_access_method",
    "authorized_regions",
    "effective_date_placeholder",
    "expiry_date_placeholder",
    "review_owner_placeholder",
    "audit_reference_placeholder",
    "source_trace_requirement",
    "data_retention_policy_status",
    "security_review_status",
    "compliance_review_status"
]

FORBIDDEN_EVIDENCE_FIELDS = [
    "real_api_key",
    "real_secret",
    "real_token",
    "real_password",
    "private_auth_url",
    "signed_contract_binary",
    "provider_credentials",
    "live_endpoint_credentials",
    "personal_data",
    "production_access_token"
]

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def test_p120_summary_exists_and_classification():
    d = load_json(P120_PATH)
    assert d["checklist_metadata"]["final_classification"] == "P120_LEGAL_PROVIDER_AUTHORIZATION_CHECKLIST_READY_WITH_BLOCKERS"

def test_p121_summary_exists():
    assert Path(P121_PATH).exists(), "P121 summary JSON missing"
    d = load_json(P121_PATH)
    assert d["placeholder_metadata"]["final_classification"].startswith("P121_PROVIDER_AUTHORIZATION_EVIDENCE_PLACEHOLDER")

def test_placeholder_sections():
    d = load_json(P121_PATH)
    for k in REQUIRED_SECTIONS:
        assert k in d, f"Missing section: {k}"

def test_evidence_schema():
    d = load_json(P121_PATH)
    schema = d["provider_authorization_evidence_placeholder"]["evidence_schema"]
    for k in ["required_future_evidence_fields", "forbidden_evidence_fields"]:
        assert k in schema
    for f in REQUIRED_EVIDENCE_FIELDS:
        assert f in schema["required_future_evidence_fields"]
    for f in FORBIDDEN_EVIDENCE_FIELDS:
        assert f in schema["forbidden_evidence_fields"]

def test_market_coverage():
    d = load_json(P121_PATH)
    matrix = d["market_authorization_matrix"]
    found = set(m["market_id"] for m in matrix)
    for m in REQUIRED_MARKETS:
        assert m in found, f"Missing market: {m}"

def test_blocker_category_coverage():
    d = load_json(P121_PATH)
    blockers = set(d["blocker_category_coverage"])
    for b in REQUIRED_BLOCKERS:
        assert b in blockers, f"Missing blocker: {b}"

def test_all_markets_blocked():
    d = load_json(P121_PATH)
    for m in d["market_authorization_matrix"]:
        assert m["authorization_status"] in ("BLOCKED", "NOT_AUTHORIZED"), f"Market {m['market_id']} not blocked"

def test_no_provider_approved():
    d = load_json(P121_PATH)
    for p in d["provider_status_matrix"]:
        assert not p["provider_approved"]
        assert not p["provider_authorized"]
        assert not p["authorization_evidence_present"]

def test_no_evidence_present():
    d = load_json(P121_PATH)
    for p in d["provider_status_matrix"]:
        assert p["provider_contract_status"] == "MISSING"

def test_no_forbidden_fields():
    d = load_json(P121_PATH)
    for m in d["market_authorization_matrix"]:
        for f in FORBIDDEN_EVIDENCE_FIELDS:
            assert f in m["forbidden_evidence_fields"]

def test_governance_flags():
    d = load_json(P121_PATH)
    g = d["governance_flags"]
    assert g["paper_only"]
    assert g["diagnostic_only"]
    assert not g["production_ready"]
    assert not g["provider_approved"]
    assert not g["provider_authorized"]
    assert not g["authorization_evidence_present"]
    assert not g["odds_used"]
    assert not g["recommendation_allowed"]
    assert not g["ev_computed"]
    assert not g["kelly_computed"]
    assert not g["stake_sizing"]
    assert not g["profit_computed"]
    assert not g["recommendation_generated"]
    assert not g["taiwan_lottery_recommendation"]
    assert not g["force_push_used"]

def test_final_classification_valid():
    d = load_json(P121_PATH)
    assert d["placeholder_metadata"]["final_classification"] in [
        "P121_PROVIDER_AUTHORIZATION_EVIDENCE_PLACEHOLDER_READY_DIAGNOSTIC_ONLY",
        "P121_PROVIDER_AUTHORIZATION_EVIDENCE_PLACEHOLDER_READY_WITH_BLOCKERS",
        "P121_PROVIDER_AUTHORIZATION_EVIDENCE_PLACEHOLDER_BLOCKED_BY_MISSING_P120",
        "P121_PROVIDER_AUTHORIZATION_EVIDENCE_PLACEHOLDER_FAILED_VALIDATION"
    ]
