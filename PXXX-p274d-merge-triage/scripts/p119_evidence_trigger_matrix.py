#!/usr/bin/env python3
"""
P119: Evidence Consolidation and Trigger Matrix for P105-P117
Read-only script. No DB writes, no strategy promotion, no lifecycle mutation.
"""

import argparse
import json
import sqlite3
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

EXPECTED_REPLAY_ROWS = 54462

ARTIFACT_MAP = {
    "P105": "outputs/replay/p105_db_state_acceptance_decision_20260527.json",
    "P106": "outputs/replay/p106_special3_prospective_evaluation_rerun_20260527.json",
    "P107A": "outputs/replay/p107a_special3_100draw_monitoring_gate_20260527.json",
    "P107B": "outputs/replay/p107b_stale_baseline_guard_repair_20260527.json",
    "P112": "outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json",
    "P113": "outputs/replay/p113_p112_action_decision_matrix_20260527.json",
    "P114": "outputs/replay/p114_temporal_stability_audit_20260527.json",
    "P116": "outputs/replay/p116_powerlotto_oos_monitoring_design_20260527.json",
    "P115": "outputs/replay/p115_biglotto_quarantine_governance_20260527.json",
    "P117": "outputs/replay/p117_powerlotto_oos_monitoring_checkpoint_20260527.json",
}

# Known PR/commit metadata from governance history
KNOWN_METADATA = {
    "P105": {"pr": None, "merge_commit": "ceea6e9", "metadata_source": "git_log"},
    "P106": {"pr": None, "merge_commit": "bfa2653", "metadata_source": "git_log"},
    "P107A": {"pr": None, "merge_commit": "782e261", "metadata_source": "git_log"},
    "P107B": {"pr": None, "merge_commit": "e79b5e9", "metadata_source": "git_log"},
    "P112": {"pr": "#238", "merge_commit": "4db894a", "metadata_source": "git_log"},
    "P113": {"pr": "#239", "merge_commit": "be3716e", "metadata_source": "git_log"},
    "P114": {"pr": "#240", "merge_commit": "3ffae64", "metadata_source": "git_log"},
    "P116": {"pr": "#241", "merge_commit": "f4b7ae4", "metadata_source": "git_log"},
    "P115": {"pr": "#242", "merge_commit": "c4ce85e", "metadata_source": "git_log"},
    "P117": {"pr": "#243", "merge_commit": "9765485", "metadata_source": "git_log"},
}

KEY_CONCLUSIONS = {
    "P105": "DB state accepted for Special3 prospective evaluation only. 4_STAR source remains unknown. Source_unknown caveat propagated forward.",
    "P106": "63 Special3 prospective draws after P99 cutoff found. 37 more needed for 100-draw re-evaluation. Partial evaluation only.",
    "P107A": "Special3 100-draw re-evaluation (P108) blocked. WAIT_MORE_DRAWS gate established at 100 prospective draws.",
    "P107B": "Stale baseline guards repaired post-DB-acceptance. Guards updated to reflect replay_rows=54462 as accepted baseline.",
    "P112": "Cross-lottery prediction helpfulness audit completed. BIG_LOTTO and POWER_LOTTO strategies assessed for continued helpfulness.",
    "P113": "Action decision matrix from P112 audit completed. Governance decisions for each strategy documented.",
    "P114": "Temporal stability audit completed. Strategy temporal drift checked across draw windows.",
    "P116": "POWER_LOTTO OOS monitoring design ready. Two candidates: midfreq_fourier_mk_3bet (min 30 draws) and pp3_freqort_4bet (min 40 draws).",
    "P115": "BIG_LOTTO quarantine governance design ready for fourier30_markov30_biglotto. Actual quarantine NOT applied. Requires explicit auth phrase.",
    "P117": "POWER_LOTTO OOS checkpoint: 0 new draws after baseline 115000041. WAIT_MORE_DRAWS. No OOS conclusions, no promotion.",
}

