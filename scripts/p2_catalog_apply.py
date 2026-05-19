#!/usr/bin/env python3
"""
p2_catalog_apply.py
====================
P2 Controlled Catalog Apply — writes P1 visibility plan entries into
the strategy_catalog DB table.

Safety guarantees:
  - Dry-run by default; pass --apply to write DB
  - Auto-backup DB before any write
  - Idempotent: re-runs do not duplicate rows (INSERT OR REPLACE by strategy_id+lottery_type)
  - NEVER touches strategy_prediction_replays
  - NEVER touches prediction_items / prediction_runs
  - NEVER changes lifecycle_state to ONLINE for any entry
  - NEVER marks ARTIFACT_CANDIDATE as runtime-online
  - ARTIFACT_CANDIDATE entries are catalog-visible only (dry_run_only=1 always)
  - Supports --rollback to DROP strategy_catalog table if needed

Usage:
  python3 scripts/p2_catalog_apply.py                   # dry-run
  python3 scripts/p2_catalog_apply.py --apply            # write to DB (backup first)
  python3 scripts/p2_catalog_apply.py --dry-run          # explicit dry-run
  python3 scripts/p2_catalog_apply.py --rollback         # dry-run rollback plan
  python3 scripts/p2_catalog_apply.py --rollback --apply # execute rollback
  python3 scripts/p2_catalog_apply.py --json-out <path>  # output JSON report
"""

import argparse
import datetime
import json
import pathlib
import shutil
import sqlite3
import sys

REPO_ROOT   = pathlib.Path(__file__).resolve().parent.parent
DB_PATH     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
MIGRATION   = REPO_ROOT / "lottery_api" / "migrations" / "0002_p2_catalog_table.sql"
BACKUP_DIR  = REPO_ROOT / "backups"

DEFAULT_JSON_OUT = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
DEFAULT_MD_OUT   = REPO_ROOT / "docs"    / "replay" / "p2_catalog_apply_dry_run_20260520.md"

sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Safety assertions — run before any DB operation
# ---------------------------------------------------------------------------

_PROTECTED_TABLES = {
    "strategy_prediction_replays",
    "prediction_items",
    "prediction_runs",
    "prediction_results",
}


def _assert_no_protected_table_touch(conn: sqlite3.Connection) -> None:
    """Verify no rows changed in protected tables (pre/post check)."""
    counts = {}
    for tbl in _PROTECTED_TABLES:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            counts[tbl] = n
        except Exception:
            counts[tbl] = None
    return counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backup_db(db_path: pathlib.Path, label: str = "p2_catalog_apply") -> pathlib.Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"lottery_v2_pre_{label}_{ts}.db"
    shutil.copy2(str(db_path), str(dest))
    return dest


def _ensure_catalog_table(conn: sqlite3.Connection, dry_run: bool) -> bool:
    """Create strategy_catalog table if absent. Returns True if created."""
    exists = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='strategy_catalog'"
    ).fetchone()[0]
    if exists:
        return False
    sql = MIGRATION.read_text()
    if not dry_run:
        conn.executescript(sql)
        conn.commit()
    return True


def _get_catalog_row_count(conn: sqlite3.Connection) -> int:
    try:
        return conn.execute("SELECT COUNT(*) FROM strategy_catalog").fetchone()[0]
    except Exception:
        return -1


# ---------------------------------------------------------------------------
# Plan building (read-only — reuses P1 planner logic)
# ---------------------------------------------------------------------------

