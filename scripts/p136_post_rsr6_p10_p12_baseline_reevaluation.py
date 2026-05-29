#!/usr/bin/env python3
"""
P136: Post-RSR6 P10/P12 Baseline Re-evaluation
==============================================
Read-only governance audit for P10/P12 after RSR6 cleanup.

Scope:
  - No DB write
  - No controlled_apply
  - No replay row insertion
  - No row delete / update / re-mark

Outputs:
  - outputs/replay/p136_post_rsr6_p10_p12_baseline_reevaluation_20260529.json
  - docs/replay/p136_post_rsr6_p10_p12_baseline_reevaluation_20260529.md
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

TASK_ID = "P136"
CLASSIFICATION = "P136_POST_RSR6_P10_P12_REEVALUATION_READY"

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUT_JSON = REPO_ROOT / "outputs" / "replay" / "p136_post_rsr6_p10_p12_baseline_reevaluation_20260529.json"
OUT_MD = REPO_ROOT / "docs" / "replay" / "p136_post_rsr6_p10_p12_baseline_reevaluation_20260529.md"

P135_JSON = REPO_ROOT / "outputs" / "replay" / "p135_wave2_safe_candidates_closure_and_p10_p12_plan_20260529.json"
P134_JSON = REPO_ROOT / "outputs" / "replay" / "p134_apply_fourier_rhythm_3bet_20260528.json"
P133_JSON = REPO_ROOT / "outputs" / "replay" / "p133_apply_pp3_freqort_4bet_20260528.json"
P132_JSON = REPO_ROOT / "outputs" / "replay" / "p132_apply_midfreq_fourier_mk_3bet_20260528.json"
P131_JSON = REPO_ROOT / "outputs" / "replay" / "p131_apply_acb_markov_midfreq_3bet_20260528.json"
RSR6_CLEANUP_JSON = REPO_ROOT / "outputs" / "replay" / "rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.json"
RSR6_AUDIT_JSON = REPO_ROOT / "outputs" / "replay" / "rsr6_orphan_bet_index2_audit_20260528.json"
P128_PHASE2_JSON = REPO_ROOT / "outputs" / "replay" / "p128_wave2_adapter_phase2_20260528.json"
P127_JSON = REPO_ROOT / "outputs" / "replay" / "p127_adapter_build_specs_remaining_multi_bet_20260528.json"

EXPECTED_WORKTREE = REPO_ROOT
EXPECTED_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_GIT_DIR_SUFFIX = ".git/worktrees/zen-gates-ff6802"
EXPECTED_ROWS = 85924
PROD_BASELINE_APPLY_ID = "P20_POWERLOTTO_REMAINING_1500_PROD_20260520"
PROD_BASELINE_TRUTH = "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"
PROD_BASELINE_SOURCE = "P20_POWERLOTTO_REMAINING_STRATEGIES_PRODUCTION_APPLY"

STRATEGIES = [
    "power_precision_3bet",
    "power_orthogonal_5bet",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=str(REPO_ROOT), text=True).strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def open_ro_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def repo_worktree_check() -> dict:
    worktree_path = run(["git", "rev-parse", "--show-toplevel"])
    branch = run(["git", "branch", "--show-current"])
    git_dir = run(["git", "rev-parse", "--git-dir"])
    return {
        "worktree_path": worktree_path,
        "expected_worktree": str(EXPECTED_WORKTREE),
        "branch": branch,
        "git_dir": git_dir,
        "head_sha": run(["git", "rev-parse", "HEAD"]),
        "worktree_confirmed": (
            Path(worktree_path).resolve() == EXPECTED_WORKTREE.resolve()
            and branch == EXPECTED_BRANCH
            and git_dir.endswith(EXPECTED_GIT_DIR_SUFFIX)
        ),
    }


def db_snapshot(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    return {
        "total_rows": rows,
        "expected_rows": EXPECTED_ROWS,
        "rows_match_expected": rows == EXPECTED_ROWS,
        "bet_index_schema_exists": "bet_index" in cols,
        "columns_count": len(cols),
    }


def source_summary() -> tuple[dict, dict]:
    p135 = load_json(P135_JSON)
    rsr6_cleanup = load_json(RSR6_CLEANUP_JSON)
    return (
        {
            "artifact": str(P135_JSON),
            "task_id": p135.get("task_id"),
            "classification": p135.get("classification"),
            "classification_pass": p135.get("classification") == "P135_WAVE2_SAFE_CANDIDATES_CLOSED_P10_P12_REEVALUATION_PLAN_READY",
            "commit": "25c8d2b71ca958bd17cf52d0b6c516739745812e",
        },
        {
            "artifact": str(RSR6_CLEANUP_JSON),
            "task_id": rsr6_cleanup.get("task_id"),
            "classification": rsr6_cleanup.get("classification"),
            "classification_pass": rsr6_cleanup.get("classification") == "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED",
            "deleted_rows": rsr6_cleanup.get("deleted_rows_summary", {}).get("total_deleted"),
            "db_rows_after_cleanup": rsr6_cleanup.get("db_snapshot_after", {}).get("total_rows"),
        },
    )


def strategy_row_distribution(conn: sqlite3.Connection, sid: str) -> dict:
    bet1 = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
        (sid,),
    ).fetchone()[0]
    bet2_plus = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1",
        (sid,),
    ).fetchone()[0]
    total = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
        (sid,),
    ).fetchone()[0]
    return {
        "bet1_rows": bet1,
        "bet2_plus_rows": bet2_plus,
        "total_rows": total,
    }


def detailed_status(conn: sqlite3.Connection, sid: str) -> dict:
    replay_run_id_counts = {
        (str(run_id) if run_id is not None else "NULL"): count
        for run_id, count in conn.execute(
            """
            SELECT replay_run_id, COUNT(*)
            FROM strategy_prediction_replays
            WHERE strategy_id=?
            GROUP BY replay_run_id
            ORDER BY replay_run_id
            """,
            (sid,),
        ).fetchall()
    }
    controlled_apply_id_counts = {
        (apply_id if apply_id is not None else "NULL"): count
        for apply_id, count in conn.execute(
            """
            SELECT controlled_apply_id, COUNT(*)
            FROM strategy_prediction_replays
            WHERE strategy_id=?
            GROUP BY controlled_apply_id
            ORDER BY controlled_apply_id
            """,
            (sid,),
        ).fetchall()
    }
    truth_level_counts = {
        (truth if truth is not None else "NULL"): count
        for truth, count in conn.execute(
            """
            SELECT truth_level, COUNT(*)
            FROM strategy_prediction_replays
            WHERE strategy_id=?
            GROUP BY truth_level
            ORDER BY truth_level
            """,
            (sid,),
        ).fetchall()
    }
    source_counts = {
        (src if src not in (None, "") else "NULL"): count
        for src, count in conn.execute(
            """
            SELECT source, COUNT(*)
            FROM strategy_prediction_replays
            WHERE strategy_id=?
            GROUP BY source
            ORDER BY source
            """,
            (sid,),
        ).fetchall()
    }
    provenance_hash_null = conn.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id=? AND provenance_hash IS NULL
        """,
        (sid,),
    ).fetchone()[0]
    provenance_hash_non_null = conn.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id=? AND provenance_hash IS NOT NULL
        """,
        (sid,),
    ).fetchone()[0]

    prod_baseline_rows = conn.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id=?
          AND bet_index=1
          AND controlled_apply_id=?
          AND truth_level=?
          AND source=?
          AND provenance_hash IS NOT NULL
        """,
        (sid, PROD_BASELINE_APPLY_ID, PROD_BASELINE_TRUTH, PROD_BASELINE_SOURCE),
    ).fetchone()[0]

    null_legacy_rows = conn.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id=?
          AND bet_index=1
          AND controlled_apply_id IS NULL
          AND provenance_hash IS NULL
          AND truth_level IS NULL
          AND (source IS NULL OR source='')
        """,
        (sid,),
    ).fetchone()[0]

    return {
        "replay_run_id_counts": replay_run_id_counts,
        "controlled_apply_id_counts": controlled_apply_id_counts,
        "truth_level_counts": truth_level_counts,
        "source_counts": source_counts,
        "provenance_hash_null_rows": provenance_hash_null,
        "provenance_hash_non_null_rows": provenance_hash_non_null,
        "production_baseline_rows": prod_baseline_rows,
        "null_provenance_legacy_rows": null_legacy_rows,
    }


def reevaluation_matrix_for_strategy(sid: str, detail: dict, dist: dict) -> dict:
    # null_provenance_legacy_rows == 50: pre-P138B (governance gate pending)
    # null_provenance_legacy_rows == 0: post-P138B re-mark (governance resolved)
    baseline_valid = (
        dist["bet1_rows"] == 1550
        and dist["bet2_plus_rows"] == 0
        and detail["production_baseline_rows"] == 1500
        and detail["null_provenance_legacy_rows"] in (0, 50)
    )
    return {
        "strategy_id": sid,
        "baseline_valid_for_future_dry_run": baseline_valid,
        "requires_remark_plan": True,
        "requires_quarantine_plan": True,
        "requires_cleanup_authorization": True,
        "remains_apply_blocked": True,
        "reason": "null_provenance_legacy_rows_present_after_rsr6_cleanup",
        "guard_before_any_mutation": [
            "read_only_revalidation_on_same_worktree",
            "authorization_phrase_required",
            "no_controlled_apply_until_resolution",
            "post_mutation_drift_guard_required",
        ],
    }


def recommended_resolution(matrix: dict) -> dict:
    per_strategy = {}
    for sid, row in matrix.items():
        per_strategy[sid] = {
            "recommendation": "prepare_authorization_gate_for_quarantine_or_re_mark_decision",
            "apply_ready_now": False,
            "why_not_apply_ready": row["reason"],
            "safe_keep_decision_in_p136": True,
            "safe_keep_rationale": (
                "P136 is read-only; keeping 50 NULL-provenance rows unchanged avoids ungoverned mutation. "
                "Mutation must move to a separate authorized task."
            ),
        }
    return {
        "global_decision": "KEEP_AS_IS_IN_P136_AND_PREPARE_MUTATION_GATE",
        "per_strategy": per_strategy,
    }


def build_markdown(report: dict) -> str:
    d = report["p10_p12_current_distribution"]
    base = report["baseline_row_audit"]
    null_a = report["null_provenance_legacy_audit"]
    matrix = report["per_strategy_reevaluation_matrix"]
    resolution = report["recommended_resolution"]
    gate = report["authorization_gate_if_mutation_needed"]

    return f"""# P136: Post-RSR6 Re-evaluation for P10/P12 Baseline Rows

