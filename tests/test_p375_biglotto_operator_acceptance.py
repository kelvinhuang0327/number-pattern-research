import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_operator_acceptance as acceptance


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P375 operator acceptance")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = acceptance.run_acceptance()
        second = acceptance.run_acceptance()
    finally:
        patcher.undo()
    return first, second


def test_required_p371_p372_p373_p374_modules_and_artifacts_exist():
    paths = acceptance.verify_required_evidence()
    assert len(paths) == len(acceptance.REQUIRED_SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)


def test_acceptance_decision_json_schema(double_run):
    first, _ = double_run
    decision = first.decision
    assert decision["task"] == acceptance.TASK
    assert decision["source_baseline"]["required_origin_main_merge_commit"] == "e7a9a16224d3fec10500283bafef38701e1d0d21"
    assert decision["overall_acceptance"] == "PASS"
    assert decision["accepted"] is True
    assert decision["blocking_issue_count"] == 0
    assert decision["rejection_reasons"] == ()
    assert decision["operator_health"]["p373_overall_operator_health"] == "PASS"
    assert decision["operator_health"]["p374_overall_operator_health"] == "PASS"
    assert decision["route_coverage"]["coverage_rate"] == "1.0000"
    assert decision["issue_counts"]["p373_issue_counts"]["FAIL"] == 0
    assert decision["statements"]["db_opened"] is False
    assert decision["statements"]["db_written"] is False
    assert decision["statements"]["adapter_calls"] is False
    assert decision["statements"]["new_scoring"] is False
    assert decision["statements"]["deployed"] is False
    assert decision["statements"]["strategy_status_changes"] is False
    assert decision["statements"]["blended_leaderboard"] is False


def test_checklist_csv_schema_and_rows(double_run):
    first, _ = double_run
    assert tuple(first.checklist_rows[0]) == acceptance.CHECKLIST_COLUMNS
    by_id = {row["check_id"]: row for row in first.checklist_rows}
    assert {"P375-CHECK-001", "P375-CHECK-004", "P375-CHECK-011"}.issubset(by_id)
    assert {row["status"] for row in first.checklist_rows} == {"PASS"}
    assert by_id["P375-CHECK-011"]["blocking"] == "true"
    assert "No DB, adapter, scoring" in by_id["P375-CHECK-011"]["description"]


def test_failure_matrix_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.failure_matrix_rows[0]) == acceptance.FAILURE_MATRIX_COLUMNS
    classes = {row["failure_class"] for row in first.failure_matrix_rows}
    assert "missing_artifact" in classes
    assert "operator_console_fail_or_warn_issue" in classes
    assert "operator_history_status_delta_failure" in classes
    assert all(row["current_count"] == "0" for row in first.failure_matrix_rows)


def test_risk_notes_json_schema(double_run):
    first, _ = double_run
    notes = first.risk_notes
    assert set(notes) >= {
        "technical_risks",
        "governance_risks",
        "known_non_goals",
        "retained_worktree_notes",
        "future_worker_notes",
        "statements",
    }
    assert any("No new scoring cohort" in item for item in notes["known_non_goals"])
    assert any("P360 readonly" in item for item in notes["retained_worktree_notes"])
    assert notes["statements"]["db_opened"] is False


def test_portal_html_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    portal = first.portal_html
    assert portal.startswith("<!doctype html>")
    assert "Scope banner:" in portal
    assert "Acceptance Decision" in portal
    assert "Checklist Table" in portal
    assert "Failure Matrix" in portal
    assert "Risk Notes" in portal
    assert "Source Artifact Inventory" in portal
    assert "Local Commands" in portal
    for line in acceptance.DISCLAIMER_LINES:
        assert line in portal
    assert "<script" not in portal.lower()


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == acceptance.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(acceptance.REQUIRED_SOURCE_ARTIFACTS)
    assert len(output_rows) == len(acceptance.P375_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 3
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert all(len(row["source_sha256"]) == 64 for row in source_rows)


def test_cli_generate_decision_checklist_failure_matrix_risk_notes_portal_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_operator_acceptance"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "overall acceptance: PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in acceptance.P375_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    decision_result = subprocess.run([sys.executable, "-m", module, "--decision"], check=True, text=True, capture_output=True)
    assert json.loads(decision_result.stdout)["overall_acceptance"] == "PASS"

    checklist_result = subprocess.run([sys.executable, "-m", module, "--checklist"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(checklist_result.stdout.splitlines()))["status"] == "PASS"

    matrix_result = subprocess.run([sys.executable, "-m", module, "--failure-matrix"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(matrix_result.stdout.splitlines()))["current_count"] == "0"

    notes_result = subprocess.run([sys.executable, "-m", module, "--risk-notes"], check=True, text=True, capture_output=True)
    assert "known_non_goals" in json.loads(notes_result.stdout)

    portal_result = subprocess.run([sys.executable, "-m", module, "--portal"], check=True, text=True, capture_output=True)
    assert portal_result.stdout.startswith("<!doctype html>")

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    assert "--decision" in help_result.stdout
    assert "--checklist" in help_result.stdout
    assert "--failure-matrix" in help_result.stdout
    assert "--risk-notes" in help_result.stdout
    assert "--portal" in help_result.stdout


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert acceptance._artifact_contents(first) == acceptance._artifact_contents(second)
    first_paths = acceptance.write_artifacts(first, tmp_path / "first")
    second_paths = acceptance.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_html_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = acceptance.write_artifacts(first, tmp_path)
    with open(paths["decision"], encoding="utf-8") as handle:
        assert json.load(handle)["overall_acceptance"] == "PASS"
    with open(paths["risk_notes"], encoding="utf-8") as handle:
        assert "technical_risks" in json.load(handle)
    with open(paths["checklist"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == acceptance.CHECKLIST_COLUMNS
    with open(paths["failure_matrix"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == acceptance.FAILURE_MATRIX_COLUMNS
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["portal"].read_text(encoding="utf-8").startswith("<!doctype html>")


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "decision": first.decision,
            "checklist": first.checklist_rows,
            "failure_matrix": first.failure_matrix_rows,
            "risk_notes": first.risk_notes,
            "manifest": first.manifest_rows,
            "portal": first.portal_html,
        },
        sort_keys=True,
    ).lower()
    for line in acceptance.DISCLAIMER_LINES:
        assert line.lower() in text
    assert "no db open/write" in text
    assert "no adapter calls" in text
    assert "no new scoring" in text
    assert "no deploy" in text
    assert "no production registry import" in text
    assert "no betting advice" in text
    assert "no future prediction guarantee" in text
    assert "no blended leaderboard" in text
    assert not [phrase for phrase in acceptance.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = acceptance.run_acceptance()
    assert output.decision["statements"]["db_opened"] is False
    assert output.decision["statements"]["db_written"] is False
    assert output.decision["statements"]["adapter_calls"] is False
    assert "historical_adapters" not in sys.modules
    assert all(row["no_db_open_write"] == "YES" for row in output.manifest_rows)
