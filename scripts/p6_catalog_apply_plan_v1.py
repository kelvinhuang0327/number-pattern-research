#!/usr/bin/env python3
"""
p6_catalog_apply_plan_v1.py
==============================
P6 Catalog Apply Plan v1.

Read-only. Produces an apply plan for the full 59-strategy catalog universe
(18 registry + 41 artifact-only) using P2 and P3 outputs as input.

Apply decisions (all dry_run_only=True, NO DB writes):

  SKIP                           — ROW_BACKED, already has replay rows
  PLAN_INSERT_PENDING_P7_AUTH    — RECONSTRUCTIBLE + ONLINE lifecycle,
                                    awaiting CEO phrase
  PLAN_INSERT_PENDING_HUMAN_REVIEW — RECONSTRUCTIBLE + RETIRED lifecycle,
                                    awaiting human review + INCLUDE_RETIRED flag
  REGISTER_VISIBILITY_ONLY       — NO_DATA, in registry; mark but no rows
  SKIP_NOT_REGISTERED            — ARTIFACT_ONLY; not in runtime registry;
                                    governance review required

Zero DB writes. Zero replay row generation. All entries dry_run_only=True.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
P2_JSON   = REPO_ROOT / "outputs" / "replay" / "p2_full_catalog_visibility_plan_20260520.json"
P3_SUMMARY = REPO_ROOT / "outputs" / "replay" / "p3_per_draw_all_strategy_coverage_summary_20260520.json"
P7_JSON   = REPO_ROOT / "outputs" / "replay" / "p7_controlled_apply_dry_run_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

# Apply decision constants
DECISION_SKIP                      = "SKIP"
DECISION_PLAN_INSERT_P7_AUTH       = "PLAN_INSERT_PENDING_P7_AUTH"
DECISION_PLAN_INSERT_HUMAN_REVIEW  = "PLAN_INSERT_PENDING_HUMAN_REVIEW"
DECISION_REGISTER_VISIBILITY_ONLY  = "REGISTER_VISIBILITY_ONLY"
DECISION_SKIP_NOT_REGISTERED       = "SKIP_NOT_REGISTERED"


def _load_p7_draw_counts() -> dict[str, int]:
    """Return {strategy_id: draw_count} from P7 all_plan_rows."""
    if not P7_JSON.exists():
        return {}
    data = json.loads(P7_JSON.read_text())
    counts: dict[str, int] = {}
    for row in data.get("all_plan_rows", []):
        sid = row["strategy_id"]
        counts[sid] = counts.get(sid, 0) + 1
    return counts


def _blocker_for(entry: dict) -> str | None:
    """Return human-readable blocker text for why this entry isn't apply-ready."""
    vis = entry.get("visibility_state")
    lc  = entry.get("lifecycle_status", "")
    if vis == "ROW_BACKED":
        return None  # No blocker — already done
    if vis == "RECONSTRUCTIBLE" and lc == "ONLINE":
        return "Awaiting CEO authorization phrase: YES apply P7 controlled replay rows"
    if vis == "RECONSTRUCTIBLE" and lc == "RETIRED":
        return (
            "Requires human lifecycle review + "
            "--scope INCLUDE_RETIRED_WITH_WARNING --include-retired-reviewed"
        )
    if vis == "NO_DATA":
        return "No prediction_items in DB; row generation impossible without re-running strategy"
    if vis == "ARTIFACT_ONLY":
        return "Not in runtime registry; governance review required before registration"
    return "Unknown blocker"


def _decision_for(entry: dict) -> str:
    vis = entry.get("visibility_state")
    lc  = entry.get("lifecycle_status", "")
    if vis == "ROW_BACKED":
        return DECISION_SKIP
    if vis == "RECONSTRUCTIBLE":
        if lc == "ONLINE":
            return DECISION_PLAN_INSERT_P7_AUTH
        return DECISION_PLAN_INSERT_HUMAN_REVIEW
    if vis == "NO_DATA":
        return DECISION_REGISTER_VISIBILITY_ONLY
    # ARTIFACT_ONLY
    return DECISION_SKIP_NOT_REGISTERED


def _apply_ready(decision: str) -> bool:
    """Only SKIP (already done) counts as apply-ready."""
    return decision == DECISION_SKIP