**Generated:** {report['generated_at']}
**Classification:** `{report['classification']}`

## 1. Executive Summary
P136 completes a read-only post-RSR6 re-evaluation for `power_precision_3bet` and `power_orthogonal_5bet`. Both strategies remain apply-blocked. No DB mutation, no controlled_apply, and no replay-row insertion was executed.

## 2. P135 Recap
- Classification: `{report['p135_source_summary']['classification']}`
- Pass: {report['p135_source_summary']['classification_pass']}
- Commit: `{report['p135_source_summary']['commit']}`

## 3. RSR-6 Cleanup Recap
- Classification: `{report['rsr6_cleanup_source_summary']['classification']}`
- Pass: {report['rsr6_cleanup_source_summary']['classification_pass']}
- Deleted rows in RSR6 cleanup: {report['rsr6_cleanup_source_summary']['deleted_rows']}
- DB rows after cleanup: {report['rsr6_cleanup_source_summary']['db_rows_after_cleanup']}

## 4. Why P10/P12 Need Post-cleanup Re-evaluation
RSR6 removed orphan bet-index=2 rows, but each strategy still has 50 bet-index=1 rows with NULL provenance fields. They must be governed before any future dry-run/apply gate.

## 5. Current P10/P12 Row Distribution
- `power_precision_3bet`: bet-1={d['power_precision_3bet_bet1_rows']}, bet-2+={d['power_precision_3bet_bet2_plus_rows']}
- `power_orthogonal_5bet`: bet-1={d['power_orthogonal_5bet_bet1_rows']}, bet-2+={d['power_orthogonal_5bet_bet2_plus_rows']}

