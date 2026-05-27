#!/usr/bin/env python3
"""
P123: Scheduled Trigger Recheck
Read-only wrapper. Reuses P122 trigger recheck logic. Writes timestamped JSON to
outputs/replay/trigger_rechecks/ (or --output-dir / --json-out).
No DB writes. No crontab. No launchd. No OS scheduler.
"""

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "replay" / "trigger_rechecks"

EXPECTED_REPLAY_ROWS = 54462
CANONICAL_REPO = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
PROJECT_LOCK = "LotteryNew"

P99_CUTOFF_DRAW = 115000024
P108_REQUIRED_COUNT = 100
P116_BASELINE_POWER_LOTTO = 115000041
P117_PARTIAL_REQUIRED = 30
P117_FULL_REQUIRED = 40
P118_EXACT_PHRASE = "YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence"
P118_CANDIDATE_STRATEGY = "fourier30_markov30_biglotto"
P118_LOTTERY_TYPE = "BIG_LOTTO"

REJECTED_CONTEXTS = [
    "Betting-pool",
    "Stock-Prediction-System",
    "Stock",
    "Novel",
    "SCB",
]

VALID_RUNTIME_CLASSIFICATIONS = {
    "P122_ALL_TRIGGERS_STILL_BLOCKED",
    "P122_P108_TRIGGER_MET",
    "P122_P117_PARTIAL_TRIGGER_MET",
    "P122_P117_FULL_TRIGGER_MET",
    "P122_P118_AUTHORIZATION_PRESENT",
    "P122_4STAR_PROVENANCE_TRIGGER_MET",
    "P122_TRIGGER_RECHECK_INCONCLUSIVE",
    "P122_BLOCKED_BY_CONTEXT_CONTAMINATION",
}