FORBIDDEN_SQL_VERBS = [
    "INSERT", "UPDATE", "DELETE", "CREATE TABLE", "DROP", "ALTER TABLE",
    "REPLACE INTO", "VACUUM", "PRAGMA writable_schema",
]


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
        "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO' AND CAST(draw AS INTEGER) > 115000041"
    )
    new_pl_draws = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR' AND CAST(draw AS INTEGER) > 115000106"
    )
    new_3star_draws = cur.fetchone()[0]
    conn.close()
    return replay_rows, rows, new_pl_draws, new_3star_draws


def load_artifacts():
    loaded = {}
    for phase, rel_path in ARTIFACT_MAP.items():
        path = PROJECT_ROOT / rel_path
        if path.exists():
            with open(path) as f:
                loaded[phase] = json.load(f)
        else:
            loaded[phase] = None
    return loaded


def build_evidence_index(artifacts):
    index = []
    for phase, rel_path in ARTIFACT_MAP.items():
        data = artifacts.get(phase) or {}
        meta = KNOWN_METADATA.get(phase, {})
        index.append({
            "phase_id": phase,
            "classification": data.get("classification") or data.get("final_classification"),
            "artifact_path": rel_path,
            "pr": meta.get("pr"),
            "merge_commit": meta.get("merge_commit"),
            "metadata_source": meta.get("metadata_source", "unknown"),
            "key_conclusion": KEY_CONCLUSIONS.get(phase, ""),
            "governance_constraints": _governance_constraints(phase),
        })
    return index


def _governance_constraints(phase):
    constraints = {
        "P105": ["source_unknown_caveat_active", "4_STAR_source_unresolved"],
        "P106": ["special3_p108_blocked_until_100_draws", "source_unknown_caveat_active"],
        "P107A": ["special3_p108_blocked_until_100_draws", "wait_more_draws_gate_active"],
        "P107B": ["guards_updated_no_other_changes", "replay_rows_baseline_locked_54462"],
        "P112": ["no_promotion_from_audit", "no_lifecycle_mutation"],
        "P113": ["no_promotion_from_matrix", "no_lifecycle_mutation"],
        "P114": ["no_promotion_from_audit", "temporal_review_only"],
        "P116": ["no_oos_execution", "design_only", "promotion_not_authorized"],
        "P115": ["actual_quarantine_not_applied", "requires_explicit_auth_phrase", "no_lifecycle_mutation"],
        "P117": ["wait_more_draws", "no_oos_conclusions", "no_promotion"],
    }
    return constraints.get(phase, [])


def build_trigger_matrix(new_pl_draws, new_3star_draws):
    special3_prospective = 63 + new_3star_draws
    pl_new = new_pl_draws

    return {
        "P108_SPECIAL3_100DRAW_REEVALUATION": {
            "trigger_type": "draw_count",
            "condition": "Special3 prospective draws after P99 cutoff >= 100",
            "current_value": special3_prospective,
            "threshold": 100,
            "remaining": max(0, 100 - special3_prospective),
            "status": "ELIGIBLE" if special3_prospective >= 100 else "BLOCKED",
            "authorization_required": "separate branch / task required; no automatic promotion",
            "blocked_reason": None if special3_prospective >= 100 else f"Need {max(0, 100 - special3_prospective)} more Special3 prospective draws",
        },
        "P117_POWERLOTTO_OOS_RETRIGGER": {
            "trigger_type": "draw_count",
            "condition_partial": "New POWER_LOTTO draws after 115000041 >= 30",
            "condition_full": "New POWER_LOTTO draws after 115000041 >= 40",
            "current_value": pl_new,
            "threshold_partial": 30,
            "threshold_full": 40,
            "remaining_for_partial": max(0, 30 - pl_new),
            "remaining_for_full": max(0, 40 - pl_new),
            "status": (
                "ELIGIBLE_FULL" if pl_new >= 40
                else "ELIGIBLE_PARTIAL" if pl_new >= 30
                else "BLOCKED"
            ),
            "authorization_required": "promotion not authorized even after checkpoint",
            "blocked_reason": None if pl_new >= 30 else f"Need {max(0, 30 - pl_new)} more POWER_LOTTO draws for partial checkpoint",
        },
        "P118_BIGLOTTO_ACTUAL_QUARANTINE": {
            "trigger_type": "explicit_authorization",
            "condition": "User provides exact phrase: YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence",
            "exact_phrase_required": "YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence",
            "candidate_strategy": "fourier30_markov30_biglotto",
            "lottery_type": "BIG_LOTTO",
            "current_status": "BLOCKED_AWAITING_AUTHORIZATION",
            "authorization_phrase_detected": False,
            "status": "BLOCKED",
            "blocked_reason": "Exact authorization phrase has not been provided",
            "notes": "P115 created governance design only. Actual quarantine requires explicit phrase above plus a separate P118 task.",
        },
        "P4STAR_PROVENANCE_AND_BACKTEST": {
            "trigger_type": "source_decision",
            "condition": "Source/provenance of 4_STAR rows must be confirmed in a separate decision artifact before backtest is authorized",
            "current_4star_count": 2922,
            "current_4star_max_draw": "115000103",
            "source_status": "UNKNOWN",
            "backtest_status": "NOT_AUTHORIZED",
            "status": "BLOCKED",
            "blocked_reason": "4_STAR source remains unknown; backtest cannot be authorized until source is confirmed in a separate artifact",
            "authorization_required": "Source acceptance task + explicit backtest authorization",
        },
    }


