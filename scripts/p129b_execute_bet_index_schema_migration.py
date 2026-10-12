#!/usr/bin/env python3
"""
P129B: Execute bet_index Schema Migration on Production DB
==========================================================
PURPOSE : Execute the corrected 18-step SQLite table-recreation migration on
          the production database. Only runs if exact authorization phrase is
          supplied via --authorization CLI argument.
SAFETY:
  - Validates authorization phrase FIRST. Stops immediately if absent.
  - Creates a verified backup BEFORE any migration step.
  - Uses ROW_NUMBER() COPY SQL (corrected by P129 rehearsal — not naive '1 AS bet_index').
  - Full transaction wrap with ROLLBACK on failure.
  - Post-migration: verifies row count, schema, bet_index distribution, UNIQUE constraint.
  - P126 apply is NOT executed in this script.
GOVERNANCE:
  - NO P126 apply
  - NO scheduler / cron / launchd
  - NO 4_STAR / P108 / P117 / P118
  - NO strategy promotion / lifecycle / champion / registry mutation
"""

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TASK_ID        = "P129B"
CLASSIFICATION = "P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED"
DATE_SUFFIX    = "20260528"
REPO_ROOT      = Path(__file__).resolve().parent.parent

P129A_ARTIFACT = REPO_ROOT / "outputs/replay/p129a_production_migration_authorization_gate_20260528.json"
P129_ARTIFACT  = REPO_ROOT / "outputs/replay/p129_bet_index_schema_migration_rehearsal_20260528.json"
OUT_JSON       = REPO_ROOT / "outputs/replay/p129b_execute_bet_index_schema_migration_20260528.json"
OUT_MD         = REPO_ROOT / "docs/replay/p129b_execute_bet_index_schema_migration_20260528.md"
DB_PATH        = REPO_ROOT / "lottery_api/data/lottery_v2.db"
BACKUP_DIR     = REPO_ROOT / "lottery_api/data/backups"

EXPECTED_ROWS_BEFORE  = 54462
EXPECTED_ROWS_AFTER   = 54462
EXACT_AUTH_PREFIX     = "YES authorize migration_plan_p128 because "

# Expected distribution after migration (from P129 rehearsal)
EXPECTED_BET_INDEX_1  = 54302
EXPECTED_BET_INDEX_GT1 = 160


# ---------------------------------------------------------------------------
# Authorization check
# ---------------------------------------------------------------------------
def validate_authorization(auth_text=None) -> dict:
    if not auth_text:
        return {
            "exact_required_phrase": f"{EXACT_AUTH_PREFIX}<reason>",
            "authorization_present": False,
            "migration_allowed": False,
            "authorization_text_observed": None,
            "reason_text": None,
            "stop_reason": "NO_AUTHORIZATION_TEXT_PROVIDED",
        }

    stripped = auth_text.strip()
    present = stripped.startswith(EXACT_AUTH_PREFIX) and not stripped.endswith("<reason>")
    reason  = stripped[len(EXACT_AUTH_PREFIX):].strip() if present else None

    return {
        "exact_required_phrase": f"{EXACT_AUTH_PREFIX}<reason>",
        "authorization_present": present,
        "migration_allowed": present,
        "authorization_text_observed": stripped,
        "reason_text": reason,
        "stop_reason": None if present else "AUTHORIZATION_PHRASE_DOES_NOT_MATCH",
    }


# ---------------------------------------------------------------------------
# Read-only DB connection
# ---------------------------------------------------------------------------
def _ro_conn(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _rw_conn(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Phase 0: snapshot DB before migration
# ---------------------------------------------------------------------------
def snapshot_db(path: Path = DB_PATH, label: str = "before") -> dict:
    print(f"[P129B] Snapshotting DB ({label})...")
    conn = _ro_conn(path)
    cur = conn.cursor()

    replay_rows = cur.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    cols = [r[1] for r in cur.execute(
        "PRAGMA table_info(strategy_prediction_replays)"
    ).fetchall()]
    has_bet_index = "bet_index" in cols

    ddl_row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
    ).fetchone()
    ddl = ddl_row[0] if ddl_row else ""

    indexes = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='strategy_prediction_replays'"
    ).fetchall()]

    conn.close()
    return {
        "replay_rows": replay_rows,
        "columns": cols,
        "has_bet_index_column": has_bet_index,
        "ddl": ddl,
        "indexes": indexes,
        "label": label,
    }


