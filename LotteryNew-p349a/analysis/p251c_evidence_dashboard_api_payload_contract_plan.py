"""P251C — Evidence dashboard API payload contract plan.

This is a read-only planning artifact. It proposes a future-only API payload
contract for serving the P251B dashboard-ready data to a UI, but it does not
implement any API route, UI, DB write, registry mutation, or strategy logic.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


TASK_ID = "P251C"
SCHEMA_VERSION = "1.0"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
P250A_JSON_PATH = OUTPUT_DIR / "p250a_cross_lottery_strategy_replay_inventory_20260606.json"
P251A_JSON_PATH = OUTPUT_DIR / "p251a_cross_lottery_evidence_dashboard_dryrun_plan_20260606.json"
P251B_JSON_PATH = OUTPUT_DIR / "p251b_cross_lottery_evidence_dashboard_data_20260606.json"

JSON_OUTPUT = OUTPUT_DIR / f"p251c_evidence_dashboard_api_payload_contract_plan_{DATE_SLUG}.json"
MD_OUTPUT = OUTPUT_DIR / f"p251c_evidence_dashboard_api_payload_contract_plan_{DATE_SLUG}.md"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_sources() -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    return _load_json(P250A_JSON_PATH), _load_json(P251A_JSON_PATH), _load_json(P251B_JSON_PATH)


def _build_source_artifacts() -> Dict[str, str]:
    return {
        "p250a_inventory": str(P250A_JSON_PATH.relative_to(REPO_ROOT)),
        "p251a_contract": str(P251A_JSON_PATH.relative_to(REPO_ROOT)),
        "p251b_dashboard_data": str(P251B_JSON_PATH.relative_to(REPO_ROOT)),
        "current_state": "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md",
        "active_task": "00-Plan/roadmap/active_task.md",
    }


def _scan_route_conventions() -> Dict[str, Any]:
    app_path = REPO_ROOT / "lottery_api" / "app.py"
    replay_path = REPO_ROOT / "lottery_api" / "routes" / "replay.py"
    best_path = REPO_ROOT / "lottery_api" / "routes" / "best_strategy_overview.py"
    data_path = REPO_ROOT / "lottery_api" / "routes" / "data.py"

    app_text = app_path.read_text(encoding="utf-8")
    replay_text = replay_path.read_text(encoding="utf-8")
    best_text = best_path.read_text(encoding="utf-8")
    data_text = data_path.read_text(encoding="utf-8")

    candidate_routes = [
        {
            "source_file": "lottery_api/app.py",
            "route_namespace": "/api/replay/*",
            "status": "read-only audit namespace",
            "notes": "Replay router is mounted as a read-only audit family.",
        },
        {
            "source_file": "lottery_api/routes/replay.py",
            "route": "/api/replay/strategies",
            "method": "GET",
            "shape": "strategy catalog / visibility list",
            "notes": "List strategies with lifecycle filters; closest naming pattern for dashboard payloads.",
        },
        {
            "source_file": "lottery_api/routes/replay.py",
            "route": "/api/replay/history",
            "method": "GET",
            "shape": "paged audit history",
            "notes": "Supports page/page_size and lifecycle filters; proves existing query conventions.",
        },
        {
            "source_file": "lottery_api/routes/replay.py",
            "route": "/api/replay/freshness",
            "method": "GET",
            "shape": "freshness / coverage advisory",
            "notes": "Useful precedent for staleness and coverage banners in a read-only dashboard.",
        },
        {
            "source_file": "lottery_api/routes/replay.py",
            "route": "/api/replay/strategy-catalog",
            "method": "GET",
            "shape": "read-only strategy catalog",
            "notes": "Existing read-only catalog endpoint; strong convention match for future payloads.",
        },
        {
            "source_file": "lottery_api/routes/best_strategy_overview.py",
            "route": "/api/best-strategy-overview",
            "method": "GET",
            "shape": "artifact-backed ranking cards",
            "notes": "Shows the repo already uses artifact-backed read-only payload endpoints.",
        },
        {
            "source_file": "lottery_api/routes/best_strategy_overview.py",
            "route": "/api/best-strategy-overview/meta/available-artifacts",
            "method": "GET",
            "shape": "artifact discovery metadata",
            "notes": "Useful precedent for source_artifacts metadata without mutating state.",
        },
        {
            "source_file": "lottery_api/routes/data.py",
            "route": "/api/data/draws",
            "method": "GET",
            "shape": "paged query with filters",
            "notes": "General page/page_size pattern used elsewhere in the API.",
        },
    ]

    return {
        "app_mounted_replay_router": bool(re.search(r"include_router\(replay\.router", app_text)),
        "app_mounted_best_strategy_overview_router": bool(re.search(r"include_router\(best_strategy_overview\.router", app_text)),
        "existing_read_only_patterns": [
            "/api/replay/strategies",
            "/api/replay/history",
            "/api/replay/freshness",
            "/api/replay/strategy-catalog",
            "/api/best-strategy-overview",
            "/api/best-strategy-overview/meta/available-artifacts",
        ],
        "observed_conventions": [
            "Read-only GET endpoints are common in replay and best-strategy namespaces.",
            "Paged queries use page/page_size in multiple routes.",
            "Freshness / coverage and artifact-metadata endpoints already exist as read-only patterns.",
            "Replay router is the clearest namespace match for an evidence dashboard payload.",
        ],
        "route_conflict_assessment": "no conflict with current routes; future-only endpoint can live under /api/replay/*",
        "candidate_routes": candidate_routes,
        "raw_scan_notes": {
            "replay_file_contains_strategy_catalog": "/api/replay/strategy-catalog" in replay_text,
            "replay_file_contains_freshness": "/api/replay/freshness" in replay_text,
            "best_strategy_file_contains_available_artifacts": "/api/best-strategy-overview/meta/available-artifacts" in best_text,
            "data_file_contains_page_size": "page_size" in data_text,
        },
    }


def _build_proposed_endpoint() -> Dict[str, Any]:
    return {
        "path": "/api/replay/evidence-dashboard",
        "http_method": "GET",
        "future_only": True,
        "status": "PROPOSED_FUTURE_ONLY",
        "namespace": "/api/replay/*",
        "reasoning": "Matches the existing replay audit namespace and keeps the payload read-only and dashboard-focused.",
        "notes": [
            "No route implemented in P251C.",
            "No UI implemented in P251C.",
            "No DB write, registry mutation, or strategy promotion.",
        ],
    }


def _build_response_schema() -> Dict[str, Any]:
    required_top_level_fields = [
        "schema_version",
        "task_id",
        "classification",
        "generated_at",
        "source_artifacts",
        "proposed_endpoint",
        "http_method",
        "route_convention_scan",
        "response_schema",
        "payload_field_contract",
        "lottery_card_schema",
        "strategy_row_schema",
        "lifecycle_filter_schema",
        "evidence_state_schema",
        "filter_sort_pagination_contract",
        "cache_and_staleness_policy",
        "validation_rules",
        "implementation_steps_future_only",
        "no_implementation_confirmed",
        "forbidden_actions_confirmed",
        "final_decision",
        "global_summary",
        "lottery_cards",
        "strategy_rows",
        "lifecycle_filter_options",
        "lifecycle_badge_vocabulary",
        "replay_coverage_summary",
        "draw_count_semantics",
        "evidence_state_summary",
        "stale_snapshot_warning",
        "no_exclusion_rules",
        "default_filter_state",
        "no_betting_advice_notice",
        "implementation_readiness",
    ]
    return {
        "schema_kind": "future_read_only_api_payload",
        "required_top_level_fields": required_top_level_fields,
        "response_payload_shape": {
            "global_summary": "object",
            "lottery_cards": "array<object>",
            "strategy_rows": "array<object>",
            "lifecycle_filter_options": "array<object>",
            "lifecycle_badge_vocabulary": "array<object>",
            "replay_coverage_summary": "array<object>",
            "draw_count_semantics": "object",
            "evidence_state_summary": "object",
            "stale_snapshot_warning": "object",
            "no_exclusion_rules": "array<string>",
            "default_filter_state": "object",
            "no_betting_advice_notice": "object",
            "implementation_readiness": "object",
            "forbidden_actions_confirmed": "object",
            "final_decision": "string",
        },
        "response_contract_notes": [
            "The response should be shaped for dashboard consumption, not for prediction execution.",
            "The payload should retain every visible P251B strategy row and preserve lifecycle badges as filters only.",
            "Pagination is proposed for row-level browsing, but default output should remain complete enough for the dashboard to render the full visible set.",
        ],
    }


def _build_payload_field_contract() -> Dict[str, Any]:
    return {
        "global_summary": {
            "purpose": "Top-level evidence summary carried forward from P251B.",
            "must_include": [
                "current_registry_entries",
                "historical_inventory_entries",
                "artifact_only_entries",
                "replay_rows_total",
                "draw_rows_total",
                "big_lotto_raw_draw_rows",
                "big_lotto_canonical_rows",
                "big_lotto_add_on_rows",
                "no_deployable_candidate",
                "no_prediction_edge_claim",
                "lifecycle_is_label_not_exclusion",
            ],
        },
        "lottery_cards": {
            "purpose": "Per-lottery summary cards for BIG_LOTTO, DAILY_539, and POWER_LOTTO.",
            "must_include": [
                "lottery_type",
                "card_title",
                "strategy_cards_visible",
                "replay_strategy_entries",
                "replay_rows",
                "draw_rows",
                "canonical_rows",
                "artifact_only_rows_visible",
                "visible_by_default",
                "lifecycle_visibility_rule",
                "summary_notes",
            ],
        },
        "strategy_rows": {
            "purpose": "Full visible inventory rows from P251B, including artifact-only evidence rows.",
            "must_include": [
                "strategy_id",
                "strategy_name",
                "lottery_type",
                "current_registry_lifecycle_status",
                "historical_snapshot_lifecycle_status",
                "latest_classification",
                "replay_presence",
                "replay_rows",
                "lottery_replay_rows",
                "lottery_draw_rows",
                "lottery_canonical_rows",
                "artifact_only_flag",
                "visible_by_default",
                "evidence_state",
                "badge",
                "filter_tags",
                "source_artifacts",
                "row_visibility",
            ],
        },
        "lifecycle_filter_options": {
            "purpose": "Filter chips / badges that narrow the view without excluding historical rows by default.",
            "default_behavior": "include all lifecycle statuses",
            "statuses": [
                "ONLINE",
                "REJECTED",
                "RETIRED",
                "OBSERVATION",
                "ARTIFACT_ONLY",
                "LIFECYCLE_UNRESOLVED",
            ],
        },
        "evidence_state": {
            "purpose": "Explicitly state live SSOT versus historical snapshot semantics.",
            "must_include": [
                "current_registry_is_live_ssot",
                "historical_scoreboard_is_snapshot",
                "artifact_only_visible_by_default",
                "lifecycle_never_excludes_historical_rows",
                "no_active_deployable_candidate",
                "no_prediction_edge_claim",
            ],
        },
        "stale_snapshot_warning": {
            "purpose": "Warn that P232A/P251A historical evidence is stale relative to live registry SSOT.",
            "must_include": [
                "message",
                "current_registry_ssot",
                "historical_snapshot",
                "dashboard_behavior",
            ],
        },
        "no_betting_advice_notice": {
            "purpose": "Prevent prediction or betting interpretation of the payload.",
            "must_include": [
                "message",
                "no_claims",
            ],
        },
    }


def _build_lottery_card_schema() -> Dict[str, Any]:
    return {
        "required_fields": [
            "lottery_type",
            "card_title",
            "strategy_cards_visible",
            "replay_strategy_entries",
            "replay_rows",
            "draw_rows",
            "canonical_rows",
            "artifact_only_rows_visible",
            "visible_by_default",
            "lifecycle_visibility_rule",
            "summary_notes",
        ],
        "visibility_rules": [
            "Cards are summary views only.",
            "Artifact-only rows must remain visible when present.",
            "Lifecycle labels may filter the card but must not hide historical evidence by default.",
        ],
    }


def _build_strategy_row_schema() -> Dict[str, Any]:
    return {
        "required_fields": [
            "strategy_id",
            "strategy_name",
            "lottery_type",
            "current_registry_lifecycle_status",
            "historical_snapshot_lifecycle_status",
            "latest_classification",
            "replay_presence",
            "replay_rows",
            "lottery_replay_rows",
            "lottery_draw_rows",
            "lottery_canonical_rows",
            "artifact_only_flag",
            "visible_by_default",
            "evidence_state",
            "badge",
            "filter_tags",
            "source_artifacts",
            "row_visibility",
        ],
        "preserved_semantics": {
            "default_visible": True,
            "exclude_by_lifecycle": False,
            "lifecycle_is_filter_only": True,
            "artifact_only_rows_visible": True,
            "historical_rows_not_hidden_by_default": True,
        },
        "row_visibility_contract": {
            "default_visible": True,
            "lifecycle_filtered": False,
            "exclude_by_lifecycle": False,
        },
    }


def _build_lifecycle_filter_schema() -> Dict[str, Any]:
    return {
        "default_includes_all_statuses": True,
        "allowed_statuses": [
            "ONLINE",
            "REJECTED",
            "RETIRED",
            "OBSERVATION",
            "ARTIFACT_ONLY",
            "LIFECYCLE_UNRESOLVED",
        ],
        "filter_semantics": "badge/filter only; never exclusion",
        "default_filter_state": {
            "include_all_rows": True,
            "include_all_lifecycle_statuses": True,
            "exclude_by_lifecycle": False,
        },
        "validation_checks": [
            "Every lifecycle badge must remain visible in the default dashboard view.",
            "Historical rejected/retired/observation/artifact-only rows must not disappear by default.",
        ],
    }


def _build_evidence_state_schema() -> Dict[str, Any]:
    return {
        "required_fields": [
            "current_registry_is_live_ssot",
            "historical_scoreboard_is_snapshot",
            "artifact_only_visible_by_default",
            "lifecycle_never_excludes_historical_rows",
            "no_active_deployable_candidate",
            "no_prediction_edge_claim",
        ],
        "truth_notes": [
            "Current registry is the live source of truth.",
            "P232A / historical scoreboard remains evidence only.",
            "BIG_LOTTO GREEN is a data-quality confirmation, not a predictive edge claim.",
            "DAILY_539 remains rejected and POWER_LOTTO has no active deployable candidate.",
        ],
    }


def _build_filter_sort_pagination_contract() -> Dict[str, Any]:
    return {
        "filters": {
            "lottery_type": "optional string or multi-select (BIG_LOTTO, DAILY_539, POWER_LOTTO)",
            "lifecycle_status": "optional multi-select; default includes all statuses",
            "artifact_only": "optional tri-state; default includes visible artifact-only rows",
            "visible_only": "optional bool; default true for dashboard render",
        },
        "sorting": {
            "default_sort": ["lottery_type", "current_registry_lifecycle_status", "strategy_id"],
            "allowed_sort_keys": [
                "lottery_type",
                "current_registry_lifecycle_status",
                "historical_snapshot_lifecycle_status",
                "strategy_id",
                "strategy_name",
                "replay_rows",
                "draw_rows",
                "canonical_rows",
            ],
            "allowed_sort_orders": ["asc", "desc"],
        },
        "pagination": {
            "supports_pagination": True,
            "default_page": 1,
            "default_page_size": 50,
            "max_page_size": 200,
            "proposal_note": "Pagination should be optional because the dashboard defaults to visible all-row evidence rendering.",
        },
        "filtering_notes": [
            "Filtering narrows the view; it does not change lifecycle truth or hide evidence by default.",
            "No filter should imply deployability or betting advice.",
        ],
    }


def _build_cache_and_staleness_policy() -> Dict[str, Any]:
    return {
        "cacheability": "read-only payload may be cached short-term",
        "cache_control_proposal": "public, max-age=300, stale-while-revalidate=3600",
        "etag_strategy": "ETag should be derived from source artifact hashes and the merged dashboard artifact revision.",
        "staleness_banner_required": True,
        "staleness_banner_note": "Always show a stale snapshot warning when the payload is rendered from a historical artifact.",
        "refresh_cadence_note": "Refresh when a new P250A/P251A/P251B-style artifact is merged or the live registry SSOT changes.",
    }


def _build_validation_rules(p251b: Dict[str, Any]) -> List[str]:
    return [
        "JSON must parse successfully.",
        "classification must equal EVIDENCE_DASHBOARD_API_PAYLOAD_CONTRACT_PLAN.",
        "proposed_endpoint must be future-only and remain unimplemented in P251C.",
        "response_schema must include global_summary, lottery_cards, strategy_rows, lifecycle_filter_options, no_exclusion_rules, and no_betting_advice_notice.",
        f"strategy_rows validation must require at least {len(p251b['strategy_rows'])} visible rows (41).",
        "Artifact-only rows must remain visible by default.",
        "Default lifecycle filter must include all statuses and must not exclude historical rows.",
        "BIG_LOTTO replay/draw/canonical/add-on semantics must remain separated.",
        "No DB write, registry mutation, strategy promotion, betting advice, or UI/API implementation may be claimed by the contract.",
    ]


def _build_implementation_steps_future_only() -> List[str]:
    return [
        "Define a FastAPI response model matching this contract in a future task.",
        "Add a future read-only endpoint under /api/replay/* that serializes the dashboard payload.",
        "Add route-level tests that enforce lifecycle visibility and no-exclusion defaults.",
        "Wire a UI consumer only after the API payload exists and remains read-only.",
        "Keep DB, registry, and strategy logic unchanged until a separate authorization is issued.",
    ]


def build_contract_plan() -> Dict[str, Any]:
    p250a, p251a, p251b = _load_sources()

    route_convention_scan = _scan_route_conventions()
    proposed_endpoint = _build_proposed_endpoint()

    contract = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "EVIDENCE_DASHBOARD_API_PAYLOAD_CONTRACT_PLAN",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_artifacts": _build_source_artifacts(),
        "route_convention_scan": route_convention_scan,
        "proposed_endpoint": proposed_endpoint,
        "http_method": proposed_endpoint["http_method"],
        "response_schema": _build_response_schema(),
        "payload_field_contract": _build_payload_field_contract(),
        "lottery_card_schema": _build_lottery_card_schema(),
        "strategy_row_schema": _build_strategy_row_schema(),
        "lifecycle_filter_schema": _build_lifecycle_filter_schema(),
        "evidence_state_schema": _build_evidence_state_schema(),
        "filter_sort_pagination_contract": _build_filter_sort_pagination_contract(),
        "cache_and_staleness_policy": _build_cache_and_staleness_policy(),
        "validation_rules": _build_validation_rules(p251b),
        "implementation_steps_future_only": _build_implementation_steps_future_only(),
        "no_implementation_confirmed": {
            "route_implemented": False,
            "ui_implemented": False,
            "db_write": False,
            "registry_mutation": False,
            "strategy_promotion": False,
            "production_recommendation_change": False,
            "betting_advice": False,
        },
        "forbidden_actions_confirmed": {
            "DB write": "NOT PERFORMED",
            "DB migration": "NOT PERFORMED",
            "CREATE VIEW / CREATE TABLE": "NOT PERFORMED",
            "registry mutation": "NOT PERFORMED",
            "strategy logic change": "NOT PERFORMED",
            "strategy promotion": "NOT PERFORMED",
            "UI/API implementation": "NOT PERFORMED",
            "production recommendation change": "NOT PERFORMED",
            "betting advice": "NOT PERFORMED",
            "controlled_apply": "NOT PERFORMED",
        },
        "final_decision": (
            "P251C complete. Future-only API payload contract plan produced for the "
            "evidence dashboard, anchored to the existing /api/replay/* read-only "
            "namespace. No route implemented, no UI implemented, no DB write, no "
            "registry mutation, no strategy promotion, and no betting advice."
        ),
        "dashboard_payload_reference": {
            "p251b_strategy_rows": len(p251b["strategy_rows"]),
            "p251b_artifact_only_rows": sum(1 for row in p251b["strategy_rows"] if row.get("artifact_only_flag")),
            "p251b_default_filter_includes_all_statuses": p251b["default_filter_state"]["include_all_lifecycle_statuses"],
            "p251b_big_lotto_replay_rows": next(card for card in p251b["lottery_cards"] if card["lottery_type"] == "BIG_LOTTO")["replay_rows"],
            "p251b_big_lotto_draw_rows": next(card for card in p251b["lottery_cards"] if card["lottery_type"] == "BIG_LOTTO")["draw_rows"],
            "p251b_big_lotto_canonical_rows": next(card for card in p251b["lottery_cards"] if card["lottery_type"] == "BIG_LOTTO")["canonical_rows"],
        },
        "source_artifact_classifications": {
            "p250a": p250a["classification"],
            "p251a": p251a["classification"],
            "p251b": p251b["classification"],
        },
    }
    return contract


def build_md_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    A = lines.append

    A("# P251C — Evidence Dashboard API Payload Contract Plan")
    A("")
    A(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    A(f"**Task:** `{TASK_ID}`  ")
    A(f"**Classification:** `EVIDENCE_DASHBOARD_API_PAYLOAD_CONTRACT_PLAN`  ")
    A("")
    A("## Executive Summary")
    A("")
    A(
        "This artifact defines the future-only read-only API payload contract that "
        "could serve the P251B evidence dashboard data to a UI later. It intentionally "
        "does not implement the route, UI, DB writes, registry changes, or strategy changes."
    )
    A("")
    A("## Source Artifacts")
    A("")
    for key, value in report["source_artifacts"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("## Existing Route Convention Scan")
    A("")
    for item in report["route_convention_scan"]["candidate_routes"]:
        route = item.get("route") or item.get("route_namespace")
        method = item.get("method") or "n/a"
        A(f"- {method} {route} from `{item['source_file']}`")
        A(f"  - {item['shape'] if 'shape' in item else item['status']}")
        A(f"  - {item['notes']}")
    A("")
    A("## Proposed Future Endpoint")
    A("")
    A(f"- Path: `{report['proposed_endpoint']['path']}`")
    A(f"- Method: `{report['http_method']}`")
    A(f"- Future only: `{report['proposed_endpoint']['future_only']}`")
    A(f"- Namespace: `{report['proposed_endpoint']['namespace']}`")
    A(f"- Reasoning: {report['proposed_endpoint']['reasoning']}")
    A("")
    A("## Response Schema")
    A("")
    for field in report["response_schema"]["required_top_level_fields"]:
        A(f"- {field}")
    A("")
    A("## Field Contract")
    A("")
    for field_name, details in report["payload_field_contract"].items():
        A(f"### {field_name}")
        A("")
        A(f"- purpose: {details['purpose']}")
        if "must_include" in details:
            for item in details["must_include"]:
                A(f"- must_include: {item}")
        if "default_behavior" in details:
            A(f"- default_behavior: {details['default_behavior']}")
        if "statuses" in details:
            A(f"- statuses: {', '.join(details['statuses'])}")
        A("")
    A("## Filter/Sort/Pagination Behavior")
    A("")
    for key, value in report["filter_sort_pagination_contract"].items():
        A(f"- {key}: {value}")
    A("")
    A("## Validation Rules")
    A("")
    for rule in report["validation_rules"]:
        A(f"- {rule}")
    A("")
    A("## No-Overclaim / No-Betting Notice")
    A("")
    A("- No API route is implemented in P251C.")
    A("- No UI is implemented in P251C.")
    A("- No DB write, no registry mutation, no strategy promotion.")
    A("- No betting advice.")
    A("")
    A("## Future Implementation Steps")
    A("")
    for step in report["implementation_steps_future_only"]:
        A(f"- {step}")
    A("")
    A("## Explicit Non-Actions")
    A("")
    for key, value in report["forbidden_actions_confirmed"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("Final Classification: `EVIDENCE_DASHBOARD_API_PAYLOAD_CONTRACT_PLAN`")
    return "\n".join(lines)


def main() -> int:
    report = build_contract_plan()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUTPUT.write_text(build_md_report(report), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {MD_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
