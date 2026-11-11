# P129 Replay Drift Alert Contract - Dedicated Test
import json
from pathlib import Path

P129_PATH = "data/mlb_2026/derived/p129_replay_drift_alert_contract_summary.json"

REQUIRED_ALERT_LEVELS = {
    "GREEN_NO_DRIFT",
    "YELLOW_METADATA_ONLY_DRIFT",
    "ORANGE_BLOCKED_REASON_OR_RULE_DRIFT",
    "RED_VERDICT_OR_UNLOCK_DRIFT",
    "CRITICAL_PROVIDER_OR_PRODUCTION_UNLOCK_DRIFT",
}

REQUIRED_BASELINE_CHANGE_FIELDS = {
    "baseline_change_request_id",
    "baseline_change_owner",
    "baseline_change_reason",
    "source_fixture_version_before",
    "source_fixture_version_after",
    "old_fingerprint",
    "new_fingerprint",
    "rule_change_summary",
    "expected_verdict_delta",
    "reviewer_approval_status",
    "reviewer_identity",
    "approval_timestamp",
    "rollback_plan",
    "non_unlock_attestation",
}

REQUIRED_BLOCKING_CONDITION_IDS = {
    "C001_PREVIOUSLY_BLOCKED_BECOMES_ALLOWED",
    "C002_UNEXPECTED_ALLOWED_COUNT_GT_ZERO",
    "C003_ACTUAL_BLOCKED_LT_EXPECTED_BLOCKED",
    "C004_RECOMMENDATION_UNLOCK_TRUE",
    "C005_PRODUCTION_UNLOCK_TRUE",
    "C006_EV_CLV_KELLY_STAKE_PROFIT_UNLOCK_TRUE",
    "C007_PROVIDER_APPROVED_WITHOUT_VERIFIED_LEGAL_EVIDENCE",
    "C008_AUTH_EVIDENCE_PRESENT_WITHOUT_VERIFIED_LEGAL_EVIDENCE",
    "C009_REAL_ODDS_INGESTED_WITHOUT_APPROVAL",
    "C010_LIVE_OR_PAID_API_CALLS_NON_ZERO",
    "C011_BASELINE_FINGERPRINT_CHANGED_WITHOUT_APPROVAL",
    "C012_DRIFT_DETAILS_MISSING_WHEN_DRIFT_DETECTED",
}

FINAL_CLASSIFICATIONS = {
    "P129_REPLAY_DRIFT_ALERT_CONTRACT_READY_WITH_BLOCKERS",
    "P129_REPLAY_DRIFT_ALERT_CONTRACT_BLOCKED_BY_MISSING_ARTIFACTS",
    "P129_REPLAY_DRIFT_ALERT_CONTRACT_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p129_summary_exists():
    assert Path(P129_PATH).exists(), "P129 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P129_PATH)
    for key in (
        "replay_drift_alert_contract_status",
        "source_replay_gate_status",
        "source_replay_run_count",
        "source_fixture_count",
        "source_baseline_fingerprint",
        "source_drift_detected",
        "alert_level_definitions",
        "alert_escalation_rules",
        "blocking_conditions",
        "baseline_hash_change_review_rules",
        "verdict_drift_rules",
        "blocked_reason_drift_rules",
        "rule_matrix_drift_rules",
        "unlock_prevention_drift_rules",
        "fingerprint_drift_rules",
        "reproducibility_metadata_drift_rules",
        "drift_details_required_fields",
        "allowed_next_actions",
        "prohibited_actions",
        "blockers",
        "final_classification",
        "governance_invariants",
        "regression_status",
    ):
        assert key in d, f"Missing section: {key}"


def test_source_replay_state_matches_p128_expectation():
    d = load_json(P129_PATH)
    assert d["source_replay_gate_status"] == "READY_WITH_BLOCKERS"
    assert d["source_replay_run_count"] == 3
    assert d["source_fixture_count"] == 19
    assert d["source_drift_detected"] is False
    assert len(d["source_baseline_fingerprint"]) == 64


def test_required_alert_levels_and_escalations_exist():
    d = load_json(P129_PATH)
    levels = set(d["alert_level_definitions"].keys())
    assert levels == REQUIRED_ALERT_LEVELS
    assert len(d["alert_escalation_rules"]) >= 4


def test_required_blocking_conditions_exist():
    d = load_json(P129_PATH)
    cond_ids = {row["condition_id"] for row in d["blocking_conditions"]}
    assert cond_ids == REQUIRED_BLOCKING_CONDITION_IDS


def test_baseline_hash_change_review_rules_cover_required_fields():
    d = load_json(P129_PATH)
    fields = set(d["baseline_hash_change_review_rules"]["required_fields"])
    assert fields == REQUIRED_BASELINE_CHANGE_FIELDS
    assert "does not unlock provider/odds/recommendation/production" in d["baseline_hash_change_review_rules"][
        "non_unlock_attestation_required"
    ]


def test_drift_rule_sections_defined():
    d = load_json(P129_PATH)
    for key in (
        "verdict_drift_rules",
        "blocked_reason_drift_rules",
        "rule_matrix_drift_rules",
        "unlock_prevention_drift_rules",
        "fingerprint_drift_rules",
        "reproducibility_metadata_drift_rules",
    ):
        assert "rule" in d[key]
        assert "required_alert_level" in d[key]
        assert "block_required" in d[key]


def test_governance_invariants_are_safe():
    d = load_json(P129_PATH)
    g = d["governance_invariants"]
    assert g["paper_only"] is True
    assert g["diagnostic_only"] is True
    assert g["production_ready"] is False
    assert g["real_bet_allowed"] is False
    assert g["recommendation_allowed"] is False
    assert g["provider_approved"] is False
    assert g["authorization_evidence_present"] is False
    assert g["placeholder_allowed_as_authorization"] is False
    assert g["real_legal_odds_ingested"] is False
    assert g["live_api_calls"] == 0
    assert g["paid_api_called"] is False
    assert g["ev_computed"] is False
    assert g["clv_computed"] is False
    assert g["kelly_computed"] is False
    assert g["stake_sizing"] is False
    assert g["profit_computed"] is False
    assert g["recommendation_generated"] is False


def test_regression_policy_and_final_classification():
    d = load_json(P129_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P129_REPLAY_DRIFT_ALERT_CONTRACT_READY_WITH_BLOCKERS"
