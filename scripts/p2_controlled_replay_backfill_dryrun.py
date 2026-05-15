#!/usr/bin/env python3
"""
P2 Controlled Replay Backfill Dry-run Script
=============================================
Strategy : ts3_regime_3bet (BIG_LOTTO)
Mode     : DRY_RUN ONLY

Safety guarantees
-----------------
- Opens DB with mode=ro (read-only URI)
- Never writes to strategy_prediction_replays
- Never updates prediction_items
- Never modifies prediction_runs
- Outputs JSON preview and CSV preview only

Usage
-----
python3 scripts/p2_controlled_replay_backfill_dryrun.py \\
  --db lottery_api/data/lottery_v2.db \\
  --strategy-id ts3_regime_3bet \\
  --prediction-item-ids 1069,1070,1071,1090,1091,1092,1093,1094,1095 \\
  --json-out outputs/replay/p2_ts3_regime_backfill_dryrun_20260515.json \\
  --csv-out  outputs/replay/p2_ts3_regime_backfill_dryrun_20260515.csv

Prerequisites
-------------
- PR #106 (chore/p13-registry-online-proposal-20260515) merged to main
- PR #107 (chore/p14-ts3-regime-adapter-binding-20260515) merged to main
If either is missing the script emits:
  final_classification: P2_TS3_REGIME_BACKFILL_DRYRUN_BLOCKED
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

# Ensure project root is on sys.path so lottery_api is importable when running
# the script directly (pytest adds '.' via pytest.ini pythonpath=.)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

SCRIPT_VERSION = "p2.0"
LOTTERY_TYPE   = "BIG_LOTTO"
NUMBERS_RANGE  = (1, 49)
EXPECTED_COUNT = 6


# ─── Adapter binding check ────────────────────────────────────────────────────

def _check_adapter_binding(strategy_id: str):
    """
    Returns (bound: bool, reason: str).

    Tries to import ts3_regime_3bet from the registry.
    On current main (before P1.3/P1.4 merge) this will fail → BLOCKED.
    After merge it succeeds → BOUND.

    Does NOT import AdapterBindingPending (only exists post-P1.4 merge).
    """
    try:
        from lottery_api.models.replay_strategy_registry import get_adapter
    except ImportError as e:
        return False, f"ImportError (lottery_api not importable): {e}"

    try:
        adapter = get_adapter(strategy_id)
    except Exception as e:
        return False, f"get_adapter raised: {e}"

    if adapter is None:
        return False, (
            f"{strategy_id} not found in registry — "
            "PR #106 (p13-registry-online-proposal) not merged yet"
        )

    # Check whether the class is still the PendingAdapter stub (pre-P1.4)
    cls_name = adapter.__class__.__name__
    if "Pending" in cls_name:
        return False, (
            f"{strategy_id} adapter class is {cls_name} — "
            "PR #107 (p14-ts3-regime-adapter-binding) not merged yet"
        )

    return True, f"BOUND ({cls_name})"


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _open_db_ro(db_path: str):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _get_next_draw(cur, latest_known_draw: str, lottery_type: str):
    """Return (draw, date, numbers_json, special) of the first draw
    after latest_known_draw for the given lottery_type, or None.

    draw column is stored as TEXT; use CAST to INTEGER to get numeric ordering
    and avoid lexicographic errors (e.g. "96000001" > "115000050" as strings).
    """
    row = cur.execute(
        "SELECT draw, date, numbers, special FROM draws "
        "WHERE lottery_type=? AND CAST(draw AS INTEGER) > CAST(? AS INTEGER) "
        "ORDER BY CAST(draw AS INTEGER) LIMIT 1",
        (lottery_type, latest_known_draw),
    ).fetchone()
    return row


def _parse_numbers(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return []


def _validate_numbers(nums, range_=NUMBERS_RANGE, expected=EXPECTED_COUNT):
    flags = []
    if len(nums) != expected:
        flags.append(f"count_mismatch:{len(nums)}_expected_{expected}")
    for n in nums:
        if not (range_[0] <= n <= range_[1]):
            flags.append(f"out_of_range:{n}")
    if len(set(nums)) != len(nums):
        flags.append("duplicates_in_predicted_numbers")
    return flags


def _compute_hit(predicted, actual):
    if not predicted or not actual:
        return [], None
    hits = sorted(set(predicted) & set(actual))
    return hits, len(hits)


def _determine_truth_level(snapshot_source: str) -> str:
    if snapshot_source == "RECONSTRUCTED":
        return "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE"
    return "REGENERATED_RETROSPECTIVE"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="P2 Controlled Replay Backfill Dry-run for ts3_regime_3bet"
    )
    parser.add_argument("--db",                   required=True,
                        help="Path to lottery_v2.db (opened read-only)")
    parser.add_argument("--strategy-id",          default="ts3_regime_3bet",
                        help="Strategy ID to backfill")
    parser.add_argument("--prediction-item-ids",  required=True,
                        help="Comma-separated prediction_item IDs")
    parser.add_argument("--json-out",             required=True,
                        help="Output JSON path")
    parser.add_argument("--csv-out",              required=True,
                        help="Output CSV path")
    args = parser.parse_args()

    strategy_id = args.strategy_id
    pending_ids = [int(x.strip()) for x in args.prediction_item_ids.split(",")]
    generated_at = datetime.now(timezone.utc).astimezone().isoformat()

    # ── Step 1: Adapter binding check ────────────────────────────────────────
    adapter_bound, adapter_reason = _check_adapter_binding(strategy_id)

    # ── Step 2: DB inspection (always runs, read-only) ────────────────────────
    conn = _open_db_ro(args.db)
    cur  = conn.cursor()

    # Fetch prediction_items
    placeholders = ",".join("?" for _ in pending_ids)
    items = [
        dict(r)
        for r in cur.execute(
            f"SELECT * FROM prediction_items "
            f"WHERE id IN ({placeholders}) ORDER BY id",
            pending_ids,
        ).fetchall()
    ]

    # Fetch prediction_runs
    run_ids = sorted({it["run_id"] for it in items})
    run_map = {
        r["id"]: dict(r)
        for r in cur.execute(
            f"SELECT * FROM prediction_runs "
            f"WHERE id IN ({','.join('?' for _ in run_ids)}) ORDER BY id",
            run_ids,
        ).fetchall()
    }

    # Check for existing replay rows (by strategy_id + target_draw pair)
    existing_replays = cur.execute(
        "SELECT strategy_id, target_draw FROM strategy_prediction_replays "
        "WHERE strategy_id=?",
        (strategy_id,),
    ).fetchall()
    existing_pairs = {(r[0], r[1]) for r in existing_replays}

    # ── Step 3: Build preview rows ────────────────────────────────────────────
    preview_rows = []
    eligible_count = 0
    blocked_count  = 0

    found_ids = {it["id"] for it in items}
    missing_ids = [pid for pid in pending_ids if pid not in found_ids]

    for item in items:
        item_id  = item["id"]
        run_id   = item["run_id"]
        run      = run_map.get(run_id, {})

        latest_known_draw = run.get("latest_known_draw", "")
        snapshot_source   = run.get("snapshot_source", "UNKNOWN")
        run_strategy_name = run.get("strategy_name", "")

        risk_flags: list = []
        notes:      list = []

        # Risk: RECONSTRUCTED snapshot
        if snapshot_source == "RECONSTRUCTED":
            risk_flags.append("run_id_175_reconstructed_snapshot")
            notes.append(
                "prediction_run.snapshot_source=RECONSTRUCTED — "
                "lower prediction provenance confidence"
            )

        # Risk: strategy_name mismatch
        if run_strategy_name and run_strategy_name != strategy_id:
            risk_flags.append(
                f"strategy_name_mismatch:{run_strategy_name}_vs_{strategy_id}"
            )

        # Target draw lookup
        target_row = _get_next_draw(cur, latest_known_draw, LOTTERY_TYPE)
        if target_row is None:
            risk_flags.append("actual_numbers_missing")
            notes.append(
                f"No draw found in DB after {latest_known_draw} — "
                "draw result not yet available"
            )
            target_draw  = None
            target_date  = None
            actual_numbers = None
            actual_special = None
        else:
            target_draw   = target_row["draw"]
            target_date   = target_row["date"]
            actual_numbers = _parse_numbers(target_row["numbers"])
            actual_special = target_row["special"]

        # Predicted numbers
        predicted_numbers = _parse_numbers(item.get("numbers"))
        val_flags = _validate_numbers(predicted_numbers)
        if val_flags:
            risk_flags.extend([f"validation:{f}" for f in val_flags])

        # Duplicate replay row check
        if target_draw and (strategy_id, target_draw) in existing_pairs:
            risk_flags.append("duplicate_replay_row_exists")
            notes.append(
                f"replay row already exists for strategy_id={strategy_id} "
                f"target_draw={target_draw}"
            )

        # Adapter binding flag
        if not adapter_bound:
            risk_flags.append("adapter_binding_pending")
            notes.append(f"adapter not bound: {adapter_reason}")

        # Eligibility
        has_blocker = "actual_numbers_missing" in risk_flags or \
                      "duplicate_replay_row_exists" in risk_flags or \
                      not adapter_bound
        would_insert = not has_blocker

        if would_insert:
            eligible_count += 1
        else:
            blocked_count += 1

        # Hit computation
        hit_numbers, hit_count = _compute_hit(predicted_numbers, actual_numbers)

        truth_level = _determine_truth_level(snapshot_source)

        preview_rows.append({
            "prediction_item_id":   item_id,
            "prediction_run_id":    run_id,
            "run_snapshot_source":  snapshot_source,
            "history_cutoff_draw":  latest_known_draw,
            "target_draw":          target_draw,
            "draw_date":            target_date,
            "predicted_numbers":    predicted_numbers,
            "actual_numbers":       actual_numbers,
            "actual_special":       actual_special,
            "hit_numbers":          hit_numbers,
            "hit_count":            hit_count,
            "would_insert_replay_row": would_insert,
            "truth_level":          truth_level,
            "risk_flags":           risk_flags,
            "notes":                "; ".join(notes) if notes else "",
        })

    conn.close()

    # ── Step 4: Final classification ──────────────────────────────────────────
    if not adapter_bound:
        final_classification = "P2_TS3_REGIME_BACKFILL_DRYRUN_BLOCKED"
        next_step            = "P2_BLOCKED_FIX_INPUTS"
        blocked_reason = (
            f"Adapter binding check failed: {adapter_reason}. "
            "Merge PR #106 (p13-registry-online-proposal) and "
            "PR #107 (p14-ts3-regime-adapter-binding) to main first."
        )
        # Per HARD STOP: do not emit preview rows in BLOCKED state
        output_preview = []
    elif missing_ids:
        final_classification = "P2_TS3_REGIME_BACKFILL_DRYRUN_BLOCKED"
        next_step            = "P2_BLOCKED_FIX_INPUTS"
        blocked_reason = f"Missing prediction_items: {missing_ids}"
        output_preview = []
    elif eligible_count == 0:
        final_classification = "P2_TS3_REGIME_BACKFILL_DRYRUN_BLOCKED"
        next_step            = "P2_BLOCKED_FIX_INPUTS"
        blocked_reason = "All items are ineligible (blocked by risk flags)"
        output_preview = preview_rows
    else:
        final_classification = "P2_TS3_REGIME_BACKFILL_DRYRUN_READY"
        next_step            = "P2B_OPERATOR_APPROVAL_FOR_DB_WRITE"
        blocked_reason       = None
        output_preview       = preview_rows

    # ── Step 5: Write JSON ────────────────────────────────────────────────────
    output = {
        "schema_version":             "p2.0",
        "generated_at":               generated_at,
        "script_version":             SCRIPT_VERSION,
        "dry_run":                    True,
        "final_classification":       final_classification,
        "strategy_id":                strategy_id,
        "lottery_type":               LOTTERY_TYPE,
        "input_prediction_item_ids":  pending_ids,
        "items_found_in_db":          len(items),
        "items_missing_from_db":      missing_ids,
        "eligible_count":             eligible_count,
        "blocked_count":              blocked_count,
        "adapter_bound":              adapter_bound,
        "adapter_check_result":       adapter_reason,
        "blocked_reason":             blocked_reason,
        "preview_rows":               output_preview,
        "safety": {
            "db_written":                 False,
            "replay_rows_inserted":       False,
            "prediction_items_promoted":  False,
            "backfill_committed":         False,
            "strategy_logic_changed":     False,
            "api_ui_backend_changed":     False,
        },
        "next_step": next_step,
    }

    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"[p2-dryrun] JSON written: {args.json_out}")

    # ── Step 6: Write CSV ─────────────────────────────────────────────────────
    csv_fields = [
        "prediction_item_id",
        "prediction_run_id",
        "draw_date",
        "predicted_numbers",
        "actual_numbers",
        "hit_count",
        "would_insert_replay_row",
        "truth_level",
        "risk_flags",
        "notes",
    ]
    with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for row in output_preview:
            writer.writerow({
                "prediction_item_id":    row["prediction_item_id"],
                "prediction_run_id":     row["prediction_run_id"],
                "draw_date":             row["draw_date"],
                "predicted_numbers":     json.dumps(row["predicted_numbers"]),
                "actual_numbers":        (
                    json.dumps(row["actual_numbers"])
                    if row["actual_numbers"] is not None else ""
                ),
                "hit_count":             (
                    "" if row["hit_count"] is None else row["hit_count"]
                ),
                "would_insert_replay_row": row["would_insert_replay_row"],
                "truth_level":           row["truth_level"],
                "risk_flags":            "|".join(row["risk_flags"]),
                "notes":                 row["notes"],
            })
    print(f"[p2-dryrun] CSV written:  {args.csv_out}")
    print(f"[p2-dryrun] Classification: {final_classification}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
