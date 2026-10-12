import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_agent_pack as pack


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P369 evidence agent pack")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = pack.run_agent_pack()
        second = pack.run_agent_pack()
    finally:
        patcher.undo()
    return first, second


def test_required_p367_p368_artifacts_exist():
    paths = pack.verify_required_artifacts()
    assert len(paths) == len(pack.REQUIRED_SOURCE_FILES)
    assert all(path.is_file() for path in paths)


def test_summary_json_schema(double_run):
    first, _ = double_run
    summary = first.summary
    assert summary["task"] == pack.TASK
    assert summary["generated_at"] == pack.GENERATED_AT
    assert summary["source_merge_baseline"] == pack.SOURCE_MERGE_BASELINE
    assert summary["statements"]["db_opened"] is False
    assert summary["api_facade_availability"]["available"] is True
    assert summary["snapshot_compatibility_status"]["compatible"] is True
    assert len(summary["source_artifacts"]) == len(pack.REQUIRED_SOURCE_FILES)
    assert all(len(row["sha256"]) == 64 for row in summary["source_artifacts"])


def test_task_prompts_json_schema(double_run):
    first, _ = double_run
    prompts = first.task_prompts
    assert prompts["task"] == pack.TASK
    assert len(prompts["prompts"]) == 5
    ids = {row["prompt_id"] for row in prompts["prompts"]}
    assert ids == {
        "read_only_api_exploration",
        "no_db_artifact_audit",
        "no_db_dashboard_smoke_check",
        "no_db_compatibility_revalidation",
        "no_db_cli_usage_examples",
    }


def test_query_recipes_json_schema(double_run):
    first, _ = double_run
    recipes = first.query_recipes
    assert recipes["task"] == pack.TASK
    assert len(recipes["recipes"]) == 6
    ids = {row["recipe_id"] for row in recipes["recipes"]}
    assert ids == {
        "list_adapters",
        "inspect_one_adapter",
        "list_compact_shortlist",
        "compare_two_adapters",
        "validate_evidence_stack",
        "inspect_snapshot_compatibility",
    }


def test_validation_checklist_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.validation_rows[0]) == pack.VALIDATION_COLUMNS
    assert {row["status"] for row in first.validation_rows} == {"PASS"}
    names = {row["check_name"] for row in first.validation_rows}
    assert "required_p367_p368_files_exist" in names
    assert "p367_api_validation_has_no_failures" in names
    assert "p368_compatibility_matrix_has_no_fail_rows" in names
    assert "p368_contract_drift_has_no_fail_rows" in names
    assert "generated_prompts_contain_required_constraints" in names
    assert "generated_prompts_do_not_authorize_forbidden_actions" in names


def test_examples_markdown_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    markdown = first.examples_md
    assert "## Local CLI commands" in markdown
    assert "## Safe copy/paste task examples" in markdown
    assert "## Expected output summaries" in markdown
    assert "## Disclaimers" in markdown
    for line in pack.DISCLAIMER_LINES:
        assert line in markdown


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == pack.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(pack.REQUIRED_SOURCE_FILES)
    assert len(output_rows) == len(pack.P369_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 2
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert all(len(row["source_sha256"]) == 64 for row in source_rows)


def test_generated_prompts_include_required_constraints(double_run):
    first, _ = double_run
    for prompt in first.task_prompts["prompts"]:
        for phrase in pack.PROMPT_REQUIRED_PHRASES:
            assert phrase in prompt["prompt"]


def test_generated_prompts_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "summary": first.summary,
            "prompts": first.task_prompts,
            "recipes": first.query_recipes,
            "examples": first.examples_md,
        },
        sort_keys=True,
    ).lower()
    assert not [phrase for phrase in pack.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_cli_generate_help_validate_commands_work(tmp_path):
    generate_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_agent_pack",
            "--artifacts-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "No DB was opened or written; no adapters were called; no new scoring cohort was created" in generate_result.stdout
    for basename in pack.P369_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    help_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_agent_pack", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "usage:" in help_result.stdout

    validate_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_agent_pack", "--validate"],
        check=True,
        text=True,
        capture_output=True,
    )
    rows = list(csv.DictReader(validate_result.stdout.splitlines()))
    assert rows
    assert {row["status"] for row in rows} == {"PASS"}


def test_cli_emit_commands_work():
    for flag, parser in (
        ("--emit-summary", json.loads),
        ("--task-prompts", json.loads),
        ("--query-recipes", json.loads),
    ):
        result = subprocess.run(
            [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_agent_pack", flag],
            check=True,
            text=True,
            capture_output=True,
        )
        assert parser(result.stdout)["task"] == pack.TASK

    handoff_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_agent_pack", "--print-handoff"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "P369 Big Lotto no-DB evidence agent handoff" in handoff_result.stdout
    assert "No DB open/write." in handoff_result.stdout


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert pack._artifact_contents(first) == pack._artifact_contents(second)
    first_paths = pack.write_artifacts(first, tmp_path / "first")
    second_paths = pack.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_markdown_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = pack.write_artifacts(first, tmp_path)
    with open(paths["summary"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == pack.TASK
    with open(paths["task_prompts"], encoding="utf-8") as handle:
        assert len(json.load(handle)["prompts"]) == 5
    with open(paths["query_recipes"], encoding="utf-8") as handle:
        assert len(json.load(handle)["recipes"]) == 6
    with open(paths["validation_checklist"], newline="", encoding="utf-8") as handle:
        assert {row["status"] for row in csv.DictReader(handle)} == {"PASS"}
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["examples"].read_text(encoding="utf-8").startswith("# P369 Big Lotto no-DB evidence agent pack examples")


def test_no_db_import_open_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = pack.run_agent_pack()
    assert output.summary["statements"]["db_opened"] is False
    assert all(row["no_db_open_write"] == "YES" for row in output.manifest_rows)


def test_no_adapter_execution_guard_if_practical(double_run):
    first, _ = double_run
    assert first.summary["statements"]["adapter_calls"] is False
    assert all(row["no_adapter_calls"] == "YES" for row in first.manifest_rows)
    assert "historical_adapters" not in sys.modules
