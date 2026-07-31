import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_regression_archive_query as query


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P380 regression archive query")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = query.run_query(include_validation=False)
        second = query.run_query(include_validation=False)
    finally:
        patcher.undo()
    return first, second


def test_required_p377_p378_p379_modules_and_artifacts_exist():
    paths = query.verify_required_evidence()
    assert len(paths) == len(query.SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)
    required = set(query.SOURCE_ARTIFACTS.values())
    assert "recovered_strategies/biglotto/no_db_command_center_regression_runner.py" in required
    assert "recovered_strategies/biglotto/no_db_regression_run_archive.py" in required
    assert "recovered_strategies/biglotto/no_db_regression_archive_explorer.py" in required
    assert "artifacts/P377_biglotto_command_center_regression_commands.csv" in required
    assert "artifacts/P378_biglotto_regression_run_archive_command_delta.csv" in required
    assert "artifacts/P379_biglotto_regression_archive_explorer_command_view.csv" in required


def test_query_index_json_schema(double_run):
    first, _ = double_run
    index = first.index
    assert index["task"] == query.TASK
    assert index["source_baseline"]["required_origin_main_merge_commit"] == query.P379_BASELINE_COMMIT
    assert set(index) >= {
        "source_baseline",
        "source_p377_artifact_paths",
        "source_p378_artifact_paths",
        "source_p379_artifact_paths",
        "source_sha256",
        "available_recipes",
        "generated_p380_artifact_paths",
        "path_warnings",
        "statements",
    }
    assert tuple(index["available_recipes"]) == query.RECIPE_IDS
    assert index["counts"]["all_commands"] == 6
    assert index["counts"]["all_deltas"] == 56
    assert all(path.startswith("artifacts/P380_biglotto_regression_archive_query_") for path in index["generated_p380_artifact_paths"].values())
    assert index["statements"]["db_opened"] is False
    assert index["path_warnings"]["p379_previous_worktree"]["policy"].startswith("read-only")


def test_recipes_json_schema(double_run):
    first, _ = double_run
    recipes = first.recipes
    assert recipes["task"] == query.TASK
    assert tuple(recipes["recipe_ids"]) == query.RECIPE_IDS
    assert len(recipes["recipes"]) == len(query.RECIPE_IDS)
    for recipe in recipes["recipes"]:
        assert set(recipe) >= {"recipe_id", "description", "source_artifacts", "output_artifact", "safety_notes"}
        assert recipe["recipe_id"] in query.RECIPE_IDS
        assert recipe["output_artifact"].startswith("artifacts/P380_biglotto_regression_archive_query_")
        assert "No DB open/write." in recipe["safety_notes"]


def test_command_results_csv_schema(double_run):
    first, _ = double_run
    rows = first.command_rows
    assert tuple(rows[0]) == query.COMMAND_RESULT_COLUMNS
    assert len([row for row in rows if row["query_id"] == "all_commands"]) == 6
    assert len([row for row in rows if row["query_id"] == "non_pass_commands"]) == 1
    assert {row["status"] for row in rows if row["query_id"] == "all_commands"} == {"PASS"}
    assert {row["related_delta"] for row in rows if row["query_id"] == "all_commands"} == {"PASS"}
    assert all("python3 -m recovered_strategies.biglotto" in row["command"] for row in rows if row["query_id"] == "all_commands")


def test_artifact_results_csv_schema(double_run):
    first, _ = double_run
    rows = first.artifact_rows
    assert tuple(rows[0]) == query.ARTIFACT_RESULT_COLUMNS
    all_rows = [row for row in rows if row["query_id"] == "all_artifacts"]
    assert len(all_rows) == len(query.SOURCE_ARTIFACTS)
    assert len([row for row in rows if row["query_id"] == "stale_or_missing_artifacts"]) == 1
    assert {row["exists"] for row in all_rows} == {"YES"}
    assert all(len(row["sha256"]) == 64 for row in all_rows)
    assert {"P377", "P378", "P379"} <= {row["source_stage"] for row in all_rows}


def test_delta_results_csv_schema(double_run):
    first, _ = double_run
    rows = first.delta_rows
    assert tuple(rows[0]) == query.DELTA_RESULT_COLUMNS
    all_rows = [row for row in rows if row["query_id"] == "all_deltas"]
    assert len(all_rows) == 56
    assert len([row for row in rows if row["query_id"] == "warn_or_fail_deltas"]) == 1
    assert {row["status"] for row in all_rows} == {"PASS"}
    assert {row["severity"] for row in all_rows} == {"INFO"}
    assert {"command_status", "artifact_freshness"} == {row["delta_type"] for row in all_rows}


def test_query_transcripts_json_schema(double_run):
    first, _ = double_run
    transcripts = first.transcripts
    assert transcripts["task"] == query.TASK
    assert set(transcripts) >= {
        "recipe_transcripts",
        "show_command_example",
        "show_artifact_example",
        "path_warnings",
        "statements",
    }
    assert set(transcripts["recipe_transcripts"]) == set(query.RECIPE_IDS)
    assert transcripts["show_command_example"]["payload"]["found"] is True
    assert transcripts["show_artifact_example"]["payload"]["found"] is True
    assert transcripts["statements"]["adapter_calls"] is False