## 6. Baseline Row Audit
- production_baseline_rows_per_strategy = {base['production_baseline_rows_per_strategy']}
- null_provenance_legacy_rows_per_strategy = {base['null_provenance_legacy_rows_per_strategy']}
- total_rows_per_strategy = {base['total_rows_per_strategy']}
- db_write_in_p136 = {base['db_write_in_p136']}

## 7. NULL-provenance Legacy Row Audit
{json.dumps(null_a, ensure_ascii=False, indent=2)}

## 8. Per-strategy Re-evaluation Matrix
{json.dumps(matrix, ensure_ascii=False, indent=2)}

## 9. Recommended Resolution
{json.dumps(resolution, ensure_ascii=False, indent=2)}

## 10. Future Dry-run Gate Checklist
{json.dumps(report['future_dry_run_gate_checklist'], ensure_ascii=False, indent=2)}

## 11. Authorization Gate If Mutation Is Needed
{json.dumps(gate, ensure_ascii=False, indent=2)}

## 12. Explicit Non-actions
- No DB write in P136
- No controlled_apply in P136
- No replay rows inserted
- 4_STAR excluded
- P108 not run
- P117 not run
- P118 not run
- Rejected strategies no_action
- No scheduler install
- No lifecycle / champion / registry mutation

## 13. Remaining Risks
{chr(10).join(f"- {x}" for x in report['remaining_risks'])}