def build_blocked_task_register(trigger_matrix):
    register = []

    for name, t in trigger_matrix.items():
        if t["status"] in ("BLOCKED", "BLOCKED_AWAITING_AUTHORIZATION"):
            register.append({
                "task": name,
                "status": "BLOCKED",
                "blocked_reason": t.get("blocked_reason"),
                "unblock_condition": t.get("condition") or t.get("condition_partial"),
            })

    return register


def build_next_action_selector(trigger_matrix):
    p108 = trigger_matrix["P108_SPECIAL3_100DRAW_REEVALUATION"]
    p117 = trigger_matrix["P117_POWERLOTTO_OOS_RETRIGGER"]
    p118 = trigger_matrix["P118_BIGLOTTO_ACTUAL_QUARANTINE"]
    p4star = trigger_matrix["P4STAR_PROVENANCE_AND_BACKTEST"]

    if p108["status"] == "ELIGIBLE":
        action = "P108_SPECIAL3_100DRAW_REEVALUATION"
        rationale = f"Special3 prospective draws ({p108['current_value']}) have reached 100-draw threshold. Plan P108 re-evaluation on a separate branch."
    elif p117["status"] in ("ELIGIBLE_FULL", "ELIGIBLE_PARTIAL"):
        action = "P117_POWERLOTTO_OOS_RETRIGGER"
        rationale = f"POWER_LOTTO has {p117['current_value']} new draws after baseline. Re-run P117 checkpoint script."
    elif p118["status"] == "ELIGIBLE":
        action = "P118_BIGLOTTO_ACTUAL_QUARANTINE"
        rationale = "Authorization phrase received. Plan P118 actual quarantine task on a separate branch."
    else:
        action = "WAIT_FOR_DATA_OR_AUTHORIZATION"
        rationale = (
            "All trigger conditions are currently unmet. "
            f"Nearest trigger: {p108['remaining']} more Special3 draws for P108, "
            f"{p117['remaining_for_partial']} more POWER_LOTTO draws for partial P117 checkpoint. "
            "Continue monitoring. No new analysis warranted until data changes."
        )

    return {
        "recommended_next_action": action,
        "rationale": rationale,
        "selector_rules": [
            {"rule": "if Special3 prospective draws >= 100 → P108_SPECIAL3_100DRAW_REEVALUATION"},
            {"rule": "elif new POWER_LOTTO draws >= 30 → P117_POWERLOTTO_OOS_RETRIGGER (partial)"},
            {"rule": "elif new POWER_LOTTO draws >= 40 → P117_POWERLOTTO_OOS_RETRIGGER (full)"},
            {"rule": "elif exact quarantine phrase present → P118_BIGLOTTO_ACTUAL_QUARANTINE"},
            {"rule": "else → WAIT_FOR_DATA_OR_AUTHORIZATION"},
        ],
    }


