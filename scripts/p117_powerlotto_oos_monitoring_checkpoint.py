#!/usr/bin/env python3
"""
P117: POWER_LOTTO OOS Monitoring Execution Checkpoint
Read-only script. Determines whether enough new POWER_LOTTO draws exist
after the P116 design baseline to start OOS monitoring execution.
No DB writes, no strategy promotion, no lifecycle mutation.
"""

import argparse
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

P116_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "p116_powerlotto_oos_monitoring_design_20260527.json"
P115_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "p115_biglotto_quarantine_governance_20260527.json"

# Fallback baseline per spec: if P116 lacks explicit baseline, use known P116-time max draw
P116_FALLBACK_BASELINE = "115000041"

EXPECTED_REPLAY_ROWS = 54462

CANDIDATES = {
    "midfreq_fourier_mk_3bet": {
        "minimum_new_power_lotto_draws": 30,
        "preferred_new_power_lotto_draws": 50,
        "promotion_discussion_minimum": 80,
    },
    "pp3_freqort_4bet": {
        "minimum_new_power_lotto_draws": 40,
        "preferred_new_power_lotto_draws": 60,
        "promotion_discussion_minimum": 100,
    },
}

FORBIDDEN_SQL_VERBS = [
    "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "REPLACE",
    "VACUUM", "PRAGMA writable_schema",
]


def load_p116():
    with open(P116_ARTIFACT) as f:
        return json.load(f)


def load_p115():
    with open(P115_ARTIFACT) as f:
        return json.load(f)


def get_db_state():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    replay_rows = cur.fetchone()[0]
    cur.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type = 'POWER_LOTTO'"
    )
    max_draw_val = cur.fetchone()[0]
    conn.close()
    return replay_rows, str(max_draw_val) if max_draw_val else None


def determine_p116_baseline(p116_data):
    baseline = p116_data.get("p116_baseline_power_lotto_max_draw")
    if baseline:
        return str(baseline)
    return P116_FALLBACK_BASELINE


def count_new_draws(baseline_draw_str, current_draw_str):
    if not current_draw_str:
        return 0
    baseline = int(baseline_draw_str)
    current = int(current_draw_str)
    if current <= baseline:
        return 0
    # Count actual draws between baseline+1 and current
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO' "
        "AND CAST(draw AS INTEGER) > ?",
        (baseline,),
    )
    count = cur.fetchone()[0]
    conn.close()
    return count


def classify(new_draws):
    if new_draws < 30:
        return "P117_POWERLOTTO_OOS_WAIT_MORE_DRAWS"
    elif new_draws < 40:
        return "P117_POWERLOTTO_OOS_PARTIAL_CHECKPOINT"
    else:
        return "P117_POWERLOTTO_OOS_CHECKPOINT_READY"


def build_candidate_entry(strategy_id, cfg, new_draws, classification):
    min_draws = cfg["minimum_new_power_lotto_draws"]
    pref_draws = cfg["preferred_new_power_lotto_draws"]
    promo_min = cfg["promotion_discussion_minimum"]

    remaining = max(0, min_draws - new_draws)

    if new_draws >= min_draws:
        threshold_status = "MET"
        checkpoint_decision = "CHECKPOINT_RUN" if classification != "P117_POWERLOTTO_OOS_WAIT_MORE_DRAWS" else "WAIT_MORE_DRAWS"
    else:
        threshold_status = "NOT_MET"
        checkpoint_decision = "WAIT_MORE_DRAWS"

    # For partial checkpoint: only midfreq_fourier_mk_3bet runs if new_draws >= 30 but < 40
    if classification == "P117_POWERLOTTO_OOS_PARTIAL_CHECKPOINT":
        if strategy_id == "pp3_freqort_4bet":
            threshold_status = "NOT_MET"
            checkpoint_decision = "WAIT_MORE_DRAWS"

    return {
        "strategy_id": strategy_id,
        "minimum_new_draws": min_draws,
        "preferred_new_draws": pref_draws,
        "promotion_discussion_minimum": promo_min,
        "threshold_status": threshold_status,
        "remaining_draws_needed_for_minimum": remaining,
        "checkpoint_metrics": None,  # No live metrics computed — read-only, no replay enrichment
        "checkpoint_decision": checkpoint_decision,
        "promotion_authorized": False,
    }