# ---------------------------------------------------------------------------
# Phase 1: read upstream artifacts
# ---------------------------------------------------------------------------
def read_upstream_artifacts() -> dict:
    print("[P129B] Reading upstream P129A and P129 artifacts...")
    assert P129A_ARTIFACT.exists(), f"P129A artifact not found: {P129A_ARTIFACT}"
    assert P129_ARTIFACT.exists(),  f"P129 artifact not found: {P129_ARTIFACT}"

    with open(P129A_ARTIFACT) as f:
        p129a = json.load(f)
    with open(P129_ARTIFACT) as f:
        p129  = json.load(f)

    p129a_cls   = p129a.get("classification", "")
    p129_cls    = p129.get("classification", "")
    rn_required = p129.get("pre_migration_duplicate_audit", {}).get(
        "p128_copy_sql_refinement_required", False
    )

    return {
        "p129a_classification":   p129a_cls,
        "p129a_classification_ok": p129a_cls == "P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION",
        "p129_classification":    p129_cls,
        "p129_classification_ok": p129_cls == "P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY",
        "row_number_copy_sql_required": rn_required,
        "duplicate_groups_found": p129.get("pre_migration_duplicate_audit", {}).get(
            "duplicate_groups_count", 0
        ),
        "extra_rows_from_old_runs": p129.get("pre_migration_duplicate_audit", {}).get(
            "extra_rows_count", 0
        ),
        "all_ok": (
            p129a_cls == "P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION"
            and p129_cls == "P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY"
            and rn_required
        ),
    }


# ---------------------------------------------------------------------------
# Phase 2: create and verify backup
# ---------------------------------------------------------------------------
def create_backup() -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"lottery_v2.db.p129b_backup_{ts}.db"

    print(f"[P129B] Creating backup: {backup_path}")
    shutil.copy2(str(DB_PATH), str(backup_path))

    # Verify backup
    conn = sqlite3.connect(str(backup_path))
    conn.execute("PRAGMA query_only = ON")
    count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    conn.close()

    ok = count == EXPECTED_ROWS_BEFORE
    return {
        "backup_path": str(backup_path),
        "backup_created": True,
        "backup_row_count": count,
        "backup_verification": "PASS" if ok else f"FAIL: count={count}",
        "backup_ok": ok,
    }


# ---------------------------------------------------------------------------
# Migration SQL fragments
# ---------------------------------------------------------------------------
_NEW_TABLE_DDL = """\
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
)"""

# Corrected COPY — ROW_NUMBER() handles 120 duplicate groups from old replay runs.
# Naive '1 AS bet_index' fails because P94 + old-run rows share same (strategy, draw).
_CORRECTED_COPY_SQL = """\
INSERT INTO strategy_prediction_replays_new
SELECT id, lottery_type, target_draw, target_date, strategy_id,
       strategy_name, strategy_version, history_cutoff_draw, replay_status,
       reject_reason, predicted_numbers, predicted_special, actual_numbers,
       actual_special, hit_numbers, hit_count, special_hit, replay_run_id,
       generated_at, truth_level, controlled_apply_id, source, provenance_hash,
       provenance_source, dry_run, prediction_cutoff_date, prediction_generated_at,
       ROW_NUMBER() OVER (
         PARTITION BY lottery_type, target_draw, strategy_id
         ORDER BY id
       ) AS bet_index
FROM strategy_prediction_replays"""

_INDEXES = [
    ("idx_spr_lottery",             "CREATE INDEX idx_spr_lottery ON strategy_prediction_replays(lottery_type)"),
    ("idx_spr_strategy",            "CREATE INDEX idx_spr_strategy ON strategy_prediction_replays(strategy_id)"),
    ("idx_spr_draw",                "CREATE INDEX idx_spr_draw ON strategy_prediction_replays(target_draw)"),
    ("idx_spr_status",              "CREATE INDEX idx_spr_status ON strategy_prediction_replays(replay_status)"),
    ("idx_spr_run",                 "CREATE INDEX idx_spr_run ON strategy_prediction_replays(replay_run_id)"),
    ("idx_spr_hit",                 "CREATE INDEX idx_spr_hit ON strategy_prediction_replays(hit_count)"),
    ("idx_spr_controlled_apply_id", "CREATE INDEX idx_spr_controlled_apply_id ON strategy_prediction_replays(controlled_apply_id)"),
    ("idx_spr_truth_level",         "CREATE INDEX idx_spr_truth_level ON strategy_prediction_replays(truth_level)"),
    ("idx_spr_bet_index",           "CREATE INDEX idx_spr_bet_index ON strategy_prediction_replays(bet_index)"),
]


