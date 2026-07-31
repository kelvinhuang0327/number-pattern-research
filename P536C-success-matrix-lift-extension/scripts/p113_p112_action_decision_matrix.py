#!/usr/bin/env python3
"""
P113: P112 Action Decision Matrix
Read-only script. Loads P112 JSON artifact and builds governance decision matrix.
No DB writes. No strategy promotion. No lifecycle mutation.
"""
import argparse
import json
import sqlite3
from pathlib import Path

TASK_ID = "P113_P112_ACTION_DECISION_MATRIX"
P112_ARTIFACT = "outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json"
DB_PATH = "lottery_api/data/lottery_v2.db"
EXPECTED_REPLAY_ROWS = 54462

# Forbidden SQL write verbs (for script self-validation)
FORBIDDEN_SQL_VERBS = [
    "INSERT", "UPDATE", "DELETE", "CREATE", "DROP",
    "ALTER", "REPLACE", "VACUUM", "PRAGMA writable_schema",
]

ACTION_DEFINITIONS = {
    "WATCHLIST_QUEUE": (
        "Strategy has demonstrated prediction edge above baseline (PREDICTION_HELPFUL). "
        "Queue for controlled OOS monitoring design. Promotion NOT authorized from P112/P113 alone."
    ),
    "OBSERVATION_QUEUE": (
        "Strategy shows positive edge vs baseline but requires more evidence (WATCHLIST_CANDIDATE). "
        "Continue accumulating data; eligible for Wave-N targeted observation planning."
    ),
    "CONTINUE_OBSERVATION": (
        "Strategy is classified OBSERVE_MORE. Sample size or stability insufficient to judge. "
        "No action beyond passive monitoring."
    ),
    "DEMOTE_OR_QUARANTINE_CANDIDATE": (
        "Strategy is SUB_BASELINE. Performs below random baseline. "
        "Candidate for demotion or quarantine in future governance task. Not auto-demoted here."
    ),
    "FALLBACK_DISCLOSURE_CANDIDATE": (
        "Strategy is FALLBACK_EQUIVALENT. Statistically indistinguishable from random. "
        "Should be disclosed as fallback-only when used in production. No active promotion."
    ),
    "HOLD_FOR_MORE_DATA": (
        "Strategy is INCONCLUSIVE or INSUFFICIENT_DATA. "
        "No action until sufficient prospective draws are available."
    ),
}

P112_TO_P113_ACTION = {
    "PREDICTION_HELPFUL": "WATCHLIST_QUEUE",
    "WATCHLIST_CANDIDATE": "OBSERVATION_QUEUE",
    "OBSERVE_MORE": "CONTINUE_OBSERVATION",
    "FALLBACK_EQUIVALENT": "FALLBACK_DISCLOSURE_CANDIDATE",
    "SUB_BASELINE": "DEMOTE_OR_QUARANTINE_CANDIDATE",
    "INCONCLUSIVE": "HOLD_FOR_MORE_DATA",
    "INSUFFICIENT_DATA": "HOLD_FOR_MORE_DATA",
}

RATIONALE_MAP = {
    "WATCHLIST_QUEUE": (
        "P112 classified this strategy as PREDICTION_HELPFUL with measurable positive edge "
        "above hypergeometric baseline. Qualifies for controlled OOS monitoring design. "
        "Promotion requires separate governance authorization."
    ),
    "OBSERVATION_QUEUE": (
        "P112 classified this strategy as WATCHLIST_CANDIDATE with positive edge vs baseline. "
        "Edge is promising but insufficient sample size or window stability to authorize promotion. "
        "Accumulate more prospective draws before escalating."
    ),
    "CONTINUE_OBSERVATION": (
        "P112 classified this strategy as OBSERVE_MORE. "
        "Edge direction unclear or sample size too small. Continue passive monitoring."
    ),
    "FALLBACK_DISCLOSURE_CANDIDATE": (
        "P112 classified this strategy as FALLBACK_EQUIVALENT. "
        "Performance is statistically indistinguishable from hypergeometric baseline. "
        "Must be disclosed as fallback when used in production context."
    ),
    "DEMOTE_OR_QUARANTINE_CANDIDATE": (
        "P112 classified this strategy as SUB_BASELINE. "
        "Performance is below hypergeometric baseline. "
        "Candidate for demotion/quarantine in future governance task (P115 or equivalent)."
    ),
    "HOLD_FOR_MORE_DATA": (
        "Insufficient data to make a governance decision. Hold pending more prospective draws."
    ),
}

