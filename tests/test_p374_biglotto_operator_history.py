import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_operator_history as history


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P374 operator history")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = history.run_operator_history()
        second = history.run_operator_history()
    finally:
        patcher.undo()
    return first, second


def test_required_p371_p372_p373_modules_and_artifacts_exist():
    paths = history.verify_required_evidence()
    assert len(paths) == len(history.REQUIRED_SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)


def test_health_snapshot_json_schema(double_run):
    first, _ = double_run
    snapshot = first.health_snapshot
    assert snapshot["task"] == history.TASK
    assert snapshot["source_baseline"]["required_origin_main_merge_commit"] == "992c0c33ca9e3db1bbe81914cd1de82b21c06bde"
    assert snapshot["history_mode"] == "initial_snapshot"
    assert len(snapshot["snapshot_id"]) == 16
    assert snapshot["operator_health"]["overall_operator_health"] == "PASS"
    assert snapshot["route_coverage"]["coverage_rate"] == "1.0000"
    assert snapshot["issue_counts"]["FAIL"] == 0
    assert snapshot["badge_summary"]["badge_count"] == 5
    assert snapshot["action_count"] == 5
    assert len(snapshot["source_artifact_sha256"]) == len(history.REQUIRED_SOURCE_ARTIFACTS)
    assert all(len(value) == 64 for value in snapshot["source_artifact_sha256"].values())
    assert snapshot["statements"]["db_opened"] is False
    assert snapshot["statements"]["adapter_calls"] is False
    assert snapshot["statements"]["new_scoring"] is False
    assert snapshot["statements"]["deployed"] is False
    assert snapshot["statements"]["blended_leaderboard"] is False


def test_status_delta_csv_schema_and_initial_snapshot_rows(double_run):
    first, _ = double_run
    assert tuple(first.status_delta_rows[0]) == history.STATUS_DELTA_COLUMNS
    by_metric = {row["metric_name"]: row for row in first.status_delta_rows}
    assert {"overall_operator_health", "route_coverage_rate", "action_count"}.issubset(by_metric)
    assert {row["status"] for row in first.status_delta_rows} == {"PASS"}
    for row in first.status_delta_rows:
        assert row["baseline_value"] == row["current_value"]
        assert "Initial snapshot baseline=current" in row["notes"]


def test_issue_trends_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.issue_trend_rows[0]) == history.ISSUE_TRENDS_COLUMNS
    row = first.issue_trend_rows[0]
    assert row["issue_type"] == "no_operator_blocking_issues"
    assert row["current_count"] == row["baseline_count"] == "1"
    assert row["trend"] == "initial_snapshot"
    assert row["severity"] == "INFO"


def test_snapshot_comparison_json_schema(double_run):
    first, _ = double_run
    comparison = first.snapshot_comparison
    assert comparison["task"] == history.TASK
    assert comparison["baseline_snapshot_id"] == first.health_snapshot["snapshot_id"]
    assert comparison["current_snapshot_id"] == first.health_snapshot["snapshot_id"]
    assert comparison["comparison_status"] == "INITIAL_SNAPSHOT_NO_CHANGES"
    assert comparison["changed_metrics"] == ()
    assert "overall_operator_health" in comparison["unchanged_metrics"]
    assert comparison["initial_snapshot"] is True


def test_history_html_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    html = first.history_html
    assert html.startswith("<!doctype html>")
    assert "Scope banner:" in html
    assert "Health snapshot summary" in html
    assert "Status delta table" in html
    assert "Issue trends table" in html
    assert "Badge summary" in html
    assert "Source artifact inventory" in html
    assert "Local commands" in html
    for line in history.DISCLAIMER_LINES:
        assert line in html
    assert "<script" not in html.lower()


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == history.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(history.REQUIRED_SOURCE_ARTIFACTS)
    assert len(output_rows) == len(history.P374_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 4
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.manifest_rows} == {"YES"}
    assert all(len(row["source_sha256"]) == 64 for row in source_rows)


def test_cli_generate_snapshot_delta_trends_compare_html_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_operator_history"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "overall operator health: PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in history.P374_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    snapshot_result = subprocess.run([sys.executable, "-m", module, "--snapshot"], check=True, text=True, capture_output=True)
    assert json.loads(snapshot_result.stdout)["operator_health"]["overall_operator_health"] == "PASS"

    delta_result = subprocess.run([sys.executable, "-m", module, "--delta"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(delta_result.stdout.splitlines()))["status"] == "PASS"

    trends_result = subprocess.run([sys.executable, "-m", module, "--trends"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(trends_result.stdout.splitlines()))["trend"] == "initial_snapshot"

    compare_result = subprocess.run([sys.executable, "-m", module, "--compare"], check=True, text=True, capture_output=True)
    assert json.loads(compare_result.stdout)["initial_snapshot"] is True

    html_result = subprocess.run([sys.executable, "-m", module, "--html"], check=True, text=True, capture_output=True)
    assert html_result.stdout.startswith("<!doctype html>")

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    assert "--snapshot" in help_result.stdout
    assert "--delta" in help_result.stdout
    assert "--trends" in help_result.stdout
    assert "--compare" in help_result.stdout
    assert "--html" in help_result.stdout


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert history._artifact_contents(first) == history._artifact_contents(second)
    first_paths = history.write_artifacts(first, tmp_path / "first")
    second_paths = history.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_html_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = history.write_artifacts(first, tmp_path)
    with open(paths["health_snapshot"], encoding="utf-8") as handle:
        assert json.load(handle)["operator_health"]["overall_operator_health"] == "PASS"
    with open(paths["snapshot_comparison"], encoding="utf-8") as handle:
        assert json.load(handle)["initial_snapshot"] is True
    with open(paths["status_delta"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == history.STATUS_DELTA_COLUMNS
    with open(paths["issue_trends"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == history.ISSUE_TRENDS_COLUMNS
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["history_html"].read_text(encoding="utf-8").startswith("<!doctype html>")


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "snapshot": first.health_snapshot,
            "delta": first.status_delta_rows,
            "trends": first.issue_trend_rows,
            "comparison": first.snapshot_comparison,
            "manifest": first.manifest_rows,
            "html": first.history_html,
        },
        sort_keys=True,
    ).lower()
    for line in history.DISCLAIMER_LINES:
        assert line.lower() in text
    assert "no db open/write" in text
    assert "no adapter calls" in text
    assert "no new scoring" in text
    assert "no deploy" in text
    assert "no blended leaderboard" in text
    assert not [phrase for phrase in history.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = history.run_operator_history()
    assert output.health_snapshot["statements"]["db_opened"] is False
    assert output.health_snapshot["statements"]["db_written"] is False
    assert output.health_snapshot["statements"]["adapter_calls"] is False
    assert "historical_adapters" not in sys.modules
    assert all(row["no_db_open_write"] == "YES" for row in output.manifest_rows)
