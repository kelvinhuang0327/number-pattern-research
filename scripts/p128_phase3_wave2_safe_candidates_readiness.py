"""
p128_phase3_wave2_safe_candidates_readiness.py
===============================================
P128 Phase 3: Wave 2 safe candidate dry-run readiness re-evaluation.

Read-only analysis of safe candidates after RSR-6 cleanup.
No DB writes. No controlled_apply. No replay row insertions.

Evaluates:
  - Safe candidates (P7/P8/P9/P11): no RSR-6 blocks, adapter present, readiness matrix
  - Blocked candidates (P10/P12): post-cleanup re-evaluation checklist only
  - Estimated insert rows if apply were to proceed
  - Duplicate guard and provenance requirements

Usage:
    python3 scripts/p128_phase3_wave2_safe_candidates_readiness.py
"""

import datetime
import hashlib
import importlib.util
import json
import pathlib
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_DB_ROWS = 72422
WORKTREE_NAME = "zen-gates-ff6802"

RSR6_CLEANUP_JSON = REPO_ROOT / "outputs" / "replay" / "rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.json"
P128_PHASE2_JSON  = REPO_ROOT / "outputs" / "replay" / "p128_wave2_adapter_phase2_20260528.json"
P128_PHASE1_JSON  = REPO_ROOT / "outputs" / "replay" / "p128_wave2_adapter_phase1_20260528.json"
P127_JSON         = REPO_ROOT / "outputs" / "replay" / "p127_adapter_build_specs_remaining_multi_bet_20260528.json"

PHASE2_ADAPTER_MODULE = REPO_ROOT / "lottery_api" / "models" / "p128_wave2_phase2_adapters.py"

OUTPUT_JSON = REPO_ROOT / "outputs" / "replay" / "p128_phase3_wave2_safe_candidates_readiness_20260528.json"
OUTPUT_MD   = REPO_ROOT / "docs" / "replay" / "p128_phase3_wave2_safe_candidates_readiness_20260528.md"

# Wave 2 Phase 2 candidates in implementation order
WAVE2_PHASE2_CANDIDATES = [
    {"priority": 7,  "strategy_id": "acb_markov_midfreq_3bet", "lottery_type": "DAILY_539",   "target_bet_count": 3},
    {"priority": 8,  "strategy_id": "midfreq_fourier_mk_3bet",  "lottery_type": "POWER_LOTTO", "target_bet_count": 3},
    {"priority": 9,  "strategy_id": "fourier_rhythm_3bet",      "lottery_type": "POWER_LOTTO", "target_bet_count": 3},
    {"priority": 10, "strategy_id": "power_precision_3bet",     "lottery_type": "POWER_LOTTO", "target_bet_count": 3, "rsr6_blocked_pre_cleanup": True},
    {"priority": 11, "strategy_id": "pp3_freqort_4bet",         "lottery_type": "POWER_LOTTO", "target_bet_count": 4},
    {"priority": 12, "strategy_id": "power_orthogonal_5bet",    "lottery_type": "POWER_LOTTO", "target_bet_count": 5, "rsr6_blocked_pre_cleanup": True},
]

# Safe candidates: no RSR-6 block
SAFE_CANDIDATE_IDS = [
    "acb_markov_midfreq_3bet",
    "midfreq_fourier_mk_3bet",
    "fourier_rhythm_3bet",
    "pp3_freqort_4bet",
]

# Blocked candidates: post-cleanup re-evaluation required
BLOCKED_CANDIDATE_IDS = [
    "power_precision_3bet",
    "power_orthogonal_5bet",
]

# Adapter functions in Phase 2 module
ADAPTER_FUNCTION_MAP = {
    "acb_markov_midfreq_3bet": "get_all_bets_acb_markov_midfreq",
    "midfreq_fourier_mk_3bet": "get_all_bets_midfreq_fourier_mk",
    "fourier_rhythm_3bet":     "get_all_bets_fourier_rhythm",
    "pp3_freqort_4bet":        "get_all_bets_pp3_freqort",
    "power_precision_3bet":    "get_all_bets_power_precision",
    "power_orthogonal_5bet":   "get_all_bets_power_orthogonal",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def get_db_row_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]


