"""Tests for P251A cross-lottery evidence dashboard dry-run plan."""

from __future__ import annotations

import json
from pathlib import Path

from analysis import p251a_cross_lottery_evidence_dashboard_dryrun_plan as p251a


REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = REPO_ROOT / "outputs" / "research" / "p251a_cross_lottery_evidence_dashboard_dryrun_plan_20260606.json"
MD_PATH = REPO_ROOT / "outputs" / "research" / "p251a_cross_lottery_evidence_dashboard_dryrun_plan_20260606.md"
P250A_JSON_PATH = REPO_ROOT / "outputs" / "research" / "p250a_cross_lottery_strategy_replay_inventory_20260606.json"


def test_p250a_artifact_readable():
    assert P250A_JSON_PATH.exists(), f"Missing P250A artifact: {P250A_JSON_PATH}"
    p250a = json.loads(P250A_JSON_PATH.read_text(encoding="utf-8"))
    assert p250a["inventory_counts"]["current_registry_entries"] == 38
    assert p250a["inventory_counts"]["historical_inventory_entries"] == 41
    assert p250a["inventory_counts"]["artifact_only_entries"] == 3


def test_contract_shape_and_summary():
    report = p251a.build_dashboard_contract()

    assert report["schema_version"] == "1.0"
    assert report["task_id"] == "P251A"
    assert report["classification"] == "CROSS_LOTTERY_EVIDENCE_DASHBOARD_DRYRUN_PLAN"

    assert report["global_summary"]["current_registry_entries"] == 38
    assert report["global_summary"]["inventory_entries"] == 41
    assert report["global_summary"]["artifact_only_entries"] == 3
    assert report["global_summary"]["no_deployable_candidate"] is True
    assert report["global_summary"]["lifecycle_is_label_not_exclusion"] is True

    assert any(section["lottery_type"] == "BIG_LOTTO" for section in report["lottery_summary"])
    assert any(section["lottery_type"] == "DAILY_539" for section in report["lottery_summary"])
    assert any(section["lottery_type"] == "POWER_LOTTO" for section in report["lottery_summary"])


def test_filters_and_no_exclusion_rules():
    report = p251a.build_dashboard_contract()

    assert "include all rows/cards by default" in report["filter_semantics"]["default_behavior"]
    assert "badge/filter only" in report["filter_semantics"]["lifecycle_filter"]
    assert len(report["no_exclusion_rules"]) >= 4
    assert "artifact-only rows visible by default" in report["filter_semantics"]["artifact_only_filter"]


def test_columns_and_warnings():
    report = p251a.build_dashboard_contract()

    for field in [
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
    ]:
        assert field in report

    assert "strategy_id" in report["strategy_table_columns"]
    assert "current_registry_lifecycle_status" in report["strategy_table_columns"]
    assert "historical_snapshot_lifecycle_status" in report["evidence_state_columns"]
    assert "P232A is a historical replay snapshot" in report["stale_snapshot_warning"]["message"]
    assert "No predictive edge is claimed." in report["no_betting_advice_notice"]["no_claims"]


def test_contract_write_and_md():
    p251a.main()
    assert JSON_PATH.exists()
    assert MD_PATH.exists()

    report = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    md = MD_PATH.read_text(encoding="utf-8")
    assert report["classification"] == "CROSS_LOTTERY_EVIDENCE_DASHBOARD_DRYRUN_PLAN"
    assert "global_summary" in md
    assert "no_betting_advice_notice" in md
    assert "implementation_candidates_for_future" in md
