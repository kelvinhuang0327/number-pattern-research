#!/usr/bin/env python3
"""
p7_controlled_replay_row_apply.py
=====================================
P7 Controlled Replay Row Apply.

DEFAULT MODE: Dry-run preview (no DB write).
--apply flag required for actual DB write.

Reads the frozen P7 dry-run JSON, verifies backup exists, runs
idempotency checks, then (with --apply) inserts one replay row
per P7 PLAN_INSERT entry into strategy_prediction_replays.

Constraints:
  - default mode reads DB with mode=ro, no writes
  - --apply required for any DB write
  - --scope ONLINE_ONLY (default) — only 28 ONLINE rows
  - RETIRED rows blocked unless BOTH --scope INCLUDE_RETIRED_WITH_WARNING
    AND --include-retired-reviewed are supplied
  - backup file required for apply
  - inserts one row per plan entry (one per draw, first prediction_item)
  - idempotent: duplicate (strategy_id + target_draw + lottery_type) skipped
  - all inserted rows get: controlled_apply_id, rollback_batch_id,
    truth_level=RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD,
    provenance_hash, source=P7_CONTROLLED_APPLY, dry_run=0
  - never imports draw data, never executes strategy logic
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sqlite3
import sys
import uuid

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P7_JSON   = REPO_ROOT / "outputs" / "replay" / "p7_controlled_apply_dry_run_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_p7_apply_plan_contract import P7ApplyDecision, P7ApplyScope

TRUTH_LEVEL_APPLIED = "RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD"
SOURCE_TAG          = "P7_CONTROLLED_APPLY"

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _open_readonly(path: pathlib.Path) -> sqlite3.Connection:
    """
    Open DB in read-only mode.
    Uses PRAGMA query_only to refuse writes at the SQLite level.
    URI mode=ro is avoided due to cross-platform path encoding edge cases.
    """
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


def _is_duplicate(conn: sqlite3.Connection, strategy_id: str, lottery_type: str, target_draw: str) -> bool:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id=? AND lottery_type=? AND target_draw=?",
        (strategy_id, lottery_type, target_draw),
    ).fetchone()[0] > 0


def _get_first_prediction_numbers(
    conn: sqlite3.Connection, run_id: int, strategy_id: str
) -> str | None:
    row = conn.execute(
        "SELECT numbers FROM prediction_items "
        "WHERE run_id=? AND strategy_name=? "
        "ORDER BY id ASC LIMIT 1",
        (run_id, strategy_id),
    ).fetchone()
    return row[0] if row else None


def _get_draw_info(
    conn: sqlite3.Connection, target_draw: str, lottery_type: str
) -> dict | None:
    """Fetch actual draw date, numbers, special from draws table."""
    row = conn.execute(
        "SELECT date, numbers, special FROM draws "
        "WHERE draw=? AND lottery_type=? LIMIT 1",
        (target_draw, lottery_type),
    ).fetchone()
    if row:
        return {"date": row[0], "numbers": row[1], "special": row[2]}
    return None


def _compute_hits(predicted: str | None, actual: str | None) -> tuple[str, int]:
    """Return (hit_numbers_json, hit_count). Empty on parse error."""
    if not predicted or not actual:
        return "[]", 0
    try:
        import json as _json
        pred_set = set(_json.loads(predicted))
        act_set  = set(_json.loads(actual))
        hits     = sorted(pred_set & act_set)
        return str(hits), len(hits)
    except Exception:
        return "[]", 0


def _get_strategy_display_name(strategy_id: str) -> str:
    """Look up strategy display name from registry."""
    try:
        from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
        for m in list_strategy_lifecycle_metadata():
            if m.get("strategy_id") == strategy_id:
                return m.get("strategy_name", strategy_id)
    except Exception:
        pass
    return strategy_id


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def _preflight(args: argparse.Namespace, conn_ro: sqlite3.Connection) -> None:
    """Run all pre-flight checks. Raises RuntimeError on failure."""

    # 1. Backup required for actual apply
    if args.apply:
        backup_path = pathlib.Path(args.backup)
        if not backup_path.exists():
            raise RuntimeError(
                f"SAFETY STOP: --apply requires backup file, not found: {backup_path}\n"
                "Create backup first: sqlite3 lottery_v2.db "
                f"'.backup {backup_path}'"
            )
        # Verify backup row count
        try:
            bconn = sqlite3.connect(str(backup_path))
            bcount = bconn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
            bconn.close()
            if bcount != args.expected_rows:
                raise RuntimeError(
                    f"SAFETY STOP: backup row count {bcount} != "
                    f"expected {args.expected_rows}"
                )
        except sqlite3.DatabaseError as e:
            raise RuntimeError(f"SAFETY STOP: backup DB is unreadable: {e}")

    # 2. Source DB row count
    live_count = _row_count(conn_ro)
    if live_count != args.expected_rows:
        raise RuntimeError(
            f"SAFETY STOP: strategy_prediction_replays row count "
            f"{live_count} != expected {args.expected_rows}"
        )

    # 3. RETIRED scope requires both flags
    if args.scope == P7ApplyScope.INCLUDE_RETIRED_WITH_WARNING:
        if not getattr(args, "include_retired_reviewed", False):
            raise RuntimeError(
                "SAFETY STOP: --scope INCLUDE_RETIRED_WITH_WARNING requires "
                "--include-retired-reviewed flag to confirm human review."
            )


# ---------------------------------------------------------------------------
# Build insert payload
# ---------------------------------------------------------------------------

def _build_payload(
    row: dict,
    conn_ro: sqlite3.Connection,
    rollback_batch_id: str,
    strategy_names: dict[str, str],
) -> dict | None:
    """
    Build a single strategy_prediction_replays row dict from a P7 plan row.
    Returns None if data is insufficient for a safe insert.
    """
    sid          = row["strategy_id"]
    lottery_type = row["lottery_type"]
    target_draw  = row["draw_id"]
    run_id       = row.get("source_run_id")
    prov_hash    = row["provenance_hash"]
    cap_id       = row["controlled_apply_id"]

    if not run_id:
        return None

    # Get first prediction_item numbers
    pred_numbers = _get_first_prediction_numbers(conn_ro, run_id, sid)
    if not pred_numbers:
        return None  # no payload — skip

    # Get draw info (date, actual numbers, special)
    draw_info = _get_draw_info(conn_ro, target_draw, lottery_type)
    target_date    = draw_info["date"]    if draw_info else None
    actual_numbers = draw_info["numbers"] if draw_info else None
    actual_special = draw_info["special"] if draw_info else None

    # Compute hits
    hit_numbers_json, hit_count = _compute_hits(pred_numbers, actual_numbers)

    # history_cutoff_draw: use the draw just before target_draw
    try:
        cutoff_draw = str(int(target_draw) - 1).zfill(len(target_draw))
    except (ValueError, TypeError):
        cutoff_draw = None

    strategy_name = strategy_names.get(sid, sid)

    return {
        "lottery_type":         lottery_type,
        "target_draw":          target_draw,
        "target_date":          target_date,
        "strategy_id":          sid,
        "strategy_name":        strategy_name,
        "strategy_version":     "P7_CONTROLLED_APPLY_v1",
        "history_cutoff_draw":  cutoff_draw,
        "replay_status":        "PREDICTED",
        "reject_reason":        None,
        "predicted_numbers":    pred_numbers,
        "predicted_special":    None,
        "actual_numbers":       actual_numbers,
        "actual_special":       actual_special,
        "hit_numbers":          hit_numbers_json,
        "hit_count":            hit_count,
        "special_hit":          0,
        "replay_run_id":        None,  # P7 source_run_ids are prediction_runs.id, not strategy_replay_runs.id
        "generated_at":         datetime.datetime.utcnow().isoformat() + "Z",
        "truth_level":          TRUTH_LEVEL_APPLIED,
        "controlled_apply_id":  cap_id,
        "source":               SOURCE_TAG,
        "provenance_hash":      prov_hash,
        "provenance_source":    "PREDICTION_ITEMS_DB",
        "dry_run":              0,
        # batch tracking (stored in rollback field via source field + controlled_apply_id)
        "_rollback_batch_id":   rollback_batch_id,
    }


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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="P7 Controlled Replay Row Apply. Default: dry-run preview."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Actually write to DB. Requires --backup.",
    )
    parser.add_argument(
        "--scope",
        choices=[
            P7ApplyScope.ONLINE_ONLY,
            P7ApplyScope.INCLUDE_RETIRED_WITH_WARNING,
        ],
        default=P7ApplyScope.ONLINE_ONLY,
    )
    parser.add_argument(
        "--include-retired-reviewed",
        action="store_true",
        default=False,
        dest="include_retired_reviewed",
        help=(
            "Required alongside --scope INCLUDE_RETIRED_WITH_WARNING to confirm "
            "that lifecycle warnings have been reviewed by a human."
        ),
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help="Target DB path (default: production DB).",
    )
    parser.add_argument(
        "--backup",
        default="backups/lottery_v2_pre_p7_controlled_apply_20260520.db",
        help="Path to backup DB (required for --apply).",
    )
    parser.add_argument(
        "--p7-json",
        default=str(P7_JSON),
    )
    parser.add_argument(
        "--expected-rows",
        type=int,
        default=460,
        dest="expected_rows",
    )
    parser.add_argument(
        "--json-out",
        default=str(REPO_ROOT / "outputs" / "replay" /
                    "p7_controlled_apply_apply_result_20260520.json"),
    )
    parser.add_argument(
        "--rollback-plan",
        metavar="CONTROLLED_APPLY_ID",
        default=None,
        help="Preview rollback SQL for a given controlled_apply_id (dry-run only).",
    )
    parser.add_argument(
        "--rollback-apply",
        action="store_true",
        default=False,
        help="Execute rollback for --rollback-plan controlled_apply_id (requires --apply).",
    )
    args = parser.parse_args()

    db_path = pathlib.Path(args.db)
    if not db_path.exists():
        print(f"STOP: DB not found: {db_path}")
        sys.exit(1)

    # ── Rollback plan (dry-run display) ───────────────────────────────────────
    if args.rollback_plan:
        _show_rollback_plan(args.rollback_plan, db_path, args.rollback_apply and args.apply)
        return

    # ── Load P7 JSON ──────────────────────────────────────────────────────────
    p7_path = pathlib.Path(args.p7_json)
    if not p7_path.exists():
        print(f"STOP: P7 JSON not found: {p7_path}")
        sys.exit(1)

    p7_data      = json.loads(p7_path.read_text())
    insert_rows  = p7_data.get("p7_insert_rows", [])

    # Filter by scope
    if args.scope == P7ApplyScope.ONLINE_ONLY:
        eligible = [r for r in insert_rows if r["lifecycle_state"] == "ONLINE"]
    else:
        eligible = list(insert_rows)

    print(f"P7 frozen set: {len(insert_rows)} PLAN_INSERT rows")
    print(f"Scope={args.scope}: {len(eligible)} eligible rows")

    # ── Pre-flight checks ─────────────────────────────────────────────────────
    conn_ro = _open_readonly(db_path)
    try:
        _preflight(args, conn_ro)
    except RuntimeError as e:
        print(str(e))
        conn_ro.close()
        sys.exit(1)

    live_count_before = _row_count(conn_ro)
    print(f"DB row count before: {live_count_before}")

    # ── Pre-compute strategy display names ────────────────────────────────────
    strategy_names = {
        r["strategy_id"]: _get_strategy_display_name(r["strategy_id"])
        for r in eligible
    }

    # ── Build payloads + duplicate check ─────────────────────────────────────
    rollback_batch_id = str(uuid.uuid4())
    planned:   list[dict] = []
    dup_skip:  list[dict] = []
    no_payload:list[dict] = []

    for row in eligible:
        sid          = row["strategy_id"]
        lottery_type = row["lottery_type"]
        target_draw  = row["draw_id"]

        if _is_duplicate(conn_ro, sid, lottery_type, target_draw):
            dup_skip.append(row)
            continue

        payload = _build_payload(row, conn_ro, rollback_batch_id, strategy_names)
        if payload is None:
            no_payload.append(row)
            continue

        planned.append(payload)

    conn_ro.close()

    # ── Preview ───────────────────────────────────────────────────────────────
    print(f"\nPlan preview:")
    print(f"  WILL INSERT:      {len(planned)}")
    print(f"  SKIP (duplicate): {len(dup_skip)}")
    print(f"  SKIP (no payload):{len(no_payload)}")
    print(f"  Rollback batch:   {rollback_batch_id}")

    if not args.apply:
        print("\n[DRY-RUN] No DB write. Pass --apply to execute.")
        _write_result_json(
            pathlib.Path(args.json_out),
            applied=False,
            scope=args.scope,
            planned=planned,
            dup_skip=dup_skip,
            no_payload=no_payload,
            rollback_batch_id=rollback_batch_id,
            rows_before=live_count_before,
            rows_after=live_count_before,
        )
        return

    # ── Safety: max insert guard ───────────────────────────────────────────────
    if len(planned) > 28:
        print(
            f"SAFETY STOP: planned insert count {len(planned)} > 28. "
            "Refusing to insert more than the ONLINE_ONLY approved set."
        )
        sys.exit(1)

    # ── Actual apply ──────────────────────────────────────────────────────────
    print("\n[APPLY] Writing to DB...")
    inserted = 0
    errors   = []

    conn_rw = _open_readwrite(db_path)
    try:
        for payload in planned:
            # Strip internal tracking key
            row_data = {k: v for k, v in payload.items() if not k.startswith("_")}
            try:
                conn_rw.execute(_INSERT_SQL, row_data)
                inserted += 1
            except sqlite3.Error as e:
                errors.append({"strategy_id": payload["strategy_id"],
                                "target_draw": payload["target_draw"],
                                "error": str(e)})
        conn_rw.commit()

        rows_after = conn_rw.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    except Exception as e:
        conn_rw.rollback()
        conn_rw.close()
        print(f"APPLY FAILED: {e}\nRolling back.")
        sys.exit(1)
    finally:
        conn_rw.close()

    print(f"\n[APPLY RESULT]")
    print(f"  Inserted:   {inserted}")
    print(f"  Errors:     {len(errors)}")
    print(f"  Rows after: {rows_after}")
    print(f"  Expected:   {live_count_before + len(planned)}")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")

    _write_result_json(
        pathlib.Path(args.json_out),
        applied=True,
        scope=args.scope,
        planned=planned,
        dup_skip=dup_skip,
        no_payload=no_payload,
        rollback_batch_id=rollback_batch_id,
        rows_before=live_count_before,
        rows_after=rows_after,
        inserted=inserted,
        errors=errors,
    )
    print(f"\nResult JSON: {args.json_out}")


def _show_rollback_plan(
    controlled_apply_id: str,
    db_path: pathlib.Path,
    execute: bool,
) -> None:
    rollback_sql = (
        f"DELETE FROM strategy_prediction_replays "
        f"WHERE controlled_apply_id = '{controlled_apply_id}';"
    )
    print("=== Rollback Plan ===")
    print(f"Controlled apply ID: {controlled_apply_id}")
    print(f"SQL: {rollback_sql}")

    conn_ro = _open_readonly(db_path)
    count = conn_ro.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id=?",
        (controlled_apply_id,),
    ).fetchone()[0]
    conn_ro.close()
    print(f"Rows matching: {count}")

    if execute:
        print("[ROLLBACK APPLY] Deleting rows...")
        conn_rw = sqlite3.connect(str(db_path))
        conn_rw.execute(
            "DELETE FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (controlled_apply_id,),
        )
        conn_rw.commit()
        remaining = conn_rw.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn_rw.close()
        print(f"Rollback complete. Remaining rows: {remaining}")
    else:
        print("[DRY-RUN] Pass --rollback-apply --apply to execute.")


def _write_result_json(
    path: pathlib.Path,
    *,
    applied: bool,
    scope: str,
    planned: list,
    dup_skip: list,
    no_payload: list,
    rollback_batch_id: str,
    rows_before: int,
    rows_after: int,
    inserted: int = 0,
    errors: list = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "phase":               "P7_APPLY",
        "applied":             applied,
        "scope":               scope,
        "rollback_batch_id":   rollback_batch_id,
        "rows_before":         rows_before,
        "rows_after":          rows_after,
        "inserted":            inserted if applied else 0,
        "duplicate_skipped":   len(dup_skip),
        "no_payload_skipped":  len(no_payload),
        "planned_insert_count": len(planned),
        "errors":              errors or [],
        "generated_at":        datetime.datetime.utcnow().isoformat() + "Z",
        "safety_flags": {
            "db_write_performed":   applied,
            "truth_level_applied":  TRUTH_LEVEL_APPLIED,
            "source_tag":           SOURCE_TAG,
            "max_insert_guard_28":  True,
            "dry_run_field_value":  0 if applied else 1,
        },
    }
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
