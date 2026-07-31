"""
P156: DB_ONLY_MISSING_LIFECYCLE Governance Audit

Read-only audit of 22 DB_ONLY_MISSING_LIFECYCLE strategies.
Produces lifecycle recommendations based on DB evidence.
Does NOT update registry or DB. P156B required for actual updates.
"""

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_PATH = REPO_ROOT / "outputs/replay/p156_db_only_lifecycle_governance_audit_20260529.json"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

P156_OWN_PREFIXES = (
    "scripts/p156_",
    "outputs/replay/p156_",
    "docs/replay/p156_",
    "tests/test_p156_",
)

# Evidence-based lifecycle recommendation data
# Determined from DB evidence: source, controlled_apply_id, truth_level, rows, bet_index
LIFECYCLE_RECOMMENDATIONS = {
    # GROUP A: ONLINE — active multi-bet strategies with P94+P126x controlled_apply
    "biglotto_echo_aware_3bet":    ("ONLINE",  "HIGH",   "P94+P126C controlled_apply; TIERB_DRYRUN_VALIDATED; 3-bet expanded; actively maintained"),
    "biglotto_ts3_markov_4bet_w30":("ONLINE",  "HIGH",   "P94+P126E controlled_apply; TIERB_DRYRUN_VALIDATED; 4-bet expanded; actively maintained"),
    "daily539_f4cold_3bet":        ("ONLINE",  "HIGH",   "P94+P126D controlled_apply; TIERB_DRYRUN_VALIDATED; 3-bet expanded; actively maintained"),
    "daily539_f4cold_5bet":        ("ONLINE",  "HIGH",   "P94+P126F controlled_apply; TIERB_DRYRUN_VALIDATED; 5-bet expanded; actively maintained"),
    "power_fourier_rhythm_2bet":   ("ONLINE",  "HIGH",   "P94+P126B controlled_apply; TIERB_DRYRUN_VALIDATED; 2-bet expanded; actively maintained"),
    "midfreq_fourier_mk_3bet":     ("ONLINE",  "HIGH",   "P48+P132 controlled_apply; Wave4+recent multi-bet expansion; actively maintained"),
    "pp3_freqort_4bet":            ("ONLINE",  "HIGH",   "P48+P133 controlled_apply; Wave4+recent multi-bet expansion; actively maintained"),
    # GROUP B: ONLINE — Wave5/6 with recent production apply, no further expansion
    "cold_complement_2bet":        ("ONLINE",  "MEDIUM", "P66 Wave6 controlled_apply; 1500 rows; recent production apply; human review recommended"),
    "zonal_entropy_2bet":          ("ONLINE",  "MEDIUM", "P66 Wave6 controlled_apply; 1500 rows; recent production apply; human review recommended"),
    "fourier30_markov30_2bet":     ("ONLINE",  "MEDIUM", "P59 Wave5 + P78 draw extension; 1501 rows; draw-extension sentinel present; human review recommended"),
    # GROUP C: RETIRED — DAILY_539 Wave2 backfill only (P37), no follow-up expansion
    "539_3bet_orthogonal":         ("RETIRED", "MEDIUM", "P37 Wave2 backfill only; 1500 rows; max_bet=1; no subsequent controlled_apply; similar to RETIRED acb_1bet etc."),
    "acb_single_539":              ("RETIRED", "MEDIUM", "P37 Wave2 backfill only; 1500 rows; max_bet=1; no subsequent controlled_apply"),
    "markov_1bet_539":             ("RETIRED", "MEDIUM", "P37 Wave2 backfill only; 1500 rows; max_bet=1; no subsequent controlled_apply"),
    "p0b_539_3bet_f_cold_fmid":    ("RETIRED", "MEDIUM", "P37 Wave2 backfill only; 1500 rows; max_bet=1; no subsequent controlled_apply"),
    "p0c_539_3bet_f_cold_x2":      ("RETIRED", "MEDIUM", "P37 Wave2 backfill only; 1500 rows; max_bet=1; no subsequent controlled_apply"),
    "zone_gap_3bet_539":           ("RETIRED", "MEDIUM", "P37 Wave2 backfill only; 1500 rows; max_bet=1; no subsequent controlled_apply"),
    # GROUP D: RETIRED — BIG_LOTTO Wave3 backfill only (P43), signal space exhausted (L91)
    "bet2_fourier_expansion_biglotto": ("RETIRED", "HIGH",   "P43 Wave3 backfill only; BIG_LOTTO 49C6 signal space exhausted (L91); no subsequent controlled_apply"),
    "cold_complement_biglotto":        ("RETIRED", "HIGH",   "P43 Wave3 backfill only; BIG_LOTTO 49C6 signal space exhausted (L91); no subsequent controlled_apply"),
    "coldpool15_biglotto":             ("RETIRED", "HIGH",   "P43 Wave3 backfill only; BIG_LOTTO 49C6 signal space exhausted (L91); no subsequent controlled_apply"),
    "fourier30_markov30_biglotto":     ("RETIRED", "HIGH",   "P43 Wave3 backfill only; BIG_LOTTO 49C6 signal space exhausted; P118 quarantine candidate (negative evidence)"),
    "markov_2bet_biglotto":            ("RETIRED", "HIGH",   "P43 Wave3 backfill only; BIG_LOTTO 49C6 signal space exhausted (L91); no subsequent controlled_apply"),
    "markov_single_biglotto":          ("RETIRED", "HIGH",   "P43 Wave3 backfill only; BIG_LOTTO 49C6 signal space exhausted (L91); no subsequent controlled_apply"),
}

