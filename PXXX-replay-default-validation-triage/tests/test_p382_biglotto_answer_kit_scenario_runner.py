import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_answer_kit_scenario_runner as runner


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P382 answer kit scenario runner")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = runner.run_scenario_runner(include_validation=False)
        second = runner.run_scenario_runner(include_validation=False)
    finally:
        patcher.undo()
    return first, second


def test_required_p380_p381_modules_and_artifacts_exist():
    paths = runner.verify_required_evidence()
    assert len(paths) == len(runner.SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)
    required = set(runner.SOURCE_ARTIFACTS.values())
    assert "recovered_strategies/biglotto/no_db_regression_archive_query.py" in required
    assert "recovered_strategies/biglotto/no_db_regression_archive_answer_kit.py" in required
    assert "artifacts/P380_biglotto_regression_archive_query_index.json" in required
    assert "artifacts/P381_biglotto_regression_archive_answer_kit_answer_cards.json" in required


def test_scenario_runner_index_json_schema(double_run):
    first, _ = double_run
    index = first.index
    assert index["task"] == runner.TASK
    assert index["source_baseline"]["required_origin_main_merge_commit"] == runner.P381_BASELINE_COMMIT
    assert set(index) >= {
        "source_baseline",
        "source_p380_artifact_paths",
        "source_p381_artifact_paths",
        "source_sha256",
        "generated_p382_artifact_paths",
        "available_scenario_ids",
        "path_warnings",
        "statements",
    }
    assert tuple(index["available_scenario_ids"]) == runner.SCENARIO_IDS
    assert all(path.startswith("artifacts/P382_biglotto_answer_kit_scenario_runner_") for path in index["generated_p382_artifact_paths"].values())
    assert index["path_warnings"]["p379_previous_worktree"]["policy"].startswith("read-only")
    assert index["statements"]["db_opened"] is False
    assert index["statements"]["adapter_calls"] is False


def test_scenarios_json_schema(double_run):
    first, _ = double_run
    scenarios = first.scenarios
    assert scenarios["task"] == runner.TASK
    assert tuple(scenarios["scenario_ids"]) == runner.SCENARIO_IDS
    assert len(scenarios["scenarios"]) == len(runner.SCENARIO_IDS)
    for scenario in scenarios["scenarios"]:
        assert set(scenario) >= {"scenario_id", "audience", "prompt", "required_answer_type", "selected_answer_ids", "intent"}
        assert scenario["scenario_id"] in runner.SCENARIO_IDS
        assert scenario["selected_answer_ids"]


def test_transcripts_json_schema(double_run):
    first, _ = double_run
    transcripts = first.transcripts
    assert transcripts["task"] == runner.TASK
    assert set(transcripts["scenario_transcripts"]) == set(runner.SCENARIO_IDS)
    for scenario_id, transcript in transcripts["scenario_transcripts"].items():
        assert transcript["scenario_id"] == scenario_id
        assert set(transcript) >= {
            "scenario_id",
            "prompt",
            "selected_answer_ids",
            "answer_summary",
            "evidence_artifacts",
            "caveats",
            "no_db_confirmed",
            "no_adapter_calls_confirmed",
            "no_new_scoring_confirmed",
            "no_deploy_confirmed",
        }
        assert transcript["answer_summary"]
        assert transcript["evidence_artifacts"]
        assert transcript["no_db_confirmed"] is True
        assert transcript["no_adapter_calls_confirmed"] is True
        assert transcript["no_new_scoring_confirmed"] is True
        assert transcript["no_deploy_confirmed"] is True


def test_coverage_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.coverage_rows[0]) == runner.COVERAGE_COLUMNS
    assert len(first.coverage_rows) == len(runner.SCENARIO_IDS)
    assert {row["coverage_status"] for row in first.coverage_rows} == {"PASS"}
    assert {row["scenario_id"] for row in first.coverage_rows} == set(runner.SCENARIO_IDS)


def test_missing_answer_matrix_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.missing_answer_rows[0]) == runner.MISSING_ANSWER_COLUMNS
    assert first.missing_answer_rows == (
        {
            "gap_id": "none",
            "scenario_id": "none",
            "missing_answer_type": "none",
            "severity": "none",
            "blocking": "NO",
            "suggested_followup": "No missing or weak answer coverage found for required P382 scenarios.",
        },
    )


def test_qa_report_markdown_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    report = first.qa_report_markdown
    for section in (
        "## Scenario Coverage Summary",
        "## Missing-Answer Summary",
        "## Recommended Safe Next Action",
        "## CTO / CEO Answer Readiness",
        "## Protected Worktree Warning Status",
        "## Safety Boundary",
    ):
        assert section in report
    for phrase in (
        "Historical descriptive evidence only.",
        "No future prediction guarantee.",
        "No betting advice.",
        "No DB open/write.",
        "No adapter calls.",
        "No new scoring cohort.",
        "No production registry import.",
        "No deploy.",
        "Not production release approval.",
    ):
        assert phrase in report


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == runner.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(runner.SOURCE_ARTIFACTS)
    assert len(output_rows) == len(runner.P382_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 4
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.manifest_rows} == {"YES"}


