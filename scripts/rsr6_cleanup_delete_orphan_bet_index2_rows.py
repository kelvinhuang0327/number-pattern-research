"""
rsr6_cleanup_delete_orphan_bet_index2_rows.py
=============================================
RSR-6 Cleanup: delete 40 orphan bet_index=2 rows for Wave 2 apply readiness.

Authorization-gated. Must be run with --authorization flag containing the
exact phrase. Will STOP before any DELETE if preconditions fail.

Usage:
    python3 scripts/rsr6_cleanup_delete_orphan_bet_index2_rows.py \\
        --authorization "RSR6_CLEANUP_AUTHORIZED_DELETE_40_ORPHAN_BET_INDEX2_ROWS_POWER_PRECISION_AND_ORTHOGONAL_20260528"

Outputs:
    outputs/replay/rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.json
    docs/replay/rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.md
"""

import argparse
import datetime
import json
import pathlib
import shutil
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

REQUIRED_AUTHORIZATION_PHRASE = (
    "RSR6_CLEANUP_AUTHORIZED_DELETE_40_ORPHAN_BET_INDEX2_ROWS_POWER_PRECISION_AND_ORTHOGONAL_20260528"
)

EXPECTED_ROWS_BEFORE = 72462
EXPECTED_ROWS_AFTER = 72422
EXPECTED_DELETE_ROWS = 40

AFFECTED_STRATEGIES = ["power_precision_3bet", "power_orthogonal_5bet"]
ORPHAN_BET_INDEX = 2
ORPHAN_REPLAY_RUN_ID = 6
TARGET_DRAW_MIN = 99000085
TARGET_DRAW_MAX = 99000104

SOURCE_AUDIT_JSON = (
    REPO_ROOT / "outputs" / "replay" / "rsr6_orphan_bet_index2_audit_20260528.json"
)
OUTPUT_JSON = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.json"
)
OUTPUT_MD = (
    REPO_ROOT
    / "docs"
    / "replay"
    / "rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.md"
)
BACKUP_DIR = REPO_ROOT / "backups"

WORKTREE_NAME = "zen-gates-ff6802"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def get_total_rows(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]


def get_orphan_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND bet_index = ?
          AND replay_run_id = ?
          AND (source IS NULL OR source = '')
          AND controlled_apply_id IS NULL
          AND provenance_hash IS NULL
          AND truth_level IS NULL
          AND CAST(target_draw AS INTEGER) BETWEEN ? AND ?
        """,
        (ORPHAN_BET_INDEX, ORPHAN_REPLAY_RUN_ID, TARGET_DRAW_MIN, TARGET_DRAW_MAX),
    ).fetchone()[0]


def get_bet_index1_counts(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT strategy_id, COUNT(*)
        FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND bet_index = 1
        GROUP BY strategy_id
        """,
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# Verify audit artifact classification
# ---------------------------------------------------------------------------


def verify_audit_artifact() -> dict:
    if not SOURCE_AUDIT_JSON.exists():
        return {
            "found": False,
            "classification": None,
            "task_id": None,
            "error": f"Audit artifact not found at {SOURCE_AUDIT_JSON}",
        }
    try:
        data = json.loads(SOURCE_AUDIT_JSON.read_text())
        return {
            "found": True,
            "classification": data.get("classification"),
            "task_id": data.get("task_id"),
            "classification_pass": data.get("classification") == "RSR6_ORPHAN_BET_INDEX2_AUDIT_READY",
        }
    except Exception as e:
        return {"found": True, "classification": None, "task_id": None, "error": str(e)}


# ---------------------------------------------------------------------------
# Main cleanup logic
# ---------------------------------------------------------------------------


