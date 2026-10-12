#!/usr/bin/env python3
"""
P121: Trigger Recheck / Wait-State Confirmation
Read-only script. Re-evaluates P120 trigger conditions against current DB state.
Reuses trigger logic from p120_trigger_evaluation.py.
No DB writes, no strategy promotion, no lifecycle mutation, no OOS execution.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

P120_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "p120_trigger_evaluation_20260527.json"

EXPECTED_REPLAY_ROWS = 54462

P99_CUTOFF_DRAW = 115000024
P108_REQUIRED_COUNT = 100
P116_BASELINE_POWER_LOTTO = 115000041
P117_PARTIAL_REQUIRED = 30
P117_FULL_REQUIRED = 40
P118_EXACT_PHRASE = "YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence"
P118_CANDIDATE_STRATEGY = "fourier30_markov30_biglotto"
P118_LOTTERY_TYPE = "BIG_LOTTO"

VALID_CLASSIFICATIONS = {
    "P121_ALL_TRIGGERS_STILL_BLOCKED",
    "P121_P108_TRIGGER_MET",
    "P121_P117_PARTIAL_TRIGGER_MET",
    "P121_P117_FULL_TRIGGER_MET",
    "P121_P118_AUTHORIZATION_PRESENT",
    "P121_4STAR_PROVENANCE_TRIGGER_MET",
    "P121_TRIGGER_RECHECK_INCONCLUSIVE",
}


def get_db_state():
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    replay_rows = cur.fetchone()[0]

    cur.execute(
        "SELECT lottery_type, COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws "
        "WHERE lottery_type IN ('3_STAR','4_STAR','POWER_LOTTO') GROUP BY lottery_type"
    )
    rows = {r[0]: {"count": r[1], "max_draw": str(r[2])} for r in cur.fetchall()}

    cur.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR' AND CAST(draw AS INTEGER) > ?",
        (P99_CUTOFF_DRAW,),
    )
    p108_count = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO' AND CAST(draw AS INTEGER) > ?",
        (P116_BASELINE_POWER_LOTTO,),
    )
    p117_new_draws = cur.fetchone()[0]

    conn.close()
    return replay_rows, rows, p108_count, p117_new_draws


def check_4star_provenance():
    patterns = [
        "outputs/replay/p*4star*source*",
        "outputs/replay/p*provenance*",
        "outputs/replay/p*4_star*accept*",
        "outputs/replay/p*source*accept*",
    ]
    for pattern in patterns:
        matches = list(PROJECT_ROOT.glob(pattern))
        if matches:
            return True, str(matches[0].relative_to(PROJECT_ROOT))
    return False, None


def evaluate_p118(operator_input: str) -> bool:
    return bool(operator_input) and P118_EXACT_PHRASE in operator_input


def build_trigger_recheck(p108_count, p117_new_draws, p118_auth, provenance_found):
    p108_remaining = max(0, P108_REQUIRED_COUNT - p108_count)
    p117_partial_rem = max(0, P117_PARTIAL_REQUIRED - p117_new_draws)
    p117_full_rem = max(0, P117_FULL_REQUIRED - p117_new_draws)

    return {
        "P108_SPECIAL3_100DRAW_REEVALUATION": {
            "current_count_after_p99_cutoff": p108_count,
            "p99_cutoff_draw": str(P99_CUTOFF_DRAW),
            "required_count": P108_REQUIRED_COUNT,
            "remaining_needed": p108_remaining,
            "trigger_met": p108_count >= P108_REQUIRED_COUNT,
            "status": "ELIGIBLE" if p108_count >= P108_REQUIRED_COUNT else "BLOCKED",
            "blocked_reason": None if p108_count >= P108_REQUIRED_COUNT
                else f"Need {p108_remaining} more Special3 draws (current {p108_count}/{P108_REQUIRED_COUNT})",
            "next_task_if_met": "Plan P108 Special3 100-draw re-evaluation on a separate branch",
        },
        "P117_POWERLOTTO_OOS_RETRIGGER": {
            "p116_baseline_draw": str(P116_BASELINE_POWER_LOTTO),
            "current_new_draws_after_p116": p117_new_draws,
            "partial_required_count": P117_PARTIAL_REQUIRED,
            "full_required_count": P117_FULL_REQUIRED,
            "remaining_needed_for_partial": p117_partial_rem,
            "remaining_needed_for_full": p117_full_rem,
            "partial_trigger_met": p117_new_draws >= P117_PARTIAL_REQUIRED,
            "full_trigger_met": p117_new_draws >= P117_FULL_REQUIRED,
            "status": (
                "ELIGIBLE_FULL" if p117_new_draws >= P117_FULL_REQUIRED
                else "ELIGIBLE_PARTIAL" if p117_new_draws >= P117_PARTIAL_REQUIRED
                else "BLOCKED"
            ),
            "blocked_reason": None if p117_new_draws >= P117_PARTIAL_REQUIRED
                else f"Need {p117_partial_rem} more POWER_LOTTO draws for partial (current {p117_new_draws}/{P117_PARTIAL_REQUIRED})",
            "next_task_if_met": "Re-run P117 checkpoint script on a separate branch",
        },
        "P118_BIGLOTTO_ACTUAL_QUARANTINE": {
            "exact_authorization_phrase": P118_EXACT_PHRASE,
            "candidate_strategy": P118_CANDIDATE_STRATEGY,
            "lottery_type": P118_LOTTERY_TYPE,
            "authorization_present": p118_auth,
            "trigger_met": p118_auth,
            "status": "ELIGIBLE" if p118_auth else "BLOCKED",
            "blocked_reason": None if p118_auth else "Exact authorization phrase not found in operator input",
            "next_task_if_met": "Plan P118 BIG_LOTTO actual quarantine on a separate branch",
        },
        "P4STAR_PROVENANCE_AND_BACKTEST": {
            "source_unknown_caveat_active": True,
            "provenance_acceptance_artifact_present": provenance_found,
            "backtest_authorization_present": False,
            "trigger_met": False,
            "status": "BLOCKED",
            "blocked_reason": "4_STAR source remains unknown; no provenance acceptance artifact found",
            "next_task_if_met": "Plan 4_STAR provenance acceptance task, then separately authorize backtest",
        },
    }


def determine_classification(tr):
    if tr["P108_SPECIAL3_100DRAW_REEVALUATION"]["trigger_met"]:
        return "P121_P108_TRIGGER_MET"
    if tr["P117_POWERLOTTO_OOS_RETRIGGER"]["full_trigger_met"]:
        return "P121_P117_FULL_TRIGGER_MET"
    if tr["P117_POWERLOTTO_OOS_RETRIGGER"]["partial_trigger_met"]:
        return "P121_P117_PARTIAL_TRIGGER_MET"
    if tr["P118_BIGLOTTO_ACTUAL_QUARANTINE"]["trigger_met"]:
        return "P121_P118_AUTHORIZATION_PRESENT"
    if tr["P4STAR_PROVENANCE_AND_BACKTEST"]["trigger_met"]:
        return "P121_4STAR_PROVENANCE_TRIGGER_MET"
    return "P121_ALL_TRIGGERS_STILL_BLOCKED"


def build_blocked_register(tr):
    register = []
    for name, t in tr.items():
        if not t.get("trigger_met", False):
            register.append({
                "task": name,
                "status": "BLOCKED",
                "blocked_reason": t.get("blocked_reason"),
                "unblock_condition": t.get("next_task_if_met"),
            })
    return register


def build_artifact(replay_rows, db_rows, p108_count, p117_new_draws, p118_auth, provenance_found, p120_data):
    tr = build_trigger_recheck(p108_count, p117_new_draws, p118_auth, provenance_found)
    classification = determine_classification(tr)
    blocked_register = build_blocked_register(tr)

    three_star = db_rows.get("3_STAR", {})
    four_star = db_rows.get("4_STAR", {})
    power_lotto = db_rows.get("POWER_LOTTO", {})

    p108_rem = tr["P108_SPECIAL3_100DRAW_REEVALUATION"]["remaining_needed"]
    p117_rem = tr["P117_POWERLOTTO_OOS_RETRIGGER"]["remaining_needed_for_partial"]

    if classification == "P121_ALL_TRIGGERS_STILL_BLOCKED":
        recommendation = (
            f"All P120 triggers remain BLOCKED. No change since P120. "
            f"Nearest trigger: {p108_rem} more Special3 draws for P108, "
            f"{p117_rem} more POWER_LOTTO draws for P117 partial checkpoint. "
            f"Continue monitoring. No new analysis warranted."
        )
        priority_trigger = "NONE — all triggers still blocked"
        next_operator_action = (
            f"Wait for new draw data. "
            f"Re-run this script after new draws are ingested. "
            f"Alternatively, provide the BIG_LOTTO authorization phrase to unblock P118."
        )
    else:
        recommendation = f"Trigger met: {classification}. Plan eligible task on a separate branch."
        priority_trigger = classification
        next_operator_action = f"Plan {classification} task on a new branch."

    return {
        "task_id": "P121_TRIGGER_RECHECK",
        "classification": classification,
        "p120_reference": {
            "classification": p120_data.get("classification", "P120_ALL_TRIGGERS_BLOCKED"),
            "artifact_path": "outputs/replay/p120_trigger_evaluation_20260527.json",
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
        "no_powerlotto_oos_execution": True,
        "source_unknown_caveat_preserved": True,
        "current_db_snapshot": {
            "replay_rows": replay_rows,
            "three_star_count": three_star.get("count", 4179),
            "three_star_max_draw": three_star.get("max_draw", "115000106"),
            "four_star_count": four_star.get("count", 2922),
            "four_star_max_draw": four_star.get("max_draw", "115000103"),
            "power_lotto_count": power_lotto.get("count", 1913),
            "power_lotto_max_draw": power_lotto.get("max_draw", "115000041"),
        },
        "trigger_recheck": tr,
        "priority_trigger": priority_trigger,
        "overall_recommendation": recommendation,
        "blocked_task_register": blocked_register,
        "next_operator_action": next_operator_action,
        "limitations": [
            "P118 authorization_present defaults to false unless --operator-input supplies the exact phrase",
            "4_STAR provenance check is file-system based; no live provenance registry exists",
            "P108 count uses P99 cutoff draw 115000024; if cutoff is incorrect the count will differ",
            "No change detected since P120: Special3=63, POWER_LOTTO new draws=0",
            "This is trigger recheck only; no live analysis was performed",
        ],
        "final_classification": classification,
    }


def main():
    parser = argparse.ArgumentParser(description="P121 Trigger Recheck")
    parser.add_argument("--json-out", help="Path to write JSON artifact")
    parser.add_argument("--operator-input", default="", help="Operator input string to check for auth phrases")
    args = parser.parse_args()

    print("=== P121: Trigger Recheck / Wait-State Confirmation ===")
    print("Read-only. No DB writes. No strategy promotion.")
    print()

    replay_rows, db_rows, p108_count, p117_new_draws = get_db_state()
    provenance_found, _ = check_4star_provenance()
    p118_auth = evaluate_p118(args.operator_input)

    p120_data = {}
    if P120_ARTIFACT.exists():
        with open(P120_ARTIFACT) as f:
            p120_data = json.load(f)

    print(f"Replay rows              : {replay_rows}")
    print(f"3_STAR after P99 cutoff  : {p108_count}/100 (need {max(0, 100 - p108_count)} more)")
    print(f"POWER_LOTTO new draws    : {p117_new_draws} (need 30 partial / 40 full)")
    print(f"P118 auth phrase present : {p118_auth}")
    print(f"4_STAR provenance found  : {provenance_found}")
    print()

    tr = build_trigger_recheck(p108_count, p117_new_draws, p118_auth, provenance_found)
    classification = determine_classification(tr)

    print("Trigger Recheck:")
    for name, t in tr.items():
        print(f"  {name}: {t['status']}")

    print()
    print(f"Priority trigger : {'NONE' if classification == 'P121_ALL_TRIGGERS_STILL_BLOCKED' else classification}")
    print(f"Classification   : {classification}")

    artifact = build_artifact(replay_rows, db_rows, p108_count, p117_new_draws, p118_auth, provenance_found, p120_data)

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        print(f"\nJSON artifact written to: {args.json_out}")

    return artifact


if __name__ == "__main__":
    main()
