import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_regression_run_archive as archive


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P378 regression run archive")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = archive.run_archive(include_validation=False)
        second = archive.run_archive(include_validation=False)
    finally:
        patcher.undo()
    return first, second


def test_required_p377_module_and_artifacts_exist():
    paths = archive.verify_required_evidence()
    assert len(paths) == len(archive.P377_SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)
    required = set(archive.P377_SOURCE_ARTIFACTS.values())
    assert "recovered_strategies/biglotto/no_db_command_center_regression_runner.py" in required
    assert "artifacts/P377_biglotto_command_center_regression_results.json" in required
    assert "artifacts/P377_biglotto_command_center_regression_commands.csv" in required
    assert "artifacts/P377_biglotto_command_center_regression_artifact_freshness.csv" in required


def test_archive_index_json_schema(double_run):
    first, _ = double_run
    index = first.index
    assert index["task"] == archive.TASK
    assert index["source_baseline"]["required_origin_main_merge_commit"] == archive.P377_BASELINE_COMMIT
    assert set(index) >= {
        "source_baseline",
        "source_p377_artifact_paths",
        "source_p377_sha256",
        "generated_p378_artifact_paths",
        "current_run_snapshot_id",
        "initial_archive",
        "statements",
    }
    assert index["current_run_snapshot_id"] == archive.SNAPSHOT_ID
    assert index["initial_archive"] is True
    assert len(index["source_p377_sha256"]) == len(archive.P377_SOURCE_ARTIFACTS)
    assert all(len(value) == 64 for value in index["source_p377_sha256"].values())
    assert all(path.startswith("artifacts/P378_biglotto_regression_run_archive_") for path in index["generated_p378_artifact_paths"].values())


def test_run_snapshot_json_schema(double_run):
    first, _ = double_run
    snapshot = first.snapshot
    assert snapshot["snapshot_id"] == archive.SNAPSHOT_ID
    assert snapshot["source_baseline"]["required_origin_main_merge_commit"] == archive.P377_BASELINE_COMMIT
    assert snapshot["p377_overall_status"] == "PASS"
    assert snapshot["p377_command_count"] == 6
    assert snapshot["p377_pass_count"] == 6
    assert snapshot["p377_warn_count"] == 0
    assert snapshot["p377_fail_count"] == 0
    assert snapshot["p377_artifact_count"] == 50
    assert len(snapshot["p377_artifact_sha256_inventory"]) == len(archive.P377_SOURCE_ARTIFACTS)
    assert snapshot["statements"]["db_opened"] is False
    assert snapshot["statements"]["db_written"] is False
    assert snapshot["statements"]["adapter_calls"] is False
    assert snapshot["statements"]["new_scoring"] is False
    assert snapshot["statements"]["deployed"] is False


def test_comparison_json_schema(double_run):
    first, _ = double_run
    comparison = first.comparison
    assert comparison["baseline_snapshot_id"] == archive.SNAPSHOT_ID
    assert comparison["current_snapshot_id"] == archive.SNAPSHOT_ID
    assert comparison["comparison_status"] == "PASS"
    assert comparison["initial_archive"] is True
    assert comparison["changed_metrics"] == {}
    assert set(comparison["unchanged_metrics"]) == {
        "p377_artifact_count",
        "p377_command_count",
        "p377_fail_count",
        "p377_overall_status",
        "p377_pass_count",
        "p377_warn_count",
    }
    assert "baseline=current" in comparison["notes"]


def test_command_delta_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.command_delta_rows[0]) == archive.COMMAND_DELTA_COLUMNS
    assert len(first.command_delta_rows) == 6
    assert {row["previous_status"] for row in first.command_delta_rows} == {"PASS"}
    assert {row["current_status"] for row in first.command_delta_rows} == {"PASS"}
    assert {row["status_delta"] for row in first.command_delta_rows} == {"UNCHANGED"}
    assert {row["delta_status"] for row in first.command_delta_rows} == {"PASS"}
    assert all("not re-executed" in row["notes"] for row in first.command_delta_rows)


def test_freshness_delta_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.freshness_delta_rows[0]) == archive.FRESHNESS_DELTA_COLUMNS
    assert len(first.freshness_delta_rows) == 50
    assert {row["sha256_delta"] for row in first.freshness_delta_rows} == {"UNCHANGED"}
    assert {row["freshness_delta_status"] for row in first.freshness_delta_rows} == {"PASS"}
    assert all(len(row["current_sha256"]) == 64 for row in first.freshness_delta_rows)
    assert all(row["previous_row_or_object_count"] == row["current_row_or_object_count"] for row in first.freshness_delta_rows)