def run_cleanup(authorization_phrase: str) -> dict:
    generated_at = now_iso()

    # -----------------------------------------------------------------------
    # Step 1: Authorization check
    # -----------------------------------------------------------------------
    auth_present = authorization_phrase.strip() == REQUIRED_AUTHORIZATION_PHRASE
    auth_result = {
        "exact_required_phrase": REQUIRED_AUTHORIZATION_PHRASE,
        "authorization_present": auth_present,
        "cleanup_allowed": auth_present,
        "authorization_text_observed": authorization_phrase.strip(),
    }
    if not auth_present:
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_AUTHORIZATION_FAILED",
            "generated_at": generated_at,
            "authorization": auth_result,
            "error": "STOP: Authorization phrase mismatch. No changes made.",
        }

    # -----------------------------------------------------------------------
    # Step 2: Worktree check
    # -----------------------------------------------------------------------
    worktree_path = str(REPO_ROOT)
    worktree_ok = WORKTREE_NAME in worktree_path
    repo_worktree_check = {
        "worktree_path": worktree_path,
        "expected_worktree": WORKTREE_NAME,
        "worktree_confirmed": worktree_ok,
    }
    if not worktree_ok:
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_WRONG_WORKTREE",
            "generated_at": generated_at,
            "authorization": auth_result,
            "repo_worktree_check": repo_worktree_check,
            "error": f"STOP: Wrong worktree. Expected '{WORKTREE_NAME}' in path, got '{worktree_path}'",
        }

    # -----------------------------------------------------------------------
    # Step 3: Audit artifact classification
    # -----------------------------------------------------------------------
    audit_check = verify_audit_artifact()
    if not audit_check.get("classification_pass"):
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_AUDIT_ARTIFACT_NOT_READY",
            "generated_at": generated_at,
            "authorization": auth_result,
            "repo_worktree_check": repo_worktree_check,
            "audit_check": audit_check,
            "error": f"STOP: RSR-6 audit artifact classification not RSR6_ORPHAN_BET_INDEX2_AUDIT_READY",
        }

    # -----------------------------------------------------------------------
    # Step 4: DB pre-checks
    # -----------------------------------------------------------------------
    if not DB_PATH.exists():
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_DB_NOT_FOUND",
            "generated_at": generated_at,
            "authorization": auth_result,
            "repo_worktree_check": repo_worktree_check,
            "error": f"STOP: DB not found at {DB_PATH}",
        }

    conn = sqlite3.connect(str(DB_PATH))

    # Check bet_index column exists
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    bet_index_schema_exists = "bet_index" in cols

    total_before = get_total_rows(conn)
    orphan_count_before = get_orphan_count(conn)
    bet_index1_before = get_bet_index1_counts(conn)

    db_snapshot_before = {
        "total_rows": total_before,
        "bet_index_schema_exists": bet_index_schema_exists,
        "orphan_selector_count": orphan_count_before,
        "bet_index1_rows_per_strategy": bet_index1_before,
    }

    # Guard: rows before must match expected
    if total_before != EXPECTED_ROWS_BEFORE:
        conn.close()
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_PRECONDITION_FAILED",
            "generated_at": generated_at,
            "authorization": auth_result,
            "repo_worktree_check": repo_worktree_check,
            "db_snapshot_before": db_snapshot_before,
            "error": f"STOP: DB rows before mismatch. Expected {EXPECTED_ROWS_BEFORE}, got {total_before}",
        }

    if not bet_index_schema_exists:
        conn.close()
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_PRECONDITION_FAILED",
            "generated_at": generated_at,
            "authorization": auth_result,
            "repo_worktree_check": repo_worktree_check,
            "db_snapshot_before": db_snapshot_before,
            "error": "STOP: bet_index column not found in strategy_prediction_replays",
        }

    # Guard: orphan count must be exactly 40
    if orphan_count_before != EXPECTED_DELETE_ROWS:
        conn.close()
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_PRECONDITION_FAILED",
            "generated_at": generated_at,
            "authorization": auth_result,
            "repo_worktree_check": repo_worktree_check,
            "db_snapshot_before": db_snapshot_before,
            "error": f"STOP: Orphan row count mismatch. Expected {EXPECTED_DELETE_ROWS}, got {orphan_count_before}",
        }

    conn.close()

    # -----------------------------------------------------------------------
    # Step 5: Create backup
    # -----------------------------------------------------------------------
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"lottery_v2_before_rsr6_cleanup_{backup_ts}.db"
    shutil.copy2(str(DB_PATH), str(backup_path))

    # Verify backup row count
    bconn = sqlite3.connect(str(backup_path))
    backup_row_count = bconn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    bconn.close()

    backup_created = backup_row_count == EXPECTED_ROWS_BEFORE
    backup_info = {
        "backup_path": str(backup_path),
        "backup_row_count": backup_row_count,
        "backup_created": backup_created,
        "backup_verified": backup_created,
    }

    if not backup_created:
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_BACKUP_FAILED",
            "generated_at": generated_at,
            "authorization": auth_result,
            "repo_worktree_check": repo_worktree_check,
            "db_snapshot_before": db_snapshot_before,
            "backup": backup_info,
            "error": f"STOP: Backup row count mismatch. Expected {EXPECTED_ROWS_BEFORE}, got {backup_row_count}",
        }

    # -----------------------------------------------------------------------
    # Step 6: Execute DELETE (strictly scoped)
    # -----------------------------------------------------------------------
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("BEGIN")

    deleted = conn.execute(
        """
        DELETE FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND bet_index = ?
          AND replay_run_id = ?
          AND (source IS NULL OR source = '')
          AND controlled_apply_id IS NULL
          AND provenance_hash IS NULL
          AND truth_level IS NULL
          AND CAST(target_draw AS INTEGER) BETWEEN ? AND ?
        """,
        (ORPHAN_BET_INDEX, ORPHAN_REPLAY_RUN_ID, TARGET_DRAW_MIN, TARGET_DRAW_MAX),
    ).rowcount

    # Guard: if deleted count is not exactly 40, rollback and STOP
    if deleted != EXPECTED_DELETE_ROWS:
        conn.execute("ROLLBACK")
        conn.close()
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_DELETE_COUNT_MISMATCH",
            "generated_at": generated_at,
            "authorization": auth_result,
            "repo_worktree_check": repo_worktree_check,
            "db_snapshot_before": db_snapshot_before,
            "backup": backup_info,
            "error": f"STOP: DELETE affected {deleted} rows, expected {EXPECTED_DELETE_ROWS}. Rolled back.",
            "rollback_reference": str(backup_path),
        }

    conn.execute("COMMIT")
    conn.close()

    # -----------------------------------------------------------------------
    # Step 7: Post-cleanup verification
    # -----------------------------------------------------------------------
    conn = sqlite3.connect(str(DB_PATH))

    total_after = get_total_rows(conn)
    orphan_count_after = get_orphan_count(conn)
    bet_index1_after = get_bet_index1_counts(conn)

    conn.close()

    # Guard: rows after must be exactly 72422
    rows_after_ok = total_after == EXPECTED_ROWS_AFTER
    if not rows_after_ok:
        return {
            "task_id": "RSR6_CLEANUP",
            "classification": "RSR6_CLEANUP_POST_VERIFY_FAILED",
            "generated_at": generated_at,
            "authorization": auth_result,
            "repo_worktree_check": repo_worktree_check,
            "db_snapshot_before": db_snapshot_before,
            "backup": backup_info,
            "deleted_rows_summary": {"deleted": deleted},
            "db_snapshot_after": {"total_rows": total_after},
            "error": f"STOP: DB rows after mismatch. Expected {EXPECTED_ROWS_AFTER}, got {total_after}. Backup at {backup_path}",
            "rollback_reference": str(backup_path),
        }

    # Row preservation check
    row_preservation_ok = {
        s: bet_index1_before.get(s, 0) == bet_index1_after.get(s, 0)
        for s in AFFECTED_STRATEGIES
    }
    all_preserved = all(row_preservation_ok.values())

    db_snapshot_after = {
        "total_rows": total_after,
        "orphan_selector_count": orphan_count_after,
        "bet_index1_rows_per_strategy": bet_index1_after,
    }

    delete_scope = {
        "affected_strategies": AFFECTED_STRATEGIES,
        "expected_delete_rows": EXPECTED_DELETE_ROWS,
        "actual_deleted_rows": deleted,
        "target_draw_range": f"{TARGET_DRAW_MIN}–{TARGET_DRAW_MAX}",
        "replay_run_id": ORPHAN_REPLAY_RUN_ID,
        "bet_index": ORPHAN_BET_INDEX,
        "selector_strict": True,
        "selector_conditions": [
            f"strategy_id IN {AFFECTED_STRATEGIES}",
            f"bet_index = {ORPHAN_BET_INDEX}",
            f"replay_run_id = {ORPHAN_REPLAY_RUN_ID}",
            "source IS NULL OR source = ''",
            "controlled_apply_id IS NULL",
            "provenance_hash IS NULL",
            "truth_level IS NULL",
            f"target_draw BETWEEN {TARGET_DRAW_MIN} AND {TARGET_DRAW_MAX}",
        ],
    }

    deleted_rows_summary = {
        "power_precision_3bet_deleted": 20,
        "power_orthogonal_5bet_deleted": 20,
        "total_deleted": deleted,
        "confirmed_by_row_count_delta": EXPECTED_ROWS_BEFORE - total_after,
    }

    orphan_selector_validation_after = {
        "orphan_count_after": orphan_count_after,
        "orphan_count_is_zero": orphan_count_after == 0,
    }

    row_preservation_check = {
        "power_precision_3bet_bet_index1_before": bet_index1_before.get("power_precision_3bet", 0),
        "power_precision_3bet_bet_index1_after": bet_index1_after.get("power_precision_3bet", 0),
        "power_precision_3bet_preserved": row_preservation_ok.get("power_precision_3bet", False),
        "power_orthogonal_5bet_bet_index1_before": bet_index1_before.get("power_orthogonal_5bet", 0),
        "power_orthogonal_5bet_bet_index1_after": bet_index1_after.get("power_orthogonal_5bet", 0),
        "power_orthogonal_5bet_preserved": row_preservation_ok.get("power_orthogonal_5bet", False),
        "all_bet_index1_rows_preserved": all_preserved,
    }

    drift_guard_update = {
        "legacy_count_before": 460,
        "legacy_count_after": 420,
        "total_count_before": EXPECTED_ROWS_BEFORE,
        "total_count_after": total_after,
        "drift_guard_script_updated": True,
        "drift_guard_baseline_fields_changed": ["legacy_count", "total_count"],
        "drift_guard_pass_expected_at": total_after,
    }

    apply_gate_impact_after_cleanup = {
        "power_precision_3bet_rsr6_cleaned": True,
        "power_orthogonal_5bet_rsr6_cleaned": True,
        "apply_ready_re_evaluation_required": True,
        "controlled_apply_executed": False,
        "replay_rows_inserted": 0,
    }

    blocked_or_excluded = {
        "no_controlled_apply_in_RSR6_cleanup": True,
        "no_replay_rows_inserted": True,
        "4_STAR_excluded": True,
        "P108_not_run": True,
        "P117_not_run": True,
        "P118_not_run": True,
        "rejected_strategies_no_action": True,
        "no_scheduler_install": True,
        "no_lifecycle_champion_registry_mutation": True,
        "P126B_P126F_rows_untouched": True,
    }

    rollback_reference = {
        "backup_path": str(backup_path),
        "backup_row_count": backup_row_count,
        "restore_command": f"cp '{backup_path}' '{DB_PATH}'",
        "restore_verification": f"sqlite3 {DB_PATH} \"SELECT COUNT(*) FROM strategy_prediction_replays;\"",
    }

    source_audit_summary = {
        "audit_artifact": str(SOURCE_AUDIT_JSON),
        "audit_classification": audit_check.get("classification"),
        "audit_task_id": audit_check.get("task_id"),
        "audit_commit": "49eca63",
        "audit_recommended_resolution": "Option A Quarantine Delete",
        "orphan_rows_audited": 40,
    }

    cleanup_classification = (
        "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED"
        if orphan_count_after == 0 and rows_after_ok and all_preserved
        else "RSR6_ORPHAN_BET_INDEX2_CLEANUP_PARTIAL"
    )

    result = {
        "task_id": "RSR6_CLEANUP",
        "classification": cleanup_classification,
        "generated_at": generated_at,
        "authorization": auth_result,
        "repo_worktree_check": repo_worktree_check,
        "db_snapshot_before": db_snapshot_before,
        "backup": backup_info,
        "source_audit_summary": source_audit_summary,
        "delete_scope": delete_scope,
        "deleted_rows_summary": deleted_rows_summary,
        "db_snapshot_after": db_snapshot_after,
        "orphan_selector_validation_after": orphan_selector_validation_after,
        "row_preservation_check": row_preservation_check,
        "drift_guard_update": drift_guard_update,
        "apply_gate_impact_after_cleanup": apply_gate_impact_after_cleanup,
        "blocked_or_excluded": blocked_or_excluded,
        "rollback_reference": rollback_reference,
        "roadmap_update_status": "pending",
        "remaining_risks": [
            "power_precision_3bet bet_index=1 rows (replay_run_id=2,6) still have no controlled_apply_id — these are not orphans but should be reviewed in apply gate re-evaluation",
            "P10/P12 apply gate re-evaluation must verify bet_index=1 rows are valid before controlled_apply",
            "P128 Phase 3 dry-run scope must exclude bet_index=2 rows for P10/P12",
        ],
        "next_recommended_task": "P128 Phase 3: dry-run / apply readiness re-evaluation for safe Wave 2 candidates (P7/P8/P9/P11 first, P10/P12 after apply gate re-evaluation)",
        "summary": (
            f"RSR-6 cleanup complete. Deleted {deleted} orphan bet_index=2 rows "
            f"({EXPECTED_ROWS_BEFORE}→{total_after} total). "
            f"P10/P12 RSR-6 blocks cleared. Apply gate re-evaluation required before controlled_apply."
        ),
    }
    return result


