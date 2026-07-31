import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_regression_archive_explorer as explorer


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P379 regression archive explorer")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = explorer.run_explorer(include_validation=False)
        second = explorer.run_explorer(include_validation=False)
    finally:
        patcher.undo()
    return first, second


def test_required_p378_module_and_artifacts_exist():
    paths = explorer.verify_required_artifacts()
    assert len(paths) == len(explorer.P378_SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)
    required = set(explorer.P378_SOURCE_ARTIFACTS.values())
    assert "recovered_strategies/biglotto/no_db_regression_run_archive.py" in required
    assert "artifacts/P378_biglotto_regression_run_archive_index.json" in required
    assert "artifacts/P378_biglotto_regression_run_archive_snapshot.json" in required
    assert "artifacts/P378_biglotto_regression_run_archive_command_delta.csv" in required
    assert "artifacts/P378_biglotto_regression_run_archive_freshness_delta.csv" in required


def test_index_json_schema(double_run):
    first, _ = double_run
    index = first.index
    assert index["task"] == explorer.TASK
    assert index["source_baseline"]["required_origin_main_commit"] == explorer.P378_BASELINE_COMMIT
    assert set(index) >= {
        "source_baseline",
        "source_p378_artifact_paths",
        "source_p378_sha256",
        "generated_p379_artifact_paths",
        "counts",
        "routes",
        "statements",
    }
    assert index["counts"]["catalog_rows"] == len(explorer.P378_SOURCE_ARTIFACTS)
    assert index["counts"]["command_rows"] == 6
    assert index["counts"]["freshness_rows"] == 50
    assert all(path.startswith("artifacts/P379_biglotto_regression_archive_explorer_") for path in index["generated_p379_artifact_paths"].values())


def test_catalog_csv_schema_and_source_hashes(double_run):
    first, _ = double_run
    assert tuple(first.catalog_rows[0]) == explorer.CATALOG_COLUMNS
    assert len(first.catalog_rows) == len(explorer.P378_SOURCE_ARTIFACTS)
    by_role = {row["artifact_role"]: row for row in first.catalog_rows}
    assert by_role["snapshot"]["explorer_route"] == "summary"
    assert by_role["command_delta"]["explorer_route"] == "commands"
    assert by_role["freshness_delta"]["explorer_route"] == "freshness"
    assert {row["no_db_open_write"] for row in first.catalog_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.catalog_rows} == {"YES"}
    assert all(len(row["sha256"]) == 64 for row in first.catalog_rows)


def test_snapshot_summary_schema(double_run):
    first, _ = double_run
    summary = first.snapshot_summary
    assert summary["task"] == explorer.TASK
    assert summary["p378_task"] == "P378_biglotto_regression_run_archive"
    assert summary["p378_comparison_status"] == "PASS"
    assert summary["p377_overall_status"] == "PASS"
    assert summary["p377_command_count"] == 6
    assert summary["p377_pass_count"] == 6
    assert summary["p377_warn_count"] == 0
    assert summary["p377_fail_count"] == 0
    assert summary["p377_artifact_count"] == 50
    assert summary["statements"]["db_opened"] is False
    assert summary["statements"]["adapter_calls"] is False


def test_command_view_schema_and_filters(double_run):
    first, _ = double_run
    rows = first.command_view_rows
    assert tuple(rows[0]) == explorer.COMMAND_VIEW_COLUMNS
    assert len(rows) == 6
    assert {row["delta_status"] for row in rows} == {"PASS"}
    assert {row["status_delta"] for row in rows} == {"UNCHANGED"}
    assert {row["explorer_status"] for row in rows} == {"QUERYABLE"}
    assert len(explorer.filter_commands(rows, status="PASS")) == 6
    assert len(explorer.filter_commands(rows, delta="UNCHANGED")) == 6
    assert explorer.filter_commands(rows, status="FAIL") == ()


def test_freshness_view_schema_and_filters(double_run):
    first, _ = double_run
    rows = first.freshness_view_rows
    assert tuple(rows[0]) == explorer.FRESHNESS_VIEW_COLUMNS
    assert len(rows) == 50
    assert {row["sha256_delta"] for row in rows} == {"UNCHANGED"}
    assert {row["freshness_delta_status"] for row in rows} == {"PASS"}
    assert {row["explorer_status"] for row in rows} == {"QUERYABLE"}
    assert all(len(row["current_sha256"]) == 64 for row in rows)
    assert len(explorer.filter_freshness(rows, status="PASS")) == 50
    assert len(explorer.filter_freshness(rows, sha_delta="UNCHANGED")) == 50
    assert explorer.filter_freshness(rows, sha_delta="CHANGED") == ()