# ---------------------------------------------------------------------------
# Phase 3: execute migration
# ---------------------------------------------------------------------------
def execute_migration() -> dict:
    print("[P129B] Phase 3: executing corrected 18-step migration on production DB...")
    conn    = _rw_conn(DB_PATH)
    log     = []
    error   = None
    success = False

    def _step(n: int, sql: str, purpose: str):
        log.append({"step": n, "sql": sql[:200], "purpose": purpose, "status": "PENDING"})
        try:
            conn.execute(sql)
            log[-1]["status"] = "OK"
            print(f"  [step {n:2d}] OK — {purpose}")
        except Exception as exc:
            log[-1]["status"] = f"ERROR: {exc}"
            raise

    try:
        _step(1,  "PRAGMA foreign_keys = OFF",              "Disable FK checks during table recreation")
        _step(2,  "BEGIN TRANSACTION",                      "Atomic migration")
        _step(3,  _NEW_TABLE_DDL,                           "Create new table with bet_index + updated UNIQUE constraint")
        _step(4,  _CORRECTED_COPY_SQL,                      "Copy all rows with ROW_NUMBER() bet_index (P129 corrected SQL)")
        _step(5,  "DROP TABLE strategy_prediction_replays", "Remove old table")
        _step(6,  "ALTER TABLE strategy_prediction_replays_new RENAME TO strategy_prediction_replays",
              "Rename new table to production name")
        for i, (name, sql) in enumerate(_INDEXES, start=7):
            _step(i, sql, f"Recreate index {name}")
        _step(16, "COMMIT",                                 "Commit atomic migration")
        _step(17, "PRAGMA foreign_keys = ON",               "Re-enable FK constraints")

        # Step 18 — post-migration row count invariant
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        status18 = "OK" if count == EXPECTED_ROWS_AFTER else f"FAIL: count={count}"
        log.append({
            "step": 18,
            "sql": "SELECT COUNT(*) FROM strategy_prediction_replays",
            "purpose": f"Post-migration invariant — must equal {EXPECTED_ROWS_AFTER}",
            "status": status18,
        })
        print(f"  [step 18] {status18} — post-migration count = {count}")
        success = count == EXPECTED_ROWS_AFTER

    except Exception as exc:
        error = str(exc)
        success = False
        try:
            conn.execute("ROLLBACK")
            print(f"  [ROLLBACK] issued after error: {exc}")
        except Exception:
            pass
        print(f"[P129B] MIGRATION FAILED: {exc}", file=sys.stderr)

    conn.close()
    return {
        "migration_executed": True,
        "migration_ok": success,
        "steps_log": log,
        "steps_count": len(log),
        "error": error,
        "corrected_copy_sql_used": True,
        "row_number_copy_sql_used": True,
        "corrected_copy_sql_text": _CORRECTED_COPY_SQL.strip(),
    }