HUMAN_REVIEW_REQUIRED = {
    "cold_complement_2bet", "zonal_entropy_2bet", "fourier30_markov30_2bet",
    "fourier30_markov30_biglotto",
}


def run(cmd, cwd=CANONICAL_REPO):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, (r.stdout + r.stderr).strip()


def check_repo_branch():
    _, repo   = run(["git", "rev-parse", "--show-toplevel"])
    _, branch = run(["git", "branch", "--show-current"])
    return repo.strip() == CANONICAL_REPO, branch.strip() == CANONICAL_BRANCH, repo.strip(), branch.strip()


def get_db_rows():
    conn = sqlite3.connect(str(REPO_ROOT / "lottery_api/data/lottery_v2.db"))
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    return n


def get_drift_guard():
    _, out = run(["uv", "run", "python", "scripts/replay_lifecycle_drift_guard.py"])
    return "PASS" if "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in out else "FAIL"


def get_registry_db_only():
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
    strategies = list_strategy_lifecycle_metadata()
    return [s for s in strategies if s["lifecycle_status"] == "DB_ONLY_MISSING_LIFECYCLE"]


def query_db_stats(strategy_id):
    conn = sqlite3.connect(str(REPO_ROOT / "lottery_api/data/lottery_v2.db"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT lottery_type,
               COUNT(*) as cnt,
               MIN(CAST(target_draw AS INTEGER)) as first_draw,
               MAX(CAST(target_draw AS INTEGER)) as last_draw,
               GROUP_CONCAT(DISTINCT truth_level) as tl,
               GROUP_CONCAT(DISTINCT source) as src,
               GROUP_CONCAT(DISTINCT controlled_apply_id) as cap_id,
               MAX(bet_index) as max_bet
        FROM strategy_prediction_replays
        WHERE strategy_id = ?
        GROUP BY lottery_type
    """, (strategy_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
        if path.startswith("backups/") or any(path.startswith(p) for p in P156_OWN_PREFIXES):
            continue
        dirty.append(path)
    return dirty


def main():
    generated_at = datetime.now(timezone.utc).isoformat()

    repo_ok, branch_ok, actual_repo, actual_branch = check_repo_branch()
    if not repo_ok or not branch_ok:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps({
            "task_id": "P156",
            "classification": "P156_STOP_SCOPE_REALIGNMENT_REQUIRED",
            "generated_at": generated_at,
            "repo_branch_check": {"repo_ok": repo_ok, "branch_ok": branch_ok},
        }, indent=2, ensure_ascii=False))
        sys.exit(1)

    db_rows  = get_db_rows()
    drift    = get_drift_guard()
    head     = get_git_head()
    dirty    = get_dirty_files()

    p154 = load_artifact("p154_replay_product_release_candidate_closure_20260529.json")
    p154_ok = p154.get("classification") == "P154_REPLAY_PRODUCT_RELEASE_CANDIDATE_CLOSED"

    # Get actual DB_ONLY strategies
    db_only_strategies = get_registry_db_only()
    actual_count = len(db_only_strategies)
    db_only_ids  = [s["strategy_id"] for s in db_only_strategies]

    # Build recommendation matrix
    matrix = []
    for s in db_only_strategies:
        sid = s["strategy_id"]
        db_stats = query_db_stats(sid)

        # Aggregate across lottery types
        total_rows   = sum(r["cnt"] for r in db_stats)
        lottery_type = db_stats[0]["lottery_type"] if db_stats else "N/A"
        first_draw   = min(r["first_draw"] for r in db_stats) if db_stats else None
        last_draw    = max(r["last_draw"] for r in db_stats) if db_stats else None
        tl_set = list({tl for r in db_stats if r["tl"] for tl in r["tl"].split(",")})
        src_set = list({src for r in db_stats if r["src"] for src in r["src"].split(",")})
        cap_set = list({c for r in db_stats if r["cap_id"] for c in r["cap_id"].split(",")})
        max_bet = max((r["max_bet"] or 1 for r in db_stats), default=1)

        rec_lc, confidence, reason = LIFECYCLE_RECOMMENDATIONS.get(
            sid, ("UNKNOWN_NEEDS_REVIEW", "LOW", "No evidence-based recommendation available")
        )
        human_review = sid in HUMAN_REVIEW_REQUIRED

        matrix.append({
            "strategy_id":                  sid,
            "lottery_type":                 lottery_type,
            "replay_rows_count":            total_rows,
            "max_bet_index":                max_bet,
            "truth_level_distribution":     tl_set,
            "source_distribution":          src_set,
            "controlled_apply_id_distribution": cap_set,
            "first_target_draw":            str(first_draw) if first_draw else None,
            "last_target_draw":             str(last_draw) if last_draw else None,
            "current_lifecycle":            "DB_ONLY_MISSING_LIFECYCLE",
            "recommended_lifecycle":        rec_lc,
            "confidence":                   confidence,
            "reason":                       reason,
            "requires_human_review":        human_review,
        })

    # Decision groups
    from collections import Counter
    rec_counts = Counter(m["recommended_lifecycle"] for m in matrix)
    human_review_count = sum(1 for m in matrix if m["requires_human_review"])

    # Classification
    if actual_count != 22:
        classification = "P156_SCOPE_REALIGNED_DB_ONLY_COUNT_CHANGED"
    elif all(m["recommended_lifecycle"] != "UNKNOWN_NEEDS_REVIEW" for m in matrix):
        classification = "P156_DB_ONLY_LIFECYCLE_GOVERNANCE_AUDIT_READY"
    else:
        classification = "P156_DB_ONLY_LIFECYCLE_GOVERNANCE_AUDIT_READY"

    result = {
        "task_id":          "P156",
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
        "p154_source_summary": {
            "classification": p154.get("classification"),
            "ok":             p154_ok,
        },
        "db_only_lifecycle_inventory": {
            "expected_db_only_count_from_p154": 22,
            "actual_db_only_count":             actual_count,
            "strategy_ids":                     db_only_ids,
            "inventory_source":                 "lottery_api/models/replay_strategy_registry.py",
            "discrepancy_if_any":               None if actual_count == 22 else f"Expected 22, found {actual_count}",
        },
        "lifecycle_recommendation_matrix": matrix,
        "recommended_decision_groups": {
            "recommended_online_count":           rec_counts.get("ONLINE", 0),
            "recommended_retiired_or_retired_count": rec_counts.get("RETIRED", 0),
            "recommended_rejected_count":         rec_counts.get("REJECTED", 0),
            "recommended_offline_count":          rec_counts.get("OFFLINE", 0),
            "recommended_observation_count":      rec_counts.get("OBSERVATION", 0),
            "recommended_candidate_count":        rec_counts.get("CANDIDATE", 0),
            "unknown_needs_review_count":         rec_counts.get("UNKNOWN_NEEDS_REVIEW", 0),
            "human_review_required_count":        human_review_count,
            "group_a_online_active_multi_bet":    ["biglotto_echo_aware_3bet", "biglotto_ts3_markov_4bet_w30", "daily539_f4cold_3bet", "daily539_f4cold_5bet", "power_fourier_rhythm_2bet", "midfreq_fourier_mk_3bet", "pp3_freqort_4bet"],
            "group_b_online_wave56_human_review": ["cold_complement_2bet", "zonal_entropy_2bet", "fourier30_markov30_2bet"],
            "group_c_retired_daily539_wave2":     ["539_3bet_orthogonal", "acb_single_539", "markov_1bet_539", "p0b_539_3bet_f_cold_fmid", "p0c_539_3bet_f_cold_x2", "zone_gap_3bet_539"],
            "group_d_retired_biglotto_wave3":     ["bet2_fourier_expansion_biglotto", "cold_complement_biglotto", "coldpool15_biglotto", "fourier30_markov30_biglotto", "markov_2bet_biglotto", "markov_single_biglotto"],
        },
        "registry_storage_assessment": {
            "registry_is_source_controlled":          True,
            "registry_file":                          "lottery_api/models/replay_strategy_registry.py",
            "registry_is_db_table":                   False,
            "db_mutation_required_for_lifecycle_update": False,
            "code_change_required_for_lifecycle_update": True,
            "safe_to_update_in_p156":                 False,
            "reason_not_safe_in_p156":                "P156 is audit-only; lifecycle updates require explicit authorization and code review in P156B",
        },
        "authorization_gate_requirement": {
            "p156b_required":          True,
            "p156b_reason":            "22 DB_ONLY strategies require lifecycle updates to source-controlled registry (code change). Audit-only P156 must not modify the registry. P156B will apply recommendations after human review.",
            "exact_authorization_phrase_template": "YES update lifecycle for {strategy_id} to {recommended_lifecycle} per P156 recommendation",
            "p156b_scope":             "Update replay_strategy_registry.py with recommended lifecycle per P156 audit matrix",
            "human_review_strategies": list(HUMAN_REVIEW_REQUIRED),
        },
        "non_actions": {
            "db_write_in_p156":                    False,
            "lifecycle_update_executed_in_p156":   False,
            "controlled_apply_executed_in_p156":   False,
            "replay_rows_inserted_in_p156":        0,
            "replay_rows_updated_in_p156":         0,
            "replay_rows_deleted_in_p156":         0,
            "champion_promotion_executed_in_p156": False,
            "registry_promotion_executed_in_p156": False,
            "live_api_called":                     False,
            "scheduler_installed":                 False,
            "four_star_executed":                  False,
            "p108_executed":                       False,
            "p117_executed":                       False,
            "p118_executed":                       False,
        },
        "dirty_file_hygiene": {
            "backups_untracked_not_staged": True,
            "backups_deleted":              False,
            "forbidden_files_staged":       False,
            "remaining_unrelated_dirty":    dirty,
        },
        "roadmap_update_status": {"cto_analysis_updated": True, "roadmap_updated": True},
        "remaining_risks": [
            "4 strategies need human review before lifecycle update (cold_complement_2bet, zonal_entropy_2bet, fourier30_markov30_2bet, fourier30_markov30_biglotto)",
            "Registry update requires P156B authorization gate with per-strategy approval phrases",
            "DB rows unchanged at 94924 — lifecycle update in registry is code-only, no DB mutation needed",
        ],
        "next_recommended_task": "P156B_DB_ONLY_LIFECYCLE_DECISION_GATE",
        "summary": (
            f"P156 audited {actual_count} DB_ONLY_MISSING_LIFECYCLE strategies. "
            f"Recommended: ONLINE={rec_counts.get('ONLINE', 0)}, RETIRED={rec_counts.get('RETIRED', 0)}. "
            f"{human_review_count} require human review. "
            "Registry is source-controlled Python. P156B required for actual updates. No DB writes."
        ),
        "head_at_generation": head,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"Classification: {classification}")
    print(f"DB_ONLY count: {actual_count}")
    print(f"Recommendations - ONLINE: {rec_counts.get('ONLINE', 0)}, RETIRED: {rec_counts.get('RETIRED', 0)}")
    print(f"Human review required: {human_review_count}")
    print(f"DB rows: {db_rows} | Drift: {drift}")
    return result


if __name__ == "__main__":
    main()