def get_worktree_branch_guard_metadata():
    try:
        git_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(PROJECT_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=str(PROJECT_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        is_worktree = ".git/worktrees" in git_dir
        is_claude_codex = branch.startswith("claude/") or branch.startswith("codex/")
    except Exception:
        git_dir = "unknown"
        branch = "unknown"
        is_worktree = False
        is_claude_codex = False

    return {
        "git_dir_expected": ".git",
        "git_dir_actual": git_dir,
        "current_branch": branch,
        "worktree_branches_allowed": False,
        "claude_codex_worktree_allowed": False,
        "branch_prefixes_rejected": ["claude/", "codex/"],
        "is_worktree_git_dir": is_worktree,
        "is_claude_codex_branch": is_claude_codex,
        "guard_result": "FAIL" if (is_worktree or is_claude_codex) else "PASS",
    }


def check_contamination(operator_input: str = "") -> bool:
    combined = operator_input.upper()
    for ctx in REJECTED_CONTEXTS:
        if ctx.upper() in combined:
            return True
    return False


def get_db_state():
    conn = sqlite3.connect(str(DB_PATH))
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
                else f"Need {p117_partial_rem} more POWER_LOTTO draws (current {p117_new_draws}/{P117_PARTIAL_REQUIRED})",
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


def determine_classification(tr, contamination_detected):
    if contamination_detected:
        return "P122_BLOCKED_BY_CONTEXT_CONTAMINATION"
    if tr["P108_SPECIAL3_100DRAW_REEVALUATION"]["trigger_met"]:
        return "P122_P108_TRIGGER_MET"
    if tr["P117_POWERLOTTO_OOS_RETRIGGER"]["full_trigger_met"]:
        return "P122_P117_FULL_TRIGGER_MET"
    if tr["P117_POWERLOTTO_OOS_RETRIGGER"]["partial_trigger_met"]:
        return "P122_P117_PARTIAL_TRIGGER_MET"
    if tr["P118_BIGLOTTO_ACTUAL_QUARANTINE"]["trigger_met"]:
        return "P122_P118_AUTHORIZATION_PRESENT"
    if tr["P4STAR_PROVENANCE_AND_BACKTEST"]["trigger_met"]:
        return "P122_4STAR_PROVENANCE_TRIGGER_MET"
    return "P122_ALL_TRIGGERS_STILL_BLOCKED"


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


def build_runtime_artifact(timestamp_str, replay_rows, db_rows, p108_count,
                            p117_new_draws, p118_auth, provenance_found,
                            contamination_detected, wtg):
    tr = build_trigger_recheck(p108_count, p117_new_draws, p118_auth, provenance_found)
    classification = determine_classification(tr, contamination_detected)
    blocked_register = build_blocked_register(tr)

    three_star = db_rows.get("3_STAR", {})
    four_star = db_rows.get("4_STAR", {})
    power_lotto = db_rows.get("POWER_LOTTO", {})

    p108_rem = tr["P108_SPECIAL3_100DRAW_REEVALUATION"]["remaining_needed"]
    p117_rem = tr["P117_POWERLOTTO_OOS_RETRIGGER"]["remaining_needed_for_partial"]

    if classification == "P122_ALL_TRIGGERS_STILL_BLOCKED":
        recommendation = (
            f"All triggers remain BLOCKED. "
            f"Nearest: {p108_rem} more Special3 draws for P108, "
            f"{p117_rem} more POWER_LOTTO draws for P117 partial. "
            f"Continue monitoring."
        )
        next_operator_action = (
            "Wait for new draw data or provide the BIG_LOTTO authorization phrase. "
            "Re-run this script after new draws are ingested."
        )
    else:
        recommendation = f"Trigger met: {classification}. Plan eligible task on a separate branch."
        next_operator_action = f"Plan {classification} task on a new branch."

    return {
        "task_id": "P123_SCHEDULED_TRIGGER_RECHECK_RUNTIME",
        "run_timestamp": timestamp_str,
        "classification": classification,
        "db_writes": False,
        "replay_rows": replay_rows,
        "no_strategy_promotion": True,
        "no_lifecycle_mutation": True,
        "no_registry_mutation": True,
        "no_actual_quarantine_applied": True,
        "no_replay_row_delete": True,
        "no_4star_backtest": True,
        "no_special3_p108_rerun": True,
        "no_powerlotto_oos_execution": True,
        "source_unknown_caveat_preserved": True,
        "cross_project_contamination_guard": {
            "project_lock": PROJECT_LOCK,
            "canonical_repo": CANONICAL_REPO,
            "rejected_project_contexts": REJECTED_CONTEXTS,
            "contamination_detected": contamination_detected,
        },
        "worktree_branch_guard": wtg,
        "current_db_snapshot": {
            "replay_rows": replay_rows,
            "three_star_count": three_star.get("count"),
            "three_star_max_draw": three_star.get("max_draw"),
            "four_star_count": four_star.get("count"),
            "four_star_max_draw": four_star.get("max_draw"),
            "power_lotto_count": power_lotto.get("count"),
            "power_lotto_max_draw": power_lotto.get("max_draw"),
        },
        "trigger_recheck": tr,
        "blocked_task_register": blocked_register,
        "recommendation": recommendation,
        "next_operator_action": next_operator_action,
        "final_classification": classification,
    }


def main():
    parser = argparse.ArgumentParser(description="P123 Scheduled Trigger Recheck")
    parser.add_argument("--json-out", help="Exact path to write JSON output")
    parser.add_argument("--output-dir", help="Directory for timestamped JSON output")
    parser.add_argument("--operator-input", default="", help="Operator input to check for auth phrases and contamination")
    parser.add_argument("--timestamp", default="", help="Override timestamp string (for deterministic tests)")
    args = parser.parse_args()

    ts = args.timestamp if args.timestamp else datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=== P123: Scheduled Trigger Recheck ===")
    print(f"Project lock : {PROJECT_LOCK}")
    print(f"Canonical repo: {CANONICAL_REPO}")
    print(f"Read-only. No DB writes. No crontab. No launchd.")
    print(f"Timestamp    : {ts}")
    print()

    contamination_detected = check_contamination(args.operator_input)
    if contamination_detected:
        print("STOP: Cross-project contamination detected in operator input!")
        print("Classification: P122_BLOCKED_BY_CONTEXT_CONTAMINATION")
        sys.exit(1)

    wtg = get_worktree_branch_guard_metadata()

    replay_rows, db_rows, p108_count, p117_new_draws = get_db_state()
    provenance_found, _ = check_4star_provenance()
    p118_auth = evaluate_p118(args.operator_input)

    tr = build_trigger_recheck(p108_count, p117_new_draws, p118_auth, provenance_found)
    classification = determine_classification(tr, contamination_detected)

    p108_rem = tr["P108_SPECIAL3_100DRAW_REEVALUATION"]["remaining_needed"]
    p117p_rem = tr["P117_POWERLOTTO_OOS_RETRIGGER"]["remaining_needed_for_partial"]
    p117f_rem = tr["P117_POWERLOTTO_OOS_RETRIGGER"]["remaining_needed_for_full"]

    print(f"Classification   : {classification}")
    print(f"P108 remaining   : {p108_rem} more Special3 draws needed")
    print(f"P117 partial rem : {p117p_rem} more POWER_LOTTO draws needed")
    print(f"P117 full rem    : {p117f_rem} more POWER_LOTTO draws needed")
    print(f"P118 auth phrase : {p118_auth}")
    print(f"4_STAR provenance: {provenance_found}")
    print(f"Contamination    : {contamination_detected}")
    print(f"Worktree guard   : {wtg['guard_result']}")
    print()

    artifact = build_runtime_artifact(
        ts, replay_rows, db_rows, p108_count, p117_new_draws,
        p118_auth, provenance_found, contamination_detected, wtg
    )

    out_path = None
    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        print(f"JSON written to: {args.json_out}")
    elif args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"trigger_recheck_{ts}.json"
        out_path = out_dir / filename
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        print(f"JSON written to: {out_path}")
    else:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"trigger_recheck_{ts}.json"
        out_path = DEFAULT_OUTPUT_DIR / filename
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        print(f"JSON written to: {out_path}")

    return artifact


if __name__ == "__main__":
    main()
