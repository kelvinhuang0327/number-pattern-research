# P122 Paper-Only Recommendation Readiness Review
# Reviews P112-P121 as one Lane A paper-only readiness system.

import json
from pathlib import Path

OUT_PATH = "data/mlb_2026/derived/p122_paper_only_recommendation_readiness_review_summary.json"
REPORT_PATH = "report/p122_paper_only_recommendation_readiness_review_20260601.md"

PHASE_ARTIFACTS = {
    "P112": {
        "summary_path": "data/mlb_2026/derived/p112_lane_a_market_contract_gap_review_summary.json",
        "objective": "Market-contract gap review"
    },
    "P113": {
        "summary_path": "data/mlb_2026/derived/p113_paper_only_market_contract_schema_fixture_summary.json",
        "objective": "Paper-only market schema fixture"
    },
    "P114": {
        "summary_path": "data/mlb_2026/derived/p114_legal_odds_source_requirements_spec_summary.json",
        "objective": "Legal odds source requirements"
    },
    "P115": {
        "summary_path": "data/mlb_2026/derived/p115_paper_only_odds_ingestion_contract_fixture_summary.json",
        "objective": "Paper-only odds ingestion contract fixture"
    },
    "P116": {
        "summary_path": "data/mlb_2026/derived/p116_paper_only_recommendation_row_dry_run_contract_summary.json",
        "objective": "Recommendation row dry-run contract"
    },
    "P117": {
        "summary_path": "data/mlb_2026/derived/p117_paper_only_recommendation_row_fixture_summary.json",
        "objective": "Recommendation row fixture"
    },
    "P118": {
        "summary_path": "data/mlb_2026/derived/p118_recommendation_row_validation_gate_summary.json",
        "objective": "Recommendation row validation gate"
    },
    "P119": {
        "summary_path": "data/mlb_2026/derived/p119_recommendation_row_gate_violation_fixture_summary.json",
        "objective": "Recommendation row gate violation fixture"
    },
    "P120": {
        "summary_path": "data/mlb_2026/derived/p120_legal_provider_authorization_checklist_summary.json",
        "objective": "Legal provider authorization checklist"
    },
    "P121": {
        "summary_path": "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json",
        "objective": "Provider authorization evidence placeholder"
    }
}

BLOCKERS = [
    "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
    "REAL_LEGAL_ODDS_NOT_INGESTED_BLOCKER",
    "PROVIDER_EVIDENCE_PLACEHOLDER_ONLY_BLOCKER",
    "PROVIDER_EVIDENCE_VALIDATION_GATE_REQUIRED_BLOCKER",
    "FULL_REGRESSION_NOT_RUN_BLOCKER"
]

ALLOWED_NEXT_ACTIONS = [
    "Maintain paper_only=true, diagnostic_only=true, production_ready=false",
    "Continue contract/governance verification only",
    "Implement explicit provider evidence validation gate (placeholder must never be treated as approval)",
    "Collect legal provider contract and legal odds evidence through compliance workflow only",
    "Run targeted/non-destructive tests and record exact PASS/FAIL/NOT RUN evidence"
]

