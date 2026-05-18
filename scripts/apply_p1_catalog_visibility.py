#!/usr/bin/env python3
"""
apply_p1_catalog_visibility.py
================================
P1 Catalog Visibility — Controlled apply script for catalog expansion.

MISSION: Register artifact-level strategies into the DB strategy_catalog_p1 table
(or a suitable P1 extension table) for catalog visibility. Does NOT touch
existing replay rows, prediction_runs, prediction_items, or strategy_replay_runs.

SAFETY:
  - Default mode is DRY-RUN ONLY
  - `--apply` required for any DB writes
  - DB backup automatically created before apply
  - Idempotent: safe to run multiple times
  - Never deletes existing rows
  - Never marks artifact-only as ONLINE
  - Never generates replay rows
  - All new entries without replay rows → NO_DATA visibility state

Usage:
    python3 scripts/apply_p1_catalog_visibility.py --dry-run   # (default)
    python3 scripts/apply_p1_catalog_visibility.py --apply     # writes to DB

Outputs:
    outputs/replay/p1_catalog_visibility_apply_dry_run_20260518.json
    outputs/replay/p1_catalog_visibility_apply_result_20260518.json  (if --apply)
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BACKUP_DIR = PROJECT_ROOT / "lottery_api" / "data" / "backups"
PLAN_PATH = PROJECT_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260518.json"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "replay"
DATE_SUFFIX = "20260518"

# P1 catalog table name — separate from existing tables to avoid conflicts
P1_TABLE = "strategy_catalog_p1"

# ─── Stop conditions ──────────────────────────────────────────────────────────

STOP_CONDITIONS = [
    "planner_cannot_distinguish_registry",
    "too_many_unstable_ids",
    "lifecycle_guessing_online",
    "apply_requires_delete",
    "api_requires_fabricating_rows",
    "db_backup_failed",
    "drift_guard_failed",
    "api_contract_tests_failed",
]


def check_stop_conditions(plan: dict) -> list[str]:
    """
    Check all STOP CONDITIONS before applying.
    Returns list of triggered conditions (empty if safe to proceed).
    """
    triggered = []

    entries = plan.get("entries", [])
    if not entries:
        triggered.append("planner_cannot_distinguish_registry: no entries in plan")
        return triggered

    # Check for unstable IDs (>20% of artifact candidates)
    artifact_candidates = [e for e in entries if e["catalog_visibility_state"] == "ARTIFACT_CANDIDATE"]
    if artifact_candidates:
        # An ID is "stable" if it's not UNKNOWN lifecycle or doesn't look like a generic name
        unstable = [e for e in artifact_candidates
                    if e["lifecycle_state"] == "UNKNOWN"
                    or len(e["strategy_id"]) < 3]
        ratio = len(unstable) / len(artifact_candidates)
        if ratio > 0.20:
            triggered.append(
                f"too_many_unstable_ids: {len(unstable)}/{len(artifact_candidates)} "
                f"({ratio:.1%}) artifact entries lack stable strategy_id"
            )

    # Check that no lifecycle mapping requires guessing ONLINE
    online_artifacts = [e for e in artifact_candidates if e["lifecycle_state"] == "ONLINE"]
    if online_artifacts:
        triggered.append(
            f"lifecycle_guessing_online: {len(online_artifacts)} artifact entries "
            f"would be marked ONLINE — must not guess lifecycle=ONLINE"
        )

    # Check safety flags
    safety = plan.get("safety", {})
    if safety.get("db_write", True):
        triggered.append("safety_flag_violated: plan has db_write=True (must be False for dry-run)")
    if safety.get("replay_row_generation", True):
        triggered.append("safety_flag_violated: plan has replay_row_generation=True")

    return triggered


# ─── DB helpers ───────────────────────────────────────────────────────────────

DDL_P1_CATALOG = f"""
CREATE TABLE IF NOT EXISTS {P1_TABLE} (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id             TEXT NOT NULL UNIQUE,
    display_name            TEXT NOT NULL,
    lottery_type            TEXT NOT NULL,
    lifecycle_state         TEXT NOT NULL,
    catalog_visibility_state TEXT NOT NULL,
    source_paths_json       TEXT NOT NULL DEFAULT '[]',
    artifact_source_type    TEXT NOT NULL DEFAULT 'UNKNOWN',
    has_replay_rows         INTEGER NOT NULL DEFAULT 0,
    has_historical_predictions INTEGER NOT NULL DEFAULT 0,
    no_data_reason          TEXT,
    provenance_hash         TEXT,
    created_by_phase        TEXT NOT NULL DEFAULT 'P1_CATALOG_VISIBILITY_20260518',
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

DDL_P1_CATALOG_INDEX = f"""
CREATE INDEX IF NOT EXISTS idx_{P1_TABLE}_lottery_type
ON {P1_TABLE}(lottery_type)
"""

DDL_P1_CATALOG_LIFECYCLE_INDEX = f"""
CREATE INDEX IF NOT EXISTS idx_{P1_TABLE}_lifecycle_state
ON {P1_TABLE}(lifecycle_state)
"""


def ensure_table(con: sqlite3.Connection):
    """Create the P1 catalog table if it doesn't exist."""
    con.execute(DDL_P1_CATALOG)
    con.execute(DDL_P1_CATALOG_INDEX)
    con.execute(DDL_P1_CATALOG_LIFECYCLE_INDEX)
    con.commit()


def get_existing_p1_ids(con: sqlite3.Connection) -> set[str]:
    """Return set of strategy_ids already in the P1 catalog table."""
    try:
        rows = con.execute(f"SELECT strategy_id FROM {P1_TABLE}").fetchall()
        return {r[0] for r in rows}
    except sqlite3.OperationalError:
        return set()


def upsert_entry(con: sqlite3.Connection, entry: dict) -> str:
    """
    Insert or update a single catalog entry.
    Returns 'INSERTED' or 'SKIPPED' (already exists, idempotent).
    NEVER deletes existing rows.
    NEVER modifies replay rows or prediction rows.
    """
    existing = con.execute(
        f"SELECT id, lifecycle_state FROM {P1_TABLE} WHERE strategy_id = ?",
        (entry["strategy_id"],)
    ).fetchone()

    if existing:
        # Idempotent: row already exists, skip
        return "SKIPPED"

    # Safety check: new artifact-only entries must NOT be ONLINE
    if (entry["catalog_visibility_state"] == "ARTIFACT_CANDIDATE"
            and entry["lifecycle_state"] == "ONLINE"):
        return "BLOCKED_LIFECYCLE_CONFLICT"

    con.execute(
        f"""INSERT INTO {P1_TABLE}
            (strategy_id, display_name, lottery_type, lifecycle_state,
             catalog_visibility_state, source_paths_json, artifact_source_type,
             has_replay_rows, has_historical_predictions, no_data_reason,
             provenance_hash, created_by_phase)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry["strategy_id"],
            entry["display_name"],
            entry["lottery_type"],
            entry["lifecycle_state"],
            entry["catalog_visibility_state"],
            json.dumps(entry.get("source_paths", [])),
            entry.get("artifact_source_type", "UNKNOWN"),
            1 if entry.get("has_replay_rows") else 0,
            1 if entry.get("has_historical_predictions") else 0,
            entry.get("no_data_reason"),
            entry.get("provenance_hash"),
            entry.get("created_by_phase", "P1_CATALOG_VISIBILITY_20260518"),
        )
    )
    return "INSERTED"


# ─── Backup ───────────────────────────────────────────────────────────────────

def backup_db() -> Path:
    """
    Create a timestamped backup of the DB before any writes.
    Returns the backup path.
    Raises RuntimeError if backup fails.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    backup_path = BACKUP_DIR / f"lottery_v2_pre_p1_{ts}.db"
    try:
        shutil.copy2(str(DB_PATH), str(backup_path))
    except Exception as e:
        raise RuntimeError(f"DB backup FAILED: {e}") from e
    if not backup_path.exists() or backup_path.stat().st_size == 0:
        raise RuntimeError(f"DB backup produced empty file: {backup_path}")
    return backup_path


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(apply: bool = False) -> dict:
    """
    Main execution. If apply=False, dry-run only. If apply=True, writes to DB.
    Returns a report dict.
    """
    generated_at = datetime.datetime.utcnow().isoformat() + "Z"
    mode = "APPLY" if apply else "DRY_RUN"

    # 1. Load plan
    if not PLAN_PATH.exists():
        return {
            "status": "BLOCKED_NO_PLAN",
            "generated_at": generated_at,
            "mode": mode,
            "error": f"Plan not found: {PLAN_PATH}. Run p1_catalog_visibility_plan.py first.",
        }

    plan = json.loads(PLAN_PATH.read_text())
    entries = plan.get("entries", [])

    # 2. Check STOP CONDITIONS
    stop_triggered = check_stop_conditions(plan)
    if stop_triggered:
        return {
            "status": "BLOCKED_STOP_CONDITIONS",
            "generated_at": generated_at,
            "mode": mode,
            "stop_conditions": stop_triggered,
            "message": "STOP CONDITIONS triggered — no DB writes performed",
        }

    # ─── DRY-RUN analysis ─────────────────────────────────────────────────────

    dry_run_results = []
    insert_count = 0
    skip_count = 0
    block_count = 0

    for entry in entries:
        # Skip UNSUPPORTED
        if entry["catalog_visibility_state"] == "UNSUPPORTED":
            continue

        # In dry-run: simulate what would happen
        would_be = "WOULD_INSERT" if entry.get("is_new_entry") else "WOULD_SKIP_EXISTS"

        # Safety check
        if (entry["catalog_visibility_state"] == "ARTIFACT_CANDIDATE"
                and entry["lifecycle_state"] == "ONLINE"):
            would_be = "WOULD_BLOCK_LIFECYCLE_CONFLICT"
            block_count += 1
        elif entry.get("is_new_entry"):
            insert_count += 1
        else:
            skip_count += 1

        dry_run_results.append({
            "strategy_id": entry["strategy_id"],
            "catalog_visibility_state": entry["catalog_visibility_state"],
            "lifecycle_state": entry["lifecycle_state"],
            "lottery_type": entry["lottery_type"],
            "has_replay_rows": entry["has_replay_rows"],
            "dry_run_action": would_be,
        })

    report = {
        "status": "DRY_RUN_COMPLETE" if not apply else None,
        "generated_at": generated_at,
        "mode": mode,
        "plan_generated_at": plan.get("generated_at"),
        "runtime_canonical_before": plan.get("runtime_canonical_before", 18),
        "entries_in_plan": len(entries),
        "would_insert": insert_count,
        "would_skip": skip_count,
        "would_block": block_count,
        "dry_run_results": dry_run_results,
        "safety": {
            "db_write": apply,
            "draw_import": False,
            "replay_row_generation": False,
            "prediction_update": False,
            "strategy_execution": False,
        },
        "rollback_plan": (
            "All P1 entries written to a separate table (strategy_catalog_p1). "
            "To rollback: DROP TABLE strategy_catalog_p1. "
            "Existing tables (strategy_replay_runs, prediction_runs, prediction_items) "
            "are NOT modified by P1 apply."
        ),
    }

    if not apply:
        return report

    # ─── APPLY ────────────────────────────────────────────────────────────────

    # 3. Backup DB
    try:
        backup_path = backup_db()
        backup_str = str(backup_path)
    except RuntimeError as e:
        return {
            "status": "BLOCKED_BACKUP_FAILED",
            "generated_at": generated_at,
            "mode": mode,
            "error": str(e),
        }

    # 4. Apply writes
    applied_results = []
    inserted = 0
    skipped = 0
    blocked = 0

    con = sqlite3.connect(str(DB_PATH))
    try:
        ensure_table(con)

        for entry in entries:
            if entry["catalog_visibility_state"] == "UNSUPPORTED":
                continue
            result = upsert_entry(con, entry)
            applied_results.append({
                "strategy_id": entry["strategy_id"],
                "catalog_visibility_state": entry["catalog_visibility_state"],
                "lifecycle_state": entry["lifecycle_state"],
                "lottery_type": entry["lottery_type"],
                "result": result,
            })
            if result == "INSERTED":
                inserted += 1
            elif result == "SKIPPED":
                skipped += 1
            else:
                blocked += 1

        con.commit()
    except Exception as e:
        con.rollback()
        return {
            "status": "APPLY_FAILED",
            "generated_at": generated_at,
            "mode": mode,
            "backup_path": backup_str,
            "error": str(e),
        }
    finally:
        con.close()

    # 5. Verify idempotency: run again and all should be SKIPPED
    con2 = sqlite3.connect(str(DB_PATH))
    try:
        idempotency_check = []
        for entry in entries:
            if entry["catalog_visibility_state"] == "UNSUPPORTED":
                continue
            result2 = "WOULD_SKIP" if con2.execute(
                f"SELECT 1 FROM {P1_TABLE} WHERE strategy_id=?",
                (entry["strategy_id"],)
            ).fetchone() else "MISSING_AFTER_APPLY"
            idempotency_check.append({
                "strategy_id": entry["strategy_id"],
                "idempotency_result": result2,
            })
        idempotency_pass = all(r["idempotency_result"] == "WOULD_SKIP" for r in idempotency_check)
    finally:
        con2.close()

    report.update({
        "status": "APPLY_COMPLETE",
        "backup_path": backup_str,
        "inserted": inserted,
        "skipped": skipped,
        "blocked": blocked,
        "idempotency_pass": idempotency_pass,
        "applied_results": applied_results,
    })
    return report


def main():
    parser = argparse.ArgumentParser(description="P1 Catalog Visibility Apply Script")
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Write to DB (default: dry-run only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Explicit dry-run (default behavior)",
    )
    args = parser.parse_args()

    apply = args.apply
    mode = "APPLY" if apply else "DRY_RUN"

    print(f"P1 Catalog Visibility Apply — Mode: {mode}")
    print(f"DB: {DB_PATH}")
    print(f"Plan: {PLAN_PATH}")
    print()

    if apply:
        print("!!! APPLY MODE: DB writes ENABLED !!!")
        print(f"!!! Backup will be created in: {BACKUP_DIR} !!!")
        print()

    report = run(apply=apply)

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if apply and report.get("status") == "APPLY_COMPLETE":
        out_path = OUTPUT_DIR / f"p1_catalog_visibility_apply_result_{DATE_SUFFIX}.json"
    else:
        out_path = OUTPUT_DIR / f"p1_catalog_visibility_apply_dry_run_{DATE_SUFFIX}.json"

    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Report written: {out_path}")
    print()

    # Summary
    print(f"Status: {report.get('status')}")
    if "stop_conditions" in report:
        print("STOP CONDITIONS:")
        for sc in report["stop_conditions"]:
            print(f"  - {sc}")
    elif apply:
        print(f"Inserted: {report.get('inserted', 0)}")
        print(f"Skipped (idempotent): {report.get('skipped', 0)}")
        print(f"Blocked: {report.get('blocked', 0)}")
        print(f"Idempotency PASS: {report.get('idempotency_pass')}")
        print(f"Backup: {report.get('backup_path')}")
        print()
        print("Rollback plan:", report.get("rollback_plan", "N/A"))
    else:
        print(f"Would insert: {report.get('would_insert', 0)}")
        print(f"Would skip: {report.get('would_skip', 0)}")
        print(f"Would block: {report.get('would_block', 0)}")
        print()
        print("Rollback plan:", report.get("rollback_plan", "N/A"))
        print()
        print("Run with --apply to write to DB (backup created automatically).")

    status = report.get("status", "UNKNOWN")
    if "BLOCKED" in status or "FAILED" in status:
        sys.exit(1)


if __name__ == "__main__":
    main()
