#!/usr/bin/env python3
"""
P3B-A: Dry-run script for resolving TRUE STALE BIG_LOTTO prediction_items.

Reads prediction_items, fetches actual draw results, computes hit counts,
and determines if replay rows would be inserted — without writing to DB.

Usage:
    python3 scripts/p3ba_resolve_stale_prediction_items_dryrun.py \
        --db lottery_api/data/lottery_v2.db \
        --strategy-id ts3_regime_3bet \
        --prediction-item-ids 1069,1070,1071,1093,1094,1095 \
        --json-out outputs/replay/p3ba_big_lotto_stale_resolution_dryrun_20260515.json \
        --csv-out outputs/replay/p3ba_big_lotto_stale_resolution_dryrun_20260515.csv
"""

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_STRATEGY = "ts3_regime_3bet"
FINAL_CLASSIFICATION_DRY_RUN_READY = "P3BA_BIG_LOTTO_STALE_RESOLUTION_DRYRUN_READY"
FINAL_CLASSIFICATION_BLOCKED = "BLOCKED"

# run_id -> target_draw mapping (from P3 audit)
RUN_TARGET_DRAW_MAP = {
    167: "115000049",
    175: "115000050",
}

# run_id -> snapshot_source
RUN_SNAPSHOT_SOURCE_MAP = {
    167: "VALID",
    175: "RECONSTRUCTED",
}


def parse_args():
    p = argparse.ArgumentParser(description="P3B-A dry-run: resolve STALE BIG_LOTTO prediction_items")
    p.add_argument("--db", required=True, help="Path to lottery_v2.db")
    p.add_argument("--strategy-id", required=True, help="Expected strategy_name")
    p.add_argument("--prediction-item-ids", required=True,
                   help="Comma-separated prediction_item IDs")
    p.add_argument("--json-out", required=True, help="Output JSON path")
    p.add_argument("--csv-out", required=True, help="Output CSV path")
    return p.parse_args()


