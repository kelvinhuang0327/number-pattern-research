import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_regression_archive_answer_kit as kit


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P381 regression archive answer kit")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = kit.run_answer_kit(include_validation=False)
        second = kit.run_answer_kit(include_validation=False)
    finally:
        patcher.undo()
    return first, second


def test_required_p377_p378_p379_p380_modules_and_artifacts_exist():
    paths = kit.verify_required_evidence()
    assert len(paths) == len(kit.SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)
    required = set(kit.SOURCE_ARTIFACTS.values())
    assert "recovered_strategies/biglotto/no_db_command_center_regression_runner.py" in required
    assert "recovered_strategies/biglotto/no_db_regression_run_archive.py" in required
    assert "recovered_strategies/biglotto/no_db_regression_archive_explorer.py" in required
    assert "recovered_strategies/biglotto/no_db_regression_archive_query.py" in required
    assert "artifacts/P380_biglotto_regression_archive_query_index.json" in required


def test_answer_kit_index_json_schema(double_run):
    first, _ = double_run
    index = first.index
    assert index["task"] == kit.TASK
    assert index["source_baseline"]["required_origin_main_merge_commit"] == kit.P380_BASELINE_COMMIT
    assert set(index) >= {
        "source_baseline",
        "source_p377_artifact_paths",
        "source_p378_artifact_paths",
        "source_p379_artifact_paths",
        "source_p380_artifact_paths",
        "source_sha256",
        "generated_p381_artifact_paths",
        "available_answer_ids",
        "path_warnings",
        "statements",
    }
    assert tuple(index["available_answer_ids"]) == kit.ANSWER_IDS
    assert all(path.startswith("artifacts/P381_biglotto_regression_archive_answer_kit_") for path in index["generated_p381_artifact_paths"].values())
    assert index["path_warnings"]["p379_previous_worktree"]["policy"].startswith("read-only")
    assert index["statements"]["db_opened"] is False
    assert index["statements"]["adapter_calls"] is False


def test_answer_cards_json_schema(double_run):
    first, _ = double_run
    cards = first.answer_cards
    assert cards["task"] == kit.TASK
    assert tuple(cards["answer_ids"]) == kit.ANSWER_IDS
    assert len(cards["cards"]) == len(kit.ANSWER_IDS)
    for card in cards["cards"]:
        assert set(card) >= {"answer_id", "title", "audience", "summary", "evidence_artifacts", "caveats", "copy_paste_text"}
        assert card["answer_id"] in kit.ANSWER_IDS
        assert card["evidence_artifacts"]
        assert "Historical descriptive evidence only." in card["caveats"]
        assert "No betting advice." in card["caveats"] or card["answer_id"] == "protected_worktree_warnings"
        assert "No DB" in card["copy_paste_text"] or card["answer_id"] not in {"safety_status", "safe_next_actions"}


def test_status_block_markdown_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    status_block = first.status_block_markdown
    for section in ("## Overall", "## Evidence Flags", "## Path Warnings", "## Safe Next Actions", "## Safety Boundary"):
        assert section in status_block
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
        assert phrase in status_block


def test_briefings_json_schema(double_run):
    first, _ = double_run
    briefings = first.briefings
    assert briefings["task"] == kit.TASK
    assert set(briefings["briefings"]) == {
        "cto_briefing_draft",
        "ceo_briefing_draft",
        "worker_handoff_draft",
        "planner_note",
    }
    for briefing in briefings["briefings"].values():
        assert set(briefing) >= {"audience", "text"}
        assert "betting advice" in briefing["text"].lower() or briefing["audience"] in {"CTO", "Worker"}
        assert "production release approval" in briefing["text"].lower() or briefing["audience"] in {"CTO", "Worker"}


def test_lookup_transcripts_json_schema(double_run):
    first, _ = double_run
    transcripts = first.lookup_transcripts
    assert transcripts["task"] == kit.TASK
    assert set(transcripts["lookup_transcripts"]) == set(kit.LOOKUP_TRANSCRIPT_IDS)
    for answer_id, transcript in transcripts["lookup_transcripts"].items():
        assert transcript["answer_id"] == answer_id
        assert transcript["command"].endswith(f"--answer {answer_id}")
        assert transcript["stdout"]
        assert transcript["evidence_artifacts"]


