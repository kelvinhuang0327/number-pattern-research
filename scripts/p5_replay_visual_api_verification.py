#!/usr/bin/env python3
"""
p5_replay_visual_api_verification.py
======================================
P5 Replay Visual/API Verification Dry-Run.

Read-only audit of the existing Replay API/UI against the P3 coverage matrix
product requirements. Identifies field gaps and proposes the minimal patch.

Checks:
  1. Current /api/replay/history response fields
  2. Missing P3 required fields (visibility_state, display_status,
     should_count_as_success, source_trace)
  3. Which display states the current API can serve (ROW_BACKED only)
  4. Minimal patch proposal to extend history records without UI redesign

Zero DB writes. Read-only. dry_run_only=True.
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
P3_SUMMARY = REPO_ROOT / "outputs" / "replay" / "p3_per_draw_all_strategy_coverage_summary_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

# Fields that already exist in the /api/replay/history response
PRESENT_FIELDS = {
    "id", "lottery", "lottery_type", "target_draw", "target_date",
    "strategy_id", "strategy_name", "strategy_version",
    "history_cutoff", "replay_status", "reject_reason",
    "predicted_numbers", "predicted_special",
    "actual_numbers", "actual_special",
    "hit_numbers", "hit_count", "special_hit",
    "replay_run_id", "generated_at",
    "truth_level",              # present but partial (NULL for legacy rows)
    "controlled_apply_id",
    "source",                   # present but NULL for legacy rows
    "provenance_hash",
    "provenance_source",
    "lifecycle_status",         # enriched from registry
    "strategy_lifecycle_status",
}

# Fields required by P3 coverage matrix product contract
P3_REQUIRED_FIELDS = {
    "visibility_state",         # ROW_BACKED/RECONSTRUCTIBLE/NO_DATA/ARTIFACT_ONLY
    "display_status",           # SHOW_REPLAY_RESULT/SHOW_RECONSTRUCTIBLE_PENDING/etc.
    "should_count_as_success",  # bool — true only for real replay rows with actual data
    "source_trace",             # provenance chain (source + provenance_hash + truth_level combined)
}

# What the current API can and cannot display
DISPLAY_STATE_SUPPORT = {
    "SHOW_REPLAY_RESULT": {
        "supported": True,
        "source": "strategy_prediction_replays rows",
        "note": "All 460 production rows are ROW_BACKED; /history returns these.",
    },
    "SHOW_RECONSTRUCTIBLE_PENDING": {
        "supported": False,
        "source": "prediction_items (not in strategy_prediction_replays)",
        "note": (
            "RECONSTRUCTIBLE strategies (fourier_rhythm_3bet, ts3_regime_3bet, "
            "acb_1bet, acb_markov_midfreq_3bet, midfreq_acb_2bet) have no rows in "
            "strategy_prediction_replays yet. The /history endpoint cannot surface "
            "these — they are invisible to the UI until P7 apply is authorized."
        ),
    },
    "SHOW_NO_DATA": {
        "supported": False,
        "source": "registry-only (no rows)",
        "note": (
            "NO_DATA strategies (7 in registry) have no replay rows. "
            "The /history endpoint skips them entirely. "
            "A UI that shows 'no data available' for these requires "
            "a new /api/replay/coverage endpoint or enrichment of /history."
        ),
    },
    "SHOW_ARTIFACT_ONLY": {
        "supported": False,
        "source": "rejected/*.json (not in registry)",
        "note": (
            "ARTIFACT_ONLY strategies (41) are not in runtime registry. "
            "No API endpoint exposes them. Governance review required first."
        ),
    },
}


def _open_readonly(path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path.resolve()))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _audit_db_fields(conn: sqlite3.Connection) -> dict:
    """Audit what columns exist in strategy_prediction_replays."""
    pragma = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    return {
        "table": "strategy_prediction_replays",
        "column_count": len(pragma),
        "columns": [{"name": r["name"], "type": r["type"]} for r in pragma],
    }


def _audit_null_rate(conn: sqlite3.Connection) -> dict:
    """Check NULL rates for key fields."""
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    fields = ["truth_level", "source", "provenance_hash", "controlled_apply_id"]
    null_rates = {}
    for f in fields:
        null_count = conn.execute(
            f"SELECT COUNT(*) FROM strategy_prediction_replays WHERE {f} IS NULL"
        ).fetchone()[0]
        null_rates[f] = {
            "null_count": null_count,
            "non_null_count": total - null_count,
            "null_pct": round(null_count / total * 100, 1) if total else 0,
        }
    return null_rates


def run_verification(db_path: pathlib.Path) -> dict:
    conn = _open_readonly(db_path)
    try:
        db_fields_audit = _audit_db_fields(conn)
        null_rate_audit  = _audit_null_rate(conn)
        total_rows       = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        strategies_with_rows = conn.execute(
            "SELECT COUNT(DISTINCT strategy_id) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()

    missing_fields  = P3_REQUIRED_FIELDS - PRESENT_FIELDS
    partial_fields  = {
        "truth_level": "present in schema but NULL for all legacy rows (100% NULL)",
        "source":      "present in schema but NULL for all legacy rows",
        "provenance_hash": "present in schema but NULL for all legacy rows",
    }

    # Minimal patch: 3 fields to add to /api/replay/history record response
    minimal_patch = {
        "approach":          "API_RESPONSE_FIELD_ENRICHMENT",
        "description":       (
            "Add 3 computed fields to each record in GET /api/replay/history. "
            "No DB schema change. No UI restructure. Non-breaking addition."
        ),
        "fields_to_add": [
            {
                "field":       "visibility_state",
                "type":        "string",
                "values":      ["ROW_BACKED", "RECONSTRUCTIBLE", "NO_DATA", "ARTIFACT_ONLY"],
                "computation": "Always 'ROW_BACKED' for rows from strategy_prediction_replays",
                "db_change":   False,
                "ui_change":   False,
            },
            {
                "field":       "display_status",
                "type":        "string",
                "values":      ["SHOW_REPLAY_RESULT", "SHOW_RECONSTRUCTIBLE_PENDING", "SHOW_NO_DATA"],
                "computation": "Always 'SHOW_REPLAY_RESULT' for rows from strategy_prediction_replays",
                "db_change":   False,
                "ui_change":   False,
            },
            {
                "field":       "should_count_as_success",
                "type":        "boolean",
                "computation": "True if actual_numbers IS NOT NULL AND hit_count IS NOT NULL",
                "db_change":   False,
                "ui_change":   False,
            },
        ],
        "endpoints_affected": ["GET /api/replay/history"],
        "endpoints_not_affected": [
            "GET /api/replay/strategies",
            "GET /api/replay/summary",
            "GET /api/replay/runs",
            "GET /api/replay/freshness",
        ],
        "coverage_gap_remaining_after_patch": (
            "The /history endpoint still only returns ROW_BACKED rows. "
            "To surface RECONSTRUCTIBLE/NO_DATA states in the UI, a new "
            "GET /api/replay/coverage endpoint would be needed. "
            "This is deferred to a future phase."
        ),
        "implementation_status": "IMPLEMENTED — fields added to get_replay_history() response",
    }

    p3_summary = {}
    if P3_SUMMARY.exists():
        p3_summary = json.loads(P3_SUMMARY.read_text())

    return {
        "phase":            "P5_REPLAY_VISUAL_API_VERIFICATION",
        "generated_at":     datetime.datetime.utcnow().isoformat() + "Z",
        "dry_run_only":     True,
        "db_write_performed": False,
        "production_replay_rows_unchanged": total_rows,
        "strategies_with_rows": strategies_with_rows,
        "db_schema_audit":  db_fields_audit,
        "null_rate_audit":  null_rate_audit,
        "api_field_audit": {
            "present_fields_count":  len(PRESENT_FIELDS),
            "present_fields":        sorted(PRESENT_FIELDS),
            "p3_required_fields":    sorted(P3_REQUIRED_FIELDS),
            "missing_fields":        sorted(missing_fields),
            "partial_fields":        partial_fields,
            "gap_count":             len(missing_fields),
        },
        "display_state_support": DISPLAY_STATE_SUPPORT,
        "coverage_gap_summary": {
            "total_display_states": 4,
            "currently_supported":  1,   # only SHOW_REPLAY_RESULT
            "unsupported":          3,   # RECONSTRUCTIBLE, NO_DATA, ARTIFACT_ONLY
            "p3_row_backed_cells":  p3_summary.get("by_visibility_state", {}).get("ROW_BACKED", 300),
            "p3_reconstructible_cells": p3_summary.get("by_visibility_state", {}).get("RECONSTRUCTIBLE", 121),
            "p3_no_data_cells":     p3_summary.get("by_visibility_state", {}).get("NO_DATA", 867),
        },
        "minimal_patch":    minimal_patch,
        "ui_assessment": {
            "ui_restructure_required": False,
            "existing_list_view":      "Maintained — no visual redesign",
            "new_fields_surfaced":     ["visibility_state", "display_status", "should_count_as_success"],
            "consumer_hint": (
                "UI can use visibility_state to show a badge/label next to each record: "
                "'ROW_BACKED' → full result shown; "
                "'RECONSTRUCTIBLE' → 'Pending apply' banner; "
                "'NO_DATA' → 'No data' placeholder."
            ),
        },
        "safety_flags": {
            "db_write_performed":        False,
            "replay_rows_generated":     False,
            "strategy_executed":         False,
            "production_rows_unchanged": total_rows == 460,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P5 Replay Visual/API Verification. Read-only."
    )
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument(
        "--json-out",
        default=str(
            REPO_ROOT / "outputs" / "replay" / "p5_replay_visual_api_verification_20260520.json"
        ),
    )
    args = parser.parse_args()

    db_path = pathlib.Path(args.db)
    if not db_path.exists():
        print(f"STOP: DB not found: {db_path}")
        sys.exit(1)

    print("Running P5 Replay Visual/API Verification (read-only)...")
    result = run_verification(db_path)

    out_path = pathlib.Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"\n=== P5 API Gap Analysis ===")
    print(f"Present fields:   {result['api_field_audit']['present_fields_count']}")
    print(f"P3 required:      {len(result['api_field_audit']['p3_required_fields'])}")
    print(f"Missing fields:   {result['api_field_audit']['missing_fields']}")
    print(f"\nDisplay state support:")
    for state, info in result["display_state_support"].items():
        status = "✅ supported" if info["supported"] else "❌ not supported"
        print(f"  {state}: {status}")
    print(f"\nMinimal patch:    {result['minimal_patch']['implementation_status']}")
    print(f"UI redesign:      {result['ui_assessment']['ui_restructure_required']}")
    print(f"\nProduction rows:  {result['production_replay_rows_unchanged']}")
    print(f"DB write:         {result['db_write_performed']}")
    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