def test_query_guide_markdown_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    guide = first.guide_markdown
    for section in (
        "## List commands",
        "## List artifacts",
        "## List deltas",
        "## Query by recipe",
        "## Inspect one command",
        "## Inspect one artifact",
        "## Safe caveats",
    ):
        assert section in guide
    for phrase in (
        "Historical descriptive evidence only.",
        "No future prediction guarantee.",
        "No betting advice.",
        "No DB open/write.",
        "No adapter calls.",
        "No new scoring cohort.",
        "No deploy.",
        "Not production release approval.",
    ):
        assert phrase in guide


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == query.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(query.SOURCE_ARTIFACTS)
    assert len(output_rows) == len(query.P380_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 4
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.manifest_rows} == {"YES"}


def test_cli_generate_recipes_lists_query_show_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_regression_archive_query"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in query.P380_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    recipes_result = subprocess.run([sys.executable, "-m", module, "--recipes"], check=True, text=True, capture_output=True)
    assert tuple(json.loads(recipes_result.stdout)["recipe_ids"]) == query.RECIPE_IDS

    commands_result = subprocess.run([sys.executable, "-m", module, "--list-commands"], check=True, text=True, capture_output=True)
    assert len(list(csv.DictReader(commands_result.stdout.splitlines()))) == 6

    artifacts_result = subprocess.run([sys.executable, "-m", module, "--list-artifacts"], check=True, text=True, capture_output=True)
    assert len(list(csv.DictReader(artifacts_result.stdout.splitlines()))) == len(query.SOURCE_ARTIFACTS)

    deltas_result = subprocess.run([sys.executable, "-m", module, "--list-deltas"], check=True, text=True, capture_output=True)
    assert len(list(csv.DictReader(deltas_result.stdout.splitlines()))) == 56

    all_commands = subprocess.run([sys.executable, "-m", module, "--query", "all_commands"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(all_commands.stdout.splitlines()))["query_id"] == "all_commands"

    non_pass = subprocess.run([sys.executable, "-m", module, "--query", "non_pass_commands"], check=True, text=True, capture_output=True)
    assert next(csv.DictReader(non_pass.stdout.splitlines()))["command_id"] == "none"

    show_command = subprocess.run([sys.executable, "-m", module, "--show-command", "P377-CMD-001"], check=True, text=True, capture_output=True)
    assert json.loads(show_command.stdout)["payload" if "payload" in json.loads(show_command.stdout) else "found"] is True

    show_artifact = subprocess.run(
        [sys.executable, "-m", module, "--show-artifact", "artifacts/P379_biglotto_regression_archive_explorer_index.json"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(show_artifact.stdout)["found"] is True

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    for flag in (
        "--generate",
        "--recipes",
        "--list-commands",
        "--list-artifacts",
        "--list-deltas",
        "--query",
        "--show-command",
        "--show-artifact",
        "--validate",
    ):
        assert flag in help_result.stdout


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "index": first.index,
            "recipes": first.recipes,
            "command_rows": first.command_rows,
            "artifact_rows": first.artifact_rows,
            "delta_rows": first.delta_rows,
            "transcripts": first.transcripts,
            "guide": first.guide_markdown,
            "manifest": first.manifest_rows,
        },
        sort_keys=True,
    ).lower()
    for line in query.DISCLAIMER_LINES:
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
    assert not [phrase for phrase in query.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert query._artifact_contents(first) == query._artifact_contents(second)
    first_paths = query.write_artifacts(first, tmp_path / "first")
    second_paths = query.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_markdown_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = query.write_artifacts(first, tmp_path)
    with open(paths["index"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == query.TASK
    with open(paths["recipes"], encoding="utf-8") as handle:
        assert tuple(json.load(handle)["recipe_ids"]) == query.RECIPE_IDS
    with open(paths["transcripts"], encoding="utf-8") as handle:
        assert json.load(handle)["show_command_example"]["payload"]["found"] is True
    with open(paths["command_results"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == query.COMMAND_RESULT_COLUMNS
    with open(paths["artifact_results"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == query.ARTIFACT_RESULT_COLUMNS
    with open(paths["delta_results"], newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.DictReader(handle))) == query.DELTA_RESULT_COLUMNS
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert "## Query by recipe" in paths["guide"].read_text(encoding="utf-8")


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = query.run_query(include_validation=False)
    assert output.index["statements"]["db_opened"] is False
    assert output.index["statements"]["adapter_calls"] is False
    assert "historical_adapters" not in sys.modules
    assert "lottery_api.models.replay_strategy_registry" not in sys.modules


def test_generated_outputs_write_only_p380_prefixed_paths(tmp_path, double_run):
    paths = query.write_artifacts(double_run[0], tmp_path)
    assert set(paths) == set(query.P380_ARTIFACT_BASENAMES)
    assert all(path.name.startswith("P380_biglotto_regression_archive_query_") for path in paths.values())
