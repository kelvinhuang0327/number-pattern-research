"""P251A — Cross-lottery evidence dashboard dry-run plan.

Read-only dashboard data-contract/spec built from the published P250A
inventory artifact. This does not implement any UI/API behavior; it only
defines the evidence model, sections, and filter semantics needed for a future
dashboard.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


TASK_ID = "P251A"
SCHEMA_VERSION = "1.0"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
P250A_JSON_PATH = OUTPUT_DIR / "p250a_cross_lottery_strategy_replay_inventory_20260606.json"

JSON_OUTPUT = OUTPUT_DIR / f"p251a_cross_lottery_evidence_dashboard_dryrun_plan_{DATE_SLUG}.json"
MD_OUTPUT = OUTPUT_DIR / f"p251a_cross_lottery_evidence_dashboard_dryrun_plan_{DATE_SLUG}.md"


def _load_p250a() -> Dict[str, Any]:
    if not P250A_JSON_PATH.exists():
        raise FileNotFoundError(f"Missing P250A artifact: {P250A_JSON_PATH}")
    return json.loads(P250A_JSON_PATH.read_text(encoding="utf-8"))


def _lottery_rows(p250a: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(p250a["replay_coverage_by_lottery"])


def build_dashboard_contract() -> Dict[str, Any]:
    p250a = _load_p250a()
    lottery_rows = _lottery_rows(p250a)

    global_summary = {
        "source_of_truth": "P250A inventory artifact (published on main)",
        "current_registry_is_live_ssot": True,
        "historical_scoreboard_is_snapshot": True,
        "inventory_entries": p250a["inventory_counts"]["historical_inventory_entries"],
        "current_registry_entries": p250a["inventory_counts"]["current_registry_entries"],
        "artifact_only_entries": p250a["inventory_counts"]["artifact_only_entries"],
        "replay_rows_total": p250a["db_read_status"]["replay_rows_total"],
        "draw_rows_total": p250a["db_read_status"]["draw_rows_total"],
        "canonical_big_lotto_rows": p250a["db_read_status"]["canonical_big_lotto_rows"],
        "no_deployable_candidate": True,
        "no_prediction_edge_claim": True,
        "lifecycle_is_label_not_exclusion": True,
    }

    lifecycle_badge_vocabulary = [
        {
            "status": "ONLINE",
            "badge": "active",
            "meaning": "Currently active in the current registry; does not imply a betting edge.",
        },
        {
            "status": "REJECTED",
            "badge": "rejected",
            "meaning": "Evaluated and rejected; remains visible in historical replay views.",
        },
        {
            "status": "RETIRED",
            "badge": "retired",
            "meaning": "Formerly used, now retired; historical rows remain visible.",
        },
        {
            "status": "OBSERVATION",
            "badge": "observation",
            "meaning": "Shadow / observation-only; visible but non-promotional.",
        },
        {
            "status": "ARTIFACT_ONLY",
            "badge": "artifact-only",
            "meaning": "Evidence-only row or snapshot entry that should remain visible.",
        },
        {
            "status": "LIFECYCLE_UNRESOLVED",
            "badge": "historical-snapshot",
            "meaning": "Legacy snapshot state; use the live registry status alongside it.",
        },
    ]

    strategy_table_columns = [
        "strategy_id",
        "strategy_name",
        "lottery_type",
        "current_registry_lifecycle_status",
        "historical_snapshot_lifecycle_status",
        "latest_classification",
        "replay_presence",
        "replay_rows",
        "draw_rows",
        "canonical_rows",
        "artifact_only_flag",
        "evidence_state",
        "badge",
        "filter_tags",
        "source_artifacts",
    ]

    evidence_state_columns = [
        "current_registry_presence",
        "historical_scoreboard_presence",
        "current_registry_lifecycle_status",
        "historical_snapshot_lifecycle_status",
        "current_lifecycle_source",
        "catalog_source_snapshot",
        "replay_presence",
        "replay_rows",
        "distinct_target_draws",
        "draw_rows",
        "canonical_rows",
        "status_note",
        "latest_classification",
        "included_in_historical_replay_or_catalog_views",
    ]

    filter_semantics = {
        "default_behavior": "include all rows/cards by default; filters narrow the view but do not hide historical entries automatically",
        "lifecycle_filter": "badge/filter only; never an exclusion rule",
        "registry_filter": "can show current-registry-only rows, but should never erase historical snapshot rows unless user explicitly asks",
        "snapshot_filter": "can reveal historical snapshot state side-by-side with current registry status",
        "lottery_filter": "scope by lottery_type without changing visibility rules",
        "artifact_only_filter": "must keep artifact-only rows visible by default and explicitly labeled",
    }

    no_exclusion_rules = [
        "Do not exclude strategies because they are retired, rejected, offline, observation, unresolved, or artifact-only.",
        "Do not hide replay-backed historical rows when lifecycle is not ONLINE.",
        "Do not infer deployability from inventory presence, row counts, or historical classifications alone.",
        "Do not treat P232A as live state; it is a historical snapshot and must not replace the current registry SSOT.",
        "Do not hide BIG_LOTTO add-on / canonical split information; display it as evidence state.",
    ]

    stale_snapshot_warning = {
        "message": "P232A is a historical replay snapshot from 20260604 and is stale relative to the live registry SSOT published in P250A/P250B.",
        "current_registry_ssot": "lottery_api/models/replay_strategy_registry.py",
        "historical_snapshot": "outputs/research/p232a_all_catalog_strategy_replay_scoreboard_20260604.json",
        "dashboard_behavior": "show both states together, with the current registry as primary and the snapshot as evidence context.",
    }

    no_betting_advice_notice = {
        "message": "This dashboard is an evidence contract, not betting advice.",
        "no_claims": [
            "No predictive edge is claimed.",
            "No strategy promotion is implied.",
            "No production recommendation is changed.",
            "GREEN canonical randomness remains a data-quality result, not a signal.",
            "Current inventory has no active deployable candidate.",
        ],
    }

    implementation_candidates_for_future = [
        {
            "priority": 1,
            "name": "Cross-lottery evidence dashboard UI",
            "why": "Render the contract as a registry-aware evidence table with badges and snapshot state.",
            "scope": "Frontend only; no new prediction logic.",
        },
        {
            "priority": 2,
            "name": "Evidence dashboard API payload",
            "why": "Serve the same contract as a read-only JSON payload for UI and reports.",
            "scope": "API contract only; no DB writes.",
        },
        {
            "priority": 3,
            "name": "Badge legend and filter chips",
            "why": "Make lifecycle visible without hiding historical rows.",
            "scope": "Display layer only.",
        },
        {
            "priority": 4,
            "name": "Stale snapshot banner",
            "why": "Warn users that P232A is historical and the current registry is live SSOT.",
            "scope": "Display layer only.",
        },
    ]

    lottery_summary = []
    for row in lottery_rows:
        lottery_summary.append(
            {
                "lottery_type": row["lottery_type"],
                "cards_to_show": row["developed_strategy_entries"],
                "replay_strategy_entries": row["replay_strategy_entries"],
                "replay_rows": row["replay_rows"],
                "draw_rows": row["draw_rows"],
                "canonical_rows": row["canonical_rows"],
                "distinct_replay_draws": row["distinct_replay_draws"],
                "visible_rows_by_default": True,
                "lifecycle_visibility_rule": "label/filter only; never exclusion",
                "artifact_only_entries_visible": row["lottery_type"] == "POWER_LOTTO",
                "snapshot_notes": row["notes"],
                "evidence_row_semantics": row["row_semantics"],
            }
        )

    dashboard_contract = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "CROSS_LOTTERY_EVIDENCE_DASHBOARD_DRYRUN_PLAN",
        "source_artifact": str(P250A_JSON_PATH.relative_to(REPO_ROOT)),
        "global_summary": global_summary,
        "lottery_summary": lottery_summary,
        "lifecycle_badge_vocabulary": lifecycle_badge_vocabulary,
        "strategy_table_columns": strategy_table_columns,
        "evidence_state_columns": evidence_state_columns,
        "filter_semantics": filter_semantics,
        "no_exclusion_rules": no_exclusion_rules,
        "stale_snapshot_warning": stale_snapshot_warning,
        "no_betting_advice_notice": no_betting_advice_notice,
        "implementation_candidates_for_future": implementation_candidates_for_future,
        "preserved_p250a_conclusions": {
            "current_registry_is_live_ssot": True,
            "p232a_scoreboard_is_historical_snapshot": True,
            "artifact_only_entries_must_remain_visible": True,
            "lifecycle_is_label_not_exclusion": True,
            "no_active_deployable_candidate": True,
        },
        "compliance": {
            "read_only": True,
            "no_db_write": True,
            "no_registry_mutation": True,
            "no_strategy_logic_change": True,
            "no_production_recommendation_change": True,
            "no_betting_advice": True,
        },
    }
    return dashboard_contract


def build_md_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    A = lines.append

    A("# P251A — Cross-Lottery Evidence Dashboard Dry-Run Plan")
    A("")
    A(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    A(f"**Task:** `{TASK_ID}`  ")
    A(f"**Classification:** `{report['classification']}`  ")
    A("")
    A("## Executive Summary")
    A("")
    A(
        "This is a read-only dashboard data-contract dry-run plan. It uses the published "
        "P250A inventory artifact as evidence and defines how a future dashboard should "
        "show current registry state, historical snapshot state, lifecycle badges, and "
        "replay/draw/canonical evidence without hiding historical entries."
    )
    A("")
    A("## global_summary")
    A("")
    for key, value in report["global_summary"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("## lottery_summary")
    A("")
    for item in report["lottery_summary"]:
        A(f"### {item['lottery_type']}")
        A("")
        A(f"- cards_to_show: `{item['cards_to_show']}`")
        A(f"- replay_strategy_entries: `{item['replay_strategy_entries']}`")
        A(f"- replay_rows: `{item['replay_rows']}`")
        A(f"- draw_rows: `{item['draw_rows']}`")
        A(f"- canonical_rows: `{item['canonical_rows']}`")
        A(f"- distinct_replay_draws: `{item['distinct_replay_draws']}`")
        A(f"- visible_rows_by_default: `{item['visible_rows_by_default']}`")
        A(f"- lifecycle_visibility_rule: `{item['lifecycle_visibility_rule']}`")
        A(f"- artifact_only_entries_visible: `{item['artifact_only_entries_visible']}`")
        for note in item["snapshot_notes"]:
            A(f"- note: {note}")
        A("")
    A("## lifecycle_badge_vocabulary")
    A("")
    for item in report["lifecycle_badge_vocabulary"]:
        A(f"- `{item['status']}` → `{item['badge']}`: {item['meaning']}")
    A("")
    A("## strategy_table_columns")
    A("")
    for col in report["strategy_table_columns"]:
        A(f"- `{col}`")
    A("")
    A("## evidence_state_columns")
    A("")
    for col in report["evidence_state_columns"]:
        A(f"- `{col}`")
    A("")
    A("## filter_semantics")
    A("")
    for key, value in report["filter_semantics"].items():
        A(f"- {key}: {value}")
    A("")
    A("## no_exclusion_rules")
    A("")
    for rule in report["no_exclusion_rules"]:
        A(f"- {rule}")
    A("")
    A("## stale_snapshot_warning")
    A("")
    for key, value in report["stale_snapshot_warning"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("## no_betting_advice_notice")
    A("")
    A(f"- message: {report['no_betting_advice_notice']['message']}")
    for claim in report["no_betting_advice_notice"]["no_claims"]:
        A(f"- {claim}")
    A("")
    A("## implementation_candidates_for_future")
    A("")
    for item in report["implementation_candidates_for_future"]:
        A(f"### {item['priority']}. {item['name']}")
        A("")
        A(f"- why: {item['why']}")
        A(f"- scope: {item['scope']}")
        A("")
    A("## preserved_p250a_conclusions")
    A("")
    for key, value in report["preserved_p250a_conclusions"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("## compliance")
    A("")
    for key, value in report["compliance"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("Final Classification: `CROSS_LOTTERY_EVIDENCE_DASHBOARD_DRYRUN_PLAN`")
    return "\n".join(lines)


def main() -> int:
    report = build_dashboard_contract()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUTPUT.write_text(build_md_report(report), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {MD_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
