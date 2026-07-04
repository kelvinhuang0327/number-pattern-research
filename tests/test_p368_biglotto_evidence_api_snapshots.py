import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_api_snapshots as snapshots


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P368 evidence API snapshots")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = snapshots.run_snapshots()
        second = snapshots.run_snapshots()
    finally:
        patcher.undo()
    return first, second


def test_required_p366_p367_artifacts_exist():
    paths = snapshots.verify_required_artifacts()
    assert len(paths) >= len(snapshots.REQUIRED_P367_ARTIFACTS) + len(snapshots.REQUIRED_P366_ARTIFACTS)
    assert all(path.is_file() for path in paths)


def test_golden_snapshots_json_schema(double_run):
    first, _ = double_run
    golden = first.golden_snapshots
    assert golden["task"] == snapshots.TASK
    assert golden["generated_at"] == snapshots.GENERATED_AT
    assert golden["statements"]["db_opened"] is False
    assert set(golden["snapshots"]) == {
        "list_adapters",
        "one_known_adapter_detail",
        "list_subsets_subset_size_2",
        "one_known_subset_detail",
        "one_known_pairwise_comparison",
        "compact_shortlist",
        "validation_summary",
    }


def test_compatibility_matrix_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.compatibility_rows[0]) == snapshots.COMPATIBILITY_COLUMNS
    assert len(first.compatibility_rows) == 9
    assert {row["compatible"] for row in first.compatibility_rows} == {"TRUE"}
    by_name = {row["api_function_name"]: row for row in first.compatibility_rows}
    assert by_name["get_adapter"]["expected_input_args"] == "adapter_function"
    assert "adapter_function" in by_name["get_adapter"]["current_output_schema_keys"]


def test_contract_drift_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.contract_drift_rows[0]) == snapshots.CONTRACT_DRIFT_COLUMNS
    assert first.contract_drift_rows
    assert {row["status"] for row in first.contract_drift_rows} == {"PASS"}
    names = {row["contract_item"] for row in first.contract_drift_rows}
    assert "supported_function_names" in names
    assert "artifact_sources.path_sha256_pairs" in names


def test_cli_transcripts_json_schema(double_run):
    first, _ = double_run
    transcripts = first.cli_transcripts
    assert transcripts["task"] == snapshots.TASK
    assert set(transcripts["transcripts"]) == {
        "help",
        "list_adapters",
        "list_subsets_subset_size_2",
        "compact_shortlist",
        "validate",
    }
    for transcript in transcripts["transcripts"].values():
        assert transcript["exit_code"] == 0
        assert transcript["command"].startswith("python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots")


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == snapshots.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(snapshots.REQUIRED_P367_ARTIFACTS) + len(snapshots.REQUIRED_P366_ARTIFACTS) + len(snapshots.REQUIRED_SOURCE_FILES)
    assert len(output_rows) == len(snapshots.P368_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 2
    by_output_role = {row["artifact_role"]: row for row in output_rows}
    assert by_output_role["manifest"]["source_sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"
    assert by_output_role["manifest"]["output_row_count"] == str(len(first.manifest_rows))
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert all(len(row["source_sha256"]) == 64 for row in source_rows)


def test_readme_contains_scope_statements(double_run):
    first, _ = double_run
    readme = first.readme_md
    assert "python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --validate" in readme
    for line in snapshots.DISCLAIMER_LINES:
        assert line in readme
    assert "does not import production registries, deploy, call adapters, open a DB, or write a DB" in readme


def test_known_golden_snapshot_values_are_stable(double_run):
    first, _ = double_run
    snap = first.golden_snapshots["snapshots"]
    assert snap["list_adapters"][0] == snapshots.KNOWN_ADAPTER
    assert snap["one_known_adapter_detail"]["adapter_function"] == snapshots.KNOWN_ADAPTER
    assert snap["one_known_subset_detail"]["adapter_subset"] == snapshots.KNOWN_SUBSET
    assert snap["one_known_pairwise_comparison"]["p363_pair_subset"] == snapshots.KNOWN_SUBSET
    assert snap["validation_summary"]["fail_count"] == 0


def test_cli_generate_help_validate_commands_work(tmp_path):
    generate_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_api_snapshots",
            "--artifacts-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "No DB was opened or written; no adapters were called; no new scoring cohort was created." in generate_result.stdout
    for basename in snapshots.P368_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    help_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_api_snapshots", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "usage:" in help_result.stdout

    validate_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_api_snapshots", "--validate"],
        check=True,
        text=True,
        capture_output=True,
    )
    rows = list(csv.DictReader(validate_result.stdout.splitlines()))
    assert rows
    assert {row["status"] for row in rows} == {"PASS"}


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert snapshots._artifact_contents(first) == snapshots._artifact_contents(second)
    first_paths = snapshots.write_artifacts(first, tmp_path / "first")
    second_paths = snapshots.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_markdown_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = snapshots.write_artifacts(first, tmp_path)
    with open(paths["golden_snapshots"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == snapshots.TASK
    with open(paths["cli_transcripts"], encoding="utf-8") as handle:
        assert json.load(handle)["transcripts"]["validate"]["exit_code"] == 0
    with open(paths["compatibility_matrix"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.compatibility_rows)
    with open(paths["contract_drift"], newline="", encoding="utf-8") as handle:
        assert {row["status"] for row in csv.DictReader(handle)} == {"PASS"}
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["readme"].read_text(encoding="utf-8").startswith("# P368 Big Lotto no-DB evidence API snapshots")


def test_no_db_import_open_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = snapshots.run_snapshots()
    assert output.golden_snapshots["statements"]["db_opened"] is False
    assert all(row["no_db_open_write"] == "YES" for row in output.manifest_rows)


def test_no_adapter_execution_guard_if_practical(double_run):
    first, _ = double_run
    assert first.golden_snapshots["statements"]["adapter_calls"] is False
    assert all(row["no_adapter_calls"] == "YES" for row in first.manifest_rows)
    assert "historical_adapters" not in sys.modules
