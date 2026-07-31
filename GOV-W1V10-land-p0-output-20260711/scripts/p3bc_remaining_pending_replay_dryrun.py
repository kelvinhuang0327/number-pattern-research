#!/usr/bin/env python3
"""
P3B-C Remaining Pending Replay Dry-Run

Evaluates prediction_items 1087,1088,1089,1072,1073,1074 against
their target draws (now imported). Reads DB only. No writes.

Output:
  - JSON: summary with dry-run results per item
  - CSV:  per-item rows

Final classification expected:
  P3BC_REMAINING_PENDING_REPLAY_DRYRUN_READY  (if all 6 eligible, none blocked)
"""
import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone


def parse_args():
    p = argparse.ArgumentParser(description="P3B-C Remaining Pending Replay Dry-Run")
    p.add_argument("--db", required=True)
    p.add_argument("--prediction-item-ids", required=True, help="comma-separated IDs")
    p.add_argument("--json-out", required=True)
    p.add_argument("--csv-out", required=True)
    return p.parse_args()


def evaluate_item(cur, item_id: int, item_row: dict) -> dict:
    """Evaluate a single prediction item against its target draw."""
    run_id = item_row["run_id"]

    # Get prediction_run to find target draw
    run = cur.execute(
        "SELECT * FROM prediction_runs WHERE id=?", (run_id,)
    ).fetchone()

    if not run:
        return {
            "item_id": item_id,
            "status": "BLOCKED",
            "reason": f"prediction_run {run_id} not found",
            "eligible": False,
        }

    run = dict(run)
    lottery_type = run.get("lottery_type")
    # target_draw = latest_known_draw + 1
    latest_known = run.get("latest_known_draw") or run.get("target_draw") or run.get("draw")
    try:
        target_draw = str(int(latest_known) + 1)
    except (TypeError, ValueError):
        target_draw = None

    # Try to find the target draw
    draw_row = cur.execute(
        """
        SELECT draw, date, lottery_type, numbers, special
        FROM draws
        WHERE lottery_type=?
          AND CAST(draw AS INTEGER)=CAST(? AS INTEGER)
        """,
        (lottery_type, target_draw),
    ).fetchone()

    if not draw_row:
        return {
            "item_id": item_id,
            "lottery_type": lottery_type,
            "target_draw": target_draw,
            "status": "BLOCKED",
            "reason": f"draw not found in DB: {lottery_type} {target_draw}",
            "eligible": False,
        }

    draw_row = dict(draw_row)
    actual_numbers = json.loads(draw_row["numbers"])
    actual_special = draw_row["special"]

    # Get predicted numbers for this item
    predicted_numbers_raw = item_row.get("numbers") or item_row.get("predicted_numbers")
    predicted_special = item_row.get("special") or item_row.get("predicted_special")

    if not predicted_numbers_raw:
        return {
            "item_id": item_id,
            "lottery_type": lottery_type,
            "target_draw": target_draw,
            "status": "BLOCKED",
            "reason": "no predicted numbers on item",
            "eligible": False,
        }

    try:
        predicted_numbers = json.loads(predicted_numbers_raw)
    except Exception:
        try:
            predicted_numbers = list(predicted_numbers_raw) if not isinstance(predicted_numbers_raw, list) else predicted_numbers_raw
        except Exception:
            predicted_numbers = []

    if not predicted_numbers:
        return {
            "item_id": item_id,
            "lottery_type": lottery_type,
            "target_draw": target_draw,
            "status": "BLOCKED",
            "reason": "could not parse predicted_numbers",
            "eligible": False,
        }

    # Calculate hits
    matched = sorted(set(predicted_numbers) & set(actual_numbers))
    hit_count = len(matched)
    special_hit = 1 if (predicted_special and actual_special and predicted_special == actual_special) else 0

    return {
        "item_id": item_id,
        "lottery_type": lottery_type,
        "target_draw": str(target_draw),
        "target_date": draw_row["date"],
        "predicted_numbers": sorted(predicted_numbers),
        "actual_numbers": sorted(actual_numbers),
        "matched": matched,
        "hit_count": hit_count,
        "special_predicted": predicted_special,
        "special_actual": actual_special,
        "special_hit": special_hit,
        "status": "ELIGIBLE",
        "eligible": True,
        "replay_rows_inserted": False,
        "prediction_items_modified": False,
    }


