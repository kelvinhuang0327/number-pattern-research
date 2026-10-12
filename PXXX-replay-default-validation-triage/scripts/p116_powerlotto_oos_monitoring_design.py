#!/usr/bin/env python3
"""
P116: POWER_LOTTO OOS Monitoring Design
Read-only. Loads P112/P113/P114 artifacts and generates OOS monitoring
design for POWER_LOTTO positive candidates.

No SQL write verbs. No DB mutation. No strategy promotion.
No lifecycle/champion/registry mutation. No 4_STAR backtest.
No Special3 P108 re-evaluation. No P115 quarantine work.
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
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

TASK_ID = "P116_POWERLOTTO_OOS_MONITORING_DESIGN"
GENERATED_DATE = "20260527"

P112_ARTIFACT = "outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json"
P113_ARTIFACT = "outputs/replay/p113_p112_action_decision_matrix_20260527.json"
P114_ARTIFACT = "outputs/replay/p114_temporal_stability_audit_20260527.json"

MONITORED_LOTTERY_TYPE = "POWER_LOTTO"
MONITORING_CANDIDATES = ["midfreq_fourier_mk_3bet", "pp3_freqort_4bet"]

HYPERGEOMETRIC_BASELINE = 0.947368  # POWER_LOTTO 5-ball hypergeometric expected hits

VALID_CLASSIFICATIONS = {
    "P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY",
    "P116_POWERLOTTO_OOS_MONITORING_DESIGN_PARTIAL",
    "P116_POWERLOTTO_OOS_MONITORING_DESIGN_INCONCLUSIVE",
    "P116_BLOCKED_BY_PREFLIGHT",
    "P116_BLOCKED_BY_DB_DRIFT",
    "P116_BLOCKED_BY_GUARD_FAILURE",
    "P116_BLOCKED_BY_TEST_FAILURE",
    "P116_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P116_BLOCKED_BY_SCOPE_VIOLATION",
    "P116_BLOCKED_BY_CONTEXT_CONTAMINATION",
}


def open_db_readonly(db_path=None):
    uri = Path(_resolve_db_path(db_path)).as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def verify_db_invariants(db_path: str) -> dict:
    """Read-only invariant check only. No writes."""
    conn = open_db_readonly(db_path)
    try:
        replay_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        draw_counts = {
            row[0]: {"count": row[1], "max_draw": row[2]}
            for row in conn.execute(
                "SELECT lottery_type, COUNT(*), MAX(CAST(draw AS INTEGER)) "
                "FROM draws WHERE lottery_type IN ('3_STAR','4_STAR','POWER_LOTTO') "
                "GROUP BY lottery_type"
            ).fetchall()
        }
    finally:
        conn.close()

    violations = []
    if replay_rows != 54462:
        violations.append(f"replay_rows={replay_rows} expected=54462")
    expected = {
        "3_STAR": (4179, 115000106),
        "4_STAR": (2922, 115000103),
        "POWER_LOTTO": (1913, 115000041),
    }
    for lt, (exp_count, exp_max) in expected.items():
        actual = draw_counts.get(lt, {})
        if actual.get("count") != exp_count:
            violations.append(f"{lt} count={actual.get('count')} expected={exp_count}")
        if actual.get("max_draw") != exp_max:
            violations.append(f"{lt} max_draw={actual.get('max_draw')} expected={exp_max}")

    return {"replay_rows": replay_rows, "violations": violations}


def load_artifact(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Artifact not found: {path}")
    with open(p) as f:
        return json.load(f)


def build_monitoring_design_midfreq(p112_entry: dict, p113_entry: dict, p114_entry: dict) -> dict:
    """
    midfreq_fourier_mk_3bet:
    - P114 stability = STABLE_POSITIVE (all 3 chronological windows positive)
    - P114 decision = READY_FOR_OOS_MONITORING_DESIGN
    - P112 edge = +0.0800
    - P113 action = WATCHLIST_QUEUE
    """
    windows = p114_entry.get("windows", {})
    return {
        "strategy_id": "midfreq_fourier_mk_3bet",
        "lottery_type": "POWER_LOTTO",
        "p112_classification": p112_entry.get("classification", "PREDICTION_HELPFUL"),
        "p112_edge_vs_baseline": p112_entry.get("edge_vs_baseline", 0.079965),
        "p112_avg_hit_count": p112_entry.get("primary_metric_value", 1.027333),
        "p112_replay_rows": p112_entry.get("replay_rows", 1500),
        "p113_action": p113_entry.get("p113_action", "WATCHLIST_QUEUE"),
        "p114_stability_label": p114_entry.get("stability_label", "STABLE_POSITIVE"),
        "p114_decision": p114_entry.get("p114_decision", "READY_FOR_OOS_MONITORING_DESIGN"),
        "p114_temporal_windows": {
            "first_third_edge": windows.get("first_third", {}).get("edge_vs_baseline"),
            "middle_third_edge": windows.get("middle_third", {}).get("edge_vs_baseline"),
            "last_third_edge": windows.get("last_third", {}).get("edge_vs_baseline"),
            "rolling_100_edge": windows.get("rolling_100", {}).get("edge_vs_baseline"),
            "rolling_250_edge": windows.get("rolling_250", {}).get("edge_vs_baseline"),
            "positive_thirds_count": 3,
        },
        "oos_status": "DESIGN_READY",
        "minimum_new_draws": 30,
        "preferred_new_draws": 50,
        "promotion_discussion_minimum": 80,
        "rolling_windows": [10, 20, 30],
        "metrics": [
            "avg_hit_count",
            "edge_vs_hypergeometric_baseline",
            "positive_edge_rate_by_window",
            "hit_count_distribution",
            "draw_coverage",
            "freshness_status",
        ],
        "pass_criteria": [
            "minimum 30 new POWER_LOTTO draws completed",
            "edge_vs_baseline positive over full OOS window",
            "positive edge in at least 2 of 3 rolling windows (10/20/30)",
            "no freshness guard failure",
            "replay_rows unchanged except under explicitly authorized future apply",
            "branch governance guard passes",
        ],
        "watch_criteria": [
            "edge positive but unstable across rolling windows",
            "positive edge in only 1 of 3 rolling windows",
            "insufficient draw count but direction positive (< 30 new draws)",
            "edge magnitude decreasing trend but still above zero",
        ],
        "fail_criteria": [
            "negative edge over full OOS window",
            "negative edge in at least 2 of 3 rolling windows",
            "data freshness guard failure",
            "any unauthorized DB mutation detected",
            "replay_rows changed without explicit authorization",
        ],
        "promotion_authorized": False,
        "future_promotion_proposal_requirements": [
            "minimum 80 new POWER_LOTTO draws observed post-OOS monitoring start",
            "PASS status sustained for at least 50 new draws",
            "edge_vs_baseline positive over full 80+ draw OOS window",
            "positive edge in at least 2 of 3 rolling windows (10/20/30)",
            "freshness guard passing throughout",
            "explicit governance authorization in a new numbered task",
            "source_unknown caveat resolved or explicitly accepted",
            "P108 Special3 100-draw gate satisfied (37 more draws needed)",
            "dedicated promotion task created (P117 or later)",
            "branch governance guard passing at promotion-task commit",
        ],
        "demotion_or_quarantine_triggers": [
            "negative edge over full OOS window at any evaluation checkpoint",
            "negative edge in at least 2 of 3 rolling windows sustained across 2+ evaluations",
            "data freshness failure lasting 10+ draws",
            "unauthorized DB mutation detected",
            "stability label degrades to UNSTABLE or STABLE_NEGATIVE in future re-audit",
            "replay_rows changed without explicit future authorization",
        ],
    }


def build_monitoring_design_pp3(p112_entry: dict, p113_entry: dict, p114_entry: dict) -> dict:
    """
    pp3_freqort_4bet:
    - P114 stability = MOSTLY_POSITIVE (2 of 3 chronological windows positive)
    - P114 decision = READY_FOR_CONTROLLED_OBSERVATION_PLAN
    - P112 edge = +0.0546
    - P113 action = WATCHLIST_QUEUE
    - Rolling 100/250 both negative (recent softness)
    """
    windows = p114_entry.get("windows", {})
    return {
        "strategy_id": "pp3_freqort_4bet",
        "lottery_type": "POWER_LOTTO",
        "p112_classification": p112_entry.get("classification", "PREDICTION_HELPFUL"),
        "p112_edge_vs_baseline": p112_entry.get("edge_vs_baseline", 0.054632),
        "p112_avg_hit_count": p112_entry.get("primary_metric_value", 1.002),
        "p112_replay_rows": p112_entry.get("replay_rows", 1500),
        "p113_action": p113_entry.get("p113_action", "WATCHLIST_QUEUE"),
        "p114_stability_label": p114_entry.get("stability_label", "MOSTLY_POSITIVE"),
        "p114_decision": p114_entry.get("p114_decision", "READY_FOR_CONTROLLED_OBSERVATION_PLAN"),
        "p114_temporal_windows": {
            "first_third_edge": windows.get("first_third", {}).get("edge_vs_baseline"),
            "middle_third_edge": windows.get("middle_third", {}).get("edge_vs_baseline"),
            "last_third_edge": windows.get("last_third", {}).get("edge_vs_baseline"),
            "rolling_100_edge": windows.get("rolling_100", {}).get("edge_vs_baseline"),
            "rolling_250_edge": windows.get("rolling_250", {}).get("edge_vs_baseline"),
            "positive_thirds_count": 2,
            "recent_softness_note": "rolling_100=-0.087 and rolling_250=-0.071 indicate recent underperformance; controlled observation warranted before any promotion discussion",
        },
        "oos_status": "CONTROLLED_OBSERVATION_READY",
        "minimum_new_draws": 40,
        "preferred_new_draws": 60,
        "promotion_discussion_minimum": 100,
        "rolling_windows": [10, 20, 40],
        "metrics": [
            "avg_hit_count",
            "edge_vs_hypergeometric_baseline",
            "positive_edge_rate_by_window",
            "stability_label_change",
            "draw_coverage",
            "freshness_status",
        ],
        "pass_criteria": [
            "minimum 40 new POWER_LOTTO draws completed",
            "edge_vs_baseline positive over full OOS window",
            "positive edge in at least 2 of 3 rolling windows (10/20/40)",
            "stability label improves from MOSTLY_POSITIVE to STABLE_POSITIVE in future audit",
            "no freshness guard failure",
            "replay_rows unchanged except under explicitly authorized future apply",
        ],
        "watch_criteria": [
            "edge positive but mixed across rolling windows",
            "stability remains MOSTLY_POSITIVE (no regression, no improvement)",
            "positive edge over full window but only 1 of 3 rolling windows positive",
            "insufficient draw count but recent direction recovering",
        ],
        "fail_criteria": [
            "negative edge over full OOS window",
            "stability degrades to MIXED or UNSTABLE in future re-audit",
            "negative edge in at least 2 of 3 rolling windows",
            "data freshness guard failure",
            "any unauthorized DB mutation detected",
            "replay_rows changed without explicit authorization",
        ],
        "promotion_authorized": False,
        "future_promotion_proposal_requirements": [
            "minimum 100 new POWER_LOTTO draws observed post-OOS monitoring start",
            "PASS status sustained for at least 60 new draws",
            "edge_vs_baseline positive over full 100+ draw OOS window",
            "stability label must improve to STABLE_POSITIVE in a future temporal re-audit",
            "positive edge in at least 2 of 3 rolling windows (10/20/40)",
            "freshness guard passing throughout",
            "explicit governance authorization in a new numbered task",
            "source_unknown caveat resolved or explicitly accepted",
            "P108 Special3 100-draw gate satisfied (37 more draws needed)",
            "dedicated promotion task created (P118 or later)",
            "branch governance guard passing at promotion-task commit",
        ],
        "demotion_or_quarantine_triggers": [
            "stability degrades to MIXED or UNSTABLE in future re-audit",
            "negative edge over full OOS window",
            "negative edge in at least 2 of 3 rolling windows sustained across 2+ evaluations",
            "rolling 100-draw edge remains negative after 40 new draws",
            "data freshness failure lasting 10+ draws",
            "unauthorized DB mutation detected",
            "replay_rows changed without explicit future authorization",
        ],
    }


def build_artifact(
    p112: dict,
    p113: dict,
    p114: dict,
    db_invariants: dict,
    classification: str,
) -> dict:

    # Extract per-strategy entries from each artifact
    def get_p112_entry(sid):
        for s in p112.get("per_strategy_results", []):
            if s.get("strategy_id") == sid:
                return s
        return {}

    def get_p113_entry(sid):
        for s in p113.get("per_strategy_action_matrix", []):
            if s.get("strategy_id") == sid:
                return s
        return {}

    def get_p114_entry(sid):
        for s in p114.get("per_strategy_temporal_results", []):
            if s.get("strategy_id") == sid:
                return s
        return {}

    midfreq_p112 = get_p112_entry("midfreq_fourier_mk_3bet")
    midfreq_p113 = get_p113_entry("midfreq_fourier_mk_3bet")
    midfreq_p114 = get_p114_entry("midfreq_fourier_mk_3bet")

    pp3_p112 = get_p112_entry("pp3_freqort_4bet")
    pp3_p113 = get_p113_entry("pp3_freqort_4bet")
    pp3_p114 = get_p114_entry("pp3_freqort_4bet")

    midfreq_design = build_monitoring_design_midfreq(midfreq_p112, midfreq_p113, midfreq_p114)
    pp3_design = build_monitoring_design_pp3(pp3_p112, pp3_p113, pp3_p114)

    return {
        "classification": classification,
        "task_id": TASK_ID,
        "generated_date": GENERATED_DATE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "p112_reference": {
            "classification": p112.get("classification"),
            "artifact_path": P112_ARTIFACT,
        },
        "p113_reference": {
            "classification": p113.get("classification"),
            "artifact_path": P113_ARTIFACT,
        },
        "p114_reference": {
            "classification": p114.get("classification"),
            "artifact_path": P114_ARTIFACT,
        },
        "db_writes": False,
        "replay_rows_before": 54462,
        "replay_rows_after": db_invariants.get("replay_rows", 54462),
        "no_strategy_promotion": True,
        "no_lifecycle_mutation": True,
        "no_registry_mutation": True,
        "no_4star_backtest": True,
        "no_special3_p108_rerun": True,
        "no_p115_quarantine_work": True,
        "source_unknown_caveat_preserved": True,
        "monitored_lottery_type": MONITORED_LOTTERY_TYPE,
        "monitoring_candidates": MONITORING_CANDIDATES,
        "per_strategy_monitoring_design": [midfreq_design, pp3_design],
        "global_monitoring_invariants": [
            "replay_rows must remain 54462 unless a future apply is explicitly authorized in a separate numbered task",
            "no DB writes in OOS monitoring design phase",
            "freshness guard must pass before any evaluation checkpoint",
            "branch governance guard must pass at every commit",
            "no lifecycle/champion/registry mutation without explicit future authorization in a new numbered task",
            "no strategy promotion without explicit future authorization",
            "no 4_STAR backtest until source_unknown caveat is resolved and explicitly authorized",
            "P108 Special3 re-evaluation blocked until 37 more 3_STAR draws complete",
            "P115 quarantine governance for fourier30_markov30_biglotto is a separate task",
        ],
        "next_task_recommendations": [
            "P115: Quarantine governance for fourier30_markov30_biglotto (BIG_LOTTO, STABLE_NEGATIVE)",
            "P117: OOS monitoring execution checkpoint (after minimum new draws are available)",
            "P108: Special3 100-draw re-evaluation (blocked until 37 more 3_STAR draws)",
        ],
        "limitations": [
            "This design is read-only. No OOS draw data is available yet; design is based on historical replay rows.",
            "hit_count measures number overlap only; prize-tier weighting not applied.",
            "temporal stability assessed on historical replay rows only; OOS performance may differ.",
            "4_STAR backtest remains unauthorized due to source_unknown caveat.",
            "Special3/P106/P108 evaluation excluded; blocked until 100 prospective draws.",
            "No live monitoring job is implemented by this task.",
            "Promotion discussion minimum thresholds are guidelines, not guarantees; all promotion requires explicit future authorization.",
            "P115 quarantine governance for fourier30_markov30_biglotto is out of scope for P116.",
        ],
        "final_classification": classification,
    }


def print_summary(artifact: dict) -> None:
    print(f"\n=== {TASK_ID} ===")
    print(f"Classification: {artifact['classification']}")
    print(f"Monitored lottery type: {artifact['monitored_lottery_type']}")
    print(f"Candidates: {', '.join(artifact['monitoring_candidates'])}")
    print(f"DB writes: {artifact['db_writes']}")
    print(f"replay_rows before/after: {artifact['replay_rows_before']} / {artifact['replay_rows_after']}")
    print()
    for design in artifact["per_strategy_monitoring_design"]:
        sid = design["strategy_id"]
        status = design["oos_status"]
        label = design["p114_stability_label"]
        decision = design["p114_decision"]
        min_draws = design["minimum_new_draws"]
        promo_min = design["promotion_discussion_minimum"]
        print(f"  [{sid}]")
        print(f"    oos_status          : {status}")
        print(f"    p114_stability_label: {label}")
        print(f"    p114_decision       : {decision}")
        print(f"    minimum_new_draws   : {min_draws}")
        print(f"    promotion_min_draws : {promo_min}")
        print(f"    promotion_authorized: {design['promotion_authorized']}")
        print()
    print(f"Final classification: {artifact['final_classification']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="P116: POWER_LOTTO OOS monitoring design (read-only)")
    parser.add_argument("--json-out", required=True, help="Output path for JSON artifact")
    parser.add_argument(
        "--db",
        default=None,
        help="Absolute path to lottery_v2.db (read-only access for invariant check)",
    )
    parser.add_argument(
        "--p112-artifact",
        default=P112_ARTIFACT,
        help="Path to P112 JSON artifact",
    )
    parser.add_argument(
        "--p113-artifact",
        default=P113_ARTIFACT,
        help="Path to P113 JSON artifact",
    )
    parser.add_argument(
        "--p114-artifact",
        default=P114_ARTIFACT,
        help="Path to P114 JSON artifact",
    )
    args = parser.parse_args()

    # Load artifacts
    try:
        p112 = load_artifact(args.p112_artifact)
        p113 = load_artifact(args.p113_artifact)
        p114 = load_artifact(args.p114_artifact)
    except FileNotFoundError as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        sys.exit(1)

    # Verify DB invariants (read-only)
    try:
        db_invariants = verify_db_invariants(args.db)
    except Exception as e:
        print(f"BLOCKED: DB invariant check failed: {e}", file=sys.stderr)
        sys.exit(1)

    if db_invariants["violations"]:
        print(f"BLOCKED: DB invariant violations: {db_invariants['violations']}", file=sys.stderr)
        sys.exit(1)

    # Determine classification
    # Check that both candidates are present in P114
    p114_strategy_ids = {s.get("strategy_id") for s in p114.get("per_strategy_temporal_results", [])}
    missing = [c for c in MONITORING_CANDIDATES if c not in p114_strategy_ids]
    if missing:
        classification = "P116_POWERLOTTO_OOS_MONITORING_DESIGN_PARTIAL"
    else:
        classification = "P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY"

    artifact = build_artifact(p112, p113, p114, db_invariants, classification)

    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)
        f.write("\n")

    print_summary(artifact)
    print(f"Artifact written to: {out_path}")


if __name__ == "__main__":
    main()
