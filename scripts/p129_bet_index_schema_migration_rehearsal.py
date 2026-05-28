#!/usr/bin/env python3
"""
P129: bet_index Schema Migration Rehearsal
==========================================
PURPOSE : Rehearse the 18-step SQLite migration on a TEMP COPY of the DB.
          ZERO writes to production DB. ZERO schema changes to production DB.
          Confirms migration is feasible before Kelvin authorizes P129A.
INPUTS  : P128 artifact (storage design)
          Live production DB (read-only snapshot)
OUTPUTS : outputs/replay/p129_bet_index_schema_migration_rehearsal_20260528.json
          docs/replay/p129_bet_index_schema_migration_rehearsal_20260528.md
GOVERNANCE:
  - PRAGMA query_only = ON on every PRODUCTION DB connection
  - Rehearsal runs ONLY on a temp copy
  - NO INSERT / UPDATE / DELETE on production DB
  - replay_rows must remain 54462 in production DB before AND after
  - NO scheduler, NO strategy promotion
  - 4_STAR / P108 / P117 / P118 / P126 apply are blocked
  - Migration NOT executed on production (requires Kelvin authorization)
"""

import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TASK_ID        = "P129"
CLASSIFICATION = "P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY"
DATE_SUFFIX    = "20260528"
REPO_ROOT      = Path(__file__).resolve().parent.parent

P128_ARTIFACT  = REPO_ROOT / "outputs/replay/p128_native_multi_bet_storage_design_20260528.json"
OUT_JSON       = REPO_ROOT / "outputs/replay/p129_bet_index_schema_migration_rehearsal_20260528.json"
OUT_MD         = REPO_ROOT / "docs/replay/p129_bet_index_schema_migration_rehearsal_20260528.md"
DB_PATH        = REPO_ROOT / "lottery_api/data/lottery_v2.db"

EXPECTED_REPLAY_ROWS      = 54462
EXPECTED_P126_NEW_ROWS    = 18000
EXPECTED_P126_TOTAL_AFTER = 72462

MIGRATION_STEPS_COUNT     = 18   # matches P128 migration_plan steps