PROHIBITED_ACTIONS = [
    "No provider approval or provider unlock",
    "No real legal odds ingestion, no odds fetch, no paid API call",
    "No recommendation output, no EV, no CLV, no Kelly, no stake, no profit",
    "No production path unlock or production mutation",
    "No crawler/scheduler/live API integration changes from this readiness review"
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_READY_WITH_BLOCKERS",
    "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_BLOCKED_BY_MISSING_ARTIFACTS",
    "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_FAILED_VALIDATION"
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_final_classification(doc: dict):
    if isinstance(doc.get("final_classification"), str):
        return doc["final_classification"]

    for key in (
        "fixture_metadata",
        "spec_metadata",
        "contract_metadata",
        "gate_metadata",
        "checklist_metadata",
        "placeholder_metadata",
        "violation_fixture_metadata",
    ):
        meta = doc.get(key)
        if isinstance(meta, dict) and isinstance(meta.get("final_classification"), str):
            return meta["final_classification"]

    return "UNKNOWN"


def find_governance(doc: dict):
    for key in ("governance_flags", "governance_locks", "governance_validation_rules", "governance"):
        g = doc.get(key)
        if isinstance(g, dict):
            return g

    nested = doc.get("paper_only_ingestion_payload_contract")
    if isinstance(nested, dict) and isinstance(nested.get("governance_flags"), dict):
        return nested["governance_flags"]

    return {}


def main():
    phase_matrix = []
    missing_artifacts = []
    loaded_docs = {}

    for phase_id, cfg in PHASE_ARTIFACTS.items():
        path = cfg["summary_path"]
        if not Path(path).exists():
            missing_artifacts.append(path)
            phase_matrix.append(
                {
                    "phase_id": phase_id,
                    "objective": cfg["objective"],
                    "summary_path": path,
                    "summary_exists": False,
                    "final_classification": "MISSING",
                    "status": "BLOCKED"
                }
            )
            continue

        doc = load_json(path)
        loaded_docs[phase_id] = doc
        final_class = find_final_classification(doc)
        phase_matrix.append(
            {
                "phase_id": phase_id,
                "objective": cfg["objective"],
                "summary_path": path,
                "summary_exists": True,
                "final_classification": final_class,
                "status": "BLOCKED" if "BLOCKER" in final_class or "WITH_BLOCKERS" in final_class or "DIAGNOSTIC_ONLY" in final_class else "UNKNOWN"
            }
        )

    p121 = loaded_docs.get("P121", {})
    p120 = loaded_docs.get("P120", {})
    p118 = loaded_docs.get("P118", {})
    p119 = loaded_docs.get("P119", {})
    p116 = loaded_docs.get("P116", {})

    p121_governance = find_governance(p121)
    p116_governance = find_governance(p116)

    provider_status_matrix = p121.get("provider_status_matrix", [])
    provider_approved = any(bool(x.get("provider_approved")) for x in provider_status_matrix)
    authorization_evidence_present = any(bool(x.get("authorization_evidence_present")) for x in provider_status_matrix)

    legal_provider_authorization_status = "BLOCKED"
    if provider_approved:
        legal_provider_authorization_status = "APPROVED"

    real_legal_odds_ingested = bool(p121_governance.get("odds_ingested", False)) or bool(p116_governance.get("odds_ingested", False))
    real_legal_odds_status = "BLOCKED"
    if real_legal_odds_ingested:
        real_legal_odds_status = "INGESTED"

    recommendation_row_contract_status = "BLOCKED"
    if "READY" in find_final_classification(p116) and "BLOCKERS" not in find_final_classification(p116):
        recommendation_row_contract_status = "READY"

    validation_gate_status = "BLOCKED"
    if "READY" in find_final_classification(p118) and "READY" in find_final_classification(p119):
        validation_gate_status = "READY_WITH_BLOCKERS"

    provider_evidence_placeholder_status = "PLACEHOLDER_ONLY_BLOCKED"
    if provider_approved or authorization_evidence_present:
        provider_evidence_placeholder_status = "EVIDENCE_PRESENT_CHECK_REQUIRED"

    regression_status = {
        "p120_p121_dedicated_tests_reported": True,
        "p120_p121_dedicated_tests_evidence_source": "report/p121_provider_authorization_evidence_placeholder_20260531.md",
        "targeted_p118_p121_tests_status": "NOT_RUN",
        "full_regression_status": "NOT_RUN",
        "full_regression_evidence": "No full regression artifact found in P121 packet."
    }

    governance_invariants = {
        "paper_only": bool(p121_governance.get("paper_only", False)),
        "diagnostic_only": bool(p121_governance.get("diagnostic_only", False)),
        "production_ready": bool(p121_governance.get("production_ready", True)),
        "real_bet_allowed": bool(p121_governance.get("real_bet_allowed", True)),
        "recommendation_allowed": bool(p121_governance.get("recommendation_allowed", True)),
        "provider_approved": provider_approved,
        "authorization_evidence_present": authorization_evidence_present,
        "real_legal_odds_ingested": real_legal_odds_ingested,
        "live_api_calls": int(p121_governance.get("live_api_calls", 1)),
        "paid_api_called": int(p121_governance.get("paid_api_calls", 1)) > 0,
        "ev_computed": bool(p121_governance.get("ev_computed", False)),
        "clv_computed": bool(p121_governance.get("clv_computed", False)),
        "kelly_computed": bool(p121_governance.get("kelly_computed", False)),
        "stake_sizing": bool(p121_governance.get("stake_sizing", False)),
        "profit_computed": bool(p121_governance.get("profit_computed", False)),
        "recommendation_generated": bool(p121_governance.get("recommendation_generated", False)),
    }

    blockers = list(BLOCKERS)
    if missing_artifacts:
        blockers.insert(0, "MISSING_REQUIRED_PHASE_ARTIFACTS_BLOCKER")

    final_classification = "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_READY_WITH_BLOCKERS"
    if missing_artifacts:
        final_classification = "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_BLOCKED_BY_MISSING_ARTIFACTS"

    hard_fail = (
        governance_invariants["paper_only"] is False
        or governance_invariants["diagnostic_only"] is False
        or governance_invariants["production_ready"] is True
        or governance_invariants["real_bet_allowed"] is True
        or governance_invariants["recommendation_allowed"] is True
        or governance_invariants["provider_approved"] is True
        or governance_invariants["authorization_evidence_present"] is True
        or governance_invariants["real_legal_odds_ingested"] is True
        or governance_invariants["live_api_calls"] != 0
        or governance_invariants["paid_api_called"] is True
        or governance_invariants["ev_computed"] is True
        or governance_invariants["clv_computed"] is True
        or governance_invariants["kelly_computed"] is True
        or governance_invariants["stake_sizing"] is True
        or governance_invariants["profit_computed"] is True
        or governance_invariants["recommendation_generated"] is True
    )
    if hard_fail:
        final_classification = "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_FAILED_VALIDATION"

    summary = {
        "readiness_metadata": {
            "review_version": "P122.20260601",
            "generated_at": "2026-06-01",
            "review_scope": "P112-P121 Lane A paper-only readiness review",
            "final_classification": final_classification
        },
        "readiness_status": "BLOCKED" if final_classification != "P122_PAPER_ONLY_RECOMMENDATION_READINESS_REVIEW_FAILED_VALIDATION" else "FAILED_VALIDATION",
        "legal_provider_authorization_status": legal_provider_authorization_status,
        "real_legal_odds_status": real_legal_odds_status,
        "recommendation_row_contract_status": recommendation_row_contract_status,
        "validation_gate_status": validation_gate_status,
        "provider_evidence_placeholder_status": provider_evidence_placeholder_status,
        "regression_status": regression_status,
        "phase_readiness_matrix": phase_matrix,
        "governance_invariants": governance_invariants,
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": blockers,
        "missing_artifacts": missing_artifacts,
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS
    }

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# P122 Paper-Only Recommendation Readiness Review (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- readiness_status: {summary['readiness_status']}\n")
        f.write(f"- final_classification: {summary['readiness_metadata']['final_classification']}\n\n")

        f.write("## Status Classification\n")
        f.write(f"- legal_provider_authorization_status: {summary['legal_provider_authorization_status']}\n")
        f.write(f"- real_legal_odds_status: {summary['real_legal_odds_status']}\n")
        f.write(f"- recommendation_row_contract_status: {summary['recommendation_row_contract_status']}\n")
        f.write(f"- validation_gate_status: {summary['validation_gate_status']}\n")
        f.write(f"- provider_evidence_placeholder_status: {summary['provider_evidence_placeholder_status']}\n\n")

        f.write("## Governance Invariants\n")
        for k, v in summary["governance_invariants"].items():
            f.write(f"- {k}: {v}\n")

        f.write("\n## P112-P121 Readiness Matrix\n")
        for row in summary["phase_readiness_matrix"]:
            f.write(
                f"- {row['phase_id']}: {row['status']} | {row['final_classification']} | {row['summary_path']}\n"
            )

        f.write("\n## Regression/Test Status\n")
        for k, v in summary["regression_status"].items():
            f.write(f"- {k}: {v}\n")

        f.write("\n## Blockers\n")
        for b in summary["blockers"]:
            f.write(f"- {b}\n")

        if summary["missing_artifacts"]:
            f.write("\n## Missing Artifacts\n")
            for p in summary["missing_artifacts"]:
                f.write(f"- {p}\n")

        f.write("\n## Allowed Next Actions\n")
        for a in summary["allowed_next_actions"]:
            f.write(f"- {a}\n")

        f.write("\n## Prohibited Actions\n")
        for a in summary["prohibited_actions"]:
            f.write(f"- {a}\n")

    print(f"P122 readiness summary written to {OUT_PATH}")
    print(f"P122 readiness report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
