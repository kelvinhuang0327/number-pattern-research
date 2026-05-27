#!/usr/bin/env python3
"""
P114: Temporal Stability Audit — read-only.

Loads P112 and P113 artifacts, queries existing replay rows to compute
chronological window-based edge stability for each candidate strategy.
Writes a JSON artifact to --json-out. No DB writes.
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH_DEFAULT = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P112_ARTIFACT_DEFAULT = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p112_cross_lottery_prediction_helpfulness_audit_20260527.json"
)
P113_ARTIFACT_DEFAULT = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p113_p112_action_decision_matrix_20260527.json"
)

EXPECTED_REPLAY_ROWS = 54462

ALLOWED_STABILITY_LABELS = {
    "STABLE_POSITIVE",
    "MOSTLY_POSITIVE",
    "MIXED",
    "UNSTABLE",
    "STABLE_NEGATIVE",
    "INSUFFICIENT_WINDOW_DATA",
}

ALLOWED_P114_DECISIONS = {
    "READY_FOR_OOS_MONITORING_DESIGN",
    "READY_FOR_CONTROLLED_OBSERVATION_PLAN",
    "HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE",
    "KEEP_IN_OBSERVATION_AND_RETEST",
    "READY_FOR_QUARANTINE_GOVERNANCE",
    "HOLD_FOR_MORE_DATA",
    "NO_ACTION",
}

VALID_CLASSIFICATIONS = {
    "P114_TEMPORAL_STABILITY_AUDIT_READY",
    "P114_TEMPORAL_STABILITY_AUDIT_PARTIAL",
    "P114_TEMPORAL_STABILITY_AUDIT_INCONCLUSIVE",
    "P114_BLOCKED_BY_PREFLIGHT",
    "P114_BLOCKED_BY_DB_DRIFT",
    "P114_BLOCKED_BY_GUARD_FAILURE",
    "P114_BLOCKED_BY_TEST_FAILURE",
    "P114_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P114_BLOCKED_BY_SCOPE_VIOLATION",
    "P114_BLOCKED_BY_CONTEXT_CONTAMINATION",
}

# Minimum rows per strategy for meaningful temporal windows
MIN_ROWS_FOR_WINDOWS = 90


def load_artifact(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def open_db_readonly(db_path: str):
    """Open SQLite in read-only mode via URI."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def verify_db_invariants(db_path: str) -> int:
    conn = open_db_readonly(db_path)
    try:
        replay_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    if replay_rows != EXPECTED_REPLAY_ROWS:
        raise RuntimeError(
            f"DB invariant violated: replay_rows={replay_rows}, expected={EXPECTED_REPLAY_ROWS}"
        )
    return replay_rows


def load_strategy_replays(db_path: str, strategy_id: str, lottery_type: str) -> list:
    """Load PREDICTED replay rows for a strategy sorted chronologically by target_draw."""
    conn = open_db_readonly(db_path)
    try:
        rows = conn.execute(
            "SELECT CAST(target_draw AS INTEGER) AS draw_int, hit_count, special_hit "
            "FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND lottery_type=? AND replay_status='PREDICTED' "
            "ORDER BY draw_int ASC",
            (strategy_id, lottery_type),
        ).fetchall()
    finally:
        conn.close()
    return rows  # list of (draw_int, hit_count, special_hit)


def compute_window_stats(rows: list, baseline: float) -> dict:
    """Compute per-window edge stats."""
    if not rows:
        return {
            "row_count": 0,
            "avg_hit_count": None,
            "baseline_avg_hit_count": None,
            "edge_vs_baseline": None,
            "positive_edge": None,
        }
    n = len(rows)
    avg_hit = sum(r[1] for r in rows) / n
    avg_special = sum(r[2] for r in rows) / n
    edge = avg_hit - baseline
    return {
        "row_count": n,
        "avg_hit_count": round(avg_hit, 6),
        "avg_special_hit": round(avg_special, 6),
        "baseline_avg_hit_count": round(baseline, 6),
        "edge_vs_baseline": round(edge, 6),
        "positive_edge": bool(edge > 0),
    }


