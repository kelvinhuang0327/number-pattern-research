import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_command_center as center


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P371 command center")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = center.run_command_center()
        second = center.run_command_center()
    finally:
        patcher.undo()
    return first, second


def test_required_p363_p370_artifacts_exist():
    paths = center.verify_required_artifacts()
    assert len(paths) == len(center.REQUIRED_SOURCE_FILES)
    assert all(path.is_file() for path in paths)


def test_index_json_schema(double_run):
    first, _ = double_run
    index = first.index
    assert index["task"] == center.TASK
    assert index["generated_at"] == center.GENERATED_AT
    assert index["source_merge_baseline"] == center.SOURCE_MERGE_BASELINE
    assert index["statements"]["db_opened"] is False
    assert index["status_summary"]["command_center_ready"] is True
    assert index["status_summary"]["p367_validation_fail_count"] == 0
    assert len(index["routes"]) == len(first.route_rows)


def test_routes_csv_schema_and_scope(double_run):
    first, _ = double_run
    assert tuple(first.route_rows[0]) == center.ROUTE_COLUMNS
    ids = {row["route_id"] for row in first.route_rows}
    assert {"status", "routes", "smoke", "list_tools", "list_artifacts", "task_cards", "validate"}.issubset(ids)
    for row in first.route_rows:
        assert row["no_db_open_write"] == "YES"
        assert row["no_adapter_calls"] == "YES"
        assert row["no_new_scoring"] == "YES"
        assert row["no_production_registry_import"] == "YES"
        assert row["no_deploy"] == "YES"
        for line in center.DISCLAIMER_LINES:
            assert line in row["scope_statement"]


def test_status_json_schema(double_run):
    first, _ = double_run
    status = first.status
    assert status["task"] == center.TASK
    assert status["command_center_ready"] is True
    assert status["required_source_file_count"] == len(center.REQUIRED_SOURCE_FILES)
    assert status["required_source_files_present"] == len(center.REQUIRED_SOURCE_FILES)
    assert status["db_registry_deploy_status"]["db_open_write"] == "NO"
    assert status["db_registry_deploy_status"]["adapter_calls"] == "NO"
    assert status["db_registry_deploy_status"]["new_scoring"] == "NO"


def test_smoke_results_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.smoke_rows[0]) == center.SMOKE_COLUMNS
    assert {row["status"] for row in first.smoke_rows} == {"PASS"}
    assert {row["no_db_open_write"] for row in first.smoke_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.smoke_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.smoke_rows} == {"YES"}


def test_task_cards_json_schema_and_template_only(double_run):
    first, _ = double_run
    cards = first.task_cards
    assert cards["task"] == center.TASK
    assert len(cards["task_cards"]) == 6
    for card in cards["task_cards"]:
        assert card["template_not_standing_authorization"] is True
        assert "not standing authorization" in card["copy_paste_prompt"].lower()
        for line in center.DISCLAIMER_LINES:
            assert line in card["copy_paste_prompt"]


def test_launchpad_and_quickstart_contain_scope(double_run):
    first, _ = double_run
    assert "<table>" in first.launchpad_html
    assert "P371 Big Lotto no-DB evidence command center" in first.quickstart_md
    for line in center.DISCLAIMER_LINES:
        assert line in first.launchpad_html
        assert line in first.quickstart_md


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == center.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(center.REQUIRED_SOURCE_FILES)
    assert len(output_rows) == len(center.P371_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 2
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert all(len(row["source_sha256"]) == 64 for row in source_rows)


def test_validation_rows_pass(double_run):
    first, _ = double_run
    assert tuple(first.validation_rows[0]) == center.VALIDATION_COLUMNS
    assert {row["status"] for row in first.validation_rows} == {"PASS"}
    names = {row["check_name"] for row in first.validation_rows}
    assert "required_p363_p370_files_exist" in names
    assert "deterministic_double_run_equality" in names
    assert "generated_artifacts_do_not_authorize_forbidden_actions" in names


def test_query_route_and_recipe_work():
    status = center.query_command_center("status")
    assert status["query_type"] == "route"
    assert status["payload"]["command_center_ready"] is True
    recipe = center.query_command_center("list_adapters")
    assert recipe["query_type"] == "p369_recipe_result"
    assert recipe["recipe_result"]["status"] == "PASS"


def test_cli_generate_help_and_required_commands_work(tmp_path):
    generate_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_command_center",
            "--artifacts-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    assert "Generated task cards are templates, not standing authorization" in generate_result.stdout
    for basename in center.P371_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    help_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_command_center", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "usage:" in help_result.stdout

    validate_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_command_center", "--validate"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}


def test_cli_emit_commands_work():
    for flag in ("--status", "--list-tools", "--show-task-cards", "--query"):
        command = [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_command_center", flag]
        if flag == "--query":
            command.append("list_adapters")
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        assert json.loads(result.stdout)["task"] == center.TASK

    for flag, columns in (("--routes", center.ROUTE_COLUMNS), ("--smoke", center.SMOKE_COLUMNS), ("--list-artifacts", center.MANIFEST_COLUMNS)):
        result = subprocess.run(
            [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_command_center", flag],
            check=True,
            text=True,
            capture_output=True,
        )
        rows = list(csv.DictReader(result.stdout.splitlines()))
        assert rows
        assert tuple(rows[0]) == columns


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert center._artifact_contents(first) == center._artifact_contents(second)
    first_paths = center.write_artifacts(first, tmp_path / "first")
    second_paths = center.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = center.write_artifacts(first, tmp_path)
    with open(paths["index"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == center.TASK
    with open(paths["status"], encoding="utf-8") as handle:
        assert json.load(handle)["command_center_ready"] is True
    with open(paths["task_cards"], encoding="utf-8") as handle:
        assert len(json.load(handle)["task_cards"]) == 6
    with open(paths["routes"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == center.ROUTE_COLUMNS
    with open(paths["smoke_results"], newline="", encoding="utf-8") as handle:
        assert {row["status"] for row in csv.DictReader(handle)} == {"PASS"}
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["launchpad"].read_text(encoding="utf-8").startswith("<!doctype html>")
    assert paths["quickstart"].read_text(encoding="utf-8").startswith("# P371 Big Lotto no-DB evidence command center quickstart")


def test_generated_outputs_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "index": first.index,
            "routes": first.route_rows,
            "status": first.status,
            "smoke": first.smoke_rows,
            "task_cards": first.task_cards,
            "quickstart": first.quickstart_md,
        },
        sort_keys=True,
    ).lower()
    assert not [phrase for phrase in center.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_no_db_import_open_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = center.run_command_center()
    assert output.status["statements"]["db_opened"] is False
    assert all(row["no_db_open_write"] == "YES" for row in output.manifest_rows)
    assert "historical_adapters" not in sys.modules
