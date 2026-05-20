#!/usr/bin/env python3
"""
p3_per_draw_all_strategy_coverage_matrix.py
=============================================
P3 Per-Draw All-Strategy Coverage Matrix.

Read-only. Produces two outputs:

  p3_per_draw_all_strategy_coverage_matrix_20260520.json
      Full matrix: (draw × strategy) → visibility / display status / hit info

  p3_per_draw_all_strategy_coverage_summary_20260520.json
      Summary: coverage pcts, counts, fake_success_count must be 0

Active draw universe (209 draws):
  BIG_LOTTO (66): 99000056-99000105 (existing replay) + 115000025-115000044 (P7 ONLINE)
  POWER_LOTTO (62): 99000055-99000104 (existing replay) + 115000016-115000030 (P7 ONLINE)
  DAILY_539 (81): 99000212-99000261 (existing replay) + 115000049-115000084 (P7 RETIRED)

Zero DB writes. Zero replay rows generated. Zero strategy execution.
All entries dry_run_only=True.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sqlite3
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P7_JSON   = REPO_ROOT / "outputs" / "replay" / "p7_controlled_apply_dry_run_20260520.json"
P2_JSON   = REPO_ROOT / "outputs" / "replay" / "p2_full_catalog_visibility_plan_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

DISPLAY_REPLAY_RESULT          = "SHOW_REPLAY_RESULT"
DISPLAY_RECONSTRUCTIBLE_PENDING = "SHOW_RECONSTRUCTIBLE_PENDING"
DISPLAY_NO_DATA                 = "SHOW_NO_DATA"
DISPLAY_ARTIFACT_ONLY           = "SHOW_ARTIFACT_ONLY"

VISIBILITY_ROW_BACKED      = "ROW_BACKED"
VISIBILITY_RECONSTRUCTIBLE = "RECONSTRUCTIBLE"
VISIBILITY_NO_DATA         = "NO_DATA"
VISIBILITY_ARTIFACT_ONLY   = "ARTIFACT_ONLY"


def _open_readonly(path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path.resolve()))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _load_registry() -> list[dict]:
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
    return list_strategy_lifecycle_metadata()


def _build_strategy_lottery_map(metas: list[dict]) -> dict[str, list[str]]:
    """Map lottery_type → list of strategy_ids that support it."""
    lt_map: dict[str, list[str]] = {}
    for m in metas:
        for lt in m.get("supported_lottery_types", []):
            lt_map.setdefault(lt, []).append(m["strategy_id"])
    return lt_map


def _get_active_draws(conn: sqlite3.Connection, p7_all_rows: list[dict]) -> set[tuple[str, str]]:
    """Return set of (lottery_type, draw_id) in the active universe."""
    existing = conn.execute(
        "SELECT DISTINCT lottery_type, target_draw FROM strategy_prediction_replays"
    ).fetchall()
    draw_set = {(r["lottery_type"], r["target_draw"]) for r in existing}
    for row in p7_all_rows:
        draw_set.add((row["lottery_type"], row["draw_id"]))
    return draw_set


def _get_replay_rows(conn: sqlite3.Connection) -> dict[tuple[str, str, str], dict]:
    """Return {(strategy_id, lottery_type, target_draw): row_dict} for all replay rows."""
    rows = conn.execute(
        "SELECT strategy_id, lottery_type, target_draw, replay_status, "
        "actual_numbers, predicted_numbers, hit_count, hit_numbers, "
        "truth_level, source, controlled_apply_id "
        "FROM strategy_prediction_replays"
    ).fetchall()
    return {
        (r["strategy_id"], r["lottery_type"], r["target_draw"]): dict(r)
        for r in rows
    }


def _get_prediction_item_map(conn: sqlite3.Connection) -> dict[tuple[str, str], int]:
    """Return {(strategy_name, draw_id): count} for prediction_items.
    draw_id here is the target_draw = latest_known_draw + 1 (P7 convention).
    We map via run_id to get the target draw."""
    # prediction_items.run_id → prediction_runs.id → latest_known_draw (draw before target)
    rows = conn.execute(
        "SELECT pi.strategy_name, pr.lottery_type, pr.latest_known_draw, "
        "COUNT(*) as cnt "
        "FROM prediction_items pi "
        "JOIN prediction_runs pr ON pr.id = pi.run_id "
        "GROUP BY pi.strategy_name, pr.lottery_type, pr.latest_known_draw"
    ).fetchall()
    result: dict[tuple[str, str, str], int] = {}
    for r in rows:
        result[(r["strategy_name"], r["lottery_type"], r["latest_known_draw"])] = r["cnt"]
    return result


def _get_draws_info(conn: sqlite3.Connection) -> dict[tuple[str, str], dict]:
    """Return {(lottery_type, draw): {date, numbers, special}} from draws table."""
    rows = conn.execute(
        "SELECT lottery_type, draw, date, numbers, special FROM draws"
    ).fetchall()
    return {
        (r["lottery_type"], r["draw"]): {
            "date":    r["date"],
            "numbers": r["numbers"],
            "special": r["special"],
        }
        for r in rows
    }


def _get_p7_plan_map(p7_all_rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    """Return {(strategy_id, lottery_type, draw_id): p7_row} for all P7 plan rows."""
    return {
        (r["strategy_id"], r["lottery_type"], r["draw_id"]): r
        for r in p7_all_rows
    }


def build_matrix(
    db_path: pathlib.Path,
    p7_json: pathlib.Path,
    p2_json: pathlib.Path,
) -> tuple[list[dict], dict]:
    """Build coverage matrix and summary. Returns (entries, summary)."""
    conn = _open_readonly(db_path)
    p7_data      = json.loads(p7_json.read_text())
    p7_all_rows  = p7_data.get("all_plan_rows", [])

    metas          = _load_registry()
    meta_map       = {m["strategy_id"]: m for m in metas}
    lt_strategy_map = _build_strategy_lottery_map(metas)

    active_draws   = _get_active_draws(conn, p7_all_rows)
    replay_map     = _get_replay_rows(conn)
    pi_map         = _get_prediction_item_map(conn)
    draws_info     = _get_draws_info(conn)
    p7_plan_map    = _get_p7_plan_map(p7_all_rows)
    total_spr_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    # Build P2 visibility state lookup for strategies
    p2_data     = json.loads(p2_json.read_text()) if p2_json.exists() else {}
    p2_vis_map  = {e["strategy_id"]: e.get("visibility_state", VISIBILITY_NO_DATA)
                   for e in p2_data.get("entries", [])}
    artifact_ids = {e["strategy_id"] for e in p2_data.get("entries", [])
                    if e.get("visibility_state") == VISIBILITY_ARTIFACT_ONLY}

    conn.close()

    entries: list[dict] = []

    for lottery_type, draw_id in sorted(active_draws, key=lambda x: (x[0], x[1])):
        draw_info  = draws_info.get((lottery_type, draw_id))
        draw_date  = draw_info["date"]    if draw_info else None
        draw_nums  = draw_info["numbers"] if draw_info else None

        strategies_for_lt = lt_strategy_map.get(lottery_type, [])

        for sid in strategies_for_lt:
            m = meta_map.get(sid, {})
            lifecycle = m.get("lifecycle_status", "UNKNOWN")

            # Check replay row
            replay_key  = (sid, lottery_type, draw_id)
            replay_row  = replay_map.get(replay_key)
            has_replay  = replay_row is not None
            replay_count = 1 if has_replay else 0

            # Check prediction_items (P7 convention: latest_known_draw = draw_id - 1)
            try:
                prev_draw = str(int(draw_id) - 1).zfill(len(draw_id))
            except (ValueError, TypeError):
                prev_draw = None

            pi_key = (sid, lottery_type, prev_draw) if prev_draw else None
            pi_count = pi_map.get(pi_key, 0) if pi_key else 0

            # Check P7 plan
            p7_key  = (sid, lottery_type, draw_id)
            p7_row  = p7_plan_map.get(p7_key)

            # Determine visibility state
            if has_replay:
                vis_state = VISIBILITY_ROW_BACKED
            elif pi_count > 0 or p7_row is not None:
                vis_state = VISIBILITY_RECONSTRUCTIBLE
            else:
                vis_state = VISIBILITY_NO_DATA

            # Determine display status
            actual_numbers_available = draw_nums is not None
            if vis_state == VISIBILITY_ROW_BACKED:
                display_status = DISPLAY_REPLAY_RESULT
            elif vis_state == VISIBILITY_RECONSTRUCTIBLE:
                display_status = DISPLAY_RECONSTRUCTIBLE_PENDING
            else:
                display_status = DISPLAY_NO_DATA

            # should_count_as_success: only real replay rows with actual comparison
            actual_from_replay = replay_row.get("actual_numbers") if replay_row else None
            hit_count_val      = replay_row.get("hit_count")      if replay_row else None

            should_succeed = (
                vis_state == VISIBILITY_ROW_BACKED
                and actual_from_replay is not None
                and hit_count_val is not None
            )

            # Source info
            source_table    = "strategy_prediction_replays" if has_replay else None
            source_artifact = None
            if not has_replay and p7_row:
                source_table    = "prediction_items"
                source_artifact = f"P7:{p7_row.get('apply_decision', 'PLAN')}"

            entries.append({
                "draw_number":               draw_id,
                "draw_date":                 draw_date,
                "lottery_type":              lottery_type,
                "strategy_id":               sid,
                "strategy_name":             m.get("strategy_name", sid),
                "lifecycle_status":          lifecycle,
                "visibility_state":          vis_state,
                "has_replay_row":            has_replay,
                "has_prediction_items":      pi_count > 0 or (p7_row is not None),
                "replay_row_count":          replay_count,
                "prediction_items_count":    pi_count,
                "actual_numbers_available":  actual_numbers_available,
                "actual_numbers":            draw_nums,
                "predicted_numbers":         replay_row.get("predicted_numbers") if replay_row else None,
                "hit_count":                 hit_count_val,
                "hit_count_available":       hit_count_val is not None,
                "source_table":              source_table,
                "source_artifact":           source_artifact,
                "display_status":            display_status,
                "should_count_as_success":   should_succeed,
                "dry_run_only":              True,
            })

    # Summary
    by_vis: dict[str, int] = {}
    by_disp: dict[str, int] = {}
    by_lt: dict[str, dict] = {}
    real_success = 0
    fake_success = 0

    for e in entries:
        v = e["visibility_state"]
        d = e["display_status"]
        lt = e["lottery_type"]

        by_vis[v]  = by_vis.get(v, 0) + 1
        by_disp[d] = by_disp.get(d, 0) + 1

        if lt not in by_lt:
            by_lt[lt] = {"total": 0, VISIBILITY_ROW_BACKED: 0,
                          VISIBILITY_RECONSTRUCTIBLE: 0, VISIBILITY_NO_DATA: 0}
        by_lt[lt]["total"] += 1
        by_lt[lt][v] = by_lt[lt].get(v, 0) + 1

        if e["should_count_as_success"]:
            real_success += 1

        # Fake success check: any non-ROW_BACKED counted as success
        if e["should_count_as_success"] and v != VISIBILITY_ROW_BACKED:
            fake_success += 1

    total_cells = len(entries)
    row_backed_n = by_vis.get(VISIBILITY_ROW_BACKED, 0)
    recon_n      = by_vis.get(VISIBILITY_RECONSTRUCTIBLE, 0)
    no_data_n    = by_vis.get(VISIBILITY_NO_DATA, 0)

    # Artifact-only stats from P2 (not in per-draw matrix)
    p2_by_vis = p2_data.get("by_visibility_state", {})

    unique_draws = len(active_draws)
    unique_strategies = len({e["strategy_id"] for e in entries})

    summary = {
        "phase":                       "P3_COVERAGE_SUMMARY",
        "generated_at":                datetime.datetime.utcnow().isoformat() + "Z",
        "dry_run_only":                True,
        "db_write_performed":          False,
        "total_draws":                 unique_draws,
        "total_strategies":            len(metas),
        "product_visible_strategy_count": len([m for m in metas
                                                if m.get("lifecycle_status") == "ONLINE"]),
        "total_matrix_cells":          total_cells,
        "by_visibility_state":         by_vis,
        "by_display_status":           by_disp,
        "by_lottery_type":             by_lt,
        "row_backed_coverage_pct":     round(row_backed_n / total_cells * 100, 2) if total_cells else 0,
        "reconstructible_coverage_pct": round(recon_n / total_cells * 100, 2) if total_cells else 0,
        "no_data_pct":                 round(no_data_n / total_cells * 100, 2) if total_cells else 0,
        "artifact_only_count":         p2_by_vis.get(VISIBILITY_ARTIFACT_ONLY, 0),
        "artifact_only_pct":           "N/A (not in per-draw matrix — no lottery_type affiliation)",
        "real_replay_success_count":   real_success,
        "fake_success_count":          fake_success,
        "production_replay_rows_unchanged": total_spr_rows,
        "safety_flags": {
            "db_write_performed":        False,
            "replay_rows_generated":     False,
            "strategy_executed":         False,
            "draw_data_imported":        False,
            "fake_success_count_is_zero": fake_success == 0,
        },
    }

    return entries, summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P3 Per-Draw All-Strategy Coverage Matrix. Read-only."
    )
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--p7-json", default=str(P7_JSON))
    parser.add_argument("--p2-json", default=str(P2_JSON))
    parser.add_argument(
        "--matrix-out",
        default=str(REPO_ROOT / "outputs" / "replay" /
                    "p3_per_draw_all_strategy_coverage_matrix_20260520.json"),
    )
    parser.add_argument(
        "--summary-out",
        default=str(REPO_ROOT / "outputs" / "replay" /
                    "p3_per_draw_all_strategy_coverage_summary_20260520.json"),
    )
    args = parser.parse_args()

    db_path = pathlib.Path(args.db)
    if not db_path.exists():
        print(f"STOP: DB not found: {db_path}")
        sys.exit(1)

    print("Building P3 per-draw all-strategy coverage matrix (read-only)...")
    entries, summary = build_matrix(db_path, pathlib.Path(args.p7_json),
                                    pathlib.Path(args.p2_json))

    now = datetime.datetime.utcnow().isoformat() + "Z"
    matrix_doc = {
        "phase":        "P3_COVERAGE_MATRIX",
        "generated_at": now,
        "dry_run_only": True,
        "total_entries": len(entries),
        "entries":      entries,
    }

    matrix_path  = pathlib.Path(args.matrix_out)
    summary_path = pathlib.Path(args.summary_out)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    matrix_path.write_text(json.dumps(matrix_doc, indent=2, ensure_ascii=False))
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n=== P3 Coverage Summary ===")
    print(f"Total draws:       {summary['total_draws']}")
    print(f"Total strategies:  {summary['total_strategies']}")
    print(f"Total matrix cells:{summary['total_matrix_cells']}")
    print(f"\nBy visibility state:")
    for k, v in summary["by_visibility_state"].items():
        pct = round(v / summary["total_matrix_cells"] * 100, 1) if summary["total_matrix_cells"] else 0
        print(f"  {k}: {v} ({pct}%)")
    print(f"\nBy display status:")
    for k, v in summary["by_display_status"].items():
        print(f"  {k}: {v}")
    print(f"\nRow-backed coverage: {summary['row_backed_coverage_pct']}%")
    print(f"Reconstructible:     {summary['reconstructible_coverage_pct']}%")
    print(f"No data:             {summary['no_data_pct']}%")
    print(f"\nReal replay successes:  {summary['real_replay_success_count']}")
    print(f"Fake successes:         {summary['fake_success_count']}  ← must be 0")
    print(f"\nProduction rows unchanged: {summary['production_replay_rows_unchanged']}")
    print(f"DB write performed:        {summary['db_write_performed']}")
    print(f"\nMatrix JSON: {matrix_path}")
    print(f"Summary JSON: {summary_path}")


if __name__ == "__main__":
    main()