def assign_stability_label(
    first_third: dict, middle_third: dict, last_third: dict, total_rows: int
) -> str:
    """Assign stability label from three chronological window edges."""
    if total_rows < MIN_ROWS_FOR_WINDOWS:
        return "INSUFFICIENT_WINDOW_DATA"

    edges = []
    for w in (first_third, middle_third, last_third):
        ev = w.get("edge_vs_baseline")
        if ev is not None:
            edges.append(ev)

    if len(edges) < 3:
        return "INSUFFICIENT_WINDOW_DATA"

    positive_count = sum(1 for e in edges if e > 0)

    if positive_count == 3:
        return "STABLE_POSITIVE"
    elif positive_count == 2:
        return "MOSTLY_POSITIVE"
    elif positive_count == 0:
        return "STABLE_NEGATIVE"
    else:
        # positive_count == 1 — check if concentrated (unstable) or just mixed
        max_edge = max(edges)
        abs_edges = [abs(e) for e in edges]
        mean_abs = sum(abs_edges) / len(abs_edges) if abs_edges else 0
        # Unstable if the one positive window dominates by >50% of mean absolute magnitude
        if mean_abs > 0 and abs(max_edge) > 1.5 * mean_abs:
            return "UNSTABLE"
        return "MIXED"


def assign_p114_decision(p113_action: str, stability_label: str) -> str:
    """Map (p113_action, stability_label) → p114_decision per spec rules."""
    if stability_label == "INSUFFICIENT_WINDOW_DATA":
        return "HOLD_FOR_MORE_DATA"

    if p113_action == "WATCHLIST_QUEUE":
        if stability_label == "STABLE_POSITIVE":
            return "READY_FOR_OOS_MONITORING_DESIGN"
        elif stability_label == "MOSTLY_POSITIVE":
            return "READY_FOR_CONTROLLED_OBSERVATION_PLAN"
        else:
            return "HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE"

    elif p113_action in ("OBSERVATION_QUEUE", "CONTINUE_OBSERVATION"):
        if stability_label in ("STABLE_POSITIVE", "MOSTLY_POSITIVE"):
            return "KEEP_IN_OBSERVATION_AND_RETEST"
        elif stability_label == "STABLE_NEGATIVE":
            return "READY_FOR_QUARANTINE_GOVERNANCE"
        else:
            return "KEEP_IN_OBSERVATION_AND_RETEST"

    elif p113_action == "DEMOTE_OR_QUARANTINE_CANDIDATE":
        if stability_label == "STABLE_NEGATIVE":
            return "READY_FOR_QUARANTINE_GOVERNANCE"
        else:
            return "HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE"

    elif p113_action == "FALLBACK_DISCLOSURE_CANDIDATE":
        if stability_label == "STABLE_NEGATIVE":
            return "READY_FOR_QUARANTINE_GOVERNANCE"
        else:
            return "KEEP_IN_OBSERVATION_AND_RETEST"

    elif p113_action == "HOLD_FOR_MORE_DATA":
        return "HOLD_FOR_MORE_DATA"

    return "NO_ACTION"


def next_task_for_decision(decision: str):
    return {
        "READY_FOR_OOS_MONITORING_DESIGN": "P116",
        "READY_FOR_CONTROLLED_OBSERVATION_PLAN": "P116",
        "READY_FOR_QUARANTINE_GOVERNANCE": "P115",
    }.get(decision)


