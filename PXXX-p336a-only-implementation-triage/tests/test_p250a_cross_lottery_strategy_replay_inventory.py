"""Tests for P250A cross-lottery strategy replay inventory."""

from __future__ import annotations

import json
from pathlib import Path

from analysis import p250a_cross_lottery_strategy_replay_inventory as p250a


REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = REPO_ROOT / "outputs" / "research" / "p250a_cross_lottery_strategy_replay_inventory_20260606.json"
MD_PATH = REPO_ROOT / "outputs" / "research" / "p250a_cross_lottery_strategy_replay_inventory_20260606.md"


def test_report_shapes_and_counts():
    report = p250a.build_report()

    assert report["schema_version"] == "1.0"
    assert report["task_id"] == "P250A"
    assert "CROSS_LOTTERY" in report["classification"]
    assert report["phase0_expected_state"]["canonical_db_is_ssot"] is True

    assert report["inventory_counts"]["current_registry_entries"] == 38
    assert report["inventory_counts"]["historical_inventory_entries"] == 41
    assert report["inventory_counts"]["artifact_only_entries"] == 3

    assert report["db_read_status"]["integrity_check"] == "ok"
    assert report["db_read_status"]["replay_rows_total"] == 94_924
    assert report["db_read_status"]["draw_rows_total"] == 64_361
    assert report["db_read_status"]["canonical_big_lotto_rows"] == 2_113

    assert len(report["tables_found"]) >= 2
    assert any(item["name"] == "draws" for item in report["tables_found"])
    assert any(item["name"] == "strategy_prediction_replays" for item in report["tables_found"])
    assert any(item["name"] == "draws_big_lotto_canonical_main" for item in report["tables_found"])


def test_inventory_contains_all_current_entries_and_artifact_only_rows():
    report = p250a.build_report()
    inventory = report["strategy_inventory"]

    assert len(inventory) == 41

    artifact_only = [item for item in inventory if item["current_lifecycle_status"] == "ARTIFACT_ONLY"]
    assert len(artifact_only) == 3
    assert {item["strategy_id"] for item in artifact_only} == {
        "pp3_freqort_4bet",
        "midfreq_fourier_mk_3bet",
        "midfreq_fourier_2bet",
    }

    current_registry = [item for item in inventory if item["current_registry_presence"]]
    assert len(current_registry) == 38
    assert all(item["current_lifecycle_status"] != "LIFECYCLE_UNRESOLVED" for item in current_registry)


def test_replay_coverage_by_lottery():
    report = p250a.build_report()
    coverage = {item["lottery_type"]: item for item in report["replay_coverage_by_lottery"]}

    assert coverage["BIG_LOTTO"]["developed_strategy_entries"] == 13
    assert coverage["BIG_LOTTO"]["replay_strategy_entries"] == 11
    assert coverage["BIG_LOTTO"]["replay_rows"] == 24_140
    assert coverage["BIG_LOTTO"]["draw_rows"] == 22_238
    assert coverage["BIG_LOTTO"]["canonical_rows"] == 2_113
    assert coverage["BIG_LOTTO"]["distinct_replay_draws"] == 1_552

    assert coverage["DAILY_539"]["developed_strategy_entries"] == 16
    assert coverage["DAILY_539"]["replay_strategy_entries"] == 15
    assert coverage["DAILY_539"]["replay_rows"] == 34_680
    assert coverage["DAILY_539"]["draw_rows"] == 5_879
    assert coverage["DAILY_539"]["distinct_replay_draws"] == 1_550

    assert coverage["POWER_LOTTO"]["developed_strategy_entries"] == 12
    assert coverage["POWER_LOTTO"]["replay_strategy_entries"] == 10
    assert coverage["POWER_LOTTO"]["replay_rows"] == 36_104
    assert coverage["POWER_LOTTO"]["draw_rows"] == 1_916
    assert coverage["POWER_LOTTO"]["distinct_replay_draws"] == 1_551


def test_phase0_and_research_state():
    report = p250a.build_report()

    phase0 = report["phase0_expected_state"]
    assert phase0["canonical_branch"] == "main"
    assert phase0["head_matches_origin_main"] is True
    assert phase0["active_task_status"] == "WAITING_FOR_USER_AUTHORIZATION"
    assert "claude-code-showcase.worktrees/" in phase0["tolerated_dirty_items"]
    assert phase0["canonical_db_path"] == "lottery_api/data/lottery_v2.db"

    research = report["research_state"]
    assert research["big_lotto"]["status"].startswith("GREEN")
    assert research["daily_539"]["status"] == "REJECTED_BY_BACKWARD_OOS"
    assert research["power_lotto"]["status"] == "NULL_OR_BASELINE_LIKE"
    assert "UNDERPOWERED" in research["star_3_4"]["status"]


def test_outputs_write_and_parse():
    p250a.main()
    assert JSON_PATH.exists()
    assert MD_PATH.exists()

    report = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert report["task_id"] == "P250A"
    assert len(report["strategy_inventory"]) == 41
    assert "P250A_CROSS_LOTTERY_STRATEGY_REPLAY_INVENTORY_COMPLETE" in MD_PATH.read_text(encoding="utf-8")
