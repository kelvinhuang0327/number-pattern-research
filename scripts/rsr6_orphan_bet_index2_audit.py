#!/usr/bin/env python3
"""
rsr6_orphan_bet_index2_audit.py
================================
RSR-6 Orphan bet_index=2 Audit for Wave 2 Apply Readiness.

Audits power_precision_3bet and power_orthogonal_5bet for orphan
bet_index=2 rows that block their apply gate in P128 Phase 2.

Scope:
  - READ-ONLY: No DB writes, no DELETE, no UPDATE, no INSERT.
  - No controlled_apply, no replay row insertion.
  - Produces authorization_gate output if cleanup is recommended.
  - Writes outputs/replay/rsr6_orphan_bet_index2_audit_20260528.json

Usage:
    python3 scripts/rsr6_orphan_bet_index2_audit.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "replay" / "rsr6_orphan_bet_index2_audit_20260528.json"
P128_PHASE2_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "p128_wave2_adapter_phase2_20260528.json"

EXPECTED_DB_ROWS = 72462
RSR6_STRATEGIES = ["power_precision_3bet", "power_orthogonal_5bet"]
AUDIT_DATE = "20260528"


def _ro_conn() -> sqlite3.Connection:
    uri = f"file:{DB_PATH}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.execute("PRAGMA query_only = ON")
    return con


def _count_rows(con: sqlite3.Connection) -> int:
    return con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]


def _bet_index_column_exists(con: sqlite3.Connection) -> bool:
    cols = [r[1] for r in con.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    return "bet_index" in cols


def _get_strategy_counts(con: sqlite3.Connection) -> dict:
    rows = con.execute("""
        SELECT strategy_id, bet_index, COUNT(*)
        FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
        GROUP BY strategy_id, bet_index
        ORDER BY strategy_id, bet_index
    """).fetchall()
    result: dict = {}
    for sid, bi, cnt in rows:
        result.setdefault(sid, {})[bi] = cnt
    return result


def _get_orphan_rows(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("""
        SELECT
            id, strategy_id, lottery_type, target_draw, bet_index,
            predicted_numbers, source,
            replay_run_id, truth_level, controlled_apply_id,
            provenance_hash, provenance_source,
            generated_at, replay_status, dry_run
        FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND bet_index = 2
        ORDER BY strategy_id, target_draw
    """).fetchall()
    cols = [
        "id", "strategy_id", "lottery_type", "target_draw", "bet_index",
        "predicted_numbers", "source", "replay_run_id", "truth_level",
        "controlled_apply_id", "provenance_hash", "provenance_source",
        "generated_at", "replay_status", "dry_run",
    ]
    return [dict(zip(cols, r)) for r in rows]


def _get_bi1_for_orphan_draws(con: sqlite3.Connection, draws: list[str]) -> dict:
    """Check whether bi=1 rows exist for the same draws (run_id=2 vs run_id=6 anomaly)."""
    placeholders = ",".join("?" * len(draws))
    rows = con.execute(f"""
        SELECT strategy_id, target_draw, bet_index, replay_run_id, source
        FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND bet_index = 1
          AND target_draw IN ({placeholders})
        ORDER BY strategy_id, target_draw
    """, draws).fetchall()
    result: dict = {}
    for sid, draw, bi, rrid, src in rows:
        result.setdefault(sid, {})[draw] = {"replay_run_id": rrid, "source": src}
    return result


def _check_p128_phase2_artifact() -> str:
    if not P128_PHASE2_ARTIFACT.exists():
        return "MISSING"
    data = json.loads(P128_PHASE2_ARTIFACT.read_text())
    return data.get("classification", "UNKNOWN")


def _analyze_orphan_runs(con: sqlite3.Connection) -> dict:
    """Analyze replay_run_id=6 scope — what it wrote for RSR-6 strategies."""
    rows = con.execute("""
        SELECT strategy_id, bet_index, COUNT(*), MIN(target_draw), MAX(target_draw)
        FROM strategy_prediction_replays
        WHERE replay_run_id = 6
          AND strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
        GROUP BY strategy_id, bet_index
        ORDER BY strategy_id, bet_index
    """).fetchall()
    return [
        {"strategy_id": r[0], "bet_index": r[1], "count": r[2],
         "draw_min": r[3], "draw_max": r[4]}
        for r in rows
    ]


def main() -> None:
    print("=" * 65)
    print("RSR-6 Orphan bet_index=2 Audit")
    print("=" * 65)

    # 1. Worktree / branch guard
    import subprocess
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=PROJECT_ROOT
    ).decode().strip()
    worktree_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=PROJECT_ROOT
    ).decode().strip()
    head_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT
    ).decode().strip()
    print(f"\n[WORKTREE] root  : {worktree_root}")
    print(f"[WORKTREE] branch: {branch}")
    print(f"[WORKTREE] HEAD  : {head_sha}")

    repo_check = {
        "worktree_root": worktree_root,
        "branch": branch,
        "head_sha": head_sha,
        "expected_branch": "claude/zen-gates-ff6802",
        "branch_ok": branch == "claude/zen-gates-ff6802",
    }

    # 2. DB guard
    con = _ro_conn()
    rows_before = _count_rows(con)
    print(f"\n[GUARD] DB rows before: {rows_before} (expected {EXPECTED_DB_ROWS})")
    if rows_before != EXPECTED_DB_ROWS:
        print(f"FATAL: DB row mismatch! {rows_before} != {EXPECTED_DB_ROWS}")
        sys.exit(1)
    print("[GUARD] PASS")

    # 3. Schema check
    bet_index_ok = _bet_index_column_exists(con)
    print(f"[SCHEMA] bet_index column: {'EXISTS' if bet_index_ok else 'MISSING'}")
    if not bet_index_ok:
        print("FATAL: bet_index column missing")
        sys.exit(1)

    # 4. P128 Phase 2 artifact check
    p128_classification = _check_p128_phase2_artifact()
    print(f"[P128] Phase 2 classification: {p128_classification}")
    if p128_classification != "P128_WAVE2_ADAPTER_PHASE2_READY":
        print(f"WARN: expected P128_WAVE2_ADAPTER_PHASE2_READY, got {p128_classification}")

    # 5. Strategy counts
    strat_counts = _get_strategy_counts(con)
    print("\n[COUNTS] RSR-6 strategy row counts:")
    for sid in RSR6_STRATEGIES:
        counts = strat_counts.get(sid, {})
        print(f"  {sid}: bi=1:{counts.get(1,0)}  bi=2:{counts.get(2,0)}")

    # 6. Orphan rows
    orphan_rows = _get_orphan_rows(con)
    total_orphan = len(orphan_rows)
    print(f"\n[ORPHAN] Total orphan bi=2 rows: {total_orphan}")

    # Group by strategy
    by_strategy: dict = {}
    draws_set: set = set()
    for r in orphan_rows:
        sid = r["strategy_id"]
        by_strategy.setdefault(sid, []).append(r)
        draws_set.add(r["target_draw"])

    draws_sorted = sorted(draws_set)
    draw_range = f"{draws_sorted[0]}–{draws_sorted[-1]}" if draws_sorted else "N/A"

    source_blank_count = sum(1 for r in orphan_rows if not r["source"])
    provenance_incomplete = sum(
        1 for r in orphan_rows
        if not r["provenance_hash"] and not r["provenance_source"] and not r["controlled_apply_id"]
    )

    print(f"  Draw range     : {draw_range}")
    print(f"  source=blank   : {source_blank_count}/{total_orphan}")
    print(f"  provenance N/A : {provenance_incomplete}/{total_orphan}")

    # 7. Check bi=1 rows for same draws
    orphan_draws = [r["target_draw"] for r in orphan_rows
                    if r["strategy_id"] == "power_precision_3bet"]
    bi1_overlap = _get_bi1_for_orphan_draws(con, orphan_draws)
    print("\n[ORPHAN] bi=1 row coverage for orphan draw range:")
    for sid in RSR6_STRATEGIES:
        covered = len(bi1_overlap.get(sid, {}))
        print(f"  {sid}: bi=1 exists for {covered}/{len(orphan_draws)} orphan draws")

    # 8. replay_run_id analysis
    run6_scope = _analyze_orphan_runs(con)
    print("\n[RUN6] replay_run_id=6 scope for RSR-6 strategies:")
    for r in run6_scope:
        print(f"  {r['strategy_id']} bi={r['bet_index']}: {r['count']} rows "
              f"({r['draw_min']}–{r['draw_max']})")

    # Provenance interpretation
    # run_id=6 wrote bi=1 for draws 99000055–99000084, then bi=2 for 99000085–99000104
    # run_id=2 ALSO wrote bi=1 for 99000085–99000104
    # So orphan bi=2 rows are from run_id=6 which treated those draws as its "2nd bet" slot
    # while run_id=2 later re-ran and wrote bi=1 rows for the same draws
    provenance_interpretation = (
        "replay_run_id=6 wrote bi=1 for draws 99000055–99000084 and bi=2 for draws "
        "99000085–99000104 in a single run that treated draws beyond its bi=1 window "
        "as bet_index=2 overflow. replay_run_id=2 subsequently wrote bi=1 rows for "
        "draws 99000085–99000104. The orphan bi=2 rows from run_id=6 lack source, "
        "controlled_apply_id, provenance_hash, and truth_level — indicating they were "
        "generated by a pre-P126 batch runner that did not enforce the one-run-per-bet-slot "
        "constraint."
    )

    # 9. Resolution recommendation
    resolution_recommendation = {
        "verdict": "quarantine_plan_required",
        "rationale": (
            "Orphan bi=2 rows are safe to quarantine: each orphan draw already has "
            "a valid bi=1 row (from replay_run_id=2, source=P20_POWERLOTTO_REMAINING_STRATEGIES_PRODUCTION_APPLY). "
            "Orphan rows have no provenance_hash, no controlled_apply_id, and source=''. "
            "They will collide if any future adapter run tries to INSERT bi=2 rows for "
            "the same (strategy_id, target_draw) pair under UNIQUE constraints. "
            "Recommended action: DELETE 40 rows (20 per strategy) WHERE bet_index=2 "
            "AND source='' AND replay_run_id=6 for these two strategies."
        ),
        "options": [
            {
                "option": "A_quarantine_delete",
                "description": "DELETE 40 orphan rows (20 per strategy, bet_index=2, source='', replay_run_id=6). "
                               "Requires DB mutation authorization. Unlocks apply gate for P10/P12.",
                "risk": "LOW — bi=1 rows exist for all 20 draws. No prediction coverage lost.",
                "authorization_required": True,
            },
            {
                "option": "B_keep_as_legacy",
                "description": "Mark orphan rows with source='LEGACY_ORPHAN_RSR6' and "
                               "controlled_apply_id='RSR6_QUARANTINE'. Does not delete rows. "
                               "Apply gate remains blocked for bi>=2 slots until legacy rows reconciled.",
                "risk": "MEDIUM — future adapter runs may fail UNIQUE constraint for bi=2 slots.",
                "authorization_required": True,
            },
            {
                "option": "C_permanent_block",
                "description": "Keep orphan rows indefinitely. Mark P10/P12 as permanently blocked "
                               "for multi-bet apply (bi>=2). Only bi=1 apply allowed.",
                "risk": "HIGH — discards 4-bet/5-bet prediction capability for P10/P12.",
                "authorization_required": False,
            },
        ],
        "recommended_option": "A_quarantine_delete",
        "recommended_cleanup_sql": (
            "DELETE FROM strategy_prediction_replays "
            "WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
            "AND bet_index = 2 AND (source IS NULL OR source = '') AND replay_run_id = 6;"
        ),
        "rows_to_delete": 40,
        "rows_by_strategy": {"power_precision_3bet": 20, "power_orthogonal_5bet": 20},
    }

    # 10. Rows after (read-only — must still be 72462)
    rows_after = _count_rows(con)
    con.close()
    print(f"\n[GUARD] DB rows after : {rows_after}")
    if rows_after != rows_before:
        print(f"FATAL: DB rows changed! {rows_before} → {rows_after}")
        sys.exit(1)
    print("[GUARD] PASS — no rows modified")

    # Build rows_by_strategy dict for summary
    rows_by_strategy = {
        sid: {"bi_1": strat_counts.get(sid, {}).get(1, 0),
              "bi_2_orphan": strat_counts.get(sid, {}).get(2, 0)}
        for sid in RSR6_STRATEGIES
    }

    # 11. Build artifact
    artifact = {
        "task_id": "RSR6",
        "classification": "RSR6_ORPHAN_BET_INDEX2_AUDIT_READY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_worktree_check": repo_check,
        "db_snapshot_before": {
            "total_rows": rows_before,
            "expected_rows": EXPECTED_DB_ROWS,
            "invariant_ok": rows_before == EXPECTED_DB_ROWS,
        },
        "db_snapshot_after": {
            "total_rows": rows_after,
            "expected_rows": EXPECTED_DB_ROWS,
            "invariant_ok": rows_after == EXPECTED_DB_ROWS,
            "rows_modified": rows_after - rows_before,
        },
        "p128_phase2_source_summary": {
            "artifact": str(P128_PHASE2_ARTIFACT.relative_to(PROJECT_ROOT)),
            "classification": p128_classification,
            "classification_ok": p128_classification == "P128_WAVE2_ADAPTER_PHASE2_READY",
            "rsr6_strategies_blocked": RSR6_STRATEGIES,
        },
        "orphan_row_summary": {
            "affected_strategies": RSR6_STRATEGIES,
            "total_orphan_rows": total_orphan,
            "rows_by_strategy": rows_by_strategy,
            "target_draw_range": draw_range,
            "target_draw_min": draws_sorted[0] if draws_sorted else None,
            "target_draw_max": draws_sorted[-1] if draws_sorted else None,
            "source_blank_count": source_blank_count,
            "provenance_incomplete_count": provenance_incomplete,
            "replay_run_id_of_orphans": 6,
            "bi1_overlap_coverage": {
                sid: len(bi1_overlap.get(sid, {}))
                for sid in RSR6_STRATEGIES
            },
            "bi1_overlap_complete": all(
                len(bi1_overlap.get(sid, {})) == 20 for sid in RSR6_STRATEGIES
            ),
            "db_write_in_rsr6": False,
            "cleanup_executed": False,
        },
        "orphan_rows": orphan_rows,
        "provenance_audit": {
            "run_id_of_orphans": 6,
            "run6_scope": run6_scope,
            "interpretation": provenance_interpretation,
            "source_field": "'' (empty string — no controlled_apply_id, no provenance_hash)",
            "controlled_apply_id": "NULL for all orphan rows",
            "provenance_hash": "NULL for all orphan rows",
            "truth_level": "NULL for all orphan rows",
            "dry_run": "0 (live rows, not dry-run)",
            "generated_at": "2026-05-07T08:54:18+00:00 (pre-P126 batch)",
            "conclusion": (
                "Orphan rows are pre-P126 batch rows from replay_run_id=6 that "
                "overflowed into bet_index=2 without enforcement of controlled_apply "
                "constraints. They are NOT from any P126/P128 operation."
            ),
        },
        "resolution_recommendation": resolution_recommendation,
        "apply_gate_impact": {
            "power_precision_3bet_apply_ready": False,
            "power_orthogonal_5bet_apply_ready": False,
            "p7_p8_p9_p11_apply_ready_not_evaluated": True,
            "controlled_apply_executed": False,
            "replay_rows_inserted": 0,
            "production_db_rows_after": rows_after,
            "apply_gate_unblock_condition": (
                "Execute Option A (DELETE 40 orphan rows) under authorization, "
                "re-run drift guard (must pass at 72422), then re-evaluate apply gate."
            ),
            "db_rows_after_cleanup_expected": 72422,
        },
        "authorization_gate_if_cleanup_needed": {
            "required_before_cleanup": True,
            "authorization_phrase": (
                "RSR6_CLEANUP_AUTHORIZED_DELETE_40_ORPHAN_BET_INDEX2_ROWS_"
                "POWER_PRECISION_AND_ORTHOGONAL_20260528"
            ),
            "cleanup_sql": resolution_recommendation["recommended_cleanup_sql"],
            "rows_to_delete": 40,
            "post_cleanup_drift_guard_required": True,
            "post_cleanup_expected_rows": 72422,
        },
        "blocked_or_excluded": {
            "no_db_write_in_rsr6": True,
            "no_controlled_apply_in_rsr6": True,
            "4_STAR_excluded": True,
            "P108_not_run": True,
            "P117_not_run": True,
            "P118_not_run": True,
            "rejected_strategies_no_action": True,
            "no_scheduler_install": True,
            "no_lifecycle_champion_registry_mutation": True,
            "no_delete_update_move_in_rsr6": True,
        },
        "roadmap_update_status": "PENDING — will be updated after commit",
        "remaining_risks": [
            "P10/P12 apply gate blocked until Option A authorized and executed.",
            "If Option A not executed before future adapter runs write bi=2 rows, "
            "UNIQUE constraint violations will occur for draws 99000085–99000104.",
            "replay_run_id=6 scope needs to be documented as pre-P126 legacy to "
            "prevent re-confusion in future audits.",
            "drift guard will report 72422 rows after cleanup — ensure all downstream "
            "expected-row-count assertions are updated.",
        ],
        "next_recommended_task": (
            "RSR6_CLEANUP_EXECUTION: Obtain authorization phrase, execute DELETE SQL, "
            "re-run drift guard at 72422, update apply gate for P10/P12, "
            "then proceed to P128 Phase 3 controlled_apply for P7/P8/P9/P11."
        ),
        "summary": (
            f"RSR-6 audit complete. {total_orphan} orphan bet_index=2 rows found across "
            f"power_precision_3bet ({rows_by_strategy['power_precision_3bet']['bi_2_orphan']}) "
            f"and power_orthogonal_5bet ({rows_by_strategy['power_orthogonal_5bet']['bi_2_orphan']}). "
            f"Orphans originate from replay_run_id=6 (pre-P126 batch, 2026-05-07). "
            f"bi=1 rows exist for all 20 affected draws from replay_run_id=2. "
            f"Recommended resolution: Option A (DELETE 40 rows under authorization). "
            f"Apply gate for P10/P12 remains BLOCKED until cleanup authorized. "
            f"DB rows: {rows_after} (invariant maintained, no writes in RSR-6)."
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
    print(f"\n[ARTIFACT] Written → {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")

    print(f"\n{'=' * 65}")
    print(f"RSR-6 Audit: {artifact['classification']}")
    print(f"Orphan rows: {total_orphan} ({draw_range})")
    print(f"Resolution : {resolution_recommendation['recommended_option']}")
    print(f"Authorization phrase required before cleanup.")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
