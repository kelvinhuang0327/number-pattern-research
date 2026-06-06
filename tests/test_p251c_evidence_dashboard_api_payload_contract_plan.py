"""Tests for P251C evidence dashboard API payload contract plan."""

from __future__ import annotations

import json
from pathlib import Path

from analysis import p251c_evidence_dashboard_api_payload_contract_plan as p251c


REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = REPO_ROOT / "outputs" / "research" / "p251c_evidence_dashboard_api_payload_contract_plan_20260606.json"
MD_PATH = REPO_ROOT / "outputs" / "research" / "p251c_evidence_dashboard_api_payload_contract_plan_20260606.md"


def test_builder_loads_sources():
    report = p251c.build_contract_plan()

    assert report["source_artifact_classifications"]["p250a"] == "CROSS_LOTTERY_STRATEGY_REPLAY_INVENTORY"
    assert report["source_artifact_classifications"]["p251a"] == "CROSS_LOTTERY_EVIDENCE_DASHBOARD_DRYRUN_PLAN"
    assert report["source_artifact_classifications"]["p251b"] == "CROSS_LOTTERY_EVIDENCE_DASHBOARD_DATA_ARTIFACT"


def test_schema_and_endpoint_future_only():
    report = p251c.build_contract_plan()

    assert report["schema_version"] == "1.0"
    assert report["task_id"] == "P251C"
    assert report["classification"] == "EVIDENCE_DASHBOARD_API_PAYLOAD_CONTRACT_PLAN"
    assert report["proposed_endpoint"]["path"] == "/api/replay/evidence-dashboard"
    assert report["proposed_endpoint"]["future_only"] is True
    assert report["proposed_endpoint"]["status"] == "PROPOSED_FUTURE_ONLY"
    assert report["no_implementation_confirmed"]["route_implemented"] is False
    assert report["no_implementation_confirmed"]["ui_implemented"] is False


def test_response_schema_and_field_contract():
    report = p251c.build_contract_plan()

    required = report["response_schema"]["required_top_level_fields"]
    assert "global_summary" in required
    assert "lottery_cards" in required
    assert "strategy_rows" in required
    assert "lifecycle_filter_options" in required
    assert "no_exclusion_rules" in required
    assert "no_betting_advice_notice" in required

    assert "strategy_rows" in report["payload_field_contract"]
    assert "global_summary" in report["payload_field_contract"]
    assert "lottery_cards" in report["payload_field_contract"]


def test_strategy_row_and_big_lotto_semantics_preserved():
    report = p251c.build_contract_plan()

    assert report["strategy_row_schema"]["preserved_semantics"]["lifecycle_is_filter_only"] is True
    assert report["strategy_row_schema"]["preserved_semantics"]["default_visible"] is True
    assert report["validation_rules"][4].endswith("(41).")
    assert report["validation_rules"][5] == "Artifact-only rows must remain visible by default."

    dashboard_ref = report["dashboard_payload_reference"]
    assert dashboard_ref["p251b_strategy_rows"] == 41
    assert dashboard_ref["p251b_artifact_only_rows"] == 3
    assert dashboard_ref["p251b_default_filter_includes_all_statuses"] is True
    assert dashboard_ref["p251b_big_lotto_replay_rows"] == 24_140
    assert dashboard_ref["p251b_big_lotto_draw_rows"] == 22_238
    assert dashboard_ref["p251b_big_lotto_canonical_rows"] == 2_113

    assert "BIG_LOTTO" in report["filter_sort_pagination_contract"]["filters"]["lottery_type"]
    assert "public, max-age=300" in report["cache_and_staleness_policy"]["cache_control_proposal"]


def test_route_scan_conclusion_and_forbidden_actions():
    report = p251c.build_contract_plan()

    scan = report["route_convention_scan"]
    assert scan["app_mounted_replay_router"] is True
    assert scan["route_conflict_assessment"] == "no conflict with current routes; future-only endpoint can live under /api/replay/*"
    assert any("/api/replay/strategy-catalog" in item.get("route", "") for item in scan["candidate_routes"])
    assert any("/api/replay/freshness" in item.get("route", "") for item in scan["candidate_routes"])
    assert report["forbidden_actions_confirmed"]["DB write"] == "NOT PERFORMED"
    assert report["forbidden_actions_confirmed"]["registry mutation"] == "NOT PERFORMED"
    assert report["forbidden_actions_confirmed"]["strategy promotion"] == "NOT PERFORMED"
    assert report["forbidden_actions_confirmed"]["betting advice"] == "NOT PERFORMED"


def test_write_and_parse():
    p251c.main()
    assert JSON_PATH.exists()
    assert MD_PATH.exists()

    report = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    md = MD_PATH.read_text(encoding="utf-8")

    assert report["final_decision"].startswith("P251C complete.")
    assert "Existing Route Convention Scan" in md
    assert "Proposed Future Endpoint" in md
    assert "No betting advice" in md
