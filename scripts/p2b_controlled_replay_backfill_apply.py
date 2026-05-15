#!/usr/bin/env python3
"""
P2B Controlled Replay Backfill Apply Script
============================================
Strategy : ts3_regime_3bet (BIG_LOTTO)
Apply ID : P2B_20260515

Safety guarantees
-----------------
- Default mode is DRY-RUN unless --apply is explicitly passed
- Requires --controlled-apply-id P2B_20260515 (exact string match)
- Only accepts prediction_item_ids: 1069, 1070, 1071, 1093, 1094, 1095
- Explicitly refuses blocked IDs: 1090, 1091, 1092
- Inserts into strategy_prediction_replays only
- Does NOT promote prediction_items
- Does NOT update prediction_runs
- Idempotent: refuses to run if rows with controlled_apply_id already exist
- Writes apply receipt JSON after success

Truth levels (from P2 dry-run):
- 1069, 1070, 1071 -> REGENERATED_RETROSPECTIVE
- 1093, 1094, 1095 -> ARTIFACT_RECONSTRUCTED_RETROSPECTIVE

Schema note:
  strategy_prediction_replays has NO prediction_item_id column.
  Item provenance is stored in provenance_source as JSON:
    {"prediction_item_id": N, "run_id": M, "risk_flags": [...]}

Usage
-----
# Dry-run preview (default, no --apply):
python3 scripts/p2b_controlled_replay_backfill_apply.py \\
  --db lottery_api/data/lottery_v2.db \\
  --dryrun-json outputs/replay/p2_ts3_regime_backfill_dryrun_20260515.json \\
  --prediction-item-ids 1069,1070,1071,1093,1094,1095 \\
  --controlled-apply-id P2B_20260515 \\
  --json-out outputs/replay/p2b_ts3_regime_backfill_apply_receipt_20260515.json

# Apply (requires explicit --apply flag):
python3 scripts/p2b_controlled_replay_backfill_apply.py \\
  --db lottery_api/data/lottery_v2.db \\
  --dryrun-json outputs/replay/p2_ts3_regime_backfill_dryrun_20260515.json \\
  --prediction-item-ids 1069,1070,1071,1093,1094,1095 \\
  --controlled-apply-id P2B_20260515 \\
  --json-out outputs/replay/p2b_ts3_regime_backfill_apply_receipt_20260515.json \\
  --apply
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

SCRIPT_VERSION      = "p2b.0"
STRATEGY_ID         = "ts3_regime_3bet"
LOTTERY_TYPE        = "BIG_LOTTO"
AUTHORIZED_APPLY_ID = "P2B_20260515"
ALLOWED_IDS         = {1069, 1070, 1071, 1093, 1094, 1095}
BLOCKED_IDS         = {1090, 1091, 1092}

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _open_db_rw(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _open_db_ro(db_path: str):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _ts() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _idempotency_check(cur, controlled_apply_id: str) -> list:
    """Return list of existing rows for this controlled_apply_id."""
    rows = cur.execute(
        "SELECT id, strategy_id, target_draw, truth_level, provenance_source "
        "FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (controlled_apply_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _build_row(preview_row: dict, controlled_apply_id: str) -> dict:
    """Construct the INSERT payload from dry-run preview row."""
    item_id  = preview_row["prediction_item_id"]
    run_id   = preview_row["prediction_run_id"]
    provenance = json.dumps({
        "prediction_item_id": item_id,
        "run_id":             run_id,
        "risk_flags":         preview_row.get("risk_flags", []),
        "notes":              preview_row.get("notes", ""),
        "p2_dryrun_script":   "scripts/p2_controlled_replay_backfill_dryrun.py",
        "p2b_apply_script":   "scripts/p2b_controlled_replay_backfill_apply.py",
    })
    return {
        "lottery_type":       LOTTERY_TYPE,
        "target_draw":        preview_row["target_draw"],
        "target_date":        preview_row["draw_date"],
        "strategy_id":        STRATEGY_ID,
        "strategy_name":      STRATEGY_ID,
        "strategy_version":   "P1.4_SAFE_RECONSTRUCTION_20260515",
        "history_cutoff_draw": preview_row["history_cutoff_draw"],
        "replay_status":      "COMPLETE",
        "reject_reason":      None,
        "predicted_numbers":  json.dumps(preview_row["predicted_numbers"]),
        "predicted_special":  None,
        "actual_numbers":     json.dumps(preview_row["actual_numbers"]),
        "actual_special":     preview_row.get("actual_special"),
        "hit_numbers":        json.dumps(preview_row["hit_numbers"]),
        "hit_count":          preview_row["hit_count"],
        "special_hit":        0,
        # replay_run_id has FK to strategy_replay_runs.id (run IDs 1-7).
        # Prediction run IDs (167/175) are from prediction_runs, not that table.
        # Set NULL to avoid FK violation — provenance stored in provenance_source.
        "replay_run_id":      None,
        "truth_level":        preview_row["truth_level"],
        "source":             "CONTROLLED_REPLAY_BACKFILL_P2B",
        "provenance_hash":    None,
        "provenance_source":  provenance,
        "controlled_apply_id": controlled_apply_id,
        "dry_run_only":       0,
    }


def _insert_row(conn, row: dict) -> int:
    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    sql = f"INSERT INTO strategy_prediction_replays ({cols}) VALUES ({placeholders})"
    cur = conn.execute(sql, list(row.values()))
    return cur.lastrowid


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="P2B Controlled Replay Backfill Apply for ts3_regime_3bet"
    )
    parser.add_argument("--db",                   required=True)
    parser.add_argument("--dryrun-json",          required=True,
                        help="Path to validated P2 dry-run JSON output")
    parser.add_argument("--prediction-item-ids",  required=True,
                        help="Comma-separated IDs (must match dry-run eligible)")
    parser.add_argument("--controlled-apply-id",  required=True,
                        help=f"Must be exactly '{AUTHORIZED_APPLY_ID}'")
    parser.add_argument("--json-out",             required=True,
                        help="Apply receipt JSON path")
    parser.add_argument("--apply",                action="store_true",
                        help="Actually write to DB (default: dry-run preview only)")
    args = parser.parse_args()

    apply_mode        = args.apply
    controlled_apply_id = args.controlled_apply_id
    requested_ids     = [int(x.strip()) for x in args.prediction_item_ids.split(",")]
    generated_at      = _ts()

    errors: list = []

    # ── Gate 1: controlled_apply_id must match exactly ─────────────────────
    if controlled_apply_id != AUTHORIZED_APPLY_ID:
        print(f"[p2b-apply] BLOCKED: controlled-apply-id '{controlled_apply_id}' "
              f"!= expected '{AUTHORIZED_APPLY_ID}'", file=sys.stderr)
        sys.exit(2)

    # ── Gate 2: requested IDs must be subset of ALLOWED_IDS ───────────────
    refused = set(requested_ids) & BLOCKED_IDS
    if refused:
        print(f"[p2b-apply] BLOCKED: requested IDs include blocked items: {sorted(refused)}",
              file=sys.stderr)
        sys.exit(2)
    unknown = set(requested_ids) - ALLOWED_IDS
    if unknown:
        print(f"[p2b-apply] BLOCKED: requested IDs not in allowed set: {sorted(unknown)}",
              file=sys.stderr)
        sys.exit(2)

    # ── Load dry-run JSON ─────────────────────────────────────────────────
    dryrun = json.load(open(args.dryrun_json))
    assert dryrun["final_classification"] == "P2_TS3_REGIME_BACKFILL_DRYRUN_READY", \
        f"dry-run not READY: {dryrun['final_classification']}"
    assert dryrun["adapter_bound"] is True
    assert dryrun["eligible_count"] == 6
    assert dryrun["safety"]["db_written"] is False

    eligible_rows_by_id = {
        r["prediction_item_id"]: r
        for r in dryrun["preview_rows"]
        if r["would_insert_replay_row"]
    }

    rows_to_insert = []
    for pid in sorted(requested_ids):
        if pid not in eligible_rows_by_id:
            errors.append(f"item {pid} not eligible in dry-run")
        else:
            rows_to_insert.append(eligible_rows_by_id[pid])

    if errors:
        print(f"[p2b-apply] BLOCKED: {errors}", file=sys.stderr)
        sys.exit(2)

    # ── Idempotency check (read-only) ─────────────────────────────────────
    ro_conn = _open_db_ro(args.db)
    existing = _idempotency_check(ro_conn.cursor(), controlled_apply_id)
    ro_conn.close()

    if existing:
        print(f"[p2b-apply] BLOCKED idempotency: {len(existing)} rows already exist "
              f"for controlled_apply_id={controlled_apply_id}", file=sys.stderr)
        receipt = {
            "schema_version":      "p2b.0",
            "generated_at":        generated_at,
            "script_version":      SCRIPT_VERSION,
            "apply_mode":          apply_mode,
            "controlled_apply_id": controlled_apply_id,
            "final_classification": "P2B_BLOCKED_IDEMPOTENCY",
            "rows_inserted":       0,
            "existing_rows":       existing,
            "safety": {
                "db_written":                False,
                "replay_rows_inserted":      False,
                "prediction_items_promoted": False,
            },
        }
        os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
        json.dump(receipt, open(args.json_out, "w"), indent=2)
        print(f"[p2b-apply] Receipt: {args.json_out}")
        sys.exit(1)

    # ── Build INSERT payloads ─────────────────────────────────────────────
    payloads = [_build_row(r, controlled_apply_id) for r in rows_to_insert]

    if not apply_mode:
        # Preview mode — show what would be inserted, no DB write
        print("[p2b-apply] DRY-RUN MODE (pass --apply to write)")
        for p in payloads:
            print(f"  WOULD INSERT: item_id={json.loads(p['provenance_source'])['prediction_item_id']} "
                  f"target={p['target_draw']} truth={p['truth_level']} hits={p['hit_count']}")
        receipt = {
            "schema_version":      "p2b.0",
            "generated_at":        generated_at,
            "script_version":      SCRIPT_VERSION,
            "apply_mode":          False,
            "controlled_apply_id": controlled_apply_id,
            "final_classification": "P2B_PREVIEW_ONLY",
            "rows_to_insert_count": len(payloads),
            "preview_payloads":    payloads,
            "safety": {
                "db_written":                False,
                "replay_rows_inserted":      False,
                "prediction_items_promoted": False,
            },
        }
        os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
        json.dump(receipt, open(args.json_out, "w"), indent=2)
        print(f"[p2b-apply] Receipt: {args.json_out}")
        return

    # ── APPLY: Write to DB ────────────────────────────────────────────────
    print(f"[p2b-apply] APPLY MODE — inserting {len(payloads)} rows "
          f"(controlled_apply_id={controlled_apply_id})")

    conn = _open_db_rw(args.db)
    inserted_rows = []
    try:
        with conn:
            for payload in payloads:
                row_id = _insert_row(conn, payload)
                prov   = json.loads(payload["provenance_source"])
                inserted_rows.append({
                    "replay_row_id":       row_id,
                    "prediction_item_id":  prov["prediction_item_id"],
                    "run_id":              prov["run_id"],
                    "target_draw":         payload["target_draw"],
                    "draw_date":           payload["target_date"],
                    "predicted_numbers":   json.loads(payload["predicted_numbers"]),
                    "actual_numbers":      json.loads(payload["actual_numbers"]),
                    "hit_count":           payload["hit_count"],
                    "truth_level":         payload["truth_level"],
                    "risk_flags":          prov.get("risk_flags", []),
                })
                print(f"  INSERTED replay_row_id={row_id} "
                      f"item_id={prov['prediction_item_id']} "
                      f"target={payload['target_draw']} "
                      f"truth={payload['truth_level']} "
                      f"hits={payload['hit_count']}")
    except Exception as exc:
        conn.close()
        print(f"[p2b-apply] ERROR during insert: {exc}", file=sys.stderr)
        sys.exit(3)

    conn.close()

    print(f"[p2b-apply] SUCCESS: {len(inserted_rows)} rows inserted")

    receipt = {
        "schema_version":       "p2b.0",
        "generated_at":         generated_at,
        "script_version":       SCRIPT_VERSION,
        "apply_mode":           True,
        "controlled_apply_id":  controlled_apply_id,
        "final_classification": "P2B_CONTROLLED_REPLAY_BACKFILL_APPLIED",
        "strategy_id":          STRATEGY_ID,
        "lottery_type":         LOTTERY_TYPE,
        "rows_inserted":        len(inserted_rows),
        "inserted_rows":        inserted_rows,
        "skipped_blocked_ids":  sorted(BLOCKED_IDS),
        "skip_reason":          "actual_numbers_missing (draw 115000051 not yet in DB)",
        "safety": {
            "db_written":                True,
            "replay_rows_inserted":      True,
            "rows_inserted_count":       len(inserted_rows),
            "prediction_items_promoted": False,
            "prediction_runs_updated":   False,
            "strategy_logic_changed":    False,
            "api_ui_backend_changed":    False,
        },
        "next_step": "P2C_POST_APPLY_DRIFT_COVERAGE_VERIFICATION",
    }

    os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
    json.dump(receipt, open(args.json_out, "w"), indent=2)
    print(f"[p2b-apply] Receipt JSON: {args.json_out}")


if __name__ == "__main__":
    main()