# ---------------------------------------------------------------------------
# Phase 4: post-migration validation
# ---------------------------------------------------------------------------
def validate_post_migration() -> dict:
    print("[P129B] Phase 4: post-migration validation...")
    conn = _rw_conn(DB_PATH)

    # Schema check
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(strategy_prediction_replays)"
    ).fetchall()]
    has_bet_index = "bet_index" in cols

    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
    ).fetchone()[0]
    has_new_unique = "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl

    indexes = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='strategy_prediction_replays'"
    ).fetchall()]
    has_bet_index_idx = "idx_spr_bet_index" in indexes

    # Row counts
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    bi1   = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index = 1").fetchone()[0]
    bi_gt1 = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index > 1").fetchone()[0]
    bi_invalid = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index IS NULL OR bet_index < 1"
    ).fetchone()[0]

    # bet_index distribution detail
    dist_rows = conn.execute(
        "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays GROUP BY bet_index ORDER BY bet_index"
    ).fetchall()
    distribution = [{"bet_index": r[0], "count": r[1]} for r in dist_rows]

    # Duplicate audit after migration
    dup_post = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT lottery_type, target_draw, strategy_id, COUNT(*) AS cnt
            FROM strategy_prediction_replays
            GROUP BY lottery_type, target_draw, strategy_id
            HAVING cnt > 1
        )
    """).fetchone()[0]

    # UNIQUE constraint validation
    unique_ok = None
    try:
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status, bet_index) VALUES (?,?,?,?,?)",
            ("P129B_TEST", "P129B_DRAW_001", "p129b_test_strategy", "PENDING", 1)
        )
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status, bet_index) VALUES (?,?,?,?,?)",
            ("P129B_TEST", "P129B_DRAW_001", "p129b_test_strategy", "PENDING", 1)
        )
        conn.execute("ROLLBACK")
        unique_ok = False
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        unique_ok = True

    # Different bet_index should be accepted
    multi_bet_ok = None
    try:
        conn.execute("BEGIN")
        for bi in (1, 2, 3):
            conn.execute(
                "INSERT INTO strategy_prediction_replays "
                "(lottery_type, target_draw, strategy_id, replay_status, bet_index) VALUES (?,?,?,?,?)",
                ("P129B_TEST", "P129B_DRAW_002", "p129b_test_strategy2", "PENDING", bi)
            )
        conn.execute("ROLLBACK")
        multi_bet_ok = True
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        multi_bet_ok = False

    conn.close()

    row_preservation_ok = total == EXPECTED_ROWS_AFTER
    bi_distribution_ok  = (bi_invalid == 0 and bi1 == EXPECTED_BET_INDEX_1
                           and bi_gt1 == EXPECTED_BET_INDEX_GT1)

    return {
        "schema_after": {
            "columns": cols,
            "has_bet_index_column": has_bet_index,
            "has_new_unique_constraint": has_new_unique,
            "full_ddl": ddl,
            "ddl_excerpt": ddl[:500],
            "indexes": indexes,
            "has_bet_index_index": has_bet_index_idx,
        },
        "bet_index_distribution": {
            "total_rows": total,
            "rows_with_bet_index_1": bi1,
            "rows_with_bet_index_gt1": bi_gt1,
            "rows_with_invalid_bet_index": bi_invalid,
            "distribution": distribution,
            "expected_bet_index_1": EXPECTED_BET_INDEX_1,
            "expected_bet_index_gt1": EXPECTED_BET_INDEX_GT1,
            "distribution_matches_expectation": bi_distribution_ok,
            "all_rows_valid": bi_invalid == 0,
        },
        "replay_row_preservation_check": {
            "expected_rows": EXPECTED_ROWS_AFTER,
            "actual_rows": total,
            "rows_preserved": row_preservation_ok,
            "check_ok": row_preservation_ok,
        },
        "unique_constraint_validation": {
            "duplicate_same_bet_index_rejected": unique_ok,
            "multi_bet_different_index_allowed": multi_bet_ok,
            "constraint_works_as_expected": (unique_ok is True and multi_bet_ok is True),
            "validation_ok": (unique_ok is True and multi_bet_ok is True),
        },
        "duplicate_audit_after_migration": {
            "groups_with_multiple_rows": dup_post,
            "note": (
                f"{dup_post} (strategy, draw) groups still have multiple rows, "
                "now distinguished by bet_index — data preserved, no rows lost."
            ) if dup_post > 0 else "No unexpected duplicates.",
        },
        "all_validation_ok": (
            has_bet_index
            and has_new_unique
            and row_preservation_ok
            and bi_invalid == 0
            and unique_ok is True
            and multi_bet_ok is True
        ),
    }


# ---------------------------------------------------------------------------
# Build output JSON
# ---------------------------------------------------------------------------
def build_output_json(
    auth:         dict,
    upstream:     dict,
    snap_before:  dict,
    backup:       dict,
    migration:    dict,
    validation:   dict,
    snap_after:   dict,
) -> dict:
    return {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "authorization": auth,

        "db_snapshot_before": {
            "replay_rows": snap_before["replay_rows"],
            "has_bet_index_column": snap_before["has_bet_index_column"],
            "columns_count": len(snap_before["columns"]),
            "indexes": snap_before["indexes"],
        },

        "backup": backup,

        "migration_steps": migration["steps_log"],
        "migration_ok": migration["migration_ok"],
        "migration_steps_count": migration["steps_count"],
        "migration_error": migration["error"],
        "corrected_copy_sql_used": migration["corrected_copy_sql_used"],
        "row_number_copy_sql_used": migration["row_number_copy_sql_used"],
        "corrected_copy_sql_text": migration["corrected_copy_sql_text"],

        "schema_before": {
            "has_bet_index_column": snap_before["has_bet_index_column"],
            "current_unique_constraint": (
                "UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)"
                if "replay_run_id" in snap_before["ddl"] else "UNKNOWN"
            ),
            "columns_count": len(snap_before["columns"]),
        },
        "schema_after": validation["schema_after"],

        "db_snapshot_after": {
            "replay_rows": snap_after["replay_rows"],
            "has_bet_index_column": snap_after["has_bet_index_column"],
            "columns_count": len(snap_after["columns"]),
            "indexes": snap_after["indexes"],
        },

        "bet_index_distribution": validation["bet_index_distribution"],
        "replay_row_preservation_check": validation["replay_row_preservation_check"],
        "unique_constraint_validation": validation["unique_constraint_validation"],
        "duplicate_audit": validation["duplicate_audit_after_migration"],

        "p126_apply_status": {
            "status": "BLOCKED_UNTIL_PER_STRATEGY_AUTHORIZATION",
            "reason": (
                "Schema migration completed. P126 apply requires 5 individual "
                "per-strategy authorization phrases from Kelvin before it can execute. "
                "Each strategy's apply must be separately authorized."
            ),
            "estimated_rows_from_p126": 18000,
            "estimated_total_after_apply": 72462,
            "apply_executed": False,
            "required_per_strategy_phrases": [
                "YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>",
                "YES authorize controlled_apply for daily539_f4cold_5bet because <reason>",
                "YES authorize controlled_apply for daily539_f4cold_3bet because <reason>",
                "YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>",
                "YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>",
            ],
        },

        "blocked_or_excluded": [
            {"item": "p126_apply",                     "reason": "Not executed — requires per-strategy authorization (5 phrases)"},
            {"item": "4_STAR",                         "reason": "Explicitly excluded from all Tier-B multi-bet work per governance"},
            {"item": "P108",                           "reason": "P108 execution blocked — trigger not met"},
            {"item": "P117",                           "reason": "P117 execution blocked — trigger not met"},
            {"item": "P118",                           "reason": "P118 execution blocked — authorization phrase absent"},
            {"item": "rejected_strategies",            "reason": "No rejected strategies promoted or included"},
            {"item": "scheduler_cron_launchd",         "reason": "No scheduler installation in P129B"},
            {"item": "lifecycle_champion_registry",    "reason": "No strategy promotion / lifecycle / champion / registry mutation"},
        ],

        "rollback_reference": {
            "backup_path": backup["backup_path"],
            "rollback_command": f"cp '{backup['backup_path']}' '{DB_PATH}'",
            "note": (
                "If migration outcome is unsatisfactory, restore from backup above. "
                "Verify row count after restore: "
                "sqlite3 lottery_api/data/lottery_v2.db 'SELECT COUNT(*) FROM strategy_prediction_replays;' "
                f"must return {EXPECTED_ROWS_AFTER}."
            ),
        },

        "p129a_source_summary": {
            "artifact": str(P129A_ARTIFACT),
            "classification": upstream["p129a_classification"],
            "classification_ok": upstream["p129a_classification_ok"],
        },
        "p129_source_summary": {
            "artifact": str(P129_ARTIFACT),
            "classification": upstream["p129_classification"],
            "classification_ok": upstream["p129_classification_ok"],
            "row_number_copy_sql_required": upstream["row_number_copy_sql_required"],
            "duplicate_groups_found": upstream["duplicate_groups_found"],
            "extra_rows_from_old_runs": upstream["extra_rows_from_old_runs"],
        },

        "summary": {
            "task_id": TASK_ID,
            "classification": CLASSIFICATION,
            "authorization_present": auth["authorization_present"],
            "migration_executed": migration["migration_executed"],
            "migration_ok": migration["migration_ok"],
            "backup_ok": backup["backup_ok"],
            "rows_before": snap_before["replay_rows"],
            "rows_after": snap_after["replay_rows"],
            "bet_index_column_present": validation["schema_after"]["has_bet_index_column"],
            "unique_constraint_ok": validation["unique_constraint_validation"]["validation_ok"],
            "all_validation_ok": validation["all_validation_ok"],
            "p126_apply_executed": False,
            "next_step": (
                "Schema migration complete. "
                "To apply P126 +18000 rows, provide 5 per-strategy authorization phrases in "
                "a new P126A apply gate task."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Build Markdown
# ---------------------------------------------------------------------------
def build_markdown(data: dict) -> str:
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    auth = data["authorization"]
    bk   = data["backup"]
    mig  = data
    val  = data
    dist = data["bet_index_distribution"]
    rr   = data["replay_row_preservation_check"]
    uc   = data["unique_constraint_validation"]
    sa   = data["schema_after"]

    def _tick(v): return "✓ PASS" if v else "✗ FAIL"

    return f"""# P129B — Production bet_index Schema Migration Execution

