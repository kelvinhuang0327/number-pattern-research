#!/usr/bin/env python3
"""
p12_1500_draw_replay_gap_analysis.py
======================================
P12 1500-Draw Historical Replay Backfill Gap Analysis.

Read-only analysis script. No DB writes. No strategy execution.
No fake rows generated.

Analyses:
  - Current 460 production replay rows (coverage, draw range, status)
  - Registry: 18 strategies (8 ONLINE + 4 REJECTED + 5 RETIRED + 1 OBSERVATION)
  - Catalog universe: 59 total (18 registry + 41 ARTIFACT_CANDIDATE)
  - Draw availability in DB per lottery type
  - Gap between current 460 rows and 1500-draw target
  - Phase 1 recommendation: 2 ONLINE strategies × 1500 draws = 3000 rows

HARD CONSTRAINTS:
  - dry_run_only = True
  - No DB writes
  - No predicted_numbers generation
  - artifact-only entries NOT counted as executable
  - NO_DATA entries NOT counted as success
  - p7_28_rows_is_product_complete = False
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
OUTPUT_DIR = REPO_ROOT / "outputs" / "replay"
OUTPUT_JSON = OUTPUT_DIR / "p12_1500_draw_gap_analysis_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

PHASE              = "P12_1500_DRAW_REPLAY_GAP_ANALYSIS"
TARGET_DRAW_WINDOW = 1500
REGISTRY_COUNT     = 18
CATALOG_UNIVERSE   = 59
ARTIFACT_ONLY_COUNT = 41
PROJECTED_ROWS_18  = REGISTRY_COUNT * TARGET_DRAW_WINDOW  # 27000


# ---------------------------------------------------------------------------
# DB helpers — read-only
# ---------------------------------------------------------------------------

def _open_readonly(path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path.resolve()))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Replay row analysis
# ---------------------------------------------------------------------------

def _analyse_current_rows(conn: sqlite3.Connection) -> dict:
    """Analyse the 460 production replay rows (read-only)."""
    rows = conn.execute(
        "SELECT strategy_id, strategy_name, lottery_type, target_draw, "
        "       replay_status, truth_level, source "
        "FROM strategy_prediction_replays"
    ).fetchall()

    total = len(rows)

    # By strategy
    by_strategy: dict[str, int] = {}
    by_lottery: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_truth: dict[str, int] = {}
    draws_seen: dict[str, set] = {}

    for r in rows:
        sid = r["strategy_id"]
        lt  = r["lottery_type"]
        st  = r["replay_status"] or "NULL"
        tl  = r["truth_level"]   or "NULL"
        dr  = r["target_draw"]

        by_strategy[sid] = by_strategy.get(sid, 0) + 1
        by_lottery[lt]   = by_lottery.get(lt, 0)   + 1
        by_status[st]    = by_status.get(st, 0)    + 1
        by_truth[tl]     = by_truth.get(tl, 0)     + 1
        draws_seen.setdefault(lt, set()).add(dr)

    unique_draws_by_lottery = {k: len(v) for k, v in draws_seen.items()}

    # Draw range per lottery
    draw_range: dict[str, dict] = {}
    for lt in draws_seen:
        draws = sorted(draws_seen[lt])
        draw_range[lt] = {"min": draws[0], "max": draws[-1], "count": len(draws)}

    return {
        "total":                   total,
        "by_strategy":             by_strategy,
        "by_lottery_type":         by_lottery,
        "by_replay_status":        by_status,
        "by_truth_level":          by_truth,
        "unique_draws_by_lottery": unique_draws_by_lottery,
        "draw_range_by_lottery":   draw_range,
    }


# ---------------------------------------------------------------------------
# Historical draw availability
# ---------------------------------------------------------------------------

def _analyse_available_draws(conn: sqlite3.Connection) -> dict:
    """Count available historical draws per lottery type."""
    rows = conn.execute(
        "SELECT lottery_type, COUNT(*) as cnt, MIN(draw) as min_draw, MAX(draw) as max_draw "
        "FROM draws GROUP BY lottery_type"
    ).fetchall()
    return {
        r["lottery_type"]: {
            "total_draws": r["cnt"],
            "min_draw":    r["min_draw"],
            "max_draw":    r["max_draw"],
            "sufficient_for_1500": r["cnt"] >= TARGET_DRAW_WINDOW + 100,  # +100 min_history
        }
        for r in rows
    }


# ---------------------------------------------------------------------------
# Registry strategy classification
# ---------------------------------------------------------------------------

def _classify_registry_strategies() -> dict:
    """
    Classify all 18 registry strategies by executability.
    Does NOT execute any prediction. Read metadata only.
    """
    from lottery_api.models.replay_strategy_registry import list_strategies

    all_strats = list_strategies()

    online_candidates:     list[dict] = []
    rejected_blocked:      list[dict] = []
    retired_blocked:       list[dict] = []
    observation_blocked:   list[dict] = []
    no_data_exclusions:    list[str]  = []

    # Catalog visibility data for cross-reference
    catalog_path = REPO_ROOT / "outputs" / "replay" / "p2_full_catalog_visibility_plan_20260520.json"
    catalog_lookup: dict[str, dict] = {}
    if catalog_path.exists():
        with open(catalog_path) as f:
            catalog_data = json.load(f)
        for e in catalog_data.get("entries", []):
            catalog_lookup[e["strategy_id"]] = e

    for s in all_strats:
        sid    = s["strategy_id"]
        status = s["strategy_lifecycle_status"]
        ltypes = s["supported_lottery_types"]
        min_h  = s["min_history"]

        cv_entry = catalog_lookup.get(sid, {})
        vis      = cv_entry.get("visibility_state", "UNKNOWN")
        row_cnt  = cv_entry.get("replay_row_count", 0)

        entry = {
            "strategy_id":          sid,
            "strategy_name":        s["strategy_name"],
            "lifecycle_status":     status,
            "supported_lottery_types": ltypes,
            "min_history":          min_h,
            "current_rows":         row_cnt,
            "visibility_state":     vis,
        }

        if status == "ONLINE":
            entry["executable"] = True
            entry["block_reason"] = None
            online_candidates.append(entry)
        elif status == "REJECTED":
            entry["executable"]   = False
            entry["block_reason"] = "REJECTED_by_governance"
            no_data_exclusions.append(sid)
            rejected_blocked.append(entry)
        elif status == "RETIRED":
            entry["executable"]   = False
            entry["block_reason"] = "RETIRED_needs_independent_human_review"
            retired_blocked.append(entry)
        elif status == "OBSERVATION":
            entry["executable"]   = False
            entry["block_reason"] = "OBSERVATION_pending_shadow_evaluation"
            observation_blocked.append(entry)
        else:
            entry["executable"]   = False
            entry["block_reason"] = f"UNKNOWN_status_{status}"

    blocked_all = rejected_blocked + retired_blocked + observation_blocked

    return {
        "online_candidates":       online_candidates,
        "rejected_blocked":        rejected_blocked,
        "retired_blocked":         retired_blocked,
        "observation_blocked":     observation_blocked,
        "all_blocked":             blocked_all,
        "online_count":            len(online_candidates),
        "blocked_count":           len(blocked_all),
        "no_data_exclusions":      no_data_exclusions,
    }


# ---------------------------------------------------------------------------
# Phase 1 recommendation
# ---------------------------------------------------------------------------

def _recommend_phase1(online_candidates: list[dict], available_draws: dict) -> dict:
    """
    Recommend 2 ONLINE strategies for Phase 1 dry-run.
    Prefer strategies with existing rows (proven working) and diverse lottery types.
    """
    # Sort by current_rows descending (prefer those with existing rows = proven)
    sorted_cands = sorted(online_candidates, key=lambda x: -x["current_rows"])

    chosen: list[dict] = []
    seen_lottery_types: set = set()

    # First pass: pick one per lottery type (diverse coverage)
    for c in sorted_cands:
        for lt in c["supported_lottery_types"]:
            if lt not in seen_lottery_types and available_draws.get(lt, {}).get("sufficient_for_1500", False):
                chosen.append({
                    "strategy_id":    c["strategy_id"],
                    "strategy_name":  c["strategy_name"],
                    "lottery_type":   lt,
                    "current_rows":   c["current_rows"],
                    "min_history":    c["min_history"],
                })
                seen_lottery_types.add(lt)
                break
        if len(chosen) >= 2:
            break

    # If we didn't get 2, fill from remaining
    if len(chosen) < 2:
        for c in sorted_cands:
            if not any(x["strategy_id"] == c["strategy_id"] for x in chosen):
                lt = c["supported_lottery_types"][0]
                if available_draws.get(lt, {}).get("sufficient_for_1500", False):
                    chosen.append({
                        "strategy_id":    c["strategy_id"],
                        "strategy_name":  c["strategy_name"],
                        "lottery_type":   lt,
                        "current_rows":   c["current_rows"],
                        "min_history":    c["min_history"],
                    })
                if len(chosen) >= 2:
                    break

    return {
        "strategy_count":    len(chosen),
        "draw_window":       TARGET_DRAW_WINDOW,
        "estimated_rows":    len(chosen) * TARGET_DRAW_WINDOW,
        "dry_run_only":      True,
        "strategies":        chosen,
        "note":              "Dry-run only. No DB writes. CEO authorization required before apply.",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(json_out: pathlib.Path | None = None) -> dict:
    conn = _open_readonly(DB_PATH)

    try:
        # 1. Current replay row analysis
        current = _analyse_current_rows(conn)

        # 2. Historical draw availability
        available_draws = _analyse_available_draws(conn)

        # 3. Registry strategy classification
        registry = _classify_registry_strategies()

        # 4. Gap calculation
        current_total   = current["total"]
        gap_vs_18       = PROJECTED_ROWS_18 - current_total
        gap_vs_online_8 = (registry["online_count"] * TARGET_DRAW_WINDOW) - current_total

        # 5. Phase 1 recommendation
        phase1 = _recommend_phase1(registry["online_candidates"], available_draws)

        # 6. Draw sufficiency check
        draw_sufficiency = {
            lt: info for lt, info in available_draws.items()
            if lt in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO")
        }

        # 7. Summary
        result = {
            "phase":                          PHASE,
            "generated_at":                   datetime.datetime.utcnow().isoformat() + "Z",
            "dry_run_only":                   True,
            "db_write_performed":             False,
            "strategy_execution_performed":   False,
            "fake_success_count":             0,

            # Current state
            "production_rows":                current_total,
            "current_replay_rows":            current_total,
            "rows_by_strategy":               current["by_strategy"],
            "rows_by_lottery_type":           current["by_lottery_type"],
            "rows_by_replay_status":          current["by_replay_status"],
            "rows_by_truth_level":            current["by_truth_level"],
            "rows_by_draw_range":             current["draw_range_by_lottery"],
            "unique_draws_by_lottery":        current["unique_draws_by_lottery"],

            # Target
            "target_draw_window":             TARGET_DRAW_WINDOW,
            "registry_strategy_count":        REGISTRY_COUNT,
            "catalog_universe_count":         CATALOG_UNIVERSE,
            "projected_rows_for_18_strategies": PROJECTED_ROWS_18,
            "projected_rows_for_8_online_strategies": registry["online_count"] * TARGET_DRAW_WINDOW,

            # Gaps
            "current_gap_vs_18_strategies":   gap_vs_18,
            "current_gap_vs_online_8_strategies": gap_vs_online_8,

            # Product truth
            "p7_28_rows_is_product_complete": False,
            "p7_28_rows_note":                (
                "The 28-row P7 controlled apply candidate is a small subset of "
                "registry-only ONLINE rows. Applying them would bring total to 488. "
                "This is NOT the 1500-draw product target."
            ),

            # Strategy classification
            "online_strategy_candidates":    [s["strategy_id"] for s in registry["online_candidates"]],
            "online_strategy_details":       registry["online_candidates"],
            "executable_strategy_candidates": [s["strategy_id"] for s in registry["online_candidates"]],
            "blocked_strategy_candidates":   [s["strategy_id"] for s in registry["all_blocked"]],
            "rejected_blocked":              [s["strategy_id"] for s in registry["rejected_blocked"]],
            "retired_blocked":               [s["strategy_id"] for s in registry["retired_blocked"]],
            "observation_blocked":           [s["strategy_id"] for s in registry["observation_blocked"]],

            # Catalog constraints
            "artifact_only_count":           ARTIFACT_ONLY_COUNT,
            "artifact_only_note":            (
                "41 ARTIFACT_CANDIDATE entries in catalog are NOT in the strategy registry. "
                "They cannot execute predictions. Visibility-only."
            ),
            "no_data_exclusions":            registry["no_data_exclusions"],

            # Draw data sufficiency
            "available_draws_by_lottery":    draw_sufficiency,
            "draw_data_sufficient_for_1500": all(
                v.get("sufficient_for_1500", False)
                for v in draw_sufficiency.values()
            ),

            # Phase 1
            "recommended_phase_1":           phase1,

            # Phase roadmap summary
            "phase_roadmap": [
                {"phase": "P12", "description": "1500-draw gap analysis and backfill architecture"},
                {"phase": "P13", "description": "Backfill engine skeleton, dry-run only"},
                {"phase": "P14", "description": "2 ONLINE strategies × 1500 draws dry-run"},
                {"phase": "P15", "description": "Apply gate for Phase 1 backfill (CEO authorization required)"},
                {"phase": "P16", "description": "Expand to all 8 ONLINE strategies"},
                {"phase": "P17", "description": "API pagination / query optimization"},
                {"phase": "P18", "description": "UI history list integration"},
                {"phase": "P19", "description": "RETIRED / OBSERVATION / REJECTED governance"},
                {"phase": "P20", "description": "Production launch checklist"},
            ],

            # Safety flags
            "safety_flags": {
                "no_db_write":               True,
                "no_strategy_execution":     True,
                "no_fake_rows":              True,
                "no_artifact_as_executable": True,
                "no_no_data_as_success":     True,
                "no_p7_apply":               True,
                "no_retired_apply":          True,
            },
        }

    finally:
        conn.close()

    # Write output
    out_path = json_out or OUTPUT_JSON
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[P12] Gap analysis complete.")
    print(f"  Production rows:           {current_total}")
    print(f"  Target window:             {TARGET_DRAW_WINDOW} draws")
    print(f"  Registry strategies:       {REGISTRY_COUNT} (8 ONLINE, 4 REJECTED, 5 RETIRED, 1 OBSERVATION)")
    print(f"  ONLINE executable:         {registry['online_count']}")
    print(f"  Projected 18×1500 rows:    {PROJECTED_ROWS_18:,}")
    print(f"  Gap (vs 18 strategies):    {gap_vs_18:,}")
    print(f"  Gap (vs 8 ONLINE):         {gap_vs_online_8:,}")
    print(f"  p7_28_rows_is_product_complete: False")
    print(f"  Draw data sufficient:      {result['draw_data_sufficient_for_1500']}")
    print(f"  Phase 1 recommendation:    {phase1['strategy_count']} strategies × {TARGET_DRAW_WINDOW} draws = {phase1['estimated_rows']} rows")
    print(f"  Output: {out_path}")
    print(f"  Final classification: P12_1500_DRAW_BACKFILL_PLAN_READY")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P12 1500-draw replay gap analysis (read-only)")
    parser.add_argument("--json-out", type=pathlib.Path, default=None,
                        help="Override output JSON path")
    args = parser.parse_args()
    main(json_out=args.json_out)