def build_artifact(p116_data, p115_data, replay_rows, current_max, new_draws, baseline):
    classification = classify(new_draws)

    candidates = [
        build_candidate_entry(sid, cfg, new_draws, classification)
        for sid, cfg in CANDIDATES.items()
    ]

    if new_draws < 30:
        recommendation = (
            f"Wait for more POWER_LOTTO draws. Current new draws after P116 baseline "
            f"({baseline}): {new_draws}. Need at least 30 for midfreq_fourier_mk_3bet "
            f"minimum threshold, 40 for pp3_freqort_4bet. "
            f"Current max draw: {current_max}. No OOS conclusions can be drawn."
        )
    elif new_draws < 40:
        recommendation = (
            f"Partial checkpoint possible for midfreq_fourier_mk_3bet only "
            f"(new draws: {new_draws} >= 30). pp3_freqort_4bet still needs "
            f"{40 - new_draws} more draws. Promotion not authorized from P117 alone."
        )
    else:
        recommendation = (
            f"Both candidates meet minimum threshold ({new_draws} new draws). "
            f"Checkpoint metrics can be computed. Promotion not authorized from P117 alone."
        )

    return {
        "task_id": "P117_POWERLOTTO_OOS_MONITORING_CHECKPOINT",
        "classification": classification,
        "p116_reference": {
            "classification": p116_data.get("classification", "P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY"),
            "artifact_path": str(P116_ARTIFACT.relative_to(PROJECT_ROOT)),
        },
        "p115_reference": {
            "classification": p115_data.get("classification", "P115_BIGLOTTO_QUARANTINE_GOVERNANCE_READY"),
            "artifact_path": str(P115_ARTIFACT.relative_to(PROJECT_ROOT)),
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
        "source_unknown_caveat_preserved": True,
        "monitored_lottery_type": "POWER_LOTTO",
        "p116_baseline_power_lotto_max_draw": baseline,
        "current_power_lotto_max_draw": current_max,
        "new_power_lotto_draws_after_p116": new_draws,
        "monitoring_candidates": candidates,
        "overall_recommendation": recommendation,
        "explicit_holds": [
            "Special3 P108 still blocked until 100 prospective draws (currently 63, need 37 more)",
            "4_STAR backtest remains unauthorized (source unknown)",
            "BIG_LOTTO actual quarantine remains blocked until explicit authorization phrase: YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence",
            "Production promotion not authorized from P117 alone",
        ],
        "limitations": [
            "checkpoint_metrics is null for all candidates because no new replay rows have been ingested after P116 baseline",
            "New POWER_LOTTO draws after P116 = 0; all threshold checks result in WAIT_MORE_DRAWS",
            "P116 artifact did not record explicit baseline draw; fallback to known P116-time max draw 115000041",
            "This checkpoint is read-only and does not implement live monitoring jobs",
            "No OOS performance conclusions can be drawn with 0 new draws",
        ],
        "final_classification": classification,
    }


def main():
    parser = argparse.ArgumentParser(description="P117 POWER_LOTTO OOS Monitoring Checkpoint")
    parser.add_argument("--json-out", help="Path to write JSON artifact")
    args = parser.parse_args()

    print("=== P117: POWER_LOTTO OOS Monitoring Execution Checkpoint ===")
    print("Read-only. No DB writes. No strategy promotion.")
    print()

    p116_data = load_p116()
    p115_data = load_p115()
    replay_rows, current_max = get_db_state()
    baseline = determine_p116_baseline(p116_data)
    new_draws = count_new_draws(baseline, current_max)

    print(f"P116 baseline POWER_LOTTO max draw : {baseline}")
    print(f"Current POWER_LOTTO max draw       : {current_max}")
    print(f"New POWER_LOTTO draws after P116   : {new_draws}")
    print(f"Replay rows (invariant)            : {replay_rows}")
    print()

    classification = classify(new_draws)
    print(f"Classification: {classification}")
    print()

    for sid, cfg in CANDIDATES.items():
        min_d = cfg["minimum_new_power_lotto_draws"]
        remaining = max(0, min_d - new_draws)
        status = "MET" if new_draws >= min_d else "NOT_MET"
        print(f"  {sid}: threshold={status}, need_min={min_d}, remaining={remaining}")

    print()
    if new_draws < 30:
        print(f"WAIT_MORE_DRAWS: Need at least 30 new draws for first candidate.")
        print(f"Currently 0 new draws after baseline {baseline}.")

    artifact = build_artifact(p116_data, p115_data, replay_rows, current_max, new_draws, baseline)

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        print(f"\nJSON artifact written to: {args.json_out}")

    return artifact


if __name__ == "__main__":
    main()