**Task ID:** P129B
**Classification:** `{data["classification"]}`
**Generated:** {now}

---

## 1. Executive Summary

P129B executed the corrected 18-step SQLite table-recreation migration on the **production database**.
The migration used ROW_NUMBER() in the COPY step (corrected by P129 rehearsal) to handle 120
duplicate (strategy, draw) groups safely.

| Check | Result |
|---|---|
| Authorization phrase present | {_tick(auth["authorization_present"])} |
| Backup created and verified | {_tick(bk["backup_ok"])} |
| 18-step migration completed | {_tick(data["migration_ok"])} |
| Corrected ROW_NUMBER() COPY used | {_tick(data["corrected_copy_sql_used"])} |
| bet_index column added | {_tick(sa["has_bet_index_column"])} |
| New UNIQUE constraint active | {_tick(sa["has_new_unique_constraint"])} |
| All 54462 rows preserved | {_tick(rr["check_ok"])} |
| bet_index distribution correct | {_tick(dist["distribution_matches_expectation"])} |
| No invalid bet_index rows | {_tick(dist["all_rows_valid"])} |
| UNIQUE constraint rejects duplicates | {_tick(uc["duplicate_same_bet_index_rejected"])} |
| Multi-bet (bet_index 1,2,3) allowed | {_tick(uc["multi_bet_different_index_allowed"])} |
| P126 apply executed | ✗ BLOCKED (not executed — requires per-strategy phrases) |