def main():
    args = parse_args()
    item_ids = [int(x.strip()) for x in args.prediction_item_ids.split(",")]

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Verify DB is read-only for safety
    replay_before = cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    items_pending_before = cur.execute(
        f"SELECT COUNT(*) FROM prediction_items WHERE id IN ({','.join(['?']*len(item_ids))}) AND status='PENDING'",
        item_ids,
    ).fetchone()[0]

    print(f"[PREFLIGHT] replay_total={replay_before}, pending_items={items_pending_before}")
    print(f"[PREFLIGHT] evaluating {len(item_ids)} items: {item_ids}")

    # Fetch all items
    placeholders = ",".join(["?"] * len(item_ids))
    items = cur.execute(
        f"SELECT * FROM prediction_items WHERE id IN ({placeholders}) ORDER BY id",
        item_ids,
    ).fetchall()

    if len(items) != len(item_ids):
        found_ids = {r["id"] for r in items}
        missing = [i for i in item_ids if i not in found_ids]
        print(f"FATAL: missing prediction_items: {missing}")
        sys.exit(1)

    results = []
    for item_row in items:
        item_dict = dict(item_row)
        result = evaluate_item(cur, item_dict["id"], item_dict)
        results.append(result)
        status = result["status"]
        if result["eligible"]:
            print(f"  [ELIGIBLE] item {result['item_id']} → {result['lottery_type']} {result['target_draw']} hits={result['hit_count']} matched={result['matched']}")
        else:
            print(f"  [BLOCKED] item {result['item_id']} → {result.get('reason')}")

    conn.close()

    eligible_count = sum(1 for r in results if r["eligible"])
    blocked_count = sum(1 for r in results if not r["eligible"])

    if blocked_count == 0 and eligible_count == len(item_ids):
        classification = "P3BC_REMAINING_PENDING_REPLAY_DRYRUN_READY"
    else:
        classification = "P3BC_REMAINING_PENDING_REPLAY_DRYRUN_BLOCKED"

    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "controlled_import_id": "P3BC_20260516",
        "db": args.db,
        "item_ids": item_ids,
        "eligible_count": eligible_count,
        "blocked_count": blocked_count,
        "replay_rows_inserted": False,
        "prediction_items_modified": False,
        "results": results,
        "final_classification": classification,
    }

    import os
    os.makedirs(os.path.dirname(args.json_out) if os.path.dirname(args.json_out) else ".", exist_ok=True)
    with open(args.json_out, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"[JSON] written to {args.json_out}")

    os.makedirs(os.path.dirname(args.csv_out) if os.path.dirname(args.csv_out) else ".", exist_ok=True)
    csv_fields = [
        "item_id","lottery_type","target_draw","target_date",
        "predicted_numbers","actual_numbers","matched",
        "hit_count","special_predicted","special_actual","special_hit",
        "status","eligible","replay_rows_inserted","prediction_items_modified",
    ]
    with open(args.csv_out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        for r in results:
            row = dict(r)
            for k in ("predicted_numbers","actual_numbers","matched"):
                row[k] = json.dumps(row.get(k, []))
            w.writerow(row)
    print(f"[CSV] written to {args.csv_out}")

    print()
    print(f"  eligible_count          : {eligible_count}")
    print(f"  blocked_count           : {blocked_count}")
    print(f"  replay_rows_inserted    : False")
    print(f"  prediction_items_modified: False")
    print(f"  final_classification    : {classification}")
    print()
    print(classification)


if __name__ == "__main__":
    main()
