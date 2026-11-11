# P122 Paper-Only Recommendation Readiness Review - Dedicated Test
import json
from pathlib import Path

P122_PATH = "data/mlb_2026/derived/p122_paper_only_recommendation_readiness_review_summary.json"

REQUIRED_PHASES = [
    "P112",
    "P113",
    "P114",
    "P115",
    "P116",
    "P117",
    "P118",
    "P119",
    "P120",
    "P121",
]

REQUIRED_BLOCKERS = [
    "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
    "REAL_LEGAL_ODDS_NOT_INGESTED_BLOCKER",
    "PROVIDER_EVIDENCE_PLACEHOLDER_ONLY_BLOCKER",
    "PROVIDER_EVIDENCE_VALIDATION_GATE_REQUIRED_BLOCKER",
    "FULL_REGRESSION_NOT_RUN_BLOCKER",
]

FINAL_CLASSIFICATIONS = [
    "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_READY_WITH_BLOCKERS",
    "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_BLOCKED_BY_MISSING_ARTIFACTS",
    "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p122_summary_exists():
    assert Path(P122_PATH).exists(), "P122 summary JSON missing"


def test_required_top_level_sections():
    d = load_json(P122_PATH)
    for key in (
        "readiness_metadata",
        "readiness_status",
        "legal_provider_authorization_status",
        "real_legal_odds_status",
        "recommendation_row_contract_status",
        "validation_gate_status",
        "provider_evidence_placeholder_status",
        "regression_status",
        "phase_readiness_matrix",
        "governance_invariants",
        "allowed_next_actions",
        "prohibited_actions",
        "blockers",
        "final_classification_options",
    ):
        assert key in d, f"Missing section: {key}"


def test_phase_matrix_has_p112_to_p121():
    d = load_json(P122_PATH)
    phase_ids = {r["phase_id"] for r in d["phase_readiness_matrix"]}
    for phase_id in REQUIRED_PHASES:
        assert phase_id in phase_ids, f"Missing phase in matrix: {phase_id}"


def test_governance_invariants_are_safe():
    d = load_json(P122_PATH)
    g = d["governance_invariants"]
    assert g["paper_only"] is True
    assert g["diagnostic_only"] is True
    assert g["production_ready"] is False
    assert g["real_bet_allowed"] is False
    assert g["recommendation_allowed"] is False
    assert g["provider_approved"] is False
    assert g["authorization_evidence_present"] is False
    assert g["real_legal_odds_ingested"] is False
    assert g["live_api_calls"] == 0
    assert g["paid_api_called"] is False
    assert g["ev_computed"] is False
    assert g["clv_computed"] is False
    assert g["kelly_computed"] is False
    assert g["stake_sizing"] is False
    assert g["profit_computed"] is False
    assert g["recommendation_generated"] is False


def test_blockers_include_required_items():
    d = load_json(P122_PATH)
    blockers = set(d["blockers"])
    for blocker in REQUIRED_BLOCKERS:
        assert blocker in blockers, f"Missing blocker: {blocker}"


def test_regression_status_not_overclaimed():
    d = load_json(P122_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"


def test_final_classification_is_allowed_and_blocked_mode():
    d = load_json(P122_PATH)
    final_class = d["readiness_metadata"]["final_classification"]
    assert final_class in FINAL_CLASSIFICATIONS
    assert final_class != "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_FAILED_VALIDATION"


def test_prohibited_actions_cover_unlock_paths():
    d = load_json(P122_PATH)
    text = "\n".join(d["prohibited_actions"]).lower()
    for word in ("provider", "odds", "recommendation", "ev", "clv", "kelly", "stake", "profit", "production"):
        assert word in text, f"Prohibited actions missing keyword: {word}"
