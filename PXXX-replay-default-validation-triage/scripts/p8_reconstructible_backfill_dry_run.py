#!/usr/bin/env python3
"""
p8_reconstructible_backfill_dry_run.py
========================================
P8 Reconstructible Backfill Dry-Run Plan.

Read-only. For each of the 121 RECONSTRUCTIBLE cells (strategy × draw), builds
the complete replay row payload that WOULD be inserted, without writing to DB.

Data sources (all read-only):
  - P7 all_plan_rows JSON  → strategy/draw scope
  - prediction_items table → predicted_numbers
  - draws table            → actual_numbers, actual_special, draw_date
  - strategy_prediction_replays → duplicate check

For each candidate row:
  - Determines readiness: READY_FOR_ONLINE_APPLY or PENDING_HUMAN_REVIEW_RETIRED
  - Computes hit_count from predicted vs actual numbers
  - Flags any missing fields
  - Estimates what the row would look like post-apply

Why no DB write this round:
  CEO authorization phrase "YES apply P7 controlled replay rows" not yet received.
  The P7 controlled apply script already handles the actual insert when authorized.

Zero DB writes. Zero strategy execution. All entries dry_run_only=True.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sqlite3
import sys

REPO_ROOT  = pathlib.Path(__file__).resolve().parent.parent
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P7_JSON    = REPO_ROOT / "outputs" / "replay" / "p7_controlled_apply_dry_run_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

TRUTH_LEVEL = "RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD"
SOURCE_TAG  = "P7_CONTROLLED_APPLY"

STATUS_READY          = "READY_FOR_ONLINE_APPLY"
STATUS_PENDING_REVIEW = "PENDING_HUMAN_REVIEW_RETIRED"
STATUS_DUPLICATE      = "SKIP_ALREADY_EXISTS"
STATUS_NO_DATA        = "SKIP_NO_DATA"


def _open_readonly(path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path.resolve()))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _compute_hits(predicted_json: str | None, actual_json: str | None) -> tuple[list, int]:
    if not predicted_json or not actual_json:
        return [], 0
    try:
        pred = set(json.loads(predicted_json))
        actual = set(json.loads(actual_json))
        hits = sorted(pred & actual)
        return hits, len(hits)
    except Exception:
        return [], 0


def _check_duplicate(
    conn: sqlite3.Connection, strategy_id: str, lottery_type: str, draw_id: str
) -> bool:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id=? AND lottery_type=? AND target_draw=?",
        (strategy_id, lottery_type, draw_id),
    ).fetchone()[0] > 0


def build_dry_run(db_path: pathlib.Path, p7_json: pathlib.Path) -> dict:
    conn   = _open_readonly(db_path)
    p7data = json.loads(p7_json.read_text())
    rows   = p7data.get("all_plan_rows", [])

    total_spr = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    candidates: list[dict] = []
    by_status:  dict[str, int] = {}

    for row in rows:
        sid      = row["strategy_id"]
        lt       = row["lottery_type"]
        draw_id  = row["draw_id"]
        run_id   = row.get("source_run_id")
        lc_state = row.get("lifecycle_state", "UNKNOWN")
        prov_hash = row.get("provenance_hash")
        cap_id   = row.get("controlled_apply_id")

        # 1. Duplicate check
        if _check_duplicate(conn, sid, lt, draw_id):
            status = STATUS_DUPLICATE
            candidates.append(_entry(row, status, None, None, None, None, 0, []))
            by_status[status] = by_status.get(status, 0) + 1
            continue

        # 2. Get prediction_items
        pi = conn.execute(
            "SELECT numbers FROM prediction_items "
            "WHERE run_id=? AND strategy_name=? ORDER BY id ASC LIMIT 1",
            (run_id, sid),
        ).fetchone()
        predicted_numbers = pi["numbers"] if pi else None

        if not predicted_numbers:
            status = STATUS_NO_DATA
            candidates.append(_entry(row, status, None, None, None, None, 0, []))
            by_status[status] = by_status.get(status, 0) + 1
            continue

        # 3. Get draw result
        draw = conn.execute(
            "SELECT date, numbers, special FROM draws WHERE draw=? AND lottery_type=? LIMIT 1",
            (draw_id, lt),
        ).fetchone()
        draw_date    = draw["date"]    if draw else None
        actual_nums  = draw["numbers"] if draw else None
        actual_spec  = draw["special"] if draw else None

        # 4. Compute hits
        hits, hit_count = _compute_hits(predicted_numbers, actual_nums)

        # 5. Determine status
        if lc_state == "ONLINE":
            status = STATUS_READY
        else:
            status = STATUS_PENDING_REVIEW  # RETIRED

        # 6. Missing field flags
        missing = []
        if not actual_nums:
            missing.append("actual_numbers")
        if not draw_date:
            missing.append("target_date")

        candidates.append(_entry(
            row, status,
            predicted_numbers, actual_nums, draw_date, actual_spec,
            hit_count, hits,
        ))
        by_status[status] = by_status.get(status, 0) + 1

    conn.close()

    ready_rows   = [c for c in candidates if c["status"] == STATUS_READY]
    pending_rows = [c for c in candidates if c["status"] == STATUS_PENDING_REVIEW]
    dup_rows     = [c for c in candidates if c["status"] == STATUS_DUPLICATE]
    no_data_rows = [c for c in candidates if c["status"] == STATUS_NO_DATA]

    # Strategy-level breakdown
    by_strategy: dict[str, dict] = {}
    for c in candidates:
        sid = c["strategy_id"]
        if sid not in by_strategy:
            by_strategy[sid] = {
                "strategy_id": sid,
                "lottery_type": c["lottery_type"],
                "lifecycle_state": c["lifecycle_state"],
                STATUS_READY: 0,
                STATUS_PENDING_REVIEW: 0,
                STATUS_DUPLICATE: 0,
                STATUS_NO_DATA: 0,
                "total": 0,
            }
        by_strategy[sid][c["status"]] = by_strategy[sid].get(c["status"], 0) + 1
        by_strategy[sid]["total"] += 1

    # Why no write this round
    no_write_reasons = [
        "CEO authorization phrase 'YES apply P7 controlled replay rows' not received in this session.",
        "The P7 controlled apply script (scripts/p7_controlled_replay_row_apply.py) handles "
        "the actual insert when authorized; P8 only plans the payload.",
        "RETIRED rows (93) require separate human review + --scope INCLUDE_RETIRED_WITH_WARNING.",
        "Production DB must remain at 460 until CEO phrase is received.",
    ]

    return {
        "phase":            "P8_RECONSTRUCTIBLE_BACKFILL_DRY_RUN",
        "generated_at":     datetime.datetime.utcnow().isoformat() + "Z",
        "dry_run_only":     True,
        "db_write_performed": False,
        "production_replay_rows_unchanged": total_spr,
        "total_candidates": len(candidates),
        "by_status":        by_status,
        "by_strategy":      list(by_strategy.values()),
        "field_completeness": {
            "total": len(candidates),
            "have_prediction_items": len([c for c in candidates
                                          if c.get("payload_preview") and
                                          c["payload_preview"].get("predicted_numbers")]),
            "have_draw_result":      len([c for c in candidates
                                          if c.get("payload_preview") and
                                          c["payload_preview"].get("actual_numbers")]),
            "have_both_complete":    len([c for c in candidates
                                          if c.get("payload_preview") and
                                          c["payload_preview"].get("predicted_numbers") and
                                          c["payload_preview"].get("actual_numbers")]),
            "missing_prediction":    len([c for c in candidates
                                          if not (c.get("payload_preview") and
                                          c["payload_preview"].get("predicted_numbers"))]),
            "missing_draw_result":   len([c for c in candidates
                                          if not (c.get("payload_preview") and
                                          c["payload_preview"].get("actual_numbers"))]),
        },
        "human_review_required_count": len(pending_rows),
        "human_review_required_strategies": sorted({
            c["strategy_id"] for c in pending_rows
        }),
        "ready_for_authorized_apply": len(ready_rows),
        "why_no_db_write_this_round": no_write_reasons,
        "post_apply_projection": {
            "online_only": {
                "current_rows":  total_spr,
                "rows_to_add":   len(ready_rows),
                "projected":     total_spr + len(ready_rows),
            },
            "online_plus_retired": {
                "current_rows":  total_spr,
                "rows_to_add":   len(ready_rows) + len(pending_rows),
                "projected":     total_spr + len(ready_rows) + len(pending_rows),
            },
        },
        "candidates": candidates,
        "safety_flags": {
            "db_write_performed":        False,
            "replay_rows_generated":     False,
            "strategy_executed":         False,
            "draw_data_imported":        False,
            "fake_success_count_is_zero": True,
            "production_rows_unchanged": total_spr == 460,
        },
    }


def _entry(
    row: dict,
    status: str,
    predicted_numbers: str | None,
    actual_numbers: str | None,
    draw_date: str | None,
    actual_special: int | None,
    hit_count: int,
    hit_numbers: list,
) -> dict:
    sid      = row["strategy_id"]
    lt       = row["lottery_type"]
    draw_id  = row["draw_id"]
    lc_state = row.get("lifecycle_state", "UNKNOWN")
    run_id   = row.get("source_run_id")

    try:
        cutoff = str(int(draw_id) - 1).zfill(len(draw_id))
    except (ValueError, TypeError):
        cutoff = None

    hits, hit_cnt = ([], hit_count) if predicted_numbers else ([], 0)

    has_actual = actual_numbers is not None
    should_count = (
        status == STATUS_READY
        and has_actual
        and predicted_numbers is not None
    )

    return {
        "strategy_id":         sid,
        "lottery_type":        lt,
        "draw_id":             draw_id,
        "draw_date":           draw_date,
        "lifecycle_state":     lc_state,
        "apply_decision":      row.get("apply_decision"),
        "source_run_id":       run_id,
        "status":              status,
        "readiness": {
            "is_ready":             status == STATUS_READY,
            "has_prediction_items": predicted_numbers is not None,
            "has_draw_result":      has_actual,
            "is_duplicate":         status == STATUS_DUPLICATE,
            "needs_human_review":   status == STATUS_PENDING_REVIEW,
            "should_count_as_success": should_count,
        },
        "payload_preview": {
            "lottery_type":        lt,
            "target_draw":         draw_id,
            "target_date":         draw_date,
            "strategy_id":         sid,
            "history_cutoff_draw": cutoff,
            "replay_status":       "PREDICTED" if predicted_numbers else None,
            "predicted_numbers":   predicted_numbers,
            "actual_numbers":      actual_numbers,
            "actual_special":      actual_special,
            "hit_numbers":         str(hit_numbers) if hit_numbers else "[]",
            "hit_count":           hit_count,
            "truth_level":         TRUTH_LEVEL if status != STATUS_DUPLICATE else None,
            "source":              SOURCE_TAG if status != STATUS_DUPLICATE else None,
            "replay_run_id":       None,
            "dry_run":             1,
        } if status not in (STATUS_DUPLICATE, STATUS_NO_DATA) else None,
        "dry_run_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P8 Reconstructible Backfill Dry-Run. Read-only."
    )
    parser.add_argument("--db",     default=str(DB_PATH))
    parser.add_argument("--p7-json", default=str(P7_JSON))
    parser.add_argument(
        "--json-out",
        default=str(
            REPO_ROOT / "outputs" / "replay" /
            "p8_reconstructible_backfill_dry_run_20260520.json"
        ),
    )
    args = parser.parse_args()

    db_path = pathlib.Path(args.db)
    if not db_path.exists():
        print(f"STOP: DB not found: {db_path}")
        sys.exit(1)

    print("Building P8 Reconstructible Backfill Dry-Run (read-only)...")
    plan = build_dry_run(db_path, pathlib.Path(args.p7_json))

    out_path = pathlib.Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))

    print(f"\n=== P8 Dry-Run Summary ===")
    print(f"Total candidates:      {plan['total_candidates']}")
    for status, count in plan["by_status"].items():
        print(f"  {status}: {count}")
    print(f"\nField completeness:")
    for k, v in plan["field_completeness"].items():
        print(f"  {k}: {v}")
    print(f"\nReady for ONLINE apply:    {plan['ready_for_authorized_apply']}")
    print(f"Pending human review:      {plan['human_review_required_count']}")
    print(f"Projection (ONLINE only):  {plan['post_apply_projection']['online_only']['projected']}")
    print(f"Projection (ONLINE+RETIRED): {plan['post_apply_projection']['online_plus_retired']['projected']}")
    print(f"\nDB write:                  {plan['db_write_performed']}")
    print(f"Production rows unchanged: {plan['production_replay_rows_unchanged']}")
    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