def test_cli_generate_scenarios_transcripts_coverage_missing_qa_scenario_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_answer_kit_scenario_runner"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in runner.P382_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    scenarios_result = subprocess.run([sys.executable, "-m", module, "--scenarios"], check=True, text=True, capture_output=True)
    assert tuple(json.loads(scenarios_result.stdout)["scenario_ids"]) == runner.SCENARIO_IDS

    transcripts_result = subprocess.run([sys.executable, "-m", module, "--transcripts"], check=True, text=True, capture_output=True)
    assert set(json.loads(transcripts_result.stdout)["scenario_transcripts"]) == set(runner.SCENARIO_IDS)

    coverage_result = subprocess.run([sys.executable, "-m", module, "--coverage"], check=True, text=True, capture_output=True)
    assert {row["coverage_status"] for row in csv.DictReader(coverage_result.stdout.splitlines())} == {"PASS"}

    missing_result = subprocess.run([sys.executable, "-m", module, "--missing-answers"], check=True, text=True, capture_output=True)
    assert list(csv.DictReader(missing_result.stdout.splitlines()))[0]["gap_id"] == "none"

    qa_result = subprocess.run([sys.executable, "-m", module, "--qa-report"], check=True, text=True, capture_output=True)
    assert "## Safety Boundary" in qa_result.stdout

    scenario_result = subprocess.run([sys.executable, "-m", module, "--scenario", "overall_status"], check=True, text=True, capture_output=True)
    assert json.loads(scenario_result.stdout)["scenario_id"] == "overall_status"

    safe_next = subprocess.run([sys.executable, "-m", module, "--scenario", "safe_next_actions"], check=True, text=True, capture_output=True)
    assert json.loads(safe_next.stdout)["scenario_id"] == "safe_next_actions"

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    for flag in (
        "--generate",
        "--scenarios",
        "--transcripts",
        "--coverage",
        "--missing-answers",
        "--qa-report",
        "--scenario",
        "--validate",
    ):
        assert flag in help_result.stdout


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "index": first.index,
            "scenarios": first.scenarios,
            "transcripts": first.transcripts,
            "coverage": first.coverage_rows,
            "missing_answers": first.missing_answer_rows,
            "qa_report": first.qa_report_markdown,
            "manifest": first.manifest_rows,
        },
        sort_keys=True,
    ).lower()
    for line in runner.DISCLAIMER_LINES:
        assert line.lower() in text
    for phrase in (
        "no db open/write",
        "no adapter calls",
        "no new scoring",
        "no deploy",
        "no production registry import",
        "no betting advice",
        "no future prediction guarantee",
        "no blended leaderboard",
        "not production release approval",
    ):
        assert phrase in text
    assert not [phrase for phrase in runner.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert runner._artifact_contents(first) == runner._artifact_contents(second)
    first_paths = runner.write_artifacts(first, tmp_path / "first")
    second_paths = runner.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_markdown_csv_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = runner.write_artifacts(first, tmp_path)
    with open(paths["index"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == runner.TASK
    with open(paths["scenarios"], encoding="utf-8") as handle:
        assert tuple(json.load(handle)["scenario_ids"]) == runner.SCENARIO_IDS
    with open(paths["transcripts"], encoding="utf-8") as handle:
        assert "safe_next_actions" in json.load(handle)["scenario_transcripts"]
    with open(paths["coverage"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.coverage_rows)
    with open(paths["missing_answers"], newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle))[0]["gap_id"] == "none"
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert "## Safety Boundary" in paths["qa_report"].read_text(encoding="utf-8")


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = runner.run_scenario_runner(include_validation=False)
    assert output.index["statements"]["db_opened"] is False
    assert output.index["statements"]["adapter_calls"] is False
    assert "historical_adapters" not in sys.modules
    assert "lottery_api.models.replay_strategy_registry" not in sys.modules


def test_p382_generation_does_not_modify_p371_p381_artifacts(tmp_path, double_run):
    before = {relpath: runner.sha256_file(runner.REPO_ROOT / relpath) for relpath in runner.SOURCE_ARTIFACTS.values()}
    runner.write_artifacts(double_run[0], tmp_path)
    after = {relpath: runner.sha256_file(runner.REPO_ROOT / relpath) for relpath in runner.SOURCE_ARTIFACTS.values()}
    assert before == after


def test_generated_outputs_write_only_p382_prefixed_paths(tmp_path, double_run):
    paths = runner.write_artifacts(double_run[0], tmp_path)
    assert set(paths) == set(runner.P382_ARTIFACT_BASENAMES)
    assert all(path.name.startswith("P382_biglotto_answer_kit_scenario_runner_") for path in paths.values())