---

## 2. Authorization Confirmation

| Field | Value |
|---|---|
| Exact required phrase | `{auth["exact_required_phrase"]}` |
| Authorization present | `{auth["authorization_present"]}` |
| Migration allowed | `{auth["migration_allowed"]}` |
| Authorization text observed | `{auth["authorization_text_observed"]}` |
| Reason | `{auth["reason_text"]}` |

---

## 3. P129A / P129 Rehearsal Recap

- **P129A:** `{data["p129a_source_summary"]["classification"]}` — gate confirmed rehearsal valid, migration blocked pending authorization
- **P129:** `{data["p129_source_summary"]["classification"]}` — 18-step migration rehearsed on temp DB, all 54462 rows preserved
- **Key finding from P129:** 120 duplicate (strategy, draw) groups require ROW_NUMBER() COPY SQL
- **ROW_NUMBER() required:** `{data["p129_source_summary"]["row_number_copy_sql_required"]}`

---

## 4. Backup Creation and Verification

| Field | Value |
|---|---|
| Backup path | `{bk["backup_path"]}` |
| Backup created | `{bk["backup_created"]}` |
| Backup row count | `{bk["backup_row_count"]}` |
| Backup verification | `{bk["backup_verification"]}` |

**Rollback command (if needed):**
```bash
cp '{bk["backup_path"]}' '{DB_PATH}'
```

---

## 5. Corrected ROW_NUMBER() Migration SQL Summary

P128 original step 4 (WOULD FAIL for 120 duplicate groups):
```sql
-- NAIVE — fails with UNIQUE constraint for duplicate (strategy, draw) groups
INSERT INTO strategy_prediction_replays_new
SELECT ..., 1 AS bet_index FROM strategy_prediction_replays
```

**Corrected step 4 (used in P129B production migration):**
```sql
{data["corrected_copy_sql_text"]}
```