def audit_strategy(db_path: str, strategy_info: dict, p112_map: dict) -> dict:
    """Compute temporal stability for one strategy."""
    strategy_id = strategy_info["strategy_id"]
    lottery_type = strategy_info["lottery_type"]
    p113_action = strategy_info["p113_action"]
    p112_classification = strategy_info.get("p112_classification", "UNKNOWN")

    p112_entry = p112_map.get((strategy_id, lottery_type))
    baseline = p112_entry["baseline_metric_value"] if p112_entry else None

    if baseline is None:
        return {
            "strategy_id": strategy_id,
            "lottery_type": lottery_type,
            "p113_action": p113_action,
            "p112_classification": p112_classification,
            "replay_rows": 0,
            "windows": {},
            "stability_label": "INSUFFICIENT_WINDOW_DATA",
            "p114_decision": "HOLD_FOR_MORE_DATA",
            "promotion_authorized": False,
            "rationale": "No P112 baseline available for this strategy.",
            "next_task_candidate": None,
        }

    rows = load_strategy_replays(db_path, strategy_id, lottery_type)
    n = len(rows)

    # Chronological thirds
    t1 = n // 3
    t2 = 2 * (n // 3)
    first_third_rows = rows[:t1]
    middle_third_rows = rows[t1:t2]
    last_third_rows = rows[t2:]

    first_stats = compute_window_stats(first_third_rows, baseline)
    middle_stats = compute_window_stats(middle_third_rows, baseline)
    last_stats = compute_window_stats(last_third_rows, baseline)

    windows: dict = {
        "first_third": first_stats,
        "middle_third": middle_stats,
        "last_third": last_stats,
    }

    # Optional rolling windows
    if n >= 100:
        windows["rolling_100"] = compute_window_stats(rows[-100:], baseline)
    if n >= 250:
        windows["rolling_250"] = compute_window_stats(rows[-250:], baseline)

    stability_label = assign_stability_label(first_stats, middle_stats, last_stats, n)
    p114_decision = assign_p114_decision(p113_action, stability_label)

    edges_str = " | ".join(
        f"{k}={v['edge_vs_baseline']:+.4f}"
        for k, v in windows.items()
        if k in ("first_third", "middle_third", "last_third")
        and v.get("edge_vs_baseline") is not None
    )
    rationale = (
        f"P113 action={p113_action}. Chronological thirds edge: [{edges_str}]. "
        f"Stability={stability_label}. baseline={baseline:.6f}. rows={n}."
    )

    return {
        "strategy_id": strategy_id,
        "lottery_type": lottery_type,
        "p113_action": p113_action,
        "p112_classification": p112_classification,
        "replay_rows": n,
        "windows": windows,
        "stability_label": stability_label,
        "p114_decision": p114_decision,
        "promotion_authorized": False,
        "rationale": rationale,
        "next_task_candidate": next_task_for_decision(p114_decision),
    }


def build_artifact(
    p112: dict,
    p113: dict,
    results: list,
    replay_rows_before: int,
    replay_rows_after: int,
) -> dict:
    oos_candidates = [
        r["strategy_id"]
        for r in results
        if r["p114_decision"] == "READY_FOR_OOS_MONITORING_DESIGN"
    ]
    controlled_candidates = [
        r["strategy_id"]
        for r in results
        if r["p114_decision"] == "READY_FOR_CONTROLLED_OBSERVATION_PLAN"
    ]
    quarantine_candidates = [
        r["strategy_id"]
        for r in results
        if r["p114_decision"] == "READY_FOR_QUARANTINE_GOVERNANCE"
    ]
    hold_candidates = [
        r["strategy_id"]
        for r in results
        if r["p114_decision"] == "HOLD_FOR_MORE_DATA"
    ]

    stability_counts: dict = {}
    decision_counts: dict = {}
    for r in results:
        sl = r["stability_label"]
        stability_counts[sl] = stability_counts.get(sl, 0) + 1
        d = r["p114_decision"]
        decision_counts[d] = decision_counts.get(d, 0) + 1

    # Classification: PARTIAL if any strategy has INSUFFICIENT_WINDOW_DATA, else READY
    has_insufficient = any(
        r["stability_label"] == "INSUFFICIENT_WINDOW_DATA" for r in results
    )
    final_classification = (
        "P114_TEMPORAL_STABILITY_AUDIT_PARTIAL"
        if has_insufficient
        else "P114_TEMPORAL_STABILITY_AUDIT_READY"
    )

    return {
        "classification": final_classification,
        "task_id": "P114_TEMPORAL_STABILITY_AUDIT",
        "audit_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "p112_reference": {
            "classification": p112.get("classification"),
            "artifact_path": "outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json",
        },
        "p113_reference": {
            "classification": p113.get("classification"),
            "artifact_path": "outputs/replay/p113_p112_action_decision_matrix_20260527.json",
        },
        "db_writes": False,
        "replay_rows_before": replay_rows_before,
        "replay_rows_after": replay_rows_after,
        "no_strategy_promotion": True,
        "no_lifecycle_mutation": True,
        "no_registry_mutation": True,
        "no_4star_backtest": True,
        "no_special3_p108_rerun": True,
        "source_unknown_caveat_preserved": True,
        "audited_lottery_types": ["POWER_LOTTO", "DAILY_539", "BIG_LOTTO"],
        "audited_strategy_count": len(results),
        "temporal_window_definitions": {
            "first_third": "First 1/3 of rows sorted by target_draw (chronologically earliest)",
            "middle_third": "Middle 1/3 of rows sorted by target_draw",
            "last_third": "Last 1/3 of rows sorted by target_draw (most recent)",
            "rolling_100": "Last 100 rows by target_draw (computed when total rows >= 100)",
            "rolling_250": "Last 250 rows by target_draw (computed when total rows >= 250)",
        },
        "per_strategy_temporal_results": results,
        "stability_label_distribution": stability_counts,
        "p114_decision_distribution": decision_counts,
        "oos_monitoring_candidates": oos_candidates,
        "controlled_observation_candidates": controlled_candidates,
        "quarantine_governance_candidates": quarantine_candidates,
        "hold_for_more_data_candidates": hold_candidates,
        "limitations": [
            "Temporal windows based on target_draw ordering (integer sort), not calendar time",
            "Baseline values carried from P112 (hypergeometric expectation per strategy)",
            "hit_count measures main number overlap only; prize-tier weighting not applied",
            "4_STAR backtest unauthorized; 4_STAR strategies excluded from this audit",
            "Special3/P106 evaluation excluded; P108 blocked until 100 prospective 3_STAR draws",
            "source_unknown caveat preserved from P112: draw data provenance unverified for some entries",
            "Stability labels derived from chronological thirds; calendar seasonality not modeled",
            "Window edges are point estimates; confidence intervals not computed in this pass",
        ],
        "explicit_holds": {
            "SPECIAL3_P108_HOLD": "P108 re-evaluation blocked until 37 more 3_STAR draws accumulated (63/100 so far)",
            "FOUR_STAR_BACKTEST_HOLD": "4_STAR backtest unauthorized; source_unknown caveat active",
            "NO_PRODUCTION_PROMOTION_FROM_P114": "P114 does not authorize any strategy promotion to production",
        },
        "final_classification": final_classification,
    }


