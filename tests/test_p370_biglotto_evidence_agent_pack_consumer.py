import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_agent_pack_consumer as consumer


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P370 agent pack consumer")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = consumer.run_consumer()
        second = consumer.run_consumer()
    finally:
        patcher.undo()
    return first, second


def test_required_p367_p368_p369_artifacts_exist():
    paths = consumer.verify_required_artifacts()
    assert len(paths) == len(consumer.REQUIRED_SOURCE_FILES)
    assert all(path.is_file() for path in paths)


def test_transcripts_json_schema(double_run):
    first, _ = double_run
    transcripts = first.transcripts
    assert transcripts["task"] == consumer.TASK
    assert transcripts["generated_at"] == consumer.GENERATED_AT
    assert transcripts["source_merge_baseline"] == consumer.SOURCE_MERGE_BASELINE
    assert transcripts["statements"]["db_opened"] is False
    assert len(transcripts["transcripts"]) == 6
    ids = {row["transcript_id"] for row in transcripts["transcripts"]}
    assert ids == {
        "list_adapters",
        "inspect_one_adapter",
        "list_compact_shortlist",
        "compare_two_adapters",
        "validate_evidence_stack",
        "inspect_snapshot_compatibility",
    }
    for row in transcripts["transcripts"]:
        assert row["no_db_confirmed"] is True
        assert row["no_adapter_calls_confirmed"] is True
        assert row["no_new_scoring_confirmed"] is True
        assert tuple(message["role"] for message in row["messages"]) == ("user", "assistant")


def test_recipe_results_csv_schema(double_run):
    first, _ = double_run
    rows = first.recipe_rows
    assert len(rows) == 6
    assert tuple(rows[0]) == consumer.RECIPE_RESULT_COLUMNS
    assert {row["status"] for row in rows} == {"PASS"}
    assert {row["no_db_confirmed"] for row in rows} == {"YES"}
    assert {row["no_adapter_calls_confirmed"] for row in rows} == {"YES"}
    assert {row["no_new_scoring_confirmed"] for row in rows} == {"YES"}


def test_prompt_safety_audit_csv_schema(double_run):
    first, _ = double_run
    rows = first.prompt_safety_rows
    assert len(rows) == 10
    assert tuple(rows[0]) == consumer.PROMPT_SAFETY_COLUMNS
    assert {row["status"] for row in rows} == {"PASS"}
    for row in rows:
        assert row["contains_no_db_constraint"] == "YES"
        assert row["contains_no_adapter_calls_constraint"] == "YES"
        assert row["contains_no_new_scoring_constraint"] == "YES"
        assert row["contains_no_deploy_constraint"] == "YES"
        assert row["contains_no_betting_advice_constraint"] == "YES"
        assert row["contains_no_future_prediction_constraint"] == "YES"
        assert row["does_not_grant_standing_authorization"] == "YES"
        assert row["forbidden_authorization_absent"] == "YES"


def test_task_cards_json_schema(double_run):
    first, _ = double_run
    cards = first.task_cards
    assert cards["task"] == consumer.TASK
    assert len(cards["task_cards"]) == 5
    ids = {row["card_id"] for row in cards["task_cards"]}
    assert ids == {
        "read_only_api_exploration",
        "artifact_inventory_audit",
        "compatibility_revalidation",
        "dashboard_explorer_smoke_check",
        "local_evidence_query_examples",
    }
    for card in cards["task_cards"]:
        assert card["template_not_standing_authorization"] is True
        assert "not standing authorization" in card["copy_paste_prompt"].lower()


def test_examples_markdown_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    markdown = first.examples_md
    assert "## Local CLI commands" in markdown
    assert "## Safe copy/paste snippets" in markdown
    assert "## Expected deterministic summaries" in markdown
    assert "## Disclaimers" in markdown
    for line in consumer.DISCLAIMER_LINES:
        assert line in markdown


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == consumer.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(consumer.REQUIRED_SOURCE_FILES)
    assert len(output_rows) == len(consumer.P370_ARTIFACT_BASENAMES)
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
    for card in first.task_cards["task_cards"]:
        prompt = card["copy_paste_prompt"]
        for phrase in consumer.PROMPT_REQUIRED_PHRASES:
            assert phrase in prompt


def test_generated_prompts_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "transcripts": first.transcripts,
            "task_cards": first.task_cards,
            "prompt_safety_rows": first.prompt_safety_rows,
            "examples": first.examples_md,
        },
        sort_keys=True,
    ).lower()
    assert not [phrase for phrase in consumer.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_generated_prompts_state_template_not_standing_authorization(double_run):
    first, _ = double_run
    for card in first.task_cards["task_cards"]:
        assert "template" in card["copy_paste_prompt"].lower()
        assert "not standing authorization" in card["copy_paste_prompt"].lower()


def test_cli_generate_help_validate_commands_work(tmp_path):
    generate_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer",
            "--artifacts-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "No DB was opened or written; no adapters were called; no new scoring cohort was created" in generate_result.stdout
    assert "Generated prompts are templates, not standing authorization" in generate_result.stdout
    for basename in consumer.P370_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    help_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "usage:" in help_result.stdout

    validate_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer", "--validate"],
        check=True,
        text=True,
        capture_output=True,
    )
    rows = list(csv.DictReader(validate_result.stdout.splitlines()))
    assert rows
    assert {row["status"] for row in rows} == {"PASS"}


def test_cli_emit_commands_work():
    for flag, parser, expected_task in (
        ("--transcripts", json.loads, consumer.TASK),
        ("--task-cards", json.loads, consumer.TASK),
    ):
        result = subprocess.run(
            [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer", flag],
            check=True,
            text=True,
            capture_output=True,
        )
        assert parser(result.stdout)["task"] == expected_task

    recipes_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer", "--run-recipes"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert list(csv.DictReader(recipes_result.stdout.splitlines()))

    audit_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_agent_pack_consumer", "--prompt-safety-audit"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert {row["status"] for row in csv.DictReader(audit_result.stdout.splitlines())} == {"PASS"}


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert consumer._artifact_contents(first) == consumer._artifact_contents(second)
    first_paths = consumer.write_artifacts(first, tmp_path / "first")
    second_paths = consumer.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_markdown_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = consumer.write_artifacts(first, tmp_path)
    with open(paths["transcripts"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == consumer.TASK
    with open(paths["task_cards"], encoding="utf-8") as handle:
        assert len(json.load(handle)["task_cards"]) == 5
    with open(paths["recipe_results"], newline="", encoding="utf-8") as handle:
        assert {row["status"] for row in csv.DictReader(handle)} == {"PASS"}
    with open(paths["prompt_safety_audit"], newline="", encoding="utf-8") as handle:
        assert {row["status"] for row in csv.DictReader(handle)} == {"PASS"}
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["examples"].read_text(encoding="utf-8").startswith("# P370 Big Lotto no-DB agent pack consumer examples")


def test_no_db_import_open_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = consumer.run_consumer()
    assert output.transcripts["statements"]["db_opened"] is False
    assert all(row["no_db_open_write"] == "YES" for row in output.manifest_rows)


def test_no_adapter_execution_guard_if_practical(double_run):
    first, _ = double_run
    assert first.transcripts["statements"]["adapter_calls"] is False
    assert all(row["no_adapter_calls"] == "YES" for row in first.manifest_rows)
    assert "historical_adapters" not in sys.modules