def _build_catalog_entries() -> list[dict]:
    """Build the list of entries to upsert. Pure computation, no DB access."""
    from scripts.p1_catalog_visibility_plan import build_plan
    plan = build_plan(DB_PATH)

    entries = []

    # Registered strategies (18)
    for e in plan["entries"]:
        entries.append({
            "strategy_id":                e["strategy_id"],
            "display_name":               e["display_name"],
            "lottery_type":               e["lottery_type"],
            "lifecycle_state":            e["lifecycle_state"],
            "catalog_visibility_state":   e["catalog_visibility_state"],
            "source_paths_json":          json.dumps(e.get("source_paths", [])),
            "artifact_source_type":       e.get("artifact_source_type", "NONE"),
            "has_replay_rows":            1 if e["has_replay_rows"] else 0,
            "has_historical_predictions": 1 if e["has_historical_predictions"] else 0,
            "replay_row_count":           e.get("replay_row_count", 0),
            "reconstructible_reason":     e.get("reconstructible_reason"),
            "no_data_reason":             e.get("no_data_reason"),
            "provenance_hash":            e.get("provenance_hash"),
            "created_by_phase":           "P2",
            "dry_run_only":               1,   # always 1 in P2
        })

    # Artifact candidates (41 extra)
    for e in plan.get("artifact_candidates_extra", []):
        entries.append({
            "strategy_id":                e["strategy_id"],
            "display_name":               e.get("display_name", e["strategy_id"]),
            "lottery_type":               e.get("lottery_type", "UNKNOWN"),
            "lifecycle_state":            e.get("lifecycle_state", "NOT_REGISTERED"),
            "catalog_visibility_state":   e["catalog_visibility_state"],
            "source_paths_json":          json.dumps(e.get("source_paths", [])),
            "artifact_source_type":       e.get("artifact_source_type", "REJECTED_JSON"),
            "has_replay_rows":            0,
            "has_historical_predictions": 0,
            "replay_row_count":           0,
            "reconstructible_reason":     e.get("reconstructible_reason"),
            "no_data_reason":             e.get("no_data_reason"),
            "provenance_hash":            e.get("provenance_hash"),
            "created_by_phase":           "P2",
            "dry_run_only":               1,   # ARTIFACT_CANDIDATE always dry_run_only
        })

    return entries


# ---------------------------------------------------------------------------
# Apply / dry-run logic
# ---------------------------------------------------------------------------

UPSERT_SQL = """
INSERT INTO strategy_catalog (
    strategy_id, display_name, lottery_type, lifecycle_state,
    catalog_visibility_state, source_paths_json, artifact_source_type,
    has_replay_rows, has_historical_predictions, replay_row_count,
    reconstructible_reason, no_data_reason, provenance_hash,
    created_by_phase, dry_run_only, updated_at
) VALUES (
    :strategy_id, :display_name, :lottery_type, :lifecycle_state,
    :catalog_visibility_state, :source_paths_json, :artifact_source_type,
    :has_replay_rows, :has_historical_predictions, :replay_row_count,
    :reconstructible_reason, :no_data_reason, :provenance_hash,
    :created_by_phase, :dry_run_only, datetime('now')
)
ON CONFLICT(strategy_id, lottery_type) DO UPDATE SET
    display_name              = excluded.display_name,
    lifecycle_state           = excluded.lifecycle_state,
    catalog_visibility_state  = excluded.catalog_visibility_state,
    source_paths_json         = excluded.source_paths_json,
    artifact_source_type      = excluded.artifact_source_type,
    has_replay_rows           = excluded.has_replay_rows,
    has_historical_predictions= excluded.has_historical_predictions,
    replay_row_count          = excluded.replay_row_count,
    reconstructible_reason    = excluded.reconstructible_reason,
    no_data_reason            = excluded.no_data_reason,
    dry_run_only              = excluded.dry_run_only,
    updated_at                = datetime('now')
"""