def print_summary(artifact: dict) -> None:
    r = artifact
    print("\n" + "=" * 60)
    print("P114: Temporal Stability Audit")
    print("=" * 60)
    print(f"Audited strategies : {r['audited_strategy_count']}")
    print(f"Replay rows before : {r['replay_rows_before']}")
    print(f"Replay rows after  : {r['replay_rows_after']}")
    print(f"\nStability distribution:")
    for k, v in sorted(r["stability_label_distribution"].items()):
        print(f"  {k}: {v}")
    print(f"\nDecision distribution:")
    for k, v in sorted(r["p114_decision_distribution"].items()):
        print(f"  {k}: {v}")
    print(f"\nOOS monitoring candidates     : {r['oos_monitoring_candidates']}")
    print(f"Controlled obs. candidates    : {r['controlled_observation_candidates']}")
    print(f"Quarantine governance cand.   : {r['quarantine_governance_candidates']}")
    print(f"Hold for more data            : {r['hold_for_more_data_candidates']}")
    print(f"\nFinal classification: {r['final_classification']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P114: Temporal Stability Audit (read-only)"
    )
    parser.add_argument("--json-out", required=True, help="Path to write JSON artifact")
    parser.add_argument(
        "--p112-artifact",
        default=str(P112_ARTIFACT_DEFAULT),
        help="Path to P112 JSON artifact",
    )
    parser.add_argument(
        "--p113-artifact",
        default=str(P113_ARTIFACT_DEFAULT),
        help="Path to P113 JSON artifact",
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH_DEFAULT),
        help="Path to lottery_v2.db",
    )
    args = parser.parse_args()

    p112 = load_artifact(args.p112_artifact)
    p113 = load_artifact(args.p113_artifact)

    # Build P112 lookup: (strategy_id, lottery_type) → entry
    p112_map = {
        (s["strategy_id"], s["lottery_type"]): s
        for s in p112.get("per_strategy_results", [])
    }

    replay_rows_before = verify_db_invariants(args.db)

    results = [
        audit_strategy(args.db, s, p112_map)
        for s in p113.get("per_strategy_action_matrix", [])
    ]

    replay_rows_after = verify_db_invariants(args.db)

    artifact = build_artifact(p112, p113, results, replay_rows_before, replay_rows_after)

    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)

    print_summary(artifact)
    print(f"\nArtifact written: {args.json_out}")


if __name__ == "__main__":
    main()
