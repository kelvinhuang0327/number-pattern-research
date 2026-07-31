"""Tests for P251B cross-lottery evidence dashboard data artifact builder."""

from __future__ import annotations

import json
from pathlib import Path

from analysis import p251b_cross_lottery_evidence_dashboard_data_builder as p251b


REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = REPO_ROOT / "outputs" / "research" / "p251b_cross_lottery_evidence_dashboard_data_20260606.json"
MD_PATH = REPO_ROOT / "outputs" / "research" / "p251b_cross_lottery_evidence_dashboard_data_20260606.md"
P250A_JSON_PATH = REPO_ROOT / "outputs" / "research" / "p250a_cross_lottery_strategy_replay_inventory_20260606.json"
P251A_JSON_PATH = REPO_ROOT / "outputs" / "research" / "p251a_cross_lottery_evidence_dashboard_dryrun_plan_20260606.json"


def test_p250a_and_p251a_artifacts_readable():
    p250a = json.loads(P250A_JSON_PATH.read_text(encoding="utf-8"))
    p251a = json.loads(P251A_JSON_PATH.read_text(encoding="utf-8"))

    assert p250a["inventory_counts"]["current_registry_entries"] == 38
    assert p250a["inventory_counts"]["historical_inventory_entries"] == 41
    assert p250a["inventory_counts"]["artifact_only_entries"] == 3
    assert p251a["classification"] == "CROSS_LOTTERY_EVIDENCE_DASHBOARD_DRYRUN_PLAN"


def test_dashboard_data_shape_and_counts():
    report = p251b.build_dashboard_data()

    assert report["schema_version"] == "1.0"
    assert report["task_id"] == "P251B"
    assert report["classification"] == "CROSS_LOTTERY_EVIDENCE_DASHBOARD_DATA_ARTIFACT"

    assert report["global_summary"]["current_registry_entries"] == 38
    assert report["global_summary"]["historical_inventory_entries"] == 41
    assert report["global_summary"]["artifact_only_entries"] == 3
    assert len(report["strategy_rows"]) >= 41
    assert sum(1 for row in report["strategy_rows"] if row["artifact_only_flag"]) == 3
    assert report["default_filter_state"]["include_all_lifecycle_statuses"] is True
    assert report["default_filter_state"]["exclude_by_lifecycle"] is False
    assert "ARTIFACT_ONLY" in report["default_filter_state"]["enabled_lifecycle_statuses"]


def test_lifecycle_and_semantics_preserved():
    report = p251b.build_dashboard_data()

    assert report["evidence_state_summary"]["artifact_only_entries"] == 3
    assert report["evidence_state_summary"]["lifecycle_never_excludes_historical_rows"] is True
    assert "lifecycle cannot exclude historical replay/catalog rows by default" in " ".join(report["no_exclusion_rules"]).lower()

    big_lotto = next(card for card in report["lottery_cards"] if card["lottery_type"] == "BIG_LOTTO")
    assert big_lotto["replay_rows"] == 24_140
    assert big_lotto["draw_rows"] == 22_238
    assert big_lotto["canonical_rows"] == 2_113
    assert report["draw_count_semantics"]["add_on_rows"].startswith("BIG_LOTTO hyphenated")


def test_no_overclaim_and_forbidden_actions():
    report = p251b.build_dashboard_data()

    assert "not betting advice" in report["no_betting_advice_notice"]["message"].lower()
    assert report["implementation_readiness"]["ui_api_implemented"] is False
    assert report["implementation_readiness"]["ui_api_implementation_ready"] is False
    assert report["forbidden_actions_confirmed"]["DB write"] == "NOT PERFORMED"
    assert report["forbidden_actions_confirmed"]["registry mutation"] == "NOT PERFORMED"
    assert report["forbidden_actions_confirmed"]["UI/API implementation"] == "NOT PERFORMED"


def test_write_and_parse():
    p251b.main()
    assert JSON_PATH.exists()
    assert MD_PATH.exists()

    report = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    md = MD_PATH.read_text(encoding="utf-8")

    assert report["final_decision"].startswith("P251B complete.")
    assert "No DB write" in md
    assert "No UI/API implementation" in md
    assert "No betting advice" in md