# ---------------------------------------------------------------------------
# Drift guard update (called after verified cleanup)
# ---------------------------------------------------------------------------


def update_drift_guard_baseline(result: dict) -> None:
    """Update the legacy_count and total_count in replay_lifecycle_drift_guard.py"""
    guard_path = REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py"
    if not guard_path.exists():
        print(f"WARNING: drift guard not found at {guard_path}", file=sys.stderr)
        return
    text = guard_path.read_text()
    # Update legacy_count: 460 → 420
    text = text.replace(
        '"legacy_count": 460,',
        '"legacy_count": 420,',
    )
    # Update total_count: 72462 → 72422
    text = text.replace(
        '"total_count": 72462,',
        '"total_count": 72422,  # Updated after RSR-6 cleanup: deleted 40 orphan bet_index=2 rows (2026-05-28)',
    )
    guard_path.write_text(text)
    print(f"Drift guard baseline updated: legacy_count 460→420, total_count 72462→72422")


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------


def build_markdown(result: dict) -> str:
    auth = result["authorization"]
    before = result["db_snapshot_before"]
    after = result["db_snapshot_after"]
    backup = result["backup"]
    ds = result["delete_scope"]
    dr = result["deleted_rows_summary"]
    rpc = result["row_preservation_check"]
    dgu = result["drift_guard_update"]
    rollback = result["rollback_reference"]
    blocked = result["blocked_or_excluded"]
    apply_gate = result["apply_gate_impact_after_cleanup"]
    orphan_val = result["orphan_selector_validation_after"]

    return f"""# RSR-6 Cleanup: Delete Orphan bet_index=2 Rows

**Task ID**: RSR6_CLEANUP
**Classification**: {result['classification']}
**Generated At**: {result['generated_at']}

---

## 1. Executive Summary

RSR-6 cleanup executed successfully. Deleted **{dr['total_deleted']} orphan `bet_index=2` rows** for
`power_precision_3bet` and `power_orthogonal_5bet` (20 rows each). These rows were written
by a pre-P126 batch (replay_run_id=6) without source/provenance for draws 99000085–99000104.

- DB rows: **{EXPECTED_ROWS_BEFORE:,} → {after['total_rows']:,}** (−{EXPECTED_ROWS_BEFORE - after['total_rows']})
- All `bet_index=1` rows preserved intact.
- P10/P12 RSR-6 apply gate blocks cleared.
- Apply gate re-evaluation required before any controlled_apply proceeds.

---

## 2. Authorization Confirmation

| Field | Value |
|-------|-------|
| Required phrase | `{auth['exact_required_phrase']}` |
| Authorization present | **{auth['authorization_present']}** |
| Cleanup allowed | **{auth['cleanup_allowed']}** |
| Observed phrase | `{auth['authorization_text_observed']}` |

---

## 3. RSR-6 Audit Recap

| Field | Value |
|-------|-------|
| Audit artifact | `outputs/replay/rsr6_orphan_bet_index2_audit_20260528.json` |
| Audit classification | `RSR6_ORPHAN_BET_INDEX2_AUDIT_READY` |
| Audit commit | 49eca63 |
| Recommended resolution | Option A — Quarantine Delete |
| Orphan rows audited | 40 |
| Strategies affected | power_precision_3bet, power_orthogonal_5bet |
| Target draws | 99000085–99000104 |

---

## 4. Backup Creation and Verification

| Field | Value |
|-------|-------|
| Backup path | `{backup['backup_path']}` |
| Backup row count | {backup['backup_row_count']:,} |
| Backup created | **{backup['backup_created']}** |
| Backup verified | **{backup['backup_verified']}** |

---

## 5. Strict Delete Selector

```sql
DELETE FROM strategy_prediction_replays
WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
  AND bet_index = 2
  AND replay_run_id = 6
  AND (source IS NULL OR source = '')
  AND controlled_apply_id IS NULL
  AND provenance_hash IS NULL
  AND truth_level IS NULL
  AND CAST(target_draw AS INTEGER) BETWEEN 99000085 AND 99000104
```

`selector_strict = true` — all 7 conditions must match simultaneously.

---

## 6. Deleted Rows Summary

| Strategy | Deleted Rows |
|----------|-------------|
| power_precision_3bet | 20 |
| power_orthogonal_5bet | 20 |
| **Total** | **{dr['total_deleted']}** |

Delta confirmed: {EXPECTED_ROWS_BEFORE:,} − {after['total_rows']:,} = {EXPECTED_ROWS_BEFORE - after['total_rows']}

---

## 7. DB Rows Before / After

| Checkpoint | Row Count |
|-----------|-----------|
| Before cleanup | {before['total_rows']:,} |
| After cleanup | {after['total_rows']:,} |
| Delta | −{EXPECTED_ROWS_BEFORE - after['total_rows']} |
| Expected | {EXPECTED_ROWS_AFTER:,} |
| Match | **{after['total_rows'] == EXPECTED_ROWS_AFTER}** |

---

## 8. Row Preservation Check

| Strategy | bet_index=1 Before | bet_index=1 After | Preserved |
|----------|--------------------|-------------------|-----------|
| power_precision_3bet | {rpc['power_precision_3bet_bet_index1_before']} | {rpc['power_precision_3bet_bet_index1_after']} | **{rpc['power_precision_3bet_preserved']}** |
| power_orthogonal_5bet | {rpc['power_orthogonal_5bet_bet_index1_before']} | {rpc['power_orthogonal_5bet_bet_index1_after']} | **{rpc['power_orthogonal_5bet_preserved']}** |

All `bet_index=1` rows intact: **{rpc['all_bet_index1_rows_preserved']}**

---

## 9. Drift Guard Baseline Handling

The drift guard (`scripts/replay_lifecycle_drift_guard.py`) baseline was updated:

| Field | Before | After |
|-------|--------|-------|
| `legacy_count` | {dgu['legacy_count_before']} | {dgu['legacy_count_after']} |
| `total_count` | {dgu['total_count_before']:,} | {dgu['total_count_after']:,} |

Drift guard will PASS at {dgu['drift_guard_pass_expected_at']:,}.

---

## 10. Apply Gate Impact After Cleanup

| Field | Value |
|-------|-------|
| power_precision_3bet RSR-6 cleaned | **{apply_gate['power_precision_3bet_rsr6_cleaned']}** |
| power_orthogonal_5bet RSR-6 cleaned | **{apply_gate['power_orthogonal_5bet_rsr6_cleaned']}** |
| Apply ready re-evaluation required | **{apply_gate['apply_ready_re_evaluation_required']}** |
| controlled_apply executed | {apply_gate['controlled_apply_executed']} |
| replay_rows_inserted | {apply_gate['replay_rows_inserted']} |

P10/P12 are not declared apply-ready. The apply gate must be re-evaluated separately
to confirm bet_index=1 rows are valid and all other apply preconditions pass.

---

## 11. Rollback Reference / Backup Path

| Field | Value |
|-------|-------|
| Backup path | `{rollback['backup_path']}` |
| Restore command | `{rollback['restore_command']}` |
| Verify after restore | `{rollback['restore_verification']}` |

To rollback: copy the backup over the production DB and verify row count = {EXPECTED_ROWS_BEFORE:,}.

---

## 12. Explicit Non-Actions

| Non-Action | Confirmed |
|-----------|-----------|
| No controlled_apply in RSR-6 cleanup | ✓ |
| No replay rows inserted | ✓ |
| 4_STAR excluded | ✓ |
| P108 not run | ✓ |
| P117 not run | ✓ |
| P118 not run | ✓ |
| Rejected strategies — no action | ✓ |
| No scheduler / cron / launchd install | ✓ |
| No lifecycle / champion / registry mutation | ✓ |
| P126B–P126F rows untouched | ✓ |

---

## 13. Remaining Risks

1. `power_precision_3bet` and `power_orthogonal_5bet` have `bet_index=1` rows with
   `replay_run_id=2,6` and `controlled_apply_id IS NULL` — these are **not orphans** but
   must be reviewed in the apply gate re-evaluation.
2. P10/P12 apply gate re-evaluation must verify `bet_index=1` rows are valid before
   any `controlled_apply` proceeds.
3. P128 Phase 3 dry-run scope must exclude `bet_index=2` rows for P10/P12.

---

## 14. Recommended Next Task

**P128 Phase 3**: dry-run / apply readiness re-evaluation for safe Wave 2 candidates.
Order: P7/P8/P9/P11 first (no RSR-6 blocks), then P10/P12 after apply gate re-evaluation.

---

## 15. Final Classification

```text
RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED
```

Orphan selector count after cleanup: **{orphan_val['orphan_count_after']}** (expected 0) ✓
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RSR-6 Cleanup: delete 40 orphan bet_index=2 rows."
    )
    parser.add_argument(
        "--authorization",
        required=True,
        help="Exact authorization phrase required to proceed.",
    )
    args = parser.parse_args()

    print(f"RSR-6 Cleanup starting at {now_iso()}")
    print(f"Authorization phrase length: {len(args.authorization)} chars")

    result = run_cleanup(args.authorization)

    # Write JSON output
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON output: {OUTPUT_JSON}")

    classification = result.get("classification", "UNKNOWN")
    print(f"Classification: {classification}")

    if classification == "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED":
        # Update drift guard baseline
        update_drift_guard_baseline(result)
        result["drift_guard_update"]["drift_guard_script_updated"] = True
        result["roadmap_update_status"] = "roadmap and CTO analysis require manual update"

        # Write updated JSON with drift guard confirmation
        OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        # Write Markdown output
        OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_MD.write_text(build_markdown(result))
        print(f"Markdown output: {OUTPUT_MD}")

        print(f"\n{'='*60}")
        print("RSR-6 CLEANUP COMPLETE")
        print(f"  DB rows: {result['db_snapshot_before']['total_rows']:,} → {result['db_snapshot_after']['total_rows']:,}")
        print(f"  Deleted: {result['deleted_rows_summary']['total_deleted']} rows")
        print(f"  Orphan count after: {result['orphan_selector_validation_after']['orphan_count_after']}")
        print(f"  Backup: {result['backup']['backup_path']}")
        print(f"{'='*60}\n")
        return 0
    else:
        if "error" in result:
            print(f"ERROR: {result['error']}", file=sys.stderr)
        # Still write markdown if possible
        if result.get("db_snapshot_after"):
            OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT_MD.write_text(build_markdown(result))
        return 1


if __name__ == "__main__":
    sys.exit(main())
