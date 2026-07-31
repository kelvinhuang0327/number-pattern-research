#!/usr/bin/env python3
"""
p5_historical_reconstruction_plan.py
======================================
P5 Historical Reconstruction Plan — READ-ONLY.

Scans prediction_items in the DB for each RECONSTRUCTIBLE strategy from the
P1 catalog, determines which (strategy, draw) pairs have verifiable payload
data, and produces a reconstruction plan for P6 to evaluate.

Constraints:
  - No DB write
  - No strategy logic execution
  - No draw import
  - can_apply always False
  - dry_run_only always True

Outputs:
  outputs/replay/p5_reconstruction_input_inventory_20260520.json
  outputs/replay/p5_historical_reconstruction_plan_20260520.json
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import sqlite3
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P1_PLAN   = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"

sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_source_promotion_policy import SourcePromotionTier


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLAN_INSERT_REPLAY_ROW     = "PLAN_INSERT_REPLAY_ROW"
SKIP_NO_HISTORICAL_PAYLOAD = "SKIP_NO_HISTORICAL_PAYLOAD"
SKIP_SOURCE_MISSING        = "SKIP_SOURCE_MISSING"

RECONSTRUCTIBLE = "RECONSTRUCTIBLE"

# Lifecycle states that block P5 plan insert
_BLOCKED_LIFECYCLE = frozenset({"REJECTED"})


# ---------------------------------------------------------------------------
# DB helpers (read-only)
# ---------------------------------------------------------------------------

def _open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _provenance_hash(run_id: int, numbers: str) -> str:
    raw = f"run_id={run_id}:numbers={numbers}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_prediction_items_by_strategy(
    conn: sqlite3.Connection,
    strategy_id: str,
) -> list[dict]:
    """
    Return all (draw, lottery_type, run_id, numbers) rows from prediction_items
    joined with prediction_runs for a given strategy_name.

    Groups by (strategy_name, draw) taking the FIRST run_id per draw.
    Returns list sorted by draw DESC.
    """
    rows = conn.execute(
        """
        SELECT pr.latest_known_draw AS draw_id,
               pr.lottery_type,
               MIN(pr.id)           AS run_id,
               MIN(pi.id)           AS item_id,
               GROUP_CONCAT(pi.numbers, '|||') AS all_numbers,
               COUNT(pi.id)         AS item_count
        FROM prediction_items pi
        JOIN prediction_runs pr ON pi.run_id = pr.id
        WHERE pi.strategy_name = ?
          AND pr.latest_known_draw IS NOT NULL
          AND pi.numbers IS NOT NULL
        GROUP BY pr.latest_known_draw
        ORDER BY CAST(pr.latest_known_draw AS INTEGER) DESC
        """,
        (strategy_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# P1 catalog loader
# ---------------------------------------------------------------------------

def _load_p1_entries() -> list[dict]:
    if not P1_PLAN.exists():
        raise FileNotFoundError(
            f"P1 catalog plan not found: {P1_PLAN}\n"
            "Run scripts/p1_catalog_visibility_plan.py first."
        )
    data = json.loads(P1_PLAN.read_text())
    return data.get("entries", [])


# ---------------------------------------------------------------------------
# Source tier determination
# ---------------------------------------------------------------------------

def _determine_source_tier(
    artifact_source_type: str,
    has_db_prediction_items: bool,
) -> str:
    """
    Determine P5 source tier for a strategy.

    P5 checks prediction_items directly — if DB data exists, it's TIER_1
    regardless of P1's artifact_source_type scan result (P1 may have
    classified as CODE_SCAN if prediction_runs.strategy_name didn't match,
    even when prediction_items.strategy_name does match).
    """
    if has_db_prediction_items:
        return SourcePromotionTier.TIER_1_DB_PREDICTION_PAYLOAD
    if artifact_source_type == "CODE_SCAN":
        return SourcePromotionTier.TIER_4_CODE_SCAN_ONLY
    if artifact_source_type == "REJECTED_JSON":
        return SourcePromotionTier.TIER_5_REJECTED_JSON_ONLY
    if artifact_source_type in ("PREDICTION_LOG", "STRATEGY_STATE", "REPLAY_RUN"):
        # Has a log/state artifact but no usable per-draw payload found in DB
        return SourcePromotionTier.TIER_2_LOG_DERIVED_PAYLOAD
    return SourcePromotionTier.TIER_0_UNKNOWN


# ---------------------------------------------------------------------------
# Main planner
# ---------------------------------------------------------------------------

def build_p5_plan(conn: sqlite3.Connection, p1_entries: list[dict]) -> dict:
    """
    Build P5 reconstruction plan.

    For each RECONSTRUCTIBLE strategy in P1:
      - Query prediction_items for actual draw data
      - Produce PLAN_INSERT_REPLAY_ROW cells for draws with data
      - Produce a single SKIP cell for strategies with no data
    """
    plan_cells: list[dict] = []
    inventory: list[dict]  = []

    generated_at = datetime.datetime.utcnow().isoformat() + "Z"

    reconstructible_entries = [
        e for e in p1_entries
        if e.get("catalog_visibility_state") == RECONSTRUCTIBLE
    ]

    for entry in reconstructible_entries:
        sid       = entry["strategy_id"]
        lifecycle = entry.get("lifecycle_state", "")
        artifact  = entry.get("artifact_source_type", "NONE")
        lottery   = entry.get("lottery_type", "")

        # Get actual prediction_items from DB
        db_rows = _get_prediction_items_by_strategy(conn, sid)
        has_db_data = len(db_rows) > 0

        source_tier = _determine_source_tier(artifact, has_db_data)

        # Lifecycle warning for non-ONLINE
        lifecycle_warning: str | None = None
        if lifecycle not in ("ONLINE", "OFFLINE", "OBSERVATION"):
            lifecycle_warning = (
                f"strategy {sid!r} lifecycle={lifecycle!r}; "
                "P7 apply will create historical-only rows — human review required"
            )
        elif lifecycle == "OBSERVATION":
            lifecycle_warning = (
                f"strategy {sid!r} is in OBSERVATION shadow mode"
            )

        # Inventory entry
        inventory.append({
            "strategy_id":              sid,
            "lottery_type":             lottery,
            "lifecycle_state":          lifecycle,
            "artifact_source_type":     artifact,
            "source_tier":              source_tier,
            "has_db_prediction_items":  has_db_data,
            "db_draw_count":            len(db_rows),
            "lifecycle_warning":        lifecycle_warning,
            "p1_has_historical_predictions": entry.get("has_historical_predictions", False),
        })

        if not has_db_data:
            # No prediction_items in DB — single SKIP row per strategy
            if artifact in ("CODE_SCAN", "NONE", "BACKTEST_REPORT"):
                action = SKIP_NO_HISTORICAL_PAYLOAD
            else:
                action = SKIP_SOURCE_MISSING

            plan_cells.append({
                "strategy_id":           sid,
                "lottery_type":          lottery,
                "draw_id":               None,
                "draw_date":             None,
                "planned_action":        action,
                "source_tier":           source_tier,
                "p5_can_apply":          False,
                "dry_run_only":          True,
                "has_predicted_numbers": False,
                "provenance_hash":       None,
                "run_id":                None,
                "item_count":            0,
                "lifecycle_state":       lifecycle,
                "lifecycle_warning":     lifecycle_warning,
                "created_by_phase":      "P5",
                "skip_reason":           f"No prediction_items in DB for {sid!r}",
            })
        else:
            # One PLAN_INSERT cell per draw with actual data
            for row in db_rows:
                draw_id       = row["draw_id"]
                run_id        = row["run_id"]
                all_numbers   = row["all_numbers"] or ""
                # Take first bet's numbers for provenance
                first_numbers = all_numbers.split("|||")[0].strip() if all_numbers else ""
                prov_hash     = _provenance_hash(run_id, first_numbers) if first_numbers else None
                has_numbers   = bool(first_numbers)

                plan_cells.append({
                    "strategy_id":           sid,
                    "lottery_type":          row["lottery_type"] or lottery,
                    "draw_id":               draw_id,
                    "draw_date":             None,  # draw date lookup deferred to P7
                    "planned_action":        PLAN_INSERT_REPLAY_ROW,
                    "source_tier":           source_tier,
                    "p5_can_apply":          False,
                    "dry_run_only":          True,
                    "has_predicted_numbers": has_numbers,
                    "provenance_hash":       prov_hash,
                    "run_id":                run_id,
                    "item_count":            row["item_count"],
                    "lifecycle_state":       lifecycle,
                    "lifecycle_warning":     lifecycle_warning,
                    "created_by_phase":      "P5",
                    "skip_reason":           None,
                })

    # Summaries
    plan_insert = [c for c in plan_cells if c["planned_action"] == PLAN_INSERT_REPLAY_ROW]
    skipped     = [c for c in plan_cells if c["planned_action"] != PLAN_INSERT_REPLAY_ROW]

    from collections import Counter
    actions_counter = Counter(c["planned_action"] for c in plan_cells)

    plan_output = {
        "phase":                    "P5",
        "generated_at":             generated_at,
        "p1_source":                str(P1_PLAN),
        "dry_run_only":             True,
        "total_plan_rows":          len(plan_cells),
        "plan_insert_rows":         len(plan_insert),
        "skipped_rows":             len(skipped),
        "by_planned_action":        dict(actions_counter),
        "reconstructible_strategies": len(reconstructible_entries),
        "strategies_with_db_data":  sum(1 for i in inventory if i["has_db_prediction_items"]),
        "strategies_without_data":  sum(1 for i in inventory if not i["has_db_prediction_items"]),
        "plan_cells":               plan_cells,
    }

    inventory_output = {
        "phase":         "P5",
        "generated_at":  generated_at,
        "strategies":    inventory,
    }

    return plan_output, inventory_output


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="P5 Historical Reconstruction Plan — READ-ONLY"
    )
    parser.add_argument(
        "--plan-out",
        default=str(REPO_ROOT / "outputs" / "replay" / "p5_historical_reconstruction_plan_20260520.json"),
    )
    parser.add_argument(
        "--inventory-out",
        default=str(REPO_ROOT / "outputs" / "replay" / "p5_reconstruction_input_inventory_20260520.json"),
    )
    args = parser.parse_args()

    # Load P1 catalog
    p1_entries = _load_p1_entries()
    print(f"P1 catalog loaded: {len(p1_entries)} entries")

    # Open DB read-only
    conn = _open_db()
    try:
        plan_output, inventory_output = build_p5_plan(conn, p1_entries)
    finally:
        conn.close()

    # Write outputs
    plan_path = pathlib.Path(args.plan_out)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan_output, indent=2, ensure_ascii=False))

    inv_path = pathlib.Path(args.inventory_out)
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text(json.dumps(inventory_output, indent=2, ensure_ascii=False))

    print(f"\n=== P5 Historical Reconstruction Plan ===")
    print(f"Total plan rows:        {plan_output['total_plan_rows']}")
    print(f"PLAN_INSERT_REPLAY_ROW: {plan_output['plan_insert_rows']}")
    print(f"Skipped:                {plan_output['skipped_rows']}")
    print(f"Strategies with data:   {plan_output['strategies_with_db_data']}")
    print(f"Strategies without:     {plan_output['strategies_without_data']}")
    print(f"\nPlan written to:        {plan_path}")
    print(f"Inventory written to:   {inv_path}")


if __name__ == "__main__":
    main()
