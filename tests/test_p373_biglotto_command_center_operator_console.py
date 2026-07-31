import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_command_center_operator_console as console


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P373 operator console")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = console.run_operator_console()
        second = console.run_operator_console()
    finally:
        patcher.undo()
    return first, second


def test_required_p371_p372_artifacts_exist():
    paths = console.verify_required_evidence()
    assert len(paths) == len(console.REQUIRED_SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)


def test_operator_status_json_schema(double_run):
    first, _ = double_run
    status = first.status
    assert status["task"] == console.TASK
    assert status["source_baseline"]["required_origin_main_merge_commit"] == "269e50da43b0173809a44bc6010668ba92e488ca"
    assert status["required_source_file_count"] == len(console.REQUIRED_SOURCE_ARTIFACTS)
    assert status["required_source_files_present"] == len(console.REQUIRED_SOURCE_ARTIFACTS)
    assert status["p371_command_center_status"]["command_center_ready"] is True
    assert status["p372_route_replay_status"]["route_health_fail_count"] == 0
    assert status["route_coverage_summary"]["coverage_rate"] == "1.0000"
    assert status["overall_operator_health"] == "PASS"
    assert status["statements"]["db_opened"] is False
    assert status["statements"]["adapter_calls"] is False
    assert status["statements"]["new_scoring"] is False
    assert status["statements"]["deployed"] is False


def test_badges_json_schema(double_run):
    first, _ = double_run
    badges = first.badges
    assert badges["task"] == console.TASK
    by_id = {badge["badge_id"]: badge for badge in badges["badges"]}
    assert set(by_id) == {
        "overall_health",
        "route_replay_health",
        "smoke_health",
        "artifact_health",
        "prompt_template_safety",
    }
    for badge in by_id.values():
        assert set(badge) == {"badge_id", "label", "status", "summary", "severity"}
        assert badge["status"] == "PASS"
        assert badge["severity"] == "low"


def test_issues_csv_schema_and_info_row(double_run):
    first, _ = double_run
    assert tuple(first.issue_rows[0]) == console.ISSUE_COLUMNS
    assert len(first.issue_rows) == 1
    row = first.issue_rows[0]
    assert row["issue_id"] == "P373-INFO-001"
    assert row["severity"] == "INFO"
    assert row["issue_type"] == "no_operator_blocking_issues"
    assert row["status"] == "INFO"


def test_actions_json_schema_and_template_only(double_run):
    first, _ = double_run
    actions = first.actions
    assert actions["task"] == console.TASK
    assert len(actions["action_cards"]) == 5
    card_ids = {card["card_id"] for card in actions["action_cards"]}
    assert {
        "run_command_center_status",
        "run_route_replay_validate",
        "inspect_failing_routes",
        "inspect_artifact_inventory",
        "rerun_regression_tests",
    } == card_ids
    for card in actions["action_cards"]:
        assert card["template_not_standing_authorization"] is True
        assert card["no_db_open_write"] is True
        assert card["no_adapter_calls"] is True
        assert card["no_new_scoring"] is True
        assert card["no_deploy"] is True
        assert "not standing authorization" in card["operator_note"].lower()


def test_console_html_contains_required_sections(double_run):
    first, _ = double_run
    html = first.console_html
    assert html.startswith("<!doctype html>")
    assert "Scope:" in html
    assert "Health badges" in html
    assert "Route coverage summary" in html
    assert "Issue table" in html
    assert "Action cards" in html
    assert "Source artifact inventory" in html
    assert "Local commands" in html
    assert "No DB open/write." in html
    assert "<script" not in html.lower()


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == console.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(console.REQUIRED_SOURCE_ARTIFACTS)
    assert len(output_rows) == len(console.P373_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 3
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["operator_manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["operator_manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert all(len(row["source_sha256"]) == 64 for row in source_rows)


def test_validation_rows_pass(double_run):
    first, _ = double_run
    assert tuple(first.validation_rows[0]) == console.VALIDATION_COLUMNS
    assert {row["status"] for row in first.validation_rows} == {"PASS"}
    names = {row["check_name"] for row in first.validation_rows}
    assert "required_p371_p372_evidence_exists" in names
    assert "deterministic_double_run_equality" in names
    assert "generated_outputs_do_not_authorize_forbidden_actions" in names


def test_cli_generate_flags_validate_and_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_command_center_operator_console"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "overall operator health: PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in console.P373_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    status_result = subprocess.run([sys.executable, "-m", module, "--status"], check=True, text=True, capture_output=True)
    assert json.loads(status_result.stdout)["overall_operator_health"] == "PASS"

    badges_result = subprocess.run([sys.executable, "-m", module, "--badges"], check=True, text=True, capture_output=True)
    assert len(json.loads(badges_result.stdout)["badges"]) == 5

    issues_result = subprocess.run([sys.executable, "-m", module, "--issues"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(issues_result.stdout.splitlines()))["severity"] == "INFO"

    actions_result = subprocess.run([sys.executable, "-m", module, "--actions"], check=True, text=True, capture_output=True)
    assert len(json.loads(actions_result.stdout)["action_cards"]) == 5

    console_result = subprocess.run([sys.executable, "-m", module, "--console"], check=True, text=True, capture_output=True)
    assert console_result.stdout.startswith("<!doctype html>")

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    assert "--badges" in help_result.stdout


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert console._artifact_contents(first) == console._artifact_contents(second)
    first_paths = console.write_artifacts(first, tmp_path / "first")
    second_paths = console.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_html_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = console.write_artifacts(first, tmp_path)
    with open(paths["operator_status"], encoding="utf-8") as handle:
        assert json.load(handle)["overall_operator_health"] == "PASS"
    with open(paths["operator_badges"], encoding="utf-8") as handle:
        assert len(json.load(handle)["badges"]) == 5
    with open(paths["operator_actions"], encoding="utf-8") as handle:
        assert len(json.load(handle)["action_cards"]) == 5
    with open(paths["operator_issues"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == console.ISSUE_COLUMNS
    with open(paths["operator_manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["operator_console"].read_text(encoding="utf-8").startswith("<!doctype html>")


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "status": first.status,
            "badges": first.badges,
            "issues": first.issue_rows,
            "actions": first.actions,
            "manifest": first.manifest_rows,
            "console": first.console_html,
        },
        sort_keys=True,
    ).lower()
    for line in console.DISCLAIMER_LINES:
        assert line.lower() in text
    assert not [phrase for phrase in console.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_no_db_import_open_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = console.run_operator_console()
    assert output.status["statements"]["db_opened"] is False
    assert output.status["statements"]["db_written"] is False
    assert output.status["statements"]["adapter_calls"] is False
    assert all(row["no_db_open_write"] == "YES" for row in output.manifest_rows)
    assert "historical_adapters" not in sys.modules
