import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_command_center_route_replay as replay
from recovered_strategies.biglotto import no_db_evidence_command_center as center


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P372 route replay")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = replay.run_route_replay()
        second = replay.run_route_replay()
    finally:
        patcher.undo()
    return first, second


def test_required_p371_module_and_artifacts_exist():
    paths = replay.verify_p371_evidence()
    assert len(paths) == len(replay.P371_REQUIRED_EVIDENCE)
    assert all(path.is_file() for path in paths)


def test_route_transcripts_json_schema(double_run):
    first, _ = double_run
    transcripts = first.transcripts
    assert transcripts["task"] == replay.TASK
    assert transcripts["source_baseline"] == replay.SOURCE_BASELINE
    assert transcripts["route_count"] == len(center.build_routes())
    assert {row["status"] for row in transcripts["transcripts"]} == {"PASS"}
    for row in transcripts["transcripts"]:
        assert set(row) >= set(replay.TRANSCRIPT_REQUIRED_KEYS)
        assert row["command"].startswith("python3 -m recovered_strategies.biglotto.no_db_evidence_command_center")
        assert row["stdout_excerpt"]
        assert row["normalized_output"]
        assert row["no_db_confirmed"] is True
        assert row["no_adapter_calls_confirmed"] is True
        assert row["no_new_scoring_confirmed"] is True
        assert row["no_deploy_confirmed"] is True


def test_route_health_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.route_health_rows[0]) == replay.ROUTE_HEALTH_COLUMNS
    assert len(first.route_health_rows) == len(center.build_routes())
    assert {row["replay_status"] for row in first.route_health_rows} == {"PASS"}
    assert {row["parse_status"] for row in first.route_health_rows} <= {"PARSED_JSON", "PARSED_CSV"}
    assert {row["safety_status"] for row in first.route_health_rows} == {"PASS"}


def test_route_coverage_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.route_coverage_rows[0]) == replay.ROUTE_COVERAGE_COLUMNS
    row = first.route_coverage_rows[0]
    assert row["total_routes"] == str(len(center.build_routes()))
    assert row["replayed_routes"] == row["total_routes"]
    assert row["skipped_routes"] == "0"
    assert row["fail_count"] == "0"
    assert row["coverage_rate"] == "1.0000"


def test_failure_taxonomy_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.failure_taxonomy_rows[0]) == replay.FAILURE_TAXONOMY_COLUMNS
    assert {row["failure_class"] for row in first.failure_taxonomy_rows} == {
        "missing_artifact",
        "parse_failure",
        "unsafe_route",
        "forbidden_language",
        "db_touch_attempt",
        "adapter_call_attempt",
        "scoring_attempt",
        "deploy_attempt",
    }
    assert {row["no_db_open_write"] for row in first.failure_taxonomy_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.failure_taxonomy_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.failure_taxonomy_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.failure_taxonomy_rows} == {"YES"}


def test_smoke_bundle_json_schema(double_run):
    first, _ = double_run
    bundle = first.smoke_bundle
    assert bundle["task"] == replay.TASK
    assert bundle["source_baseline"] == replay.SOURCE_BASELINE
    assert len(bundle["source_artifacts"]) == len(replay.P371_REQUIRED_EVIDENCE)
    assert bundle["route_health_summary"]["fail_count"] == 0
    assert bundle["transcripts_summary"]["fail_count"] == 0
    assert bundle["statements"]["db_opened"] is False
    assert bundle["statements"]["adapter_calls"] is False
    assert bundle["statements"]["new_scoring"] is False
    assert bundle["statements"]["deployed"] is False
    assert bundle["recommended_safe_next_checks"]


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == replay.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(replay.P371_REQUIRED_EVIDENCE)
    assert len(output_rows) == len(replay.P372_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 3
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.manifest_rows} == {"YES"}
    assert all(len(row["source_sha256"]) == 64 for row in source_rows)
    assert {row["artifact_role"] for row in output_rows} == set(replay.P372_ARTIFACT_BASENAMES)


def test_validation_rows_pass(double_run):
    first, _ = double_run
    assert tuple(first.validation_rows[0]) == replay.VALIDATION_COLUMNS
    assert {row["status"] for row in first.validation_rows} == {"PASS"}
    names = {row["check_name"] for row in first.validation_rows}
    assert "required_p371_module_and_artifacts_exist" in names
    assert "deterministic_double_run_equality" in names
    assert "generated_outputs_do_not_authorize_forbidden_actions" in names


def test_cli_generate_replay_health_coverage_smoke_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_command_center_route_replay"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in replay.P372_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    replay_result = subprocess.run([sys.executable, "-m", module, "--replay-routes"], check=True, text=True, capture_output=True)
    assert json.loads(replay_result.stdout)["route_count"] == len(center.build_routes())

    health_result = subprocess.run([sys.executable, "-m", module, "--health"], check=True, text=True, capture_output=True)
    assert {row["replay_status"] for row in csv.DictReader(health_result.stdout.splitlines())} == {"PASS"}

    coverage_result = subprocess.run([sys.executable, "-m", module, "--coverage"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(coverage_result.stdout.splitlines()))["coverage_rate"] == "1.0000"

    smoke_result = subprocess.run([sys.executable, "-m", module, "--smoke-bundle"], check=True, text=True, capture_output=True)
    assert json.loads(smoke_result.stdout)["route_health_summary"]["fail_count"] == 0

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    assert "--replay-routes" in help_result.stdout


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "transcripts": first.transcripts,
            "route_health": first.route_health_rows,
            "route_coverage": first.route_coverage_rows,
            "failure_taxonomy": first.failure_taxonomy_rows,
            "smoke_bundle": first.smoke_bundle,
            "manifest": first.manifest_rows,
        },
        sort_keys=True,
    ).lower()
    for line in replay.DISCLAIMER_LINES:
        assert line.lower() in text
    assert "no db open/write" in text
    assert "no adapter calls" in text
    assert "no new scoring" in text
    assert "no deploy" in text
    assert not [phrase for phrase in replay.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert replay._artifact_contents(first) == replay._artifact_contents(second)
    first_paths = replay.write_artifacts(first, tmp_path / "first")
    second_paths = replay.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = replay.write_artifacts(first, tmp_path)
    with open(paths["route_transcripts"], encoding="utf-8") as handle:
        assert json.load(handle)["route_count"] == len(center.build_routes())
    with open(paths["smoke_bundle"], encoding="utf-8") as handle:
        assert json.load(handle)["route_health_summary"]["fail_count"] == 0
    with open(paths["route_health"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == replay.ROUTE_HEALTH_COLUMNS
    with open(paths["route_coverage"], newline="", encoding="utf-8") as handle:
        assert next(csv.DictReader(handle))["coverage_rate"] == "1.0000"
    with open(paths["failure_taxonomy"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 8
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = replay.run_route_replay()
    assert output.smoke_bundle["statements"]["db_opened"] is False
    assert output.smoke_bundle["statements"]["db_written"] is False
    assert output.smoke_bundle["statements"]["adapter_calls"] is False
    assert all(row["no_db_open_write"] == "YES" for row in output.manifest_rows)
    assert all(row["no_adapter_calls"] == "YES" for row in output.manifest_rows)
    assert "historical_adapters" not in sys.modules