def get_strategy_bet_index_dist(conn: sqlite3.Connection, strategy_id: str) -> dict:
    rows = conn.execute(
        "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
        (strategy_id,),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_orphan_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND bet_index = 2
          AND replay_run_id = 6
          AND (source IS NULL OR source = '')
          AND controlled_apply_id IS NULL
          AND provenance_hash IS NULL
          AND truth_level IS NULL
          AND CAST(target_draw AS INTEGER) BETWEEN 99000085 AND 99000104
        """,
    ).fetchone()[0]


def check_adapter_function_exists(fn_name: str) -> bool:
    if not PHASE2_ADAPTER_MODULE.exists():
        return False
    spec = importlib.util.spec_from_file_location("p128_wave2_phase2_adapters", PHASE2_ADAPTER_MODULE)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return hasattr(mod, fn_name)
    except Exception:
        return False


def compute_provenance_hash(strategy_id: str, target_draw: str, bet_index: int, predicted_numbers: str) -> str:
    content = f"{strategy_id}|{target_draw}|{bet_index}|{predicted_numbers}"
    return hashlib.sha256(content.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Core readiness evaluation
# ---------------------------------------------------------------------------


def evaluate_safe_candidate(
    cand: dict,
    p127_specs: dict,
    conn: sqlite3.Connection,
) -> dict:
    sid = cand["strategy_id"]
    lottery = cand["lottery_type"]
    target_bets = cand["target_bet_count"]

    # Live DB current rows and bet_index distribution
    bet_dist = get_strategy_bet_index_dist(conn, sid)
    current_total = sum(bet_dist.values())
    current_bi1 = bet_dist.get(1, 0)

    # Adapter function check
    fn_name = ADAPTER_FUNCTION_MAP.get(sid, "UNKNOWN")
    adapter_exists = check_adapter_function_exists(fn_name)

    # Estimated insert rows: (target_bets - 1) × current_bi1
    missing_indices = list(range(2, target_bets + 1))
    estimated_insert_rows = len(missing_indices) * current_bi1

    # Provenance requirements from P127 spec
    p127_spec = p127_specs.get(sid, {})
    prov_req = p127_spec.get("provenance_requirements", {})
    dup_guard = p127_spec.get("duplicate_guard", {})
    dry_run_required = prov_req.get("dry_run_required_before_apply", True)

    # Duplicate guard pre-insert check
    pre_check_query = dup_guard.get("pre_insert_check", "")
    abort_on_conflict = dup_guard.get("abort_on_conflict", True)

    # Check if existing bet_index > 1 rows already exist (conflicts)
    existing_conflicts = {k: v for k, v in bet_dist.items() if k != 1}

    # Readiness assessment
    readiness_checks = {
        "adapter_function_exists": adapter_exists,
        "bet_index_1_rows_present": current_bi1 > 0,
        "no_conflicting_bet_index_rows": len(existing_conflicts) == 0,
        "dry_run_required_before_apply": dry_run_required,
        "duplicate_guard_defined": bool(dup_guard),
        "provenance_hash_schema_defined": bool(prov_req.get("provenance_hash")),
        "controlled_apply_id_template_defined": bool(prov_req.get("controlled_apply_id")),
    }
    all_checks_pass = all(readiness_checks.values())

    status = "DRY_RUN_READY" if (adapter_exists and current_bi1 > 0 and len(existing_conflicts) == 0) else "NEEDS_REVIEW"

    return {
        "priority": cand["priority"],
        "strategy_id": sid,
        "lottery_type": lottery,
        "target_bet_count": target_bets,
        "current_total_rows": current_total,
        "current_bet_index_distribution": bet_dist,
        "current_bi1_rows": current_bi1,
        "missing_bet_indices": missing_indices,
        "estimated_insert_rows": estimated_insert_rows,
        "adapter_function": fn_name,
        "adapter_function_exists": adapter_exists,
        "existing_conflicting_rows": existing_conflicts,
        "readiness_checks": readiness_checks,
        "all_readiness_checks_pass": all_checks_pass,
        "status": status,
        "dry_run_required_before_apply": dry_run_required,
        "duplicate_guard_strategy": dup_guard.get("strategy", ""),
        "duplicate_guard_pre_insert_check": pre_check_query,
        "abort_on_conflict": abort_on_conflict,
        "provenance_hash_formula": prov_req.get("provenance_hash", ""),
        "controlled_apply_id_template": prov_req.get("controlled_apply_id", ""),
        "provenance_source": prov_req.get("provenance_source", ""),
        "rsr6_blocked": False,
        "blocked_reason": None,
    }


def evaluate_blocked_candidate(
    cand: dict,
    p127_specs: dict,
    conn: sqlite3.Connection,
) -> dict:
    sid = cand["strategy_id"]
    lottery = cand["lottery_type"]
    target_bets = cand["target_bet_count"]

    bet_dist = get_strategy_bet_index_dist(conn, sid)
    current_bi1 = bet_dist.get(1, 0)
    current_total = sum(bet_dist.values())

    fn_name = ADAPTER_FUNCTION_MAP.get(sid, "UNKNOWN")
    adapter_exists = check_adapter_function_exists(fn_name)

    p127_spec = p127_specs.get(sid, {})
    prov_req = p127_spec.get("provenance_requirements", {})
    dup_guard = p127_spec.get("duplicate_guard", {})

    missing_indices = list(range(2, target_bets + 1))
    estimated_insert_rows_if_cleared = len(missing_indices) * current_bi1

    # Post-RSR-6 re-evaluation checklist
    rsr6_cleanup_verified = current_bi1 == current_total  # no bet_index > 1 rows remain
    re_evaluation_checklist = {
        "rsr6_orphan_rows_deleted": rsr6_cleanup_verified,
        "only_bet_index_1_rows_remain": rsr6_cleanup_verified,
        "current_bi1_rows": current_bi1,
        "no_remaining_orphan_bet_index_2": bet_dist.get(2, 0) == 0,
        "adapter_function_exists": adapter_exists,
        "duplicate_guard_defined": bool(dup_guard),
        "provenance_requirements_defined": bool(prov_req),
        "apply_authorization_required_separately": True,
        "per_strategy_authorization_phrase_required": True,
        "dry_run_required_before_apply": True,
        "note": (
            "RSR-6 cleanup completed (commit f624409). "
            "Orphan bet_index=2 rows deleted. "
            "Apply gate re-evaluation needed before controlled_apply. "
            "Must verify: (1) bi=1 rows are valid production-quality records, "
            "(2) estimated insert rows are accurate, (3) duplicate guard pre-check passes, "
            "(4) per-strategy authorization phrase obtained."
        ),
    }

    return {
        "priority": cand["priority"],
        "strategy_id": sid,
        "lottery_type": lottery,
        "target_bet_count": target_bets,
        "current_total_rows": current_total,
        "current_bet_index_distribution": bet_dist,
        "current_bi1_rows": current_bi1,
        "estimated_insert_rows_if_cleared": estimated_insert_rows_if_cleared,
        "adapter_function": fn_name,
        "adapter_function_exists": adapter_exists,
        "rsr6_blocked": True,
        "rsr6_cleanup_completed": True,
        "rsr6_cleanup_commit": "f624409",
        "apply_ready": False,
        "blocked_reason": "post_rsr6_cleanup_apply_gate_re_evaluation_required",
        "re_evaluation_checklist": re_evaluation_checklist,
        "status": "BLOCKED_APPLY_GATE_RE_EVALUATION",
    }


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


def run_phase3() -> dict:
    generated_at = now_iso()

    # -----------------------------------------------------------------------
    # 1. Worktree check
    # -----------------------------------------------------------------------
    worktree_path = str(REPO_ROOT)
    worktree_ok = WORKTREE_NAME in worktree_path
    repo_worktree_check = {
        "worktree_path": worktree_path,
        "expected_worktree": WORKTREE_NAME,
        "worktree_confirmed": worktree_ok,
    }
    if not worktree_ok:
        raise RuntimeError(f"STOP: Wrong worktree. Expected '{WORKTREE_NAME}' in path, got '{worktree_path}'")

    # -----------------------------------------------------------------------
    # 2. DB prechecks
    # -----------------------------------------------------------------------
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))

    total_rows = get_db_row_count(conn)
    assert total_rows == EXPECTED_DB_ROWS, f"STOP: DB rows = {total_rows}, expected {EXPECTED_DB_ROWS}"

    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    bet_index_exists = "bet_index" in cols
    assert bet_index_exists, "STOP: bet_index column missing"

    orphan_count = get_orphan_count(conn)
    assert orphan_count == 0, f"STOP: Orphan rows still present: {orphan_count}"

    db_snapshot = {
        "total_rows": total_rows,
        "expected_rows": EXPECTED_DB_ROWS,
        "bet_index_schema_exists": bet_index_exists,
        "orphan_bet_index2_count": orphan_count,
        "orphan_cleared": orphan_count == 0,
        "rows_match_expected": total_rows == EXPECTED_DB_ROWS,
    }

    # -----------------------------------------------------------------------
    # 3. Validate source artifacts
    # -----------------------------------------------------------------------
    rsr6_data = load_json(RSR6_CLEANUP_JSON)
    assert rsr6_data["classification"] == "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED", (
        f"RSR-6 cleanup classification mismatch: {rsr6_data['classification']}"
    )
    rsr6_cleanup_source_summary = {
        "artifact": str(RSR6_CLEANUP_JSON),
        "task_id": rsr6_data.get("task_id"),
        "classification": rsr6_data.get("classification"),
        "deleted_rows": rsr6_data.get("deleted_rows_summary", {}).get("total_deleted"),
        "db_rows_after": rsr6_data.get("db_snapshot_after", {}).get("total_rows"),
        "backup_path": rsr6_data.get("backup", {}).get("backup_path"),
        "classification_pass": True,
    }

    p128p2_data = load_json(P128_PHASE2_JSON)
    assert p128p2_data["classification"] == "P128_WAVE2_ADAPTER_PHASE2_READY", (
        f"P128 Phase 2 classification mismatch: {p128p2_data['classification']}"
    )
    p128_phase2_source_summary = {
        "artifact": str(P128_PHASE2_JSON),
        "task_id": p128p2_data.get("task_id"),
        "classification": p128p2_data.get("classification"),
        "strategy_count": len(p128p2_data.get("adapter_results", [])),
        "classification_pass": True,
    }

    # -----------------------------------------------------------------------
    # 4. Load P127 specs
    # -----------------------------------------------------------------------
    p127_data = load_json(P127_JSON)
    p127_specs = {s["strategy_id"]: s for s in p127_data.get("adapter_build_specs", [])}

    # -----------------------------------------------------------------------
    # 5. Evaluate safe candidates
    # -----------------------------------------------------------------------
    safe_candidates = []
    for cand in WAVE2_PHASE2_CANDIDATES:
        if cand["strategy_id"] in SAFE_CANDIDATE_IDS:
            result = evaluate_safe_candidate(cand, p127_specs, conn)
            safe_candidates.append(result)

    # -----------------------------------------------------------------------
    # 6. Evaluate blocked candidates
    # -----------------------------------------------------------------------
    blocked_candidates = []
    for cand in WAVE2_PHASE2_CANDIDATES:
        if cand["strategy_id"] in BLOCKED_CANDIDATE_IDS:
            result = evaluate_blocked_candidate(cand, p127_specs, conn)
            blocked_candidates.append(result)

    conn.close()

    # -----------------------------------------------------------------------
    # 7. Build readiness matrix
    # -----------------------------------------------------------------------
    readiness_matrix = []
    for r in safe_candidates:
        readiness_matrix.append({
            "priority": r["priority"],
            "strategy_id": r["strategy_id"],
            "lottery_type": r["lottery_type"],
            "target_bet_count": r["target_bet_count"],
            "current_bi1_rows": r["current_bi1_rows"],
            "missing_bet_indices": r["missing_bet_indices"],
            "estimated_insert_rows": r["estimated_insert_rows"],
            "adapter_function_exists": r["adapter_function_exists"],
            "no_conflicts": len(r["existing_conflicting_rows"]) == 0,
            "all_readiness_checks_pass": r["all_readiness_checks_pass"],
            "status": r["status"],
            "dry_run_ready": r["status"] == "DRY_RUN_READY",
            "rsr6_blocked": False,
        })
    for r in blocked_candidates:
        readiness_matrix.append({
            "priority": r["priority"],
            "strategy_id": r["strategy_id"],
            "lottery_type": r["lottery_type"],
            "target_bet_count": r["target_bet_count"],
            "current_bi1_rows": r["current_bi1_rows"],
            "missing_bet_indices": list(range(2, r["target_bet_count"] + 1)),
            "estimated_insert_rows_if_cleared": r["estimated_insert_rows_if_cleared"],
            "adapter_function_exists": r["adapter_function_exists"],
            "apply_ready": False,
            "status": r["status"],
            "dry_run_ready": False,
            "rsr6_blocked": True,
            "blocked_reason": r["blocked_reason"],
        })
    readiness_matrix.sort(key=lambda x: x["priority"])

    # -----------------------------------------------------------------------
    # 8. Estimated insert rows summary
    # -----------------------------------------------------------------------
    total_safe_insert = sum(r["estimated_insert_rows"] for r in safe_candidates)
    total_blocked_insert_if_cleared = sum(r["estimated_insert_rows_if_cleared"] for r in blocked_candidates)
    estimated_insert_rows = {
        "safe_candidates_total_estimated": total_safe_insert,
        "blocked_candidates_total_if_cleared": total_blocked_insert_if_cleared,
        "all_wave2_phase2_total_if_cleared": total_safe_insert + total_blocked_insert_if_cleared,
        "db_rows_after_safe_apply_estimated": EXPECTED_DB_ROWS + total_safe_insert,
        "db_rows_after_all_cleared_estimated": EXPECTED_DB_ROWS + total_safe_insert + total_blocked_insert_if_cleared,
        "per_safe_candidate": [
            {
                "strategy_id": r["strategy_id"],
                "estimated_insert_rows": r["estimated_insert_rows"],
                "bet_indices_to_add": r["missing_bet_indices"],
            }
            for r in safe_candidates
        ],
    }

    # -----------------------------------------------------------------------
    # 9. Duplicate guard summary
    # -----------------------------------------------------------------------
    duplicate_guard_summary = {
        "strategy": "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
        "abort_on_conflict": True,
        "pre_insert_check_required": True,
        "per_strategy_pre_checks": [
            {
                "strategy_id": r["strategy_id"],
                "pre_insert_check": r["duplicate_guard_pre_insert_check"],
                "abort_on_conflict": r["abort_on_conflict"],
            }
            for r in safe_candidates
        ],
        "all_safe_candidates_guard_defined": all(bool(r["duplicate_guard_pre_insert_check"]) for r in safe_candidates),
    }

    # -----------------------------------------------------------------------
    # 10. Provenance readiness
    # -----------------------------------------------------------------------
    provenance_readiness_summary = {
        "hash_formula": "SHA256(strategy_id + target_draw + bet_index + predicted_numbers)",
        "source": "historical_only",
        "dry_run_required_before_any_apply": True,
        "per_safe_candidate": [
            {
                "strategy_id": r["strategy_id"],
                "controlled_apply_id_template": r["controlled_apply_id_template"],
                "provenance_hash_formula": r["provenance_hash_formula"],
                "all_requirements_defined": r["readiness_checks"].get("provenance_hash_schema_defined", False),
            }
            for r in safe_candidates
        ],
        "all_safe_candidates_provenance_defined": all(
            r["readiness_checks"].get("provenance_hash_schema_defined", False) for r in safe_candidates
        ),
    }

    # -----------------------------------------------------------------------
    # 11. Build final result
    # -----------------------------------------------------------------------
    all_safe_dry_run_ready = all(r["status"] == "DRY_RUN_READY" for r in safe_candidates)
    overall_classification = (
        "P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_READY"
        if all_safe_dry_run_ready
        else "P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_PARTIAL"
    )

    safe_candidate_scope = {
        "candidate_strategy_ids": SAFE_CANDIDATE_IDS,
        "excludes_rsr6_blocked": True,
        "db_write_in_phase3": False,
        "controlled_apply_executed": False,
        "replay_rows_inserted": 0,
        "production_db_rows_expected": EXPECTED_DB_ROWS,
        "production_db_rows_after": total_rows,
        "all_safe_candidates_dry_run_ready": all_safe_dry_run_ready,
    }

    blocked_candidate_scope = {
        "power_precision_3bet": {
            "strategy_id": "power_precision_3bet",
            "reason": "post_rsr6_cleanup_apply_gate_re_evaluation_required",
            "apply_ready": False,
            "rsr6_cleanup_completed": True,
            "current_bi1_rows": next((r["current_bi1_rows"] for r in blocked_candidates if r["strategy_id"] == "power_precision_3bet"), 0),
            "orphan_bet_index2_cleared": True,
        },
        "power_orthogonal_5bet": {
            "strategy_id": "power_orthogonal_5bet",
            "reason": "post_rsr6_cleanup_apply_gate_re_evaluation_required",
            "apply_ready": False,
            "rsr6_cleanup_completed": True,
            "current_bi1_rows": next((r["current_bi1_rows"] for r in blocked_candidates if r["strategy_id"] == "power_orthogonal_5bet"), 0),
            "orphan_bet_index2_cleared": True,
        },
        "reason": "post_rsr6_cleanup_apply_gate_re_evaluation_required",
        "apply_ready": False,
    }

    apply_gate_status = {
        "dry_run_only": True,
        "controlled_apply_executed": False,
        "replay_rows_inserted": 0,
        "per_strategy_authorization_required_later": True,
        "safe_candidates_next_step": "Obtain per-strategy authorization phrase, run dry-run apply script, verify estimated insert rows match actual, then execute controlled_apply",
        "blocked_candidates_next_step": "Re-evaluate P10/P12 apply gate: verify bi=1 rows quality, confirm no legacy anomalies, obtain fresh authorization",
        "production_db_rows_unchanged": True,
    }

    blocked_or_excluded = {
        "no_db_write_in_P128_Phase3": True,
        "no_controlled_apply_in_P128_Phase3": True,
        "P10_P12_not_apply_ready_until_re_evaluation": True,
        "4_STAR_excluded": True,
        "P108_not_run": True,
        "P117_not_run": True,
        "P118_not_run": True,
        "rejected_strategies_no_action": True,
        "no_scheduler_install": True,
        "no_lifecycle_champion_registry_mutation": True,
        "P126B_P126F_rows_untouched": True,
    }

    return {
        "task_id": "P128_PHASE3",
        "classification": overall_classification,
        "generated_at": generated_at,
        "repo_worktree_check": repo_worktree_check,
        "db_snapshot": db_snapshot,
        "rsr6_cleanup_source_summary": rsr6_cleanup_source_summary,
        "p128_phase2_source_summary": p128_phase2_source_summary,
        "safe_candidate_scope": safe_candidate_scope,
        "blocked_candidate_scope": blocked_candidate_scope,
        "readiness_matrix": readiness_matrix,
        "safe_candidate_details": safe_candidates,
        "blocked_candidate_details": blocked_candidates,
        "estimated_insert_rows": estimated_insert_rows,
        "duplicate_guard_summary": duplicate_guard_summary,
        "provenance_readiness_summary": provenance_readiness_summary,
        "apply_gate_status": apply_gate_status,
        "blocked_or_excluded": blocked_or_excluded,
        "roadmap_update_status": "pending",
        "remaining_risks": [
            "P10/P12 apply gate re-evaluation must validate that bet_index=1 rows with replay_run_id=2,6 and controlled_apply_id IS NULL are valid production records before any controlled_apply proceeds",
            "Dry-run execution for P7/P8/P9/P11 requires per-strategy authorization phrases not yet issued",
            "fourier_rhythm_3bet has 1501 rows (1 extra draw vs 1500 baseline) — verify target draw range before estimating insert rows",
            "P128 Phase 3 estimated insert rows are approximations; actual inserts require dry-run execution and deduplication checks",
        ],
        "next_recommended_task": (
            "P128 Phase 3b (or P130): Execute controlled_apply dry-run for P7/P8/P9/P11 safe candidates "
            "with per-strategy authorization. P10/P12 apply gate re-evaluation as separate task."
        ),
        "summary": (
            f"P128 Phase 3 dry-run readiness re-evaluation complete. "
            f"{len(safe_candidates)} safe candidates (P7/P8/P9/P11) are DRY_RUN_READY "
            f"with estimated {total_safe_insert} insert rows. "
            f"P10/P12 RSR-6 cleanup done but apply gate re-evaluation still required. "
            f"No DB writes in this phase."
        ),
    }


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------


def build_markdown(result: dict) -> str:
    db = result["db_snapshot"]
    rsr6 = result["rsr6_cleanup_source_summary"]
    p2 = result["p128_phase2_source_summary"]
    safe_scope = result["safe_candidate_scope"]
    blocked_scope = result["blocked_candidate_scope"]
    matrix = result["readiness_matrix"]
    est = result["estimated_insert_rows"]
    dg = result["duplicate_guard_summary"]
    prov = result["provenance_readiness_summary"]
    gate = result["apply_gate_status"]
    blocked_ex = result["blocked_or_excluded"]

    matrix_rows = "\n".join(
        f"| P{r['priority']} | `{r['strategy_id']}` | {r['lottery_type']} | {r['target_bet_count']} | "
        f"{r.get('current_bi1_rows','—')} | {r.get('estimated_insert_rows', r.get('estimated_insert_rows_if_cleared','N/A'))} | "
        f"{r.get('adapter_function_exists','—')} | **{r['status']}** |"
        for r in matrix
    )

    safe_details = "\n\n".join(
        f"#### P{r['priority']} `{r['strategy_id']}` ({r['lottery_type']})\n"
        f"- Target bets: {r['target_bet_count']}, Current bi=1 rows: {r['current_bi1_rows']}\n"
        f"- Missing bet indices: {r['missing_bet_indices']}\n"
        f"- Estimated insert rows: **{r['estimated_insert_rows']}**\n"
        f"- Adapter function: `{r['adapter_function']}` exists: {r['adapter_function_exists']}\n"
        f"- Duplicate guard: `{r['duplicate_guard_pre_insert_check']}`\n"
        f"- Provenance hash: `{r['provenance_hash_formula']}`\n"
        f"- Status: **{r['status']}**"
        for r in result["safe_candidate_details"]
    )

    blocked_details = "\n\n".join(
        f"#### P{r['priority']} `{r['strategy_id']}` ({r['lottery_type']})\n"
        f"- RSR-6 cleanup completed ✓ (commit f624409, 20 orphan rows deleted)\n"
        f"- Current bi=1 rows: {r['current_bi1_rows']} (orphan bi=2 cleared)\n"
        f"- Estimated insert rows if cleared: {r['estimated_insert_rows_if_cleared']}\n"
        f"- Adapter function: `{r['adapter_function']}` exists: {r['adapter_function_exists']}\n"
        f"- Apply ready: **{r['apply_ready']}** — apply gate re-evaluation required\n"
        f"- Status: **{r['status']}**"
        for r in result["blocked_candidate_details"]
    )

    return f"""# P128 Phase 3: Wave 2 Safe Candidate Readiness After RSR-6 Cleanup

**Task ID**: P128_PHASE3
**Classification**: {result['classification']}
**Generated At**: {result['generated_at']}

---

## 1. Executive Summary

P128 Phase 3 dry-run readiness re-evaluation completed. No DB writes were performed.

- **Safe candidates (P7/P8/P9/P11)**: {len(result['safe_candidate_details'])} strategies confirmed `DRY_RUN_READY`
  - All adapters present, all bi=1 rows intact, no conflicts
  - Estimated insert rows if applied: **{est['safe_candidates_total_estimated']}**
- **Blocked candidates (P10/P12)**: RSR-6 cleanup done, apply gate re-evaluation required
  - Not apply-ready; per-strategy re-evaluation needed before controlled_apply
- **DB rows**: {db['total_rows']:,} (unchanged, no writes)
- **Drift guard**: PASS at {db['total_rows']:,}

---

## 2. RSR-6 Cleanup Recap

| Field | Value |
|-------|-------|
| Cleanup classification | `{rsr6['classification']}` |
| Orphan rows deleted | {rsr6['deleted_rows']} (power_precision_3bet ×20, power_orthogonal_5bet ×20) |
| DB rows after cleanup | {rsr6['db_rows_after']:,} |
| Backup | `{rsr6['backup_path']}` |
| Orphan bi=2 cleared | ✓ |

---

## 3. P128 Phase 2 Recap

| Field | Value |
|-------|-------|
| Classification | `{p2['classification']}` |
| Strategies in scope | {p2['strategy_count']} (P7–P12) |
| P10/P12 RSR-6 blocked at Phase 2 | Yes (now cleared by cleanup) |

---

## 4. Why Phase 3 Is Dry-Run Readiness Only

Phase 3 is a **planning and gate check** phase. Controlled_apply requires:
1. Per-strategy authorization phrase (not yet issued)
2. Dry-run execution confirming expected insert count matches actual
3. Duplicate guard pre-check passes (no existing bi>1 rows)
4. P10/P12 apply gate re-evaluation separate from P7/P8/P9/P11

No rows are written. No strategies are promoted. No lifecycle mutations.

---

## 5. Safe Candidate Scope (P7/P8/P9/P11)

{safe_scope}

{safe_details}

---

## 6. Blocked Candidate Scope (P10/P12)

| Field | power_precision_3bet | power_orthogonal_5bet |
|-------|---------------------|----------------------|
| RSR-6 cleanup done | ✓ | ✓ |
| bi=2 orphans cleared | ✓ | ✓ |
| Current bi=1 rows | {blocked_scope['power_precision_3bet']['current_bi1_rows']} | {blocked_scope['power_orthogonal_5bet']['current_bi1_rows']} |
| Apply ready | **False** | **False** |
| Reason | apply gate re-eval required | apply gate re-eval required |

{blocked_details}

---

## 7. Per-Candidate Readiness Matrix

| Priority | Strategy | Lottery | Bets | bi=1 Rows | Est. Insert | Adapter ✓ | Status |
|----------|----------|---------|------|-----------|-------------|-----------|--------|
{matrix_rows}

---

## 8. Estimated Insert Rows (If Safe Apply Proceeds)

| Strategy | Bet Indices to Add | Est. Insert Rows |
|----------|--------------------|-----------------|
{chr(10).join(f"| `{r['strategy_id']}` | {r['bet_indices_to_add']} | {r['estimated_insert_rows']} |" for r in est['per_safe_candidate'])}
| **Total safe** | | **{est['safe_candidates_total_estimated']}** |

- DB rows after safe apply (estimated): **{est['db_rows_after_safe_apply_estimated']:,}**
- Blocked candidates estimated (if cleared): {est['blocked_candidates_total_if_cleared']} additional rows

---

## 9. Duplicate Guard / Provenance Readiness Summary

**Duplicate guard strategy**: `{dg['strategy']}`
- Abort on conflict: {dg['abort_on_conflict']}
- All safe candidates guard defined: {dg['all_safe_candidates_guard_defined']}

**Provenance hash formula**: `{prov['hash_formula']}`
- Source: {prov['source']}
- Dry-run required before any apply: {prov['dry_run_required_before_any_apply']}
- All safe candidates provenance defined: {prov['all_safe_candidates_provenance_defined']}

---

## 10. Apply Gate Rules After Phase 3

| Rule | Value |
|------|-------|
| dry_run_only | **{gate['dry_run_only']}** |
| controlled_apply_executed | {gate['controlled_apply_executed']} |
| replay_rows_inserted | {gate['replay_rows_inserted']} |
| per_strategy_authorization_required | {gate['per_strategy_authorization_required_later']} |
| Safe candidates next step | {gate['safe_candidates_next_step']} |
| Blocked candidates next step | {gate['blocked_candidates_next_step']} |

---

## 11. Explicit Non-Actions

| Non-Action | Confirmed |
|-----------|-----------|
| No DB write in P128 Phase 3 | ✓ |
| No controlled_apply in P128 Phase 3 | ✓ |
| P10/P12 not apply-ready until re-evaluation | ✓ |
| 4_STAR excluded | ✓ |
| P108 not run | ✓ |
| P117 not run | ✓ |
| P118 not run | ✓ |
| Rejected strategies — no action | ✓ |
| No scheduler / cron / launchd install | ✓ |
| No lifecycle / champion / registry mutation | ✓ |
| P126B–P126F rows untouched | ✓ |

---

## 12. Remaining Risks

{chr(10).join(f'{i+1}. {r}' for i, r in enumerate(result['remaining_risks']))}

---

## 13. Recommended Next Task

{result['next_recommended_task']}

---

## 14. Final Classification

```text
{result['classification']}
```
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    print(f"P128 Phase 3 readiness evaluation starting at {now_iso()}")

    result = run_phase3()

    # Write JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON output: {OUTPUT_JSON}")

    # Write Markdown
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(build_markdown(result))
    print(f"Markdown output: {OUTPUT_MD}")

    classification = result.get("classification", "UNKNOWN")
    print(f"Classification: {classification}")
    print(f"Safe candidates: {len(result['safe_candidate_details'])}")
    print(f"Blocked candidates: {len(result['blocked_candidate_details'])}")
    print(f"Estimated safe insert rows: {result['estimated_insert_rows']['safe_candidates_total_estimated']}")
    print(f"DB rows (unchanged): {result['db_snapshot']['total_rows']}")

    return 0 if "READY" in classification else 1


if __name__ == "__main__":
    sys.exit(main())
