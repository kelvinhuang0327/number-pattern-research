import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_acceptance_summary as summary


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P376 acceptance summary")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = summary.run_summary()
        second = summary.run_summary()
    finally:
        patcher.undo()
    return first, second


def test_required_p371_p372_p373_p374_p375_modules_and_artifacts_exist():
    paths = summary.verify_required_evidence()
    assert len(paths) == len(summary.REQUIRED_SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)
    required_names = set(summary.REQUIRED_SOURCE_ARTIFACTS)
    assert "recovered_strategies/biglotto/no_db_operator_acceptance.py" in required_names
    assert "tests/test_p375_biglotto_operator_acceptance.py" in required_names
    assert "artifacts/P375_biglotto_operator_acceptance_decision.json" in required_names


def test_badges_json_schema(double_run):
    first, _ = double_run
    assert first.badges["task"] == summary.TASK
    assert first.badges["source_baseline"]["required_origin_main_merge_commit"] == "602fc1ead6cc86784db03612e76e9853c0c8de75"
    badges = first.badges["badges"]
    assert set(badges) == {
        "acceptance",
        "operator_health",
        "route_coverage",
        "issue",
        "no_db",
        "no_adapter_call",
        "no_new_scoring",
    }
    for badge in badges.values():
        assert set(badge) >= set(summary.BADGE_REQUIRED_KEYS)
        assert badge["status"] in {"PASS", "WARN", "FAIL"}
        assert badge["severity"] in {"low", "medium", "high"}
        assert badge["summary"]
    assert badges["acceptance"]["status"] == "PASS"
    assert badges["no_db"]["status"] == "PASS"
    assert badges["no_adapter_call"]["status"] == "PASS"
    assert badges["no_new_scoring"]["status"] == "PASS"


def test_status_block_markdown_contains_required_fields_and_disclaimers(double_run):
    first, _ = double_run
    text = first.status_block
    assert text.startswith("# P376 Big Lotto no-DB acceptance summary")
    for required in (
        "Acceptance decision:",
        "Source baseline:",
        "Operator health:",
        "Route coverage:",
        "Blocking issue count:",
        "Safe caveats:",
        "No future prediction guarantee.",
        "No betting advice.",
        "This is not production release approval.",
    ):
        assert required in text


def test_agent_json_schema(double_run):
    first, _ = double_run
    agent = first.agent_json
    assert set(agent) >= {
        "acceptance_summary",
        "source_artifacts",
        "recommended_safe_next_action_categories",
        "stop_boundaries",
        "not_authorized",
    }
    acceptance = agent["acceptance_summary"]
    assert acceptance["decision"] == "PASS"
    assert acceptance["accepted"] is True
    assert acceptance["blocking_issue_count"] == 0
    assert acceptance["statements"]["db_opened"] is False
    assert acceptance["statements"]["db_written"] is False
    assert acceptance["statements"]["adapter_calls"] is False
    assert acceptance["statements"]["new_scoring"] is False
    assert acceptance["statements"]["deployed"] is False
    assert len(agent["source_artifacts"]) == len(summary.REQUIRED_SOURCE_ARTIFACTS)
    assert all(len(row["sha256"]) == 64 for row in agent["source_artifacts"])
    assert any("DB open/write" in boundary for boundary in agent["stop_boundaries"])


def test_release_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.release_rows[0]) == summary.RELEASE_COLUMNS
    by_metric = {row["metric"]: row for row in first.release_rows}
    assert by_metric["acceptance_decision"]["value"] == "PASS"
    assert by_metric["accepted"]["value"] == "True"
    assert by_metric["operator_health"]["value"] == "PASS"
    assert by_metric["route_coverage_rate"]["value"] == "1.0000"
    assert by_metric["blocking_issue_count"]["value"] == "0"
    assert by_metric["no_db_open_write"]["value"] == "YES"
    assert by_metric["no_adapter_calls"]["value"] == "YES"
    assert by_metric["no_new_scoring"]["value"] == "YES"
    assert by_metric["not_production_release_approval"]["value"] == "YES"