NEXT_TASK_MAP = {
    "WATCHLIST_QUEUE": "P114_TEMPORAL_STABILITY_AUDIT or P116_OOS_MONITORING_DESIGN",
    "OBSERVATION_QUEUE": "P114_TEMPORAL_STABILITY_AUDIT or WAVE_N_TARGETED_OBSERVATION",
    "CONTINUE_OBSERVATION": "PASSIVE_MONITORING_ONLY",
    "FALLBACK_DISCLOSURE_CANDIDATE": "P116_FALLBACK_DISCLOSURE_GOVERNANCE or NO_IMMEDIATE_ACTION",
    "DEMOTE_OR_QUARANTINE_CANDIDATE": "P115_STRATEGY_QUARANTINE_GOVERNANCE",
    "HOLD_FOR_MORE_DATA": "HOLD_PENDING_MORE_PROSPECTIVE_DRAWS",
}

WAVE_N_BACKLOG = [
    {
        "priority": 1,
        "lottery_type": "POWER_LOTTO",
        "candidate_scope": ["midfreq_fourier_mk_3bet", "pp3_freqort_4bet"],
        "wave_label": "WAVE_N_POWER_LOTTO_OOS_MONITORING",
        "rationale": (
            "Two PREDICTION_HELPFUL strategies with positive edge (+0.080 and +0.055) vs baseline. "
            "Highest priority for controlled OOS monitoring design. "
            "Requires separate P114/P116 authorization before any deployment."
        ),
        "required_authorization_before_execution": [
            "P114 temporal stability audit PASS",
            "OOS monitoring design review",
            "Explicit promotion authorization (not granted by P112/P113)",
        ],
    },
    {
        "priority": 2,
        "lottery_type": "POWER_LOTTO",
        "candidate_scope": [
            "fourier_rhythm_3bet", "power_fourier_rhythm_2bet",
            "power_orthogonal_5bet", "power_precision_3bet",
            "midfreq_fourier_2bet", "fourier30_markov30_2bet",
        ],
        "wave_label": "WAVE_N_POWER_LOTTO_WATCHLIST_EXPANSION",
        "rationale": (
            "Six WATCHLIST_CANDIDATE strategies with positive edges (+0.017 to +0.045). "
            "Accumulate more prospective draws and assess temporal stability "
            "before deciding on targeted observation or demotion."
        ),
        "required_authorization_before_execution": [
            "P114 temporal stability audit",
            "Minimum prospective draw count TBD",
            "Explicit promotion authorization (not granted by P112/P113)",
        ],
    },
    {
        "priority": 3,
        "lottery_type": "DAILY_539",
        "candidate_scope": [
            "p0b_539_3bet_f_cold_fmid", "p0c_539_3bet_f_cold_x2",
            "daily539_f4cold", "539_3bet_orthogonal",
            "acb_1bet", "acb_markov_midfreq_3bet", "acb_single_539",
            "daily539_f4cold_3bet", "daily539_f4cold_5bet",
            "midfreq_acb_2bet", "midfreq_fourier_2bet",
        ],
        "wave_label": "WAVE_N_DAILY_539_OBSERVATION_EXPANSION",
        "rationale": (
            "Eleven WATCHLIST_CANDIDATE strategies with edges +0.028 to +0.036. "
            "Cold-pool and orthogonal variants consistently outperform Markov. "
            "Medium priority; needs temporal stability confirmation."
        ),
        "required_authorization_before_execution": [
            "P114 temporal stability audit for DAILY_539",
            "Explicit promotion authorization (not granted by P112/P113)",
        ],
    },
    {
        "priority": 4,
        "lottery_type": "BIG_LOTTO",
        "candidate_scope": ["biglotto_deviation_2bet"],
        "wave_label": "WAVE_N_BIG_LOTTO_SINGLE_WATCHLIST",
        "rationale": (
            "Only one WATCHLIST_CANDIDATE (biglotto_deviation_2bet, edge=+0.023). "
            "BIG_LOTTO is the hardest lottery to beat; 4 strategies are SUB_BASELINE. "
            "Low priority; strategy redesign for BIG_LOTTO should precede expansion."
        ),
        "required_authorization_before_execution": [
            "P115 quarantine of sub-baseline BIG_LOTTO strategies",
            "Strategy redesign for BIG_LOTTO context",
            "Explicit promotion authorization (not granted by P112/P113)",
        ],
    },
    {
        "priority": 5,
        "lottery_type": "BIG_LOTTO",
        "candidate_scope": [
            "bet2_fourier_expansion_biglotto", "biglotto_ts3_markov_4bet_w30",
            "fourier30_markov30_biglotto", "ts3_regime_3bet",
        ],
        "wave_label": "WAVE_N_BIG_LOTTO_QUARANTINE_REVIEW",
        "rationale": (
            "Four SUB_BASELINE strategies in BIG_LOTTO context. "
            "Quarantine/demotion should be executed as a separate governance task (P115). "
            "Not auto-demoted in P113."
        ),
        "required_authorization_before_execution": [
            "P115 strategy quarantine governance task authorization",
            "Explicit demotion/quarantine decision (not granted by P112/P113)",
        ],
    },
]