def test_html_report_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    page = first.report_html
    assert page.startswith("<!doctype html>")
    for required in (
        "Scope banner:",
        "Current Snapshot Summary",
        "Comparison Summary",
        "Command Delta Table",
        "Freshness Delta Table",
        "Source P377 Artifact Inventory",
        "Local Commands",
        "No-DB / No-Adapter / No-Scoring / No-Deploy Disclaimers",
    ):
        assert required in page
    for line in archive.DISCLAIMER_LINES:
        assert line in page
    assert "<script" not in page.lower()


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == archive.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(archive.P377_SOURCE_ARTIFACTS)
    assert len(output_rows) == len(archive.P378_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 4
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.manifest_rows} == {"YES"}


def test_cli_generate_index_snapshot_compare_command_delta_freshness_delta_report_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_regression_run_archive"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "comparison status: PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in archive.P378_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    index_result = subprocess.run([sys.executable, "-m", module, "--index"], check=True, text=True, capture_output=True)
    assert json.loads(index_result.stdout)["current_run_snapshot_id"] == archive.SNAPSHOT_ID

    snapshot_result = subprocess.run([sys.executable, "-m", module, "--snapshot"], check=True, text=True, capture_output=True)
    assert json.loads(snapshot_result.stdout)["p377_overall_status"] == "PASS"

    compare_result = subprocess.run([sys.executable, "-m", module, "--compare"], check=True, text=True, capture_output=True)
    assert json.loads(compare_result.stdout)["comparison_status"] == "PASS"

    command_delta_result = subprocess.run([sys.executable, "-m", module, "--command-delta"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(command_delta_result.stdout.splitlines()))["delta_status"] == "PASS"

    freshness_delta_result = subprocess.run([sys.executable, "-m", module, "--freshness-delta"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(freshness_delta_result.stdout.splitlines()))["freshness_delta_status"] == "PASS"

    report_result = subprocess.run([sys.executable, "-m", module, "--report"], check=True, text=True, capture_output=True)
    assert report_result.stdout.startswith("<!doctype html>")

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    for flag in ("--generate", "--index", "--snapshot", "--compare", "--command-delta", "--freshness-delta", "--report", "--validate"):
        assert flag in help_result.stdout


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "index": first.index,
            "snapshot": first.snapshot,
            "comparison": first.comparison,
            "command_delta": first.command_delta_rows,
            "freshness_delta": first.freshness_delta_rows,
            "manifest": first.manifest_rows,
            "report": first.report_html,
        },
        sort_keys=True,
    ).lower()
    for line in archive.DISCLAIMER_LINES:
        assert line.lower() in text
    assert "no db open/write" in text
    assert "no adapter calls" in text
    assert "no new scoring" in text
    assert "no deploy" in text
    assert "no production registry import" in text
    assert "no betting advice" in text
    assert "no future prediction guarantee" in text
    assert "no blended leaderboard" in text
    assert "not production release approval" in text
    assert not [phrase for phrase in archive.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert archive._artifact_contents(first) == archive._artifact_contents(second)
    first_paths = archive.write_artifacts(first, tmp_path / "first")
    second_paths = archive.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_html_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = archive.write_artifacts(first, tmp_path)
    with open(paths["index"], encoding="utf-8") as handle:
        assert json.load(handle)["current_run_snapshot_id"] == archive.SNAPSHOT_ID
    with open(paths["snapshot"], encoding="utf-8") as handle:
        assert json.load(handle)["p377_overall_status"] == "PASS"
    with open(paths["comparison"], encoding="utf-8") as handle:
        assert json.load(handle)["comparison_status"] == "PASS"
    with open(paths["command_delta"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == archive.COMMAND_DELTA_COLUMNS
    with open(paths["freshness_delta"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == archive.FRESHNESS_DELTA_COLUMNS
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["report"].read_text(encoding="utf-8").startswith("<!doctype html>")


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    snapshot = archive.build_snapshot()
    assert snapshot["statements"]["db_opened"] is False
    assert "historical_adapters" not in sys.modules
    assert "lottery_adapter" not in sys.modules


def test_p378_generation_does_not_modify_p371_p377_artifacts(tmp_path, double_run):
    before = {row["path"]: row["sha256"] for row in archive.source_inventory()}
    archive.write_artifacts(double_run[0], tmp_path)
    after = {row["path"]: row["sha256"] for row in archive.source_inventory()}
    assert before == after


def test_generated_outputs_write_only_p378_prefixed_paths(tmp_path, double_run):
    paths = archive.write_artifacts(double_run[0], tmp_path)
    assert set(paths) == set(archive.P378_ARTIFACT_BASENAMES)
    assert all(path.name.startswith("P378_biglotto_regression_run_archive_") for path in paths.values())