def build_artifact(replay_rows, db_rows, new_pl_draws, new_3star_draws, artifacts):
    evidence_index = build_evidence_index(artifacts)
    trigger_matrix = build_trigger_matrix(new_pl_draws, new_3star_draws)
    blocked_register = build_blocked_task_register(trigger_matrix)
    next_action = build_next_action_selector(trigger_matrix)

    three_star = db_rows.get("3_STAR", {})
    four_star = db_rows.get("4_STAR", {})
    power_lotto = db_rows.get("POWER_LOTTO", {})

    return {
        "task_id": "P119_EVIDENCE_TRIGGER_MATRIX",
        "classification": "P119_EVIDENCE_TRIGGER_MATRIX_READY",
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
        "evidence_index": evidence_index,
        "trigger_matrix": trigger_matrix,
        "blocked_task_register": blocked_register,
        "next_action_selector": next_action,
        "explicit_authorization_phrases": [
            {
                "purpose": "BIG_LOTTO actual quarantine of fourier30_markov30_biglotto",
                "required_phrase": "YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence",
                "task": "P118_BIGLOTTO_ACTUAL_QUARANTINE",
            }
        ],
        "future_task_candidates": [
            {
                "task": "P108_SPECIAL3_100DRAW_REEVALUATION",
                "condition": "Special3 prospective draws >= 100",
                "current_progress": f"{63 + new_3star_draws}/100",
            },
            {
                "task": "P117_POWERLOTTO_OOS_RETRIGGER_PARTIAL",
                "condition": "New POWER_LOTTO draws after 115000041 >= 30",
                "current_progress": f"{new_pl_draws}/30",
            },
            {
                "task": "P117_POWERLOTTO_OOS_RETRIGGER_FULL",
                "condition": "New POWER_LOTTO draws after 115000041 >= 40",
                "current_progress": f"{new_pl_draws}/40",
            },
            {
                "task": "P118_BIGLOTTO_ACTUAL_QUARANTINE",
                "condition": "Explicit authorization phrase provided by user/operator",
                "current_progress": "0/1 (phrase not yet provided)",
            },
            {
                "task": "P4STAR_PROVENANCE_DECISION",
                "condition": "4_STAR source confirmed in a separate decision artifact",
                "current_progress": "source_unknown",
            },
        ],
        "limitations": [
            "P108/P109 through P111 artifacts not found in outputs/replay/ — these tasks may predate the current artifact naming convention or may not have produced JSON outputs; evidence index covers available artifacts only",
            "P116 did not record explicit baseline draw field; P117 used fallback 115000041",
            "new_3star_draws and new_pl_draws computed from DB at checkpoint time; recalculate at future trigger evaluation",
            "This is documentation consolidation only; no live analysis was run",
        ],
        "final_classification": "P119_EVIDENCE_TRIGGER_MATRIX_READY",
    }


def main():
    parser = argparse.ArgumentParser(description="P119 Evidence Trigger Matrix")
    parser.add_argument("--json-out", help="Path to write JSON artifact")
    args = parser.parse_args()

    print("=== P119: Evidence Consolidation and Trigger Matrix ===")
    print("Read-only. No DB writes. No strategy promotion.")
    print()

    replay_rows, db_rows, new_pl_draws, new_3star_draws = get_db_state()
    artifacts = load_artifacts()

    print(f"Replay rows:              {replay_rows}")
    print(f"POWER_LOTTO new draws:    {new_pl_draws} (baseline 115000041)")
    print(f"3_STAR new draws (est):   {new_3star_draws} (after 115000106)")
    print(f"Special3 prospective est: {63 + new_3star_draws}/100")
    print()

    artifact = build_artifact(replay_rows, db_rows, new_pl_draws, new_3star_draws, artifacts)

    print(f"Evidence phases indexed:  {len(artifact['evidence_index'])}")
    print(f"Trigger matrix entries:   {len(artifact['trigger_matrix'])}")
    print(f"Blocked tasks:            {len(artifact['blocked_task_register'])}")
    print()

    tm = artifact["trigger_matrix"]
    print("Trigger Matrix:")
    for name, t in tm.items():
        print(f"  {name}: {t['status']}")

    print()
    sel = artifact["next_action_selector"]
    print(f"Next recommended action: {sel['recommended_next_action']}")
    print(f"Rationale: {sel['rationale'][:120]}...")

    print()
    print(f"Classification: {artifact['final_classification']}")

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        print(f"\nJSON artifact written to: {args.json_out}")

    return artifact


if __name__ == "__main__":
    main()