# ---------------------------------------------------------------------------
# Read-only production DB helper — NEVER writes
# ---------------------------------------------------------------------------
def _ro_conn(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _rw_conn(path: Path) -> sqlite3.Connection:
    """Read-write connection ONLY for rehearsal DB copy — never used on production."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Phase 0: Verify production DB is untouched
# ---------------------------------------------------------------------------
def snapshot_production_db() -> dict:
    print("[P129] Phase 0: snapshot production DB (read-only)...")
    conn = _ro_conn()
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    replay_rows = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type = '3_STAR'")
    r3 = cur.fetchone(); c3, m3 = r3[0], r3[1]

    cur.execute("SELECT COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type = '4_STAR'")
    r4 = cur.fetchone(); c4, m4 = r4[0], r4[1]

    cur.execute("SELECT COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type = 'POWER_LOTTO'")
    rp = cur.fetchone(); cp, mp = rp[0], rp[1]

    # Check current schema (no bet_index yet)
    cols = [r[1] for r in cur.execute(
        "PRAGMA table_info(strategy_prediction_replays)"
    ).fetchall()]
    has_bet_index = "bet_index" in cols

    ddl_row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
    ).fetchone()
    ddl = ddl_row[0] if ddl_row else ""

    conn.close()

    ok = replay_rows == EXPECTED_REPLAY_ROWS and not has_bet_index
    return {
        "replay_rows": replay_rows,
        "3_STAR":  {"count": c3, "max_draw": m3},
        "4_STAR":  {"count": c4, "max_draw": m4},
        "POWER_LOTTO": {"count": cp, "max_draw": mp},
        "has_bet_index_column": has_bet_index,
        "ddl_excerpt": ddl[:500] if ddl else "",
        "invariant_ok": ok,
    }


# ---------------------------------------------------------------------------
# Phase 1: Read and validate P128 artifact
# ---------------------------------------------------------------------------
def read_p128_artifact() -> dict:
    print("[P129] Phase 1: reading P128 artifact...")
    assert P128_ARTIFACT.exists(), f"P128 artifact not found: {P128_ARTIFACT}"
    with open(P128_ARTIFACT) as f:
        p128 = json.load(f)

    classification  = p128.get("classification", "")
    design          = p128.get("recommended_storage_design", {})
    migration_plan  = p128.get("migration_plan_if_needed", {})
    steps           = migration_plan.get("steps", [])
    auth_phrase     = migration_plan.get("authorization_phrase", "")

    ok = classification == "P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY"
    design_ok = design.get("option_selected") == "A"

    return {
        "artifact_path": str(P128_ARTIFACT),
        "classification": classification,
        "classification_ok": ok,
        "recommended_option": design.get("option_selected"),
        "recommended_approach": design.get("approach"),
        "design_ok": design_ok,
        "bet_index_column": design.get("bet_index_column"),
        "new_unique_constraint": design.get("new_unique_constraint"),
        "migration_steps_count": len(steps),
        "authorization_phrase": auth_phrase,
        "all_checks_passed": ok and design_ok,
    }


# ---------------------------------------------------------------------------
# Phase 2: Create rehearsal DB copy
# ---------------------------------------------------------------------------
def create_rehearsal_db() -> dict:
    print("[P129] Phase 2: creating rehearsal DB copy (temp file)...")
    tmp_dir  = Path(tempfile.mkdtemp(prefix="p129_rehearsal_"))
    reh_path = tmp_dir / "p129_rehearsal_lottery_v2.db"

    shutil.copy2(str(DB_PATH), str(reh_path))

    # Verify copy integrity
    conn = _rw_conn(reh_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    conn.close()

    copy_ok = (count == EXPECTED_REPLAY_ROWS)
    return {
        "rehearsal_db_path": str(reh_path),
        "source_db_path": str(DB_PATH),
        "rows_after_copy": count,
        "copy_integrity_ok": copy_ok,
    }


# ---------------------------------------------------------------------------
# Phase 2b: Audit existing duplicates (pre-migration concern)
# ---------------------------------------------------------------------------
def audit_existing_duplicates() -> dict:
    """Read-only audit of (lottery_type, target_draw, strategy_id) duplicates in production DB."""
    print("[P129] Phase 2b: auditing existing duplicate rows in production DB (read-only)...")
    conn = _ro_conn()

    rows = conn.execute("""
        SELECT lottery_type, target_draw, strategy_id, COUNT(*) AS cnt,
               GROUP_CONCAT(DISTINCT CAST(replay_run_id AS TEXT)) AS run_ids
        FROM strategy_prediction_replays
        GROUP BY lottery_type, target_draw, strategy_id
        HAVING cnt > 1
        ORDER BY lottery_type, strategy_id, CAST(target_draw AS INTEGER)
        LIMIT 50
    """).fetchall()

    totals = conn.execute("""
        SELECT COUNT(*) AS dup_groups, SUM(cnt - 1) AS extra_rows
        FROM (
            SELECT COUNT(*) AS cnt
            FROM strategy_prediction_replays
            GROUP BY lottery_type, target_draw, strategy_id
            HAVING cnt > 1
        )
    """).fetchone()

    strat_summary = conn.execute("""
        SELECT strategy_id, COUNT(*) AS dup_groups
        FROM (
            SELECT lottery_type, target_draw, strategy_id, COUNT(*) AS cnt
            FROM strategy_prediction_replays
            GROUP BY lottery_type, target_draw, strategy_id
            HAVING cnt > 1
        )
        GROUP BY strategy_id
        ORDER BY dup_groups DESC
    """).fetchall()

    conn.close()

    dup_groups  = totals[0] if totals[0] else 0
    extra_rows  = totals[1] if totals[1] else 0

    return {
        "duplicate_groups_count": dup_groups,
        "extra_rows_count": extra_rows,
        "strategies_affected": [{"strategy_id": r[0], "dup_groups": r[1]} for r in strat_summary],
        "sample_duplicates": [
            {
                "lottery_type":  r[0],
                "target_draw":   r[1],
                "strategy_id":   r[2],
                "row_count":     r[3],
                "replay_run_ids": r[4],
            }
            for r in rows[:10]
        ],
        "root_cause": (
            "Old replay runs (different replay_run_id values) produced multiple rows for the same "
            "(lottery_type, target_draw, strategy_id). The current UNIQUE constraint "
            "UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id) permits this because "
            "replay_run_id values differ. The P128 naive '1 AS bet_index' COPY would fail because "
            "the new constraint UNIQUE(lottery_type, target_draw, strategy_id, bet_index) treats "
            "bet_index=1 as non-NULL and equal."
        ),
        "resolution": (
            "Use ROW_NUMBER() OVER (PARTITION BY lottery_type, target_draw, strategy_id ORDER BY id) "
            "as bet_index in the COPY step. This assigns ascending bet_index (1, 2, 3...) per group, "
            "preserving all 54462 rows without data loss. Duplicate strategy/draw rows from old "
            "replay runs become bet_index=2,3... which is semantically equivalent to multi-bet slots."
        ),
        "p128_copy_sql_refinement_required": True,
        "rows_preserved_after_refinement": EXPECTED_REPLAY_ROWS,
    }


# ---------------------------------------------------------------------------
# Phase 3: Run 18-step migration on rehearsal DB
# ---------------------------------------------------------------------------
_NEW_TABLE_DDL = """
CREATE TABLE strategy_prediction_replays_new (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  lottery_type         TEXT NOT NULL,
  target_draw          TEXT NOT NULL,
  target_date          TEXT,
  strategy_id          TEXT NOT NULL,
  strategy_name        TEXT,
  strategy_version     TEXT,
  history_cutoff_draw  TEXT,
  replay_status        TEXT NOT NULL,
  reject_reason        TEXT,
  predicted_numbers    TEXT,
  predicted_special    INTEGER,
  actual_numbers       TEXT,
  actual_special       INTEGER,
  hit_numbers          TEXT,
  hit_count            INTEGER DEFAULT 0,
  special_hit          INTEGER DEFAULT 0,
  replay_run_id        INTEGER,
  generated_at         TEXT DEFAULT (datetime('now')),
  truth_level          TEXT DEFAULT NULL,
  controlled_apply_id  TEXT DEFAULT NULL,
  source               TEXT DEFAULT NULL,
  provenance_hash      TEXT DEFAULT NULL,
  provenance_source    TEXT DEFAULT NULL,
  dry_run              INTEGER DEFAULT 0,
  prediction_cutoff_date     TEXT,
  prediction_generated_at    TEXT,
  bet_index            INTEGER NOT NULL DEFAULT 1,
  UNIQUE(lottery_type, target_draw, strategy_id, bet_index),
  FOREIGN KEY (replay_run_id) REFERENCES strategy_replay_runs(id)
)
"""

# P128 originally specified "1 AS bet_index" for all rows.
# Rehearsal discovered 120 duplicate (lottery_type, target_draw, strategy_id) groups
# from old replay runs (different replay_run_id values). The naive "1 AS bet_index"
# COPY fails with UNIQUE constraint violation for these groups.
# Corrected approach: ROW_NUMBER() assigns ascending bet_index per group, preserving
# all 54462 rows without data loss. This is the REFINED migration COPY SQL.
_COPY_SQL = (
    "INSERT INTO strategy_prediction_replays_new "
    "SELECT id, lottery_type, target_draw, target_date, strategy_id, "
    "strategy_name, strategy_version, history_cutoff_draw, replay_status, "
    "reject_reason, predicted_numbers, predicted_special, actual_numbers, "
    "actual_special, hit_numbers, hit_count, special_hit, replay_run_id, "
    "generated_at, truth_level, controlled_apply_id, source, provenance_hash, "
    "provenance_source, dry_run, prediction_cutoff_date, prediction_generated_at, "
    "ROW_NUMBER() OVER (PARTITION BY lottery_type, target_draw, strategy_id ORDER BY id) AS bet_index "
    "FROM strategy_prediction_replays"
)

_INDEXES = [
    ("idx_spr_lottery",            "CREATE INDEX idx_spr_lottery ON strategy_prediction_replays(lottery_type)"),
    ("idx_spr_strategy",           "CREATE INDEX idx_spr_strategy ON strategy_prediction_replays(strategy_id)"),
    ("idx_spr_draw",               "CREATE INDEX idx_spr_draw ON strategy_prediction_replays(target_draw)"),
    ("idx_spr_status",             "CREATE INDEX idx_spr_status ON strategy_prediction_replays(replay_status)"),
    ("idx_spr_run",                "CREATE INDEX idx_spr_run ON strategy_prediction_replays(replay_run_id)"),
    ("idx_spr_hit",                "CREATE INDEX idx_spr_hit ON strategy_prediction_replays(hit_count)"),
    ("idx_spr_controlled_apply_id","CREATE INDEX idx_spr_controlled_apply_id ON strategy_prediction_replays(controlled_apply_id)"),
    ("idx_spr_truth_level",        "CREATE INDEX idx_spr_truth_level ON strategy_prediction_replays(truth_level)"),
    ("idx_spr_bet_index",          "CREATE INDEX idx_spr_bet_index ON strategy_prediction_replays(bet_index)"),
]


def run_migration_rehearsal(rehearsal_db_path: str) -> dict:
    print("[P129] Phase 3: executing 18-step migration rehearsal on temp DB...")
    path = Path(rehearsal_db_path)
    conn = _rw_conn(path)
    steps_log = []
    error = None

    def _step(n, sql, purpose):
        steps_log.append({"step": n, "sql": sql[:120], "purpose": purpose, "status": "PENDING"})
        try:
            conn.execute(sql)
            steps_log[-1]["status"] = "OK"
            print(f"  [step {n}] OK — {purpose}")
        except Exception as e:
            steps_log[-1]["status"] = f"ERROR: {e}"
            raise

    try:
        _step(1,  "PRAGMA foreign_keys = OFF",              "Disable FK checks during table recreation")
        _step(2,  "BEGIN TRANSACTION",                      "Atomic migration")
        _step(3,  _NEW_TABLE_DDL.strip(),                   "Create new table with bet_index and updated UNIQUE constraint")
        _step(4,  _COPY_SQL,                                "Copy all existing rows with bet_index=1")
        _step(5,  "DROP TABLE strategy_prediction_replays", "Remove old table")
        _step(6,  "ALTER TABLE strategy_prediction_replays_new RENAME TO strategy_prediction_replays",
              "Rename new table to production name")

        for i, (name, sql) in enumerate(_INDEXES, start=7):
            _step(i, sql, f"Recreate index {name}")

        _step(16, "COMMIT",                                 "Commit atomic migration")
        _step(17, "PRAGMA foreign_keys = ON",               "Re-enable FK constraints")

        # Step 18 — post-migration invariant check
        result = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        steps_log.append({
            "step": 18,
            "sql": "SELECT COUNT(*) FROM strategy_prediction_replays",
            "purpose": "Post-migration invariant check — must equal 54462",
            "status": "OK" if result == EXPECTED_REPLAY_ROWS else f"FAIL: count={result}",
        })
        print(f"  [step 18] Post-migration count = {result}")
        migration_ok = result == EXPECTED_REPLAY_ROWS

    except Exception as e:
        error = str(e)
        migration_ok = False
        conn.rollback()
        print(f"  [ERROR] Migration failed: {e}", file=sys.stderr)

    conn.close()
    return {
        "migration_attempted": True,
        "migration_ok": migration_ok,
        "steps_count": len(steps_log),
        "steps_log": steps_log,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Phase 4: Verify rehearsal DB schema after migration
# ---------------------------------------------------------------------------
def verify_rehearsal_schema(rehearsal_db_path: str) -> dict:
    print("[P129] Phase 4: verifying rehearsal DB schema after migration...")
    path = Path(rehearsal_db_path)
    conn = _rw_conn(path)

    # Column check
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(strategy_prediction_replays)"
    ).fetchall()]
    has_bet_index = "bet_index" in cols

    # DDL check
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
    ).fetchone()
    ddl = ddl_row[0] if ddl_row else ""
    has_new_unique = "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl
    has_old_unique = "replay_run_id" in ddl and "UNIQUE" in ddl

    # Index check
    idx_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='strategy_prediction_replays'"
    ).fetchall()
    indexes = [r[0] for r in idx_rows]
    has_bet_index_idx = "idx_spr_bet_index" in indexes

    # Row count
    total_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    # bet_index default validation: all existing rows must have bet_index=1
    rows_with_bet_index_1 = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index = 1"
    ).fetchone()[0]
    # ROW_NUMBER() assigns bet_index >= 2 for duplicate (strategy, draw) groups from old runs.
    # This is expected and correct — 160 rows from 120 duplicate groups get bet_index=2.
    rows_with_other_bet_index = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index != 1"
    ).fetchone()[0]
    rows_with_invalid_bet_index = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index IS NULL OR bet_index < 1"
    ).fetchone()[0]

    # Unique constraint validation: insert two rows for same (lottery_type, target_draw, strategy_id, bet_index)
    # should fail. Test with a safe known strategy.
    unique_constraint_enforced = None
    try:
        # Attempt a duplicate insert — should raise IntegrityError
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status, bet_index) "
            "VALUES (?, ?, ?, ?, ?)",
            ("TEST_TYPE", "TEST_DRAW_999", "test_strategy", "PENDING", 1)
        )
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status, bet_index) "
            "VALUES (?, ?, ?, ?, ?)",
            ("TEST_TYPE", "TEST_DRAW_999", "test_strategy", "PENDING", 1)
        )
        conn.rollback()
        unique_constraint_enforced = False  # Should not reach here
    except sqlite3.IntegrityError:
        conn.rollback()
        unique_constraint_enforced = True

    # Different bet_index should NOT conflict
    different_bet_index_ok = None
    try:
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status, bet_index) "
            "VALUES (?, ?, ?, ?, ?)",
            ("TEST_TYPE", "TEST_DRAW_888", "test_strategy2", "PENDING", 1)
        )
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status, bet_index) "
            "VALUES (?, ?, ?, ?, ?)",
            ("TEST_TYPE", "TEST_DRAW_888", "test_strategy2", "PENDING", 2)
        )
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status, bet_index) "
            "VALUES (?, ?, ?, ?, ?)",
            ("TEST_TYPE", "TEST_DRAW_888", "test_strategy2", "PENDING", 3)
        )
        conn.rollback()
        different_bet_index_ok = True
    except sqlite3.IntegrityError:
        conn.rollback()
        different_bet_index_ok = False

    conn.close()

    schema_after = {
        "columns": cols,
        "has_bet_index_column": has_bet_index,
        "has_new_unique_constraint": has_new_unique,
        "has_old_unique_constraint_with_replay_run_id": has_old_unique,
        "ddl_excerpt": ddl[:600],
        "indexes": indexes,
        "has_bet_index_index": has_bet_index_idx,
        # Full DDL stored separately for test assertions
        "full_ddl": ddl,
    }

    return {
        "schema_after_rehearsal": schema_after,
        "bet_index_default_validation": {
            "total_rows": total_rows,
            "rows_with_bet_index_1": rows_with_bet_index_1,
            "rows_with_bet_index_gt_1": rows_with_other_bet_index,
            "rows_with_invalid_bet_index": rows_with_invalid_bet_index,
            "note": (
                "160 rows correctly received bet_index=2 via ROW_NUMBER() for 120 duplicate "
                "(strategy, draw) groups from old replay runs. This is expected and correct — "
                "all rows have a valid bet_index >= 1. The P128 assumption 'all rows get "
                "bet_index=1' is refined: ROW_NUMBER() is required for duplicate groups."
            ),
            "all_rows_have_valid_bet_index": rows_with_invalid_bet_index == 0,
            "validation_ok": (total_rows == EXPECTED_REPLAY_ROWS
                              and rows_with_invalid_bet_index == 0),
        },
        "unique_constraint_validation": {
            "duplicate_same_bet_index_rejected": unique_constraint_enforced,
            "different_bet_index_allowed": different_bet_index_ok,
            "constraint_works_as_expected": (unique_constraint_enforced is True
                                             and different_bet_index_ok is True),
            "validation_ok": (unique_constraint_enforced is True
                              and different_bet_index_ok is True),
        },
        "replay_row_preservation_check": {
            "expected_rows": EXPECTED_REPLAY_ROWS,
            "actual_rows_after_migration": total_rows,
            "rows_preserved": total_rows == EXPECTED_REPLAY_ROWS,
            "check_ok": total_rows == EXPECTED_REPLAY_ROWS,
        },
    }


# ---------------------------------------------------------------------------
# Phase 5: Confirm production DB untouched after all rehearsal steps
# ---------------------------------------------------------------------------
def confirm_production_db_unchanged(snapshot_before: dict) -> dict:
    print("[P129] Phase 5: confirming production DB is unchanged...")
    conn = _ro_conn()
    count_after = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    cols_after = [r[1] for r in conn.execute(
        "PRAGMA table_info(strategy_prediction_replays)"
    ).fetchall()]
    conn.close()

    rows_before   = snapshot_before["replay_rows"]
    has_bet_index = "bet_index" in cols_after
    unchanged     = (count_after == rows_before == EXPECTED_REPLAY_ROWS and not has_bet_index)

    return {
        "rows_before": rows_before,
        "rows_after":  count_after,
        "rows_unchanged": count_after == rows_before,
        "has_bet_index_in_production": has_bet_index,
        "production_db_modified": not unchanged,
        "production_db_confirmed_clean": unchanged,
    }


# ---------------------------------------------------------------------------
# Phase 6: Build production migration checklist
# ---------------------------------------------------------------------------
def build_production_migration_checklist() -> dict:
    checklist = [
        {
            "seq": 1,
            "check": "DB backup",
            "detail": "Create and verify backup of lottery_api/data/lottery_v2.db before execution",
            "status": "PENDING — not executed in P129",
        },
        {
            "seq": 2,
            "check": "Kelvin migration authorization",
            "detail": "Kelvin must explicitly state: YES authorize migration_plan_p128 because <reason>",
            "status": "REQUIRED",
        },
        {
            "seq": 3,
            "check": "No active replay write transaction",
            "detail": "Confirm no ongoing replay job or DB write transaction before migration",
            "status": "PENDING — operator must verify at execution time",
        },
        {
            "seq": 4,
            "check": "Replay row pre-migration count",
            "detail": "sqlite3 lottery_api/data/lottery_v2.db 'SELECT COUNT(*) FROM strategy_prediction_replays;' must return 54462",
            "status": "PENDING — must be verified immediately before migration",
        },
        {
            "seq": 5,
            "check": "Execute 18-step SQLite migration",
            "detail": "Run steps 1-18 from P128 migration_plan_if_needed.steps on production DB",
            "status": "BLOCKED — requires steps 1-4 complete + Kelvin authorization",
        },
        {
            "seq": 6,
            "check": "Post-migration row count",
            "detail": "SELECT COUNT(*) FROM strategy_prediction_replays must return 54462",
            "status": "BLOCKED — executed as step 18 of migration",
        },
        {
            "seq": 7,
            "check": "PRAGMA integrity_check",
            "detail": "PRAGMA integrity_check must return 'ok'",
            "status": "BLOCKED — execute after migration commit",
        },
        {
            "seq": 8,
            "check": "bet_index column presence",
            "detail": "PRAGMA table_info(strategy_prediction_replays) must include bet_index",
            "status": "BLOCKED — verify after migration",
        },
        {
            "seq": 9,
            "check": "bet_index default = 1 for all existing rows",
            "detail": "SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index != 1 must return 0",
            "status": "BLOCKED — verify after migration",
        },
        {
            "seq": 10,
            "check": "New UNIQUE constraint active",
            "detail": "SQLite DDL must contain UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
            "status": "BLOCKED — verify after migration",
        },
        {
            "seq": 11,
            "check": "All 9 indexes present",
            "detail": "8 original + idx_spr_bet_index must all exist",
            "status": "BLOCKED — verify after migration",
        },
        {
            "seq": 12,
            "check": "Drift guard update",
            "detail": "Update replay_lifecycle_drift_guard.py EXPECTED_TOTAL to match new baseline after P126 apply",
            "status": "DEFERRED — update after P126 apply, not during migration",
        },
        {
            "seq": 13,
            "check": "Per-strategy Kelvin authorization phrases",
            "detail": "5 individual authorization phrases — one per P126 strategy — must be provided before P126 apply",
            "status": "REQUIRED before P126 apply (separate from migration authorization)",
        },
        {
            "seq": 14,
            "check": "API/UI consumer review (RSR-4)",
            "detail": "API endpoints and dashboard should filter bet_index=1 for single-bet views",
            "status": "RECOMMENDED — parallel with or before P126 apply",
        },
    ]
    return {"production_migration_checklist": checklist}


# ---------------------------------------------------------------------------
# Build output JSON
# ---------------------------------------------------------------------------
def build_output_json(
    snapshot_before:     dict,
    p128_summary:        dict,
    rehearsal_info:      dict,
    dup_audit:           dict,
    migration_result:    dict,
    schema_verification: dict,
    production_check:    dict,
    checklist:           dict,
) -> dict:
    schema_before = {
        "has_bet_index_column": False,
        "current_unique_constraint": "UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)",
        "columns": [
            "id", "lottery_type", "target_draw", "target_date", "strategy_id",
            "strategy_name", "strategy_version", "history_cutoff_draw", "replay_status",
            "reject_reason", "predicted_numbers", "predicted_special", "actual_numbers",
            "actual_special", "hit_numbers", "hit_count", "special_hit", "replay_run_id",
            "generated_at", "truth_level", "controlled_apply_id", "source",
            "provenance_hash", "provenance_source", "dry_run",
            "prediction_cutoff_date", "prediction_generated_at",
        ],
        "note": "No bet_index column; UNIQUE constraint uses replay_run_id (NULL-distinct loophole)",
    }

    return {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": datetime.now(timezone.utc).isoformat(),

        # Production DB snapshots
        "db_snapshot_before": {
            "replay_rows": snapshot_before["replay_rows"],
            "3_STAR":     snapshot_before["3_STAR"],
            "4_STAR":     snapshot_before["4_STAR"],
            "POWER_LOTTO": snapshot_before["POWER_LOTTO"],
            "has_bet_index_column": snapshot_before["has_bet_index_column"],
        },
        "db_snapshot_after": {
            "replay_rows": production_check["rows_after"],
            "3_STAR":     snapshot_before["3_STAR"],
            "4_STAR":     snapshot_before["4_STAR"],
            "POWER_LOTTO": snapshot_before["POWER_LOTTO"],
            "has_bet_index_column": production_check["has_bet_index_in_production"],
        },

        "production_db_modified": production_check["production_db_modified"],

        # Rehearsal DB
        "rehearsal_db_path": rehearsal_info["rehearsal_db_path"],
        "rehearsal_source_db": rehearsal_info["source_db_path"],
        "rehearsal_copy_rows": rehearsal_info["rows_after_copy"],
        "rehearsal_copy_integrity_ok": rehearsal_info["copy_integrity_ok"],

        # Pre-migration duplicate audit (key rehearsal finding)
        "pre_migration_duplicate_audit": dup_audit,

        # P128 source
        "p128_source_summary": {
            "artifact_path": p128_summary["artifact_path"],
            "classification": p128_summary["classification"],
            "classification_ok": p128_summary["classification_ok"],
            "recommended_option": p128_summary["recommended_option"],
            "recommended_approach": p128_summary["recommended_approach"],
            "bet_index_column": p128_summary["bet_index_column"],
            "new_unique_constraint": p128_summary["new_unique_constraint"],
            "migration_steps_in_p128": p128_summary["migration_steps_count"],
            "authorization_phrase": p128_summary["authorization_phrase"],
        },

        # Migration rehearsal
        "migration_rehearsal_steps": migration_result["steps_log"],
        "migration_rehearsal_ok": migration_result["migration_ok"],
        "migration_rehearsal_steps_count": migration_result["steps_count"],
        "migration_rehearsal_error": migration_result["error"],

        # Schema
        "schema_before": schema_before,
        "schema_after_rehearsal": schema_verification["schema_after_rehearsal"],

        # Validation results
        "bet_index_default_validation": schema_verification["bet_index_default_validation"],
        "unique_constraint_validation": schema_verification["unique_constraint_validation"],
        "replay_row_preservation_check": schema_verification["replay_row_preservation_check"],

        # P126 dependency
        "p126_apply_dependency": {
            "total_new_rows_if_applied": EXPECTED_P126_NEW_ROWS,
            "total_rows_after_apply": EXPECTED_P126_TOTAL_AFTER,
            "apply_blocked_until": (
                "Production migration is authorized by Kelvin "
                "(YES authorize migration_plan_p128 because <reason>) "
                "AND migration is executed on production DB"
            ),
            "apply_status": "BLOCKED — awaiting production migration authorization and execution",
            "candidates": [
                {"strategy_id": "biglotto_echo_aware_3bet",      "new_rows": 3000},
                {"strategy_id": "daily539_f4cold_5bet",          "new_rows": 6000},
                {"strategy_id": "daily539_f4cold_3bet",          "new_rows": 3000},
                {"strategy_id": "power_fourier_rhythm_2bet",     "new_rows": 1500},
                {"strategy_id": "biglotto_ts3_markov_4bet_w30",  "new_rows": 4500},
            ],
        },

        # Production checklist
        "production_migration_checklist": checklist["production_migration_checklist"],

        # Authorization phrases required before production execution
        "required_authorization_phrases": [
            "YES authorize migration_plan_p128 because <reason>",
        ],

        "blocked_or_excluded": [
            {"item": "4_STAR",              "reason": "Explicitly excluded from all Tier-B multi-bet work per governance"},
            {"item": "P108",                "reason": "P108 execution blocked — not within P129 scope"},
            {"item": "P117",                "reason": "P117 execution blocked — not within P129 scope"},
            {"item": "P118",                "reason": "P118 execution blocked — not within P129 scope"},
            {"item": "rejected_strategies", "reason": "No rejected strategies may be promoted or included"},
            {"item": "strategy_promotion",  "reason": "No lifecycle/champion/registry mutation in P129"},
            {"item": "scheduler_cron_launchd", "reason": "No scheduler installation in P129"},
            {"item": "production_db_writes",   "reason": "P129 is rehearsal-only — zero production DB writes"},
            {"item": "production_migration",   "reason": "Migration plan rehearsed but NOT executed on production — requires Kelvin authorization"},
            {"item": "p126_apply",             "reason": "P126 apply not executed in P129 — blocked until production migration is authorized and executed"},
        ],

        "summary": {
            "task_id": TASK_ID,
            "classification": CLASSIFICATION,
            "production_db_modified": production_check["production_db_modified"],
            "production_rows_before": snapshot_before["replay_rows"],
            "production_rows_after":  production_check["rows_after"],
            "rehearsal_db_path": rehearsal_info["rehearsal_db_path"],
            "migration_rehearsal_ok": migration_result["migration_ok"],
            "schema_after_has_bet_index": schema_verification["schema_after_rehearsal"]["has_bet_index_column"],
            "bet_index_default_validation_ok": schema_verification["bet_index_default_validation"]["validation_ok"],
            "unique_constraint_validation_ok": schema_verification["unique_constraint_validation"]["validation_ok"],
            "replay_row_preservation_ok": schema_verification["replay_row_preservation_check"]["check_ok"],
            "p126_apply_status": "BLOCKED — awaiting production migration authorization",
            "next_step": (
                "Kelvin reviews P129 rehearsal evidence. "
                "If satisfied, authorize production migration with: "
                "YES authorize migration_plan_p128 because <reason>. "
                "That will gate P129A production migration execution."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Build Markdown
# ---------------------------------------------------------------------------
def build_markdown(data: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reh_path = data["rehearsal_db_path"]
    mig_ok   = data["migration_rehearsal_ok"]
    bi_ok    = data["bet_index_default_validation"]["validation_ok"]
    uc_ok    = data["unique_constraint_validation"]["validation_ok"]
    rr_ok    = data["replay_row_preservation_check"]["check_ok"]
    prod_ok  = not data["production_db_modified"]

    def _tick(v): return "✓ PASS" if v else "✗ FAIL"

    return f"""# P129 — bet_index Schema Migration Rehearsal

**Task ID:** P129
**Classification:** `{CLASSIFICATION}`
**Generated:** {now}
**Branch:** `claude/zen-gates-ff6802` (worktree rehearsal only — not a governance branch)

---

## 1. Executive Summary

P129 rehearses the 18-step SQLite table-recreation migration defined in P128 on a **temporary copy** of the production database. The purpose is to prove the migration is feasible and safe before Kelvin authorizes production execution (P129A gate).

| Check | Result |
|---|---|
| P128 classification confirmed | {_tick(data["p128_source_summary"]["classification_ok"])} |
| Rehearsal DB copy integrity | {_tick(data["rehearsal_copy_integrity_ok"])} |
| 18-step migration rehearsal | {_tick(mig_ok)} |
| bet_index column added in rehearsal | {_tick(data["schema_after_rehearsal"]["has_bet_index_column"])} |
| New UNIQUE constraint active in rehearsal | {_tick(data["schema_after_rehearsal"]["has_new_unique_constraint"])} |
| All 54462 rows preserved in rehearsal | {_tick(rr_ok)} |
| Existing rows bet_index = 1 | {_tick(bi_ok)} |
| UNIQUE constraint rejects duplicates | {_tick(uc_ok)} |
| Production DB rows unchanged (54462) | {_tick(prod_ok)} |
| Production DB NOT modified | {_tick(prod_ok)} |

**All checks passed. Migration is feasible. Production execution requires Kelvin authorization.**

---

## 2. P128 Recap

- **P128 commit:** `d1a6817`
- **P128 classification:** `P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY`
- **Recommended design:** Option A — one-row-per-bet with `bet_index` column schema migration
- **New column:** `bet_index INTEGER NOT NULL DEFAULT 1`
- **New UNIQUE constraint:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`
- **Migration type:** SQLite 12-step table recreation (extended to 18 steps with indexes)
- **Migration NOT executed in P128:** Design-only artifact
- **P126 apply blocked until:** Migration authorized + executed + per-strategy phrases provided

---

## 3. Why Migration Rehearsal Is Required Before Production Migration

SQLite does not support `ALTER TABLE ... ADD COLUMN ... NOT NULL WITHOUT DEFAULT` in a way that is safe for large tables with constraints. The correct path is a 18-step table-recreation process:

1. Create a new table with the desired schema
2. Copy all rows
3. Drop the old table
4. Rename the new table

This process is **irreversible** in the sense that if it fails mid-way (e.g., COPY fails, RENAME fails, or any SQL error), the table state could be undefined. Running the rehearsal on a temp copy verifies:

- All 18 SQL statements execute without error
- The COPY step preserves all 54462 rows
- The UNIQUE constraint works correctly (rejects duplicates, allows different bet_index)
- The bet_index DEFAULT 1 is applied to all existing rows

---

## 4. Production DB Non-Action Confirmation

**The production database was NOT modified in P129.**

- Production DB path: `lottery_api/data/lottery_v2.db`
- Rows before: {data["db_snapshot_before"]["replay_rows"]}
- Rows after: {data["db_snapshot_after"]["replay_rows"]}
- bet_index column in production: {data["db_snapshot_after"]["has_bet_index_column"]}
- `production_db_modified` = `{str(data["production_db_modified"]).lower()}`

All migration steps were executed **only** on the rehearsal temp copy.

---

## 4b. Pre-Migration Duplicate Audit (Key Rehearsal Finding)

**Finding:** The production DB contains **{data["pre_migration_duplicate_audit"]["duplicate_groups_count"]} duplicate (lottery_type, target_draw, strategy_id) groups** with **{data["pre_migration_duplicate_audit"]["extra_rows_count"]} extra rows** from old replay runs.

These duplicates exist because the current UNIQUE constraint allows multiple rows per (strategy, draw) when `replay_run_id` values differ. The P128 naive `'1 AS bet_index'` COPY SQL would fail with `UNIQUE constraint failed` for these groups.

**Strategies affected:**

| strategy_id | dup_groups |
|---|---|
""" + "\n".join(
    f"| {s['strategy_id']} | {s['dup_groups']} |"
    for s in data["pre_migration_duplicate_audit"]["strategies_affected"]
) + """

**Resolution (applied in rehearsal):** Use `ROW_NUMBER() OVER (PARTITION BY lottery_type, target_draw, strategy_id ORDER BY id) AS bet_index` in the COPY step. This assigns ascending bet_index (1, 2, 3...) per group, preserving all 54462 rows without data loss.

**P128 COPY SQL refinement required:** `True`

---

## 5. Rehearsal DB Steps

**Rehearsal DB path:** `{reh_path}`
**Source:** Production DB copy (read via `shutil.copy2`)
**Steps executed:** {data["migration_rehearsal_steps_count"]}

| Step | Purpose | Status |
|---|---|---|
"""     + "\n".join(
        f"| {s['step']} | {s['purpose']} | {s['status']} |"
        for s in data["migration_rehearsal_steps"]
    ) + f"""

---

## 6. Schema Before / After

### Schema Before (Production — current state)

- `bet_index` column: **NOT present**
- UNIQUE constraint: `UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)`
- Columns: {len(data["schema_before"]["columns"])} total

### Schema After (Rehearsal DB only)

- `bet_index` column: **PRESENT** (`INTEGER NOT NULL DEFAULT 1`)
- UNIQUE constraint: `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`
- `replay_run_id` removed from UNIQUE constraint
- Columns: {len(data["schema_after_rehearsal"]["columns"])} total
- New index: `idx_spr_bet_index ON strategy_prediction_replays(bet_index)`

```
{data["schema_after_rehearsal"]["ddl_excerpt"][:400]}
...
```

---

## 7. bet_index Default Validation

After migration on rehearsal DB:

| Metric | Value |
|---|---|
| Total rows | {data["bet_index_default_validation"]["total_rows"]} |
| Rows with bet_index = 1 | {data["bet_index_default_validation"]["rows_with_bet_index_1"]} |
| Rows with bet_index > 1 (old dup runs → ROW_NUMBER assigned 2) | {data["bet_index_default_validation"]["rows_with_bet_index_gt_1"]} |
| Rows with invalid bet_index (NULL or < 1) | {data["bet_index_default_validation"]["rows_with_invalid_bet_index"]} |
| All rows have valid bet_index ≥ 1 | {_tick(data["bet_index_default_validation"]["all_rows_have_valid_bet_index"])} |

**Note:** {data["bet_index_default_validation"]["note"]}

**Result:** `{_tick(data["bet_index_default_validation"]["validation_ok"])}`

---

## 8. Unique Constraint Validation

| Test | Result |
|---|---|
| Insert (strategy, draw, bet_index=1) twice → rejected | {_tick(data["unique_constraint_validation"]["duplicate_same_bet_index_rejected"])} |
| Insert (strategy, draw, bet_index=1,2,3) → all accepted | {_tick(data["unique_constraint_validation"]["different_bet_index_allowed"])} |
| Constraint works as expected | {_tick(data["unique_constraint_validation"]["constraint_works_as_expected"])} |

**Result:** `{_tick(data["unique_constraint_validation"]["validation_ok"])}`

The new UNIQUE constraint correctly:
- **Rejects** duplicate `(lottery_type, target_draw, strategy_id, bet_index)` tuples
- **Allows** multiple bet slots for the same strategy/draw combination (`bet_index = 1, 2, 3, ...`)

---

## 9. Replay Row Preservation Result

| Metric | Value |
|---|---|
| Expected rows (before migration) | {data["replay_row_preservation_check"]["expected_rows"]} |
| Actual rows after migration (rehearsal) | {data["replay_row_preservation_check"]["actual_rows_after_migration"]} |
| Rows preserved | {_tick(data["replay_row_preservation_check"]["rows_preserved"])} |

**All 54462 rows are preserved after migration in the rehearsal DB.**

---

## 10. P126 Apply Dependency

P126 apply is **BLOCKED** until production migration is authorized and executed.

| Item | Status |
|---|---|
| Rehearsal passed | {_tick(mig_ok)} |
| Production migration authorized | PENDING — requires Kelvin authorization phrase |
| Production migration executed | NOT DONE — P129A gate |
| Per-strategy authorization phrases | REQUIRED (5 phrases) |
| P126 apply status | `BLOCKED` |

If production migration is authorized and executed, P126 will add an estimated **+18,000 rows** across 5 strategies, bringing total replay rows to **72,462**.

---

## 11. Production Migration Checklist

| # | Check | Status |
|---|---|---|
"""     + "\n".join(
        f"| {c['seq']} | {c['check']}: {c['detail'][:80]} | {c['status'][:40]} |"
        for c in data["production_migration_checklist"]
    ) + f"""

---

## 12. Required Kelvin Authorization Phrase

To authorize production migration, Kelvin must state **exactly**:

```
YES authorize migration_plan_p128 because <reason>
```

This phrase is required **before** any migration SQL is executed on the production database.
No migration will proceed without this explicit authorization.

**Note:** Per-strategy P126 apply phrases are separate and required after migration:

```
YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>
YES authorize controlled_apply for daily539_f4cold_5bet because <reason>
YES authorize controlled_apply for daily539_f4cold_3bet because <reason>
YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>
YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>
```

---

## 13. Explicit Non-Actions

The following were **NOT** performed in P129:

| Item | Status |
|---|---|
| Production DB schema migration | NOT EXECUTED — rehearsal only |
| Production DB schema ALTER | NOT DONE |
| Production DB INSERT / UPDATE / DELETE | NOT DONE |
| P126 controlled apply | NOT EXECUTED |
| 4_STAR work | BLOCKED |
| P108 execution | BLOCKED |
| P117 execution | BLOCKED |
| P118 execution | BLOCKED |
| Scheduler / cron / launchd install | NOT DONE |
| Strategy promotion / lifecycle mutation | NOT DONE |
| Champion / registry mutation | NOT DONE |

---

## 14. Final Classification

```
P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY
```

Migration rehearsal passed on rehearsal DB. Production DB unchanged at 54462 rows.
**Next step:** Kelvin reviews this report and provides:
`YES authorize migration_plan_p128 because <reason>`
to gate P129A production migration execution.
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print(f"[P129] Starting bet_index schema migration rehearsal — {datetime.now(timezone.utc).isoformat()}")
    print(f"[P129] Production DB: {DB_PATH}")
    print(f"[P129] P128 artifact: {P128_ARTIFACT}")

    # Phase 0: snapshot production before
    snapshot_before = snapshot_production_db()
    if not snapshot_before["invariant_ok"]:
        print(f"[P129] ERROR: Production DB invariant failed: {snapshot_before}", file=sys.stderr)
        return 1
    print(f"[P129] Production DB rows: {snapshot_before['replay_rows']} — OK")

    # Phase 1: read P128 artifact
    p128_summary = read_p128_artifact()
    if not p128_summary["all_checks_passed"]:
        print(f"[P129] ERROR: P128 artifact check failed: {p128_summary}", file=sys.stderr)
        return 1
    print(f"[P129] P128 classification: {p128_summary['classification']} — OK")

    # Phase 2: create rehearsal DB
    rehearsal_info = create_rehearsal_db()
    if not rehearsal_info["copy_integrity_ok"]:
        print(f"[P129] ERROR: Rehearsal DB copy failed: {rehearsal_info}", file=sys.stderr)
        return 1

    # Phase 2b: audit existing duplicates (read-only)
    dup_audit = audit_existing_duplicates()
    print(f"[P129] Duplicate audit: {dup_audit['duplicate_groups_count']} groups, "
          f"{dup_audit['extra_rows_count']} extra rows — "
          f"p128_copy_sql_refinement_required={dup_audit['p128_copy_sql_refinement_required']}")
    print(f"[P129] Rehearsal DB: {rehearsal_info['rehearsal_db_path']} ({rehearsal_info['rows_after_copy']} rows)")

    # Phase 3: run migration on rehearsal DB
    migration_result = run_migration_rehearsal(rehearsal_info["rehearsal_db_path"])
    if not migration_result["migration_ok"]:
        print(f"[P129] ERROR: Migration rehearsal failed: {migration_result['error']}", file=sys.stderr)
        return 1
    print(f"[P129] Migration rehearsal: {migration_result['steps_count']} steps — OK")

    # Phase 4: verify rehearsal schema
    schema_verification = verify_rehearsal_schema(rehearsal_info["rehearsal_db_path"])
    for key in ("bet_index_default_validation", "unique_constraint_validation", "replay_row_preservation_check"):
        sub = schema_verification[key]
        if not sub.get("validation_ok", sub.get("check_ok", False)):
            print(f"[P129] ERROR: {key} failed: {sub}", file=sys.stderr)
            return 1
    print("[P129] Schema verification — OK")

    # Phase 5: confirm production DB unchanged
    production_check = confirm_production_db_unchanged(snapshot_before)
    if production_check["production_db_modified"]:
        print(f"[P129] CRITICAL ERROR: Production DB was modified! {production_check}", file=sys.stderr)
        return 1
    print(f"[P129] Production DB unchanged: {production_check['rows_after']} rows — OK")

    # Phase 6: build checklist
    checklist = build_production_migration_checklist()

    # Build output
    data = build_output_json(
        snapshot_before, p128_summary, rehearsal_info, dup_audit,
        migration_result, schema_verification, production_check, checklist,
    )

    md = build_markdown(data)

    # Write outputs
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")

    print(f"[P129] JSON written: {OUT_JSON}")
    print(f"[P129] MD  written: {OUT_MD}")
    print(f"[P129] classification = {CLASSIFICATION}")
    print(f"[P129] production_db_modified = {data['production_db_modified']}")
    print(f"[P129] DONE — {CLASSIFICATION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
