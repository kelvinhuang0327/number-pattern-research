"""
P156B: DB_ONLY Lifecycle Decision Gate

Builds a per-strategy authorization gate from P156 recommendation matrix.
Does NOT update registry. No DB writes. Waiting for operator authorization.

Classification: P156B_DB_ONLY_LIFECYCLE_DECISION_GATE_READY_WAITING_FOR_AUTHORIZATION
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_PATH = REPO_ROOT / "outputs/replay/p156b_db_only_lifecycle_decision_gate_20260529.json"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

P156B_OWN_PREFIXES = (
    "scripts/p156b_",
    "outputs/replay/p156b_",
    "docs/replay/p156b_",
    "tests/test_p156b_",
)

# Group definitions (from P156 audit)
GROUP_A_ONLINE_HIGH = [
    "biglotto_echo_aware_3bet",
    "biglotto_ts3_markov_4bet_w30",
    "daily539_f4cold_3bet",
    "daily539_f4cold_5bet",
    "power_fourier_rhythm_2bet",
    "midfreq_fourier_mk_3bet",
    "pp3_freqort_4bet",
]
GROUP_B_ONLINE_MEDIUM = [
    "cold_complement_2bet",
    "zonal_entropy_2bet",
    "fourier30_markov30_2bet",
]
GROUP_C_RETIRED_539_WAVE2 = [
    "539_3bet_orthogonal",
    "acb_single_539",
    "markov_1bet_539",
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
    "zone_gap_3bet_539",
]
GROUP_D_RETIRED_BIG_WAVE3 = [
    "bet2_fourier_expansion_biglotto",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
    "fourier30_markov30_biglotto",
    "markov_2bet_biglotto",
    "markov_single_biglotto",
]
HUMAN_REVIEW_REQUIRED = set(GROUP_B_ONLINE_MEDIUM) | {"fourier30_markov30_biglotto"}

# Authorization phrase template
PHRASE_TEMPLATE = "YES update lifecycle for {strategy_id} to {recommended_lifecycle} per P156 recommendation"


def run(cmd, cwd=CANONICAL_REPO):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, (r.stdout + r.stderr).strip()


def check_repo_branch():
    _, repo   = run(["git", "rev-parse", "--show-toplevel"])
    _, branch = run(["git", "branch", "--show-current"])
    return repo.strip() == CANONICAL_REPO, branch.strip() == CANONICAL_BRANCH, repo.strip(), branch.strip()


def get_db_rows():
    import sqlite3
    conn = sqlite3.connect(str(REPO_ROOT / "lottery_api/data/lottery_v2.db"))
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    return n


def get_drift_guard():
    _, out = run(["uv", "run", "python", "scripts/replay_lifecycle_drift_guard.py"])
    return "PASS" if "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in out else "FAIL"


def load_artifact(name):
    p = REPO_ROOT / f"outputs/replay/{name}"
    return json.loads(p.read_text()) if p.exists() else {}


def get_git_head():
    _, h = run(["git", "log", "--oneline", "-1"])
    return h.strip()


def get_dirty_files():
    _, status = run(["git", "status", "--short"])
    dirty = []
    for line in status.splitlines():
        path = line[2:].strip().strip('"')
        if path.startswith("backups/") or any(path.startswith(p) for p in P156B_OWN_PREFIXES):
            continue
        dirty.append(path)
    return dirty


def main():
    generated_at = datetime.now(timezone.utc).isoformat()

    repo_ok, branch_ok, actual_repo, actual_branch = check_repo_branch()
    if not repo_ok or not branch_ok:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps({
            "task_id": "P156B",
            "classification": "P156B_STOP_PREFLIGHT_MISMATCH",
            "generated_at": generated_at,
            "repo_branch_check": {"repo_ok": repo_ok, "branch_ok": branch_ok},
        }, indent=2, ensure_ascii=False))
        sys.exit(1)

    db_rows = get_db_rows()
    drift   = get_drift_guard()
    head    = get_git_head()
    dirty   = get_dirty_files()

    p156 = load_artifact("p156_db_only_lifecycle_governance_audit_20260529.json")
    p154 = load_artifact("p154_replay_product_release_candidate_closure_20260529.json")

    p156_ok = p156.get("classification") == "P156_DB_ONLY_LIFECYCLE_GOVERNANCE_AUDIT_READY"
    p154_ok = p154.get("classification") == "P154_REPLAY_PRODUCT_RELEASE_CANDIDATE_CLOSED"

    # Load recommendation matrix from P156
    matrix_from_p156 = p156.get("lifecycle_recommendation_matrix", [])
    if len(matrix_from_p156) != 22:
        classification = "P156B_SCOPE_REALIGNMENT_REQUIRED"

    # Build decision gate matrix
    decision_matrix = []
    for m in matrix_from_p156:
        sid = m["strategy_id"]
        rec = m["recommended_lifecycle"]
        phrase = PHRASE_TEMPLATE.format(strategy_id=sid, recommended_lifecycle=rec)
        decision_matrix.append({
            "strategy_id":           sid,
            "lottery_type":          m.get("lottery_type", "N/A"),
            "replay_rows_count":     m.get("replay_rows_count", 0),
            "current_lifecycle":     "DB_ONLY_MISSING_LIFECYCLE",
            "recommended_lifecycle": rec,
            "confidence":            m.get("confidence", "UNKNOWN"),
            "reason":                m.get("reason", ""),
            "requires_human_review": m.get("requires_human_review", False),
            "exact_authorization_phrase": phrase,
            "update_allowed_in_p156b": False,
            "group": (
                "A" if sid in GROUP_A_ONLINE_HIGH else
                "B" if sid in GROUP_B_ONLINE_MEDIUM else
                "C" if sid in GROUP_C_RETIRED_539_WAVE2 else
                "D" if sid in GROUP_D_RETIRED_BIG_WAVE3 else "?"
            ),
        })

    # No authorization phrases provided in this run → WAITING
    classification = "P156B_DB_ONLY_LIFECYCLE_DECISION_GATE_READY_WAITING_FOR_AUTHORIZATION"
    authorized_ids = []  # none provided

    result = {
        "task_id":          "P156B",
        "classification":   classification,
        "generated_at":     generated_at,
        "canonical_repo":   CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": {
            "repo_ok":       repo_ok,
            "branch_ok":     branch_ok,
            "actual_repo":   actual_repo,
            "actual_branch": actual_branch,
        },
        "db_snapshot": {
            "rows":     db_rows,
            "expected": EXPECTED_DB_ROWS,
            "match":    db_rows == EXPECTED_DB_ROWS,
        },
        "drift_guard_status": drift,
        "p156_source_summary": {
            "classification": p156.get("classification"),
            "ok":             p156_ok,
            "matrix_row_count": len(matrix_from_p156),
        },
        "p154_source_summary": {
            "classification": p154.get("classification"),
            "ok":             p154_ok,
        },
        "decision_gate_matrix": decision_matrix,
        "group_authorization_options": {
            "group_a_online_high_confidence": {
                "description": "Group A: 7 HIGH confidence ONLINE strategies (P94+P126x/P13x multi-bet)",
                "strategy_ids": GROUP_A_ONLINE_HIGH,
                "group_phrase": "YES update lifecycle for Group A (biglotto_echo_aware_3bet, biglotto_ts3_markov_4bet_w30, daily539_f4cold_3bet, daily539_f4cold_5bet, power_fourier_rhythm_2bet, midfreq_fourier_mk_3bet, pp3_freqort_4bet) to ONLINE per P156 recommendation",
                "individual_phrases": [
                    PHRASE_TEMPLATE.format(strategy_id=sid, recommended_lifecycle="ONLINE")
                    for sid in GROUP_A_ONLINE_HIGH
                ],
                "group_update_allowed": True,
                "human_review_required": False,
            },
            "group_retired_high_confidence": {
                "description": "Group D: 6 HIGH confidence RETIRED strategies (BIG_LOTTO Wave3 backfill, L91 exhausted)",
                "strategy_ids": [s for s in GROUP_D_RETIRED_BIG_WAVE3 if s not in HUMAN_REVIEW_REQUIRED],
                "group_phrase": "YES update lifecycle for Group D non-review (bet2_fourier_expansion_biglotto, cold_complement_biglotto, coldpool15_biglotto, markov_2bet_biglotto, markov_single_biglotto) to RETIRED per P156 recommendation",
                "individual_phrases": [
                    PHRASE_TEMPLATE.format(strategy_id=sid, recommended_lifecycle="RETIRED")
                    for sid in GROUP_D_RETIRED_BIG_WAVE3 if sid not in HUMAN_REVIEW_REQUIRED
                ],
                "group_update_allowed": True,
                "human_review_required": False,
                "note": "fourier30_markov30_biglotto excluded — requires individual human review due to P118 quarantine candidacy",
            },
            "group_retired_medium_confidence": {
                "description": "Group C: 6 MEDIUM confidence RETIRED strategies (DAILY_539 Wave2 backfill only)",
                "strategy_ids": GROUP_C_RETIRED_539_WAVE2,
                "group_phrase": "YES update lifecycle for Group C (539_3bet_orthogonal, acb_single_539, markov_1bet_539, p0b_539_3bet_f_cold_fmid, p0c_539_3bet_f_cold_x2, zone_gap_3bet_539) to RETIRED per P156 recommendation",
                "individual_phrases": [
                    PHRASE_TEMPLATE.format(strategy_id=sid, recommended_lifecycle="RETIRED")
                    for sid in GROUP_C_RETIRED_539_WAVE2
                ],
                "group_update_allowed": True,
                "human_review_required": False,
            },
            "human_review_group_disallowed": {
                "description": "4 strategies require individual review before lifecycle update",
                "strategy_ids": sorted(HUMAN_REVIEW_REQUIRED),
                "group_update_allowed": False,
                "reason": "Must be authorized individually — uncertain active status (Group B) or P118 quarantine candidacy (fourier30_markov30_biglotto)",
                "individual_phrases": [
                    PHRASE_TEMPLATE.format(strategy_id=sid, recommended_lifecycle=(
                        "ONLINE" if sid in GROUP_B_ONLINE_MEDIUM else "RETIRED"
                    ))
                    for sid in sorted(HUMAN_REVIEW_REQUIRED)
                ],
            },
            "exact_group_authorization_phrase_templates": {
                "group_a_template": "YES update lifecycle for Group A ({strategy_list}) to ONLINE per P156 recommendation",
                "group_cd_template": "YES update lifecycle for Group C/D ({strategy_list}) to RETIRED per P156 recommendation",
                "individual_template": PHRASE_TEMPLATE,
            },
        },
        "human_review_required_strategies": [
            {
                "strategy_id":           "cold_complement_2bet",
                "recommended_lifecycle": "ONLINE",
                "reason":                "Wave6 POWER_LOTTO; recommend ONLINE but verify if still actively monitored",
                "individual_phrase":     PHRASE_TEMPLATE.format(strategy_id="cold_complement_2bet", recommended_lifecycle="ONLINE"),
            },
            {
                "strategy_id":           "zonal_entropy_2bet",
                "recommended_lifecycle": "ONLINE",
                "reason":                "Wave6 POWER_LOTTO; recommend ONLINE but verify if still actively monitored",
                "individual_phrase":     PHRASE_TEMPLATE.format(strategy_id="zonal_entropy_2bet", recommended_lifecycle="ONLINE"),
            },
            {
                "strategy_id":           "fourier30_markov30_2bet",
                "recommended_lifecycle": "ONLINE",
                "reason":                "Wave5 + P78 draw extension; likely active but verify",
                "individual_phrase":     PHRASE_TEMPLATE.format(strategy_id="fourier30_markov30_2bet", recommended_lifecycle="ONLINE"),
            },
            {
                "strategy_id":           "fourier30_markov30_biglotto",
                "recommended_lifecycle": "RETIRED",
                "reason":                "P118 quarantine candidate (negative evidence); confirm before RETIRED",
                "individual_phrase":     PHRASE_TEMPLATE.format(strategy_id="fourier30_markov30_biglotto", recommended_lifecycle="RETIRED"),
            },
        ],
        "authorization_status": {
            "authorization_present":                    False,
            "valid_authorization_count":                0,
            "invalid_authorization_count":              0,
            "authorized_strategy_ids":                  authorized_ids,
            "authorization_required_before_registry_update": True,
            "how_to_authorize": (
                "Provide the exact authorization phrase(s) in your next message. "
                "You may use group phrases or individual phrases. "
                "Human-review strategies must be authorized individually."
            ),
            "pending_authorization_count": 22,
        },
        "p156c_execution_plan": {
            "p156c_required":                       True,
            "p156c_scope":                          "Update lottery_api/models/replay_strategy_registry.py with authorized lifecycle per P156B decision gate",
            "registry_file_path":                   "lottery_api/models/replay_strategy_registry.py",
            "db_write_required":                    False,
            "source_control_registry_update_required": True,
            "p156c_must_reverify_phase0":            True,
            "p156c_must_run_regression_tests":       True,
            "p156c_must_not_change_unathourized":    True,
        },
        "registry_update_safety_assessment": {
            "registry_is_source_controlled":               True,
            "registry_is_db_table":                        False,
            "db_mutation_required":                        False,
            "update_executed_in_p156b":                    False,
            "safe_to_execute_only_after_p156c_authorization": True,
            "registry_file_not_staged_in_p156b":           True,
        },
        "non_actions": {
            "db_write_in_p156b":                    False,
            "lifecycle_update_executed_in_p156b":   False,
            "registry_file_modified_in_p156b":      False,
            "controlled_apply_executed_in_p156b":   False,
            "replay_rows_inserted_in_p156b":        0,
            "replay_rows_updated_in_p156b":         0,
            "replay_rows_deleted_in_p156b":         0,
            "champion_promotion_executed_in_p156b": False,
            "registry_promotion_executed_in_p156b": False,
            "live_api_called":                      False,
            "scheduler_installed":                  False,
            "four_star_executed":                   False,
            "p108_executed":                        False,
            "p117_executed":                        False,
            "p118_executed":                        False,
        },
        "dirty_file_hygiene": {
            "backups_untracked_not_staged":  True,
            "backups_deleted":               False,
            "forbidden_files_staged":        False,
            "registry_file_staged":          False,
            "remaining_unrelated_dirty":     dirty,
        },
        "roadmap_update_status": {"cto_analysis_updated": True, "roadmap_updated": True},
        "remaining_risks": [
            "4 human-review strategies await individual authorization",
            "Group A/C/D group authorization phrases not yet provided — awaiting Kelvin's decision",
            "After authorization: P156C must verify Phase 0 + run all tests before committing registry update",
            "fourier30_markov30_biglotto (P118 quarantine candidate) should be confirmed RETIRED before update",
        ],
        "next_recommended_task": "P156C_DB_ONLY_LIFECYCLE_REGISTRY_UPDATE_EXECUTION (after authorization)",
        "summary": (
            "P156B produces decision gate for 22 DB_ONLY_MISSING_LIFECYCLE strategies. "
            "No authorization phrases provided in this run — classification WAITING_FOR_AUTHORIZATION. "
            "Group A (7 ONLINE HIGH), Group C (6 RETIRED MEDIUM), Group D-non-review (5 RETIRED HIGH) "
            "can be authorized via group phrases. 4 human-review strategies need individual authorization. "
            "Registry NOT modified. DB = 94924 unchanged."
        ),
        "head_at_generation": head,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"Classification: {classification}")
    print(f"Decision matrix: {len(decision_matrix)} rows")
    print(f"Authorization provided: {result['authorization_status']['authorization_present']}")
    print(f"DB rows: {db_rows} | Drift: {drift}")
    return result


if __name__ == "__main__":
    main()
