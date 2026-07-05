import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_command_center_regression_runner as runner


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P377 regression runner")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = runner.run_regression(include_validation=False)
        second = runner.run_regression(include_validation=False)
    finally:
        patcher.undo()
    return first, second


def test_required_p371_p372_p373_p374_p375_p376_modules_and_artifacts_exist():
    paths = runner.verify_required_evidence()
    assert len(paths) == len(runner.REQUIRED_SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)
    required = set(runner.REQUIRED_SOURCE_ARTIFACTS)
    assert "recovered_strategies/biglotto/no_db_evidence_command_center.py" in required
    assert "recovered_strategies/biglotto/no_db_acceptance_summary.py" in required
    assert "artifacts/P376_biglotto_acceptance_summary_agent.json" in required
    assert "tests/test_p376_biglotto_acceptance_summary.py" in required


def test_regression_results_json_schema(double_run):
    first, _ = double_run
    results = first.results
    assert results["task"] == runner.TASK
    assert results["source_baseline"]["required_origin_main_merge_commit"] == "8467ea77b851fc94951490332c51dc7ffd7b868f"
    assert results["overall_status"] == "PASS"
    assert results["command_count"] == len(runner.SAFE_COMMAND_SPECS)
    assert results["pass_count"] == len(runner.SAFE_COMMAND_SPECS)
    assert results["warn_count"] == 0
    assert results["fail_count"] == 0
    assert results["artifact_count"] == len(runner.REQUIRED_SOURCE_ARTIFACTS)
    assert results["statements"]["db_opened"] is False
    assert results["statements"]["db_written"] is False
    assert results["statements"]["adapter_calls"] is False
    assert results["statements"]["new_scoring"] is False
    assert results["statements"]["deployed"] is False


def test_commands_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.command_rows[0]) == runner.COMMAND_COLUMNS
    assert len(first.command_rows) == len(runner.SAFE_COMMAND_SPECS)
    assert {row["status"] for row in first.command_rows} == {"PASS"}
    assert {row["no_db_confirmed"] for row in first.command_rows} == {"YES"}
    assert {row["no_adapter_calls_confirmed"] for row in first.command_rows} == {"YES"}
    assert {row["no_new_scoring_confirmed"] for row in first.command_rows} == {"YES"}
    assert all("--validate" in row["command"] for row in first.command_rows)


def test_failures_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.failure_rows[0]) == runner.FAILURE_COLUMNS
    assert first.failure_rows == (
        {
            "failure_id": "none",
            "command_id": "none",
            "failure_class": "none",
            "severity": "none",
            "blocking": "false",
            "description": "No warnings or failures were observed.",
            "remediation_hint": "No remediation required.",
        },
    )


def test_artifact_freshness_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.freshness_rows[0]) == runner.FRESHNESS_COLUMNS
    assert len(first.freshness_rows) == len(runner.REQUIRED_SOURCE_ARTIFACTS)
    assert {row["exists"] for row in first.freshness_rows} == {"YES"}
    assert {row["freshness_status"] for row in first.freshness_rows} == {"FRESH"}
    assert all(len(row["sha256"]) == 64 for row in first.freshness_rows)
    assert all(row["row_or_object_count"] for row in first.freshness_rows)


def test_html_report_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    page = first.report_html
    assert page.startswith("<!doctype html>")
    for required in (
        "Scope banner:",
        "Overall Status",
        "Command Results Table",
        "Failures Table",
        "Artifact Freshness Table",
        "Local Commands",
        "No-DB / No-Adapter / No-Scoring / No-Deploy Disclaimers",
    ):
        assert required in page
    for line in runner.DISCLAIMER_LINES:
        assert line in page
    assert "<script" not in page.lower()


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == runner.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(runner.REQUIRED_SOURCE_ARTIFACTS)
    assert len(output_rows) == len(runner.P377_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 4
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.manifest_rows} == {"YES"}


def test_cli_generate_run_commands_failures_freshness_report_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_command_center_regression_runner"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "overall status: PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in runner.P377_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    run_result = subprocess.run([sys.executable, "-m", module, "--run"], check=True, text=True, capture_output=True)
    assert json.loads(run_result.stdout)["overall_status"] == "PASS"

    commands_result = subprocess.run([sys.executable, "-m", module, "--commands"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(commands_result.stdout.splitlines()))["status"] == "PASS"

    failures_result = subprocess.run([sys.executable, "-m", module, "--failures"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(failures_result.stdout.splitlines()))["failure_id"] == "none"

    freshness_result = subprocess.run([sys.executable, "-m", module, "--freshness"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(freshness_result.stdout.splitlines()))["freshness_status"] == "FRESH"

    report_result = subprocess.run([sys.executable, "-m", module, "--report"], check=True, text=True, capture_output=True)
    assert report_result.stdout.startswith("<!doctype html>")

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    assert "--generate" in help_result.stdout
    assert "--run" in help_result.stdout
    assert "--commands" in help_result.stdout
    assert "--failures" in help_result.stdout
    assert "--freshness" in help_result.stdout
    assert "--report" in help_result.stdout
    assert "--validate" in help_result.stdout


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert runner._artifact_contents(first) == runner._artifact_contents(second)
    first_paths = runner.write_artifacts(first, tmp_path / "first")
    second_paths = runner.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_html_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = runner.write_artifacts(first, tmp_path)
    with open(paths["results"], encoding="utf-8") as handle:
        assert json.load(handle)["overall_status"] == "PASS"
    with open(paths["commands"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == runner.COMMAND_COLUMNS
    with open(paths["failures"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == runner.FAILURE_COLUMNS
    with open(paths["freshness"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == runner.FRESHNESS_COLUMNS
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["report"].read_text(encoding="utf-8").startswith("<!doctype html>")


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "results": first.results,
            "commands": first.command_rows,
            "failures": first.failure_rows,
            "freshness": first.freshness_rows,
            "manifest": first.manifest_rows,
            "report": first.report_html,
        },
        sort_keys=True,
    ).lower()
    for line in runner.DISCLAIMER_LINES:
        assert line.lower() in text
    assert "no db open/write" in text
    assert "no adapter calls" in text
    assert "no new scoring" in text
    assert "no deploy" in text
    assert "no production registry import" in text
    assert "no betting advice" in text
    assert "no future prediction guarantee" in text
    assert "no blended leaderboard" in text
    assert not [phrase for phrase in runner.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    freshness = runner.build_artifact_freshness()
    assert len(freshness) == len(runner.REQUIRED_SOURCE_ARTIFACTS)
    assert "historical_adapters" not in sys.modules
    assert "lottery_adapter" not in sys.modules


def test_p377_generation_does_not_modify_p371_p376_artifacts(tmp_path, double_run):
    before = {row["path"]: row["sha256"] for row in runner.source_inventory()}
    runner.write_artifacts(double_run[0], tmp_path)
    after = {row["path"]: row["sha256"] for row in runner.source_inventory()}
    assert before == after


def test_generated_outputs_write_only_p377_prefixed_paths(tmp_path, double_run):
    paths = runner.write_artifacts(double_run[0], tmp_path)
    assert set(paths) == set(runner.P377_ARTIFACT_BASENAMES)
    assert all(path.name.startswith("P377_biglotto_command_center_regression_") for path in paths.values())