def test_query_snapshots_schema(double_run):
    first, _ = double_run
    snapshots = first.query_snapshots
    assert snapshots["task"] == explorer.TASK
    assert snapshots["generated_at"] == explorer.GENERATED_AT
    assert snapshots["scope"]["db_opened"] is False
    assert snapshots["scope"]["adapter_calls"] is False
    assert snapshots["counts"]["source_artifacts"] == len(explorer.P378_SOURCE_ARTIFACTS)
    assert snapshots["counts"]["command_rows"] == 6
    assert snapshots["counts"]["freshness_rows"] == 50
    assert len(snapshots["query_examples"]["list_artifacts"]) == len(explorer.P378_SOURCE_ARTIFACTS)
    assert snapshots["query_examples"]["show_artifact_index"]["artifact_role"] == "index"
    assert snapshots["query_examples"]["summary"]["p378_comparison_status"] == "PASS"
    assert len(snapshots["query_examples"]["filter_commands_pass"]) == 6
    assert len(snapshots["query_examples"]["filter_freshness_unchanged"]) == 50


def test_html_explorer_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    page = first.html_text
    assert page.startswith("<!doctype html>")
    for required in (
        "Scope / disclaimer banner",
        "Explorer Index",
        "Snapshot Summary Section",
        "Archive Catalog Section",
        "Command View Section",
        "Freshness View Section",
        "Query Snapshot Section",
        "No-DB / No-Adapter / No-Scoring / No-Deploy Disclaimers",
    ):
        assert required in page
    for line in explorer.DISCLAIMER_LINES:
        assert line in page
    assert "<script" not in page.lower()


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == explorer.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(explorer.P378_SOURCE_ARTIFACTS)
    assert len(output_rows) == len(explorer.P379_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 4
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.manifest_rows} == {"YES"}


def test_cli_generate_index_summary_catalog_commands_freshness_snapshots_html_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_regression_archive_explorer"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "snapshot summary: P378=PASS P377=PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in explorer.P379_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    index_result = subprocess.run([sys.executable, "-m", module, "--index"], check=True, text=True, capture_output=True)
    assert json.loads(index_result.stdout)["task"] == explorer.TASK

    summary_result = subprocess.run([sys.executable, "-m", module, "--summary"], check=True, text=True, capture_output=True)
    assert json.loads(summary_result.stdout)["p378_comparison_status"] == "PASS"

    catalog_result = subprocess.run([sys.executable, "-m", module, "--catalog"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(catalog_result.stdout.splitlines()))["artifact_role"] == "module"

    commands_result = subprocess.run([sys.executable, "-m", module, "--commands", "--command-status", "PASS"], check=True, text=True, capture_output=True)
    assert len(list(csv.DictReader(commands_result.stdout.splitlines()))) == 6

    freshness_result = subprocess.run([sys.executable, "-m", module, "--freshness", "--sha-delta", "UNCHANGED"], check=True, text=True, capture_output=True)
    assert len(list(csv.DictReader(freshness_result.stdout.splitlines()))) == 50

    snapshots_result = subprocess.run([sys.executable, "-m", module, "--snapshots"], check=True, text=True, capture_output=True)
    assert json.loads(snapshots_result.stdout)["counts"]["command_rows"] == 6

    html_result = subprocess.run([sys.executable, "-m", module, "--html"], check=True, text=True, capture_output=True)
    assert html_result.stdout.startswith("<!doctype html>")

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    for flag in ("--generate", "--index", "--summary", "--catalog", "--commands", "--freshness", "--snapshots", "--html", "--validate"):
        assert flag in help_result.stdout


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "index": first.index,
            "catalog": first.catalog_rows,
            "snapshot_summary": first.snapshot_summary,
            "command_view": first.command_view_rows,
            "freshness_view": first.freshness_view_rows,
            "query_snapshots": first.query_snapshots,
            "html": first.html_text,
            "manifest": first.manifest_rows,
        },
        sort_keys=True,
    ).lower()
    for line in explorer.DISCLAIMER_LINES:
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
    assert not [phrase for phrase in explorer.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert explorer._artifact_contents(first) == explorer._artifact_contents(second)
    first_paths = explorer.write_artifacts(first, tmp_path / "first")
    second_paths = explorer.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_html_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = explorer.write_artifacts(first, tmp_path)
    with open(paths["index"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == explorer.TASK
    with open(paths["snapshot_summary"], encoding="utf-8") as handle:
        assert json.load(handle)["p377_overall_status"] == "PASS"
    with open(paths["query_snapshots"], encoding="utf-8") as handle:
        assert json.load(handle)["counts"]["freshness_rows"] == 50
    with open(paths["catalog"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == explorer.CATALOG_COLUMNS
    with open(paths["command_view"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == explorer.COMMAND_VIEW_COLUMNS
    with open(paths["freshness_view"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == explorer.FRESHNESS_VIEW_COLUMNS
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["html"].read_text(encoding="utf-8").startswith("<!doctype html>")


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = explorer.run_explorer(include_validation=False)
    assert output.snapshot_summary["statements"]["db_opened"] is False
    assert output.snapshot_summary["statements"]["adapter_calls"] is False
    assert "historical_adapters" not in sys.modules
    assert "lottery_api.models.replay_strategy_registry" not in sys.modules


def test_generated_outputs_write_only_p379_prefixed_paths(tmp_path, double_run):
    paths = explorer.write_artifacts(double_run[0], tmp_path)
    assert set(paths) == set(explorer.P379_ARTIFACT_BASENAMES)
    assert all(path.name.startswith("P379_biglotto_regression_archive_explorer_") for path in paths.values())