EXPLICIT_HOLDS = [
    {
        "hold_id": "SPECIAL3_P108_HOLD",
        "description": "Special3 P108 100-draw re-evaluation is NOT executable.",
        "reason": (
            "Only 63 prospective draws available after P99 cutoff. "
            "37 more draws required to reach 100-draw threshold."
        ),
        "unblock_condition": "37 additional 3_STAR draws completed.",
        "current_count": 63,
        "target_count": 100,
        "remaining": 37,
    },
    {
        "hold_id": "FOUR_STAR_BACKTEST_HOLD",
        "description": "4_STAR backtest remains NOT AUTHORIZED.",
        "reason": (
            "4_STAR row source/provenance is unknown. "
            "Source determination and acceptance must precede any backtest."
        ),
        "unblock_condition": "Source/provenance decision and explicit backtest authorization.",
        "source_unknown_caveat_preserved": True,
    },
    {
        "hold_id": "NO_PRODUCTION_PROMOTION_FROM_P112_P113",
        "description": "No strategy promotion from P112 or P113 findings alone.",
        "reason": (
            "P112 is an audit; P113 is a decision matrix. "
            "Neither authorizes production deployment or lifecycle mutation. "
            "Promotion requires separate governance authorization (P114+ chain)."
        ),
        "unblock_condition": "Explicit promotion authorization task (P114/P116 equivalent).",
    },
]

PER_LOTTERY_DECISION_MATRIX = {
    "POWER_LOTTO": {
        "priority": "HIGH",
        "reason": "2 PREDICTION_HELPFUL + 6 WATCHLIST_CANDIDATE strategies; highest observed edge.",
        "recommended_next": "P114 temporal stability audit; design OOS monitoring for helpful strategies.",
        "watchlist_queue_count": 2,
        "observation_queue_count": 6,
        "fallback_disclosure_count": 2,
        "demote_quarantine_count": 0,
        "baseline_main": 0.947368,
        "max_helpful_edge": 0.079965,
    },
    "DAILY_539": {
        "priority": "MEDIUM",
        "reason": "11 WATCHLIST_CANDIDATE strategies; cold-pool/orthogonal variants consistently outperform Markov. 1 SUB_BASELINE to quarantine.",
        "recommended_next": "P114 temporal stability audit; P115 quarantine for zone_gap_3bet_539.",
        "watchlist_queue_count": 0,
        "observation_queue_count": 11,
        "fallback_disclosure_count": 3,
        "demote_quarantine_count": 1,
        "baseline_main": 0.641026,
        "max_helpful_edge": 0.036308,
    },
    "BIG_LOTTO": {
        "priority": "LOW_REPAIR_FIRST",
        "reason": "Only 1 WATCHLIST_CANDIDATE; 4 SUB_BASELINE strategies. Strategy redesign needed before expansion.",
        "recommended_next": "P115 quarantine for 4 sub-baseline strategies; strategy redesign before Wave-N expansion.",
        "watchlist_queue_count": 0,
        "observation_queue_count": 1,
        "fallback_disclosure_count": 6,
        "demote_quarantine_count": 4,
        "baseline_main": 0.734694,
        "max_helpful_edge": 0.022631,
    },
}


def load_p112(artifact_path: Path) -> dict:
    with open(artifact_path) as f:
        return json.load(f)


def verify_p112(p112: dict) -> None:
    assert p112.get("classification") == "P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY", (
        f"Unexpected P112 classification: {p112.get('classification')}"
    )
    assert p112.get("task_id") == "P112_CROSS_LOTTERY_PREDICTION_HELPFULNESS_AUDIT"
    assert isinstance(p112.get("per_strategy_results"), list)
    assert len(p112["per_strategy_results"]) > 0


def verify_db_invariants(db_path: Path) -> int:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    assert rows == EXPECTED_REPLAY_ROWS, f"replay_rows={rows} != {EXPECTED_REPLAY_ROWS}"
    return rows


def build_per_strategy_matrix(p112_strategies: list) -> list:
    matrix = []
    for s in p112_strategies:
        p112_cls = s["classification"]
        action = P112_TO_P113_ACTION.get(p112_cls, "HOLD_FOR_MORE_DATA")
        edge = s.get("edge_vs_baseline", s.get("edge_main", None))
        matrix.append({
            "strategy_id": s["strategy_id"],
            "lottery_type": s["lottery_type"],
            "p112_classification": p112_cls,
            "p113_action": action,
            "promotion_authorized": False,
            "edge_vs_baseline": edge,
            "rationale": RATIONALE_MAP[action],
            "next_task_candidate": NEXT_TASK_MAP[action],
        })
    return matrix


