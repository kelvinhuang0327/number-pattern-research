# P137 Drift Alert Replay Consistency Gate - Dedicated Test
import json
from pathlib import Path

P136_PATH = "data/mlb_2026/derived/p136_signoff_drift_alert_runner_escalation_decision_packet_summary.json"
P137_PATH = "data/mlb_2026/derived/p137_drift_alert_replay_consistency_gate_summary.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "drift_alert_replay_consistency_gate_status",
    "source_signoff_drift_alert_runner_status",
    "source_evaluated_drift_event_count",
    "source_replay_run_count",
    "source_signoff_packet_count",
    "source_invalid_packet_count",
    "replay_run_count",
    "baseline_fingerprint",
    "replay_fingerprints",
    "fingerprint_consistency_status",
    "alert_verdict_consistency_status",
    "escalation_decision_packet_consistency_status",
    "alert_level_matrix_consistency_status",
    "drift_type_matrix_consistency_status",
    "escalation_path_matrix_consistency_status",
    "sla_matrix_consistency_status",
    "required_owner_matrix_consistency_status",
    "blocked_action_matrix_consistency_status",
    "unlock_prevention_matrix_consistency_status",
    "no_drift_record_packet_consistency_status",
    "simulated_blocking_drift_case_consistency_status",
    "final_classification_consistency_status",
    "drift_detected",
    "drift_details",
    "replay_alert_verdict_matrix",
    "replay_escalation_decision_packet_matrix",
    "replay_blocked_action_matrix",
    "replay_unlock_prevention_matrix",
    "reproducibility_metadata",
    "allowed_next_actions",
    "prohibited_actions",
    "blockers",
    "final_classification",
    "governance_invariant_summary",
    "governance_statement",
    "regression_status",
}

CONSISTENCY_STATUS_KEYS = {
    "fingerprint_consistency_status",
    "alert_verdict_consistency_status",
    "escalation_decision_packet_consistency_status",
    "alert_level_matrix_consistency_status",
    "drift_type_matrix_consistency_status",
    "escalation_path_matrix_consistency_status",
    "sla_matrix_consistency_status",
    "required_owner_matrix_consistency_status",
    "blocked_action_matrix_consistency_status",
    "unlock_prevention_matrix_consistency_status",
    "no_drift_record_packet_consistency_status",
    "simulated_blocking_drift_case_consistency_status",
    "final_classification_consistency_status",
}

FINAL_CLASSIFICATIONS = {
    "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS",
    "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p137_summary_exists():
    assert Path(P137_PATH).exists(), "P137 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P137_PATH)
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(set(d.keys()))


def test_source_values_match_p136():
    p136 = load_json(P136_PATH)
    p137 = load_json(P137_PATH)

    assert p137["source_signoff_drift_alert_runner_status"] == p136["signoff_drift_alert_runner_status"]
    assert p137["source_evaluated_drift_event_count"] == p136["evaluated_drift_event_count"]
    assert p137["source_replay_run_count"] == p136["source_replay_run_count"]
    assert p137["source_signoff_packet_count"] == p136["source_signoff_packet_count"]
    assert p137["source_invalid_packet_count"] == p136["source_invalid_packet_count"]


def test_replay_count_and_fingerprints_consistent():
    d = load_json(P137_PATH)
    assert d["replay_run_count"] >= 3
    assert len(d["replay_fingerprints"]) == d["replay_run_count"]

    baseline = d["baseline_fingerprint"]
    assert baseline
    for _, fp in d["replay_fingerprints"].items():
        assert fp == baseline


def test_all_consistency_statuses_consistent_and_no_drift():
    d = load_json(P137_PATH)
    for key in CONSISTENCY_STATUS_KEYS:
        assert d[key] == "CONSISTENT"

    assert d["drift_detected"] is False
    assert d["drift_details"] == []


def test_replay_matrices_identical_across_runs():
    d = load_json(P137_PATH)

    run_keys = sorted(d["replay_alert_verdict_matrix"].keys())
    first = d["replay_alert_verdict_matrix"][run_keys[0]]
    for key in run_keys[1:]:
        assert d["replay_alert_verdict_matrix"][key] == first

    run_keys = sorted(d["replay_escalation_decision_packet_matrix"].keys())
    first = d["replay_escalation_decision_packet_matrix"][run_keys[0]]
    for key in run_keys[1:]:
        assert d["replay_escalation_decision_packet_matrix"][key] == first

    run_keys = sorted(d["replay_blocked_action_matrix"].keys())
    first = d["replay_blocked_action_matrix"][run_keys[0]]
    for key in run_keys[1:]:
        assert d["replay_blocked_action_matrix"][key] == first

    run_keys = sorted(d["replay_unlock_prevention_matrix"].keys())
    first = d["replay_unlock_prevention_matrix"][run_keys[0]]
    for key in run_keys[1:]:
        assert d["replay_unlock_prevention_matrix"][key] == first


def test_required_behavior_for_dangerous_and_no_drift_cases():
    d = load_json(P137_PATH)

    packets = d["replay_escalation_decision_packet_matrix"]["run_1"]
    packet_by_id = {p["drift_case_id"]: p for p in packets}

    no_drift = packet_by_id["NO_SIGNOFF_DRIFT_RECORD_ONLY"]
    assert no_drift["blocked"] is False
    assert no_drift["critical_stop"] is False
    assert no_drift["escalation_path"] == "record_only"

    for case_id, packet in packet_by_id.items():
        if case_id == "NO_SIGNOFF_DRIFT_RECORD_ONLY":
            continue
        assert packet["blocked"] is True


def test_governance_invariants_remain_safe():
    d = load_json(P137_PATH)
    g = d["governance_invariant_summary"]

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


def test_regression_status_and_final_classification():
    d = load_json(P137_PATH)

    assert d["regression_status"]["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS"
    assert "does not imply legal provider approval" in d["governance_statement"]