def open_readonly(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def parse_numbers(raw) -> list[int]:
    """Parse numbers from JSON array string or comma-separated string."""
    if raw is None:
        return []
    s = str(raw).strip()
    if s.startswith("["):
        return [int(x) for x in json.loads(s)]
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def check_existing_replay(cur: sqlite3.Cursor, item_id: int) -> list[dict]:
    """Check if replay rows already exist for this prediction_item_id via provenance_source."""
    rows = cur.execute(
        "SELECT id, controlled_apply_id, target_draw, hit_count, truth_level, dry_run_only "
        "FROM strategy_prediction_replays WHERE provenance_source LIKE ?",
        (f'%"prediction_item_id": {item_id}%',)
    ).fetchall()
    return [dict(r) for r in rows]


def main():
    args = parse_args()

    item_ids = [int(x.strip()) for x in args.prediction_item_ids.split(",")]
    db_path = args.db

    if not Path(db_path).exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = open_readonly(db_path)
    cur = conn.cursor()

    run_at = datetime.now(timezone.utc).isoformat()
    results = []
    blocked_reasons = []

    print(f"[P3B-A DRY-RUN] started at {run_at}")
    print(f"[P3B-A DRY-RUN] target items: {item_ids}")
    print(f"[P3B-A DRY-RUN] expected strategy: {args.strategy_id}")
    print()

    for item_id in item_ids:
        print(f"--- item {item_id} ---")

        # Load prediction_item
        row = cur.execute(
            "SELECT id, run_id, status, numbers, special, strategy_name "
            "FROM prediction_items WHERE id=?",
            (item_id,)
        ).fetchone()

        if row is None:
            msg = f"item {item_id}: NOT FOUND in prediction_items"
            print(f"  BLOCKED: {msg}")
            blocked_reasons.append(msg)
            results.append({
                "item_id": item_id,
                "status": "BLOCKED",
                "block_reason": msg,
            })
            continue

        item = dict(row)
        print(f"  prediction_item: status={item['status']} run_id={item['run_id']} strategy_name={item['strategy_name']}")

        # Determine target draw from run_id map
        run_id = item["run_id"]
        target_draw = RUN_TARGET_DRAW_MAP.get(run_id)
        snapshot_source = RUN_SNAPSHOT_SOURCE_MAP.get(run_id, "UNKNOWN")

        if target_draw is None:
            msg = f"item {item_id}: run_id={run_id} not in known run->draw map"
            print(f"  BLOCKED: {msg}")
            blocked_reasons.append(msg)
            results.append({
                "item_id": item_id,
                "run_id": run_id,
                "status": "BLOCKED",
                "block_reason": msg,
            })
            continue

        # Verify strategy from prediction_runs
        run_row = cur.execute(
            "SELECT strategy_name, snapshot_source, latest_known_draw FROM prediction_runs WHERE id=?",
            (run_id,)
        ).fetchone()

        actual_strategy = None
        if run_row:
            actual_strategy = run_row["strategy_name"]
            db_snapshot_source = run_row["snapshot_source"]
            if db_snapshot_source != snapshot_source:
                print(f"  WARNING: snapshot_source mismatch: expected={snapshot_source} db={db_snapshot_source}")
                snapshot_source = db_snapshot_source
        else:
            msg = f"item {item_id}: prediction_runs row not found for run_id={run_id}"
            print(f"  BLOCKED: {msg}")
            blocked_reasons.append(msg)
            results.append({
                "item_id": item_id,
                "run_id": run_id,
                "status": "BLOCKED",
                "block_reason": msg,
            })
            continue

        # Strategy validation
        strategy_valid = (actual_strategy == args.strategy_id)
        if not strategy_valid:
            print(f"  WARNING: strategy mismatch: expected={args.strategy_id} actual={actual_strategy}")

        # Fetch actual draw result
        draw_row = cur.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type='BIG_LOTTO' AND CAST(draw AS INTEGER)=CAST(? AS INTEGER)",
            (target_draw,)
        ).fetchone()

        if draw_row is None:
            msg = f"item {item_id}: target_draw={target_draw} not found in draws table"
            print(f"  BLOCKED: {msg}")
            blocked_reasons.append(msg)
            results.append({
                "item_id": item_id,
                "run_id": run_id,
                "target_draw": target_draw,
                "status": "BLOCKED",
                "block_reason": msg,
            })
            continue

        actual_numbers = parse_numbers(draw_row["numbers"])
        actual_special = draw_row["special"]
        actual_date = draw_row["date"]

        # Parse predicted numbers
        predicted_numbers = parse_numbers(item["numbers"])

        # Compute hit_count and matched_numbers
        actual_set = set(actual_numbers)
        predicted_set = set(predicted_numbers)
        matched = sorted(actual_set & predicted_set)
        hit_count = len(matched)

        # Determine truth_level
        if snapshot_source == "RECONSTRUCTED":
            truth_level = "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE"
        else:
            truth_level = "REGENERATED_RETROSPECTIVE"

        # Risk flags
        risk_flags = []
        if snapshot_source == "RECONSTRUCTED":
            risk_flags.append("RECONSTRUCTED_SNAPSHOT_RISK")
        if item["status"] != "PENDING":
            risk_flags.append(f"UNEXPECTED_STATUS_{item['status']}")
        if not strategy_valid:
            risk_flags.append(f"STRATEGY_MISMATCH_{actual_strategy}")

        # Idempotency check
        existing_replays = check_existing_replay(cur, item_id)
        already_exists = len(existing_replays) > 0
        would_insert = not already_exists

        print(f"  target_draw: {target_draw} ({actual_date})")
        print(f"  predicted:   {predicted_numbers}")
        print(f"  actual:      {actual_numbers} (SP={actual_special})")
        print(f"  hit_count:   {hit_count}  matched={matched}")
        print(f"  truth_level: {truth_level}")
        print(f"  risk_flags:  {risk_flags}")
        print(f"  existing_replays: {existing_replays}")
        print(f"  would_insert: {would_insert}")
        print()

        results.append({
            "item_id": item_id,
            "run_id": run_id,
            "status": "OK",
            "item_db_status": item["status"],
            "strategy_name": actual_strategy,
            "strategy_valid": strategy_valid,
            "snapshot_source": snapshot_source,
            "target_draw": target_draw,
            "target_date": actual_date,
            "predicted_numbers": predicted_numbers,
            "actual_numbers": actual_numbers,
            "actual_special": actual_special,
            "hit_count": hit_count,
            "matched_numbers": matched,
            "truth_level": truth_level,
            "risk_flags": risk_flags,
            "existing_replay_ids": [r["id"] for r in existing_replays],
            "existing_controlled_apply_ids": list({r["controlled_apply_id"] for r in existing_replays}),
            "already_exists": already_exists,
            "would_insert": would_insert,
        })

    conn.close()

    # Determine final classification
    blocked_items = [r for r in results if r.get("status") == "BLOCKED"]
    if blocked_items or blocked_reasons:
        final_classification = FINAL_CLASSIFICATION_BLOCKED
    else:
        final_classification = FINAL_CLASSIFICATION_DRY_RUN_READY

    summary = {
        "run_at": run_at,
        "db_written": False,
        "db_path": db_path,
        "strategy_id": args.strategy_id,
        "target_item_ids": item_ids,
        "total_items": len(item_ids),
        "ok_items": len([r for r in results if r.get("status") == "OK"]),
        "blocked_items": len(blocked_items),
        "would_insert_count": len([r for r in results if r.get("would_insert") is True]),
        "already_exists_count": len([r for r in results if r.get("already_exists") is True]),
        "blocked_reasons": blocked_reasons,
        "final_classification": final_classification,
        "items": results,
    }

    # Write JSON
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.json_out, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[P3B-A DRY-RUN] JSON written: {args.json_out}")

    # Write CSV
    csv_fields = [
        "item_id", "run_id", "target_draw", "target_date",
        "predicted_numbers", "actual_numbers", "actual_special",
        "hit_count", "matched_numbers", "truth_level",
        "risk_flags", "already_exists", "would_insert",
        "existing_replay_ids", "existing_controlled_apply_ids",
    ]
    Path(args.csv_out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.csv_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row_out = dict(r)
            for field in ["predicted_numbers", "actual_numbers", "matched_numbers", "risk_flags",
                          "existing_replay_ids", "existing_controlled_apply_ids"]:
                if field in row_out:
                    row_out[field] = json.dumps(row_out[field])
            writer.writerow(row_out)
    print(f"[P3B-A DRY-RUN] CSV written: {args.csv_out}")

    print(f"\n[P3B-A DRY-RUN] final_classification: {final_classification}")
    print(f"[P3B-A DRY-RUN] db_written: False")

    if final_classification == FINAL_CLASSIFICATION_BLOCKED:
        sys.exit(1)


if __name__ == "__main__":
    main()