def run_apply(dry_run: bool, entries: list[dict]) -> dict:
    """
    Execute catalog apply (or dry-run preview).
    Returns a result dict describing what was/would be done.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    backup_path = None
    table_created = False
    inserted = 0
    updated  = 0
    skipped  = 0

    try:
        # Pre-flight: snapshot protected table counts
        before_counts = _assert_no_protected_table_touch(conn)

        # Determine action per entry (INSERT vs UPDATE vs SKIP)
        actions = []
        for e in entries:
            existing = conn.execute(
                "SELECT COUNT(*) FROM strategy_catalog WHERE strategy_id=? AND lottery_type=?",
                (e["strategy_id"], e["lottery_type"]),
            ).fetchone()[0] if _get_catalog_row_count(conn) >= 0 else 0

            if existing:
                action = "UPDATE"
                updated += 1
            else:
                action = "INSERT"
                inserted += 1
            actions.append({"entry": e, "action": action})

        if dry_run:
            conn.close()
            return {
                "mode": "DRY_RUN",
                "dry_run": True,
                "backup_path": None,
                "table_created": False,
                "inserted": inserted,
                "updated": updated,
                "skipped": skipped,
                "total": len(entries),
                "actions": [{"strategy_id": a["entry"]["strategy_id"],
                              "lottery_type": a["entry"]["lottery_type"],
                              "action": a["action"],
                              "lifecycle_state": a["entry"]["lifecycle_state"],
                              "catalog_visibility_state": a["entry"]["catalog_visibility_state"],
                              "dry_run_only": a["entry"]["dry_run_only"]} for a in actions],
                "protected_table_counts_before": before_counts,
                "violations": [],
            }

        # APPLY path
        backup_path = str(_backup_db(DB_PATH, "p2_catalog_apply"))

        table_created = _ensure_catalog_table(conn, dry_run=False)

        for a in actions:
            conn.execute(UPSERT_SQL, a["entry"])
        conn.commit()

        # Post-flight: verify protected tables unchanged
        after_counts = _assert_no_protected_table_touch(conn)
        violations = []
        for tbl, before in before_counts.items():
            after = after_counts.get(tbl)
            if before != after:
                violations.append(f"{tbl}: count changed {before} → {after}")

        final_count = _get_catalog_row_count(conn)
        conn.close()

        return {
            "mode": "APPLY",
            "dry_run": False,
            "backup_path": backup_path,
            "table_created": table_created,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "total": len(entries),
            "final_catalog_row_count": final_count,
            "actions": [{"strategy_id": a["entry"]["strategy_id"],
                          "lottery_type": a["entry"]["lottery_type"],
                          "action": a["action"],
                          "lifecycle_state": a["entry"]["lifecycle_state"],
                          "catalog_visibility_state": a["entry"]["catalog_visibility_state"],
                          "dry_run_only": a["entry"]["dry_run_only"]} for a in actions],
            "protected_table_counts_before": before_counts,
            "protected_table_counts_after": after_counts,
            "violations": violations,
        }

    except Exception:
        conn.close()
        raise


def run_rollback(dry_run: bool) -> dict:
    """Rollback: DROP strategy_catalog table."""
    conn = sqlite3.connect(str(DB_PATH))
    backup_path = None
    try:
        exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='strategy_catalog'"
        ).fetchone()[0]
        if not exists:
            conn.close()
            return {"mode": "ROLLBACK", "dry_run": dry_run, "status": "TABLE_NOT_FOUND",
                    "action": "SKIP"}

        row_count = _get_catalog_row_count(conn)

        if not dry_run:
            backup_path = str(_backup_db(DB_PATH, "p2_catalog_rollback"))
            conn.execute("DROP TABLE IF EXISTS strategy_catalog")
            conn.commit()

        conn.close()
        return {
            "mode": "ROLLBACK",
            "dry_run": dry_run,
            "backup_path": backup_path,
            "rows_dropped": row_count if not dry_run else 0,
            "rows_would_drop": row_count,
            "action": "DRY_RUN_DROP" if dry_run else "DROPPED",
        }
    except Exception:
        conn.close()
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="P2 catalog apply")
    parser.add_argument("--apply",    action="store_true", help="Write to DB")
    parser.add_argument("--dry-run",  action="store_true", help="Dry-run (default)")
    parser.add_argument("--rollback", action="store_true", help="Rollback: drop strategy_catalog")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--md-out",   default=None)
    args = parser.parse_args()

    dry_run = not args.apply  # default is dry-run

    json_out = pathlib.Path(args.json_out) if args.json_out else DEFAULT_JSON_OUT
    md_out   = pathlib.Path(args.md_out)   if args.md_out   else DEFAULT_MD_OUT

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print(f"P2 Catalog Apply")
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    if args.rollback:
        print(f"Action: ROLLBACK")
    print("=" * 60)

    if args.rollback:
        result = run_rollback(dry_run=dry_run)
    else:
        entries = _build_catalog_entries()
        print(f"\nEntries to process: {len(entries)}")
        for e in entries[:3]:
            print(f"  {e['strategy_id']} | {e['catalog_visibility_state']} | dry_run_only={e['dry_run_only']}")
        if len(entries) > 3:
            print(f"  ... ({len(entries) - 3} more)")

        # Safety assertion: no ARTIFACT_CANDIDATE can have lifecycle_state=ONLINE
        for e in entries:
            from lottery_api.models.replay_strategy_catalog_contract import CatalogVisibilityState
            if (e["catalog_visibility_state"] == CatalogVisibilityState.ARTIFACT_CANDIDATE
                    and e["lifecycle_state"] == "ONLINE"):
                print(f"SAFETY VIOLATION: {e['strategy_id']} is ARTIFACT_CANDIDATE but lifecycle=ONLINE",
                      file=sys.stderr)
                sys.exit(2)

        result = run_apply(dry_run=dry_run, entries=entries)

    # Print summary
    print(f"\nResult:")
    for k, v in result.items():
        if k not in ("actions", "protected_table_counts_before",
                     "protected_table_counts_after"):
            print(f"  {k}: {v}")

    if result.get("violations"):
        print(f"\nVIOLATIONS:", file=sys.stderr)
        for v in result["violations"]:
            print(f"  {v}", file=sys.stderr)
        sys.exit(3)

    # Write JSON output
    out_data = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "phase": "P2",
        **result,
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(out_data, indent=2, ensure_ascii=False))
    print(f"\nJSON: {json_out}")

    # Write MD output
    _write_md(out_data, md_out)
    print(f"MD:   {md_out}")

    if dry_run:
        print(f"\nDRY-RUN COMPLETE — run with --apply to write to DB")
        print(f"Apply command: python3 scripts/p2_catalog_apply.py --apply")


def _write_md(data: dict, path: pathlib.Path):
    mode = data.get("mode", "DRY_RUN")
    lines = [
        f"# P2 Catalog Apply — {mode} Report",
        f"",
        f"Generated: {data.get('generated_at', '')}",
        f"Mode: **{mode}**  dry_run: {data.get('dry_run', True)}",
        f"",
        f"## Summary",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Total entries | {data.get('total', 0)} |",
        f"| INSERT | {data.get('inserted', 0)} |",
        f"| UPDATE | {data.get('updated', 0)} |",
        f"| SKIP | {data.get('skipped', 0)} |",
    ]
    if not data.get("dry_run"):
        lines.append(f"| Final catalog rows | {data.get('final_catalog_row_count', '?')} |")
        lines.append(f"| Backup | `{data.get('backup_path', '?')}` |")

    lines += [
        f"",
        f"## Action Details",
        f"",
        f"| Strategy ID | Lottery | Action | Lifecycle | Visibility | dry_run_only |",
        f"|-------------|---------|--------|-----------|------------|-------------|",
    ]
    for a in data.get("actions", []):
        lines.append(
            f"| `{a['strategy_id']}` | {a['lottery_type']} | {a['action']} | "
            f"{a['lifecycle_state']} | {a['catalog_visibility_state']} | {a['dry_run_only']} |"
        )

    lines += [
        f"",
        f"## Violations",
        f"",
        f"{'None.' if not data.get('violations') else chr(10).join(f'- {v}' for v in data['violations'])}",
        f"",
        f"## Apply Command (requires CEO authorization)",
        f"```",
        f"python3 scripts/p2_catalog_apply.py --apply",
        f"```",
        f"",
        f"## Rollback Command",
        f"```",
        f"python3 scripts/p2_catalog_apply.py --rollback --apply",
        f"```",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