This assigns `bet_index = 1` to the first (lowest id) row per (strategy, draw) group,
and `bet_index = 2, 3, ...` to subsequent rows. All 54462 rows are preserved.

---

## 6. Schema Before / After

### Before Migration
- `bet_index` column: **NOT present**
- UNIQUE constraint: `UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)`
- Columns: {data["db_snapshot_before"]["columns_count"]}

### After Migration
- `bet_index` column: **PRESENT** (`INTEGER NOT NULL DEFAULT 1`)
- UNIQUE constraint: `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`
- `replay_run_id` removed from UNIQUE (still a column, just not in the constraint)
- Columns: {len(sa["columns"])}
- New index: `idx_spr_bet_index ON strategy_prediction_replays(bet_index)`
- All indexes: {len(sa["indexes"])}

---

## 7. bet_index Distribution

| bet_index | Rows | Notes |
|---|---|---|
"""     + "\n".join(
        f"| {r['bet_index']} | {r['count']:,} | {'Primary/single-bet rows' if r['bet_index'] == 1 else 'Old multi-run duplicate rows'} |"
        for r in dist["distribution"]
    ) + f"""

| Metric | Expected | Actual | Status |
|---|---|---|---|
| Total rows | {dist["expected_bet_index_1"] + dist["expected_bet_index_gt1"]:,} | {dist["total_rows"]:,} | {_tick(dist["total_rows"] == EXPECTED_ROWS_AFTER)} |
| Rows bet_index = 1 | {dist["expected_bet_index_1"]:,} | {dist["rows_with_bet_index_1"]:,} | {_tick(dist["rows_with_bet_index_1"] == dist["expected_bet_index_1"])} |
| Rows bet_index > 1 | {dist["expected_bet_index_gt1"]:,} | {dist["rows_with_bet_index_gt1"]:,} | {_tick(dist["rows_with_bet_index_gt1"] == dist["expected_bet_index_gt1"])} |
| Invalid (NULL / < 1) | 0 | {dist["rows_with_invalid_bet_index"]:,} | {_tick(dist["rows_with_invalid_bet_index"] == 0)} |

---

## 8. Replay Row Preservation Result

| Metric | Value |
|---|---|
| Expected rows | {rr["expected_rows"]:,} |
| Actual rows after migration | {rr["actual_rows"]:,} |
| Rows preserved | {_tick(rr["rows_preserved"])} |

**Result:** `{_tick(rr["check_ok"])}`

---

## 9. Unique Constraint Validation

| Test | Result |
|---|---|
| Insert duplicate (strategy, draw, bet_index=1) × 2 → rejected | {_tick(uc["duplicate_same_bet_index_rejected"])} |
| Insert (strategy, draw, bet_index=1,2,3) → all accepted | {_tick(uc["multi_bet_different_index_allowed"])} |
| Constraint works as expected | {_tick(uc["constraint_works_as_expected"])} |

---

## 10. P126 Apply Remains Blocked

Schema migration is complete. However, P126 apply is **BLOCKED** pending 5 individual
per-strategy authorization phrases from Kelvin:

```
YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>
YES authorize controlled_apply for daily539_f4cold_5bet because <reason>
YES authorize controlled_apply for daily539_f4cold_3bet because <reason>
YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>
YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>
```

If all 5 apply phrases are provided, P126 will add an estimated **+18,000 rows**
(total 72,462). Each strategy must be authorized separately in a new P126A gate task.

---

## 11. Rollback Reference / Backup Path

**Backup:** `{bk["backup_path"]}`

To restore production DB to pre-migration state:
```bash
cp '{bk["backup_path"]}' '{DB_PATH}'
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"
# must return 54462
```

---

## 12. Explicit Non-Actions

| Item | Status |
|---|---|
| P126 controlled apply | NOT EXECUTED — requires per-strategy phrases |
| 4_STAR work | BLOCKED |
| P108 execution | BLOCKED |
| P117 execution | BLOCKED |
| P118 execution | BLOCKED |
| Scheduler / cron / launchd install | NOT DONE |
| Strategy promotion / lifecycle / registry mutation | NOT DONE |

---

## 13. Final Classification

```
P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED
```