def test_html_summary_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    page = first.html_summary
    assert page.startswith("<!doctype html>")
    assert "Acceptance Badge" in page
    assert "Compact Release Table" in page
    assert "Key Risk Notes" in page
    assert "Source Artifact List" in page
    assert "Local Commands" in page
    for line in summary.DISCLAIMER_LINES:
        assert line in page
    assert "<script" not in page.lower()


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == summary.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(summary.REQUIRED_SOURCE_ARTIFACTS)
    assert len(output_rows) == len(summary.P376_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 4
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.manifest_rows} == {"YES"}
    assert all(len(row["source_sha256"]) == 64 for row in source_rows)


def test_cli_generate_badges_status_block_agent_json_release_csv_html_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_acceptance_summary"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "acceptance decision: PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in summary.P376_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    badges_result = subprocess.run([sys.executable, "-m", module, "--badges"], check=True, text=True, capture_output=True)
    assert json.loads(badges_result.stdout)["badges"]["acceptance"]["status"] == "PASS"

    status_result = subprocess.run([sys.executable, "-m", module, "--status-block"], check=True, text=True, capture_output=True)
    assert "Acceptance decision: PASS" in status_result.stdout

    agent_result = subprocess.run([sys.executable, "-m", module, "--agent-json"], check=True, text=True, capture_output=True)
    assert json.loads(agent_result.stdout)["acceptance_summary"]["decision"] == "PASS"

    release_result = subprocess.run([sys.executable, "-m", module, "--release-csv"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(release_result.stdout.splitlines()))["metric"] == "acceptance_decision"

    html_result = subprocess.run([sys.executable, "-m", module, "--html"], check=True, text=True, capture_output=True)
    assert html_result.stdout.startswith("<!doctype html>")

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    assert "--badges" in help_result.stdout
    assert "--status-block" in help_result.stdout
    assert "--agent-json" in help_result.stdout
    assert "--release-csv" in help_result.stdout
    assert "--html" in help_result.stdout


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert summary._artifact_contents(first) == summary._artifact_contents(second)
    first_paths = summary.write_artifacts(first, tmp_path / "first")
    second_paths = summary.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_html_markdown_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = summary.write_artifacts(first, tmp_path)
    with open(paths["badges"], encoding="utf-8") as handle:
        assert json.load(handle)["badges"]["acceptance"]["status"] == "PASS"
    with open(paths["agent_json"], encoding="utf-8") as handle:
        assert json.load(handle)["acceptance_summary"]["accepted"] is True
    with open(paths["release_csv"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == summary.RELEASE_COLUMNS
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["html"].read_text(encoding="utf-8").startswith("<!doctype html>")
    assert "Safe caveats:" in paths["status_block"].read_text(encoding="utf-8")


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "badges": first.badges,
            "status_block": first.status_block,
            "agent_json": first.agent_json,
            "release_rows": first.release_rows,
            "manifest": first.manifest_rows,
            "html": first.html_summary,
        },
        sort_keys=True,
    ).lower()
    for line in summary.DISCLAIMER_LINES:
        assert line.lower() in text
    assert "no db open/write" in text
    assert "no adapter calls" in text
    assert "no new scoring" in text
    assert "no deploy" in text
    assert "no production registry import" in text
    assert "no betting advice" in text
    assert "no future prediction guarantee" in text
    assert "no blended leaderboard" in text
    assert "this is not production release approval" in text
    assert not [phrase for phrase in summary.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = summary.run_summary()
    acceptance = output.agent_json["acceptance_summary"]
    assert acceptance["statements"]["db_opened"] is False
    assert acceptance["statements"]["db_written"] is False
    assert acceptance["statements"]["adapter_calls"] is False
    assert "historical_adapters" not in sys.modules
    assert all(row["no_db_open_write"] == "YES" for row in output.manifest_rows)