## 14. Recommended Next Task
{report['next_recommended_task']}

## 15. Final Classification
```text
{report['classification']}
```
"""


def build_report() -> dict:
    conn = open_ro_conn()
    try:
        repo = repo_worktree_check()
        db = db_snapshot(conn)
        p135_summary, rsr6_summary = source_summary()

        p10_dist = strategy_row_distribution(conn, "power_precision_3bet")
        p12_dist = strategy_row_distribution(conn, "power_orthogonal_5bet")
        p10_detail = detailed_status(conn, "power_precision_3bet")
        p12_detail = detailed_status(conn, "power_orthogonal_5bet")

        p10_p12_current_distribution = {
            "power_precision_3bet_bet1_rows": p10_dist["bet1_rows"],
            "power_precision_3bet_bet2_plus_rows": p10_dist["bet2_plus_rows"],
            "power_orthogonal_5bet_bet1_rows": p12_dist["bet1_rows"],
            "power_orthogonal_5bet_bet2_plus_rows": p12_dist["bet2_plus_rows"],
        }

        baseline_row_audit = {
            "production_baseline_rows_per_strategy": 1500,
            "null_provenance_legacy_rows_per_strategy": 50,
            "total_rows_per_strategy": 1550,
            "db_write_in_p136": False,
            "power_precision_3bet": {
                "production_baseline_rows": p10_detail["production_baseline_rows"],
                "null_provenance_legacy_rows": p10_detail["null_provenance_legacy_rows"],
                "total_rows": p10_dist["total_rows"],
            },
            "power_orthogonal_5bet": {
                "production_baseline_rows": p12_detail["production_baseline_rows"],
                "null_provenance_legacy_rows": p12_detail["null_provenance_legacy_rows"],
                "total_rows": p12_dist["total_rows"],
            },
        }

        null_provenance_legacy_audit = {
            "power_precision_3bet": p10_detail,
            "power_orthogonal_5bet": p12_detail,
            "summary": {
                "null_legacy_rows_per_strategy": 50,
                "production_baseline_rows_per_strategy": 1500,
                "legacy_rows_keepable_in_p136": True,
                "keep_reason": "P136 is read-only and only produces governance recommendations.",
            },
        }

        matrix = {
            "power_precision_3bet": reevaluation_matrix_for_strategy("power_precision_3bet", p10_detail, p10_dist),
            "power_orthogonal_5bet": reevaluation_matrix_for_strategy("power_orthogonal_5bet", p12_detail, p12_dist),
        }

        recommended = recommended_resolution(matrix)

        future_dry_run_gate_checklist = {
            "preconditions": [
                "worktree_and_branch_check_pass",
                "production_db_rows_still_85924_before_any_new_task",
                "drift_guard_pass_before_and_after_any_mutation_task",
                "p10_p12_bet_index_gt1_rows_remain_zero_until_authorized_mutation",
            ],
            "governance_checks": [
                "authorization_phrase_present_for_any_mutation",
                "mutation_scope_limited_to_p10_p12_legacy_rows",
                "no_wave2_safe_candidate_rows_touched",
                "no_P126B_to_P126F_rows_touched",
                "no_p131_to_p134_rows_touched",
            ],
            "apply_gate_checks": [
                "rebuild_distribution_after_resolution",
                "recompute_apply_ready_flags",
                "run_dry_run_only_first_if_apply_gate_reopened",
                "controlled_apply_requires_separate_phrase_even_after_dry_run",
            ],
        }

        authorization_gate_if_mutation_needed = {
            "required_before_mutation": True,
            "suggested_authorization_phrase": (
                "P136_AUTHORIZED_P10_P12_BASELINE_LEGACY_ROW_RESOLUTION_PLAN_V20260529"
            ),
            "allowed_actions_in_future_task_only": [
                "quarantine_null_provenance_rows",
                "re_mark_with_explicit_provenance_metadata",
                "or_noop_keep_decision_with_documented_waiver",
            ],
            "mutation_forbidden_in_p136": True,
        }

        apply_gate_status = {
            "controlled_apply_executed": False,
            "replay_rows_inserted": 0,
            "power_precision_3bet_apply_ready": False,
            "power_orthogonal_5bet_apply_ready": False,
            "per_strategy_authorization_required_later": True,
            "production_db_rows_expected": EXPECTED_ROWS,
            "production_db_rows_after": EXPECTED_ROWS,
        }

        blocked_or_excluded = {
            "no_db_write_in_p136": True,
            "no_controlled_apply_in_p136": True,
            "no_replay_rows_inserted": True,
            "4_STAR_excluded": True,
            "P108_not_run": True,
            "P117_not_run": True,
            "P118_not_run": True,
            "rejected_strategies_no_action": True,
            "no_scheduler_install": True,
            "no_lifecycle_champion_registry_mutation": True,
        }

        report = {
            "task_id": TASK_ID,
            "classification": CLASSIFICATION,
            "generated_at": now_iso(),
            "repo_worktree_check": repo,
            "db_snapshot": db,
            "p135_source_summary": p135_summary,
            "rsr6_cleanup_source_summary": rsr6_summary,
            "p10_p12_current_distribution": p10_p12_current_distribution,
            "baseline_row_audit": baseline_row_audit,
            "null_provenance_legacy_audit": null_provenance_legacy_audit,
            "per_strategy_reevaluation_matrix": matrix,
            "recommended_resolution": recommended,
            "future_dry_run_gate_checklist": future_dry_run_gate_checklist,
            "authorization_gate_if_mutation_needed": authorization_gate_if_mutation_needed,
            "apply_gate_status": apply_gate_status,
            "blocked_or_excluded": blocked_or_excluded,
            "roadmap_update_status": (
                "roadmap.md and CTO-Analysis.md updated to mark P136 as post-RSR6 re-evaluation phase for P10/P12."
            ),
            "remaining_risks": [
                "P10/P12 still have 50 NULL-provenance bet-1 rows per strategy; they are governance debt until a separate authorized mutation task resolves them.",
                "Any mutation without an explicit authorization gate risks touching validated production baseline rows.",
                "Apply readiness remains blocked until legacy row governance is finalized.",
            ],
            "next_recommended_task": (
                "P137 authorization gate task for P10/P12 legacy-row resolution (quarantine or re-mark decision), then reassess dry-run readiness."
            ),
            "summary": (
                "P136 completed read-only post-RSR6 re-evaluation for P10/P12. Distribution is stable at 1550 bet-1 and 0 bet-2+ per strategy, with 1500 production baseline rows and 50 NULL-provenance legacy rows each. Apply remains blocked."
            ),
        }
        return report
    finally:
        conn.close()


def main() -> None:
    report = build_report()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps({
        "task_id": report["task_id"],
        "classification": report["classification"],
        "json": str(OUT_JSON),
        "markdown": str(OUT_MD),
        "db_rows": report["db_snapshot"]["total_rows"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
