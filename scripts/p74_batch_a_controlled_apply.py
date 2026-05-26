#!/usr/bin/env python3
"""
p74_batch_a_controlled_apply.py
=====================================
P74 Batch A Controlled Apply — POWER_LOTTO only.

DEFAULT MODE: Dry-run preview (no DB write).
--apply flag required for actual DB write.

Reads outputs/replay/p74_batch_a_apply_plan_20260526.json,
verifies readiness, then (with --apply) inserts PLAN_INSERT entries
for fourier_rhythm_3bet and fourier30_markov30_2bet into
strategy_prediction_replays.

Constraints:
  - dry-run by default; --apply flag required for write
  - --backup path required for --apply
  - refuses --apply unless source DB rows == EXPECTED_ROWS_BEFORE_APPLY
  - refuses --apply if any P74 controlled_apply_id rows already exist
  - duplicate detection by (strategy_id, lottery_type, target_draw, controlled_apply_id)
  - batch scope = POWER_LOTTO Batch A only
  - never touches lifecycle / champion / registry
  - exits cleanly with PLAN_BLOCKED status if plan has no eligible rows
  - no git reset --hard, no git clean, no force push
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import sqlite3
import sys

REPO_ROOT  = pathlib.Path(__file__).resolve().parent.parent
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
PLAN_JSON  = REPO_ROOT / "outputs" / "replay" / "p74_batch_a_apply_plan_20260526.json"

EXPECTED_ROWS_BEFORE_APPLY  = 46960
EXPECTED_ROWS_AFTER_APPLY   = 49960
BATCH_A_STRATEGIES          = {"fourier_rhythm_3bet", "fourier30_markov30_2bet"}
ALLOWED_LOTTERY_TYPE        = "POWER_LOTTO"
CONTROLLED_APPLY_ID_MAP     = {
    "fourier_rhythm_3bet":    "P74_POWERLOTTO_BATCH_A_FOURIER_RHYTHM_1500_PROD_20260526",
    "fourier30_markov30_2bet": "P74_POWERLOTTO_BATCH_A_FOURIER30_MARKOV30_1500_PROD_20260526",
}
SOURCE_TAG   = "P74_BATCH_A_CONTROLLED_APPLY"
TRUTH_LEVEL  = "RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _open_readonly(path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path.resolve()))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _open_readwrite(path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _row_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]


def _p74_existing_count(conn: sqlite3.Connection) -> int:
    placeholders = ",".join("?" for _ in CONTROLLED_APPLY_ID_MAP.values())
    ids = list(CONTROLLED_APPLY_ID_MAP.values())
    return conn.execute(
        f"SELECT COUNT(*) FROM strategy_prediction_replays "
        f"WHERE controlled_apply_id IN ({placeholders})",
        ids,
    ).fetchone()[0]


def _is_duplicate(
    conn: sqlite3.Connection,
    strategy_id: str,
    lottery_type: str,
    target_draw: str,
    controlled_apply_id: str,
) -> bool:
    """Check duplicate by (strategy_id + lottery_type + target_draw + controlled_apply_id)."""
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id=? AND lottery_type=? AND target_draw=? AND controlled_apply_id=?",
        (strategy_id, lottery_type, target_draw, controlled_apply_id),
    ).fetchone()[0] > 0


def _provenance_hash(strategy_id: str, lottery_type: str, target_draw: str) -> str:
    raw = f"{strategy_id}|{lottery_type}|{target_draw}|{SOURCE_TAG}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Load and validate plan
# ---------------------------------------------------------------------------

def _load_plan(plan_path: pathlib.Path) -> dict:
    if not plan_path.exists():
        print(f"ERROR: Plan JSON not found: {plan_path}", file=sys.stderr)
        sys.exit(1)
    with plan_path.open() as f:
        plan = json.load(f)
    if plan.get("project_context_lock") != "LotteryNew":
        print("ERROR: project_context_lock mismatch — not LotteryNew", file=sys.stderr)
        sys.exit(1)
    return plan


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def _preflight_apply(args: argparse.Namespace, conn_ro: sqlite3.Connection) -> None:
    """Checks run only when --apply is requested."""
    # 1. Backup required
    backup_path = pathlib.Path(args.backup)
    if not backup_path.exists():
        print(
            f"SAFETY STOP: --apply requires backup file, not found: {backup_path}\n"
            "Create backup: cp lottery_api/data/lottery_v2.db <backup_path>",
            file=sys.stderr,
        )
        sys.exit(2)

    # 2. Verify backup row count
    try:
        bconn = sqlite3.connect(str(backup_path))
        bconn.execute("PRAGMA query_only = ON")
        bcount = bconn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        bconn.close()
    except sqlite3.DatabaseError as e:
        print(f"SAFETY STOP: backup DB unreadable: {e}", file=sys.stderr)
        sys.exit(2)
    if bcount != EXPECTED_ROWS_BEFORE_APPLY:
        print(
            f"SAFETY STOP: backup row count {bcount} != expected {EXPECTED_ROWS_BEFORE_APPLY}",
            file=sys.stderr,
        )
        sys.exit(2)

    # 3. Live DB row count
    live_count = _row_count(conn_ro)
    if live_count != EXPECTED_ROWS_BEFORE_APPLY:
        print(
            f"SAFETY STOP: live DB row count {live_count} != expected {EXPECTED_ROWS_BEFORE_APPLY}",
            file=sys.stderr,
        )
        sys.exit(2)

    # 4. No P74 rows already exist
    existing_p74 = _p74_existing_count(conn_ro)
    if existing_p74 > 0:
        print(
            f"SAFETY STOP: {existing_p74} P74 controlled_apply_id rows already exist. "
            "Apply is idempotent but this indicates a previous partial apply. "
            "Investigate before retrying.",
            file=sys.stderr,
        )
        sys.exit(2)


def _preflight_dryrun(conn_ro: sqlite3.Connection) -> dict:
    """Checks run in dry-run mode. Returns summary dict."""
    live_count   = _row_count(conn_ro)
    existing_p74 = _p74_existing_count(conn_ro)
    return {
        "live_rows": live_count,
        "rows_ok": live_count == EXPECTED_ROWS_BEFORE_APPLY,
        "p74_existing_rows": existing_p74,
        "p74_collision_free": existing_p74 == 0,
    }


# ---------------------------------------------------------------------------
# Dry-run report
# ---------------------------------------------------------------------------

def _dry_run(plan: dict, conn_ro: sqlite3.Connection) -> None:
    print("=" * 60)
    print("P74 BATCH A CONTROLLED APPLY — DRY-RUN MODE")
    print("NO DB WRITE IN THIS MODE.")
    print("=" * 60)

    plan_status = plan.get("final_plan_status", "UNKNOWN")
    print(f"\nPlan status : {plan_status}")
    print(f"Total plan rows : {plan.get('total_plan_insert_rows', 0)}")

    if plan_status != "PLAN_READY_FOR_P76_APPLY":
        print(
            f"\nPLAN NOT READY — status is '{plan_status}'.\n"
            "No rows available to preview.\n"
        )
        gap_info = plan.get("source_draw_discovery", {})
        print("Source draw discovery:")
        print(f"  draws > 115000040 : {gap_info.get('draws_after_115000040', 'N/A')}")
        print(f"  gap_reason        : {gap_info.get('gap_reason', 'N/A')}")
        print("\nUnblock requirements:")
        for step in plan.get("unblock_requirements", []):
            print(f"  {step}")
        print()

    checks = _preflight_dryrun(conn_ro)
    print("Pre-flight (dry-run):")
    print(f"  live_rows              : {checks['live_rows']} (expected {EXPECTED_ROWS_BEFORE_APPLY}) — {'OK' if checks['rows_ok'] else 'MISMATCH'}")
    print(f"  p74_existing_rows      : {checks['p74_existing_rows']} (expected 0) — {'OK' if checks['p74_collision_free'] else 'COLLISION'}")

    # Enumerate plan rows (0 if blocked)
    all_rows: list[dict] = []
    by_strategy = plan.get("plan_insert_rows_by_strategy", {})
    for sid, rows in by_strategy.items():
        all_rows.extend(rows)

    eligible = 0
    skipped  = 0
    for entry in all_rows:
        sid          = entry["strategy_id"]
        lottery_type = entry.get("lottery_type", ALLOWED_LOTTERY_TYPE)
        target_draw  = entry["target_draw"]
        cap_id       = CONTROLLED_APPLY_ID_MAP.get(sid, "")
        if lottery_type != ALLOWED_LOTTERY_TYPE or sid not in BATCH_A_STRATEGIES:
            skipped += 1
            continue
        dup = _is_duplicate(conn_ro, sid, lottery_type, target_draw, cap_id)
        if dup:
            skipped += 1
        else:
            eligible += 1

    print(f"\nDry-run row analysis:")
    print(f"  total plan rows : {len(all_rows)}")
    print(f"  eligible (no dup) : {eligible}")
    print(f"  would be skipped  : {skipped}")
    print(f"  rows after apply (if applied) : {checks['live_rows'] + eligible}")

    if eligible == 0:
        print(
            "\nDRY-RUN RESULT: 0 eligible rows.\n"
            "Apply would make no changes to the DB.\n"
            "Classification: PLAN_BLOCKED_BY_SOURCE_DATA_GAP"
        )
    else:
        print(
            f"\nDRY-RUN RESULT: {eligible} rows would be inserted.\n"
            f"Expected rows after: {checks['live_rows'] + eligible}"
        )

    print("\nNO DB WRITE OCCURRED.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Apply (requires --apply flag)
# ---------------------------------------------------------------------------

_INSERT_SQL = """
INSERT INTO strategy_prediction_replays (
    lottery_type, target_draw, target_date, strategy_id, strategy_name,
    strategy_version, history_cutoff_draw, replay_status, reject_reason,
    predicted_numbers, predicted_special, actual_numbers, actual_special,
    hit_numbers, hit_count, special_hit, replay_run_id, generated_at,
    truth_level, controlled_apply_id, source, provenance_hash,
    provenance_source, dry_run
) VALUES (
    :lottery_type, :target_draw, :target_date, :strategy_id, :strategy_name,
    :strategy_version, :history_cutoff_draw, :replay_status, :reject_reason,
    :predicted_numbers, :predicted_special, :actual_numbers, :actual_special,
    :hit_numbers, :hit_count, :special_hit, :replay_run_id, :generated_at,
    :truth_level, :controlled_apply_id, :source, :provenance_hash,
    :provenance_source, :dry_run
)
"""


def _apply(plan: dict, conn_ro: sqlite3.Connection, db_path: pathlib.Path) -> None:
    """Execute actual DB write. Only called when --apply is present."""
    plan_status = plan.get("final_plan_status", "UNKNOWN")
    if plan_status != "PLAN_READY_FOR_P76_APPLY":
        print(
            f"SAFETY STOP: --apply refused because plan_status='{plan_status}'.\n"
            "Plan must be PLAN_READY_FOR_P76_APPLY before apply can proceed.",
            file=sys.stderr,
        )
        sys.exit(3)

    total_planned = plan.get("total_plan_insert_rows", 0)
    if total_planned == 0:
        print(
            "SAFETY STOP: --apply refused because total_plan_insert_rows=0.",
            file=sys.stderr,
        )
        sys.exit(3)

    conn_rw = _open_readwrite(db_path)
    rows_before = _row_count(conn_rw)

    inserted = 0
    skipped  = 0
    by_strategy = plan.get("plan_insert_rows_by_strategy", {})
    generated_at = datetime.datetime.utcnow().isoformat() + "Z"

    for sid, plan_rows in by_strategy.items():
        if sid not in BATCH_A_STRATEGIES:
            print(f"SKIP (out of Batch A scope): {sid}", file=sys.stderr)
            continue
        cap_id = CONTROLLED_APPLY_ID_MAP[sid]
        for entry in plan_rows:
            lt   = entry.get("lottery_type", ALLOWED_LOTTERY_TYPE)
            draw = entry["target_draw"]
            if lt != ALLOWED_LOTTERY_TYPE:
                skipped += 1
                continue
            if _is_duplicate(conn_rw, sid, lt, draw, cap_id):
                skipped += 1
                continue
            ph = _provenance_hash(sid, lt, draw)
            payload = {
                "lottery_type":        lt,
                "target_draw":         draw,
                "target_date":         entry.get("target_date"),
                "strategy_id":         sid,
                "strategy_name":       entry.get("strategy_name", sid),
                "strategy_version":    "P74_BATCH_A_CONTROLLED_APPLY_v1",
                "history_cutoff_draw": entry.get("history_cutoff_draw"),
                "replay_status":       "PREDICTED",
                "reject_reason":       None,
                "predicted_numbers":   entry.get("predicted_numbers"),
                "predicted_special":   None,
                "actual_numbers":      entry.get("actual_numbers"),
                "actual_special":      entry.get("actual_special"),
                "hit_numbers":         entry.get("hit_numbers", "[]"),
                "hit_count":           entry.get("hit_count", 0),
                "special_hit":         0,
                "replay_run_id":       None,
                "generated_at":        generated_at,
                "truth_level":         TRUTH_LEVEL,
                "controlled_apply_id": cap_id,
                "source":              SOURCE_TAG,
                "provenance_hash":     ph,
                "provenance_source":   "P74_PLAN_JSON",
                "dry_run":             0,
            }
            conn_rw.execute(_INSERT_SQL, payload)
            inserted += 1

    conn_rw.commit()
    rows_after = _row_count(conn_rw)
    conn_rw.close()

    print(f"Apply complete: inserted={inserted}, skipped={skipped}")
    print(f"Rows before: {rows_before}, rows after: {rows_after}")
    if rows_after != EXPECTED_ROWS_AFTER_APPLY:
        print(
            f"WARNING: rows_after={rows_after} != expected {EXPECTED_ROWS_AFTER_APPLY}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "P74 Batch A Controlled Apply. Default: dry-run (no DB write)."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Write to DB. Requires --backup. REFUSED if plan not PLAN_READY_FOR_P76_APPLY.",
    )
    parser.add_argument(
        "--backup",
        default="",
        help="Path to pre-apply backup file. REQUIRED for --apply.",
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help="Target DB path (default: production DB).",
    )
    parser.add_argument(
        "--plan-json",
        default=str(PLAN_JSON),
        dest="plan_json",
        help="Apply plan JSON path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        dest="dry_run",
        help="Dry-run mode (default). No DB write.",
    )
    args = parser.parse_args()

    # --apply overrides dry_run flag
    if args.apply:
        args.dry_run = False

    plan = _load_plan(pathlib.Path(args.plan_json))
    db_path = pathlib.Path(args.db)

    conn_ro = _open_readonly(db_path)

    if args.apply:
        _preflight_apply(args, conn_ro)
        conn_ro.close()
        _apply(plan, _open_readonly(db_path), db_path)
    else:
        _dry_run(plan, conn_ro)
        conn_ro.close()


if __name__ == "__main__":
    main()