def test_html_portal_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    portal = first.portal_html
    for section in (
        "Scope banner",
        "Answer Cards",
        "Status Block",
        "Briefing Snippets",
        "Source Artifact Inventory",
        "Local Commands",
        "Safety Disclaimers",
    ):
        assert section in portal
    for phrase in (
        "No DB open/write.",
        "No adapter calls.",
        "No new scoring.",
        "No deploy.",
        "No betting advice.",
        "No future prediction guarantee.",
        "Not production release approval.",
    ):
        assert phrase in portal


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == kit.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(kit.SOURCE_ARTIFACTS)
    assert len(output_rows) == len(kit.P381_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 4
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_deploy"] for row in first.manifest_rows} == {"YES"}


def test_cli_generate_answers_status_block_briefings_lookup_portal_answer_validate_help_work(tmp_path):
    module = "recovered_strategies.biglotto.no_db_regression_archive_answer_kit"
    generate_result = subprocess.run(
        [sys.executable, "-m", module, "--generate", "--artifacts-dir", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "No DB was opened or written" in generate_result.stdout
    for basename in kit.P381_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    answers_result = subprocess.run([sys.executable, "-m", module, "--answers"], check=True, text=True, capture_output=True)
    assert tuple(json.loads(answers_result.stdout)["answer_ids"]) == kit.ANSWER_IDS

    status_result = subprocess.run([sys.executable, "-m", module, "--status-block"], check=True, text=True, capture_output=True)
    assert "## Safety Boundary" in status_result.stdout

    briefings_result = subprocess.run([sys.executable, "-m", module, "--briefings"], check=True, text=True, capture_output=True)
    assert "cto_briefing_draft" in json.loads(briefings_result.stdout)["briefings"]

    lookup_result = subprocess.run([sys.executable, "-m", module, "--lookup-transcripts"], check=True, text=True, capture_output=True)
    assert set(json.loads(lookup_result.stdout)["lookup_transcripts"]) == set(kit.LOOKUP_TRANSCRIPT_IDS)

    portal_result = subprocess.run([sys.executable, "-m", module, "--portal"], check=True, text=True, capture_output=True)
    assert "<!doctype html>" in portal_result.stdout
    assert "Local Commands" in portal_result.stdout

    answer_result = subprocess.run([sys.executable, "-m", module, "--answer", "overall_status"], check=True, text=True, capture_output=True)
    assert not answer_result.stdout.lstrip().startswith("{")
    assert "historical descriptive evidence" in answer_result.stdout.lower()

    safe_next = subprocess.run([sys.executable, "-m", module, "--answer", "safe_next_actions"], check=True, text=True, capture_output=True)
    assert "Safe next action answer" in safe_next.stdout

    validate_result = subprocess.run([sys.executable, "-m", module, "--validate"], check=True, text=True, capture_output=True)
    assert {row["status"] for row in csv.DictReader(validate_result.stdout.splitlines())} == {"PASS"}

    help_result = subprocess.run([sys.executable, "-m", module, "--help"], check=True, text=True, capture_output=True)
    assert "usage:" in help_result.stdout
    for flag in (
        "--generate",
        "--answers",
        "--status-block",
        "--briefings",
        "--lookup-transcripts",
        "--portal",
        "--answer",
        "--validate",
    ):
        assert flag in help_result.stdout


def test_generated_outputs_include_constraints_and_do_not_authorize_forbidden_actions(double_run):
    first, _ = double_run
    text = json.dumps(
        {
            "index": first.index,
            "answer_cards": first.answer_cards,
            "status_block": first.status_block_markdown,
            "briefings": first.briefings,
            "lookup_transcripts": first.lookup_transcripts,
            "portal": first.portal_html,
            "manifest": first.manifest_rows,
        },
        sort_keys=True,
    ).lower()
    for line in kit.DISCLAIMER_LINES:
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
    assert not [phrase for phrase in kit.FORBIDDEN_AUTHORIZATION_PHRASES if phrase in text]


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert kit._artifact_contents(first) == kit._artifact_contents(second)
    first_paths = kit.write_artifacts(first, tmp_path / "first")
    second_paths = kit.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_markdown_html_csv_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = kit.write_artifacts(first, tmp_path)
    with open(paths["index"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == kit.TASK
    with open(paths["answer_cards"], encoding="utf-8") as handle:
        assert tuple(json.load(handle)["answer_ids"]) == kit.ANSWER_IDS
    with open(paths["briefings"], encoding="utf-8") as handle:
        assert "ceo_briefing_draft" in json.load(handle)["briefings"]
    with open(paths["lookup_transcripts"], encoding="utf-8") as handle:
        assert "safe_next_actions" in json.load(handle)["lookup_transcripts"]
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert "## Safety Boundary" in paths["status_block"].read_text(encoding="utf-8")
    assert "Source Artifact Inventory" in paths["portal"].read_text(encoding="utf-8")


def test_no_db_import_open_and_no_adapter_execution_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = kit.run_answer_kit(include_validation=False)
    assert output.index["statements"]["db_opened"] is False
    assert output.index["statements"]["adapter_calls"] is False
    assert "historical_adapters" not in sys.modules
    assert "lottery_api.models.replay_strategy_registry" not in sys.modules


def test_p381_generation_does_not_modify_p371_p380_artifacts(tmp_path, double_run):
    before = {relpath: kit.sha256_file(kit.REPO_ROOT / relpath) for relpath in kit.SOURCE_ARTIFACTS.values()}
    kit.write_artifacts(double_run[0], tmp_path)
    after = {relpath: kit.sha256_file(kit.REPO_ROOT / relpath) for relpath in kit.SOURCE_ARTIFACTS.values()}
    assert before == after


def test_generated_outputs_write_only_p381_prefixed_paths(tmp_path, double_run):
    paths = kit.write_artifacts(double_run[0], tmp_path)
    assert set(paths) == set(kit.P381_ARTIFACT_BASENAMES)
    assert all(path.name.startswith("P381_biglotto_regression_archive_answer_kit_") for path in paths.values())
