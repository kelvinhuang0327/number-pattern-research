#!/usr/bin/env python3
"""
p2_full_catalog_visibility_plan.py
====================================
P2 Full-Catalog Visibility Plan.

Read-only analysis of the complete strategy universe.
Produces a four-state visibility classification:

  ROW_BACKED       — has actual rows in strategy_prediction_replays
  RECONSTRUCTIBLE  — has prediction_items data; replay rows can be generated
                     from DB without re-running any strategy
  NO_DATA          — in runtime registry but no source data in DB
  ARTIFACT_ONLY    — not in registry; exists only as artifact files

Zero DB writes. Zero replay row generation. Zero strategy execution.
All entries produced with dry_run_only=True.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sqlite3
import sys

REPO_ROOT   = pathlib.Path(__file__).resolve().parent.parent
DB_PATH     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P1_JSON     = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
REJECTED_DIR = REPO_ROOT / "rejected"

sys.path.insert(0, str(REPO_ROOT))

VISIBILITY_ROW_BACKED      = "ROW_BACKED"
VISIBILITY_RECONSTRUCTIBLE = "RECONSTRUCTIBLE"
VISIBILITY_NO_DATA         = "NO_DATA"
VISIBILITY_ARTIFACT_ONLY   = "ARTIFACT_ONLY"


def _open_readonly(path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path.resolve()))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _get_replay_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return {strategy_id: row_count} for all strategies with replay rows."""
    rows = conn.execute(
        "SELECT strategy_id, COUNT(*) as cnt FROM strategy_prediction_replays GROUP BY strategy_id"
    ).fetchall()
    return {r["strategy_id"]: r["cnt"] for r in rows}


def _get_prediction_item_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return {strategy_name: count} for prediction_items grouped by strategy_name."""
    rows = conn.execute(
        "SELECT strategy_name, COUNT(*) as cnt FROM prediction_items GROUP BY strategy_name"
    ).fetchall()
    return {r["strategy_name"]: r["cnt"] for r in rows}


def _load_artifact_only_from_p1(p1_json: pathlib.Path) -> list[dict]:
    """Load ARTIFACT_ONLY entries from the P1 catalog JSON."""
    if not p1_json.exists():
        return []
    data = json.loads(p1_json.read_text())
    return data.get("artifact_candidates_extra", [])


def _scan_rejected_dir(rejected_dir: pathlib.Path, registry_ids: set[str]) -> list[str]:
    """Scan rejected/ for strategy JSON files not in registry."""
    if not rejected_dir.exists():
        return []
    found = []
    for f in sorted(rejected_dir.glob("*.json")):
        sid = f.stem
        if sid not in registry_ids:
            found.append(sid)
    return found


def build_plan(db_path: pathlib.Path, p1_json: pathlib.Path) -> dict:
    """Build the full-catalog visibility plan. Read-only."""
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata

    conn = _open_readonly(db_path)
    try:
        replay_counts  = _get_replay_row_counts(conn)
        pi_counts      = _get_prediction_item_counts(conn)
        total_spr_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()

    metas       = list_strategy_lifecycle_metadata()
    registry_ids = {m["strategy_id"] for m in metas}

    entries: list[dict] = []

    for m in metas:
        sid       = m["strategy_id"]
        lifecycle = m.get("lifecycle_status", "UNKNOWN")
        lt_list   = m.get("supported_lottery_types", [])
        lottery   = lt_list[0] if lt_list else "UNKNOWN"

        row_count = replay_counts.get(sid, 0)
        pi_count  = pi_counts.get(sid, 0)

        if row_count > 0:
            vis_state = VISIBILITY_ROW_BACKED
            reconstructible_reason = None
            no_data_reason = None
        elif pi_count > 0:
            vis_state = VISIBILITY_RECONSTRUCTIBLE
            reconstructible_reason = f"{pi_count} prediction_items rows available in DB"
            no_data_reason = None
        else:
            vis_state = VISIBILITY_NO_DATA
            reconstructible_reason = None
            no_data_reason = "No replay rows and no prediction_items in DB"

        entries.append({
            "strategy_id":           sid,
            "display_name":          m.get("strategy_name", sid),
            "lottery_type":          lottery,
            "lifecycle_status":      lifecycle,
            "visibility_state":      vis_state,
            "replay_row_count":      row_count,
            "prediction_items_count": pi_count,
            "reconstructible_reason": reconstructible_reason,
            "no_data_reason":        no_data_reason,
            "dry_run_only":          True,
            "can_generate_replay_rows": False,
        })

    artifact_only_entries = _load_artifact_only_from_p1(p1_json)
    for ae in artifact_only_entries:
        ae_updated = dict(ae)
        ae_updated["visibility_state"] = VISIBILITY_ARTIFACT_ONLY
        ae_updated["dry_run_only"] = True
        ae_updated["can_generate_replay_rows"] = False
        entries.append(ae_updated)

    by_vis: dict[str, int] = {}
    for e in entries:
        k = e["visibility_state"]
        by_vis[k] = by_vis.get(k, 0) + 1

    return {
        "phase":           "P2_FULL_CATALOG_VISIBILITY_PLAN",
        "generated_at":    datetime.datetime.utcnow().isoformat() + "Z",
        "dry_run_only":    True,
        "db_write_performed": False,
        "strategy_execution_performed": False,
        "total_entries":   len(entries),
        "registry_count":  len(metas),
        "artifact_only_count": len(artifact_only_entries),
        "production_replay_rows_unchanged": total_spr_rows,
        "by_visibility_state": by_vis,
        "entries": entries,
        "safety_flags": {
            "db_write_performed":           False,
            "replay_rows_generated":        False,
            "strategy_execution_performed": False,
            "draw_import_performed":        False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P2 Full-Catalog Visibility Plan. Read-only."
    )
    parser.add_argument("--db",     default=str(DB_PATH))
    parser.add_argument("--p1-json", default=str(P1_JSON))
    parser.add_argument(
        "--json-out",
        default=str(
            REPO_ROOT / "outputs" / "replay" / "p2_full_catalog_visibility_plan_20260520.json"
        ),
    )
    args = parser.parse_args()

    db_path = pathlib.Path(args.db)
    if not db_path.exists():
        print(f"STOP: DB not found: {db_path}")
        sys.exit(1)

    print("Building P2 full-catalog visibility plan (read-only)...")
    plan = build_plan(db_path, pathlib.Path(args.p1_json))

    out_path = pathlib.Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))

    print(f"\nTotal entries:     {plan['total_entries']}")
    print(f"Registry count:    {plan['registry_count']}")
    print(f"Artifact-only:     {plan['artifact_only_count']}")
    print(f"By visibility state:")
    for k, v in plan["by_visibility_state"].items():
        print(f"  {k}: {v}")
    print(f"\nProduction rows unchanged: {plan['production_replay_rows_unchanged']}")
    print(f"DB write performed:        {plan['db_write_performed']}")
    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