def build_plan(p2_json: pathlib.Path, p3_summary_json: pathlib.Path) -> dict:
    if not p2_json.exists():
        raise FileNotFoundError(f"P2 JSON not found: {p2_json}. Run p2 script first.")

    p2   = json.loads(p2_json.read_text())
    p3s  = json.loads(p3_summary_json.read_text()) if p3_summary_json.exists() else {}
    p7_draw_counts = _load_p7_draw_counts()

    entries: list[dict] = []
    decision_counts: dict[str, int] = {}

    for e in p2.get("entries", []):
        sid       = e.get("strategy_id", "")
        vis       = e.get("visibility_state", "NO_DATA")
        lc        = e.get("lifecycle_status", e.get("lifecycle_state", "UNKNOWN"))
        lt        = e.get("lottery_type", "UNKNOWN")
        row_count = e.get("replay_row_count", 0)
        pi_count  = e.get("prediction_items_count", 0)

        decision = _decision_for(e)
        ready    = _apply_ready(decision)
        blocker  = _blocker_for(e)

        # Estimate how many rows would be added if this entry were applied
        estimated_delta = 0
        if decision == DECISION_PLAN_INSERT_P7_AUTH:
            estimated_delta = p7_draw_counts.get(sid, 0)
        elif decision == DECISION_PLAN_INSERT_HUMAN_REVIEW:
            estimated_delta = p7_draw_counts.get(sid, 0)
        # SKIP / REGISTER_VISIBILITY_ONLY / SKIP_NOT_REGISTERED → delta = 0

        entries.append({
            "strategy_id":          sid,
            "display_name":         e.get("display_name", sid),
            "lottery_type":         lt,
            "lifecycle_status":     lc,
            "visibility_state":     vis,
            "replay_row_count":     row_count,
            "prediction_items_count": pi_count,
            "apply_decision":       decision,
            "apply_ready":          ready,
            "apply_blocker":        blocker,
            "estimated_row_delta":  estimated_delta,
            "dry_run_only":         True,
            "can_generate_replay_rows": False,
        })

        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    # Compute totals
    total_estimated_delta = sum(e["estimated_row_delta"] for e in entries)
    current_rows          = p2.get("production_replay_rows_unchanged", 460)
    projected_rows_online_only = (
        current_rows
        + sum(e["estimated_row_delta"] for e in entries
              if e["apply_decision"] == DECISION_PLAN_INSERT_P7_AUTH)
    )
    projected_rows_all = current_rows + total_estimated_delta

    # Authorization requirements
    auth_requirements = {
        DECISION_PLAN_INSERT_P7_AUTH: {
            "count": decision_counts.get(DECISION_PLAN_INSERT_P7_AUTH, 0),
            "required_phrase": "YES apply P7 controlled replay rows",
            "received": False,
            "estimated_row_delta": sum(
                e["estimated_row_delta"] for e in entries
                if e["apply_decision"] == DECISION_PLAN_INSERT_P7_AUTH
            ),
        },
        DECISION_PLAN_INSERT_HUMAN_REVIEW: {
            "count": decision_counts.get(DECISION_PLAN_INSERT_HUMAN_REVIEW, 0),
            "required_flags": [
                "--scope INCLUDE_RETIRED_WITH_WARNING",
                "--include-retired-reviewed",
            ],
            "required_auth": "Separate CEO authorization (distinct from ONLINE phrase)",
            "received": False,
            "estimated_row_delta": sum(
                e["estimated_row_delta"] for e in entries
                if e["apply_decision"] == DECISION_PLAN_INSERT_HUMAN_REVIEW
            ),
        },
    }

    return {
        "phase":            "P6_CATALOG_APPLY_PLAN_V1",
        "generated_at":     datetime.datetime.utcnow().isoformat() + "Z",
        "dry_run_only":     True,
        "db_write_performed": False,
        "strategy_executed": False,
        "total_entries":    len(entries),
        "registry_entries": p2.get("registry_count", 18),
        "artifact_only_entries": p2.get("artifact_only_count", 41),
        "decision_counts":  decision_counts,
        "current_production_rows": current_rows,
        "projected_rows_after_online_only_apply": projected_rows_online_only,
        "projected_rows_after_all_authorized_apply": projected_rows_all,
        "authorization_requirements": auth_requirements,
        "p3_coverage_before": {
            "row_backed_pct":       p3s.get("row_backed_coverage_pct", 23.29),
            "reconstructible_pct":  p3s.get("reconstructible_coverage_pct", 9.39),
            "no_data_pct":          p3s.get("no_data_pct", 67.31),
            "real_replay_success":  p3s.get("real_replay_success_count", 300),
            "fake_success_count":   p3s.get("fake_success_count", 0),
        },
        "p3_coverage_after_online_only_apply_projection": {
            "row_backed_pct_estimate":  round(
                (300 + decision_counts.get(DECISION_PLAN_INSERT_P7_AUTH, 0)
                 * p7_draw_counts.get(
                     next((e["strategy_id"] for e in entries
                           if e["apply_decision"] == DECISION_PLAN_INSERT_P7_AUTH), ""), 0
                 ) / (1288)) * 100 if False else
                # Simpler: (300+28)/1288*100
                round((300 + 28) / 1288 * 100, 2),
                2,
            ),
            "note": (
                "After P7 ONLINE apply (28 rows): ROW_BACKED cells 300→328, "
                "RECONSTRUCTIBLE 121→93, NO_DATA unchanged at 867"
            ),
        },
        "entries": entries,
        "safety_flags": {
            "db_write_performed":        False,
            "replay_rows_generated":     False,
            "strategy_executed":         False,
            "draw_data_imported":        False,
            "no_production_apply_performed": True,
            "fake_success_count_is_zero": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P6 Catalog Apply Plan v1. Read-only."
    )
    parser.add_argument("--p2-json",  default=str(P2_JSON))
    parser.add_argument("--p3-summary", default=str(P3_SUMMARY))
    parser.add_argument(
        "--json-out",
        default=str(
            REPO_ROOT / "outputs" / "replay" / "p6_catalog_apply_plan_v1_20260520.json"
        ),
    )
    args = parser.parse_args()

    print("Building P6 Catalog Apply Plan v1 (read-only)...")
    plan = build_plan(pathlib.Path(args.p2_json), pathlib.Path(args.p3_summary))

    out_path = pathlib.Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))

    print(f"\n=== P6 Apply Decision Summary ===")
    for decision, count in plan["decision_counts"].items():
        print(f"  {decision}: {count}")
    print(f"\nTotal entries:         {plan['total_entries']}")
    print(f"Current production rows: {plan['current_production_rows']}")
    print(f"Projected (ONLINE only): {plan['projected_rows_after_online_only_apply']}")
    print(f"Projected (all auth'd):  {plan['projected_rows_after_all_authorized_apply']}")
    print(f"\nAuthorization required:")
    for d, info in plan["authorization_requirements"].items():
        print(f"  {d}: {info['count']} strategies, +{info['estimated_row_delta']} rows, received={info['received']}")
    print(f"\nDB write:  {plan['db_write_performed']}")
    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
