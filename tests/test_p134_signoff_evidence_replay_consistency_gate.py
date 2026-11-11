# P134 Sign-off Evidence Replay Consistency Gate - Dedicated Test
import json
from pathlib import Path

P133_PATH = "data/mlb_2026/derived/p133_escalation_signoff_evidence_packet_validator_summary.json"
P134_PATH = "data/mlb_2026/derived/p134_signoff_evidence_replay_consistency_gate_summary.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "signoff_replay_consistency_gate_status",
    "source_signoff_packet_validator_status",
    "replay_run_count",
    "source_signoff_packet_count",
    "source_invalid_packet_count",
    "baseline_fingerprint",
    "replay_fingerprints",
    "fingerprint_consistency_status",
    "verdict_matrix_consistency_status",
    "blocker_classification_consistency_status",
    "required_evidence_matrix_consistency_status",
    "escalation_level_coverage_consistency_status",
    "governance_invariant_consistency_status",
    "unlock_prevention_consistency_status",
    "drift_detected",
    "drift_details",
    "replay_signoff_verdict_matrix",
    "replay_blocker_matrix",
    "replay_required_evidence_matrix",
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

FINAL_CLASSIFICATIONS = {
    "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS",
    "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p134_summary_exists():
    assert Path(P134_PATH).exists(), "P134 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P134_PATH)
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(set(d.keys()))


def test_source_status_and_counts_match_p133():
    p133 = load_json(P133_PATH)
    p134 = load_json(P134_PATH)

    assert p134["source_signoff_packet_validator_status"] == p133["signoff_packet_validator_status"]
    assert p134["source_signoff_packet_count"] == len(p133["signoff_verdict_matrix"])
    assert p134["source_invalid_packet_count"] == len(p133["invalid_signoff_packet_cases"])


def test_replay_count_and_fingerprint_consistency():
    d = load_json(P134_PATH)
    assert d["replay_run_count"] >= 3
    assert len(d["replay_fingerprints"]) == d["replay_run_count"]

    baseline = d["baseline_fingerprint"]
    assert baseline
    for _, fp in d["replay_fingerprints"].items():
        assert fp == baseline

    assert d["fingerprint_consistency_status"] == "CONSISTENT"


def test_matrix_consistency_statuses_and_no_drift():
    d = load_json(P134_PATH)

    assert d["verdict_matrix_consistency_status"] == "CONSISTENT"
    assert d["blocker_classification_consistency_status"] == "CONSISTENT"
    assert d["required_evidence_matrix_consistency_status"] == "CONSISTENT"
    assert d["escalation_level_coverage_consistency_status"] == "CONSISTENT"
    assert d["governance_invariant_consistency_status"] == "CONSISTENT"
    assert d["unlock_prevention_consistency_status"] == "CONSISTENT"
    assert d["drift_detected"] is False
    assert d["drift_details"] == []


def test_replay_content_stable_and_invalid_cases_blocked():
    d = load_json(P134_PATH)

    runs = sorted(d["replay_signoff_verdict_matrix"].keys())
    first = d["replay_signoff_verdict_matrix"][runs[0]]
    for run in runs[1:]:
        assert d["replay_signoff_verdict_matrix"][run] == first

    assert first["VALID_SIGNOFF_PACKET_TEMPLATE"]["status"] == "GOVERNANCE_ONLY_PENDING_REVIEW"
    for case_id, row in first.items():
        if case_id == "VALID_SIGNOFF_PACKET_TEMPLATE":
            continue
        assert row["status"] == "BLOCKED"


def test_governance_invariants_remain_safe():
    d = load_json(P134_PATH)
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
    d = load_json(P134_PATH)
    assert d["regression_status"]["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS"