def build_artifact(p112: dict, replay_rows: int) -> dict:
    strategies = p112["per_strategy_results"]
    per_strategy_matrix = build_per_strategy_matrix(strategies)

    # Count actions
    action_counts = {}
    for s in per_strategy_matrix:
        a = s["p113_action"]
        action_counts[a] = action_counts.get(a, 0) + 1

    return {
        "classification": "P113_P112_ACTION_DECISION_MATRIX_READY",
        "task_id": TASK_ID,
        "generated_date": "20260527",
        "p112_reference": {
            "classification": p112["classification"],
            "artifact_path": str(P112_ARTIFACT),
            "task_id": p112["task_id"],
            "audited_strategy_count": len(strategies),
            "audited_lotteries": ["POWER_LOTTO", "DAILY_539", "BIG_LOTTO"],
        },
        "db_writes": False,
        "replay_rows_before": EXPECTED_REPLAY_ROWS,
        "replay_rows_after": replay_rows,
        "no_strategy_promotion": True,
        "no_lifecycle_mutation": True,
        "no_registry_mutation": True,
        "no_4star_backtest": True,
        "no_special3_p108_rerun": True,
        "source_unknown_caveat_preserved": True,
        "action_definitions": ACTION_DEFINITIONS,
        "action_summary_counts": action_counts,
        "per_lottery_decision_matrix": PER_LOTTERY_DECISION_MATRIX,
        "per_strategy_action_matrix": per_strategy_matrix,
        "wave_n_backlog": WAVE_N_BACKLOG,
        "explicit_holds": EXPLICIT_HOLDS,
        "limitations": [
            "P112 audit window covers only historical replay rows as of 2026-05-27; "
            "prospective performance may differ.",
            "Edge estimates are point estimates from available replay data; "
            "no confidence intervals are computed in P113.",
            "P113 decision matrix uses P112 classification as input; "
            "any P112 misclassification propagates here.",
            "No temporal stability analysis is performed in P113; "
            "this is deferred to P114.",
            "Promotion decisions require separate explicit governance authorization not present in P112/P113.",
            "BIG_LOTTO strategies with FALLBACK_EQUIVALENT classification may still appear "
            "in live rotation; this audit does not modify live routing.",
        ],
        "final_classification": "P113_P112_ACTION_DECISION_MATRIX_READY",
    }


def print_summary(artifact: dict) -> None:
    print(f"=== {TASK_ID} ===")
    print(f"classification: {artifact['classification']}")
    print(f"replay_rows_before={artifact['replay_rows_before']}  "
          f"replay_rows_after={artifact['replay_rows_after']}")
    print(f"db_writes: {artifact['db_writes']}")
    print(f"no_strategy_promotion: {artifact['no_strategy_promotion']}")
    print()
    print("Action summary:")
    for action, count in sorted(artifact["action_summary_counts"].items(), key=lambda x: -x[1]):
        print(f"  {action}: {count}")
    print()
    print("Per-lottery priorities:")
    for lt, info in artifact["per_lottery_decision_matrix"].items():
        print(f"  {lt}: {info['priority']}  watchlist_queue={info['watchlist_queue_count']}  "
              f"obs={info['observation_queue_count']}  demote={info['demote_quarantine_count']}")
    print()
    print("Explicit holds:")
    for h in artifact["explicit_holds"]:
        print(f"  [{h['hold_id']}] {h['description']}")
    print()
    print(f"Wave-N backlog items: {len(artifact['wave_n_backlog'])}")
    print(f"final_classification: {artifact['final_classification']}")


def main():
    parser = argparse.ArgumentParser(description="P113: P112 Action Decision Matrix")
    parser.add_argument("--json-out", required=True, help="Output JSON artifact path")
    parser.add_argument(
        "--p112-artifact",
        default=P112_ARTIFACT,
        help="Path to P112 JSON artifact",
    )
    parser.add_argument("--db", default=DB_PATH, help="Path to lottery DB")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    p112_path = base / args.p112_artifact
    db_path = base / args.db
    out_path = Path(args.json_out)

    print(f"Loading P112 artifact: {p112_path}")
    p112 = load_p112(p112_path)
    verify_p112(p112)
    print("P112 verification: PASS")

    print(f"Verifying DB invariants: {db_path}")
    replay_rows = verify_db_invariants(db_path)
    print(f"replay_rows={replay_rows}: PASS")

    artifact = build_artifact(p112, replay_rows)
    print_summary(artifact)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"\nArtifact written: {out_path}")


if __name__ == "__main__":
    main()