bet_index schema migration applied to production DB.
All 54462 rows preserved. UNIQUE(lottery_type, target_draw, strategy_id, bet_index) active.
Next step: provide per-strategy P126 authorization phrases to gate P126A apply.
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P129B: Execute production bet_index migration")
    parser.add_argument("--authorization", type=str, default=None,
                        help="Kelvin authorization phrase")
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).isoformat()
    print(f"[P129B] Starting production migration execution — {ts}")

    # ── Step 0: validate authorization FIRST ─────────────────────────────
    auth = validate_authorization(args.authorization)
    if not auth["migration_allowed"]:
        print(f"[P129B] STOP — Authorization not present or invalid.", file=sys.stderr)
        print(f"[P129B] stop_reason: {auth['stop_reason']}", file=sys.stderr)
        print(f"[P129B] Required phrase: {auth['exact_required_phrase']}", file=sys.stderr)
        print(f"[P129B] Migration NOT executed. Production DB unchanged.", file=sys.stderr)
        return 1
    print(f"[P129B] Authorization confirmed: {auth['reason_text']}")

    # ── Step 1: read upstream artifacts ──────────────────────────────────
    upstream = read_upstream_artifacts()
    if not upstream["all_ok"]:
        print(f"[P129B] ERROR: Upstream artifact checks failed: {upstream}", file=sys.stderr)
        return 1
    print(f"[P129B] P129A: {upstream['p129a_classification']}")
    print(f"[P129B] P129:  {upstream['p129_classification']}")
    print(f"[P129B] ROW_NUMBER() required: {upstream['row_number_copy_sql_required']}")

    # ── Step 2: snapshot before ───────────────────────────────────────────
    snap_before = snapshot_db(label="before")
    if snap_before["replay_rows"] != EXPECTED_ROWS_BEFORE:
        print(f"[P129B] ERROR: rows before={snap_before['replay_rows']} expected={EXPECTED_ROWS_BEFORE}",
              file=sys.stderr)
        return 1
    if snap_before["has_bet_index_column"]:
        print("[P129B] ERROR: bet_index already exists in production DB — migration may have already run",
              file=sys.stderr)
        return 1
    print(f"[P129B] DB before: {snap_before['replay_rows']} rows, bet_index={snap_before['has_bet_index_column']}")

    # ── Step 3: backup ────────────────────────────────────────────────────
    backup = create_backup()
    if not backup["backup_ok"]:
        print(f"[P129B] ERROR: Backup verification failed: {backup}", file=sys.stderr)
        return 1
    print(f"[P129B] Backup: {backup['backup_path']} ({backup['backup_row_count']} rows) — {backup['backup_verification']}")

    # ── Step 4: execute migration ─────────────────────────────────────────
    migration = execute_migration()
    if not migration["migration_ok"]:
        print(f"[P129B] ERROR: Migration failed. Restore from: {backup['backup_path']}", file=sys.stderr)
        return 1
    print(f"[P129B] Migration: {migration['steps_count']} steps — OK")

    # ── Step 5: post-migration validation ─────────────────────────────────
    validation = validate_post_migration()
    if not validation["all_validation_ok"]:
        print(f"[P129B] ERROR: Post-migration validation failed: {validation}", file=sys.stderr)
        print(f"[P129B] Restore from: {backup['backup_path']}", file=sys.stderr)
        return 1
    print("[P129B] Post-migration validation — OK")
    dist = validation["bet_index_distribution"]
    print(f"[P129B] bet_index=1: {dist['rows_with_bet_index_1']}, "
          f"bet_index>1: {dist['rows_with_bet_index_gt1']}, "
          f"invalid: {dist['rows_with_invalid_bet_index']}")

    # ── Step 6: snapshot after ────────────────────────────────────────────
    snap_after = snapshot_db(label="after")
    print(f"[P129B] DB after: {snap_after['replay_rows']} rows, bet_index={snap_after['has_bet_index_column']}")

    # ── Step 7: write outputs ─────────────────────────────────────────────
    data = build_output_json(auth, upstream, snap_before, backup, migration, validation, snap_after)
    md   = build_markdown(data)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")

    print(f"[P129B] JSON written: {OUT_JSON}")
    print(f"[P129B] MD  written: {OUT_MD}")
    print(f"[P129B] classification = {data['classification']}")
    print(f"[P129B] DONE — {CLASSIFICATION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
