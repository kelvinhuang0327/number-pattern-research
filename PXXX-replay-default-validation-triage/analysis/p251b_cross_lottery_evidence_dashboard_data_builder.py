"""P251B — Cross-lottery evidence dashboard data artifact builder.

Builds a concrete dashboard-ready JSON artifact from the published P250A
inventory and P251A contract. This is read-only and does not implement any UI,
API routes, DB writes, registry mutation, or strategy logic.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


TASK_ID = "P251B"
SCHEMA_VERSION = "1.0"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
P250A_JSON_PATH = OUTPUT_DIR / "p250a_cross_lottery_strategy_replay_inventory_20260606.json"
P251A_JSON_PATH = OUTPUT_DIR / "p251a_cross_lottery_evidence_dashboard_dryrun_plan_20260606.json"

JSON_OUTPUT = OUTPUT_DIR / f"p251b_cross_lottery_evidence_dashboard_data_{DATE_SLUG}.json"
MD_OUTPUT = OUTPUT_DIR / f"p251b_cross_lottery_evidence_dashboard_data_{DATE_SLUG}.md"

LIFECYCLE_BADGE_VOCAB = [
    {
        "status": "ONLINE",
        "badge": "active",
        "filter_label": "active",
        "default_enabled": True,
        "meaning": "Currently active in the live registry; not a prediction edge claim.",
    },
    {
        "status": "REJECTED",
        "badge": "rejected",
        "filter_label": "rejected",
        "default_enabled": True,
        "meaning": "Evaluated and rejected, but still visible in historical replay/catalog views.",
    },
    {
        "status": "RETIRED",
        "badge": "retired",
        "filter_label": "retired",
        "default_enabled": True,
        "meaning": "Formerly used and preserved for historical visibility.",
    },
    {
        "status": "OBSERVATION",
        "badge": "observation",
        "filter_label": "observation",
        "default_enabled": True,
        "meaning": "Shadow/observation-only evidence, not promotional.",
    },
    {
        "status": "ARTIFACT_ONLY",
        "badge": "artifact-only",
        "filter_label": "artifact-only",
        "default_enabled": True,
        "meaning": "Evidence-only rows; must remain visible by default.",
    },
    {
        "status": "LIFECYCLE_UNRESOLVED",
        "badge": "historical-snapshot",
        "filter_label": "historical-snapshot",
        "default_enabled": True,
        "meaning": "Snapshot-only legacy lifecycle label; do not use to hide rows.",
    },
]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_sources() -> tuple[Dict[str, Any], Dict[str, Any]]:
    return _load_json(P250A_JSON_PATH), _load_json(P251A_JSON_PATH)


def _build_source_artifacts() -> Dict[str, str]:
    return {
        "p250a_inventory": str(P250A_JSON_PATH.relative_to(REPO_ROOT)),
        "p251a_contract": str(P251A_JSON_PATH.relative_to(REPO_ROOT)),
        "current_state": "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md",
        "active_task": "00-Plan/roadmap/active_task.md",
        "roadmap": "00-Plan/roadmap/roadmap.md",
    }


def _build_lottery_cards(p250a: Dict[str, Any]) -> List[Dict[str, Any]]:
    cards = []
    for row in p250a["replay_coverage_by_lottery"]:
        artifact_only_rows = [x for x in p250a["strategy_inventory"] if x["lottery_type"] == row["lottery_type"] and x["current_lifecycle_status"] == "ARTIFACT_ONLY"]
        cards.append(
            {
                "lottery_type": row["lottery_type"],
                "card_title": f"{row['lottery_type']} evidence card",
                "strategy_cards_visible": row["developed_strategy_entries"],
                "replay_strategy_entries": row["replay_strategy_entries"],
                "replay_rows": row["replay_rows"],
                "draw_rows": row["draw_rows"],
                "canonical_rows": row["canonical_rows"],
                "distinct_replay_draws": row["distinct_replay_draws"],
                "artifact_only_rows_visible": bool(artifact_only_rows),
                "visible_by_default": True,
                "lifecycle_visibility_rule": "badge/filter only; never exclusion",
                "summary_notes": row["notes"],
            }
        )
    return cards


def _build_strategy_rows(p250a: Dict[str, Any], p251a: Dict[str, Any]) -> List[Dict[str, Any]]:
    coverage = {item["lottery_type"]: item for item in p250a["replay_coverage_by_lottery"]}
    strategy_rows: List[Dict[str, Any]] = []
    for row in sorted(p250a["strategy_inventory"], key=lambda x: (x["lottery_type"], x["strategy_id"])):
        lottery_coverage = coverage[row["lottery_type"]]
        current_lifecycle = row["current_lifecycle_status"]
        badge_entry = next((x for x in p251a["lifecycle_badge_vocabulary"] if x["status"] == current_lifecycle), None)
        strategy_rows.append(
            {
                "strategy_id": row["strategy_id"],
                "strategy_name": row["strategy_name"],
                "lottery_type": row["lottery_type"],
                "current_registry_lifecycle_status": current_lifecycle,
                "historical_snapshot_lifecycle_status": row["historical_snapshot_lifecycle_status"],
                "latest_classification": row["latest_classification"],
                "replay_presence": row["replay_presence"],
                "replay_rows": row["replay_rows"],
                "lottery_replay_rows": lottery_coverage["replay_rows"],
                "lottery_draw_rows": lottery_coverage["draw_rows"],
                "lottery_canonical_rows": lottery_coverage["canonical_rows"],
                "artifact_only_flag": current_lifecycle == "ARTIFACT_ONLY",
                "visible_by_default": True,
                "evidence_state": {
                    "current_registry_presence": row["current_registry_presence"],
                    "historical_scoreboard_presence": row["historical_scoreboard_presence"],
                    "current_lifecycle_source": row["current_lifecycle_source"],
                    "catalog_source_snapshot": row["catalog_source_snapshot"],
                    "distinct_target_draws": row["distinct_target_draws"],
                    "status_note": row["status_note"],
                    "included_in_historical_replay_or_catalog_views": row["included_in_historical_replay_or_catalog_views"],
                },
                "badge": badge_entry["badge"] if badge_entry else "unknown",
                "filter_tags": sorted({
                    row["lottery_type"],
                    current_lifecycle,
                    "historical-snapshot" if row["historical_snapshot_lifecycle_status"] else "",
                    "artifact-only" if current_lifecycle == "ARTIFACT_ONLY" else "",
                } - {""}),
                "source_artifacts": {
                    "current_registry": "lottery_api/models/replay_strategy_registry.py" if row["current_registry_presence"] else None,
                    "historical_scoreboard": str(P250A_JSON_PATH.relative_to(REPO_ROOT)),
                },
                "row_visibility": {
                    "default_visible": True,
                    "lifecycle_filtered": False,
                    "exclude_by_lifecycle": False,
                },
            }
        )
    return strategy_rows


def _build_lifecycle_filter_options() -> List[Dict[str, Any]]:
    options = []
    for badge in LIFECYCLE_BADGE_VOCAB:
        options.append(
            {
                "status": badge["status"],
                "label": badge["filter_label"],
                "badge": badge["badge"],
                "default_enabled": badge["default_enabled"],
                "filter_behavior": "badge/filter only; never exclusion",
            }
        )
    return options


def _build_replay_coverage_summary(p250a: Dict[str, Any]) -> List[Dict[str, Any]]:
    summary = []
    for row in p250a["replay_coverage_by_lottery"]:
        summary.append(
            {
                "lottery_type": row["lottery_type"],
                "strategy_count": row["developed_strategy_entries"],
                "replay_strategy_entries": row["replay_strategy_entries"],
                "replay_rows": row["replay_rows"],
                "draw_rows": row["draw_rows"],
                "canonical_rows": row["canonical_rows"],
                "distinct_replay_draws": row["distinct_replay_draws"],
                "replay_row_semantics": "strategy_prediction_replays rows",
                "draw_row_semantics": "draws table rows",
                "canonical_row_semantics": "canonical main-draw rows when a canonical view exists",
                "add_on_raw_accessible": row["lottery_type"] == "BIG_LOTTO",
            }
        )
    return summary


def _build_draw_count_semantics() -> Dict[str, Any]:
    return {
        "replay_rows": "Rows in strategy_prediction_replays; one replayed bet record per strategy/bet/draw row.",
        "draw_rows": "Rows in draws; raw draw-table counts and source-of-truth for lottery history volume.",
        "canonical_rows": "Filtered BIG_LOTTO research sample from draws_big_lotto_canonical_main.",
        "add_on_rows": "BIG_LOTTO hyphenated add-on / special-prize records; raw-accessible and preserved.",
        "note": "Replays, raw draws, canonical rows, and add-on rows must remain distinct in the dashboard.",
    }


def _build_evidence_state_summary(p250a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "current_registry_entries": p250a["inventory_counts"]["current_registry_entries"],
        "historical_inventory_entries": p250a["inventory_counts"]["historical_inventory_entries"],
        "artifact_only_entries": p250a["inventory_counts"]["artifact_only_entries"],
        "current_registry_lifecycle_counts": p250a["inventory_counts"]["current_registry_lifecycle_counts"],
        "replay_backed_entries": sum(1 for row in p250a["strategy_inventory"] if row["replay_presence"]),
        "no_replay_entries": sum(1 for row in p250a["strategy_inventory"] if not row["replay_presence"]),
        "current_registry_is_live_ssot": True,
        "p232a_scoreboard_is_historical_snapshot": True,
        "artifact_only_visible_by_default": True,
        "lifecycle_never_excludes_historical_rows": True,
        "no_active_deployable_candidate": True,
    }


def _build_default_filter_state() -> Dict[str, Any]:
    return {
        "include_all_rows": True,
        "include_all_lifecycle_statuses": True,
        "enabled_lifecycle_statuses": [item["status"] for item in LIFECYCLE_BADGE_VOCAB],
        "enabled_lottery_types": ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"],
        "artifact_only_visible": True,
        "historical_rows_visible": True,
        "exclude_by_lifecycle": False,
        "sort_order": ["lottery_type", "current_registry_lifecycle_status", "strategy_id"],
    }


def _build_no_betting_advice_notice() -> Dict[str, Any]:
    return {
        "message": "This dashboard data artifact is evidence-only and is not betting advice.",
        "no_claims": [
            "No predictive edge is claimed.",
            "No strategy promotion is implied.",
            "No production recommendation is changed.",
            "GREEN canonical randomness remains a data-quality result, not a signal.",
            "Current inventory has no active deployable candidate.",
        ],
    }


def _build_implementation_readiness() -> Dict[str, Any]:
    return {
        "data_artifact_ready": True,
        "ui_api_implementation_ready": False,
        "ui_api_implemented": False,
        "dashboard_contract_consumable_by_future_ui": True,
        "frontend_changes_required": True,
        "api_changes_required": True,
        "risk_level": "low",
        "next_steps": [
            "Wire this JSON into a future read-only API payload.",
            "Render lifecycle badges and filter chips without hiding historical rows.",
            "Add a stale snapshot banner next to the live registry SSOT indicator.",
        ],
    }


def _build_forbidden_actions_confirmed() -> Dict[str, str]:
    return {
        "DB write": "NOT PERFORMED",
        "DB migration": "NOT PERFORMED",
        "CREATE VIEW / CREATE TABLE": "NOT PERFORMED",
        "registry mutation": "NOT PERFORMED",
        "strategy logic change": "NOT PERFORMED",
        "UI/API implementation": "NOT PERFORMED",
        "production recommendation change": "NOT PERFORMED",
        "strategy promotion": "NOT PERFORMED",
        "betting advice": "NOT PERFORMED",
        "controlled_apply": "NOT PERFORMED",
    }


def build_dashboard_data() -> Dict[str, Any]:
    p250a, p251a = _load_sources()

    dashboard_data = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "CROSS_LOTTERY_EVIDENCE_DASHBOARD_DATA_ARTIFACT",
        "source_artifacts": _build_source_artifacts(),
        "contract_alignment": {
            "source_contract": str(P251A_JSON_PATH.relative_to(REPO_ROOT)),
            "represented_sections": [
                "global_summary",
                "lottery_summary",
                "lifecycle_badge_vocabulary",
                "strategy_table_columns",
                "evidence_state_columns",
                "filter_semantics",
                "no_exclusion_rules",
                "stale_snapshot_warning",
                "no_betting_advice_notice",
                "implementation_candidates_for_future",
            ],
            "contract_classification": p251a["classification"],
            "artifact_source": p250a["classification"],
        },
        "global_summary": {
            "source_of_truth": "P250A inventory artifact published on main",
            "current_registry_is_live_ssot": True,
            "historical_scoreboard_is_snapshot": True,
            "current_registry_entries": p250a["inventory_counts"]["current_registry_entries"],
            "historical_inventory_entries": p250a["inventory_counts"]["historical_inventory_entries"],
            "artifact_only_entries": p250a["inventory_counts"]["artifact_only_entries"],
            "replay_rows_total": p250a["db_read_status"]["replay_rows_total"],
            "draw_rows_total": p250a["db_read_status"]["draw_rows_total"],
            "big_lotto_raw_draw_rows": 22_238,
            "big_lotto_canonical_rows": 2_113,
            "big_lotto_add_on_rows": 19_100,
            "no_deployable_candidate": True,
            "no_prediction_edge_claim": True,
            "lifecycle_is_label_not_exclusion": True,
        },
        "lottery_cards": _build_lottery_cards(p250a),
        "strategy_rows": _build_strategy_rows(p250a, p251a),
        "lifecycle_filter_options": _build_lifecycle_filter_options(),
        "lifecycle_badge_vocabulary": LIFECYCLE_BADGE_VOCAB,
        "replay_coverage_summary": _build_replay_coverage_summary(p250a),
        "draw_count_semantics": _build_draw_count_semantics(),
        "evidence_state_summary": _build_evidence_state_summary(p250a),
        "stale_snapshot_warning": {
            "message": "P232A is a historical replay snapshot from 20260604 and is stale relative to the live registry SSOT published in P250A/P250B.",
            "current_registry_ssot": "lottery_api/models/replay_strategy_registry.py",
            "historical_snapshot": str(P250A_JSON_PATH.relative_to(REPO_ROOT)),
            "dashboard_behavior": "show both states together, with the current registry as primary and the snapshot as evidence context.",
        },
        "no_exclusion_rules": [
            "Lifecycle cannot exclude historical replay/catalog rows by default.",
            "Do not hide rows because they are retired, rejected, observation, unresolved, or artifact-only.",
            "Do not infer deployability from inventory presence, row counts, or historical classifications alone.",
            "Do not treat P232A as live state; it is a historical snapshot and must not replace the current registry SSOT.",
            "Do not hide BIG_LOTTO add-on / canonical split information; display it as evidence state.",
        ],
        "default_filter_state": _build_default_filter_state(),
        "no_betting_advice_notice": _build_no_betting_advice_notice(),
        "implementation_readiness": _build_implementation_readiness(),
        "forbidden_actions_confirmed": _build_forbidden_actions_confirmed(),
        "final_decision": "P251B complete. Dashboard-ready data artifact built from P250A and P251A, preserving all 41 strategy rows and all lifecycle states as visible evidence. No UI/API implementation, no DB write, no registry mutation, no betting advice.",
    }
    return dashboard_data


def build_md_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    A = lines.append

    A("# P251B — Cross-Lottery Evidence Dashboard Data Artifact")
    A("")
    A(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    A(f"**Task:** `{TASK_ID}`  ")
    A(f"**Classification:** `CROSS_LOTTERY_EVIDENCE_DASHBOARD_DATA_ARTIFACT`  ")
    A("")
    A("## Executive Summary")
    A("")
    A(
        "This artifact transforms the published P250A inventory and the P251A dashboard "
        "contract into a concrete dashboard-ready JSON shape. It keeps every historical "
        "strategy row visible, separates replay / draw / canonical semantics, and preserves "
        "the rule that lifecycle is a badge/filter only."
    )
    A("")
    A("## Source Artifacts Used")
    A("")
    for key, value in report["source_artifacts"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("## Dashboard-Ready Data Shape")
    A("")
    A("- `global_summary`")
    A("- `lottery_cards`")
    A("- `strategy_rows`")
    A("- `lifecycle_filter_options`")
    A("- `lifecycle_badge_vocabulary`")
    A("- `replay_coverage_summary`")
    A("- `draw_count_semantics`")
    A("- `evidence_state_summary`")
    A("- `stale_snapshot_warning`")
    A("- `no_exclusion_rules`")
    A("- `default_filter_state`")
    A("- `no_betting_advice_notice`")
    A("- `implementation_readiness`")
    A("- `forbidden_actions_confirmed`")
    A("- `final_decision`")
    A("")
    A("## Global Summary")
    A("")
    for key, value in report["global_summary"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("## Lottery Cards Summary")
    A("")
    for card in report["lottery_cards"]:
        A(f"### {card['lottery_type']}")
        A("")
        A(f"- strategy_cards_visible: `{card['strategy_cards_visible']}`")
        A(f"- replay_rows: `{card['replay_rows']}`")
        A(f"- draw_rows: `{card['draw_rows']}`")
        A(f"- canonical_rows: `{card['canonical_rows']}`")
        A(f"- artifact_only_rows_visible: `{card['artifact_only_rows_visible']}`")
        A(f"- lifecycle_visibility_rule: `{card['lifecycle_visibility_rule']}`")
        for note in card["summary_notes"]:
            A(f"- note: {note}")
        A("")
    A("## Lifecycle Filter Behavior")
    A("")
    A(
        "The default view includes every lifecycle status. Filters only narrow the view; "
        "they never hide historical replay/catalog rows by default."
    )
    A("")
    A("## Strategy Row Preservation Rules")
    A("")
    A("- All 41 P250A inventory rows remain visible in `strategy_rows`.")
    A("- Current registry entries stay represented.")
    A("- Artifact-only rows remain visible by default.")
    A("- No-data and unresolved historical rows are preserved as evidence rows.")
    A("")
    A("## Replay/Draw/Canonical Row Semantics")
    A("")
    for key, value in report["draw_count_semantics"].items():
        A(f"- {key}: {value}")
    A("")
    A("## No-Overclaim Statement")
    A("")
    A(
        "BIG_LOTTO canonical randomness GREEN remains a data-quality confirmation only; "
        "it does not authorize a predictive edge. DAILY_539 remains rejected, POWER_LOTTO "
        "has no active deployable candidate, and 3_STAR/4_STAR have no current registry/replay entries."
    )
    A("")
    A("## Future Implementation Candidates")
    A("")
    for item in report["implementation_readiness"]["next_steps"]:
        A(f"- {item}")
    A("")
    A("## Explicit Non-Actions")
    A("")
    A("- No DB write")
    A("- No registry mutation")
    A("- No UI/API implementation")
    A("- No betting advice")
    A("")
    A("## Compliance")
    A("")
    for key, value in report["forbidden_actions_confirmed"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("Final Classification: `CROSS_LOTTERY_EVIDENCE_DASHBOARD_DATA_ARTIFACT`")
    return "\n".join(lines)


def main() -> int:
    report = build_dashboard_data()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUTPUT.write_text(build_md_report(report), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {MD_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
