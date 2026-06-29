"""
scripts/p115_biglotto_quarantine_governance.py

P115: BIG_LOTTO Quarantine Governance Design for fourier30_markov30_biglotto.

Read-only. No DB writes. No strategy promotion. No lifecycle mutation.
No registry mutation. No actual quarantine applied.
No replay row insert or delete.
No 4_STAR backtest. No Special3 P108 re-evaluation.
No POWER_LOTTO P117 execution.

Usage:
    .venv/bin/python scripts/p115_biglotto_quarantine_governance.py \
        --json-out outputs/replay/p115_biglotto_quarantine_governance_20260527.json \
        --db lottery_api/data/lottery_v2.db
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path


def _repo_root():
    return Path(__file__).resolve().parent.parent


def _canonical_db_path():
    return _repo_root() / "lottery_api" / "data" / "lottery_v2.db"


def _resolve_db_path(db_path=None):
    candidate = _canonical_db_path() if db_path is None else Path(db_path)
    if db_path is not None and not candidate.is_absolute():
        raise ValueError("db_path must be absolute; use None for the canonical lottery_v2.db")
    if not candidate.exists():
        raise FileNotFoundError(f"Lottery DB path does not exist: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Lottery DB path is not a regular file: {candidate}")
    return str(candidate)


# ── Artifact paths ────────────────────────────────────────────────────────────
P112_ARTIFACT = "outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json"
P113_ARTIFACT = "outputs/replay/p113_p112_action_decision_matrix_20260527.json"
P114_ARTIFACT = "outputs/replay/p114_temporal_stability_audit_20260527.json"
P116_ARTIFACT = "outputs/replay/p116_powerlotto_oos_monitoring_design_20260527.json"

TARGET_STRATEGY_ID = "fourier30_markov30_biglotto"
TARGET_LOTTERY_TYPE = "BIG_LOTTO"
EXPECTED_REPLAY_ROWS = 54462

VALID_CLASSIFICATIONS = {
    "P115_BIGLOTTO_QUARANTINE_GOVERNANCE_READY",
    "P115_BIGLOTTO_QUARANTINE_GOVERNANCE_PARTIAL",
    "P115_BIGLOTTO_QUARANTINE_GOVERNANCE_INCONCLUSIVE",
    "P115_BLOCKED_BY_PREFLIGHT",
    "P115_BLOCKED_BY_DB_DRIFT",
    "P115_BLOCKED_BY_GUARD_FAILURE",
    "P115_BLOCKED_BY_TEST_FAILURE",
    "P115_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P115_BLOCKED_BY_SCOPE_VIOLATION",
    "P115_BLOCKED_BY_CONTEXT_CONTAMINATION",
}


# ── DB read-only helper ───────────────────────────────────────────────────────
def open_db_readonly(db_path=None) -> sqlite3.Connection:
    """Open SQLite DB in read-only mode via URI. No writes possible."""
    uri = Path(_resolve_db_path(db_path)).as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def verify_db_invariants(db_path: str) -> dict:
    """Verify DB invariants. Returns dict with row counts."""
    conn = open_db_readonly(db_path)
    try:
        replay_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        draw_counts = conn.execute(
            "SELECT lottery_type, COUNT(*), MAX(CAST(draw AS INTEGER)) "
            "FROM draws WHERE lottery_type IN ('3_STAR','4_STAR','POWER_LOTTO') "
            "GROUP BY lottery_type"
        ).fetchall()
    finally:
        conn.close()

    result = {"replay_rows": replay_rows, "draw_counts": {}}
    for row in draw_counts:
        result["draw_counts"][row[0]] = {"count": row[1], "max_draw": row[2]}
    return result


# ── Artifact loaders ──────────────────────────────────────────────────────────
def load_artifact(path: str, label: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{label} artifact not found: {path}")
    with open(p) as f:
        return json.load(f)


# ── Evidence extraction ───────────────────────────────────────────────────────
def extract_p112_evidence(p112: dict) -> dict:
    """Extract fourier30_markov30_biglotto entry from P112."""
    for entry in p112.get("per_strategy_results", []):
        if entry.get("strategy_id") == TARGET_STRATEGY_ID:
            return {
                "strategy_id": entry["strategy_id"],
                "lottery_type": entry.get("lottery_type"),
                "classification": entry.get("classification"),
                "edge_vs_baseline": entry.get("edge_vs_baseline"),
                "primary_metric_value": entry.get("primary_metric_value"),
                "baseline_metric_value": entry.get("baseline_metric_value"),
                "replay_rows": entry.get("replay_rows"),
                "recommendation": entry.get("recommendation"),
                "sample_size_status": entry.get("sample_size_status"),
            }
    return {"strategy_id": TARGET_STRATEGY_ID, "classification": "NOT_FOUND", "note": "Strategy not found in P112 per_strategy_results"}


def extract_p113_evidence(p113: dict) -> dict:
    """Extract fourier30_markov30_biglotto entry from P113."""
    for entry in p113.get("per_strategy_action_matrix", []):
        if entry.get("strategy_id") == TARGET_STRATEGY_ID:
            return {
                "strategy_id": entry["strategy_id"],
                "lottery_type": entry.get("lottery_type"),
                "p112_classification": entry.get("p112_classification"),
                "p113_action": entry.get("p113_action"),
                "promotion_authorized": entry.get("promotion_authorized"),
                "edge_vs_baseline": entry.get("edge_vs_baseline"),
                "rationale": entry.get("rationale"),
                "next_task_candidate": entry.get("next_task_candidate"),
            }
    return {"strategy_id": TARGET_STRATEGY_ID, "p113_action": "NOT_FOUND", "note": "Strategy not found in P113 per_strategy_action_matrix"}


def extract_p114_evidence(p114: dict) -> dict:
    """Extract fourier30_markov30_biglotto entry from P114."""
    for entry in p114.get("per_strategy_temporal_results", []):
        if entry.get("strategy_id") == TARGET_STRATEGY_ID:
            windows = entry.get("windows", {})
            negative_count = sum(
                1 for w in windows.values()
                if isinstance(w, dict) and w.get("positive_edge") is False
            )
            total_count = len([w for w in windows.values() if isinstance(w, dict) and "positive_edge" in w])
            return {
                "strategy_id": entry["strategy_id"],
                "lottery_type": entry.get("lottery_type"),
                "stability_label": entry.get("stability_label"),
                "p114_decision": entry.get("p114_decision"),
                "p112_classification": entry.get("p112_classification"),
                "p113_action": entry.get("p113_action"),
                "replay_rows": entry.get("replay_rows"),
                "rationale": entry.get("rationale"),
                "promotion_authorized": entry.get("promotion_authorized"),
                "next_task_candidate": entry.get("next_task_candidate"),
                "temporal_window_negative_count": negative_count,
                "temporal_window_total_count": total_count,
                "windows": windows,
            }
    return {
        "strategy_id": TARGET_STRATEGY_ID,
        "stability_label": "NOT_FOUND",
        "p114_decision": "NOT_FOUND",
        "note": "Strategy not found in P114 per_strategy_temporal_results",
        "temporal_window_negative_count": 0,
        "temporal_window_total_count": 0,
    }


# ── Quarantine governance design builder ──────────────────────────────────────
def build_quarantine_governance_design(p112_ev: dict, p113_ev: dict, p114_ev: dict) -> dict:
    """
    Build the quarantine governance design for fourier30_markov30_biglotto.
    Design-only. No production state is mutated.
    """
    all_evidence_present = (
        p112_ev.get("classification") == "SUB_BASELINE"
        and p113_ev.get("p113_action") == "DEMOTE_OR_QUARANTINE_CANDIDATE"
        and p114_ev.get("stability_label") == "STABLE_NEGATIVE"
        and p114_ev.get("p114_decision") == "READY_FOR_QUARANTINE_GOVERNANCE"
        and p114_ev.get("temporal_window_negative_count", 0) >= 3
    )

    quarantine_status = "GOVERNANCE_READY" if all_evidence_present else "GOVERNANCE_PARTIAL"

    return {
        "quarantine_status": quarantine_status,
        "production_quarantine_applied": False,
        "recommended_operator_label": "STABLE_NEGATIVE_QUARANTINE_CANDIDATE",
        "recommended_catalog_disclosure": (
            "Strategy has persistent negative edge across all temporal windows "
            "(first_third, middle_third, last_third, rolling_100, rolling_250). "
            "P112 classified as SUB_BASELINE (edge=-0.013361 vs hypergeometric baseline=0.734694). "
            "P113 action=DEMOTE_OR_QUARANTINE_CANDIDATE. "
            "P114 stability=STABLE_NEGATIVE across 5/5 temporal windows. "
            "Keep visible in catalog but label as not recommended for active use. "
            "Do not promote. Actual quarantine requires explicit future authorization."
        ),
        "future_quarantine_authorization_required": True,
        "future_authorization_phrase": (
            "YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence"
        ),
        "minimum_evidence_required_before_actual_quarantine": [
            "P112 classification is SUB_BASELINE or equivalent negative classification",
            "P113 action is DEMOTE_OR_QUARANTINE_CANDIDATE",
            "P114 stability_label is STABLE_NEGATIVE",
            "Negative edge appears across at least 3 major temporal windows",
            "DB invariants unchanged (replay_rows=54462)",
            "No source_unknown or data drift issue explains the negative result",
            "Explicit user authorization is present using the authorized phrase",
            "A separate lifecycle mutation artifact has been produced and reviewed",
        ],
        "future_quarantine_action_requirements": [
            "Must NOT delete replay rows",
            "Must NOT rewrite historical predictions",
            "Must NOT alter DB without explicit DB mutation authorization",
            "Must produce a separate lifecycle mutation artifact before any mutation",
            "Must update catalog/operator disclosure if and only if separately authorized",
            "Must re-run DB invariant verification before and after any mutation",
            "Must re-run both guards (lifecycle drift + branch governance) after any mutation",
        ],
        "evidence_satisfied": all_evidence_present,
        "evidence_gaps": [] if all_evidence_present else [
            f"P112 classification={p112_ev.get('classification')} (expected SUB_BASELINE)",
            f"P113 action={p113_ev.get('p113_action')} (expected DEMOTE_OR_QUARANTINE_CANDIDATE)",
            f"P114 stability_label={p114_ev.get('stability_label')} (expected STABLE_NEGATIVE)",
            f"P114 decision={p114_ev.get('p114_decision')} (expected READY_FOR_QUARANTINE_GOVERNANCE)",
            f"Negative window count={p114_ev.get('temporal_window_negative_count',0)} (expected >=3)",
        ] if not all_evidence_present else [],
    }


def build_pass_hold_quarantine_criteria() -> dict:
    """Define PASS / HOLD / QUARANTINE_CANDIDATE decision criteria."""
    return {
        "pass": {
            "label": "PASS",
            "description": "Strategy no longer shows negative edge after a future re-test.",
            "criteria": [
                "A future temporal audit shows positive edge across majority of windows",
                "P112 reclassification from SUB_BASELINE to ABOVE_BASELINE or WATCHLIST_CANDIDATE",
                "P113 action upgraded from DEMOTE_OR_QUARANTINE_CANDIDATE",
            ],
            "action": "Do not quarantine. Return to observation or watchlist queue.",
        },
        "hold": {
            "label": "HOLD",
            "description": "Evidence is mixed or insufficient. Continue observation only.",
            "criteria": [
                "Mixed temporal windows (some positive, some negative)",
                "Insufficient replay rows for reliable temporal split",
                "Data quality concerns (source_unknown or drift issues)",
                "P113 action is OBSERVATION_QUEUE or CONTINUE_OBSERVATION",
            ],
            "action": "Do not quarantine yet. Schedule re-audit after more data.",
        },
        "quarantine_candidate": {
            "label": "QUARANTINE_CANDIDATE",
            "description": "Persistent negative edge across major windows. Full evidence chain supports demotion/quarantine candidate.",
            "criteria": [
                "P112 classification is SUB_BASELINE",
                "P113 action is DEMOTE_OR_QUARANTINE_CANDIDATE",
                "P114 stability_label is STABLE_NEGATIVE",
                "Negative edge across at least 3 of 5 temporal windows",
                "DB invariants unchanged",
                "No data quality issue explains the negative result",
            ],
            "action": "Designate as quarantine candidate. Explicit future authorization still required before actual lifecycle mutation.",
            "current_assessment": "fourier30_markov30_biglotto meets QUARANTINE_CANDIDATE criteria as of P115.",
        },
    }


def build_global_invariants() -> list:
    return [
        "No DB write in this task (db_writes=false)",
        "No replay row insert or delete",
        "No historical artifact rewrite (P98-P116 artifacts are immutable)",
        "No lifecycle mutation without explicit future authorization and separate lifecycle mutation artifact",
        "No catalog label mutation without explicit future authorization",
        "No strategy promotion",
        "No 4_STAR backtest (unauthorized, source unknown)",
        "No Special3 P108 re-evaluation (blocked until 37 more 3_STAR draws = 100 prospective total)",
        "No POWER_LOTTO P117 OOS execution (separate task scope)",
        "No registry mutation",
        "DB opened read-only via mode=ro URI",
    ]


def build_next_task_recommendations() -> list:
    return [
        {
            "task_id": "P117",
            "description": "POWER_LOTTO OOS monitoring execution checkpoint",
            "lottery_type": "POWER_LOTTO",
            "priority": "HIGH",
            "prerequisite": "New POWER_LOTTO draws must be available (>=30 draws after P116 design date)",
            "blocked": False,
        },
        {
            "task_id": "P118",
            "description": "fourier30_markov30_biglotto actual quarantine execution (lifecycle mutation)",
            "lottery_type": "BIG_LOTTO",
            "priority": "MEDIUM",
            "prerequisite": "Explicit user authorization phrase: 'YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence'. Separate lifecycle mutation artifact required.",
            "blocked": True,
            "block_reason": "Awaiting explicit user authorization and separate lifecycle mutation artifact",
        },
        {
            "task_id": "P108",
            "description": "Special3 100-draw prospective re-evaluation",
            "lottery_type": "3_STAR",
            "priority": "LOW",
            "prerequisite": "37 more 3_STAR prospective draws needed (63/100 as of P107A)",
            "blocked": True,
            "block_reason": "Only 63/100 prospective draws available. Need 37 more.",
        },
    ]


def build_limitations() -> list:
    return [
        "This task is governance-design-only. No production state was changed.",
        "No actual quarantine was applied to fourier30_markov30_biglotto.",
        "No lifecycle, champion, or registry metadata was mutated.",
        "BIG_LOTTO hypergeometric baseline (0.734694) derived from replay data; prize-tier weighting not applied.",
        "Temporal window analysis covers historical replay rows only; prospective performance may differ.",
        "4_STAR strategies excluded from all analysis (source unknown, backtest unauthorized).",
        "Special3/3_STAR strategies excluded (P108 blocked until 100 prospective draws).",
        "POWER_LOTTO P117 OOS execution is a separate task; no OOS draws were consumed here.",
        "Source_unknown caveat for 4_STAR rows is preserved; this audit does not resolve it.",
        "The recommended_catalog_disclosure is advisory only; actual catalog mutation requires separate authorization.",
    ]


# ── Artifact builder ──────────────────────────────────────────────────────────
def build_artifact(
    p112: dict,
    p113: dict,
    p114: dict,
    p116: dict,
    db_invariants: dict,
) -> dict:
    replay_rows = db_invariants["replay_rows"]

    p112_ev = extract_p112_evidence(p112)
    p113_ev = extract_p113_evidence(p113)
    p114_ev = extract_p114_evidence(p114)

    governance_design = build_quarantine_governance_design(p112_ev, p113_ev, p114_ev)

    all_evidence_ok = governance_design.get("evidence_satisfied", False)
    classification = (
        "P115_BIGLOTTO_QUARANTINE_GOVERNANCE_READY"
        if all_evidence_ok
        else "P115_BIGLOTTO_QUARANTINE_GOVERNANCE_PARTIAL"
    )

    negative_evidence_summary = {
        "p112_classification": p112_ev.get("classification"),
        "p112_edge_vs_baseline": p112_ev.get("edge_vs_baseline"),
        "p112_primary_metric_value": p112_ev.get("primary_metric_value"),
        "p112_baseline_metric_value": p112_ev.get("baseline_metric_value"),
        "p113_action": p113_ev.get("p113_action"),
        "p113_rationale": p113_ev.get("rationale"),
        "p114_stability_label": p114_ev.get("stability_label"),
        "p114_decision": p114_ev.get("p114_decision"),
        "temporal_window_negative_count": p114_ev.get("temporal_window_negative_count", 0),
        "temporal_window_total_count": p114_ev.get("temporal_window_total_count", 0),
        "all_windows_negative": p114_ev.get("temporal_window_negative_count", 0) == p114_ev.get("temporal_window_total_count", 5),
        "temporal_windows": p114_ev.get("windows", {}),
    }

    return {
        "classification": classification,
        "task_id": "P115_BIGLOTTO_QUARANTINE_GOVERNANCE",
        "generated_date": "2026-05-27",
        "p112_reference": {
            "classification": p112.get("classification"),
            "artifact_path": P112_ARTIFACT,
            "task_id": p112.get("task_id"),
        },
        "p113_reference": {
            "classification": p113.get("classification"),
            "artifact_path": P113_ARTIFACT,
            "task_id": p113.get("task_id"),
        },
        "p114_reference": {
            "classification": p114.get("classification"),
            "artifact_path": P114_ARTIFACT,
            "task_id": p114.get("task_id"),
        },
        "p116_reference": {
            "classification": p116.get("classification"),
            "artifact_path": P116_ARTIFACT,
            "task_id": p116.get("task_id"),
        },
        "db_writes": False,
        "replay_rows_before": EXPECTED_REPLAY_ROWS,
        "replay_rows_after": replay_rows,
        "no_strategy_promotion": True,
        "no_lifecycle_mutation": True,
        "no_registry_mutation": True,
        "no_actual_quarantine_applied": True,
        "no_replay_row_delete": True,
        "no_4star_backtest": True,
        "no_special3_p108_rerun": True,
        "no_powerlotto_p117_execution": True,
        "source_unknown_caveat_preserved": True,
        "target_lottery_type": TARGET_LOTTERY_TYPE,
        "target_strategy_id": TARGET_STRATEGY_ID,
        "negative_evidence_summary": negative_evidence_summary,
        "quarantine_governance_design": governance_design,
        "pass_hold_quarantine_candidate_criteria": build_pass_hold_quarantine_criteria(),
        "global_invariants": build_global_invariants(),
        "next_task_recommendations": build_next_task_recommendations(),
        "limitations": build_limitations(),
        "final_classification": classification,
    }


# ── Summary printer ───────────────────────────────────────────────────────────
def print_summary(artifact: dict) -> None:
    ev = artifact.get("negative_evidence_summary", {})
    design = artifact.get("quarantine_governance_design", {})

    print("=" * 70)
    print("P115: BIG_LOTTO QUARANTINE GOVERNANCE DESIGN")
    print("=" * 70)
    print(f"Classification        : {artifact['classification']}")
    print(f"Target strategy       : {artifact['target_strategy_id']}")
    print(f"Target lottery        : {artifact['target_lottery_type']}")
    print()
    print("=== NEGATIVE EVIDENCE SUMMARY ===")
    print(f"  P112 classification : {ev.get('p112_classification')}")
    print(f"  P112 edge           : {ev.get('p112_edge_vs_baseline')}")
    print(f"  P113 action         : {ev.get('p113_action')}")
    print(f"  P114 stability      : {ev.get('p114_stability_label')}")
    print(f"  P114 decision       : {ev.get('p114_decision')}")
    print(f"  Negative windows    : {ev.get('temporal_window_negative_count')}/{ev.get('temporal_window_total_count')}")
    windows = ev.get("temporal_windows", {})
    for wname, wdata in windows.items():
        if isinstance(wdata, dict):
            edge = wdata.get("edge_vs_baseline", "?")
            pos = wdata.get("positive_edge", "?")
            print(f"    {wname:15s}: edge={edge:+.6f}  positive={pos}")
    print()
    print("=== QUARANTINE GOVERNANCE DESIGN ===")
    print(f"  quarantine_status   : {design.get('quarantine_status')}")
    print(f"  production_quarantine_applied: {design.get('production_quarantine_applied')}")
    print(f"  recommended_label   : {design.get('recommended_operator_label')}")
    print(f"  future_auth_required: {design.get('future_quarantine_authorization_required')}")
    print(f"  evidence_satisfied  : {design.get('evidence_satisfied')}")
    print()
    print("=== AUTHORIZATION PHRASE ===")
    print(f"  '{design.get('future_authorization_phrase')}'")
    print()
    print("=== GOVERNANCE FLAGS ===")
    print(f"  db_writes                  : {artifact['db_writes']}")
    print(f"  no_actual_quarantine_applied: {artifact['no_actual_quarantine_applied']}")
    print(f"  no_replay_row_delete       : {artifact['no_replay_row_delete']}")
    print(f"  no_lifecycle_mutation      : {artifact['no_lifecycle_mutation']}")
    print(f"  replay_rows_before         : {artifact['replay_rows_before']}")
    print(f"  replay_rows_after          : {artifact['replay_rows_after']}")
    print()
    print(f"Final classification: {artifact['final_classification']}")
    print("=" * 70)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="P115: BIG_LOTTO Quarantine Governance Design")
    parser.add_argument("--json-out", required=True, help="Path to write JSON artifact")
    parser.add_argument("--db", default=None, help="Absolute path to SQLite DB")
    parser.add_argument("--p112-artifact", default=P112_ARTIFACT)
    parser.add_argument("--p113-artifact", default=P113_ARTIFACT)
    parser.add_argument("--p114-artifact", default=P114_ARTIFACT)
    parser.add_argument("--p116-artifact", default=P116_ARTIFACT)
    args = parser.parse_args()

    # Load artifacts
    p112 = load_artifact(args.p112_artifact, "P112")
    p113 = load_artifact(args.p113_artifact, "P113")
    p114 = load_artifact(args.p114_artifact, "P114")
    p116 = load_artifact(args.p116_artifact, "P116")

    # Verify DB invariants (read-only)
    db_invariants = verify_db_invariants(args.db)

    # Build artifact
    artifact = build_artifact(p112, p113, p114, p116, db_invariants)

    # Write JSON
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)

    print_summary(artifact)
    print(f"\nJSON artifact written: {out_path}")
    print(f"Classification: {artifact['classification']}")


if __name__ == "__main__":
    main()
