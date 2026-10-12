import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_api as api


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P367 evidence API")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = api.run_api()
        second = api.run_api()
    finally:
        patcher.undo()
    return first, second


def test_required_p363_p364_p365_p366_artifacts_exist():
    paths = api.verify_required_artifacts()
    assert len(paths) == len(api.SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)


def test_api_functions_return_stable_schemas(double_run):
    first, _ = double_run
    manifest = api.load_release_manifest()
    inventory = api.load_inventory()
    adapters = api.list_adapters()
    adapter = api.get_adapter(adapters[0])
    subsets = api.list_subsets(subset_size=2)
    subset = api.get_subset(subsets[0]["adapter_subset"])
    pair = subsets[0]["adapter_subset"].split(";")
    comparison = api.compare_adapters(pair[1], pair[0])
    shortlist = api.get_compact_shortlist()

    assert manifest["task"] == "P366_biglotto_evidence_release_bundle"
    assert len(inventory) == 28
    assert len(adapters) == api.EXPECTED_ADAPTER_COUNT
    assert adapter["adapter_function"] == adapters[0]
    assert len(subsets) == api.EXPECTED_PAIRWISE_COUNT
    assert subset["subset_size"] == "2"
    assert comparison["subset_size"] == "2"
    assert len(shortlist) == api.EXPECTED_COMPACT_SHORTLIST_COUNT
    assert first.contract["statements"]["db_opened"] is False
    assert first.contract["statements"]["adapter_calls"] is False


def test_cli_list_get_filter_compare_validate_commands_work():
    list_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_api", "--list-adapters"],
        check=True,
        text=True,
        capture_output=True,
    )
    adapters = json.loads(list_result.stdout)
    assert len(adapters) == api.EXPECTED_ADAPTER_COUNT

    adapter_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_api",
            "--get-adapter",
            adapters[0],
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(adapter_result.stdout)["adapter_function"] == adapters[0]

    subset_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_api",
            "--list-subsets",
            "--subset-size",
            "2",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    subsets = json.loads(subset_result.stdout)
    assert len(subsets) == api.EXPECTED_PAIRWISE_COUNT
    assert {row["subset_size"] for row in subsets} == {"2"}

    subset_name = subsets[0]["adapter_subset"]
    subset_detail_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_api",
            "--get-subset",
            subset_name,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(subset_detail_result.stdout)["adapter_subset"] == subset_name

    pair = subset_name.split(";")
    compare_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_api",
            "--compare-adapters",
            pair[1],
            pair[0],
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(compare_result.stdout)["p363_pair_subset"] == subset_name

    shortlist_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_api", "--compact-shortlist"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert len(list(csv.DictReader(shortlist_result.stdout.splitlines()))) == api.EXPECTED_COMPACT_SHORTLIST_COUNT

    validate_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_api", "--validate"],
        check=True,
        text=True,
        capture_output=True,
    )
    validation_rows = list(csv.DictReader(validate_result.stdout.splitlines()))
    assert validation_rows
    assert {row["status"] for row in validation_rows} == {"PASS"}


def test_help_and_emit_contract_cli_work():
    help_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_api", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "usage:" in help_result.stdout

    contract_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_api", "--emit-contract"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(contract_result.stdout)["task"] == api.TASK


def test_api_contract_json_schema(double_run):
    first, _ = double_run
    contract = first.contract
    assert contract["task"] == api.TASK
    assert contract["generated_at"] == api.GENERATED_AT
    assert len(contract["supported_functions"]) == 9
    by_name = {row["name"]: row for row in contract["supported_functions"]}
    assert by_name["get_adapter"]["input_arguments"] == ["adapter_function"]
    assert by_name["compare_adapters"]["input_arguments"] == ["adapter_a", "adapter_b"]
    assert by_name["validate_evidence_stack"]["output_schema_name"] == "ValidationRows"
    assert len(contract["artifact_sources"]) == len(api.SOURCE_ARTIFACTS)
    assert contract["statements"]["new_scoring_cohort"] is False
    assert "No DB was opened or written." == contract["no_db_open_write_statement"]


def test_examples_json_schema(double_run):
    first, _ = double_run
    examples = first.examples
    assert examples["task"] == api.TASK
    assert set(examples["examples"]) == {
        "list_adapters",
        "one_adapter_detail",
        "list_subset_size_2",
        "one_subset_detail",
        "one_pairwise_comparison",
        "compact_shortlist",
        "validation_summary",
    }
    assert len(examples["examples"]["list_adapters"]) == api.EXPECTED_ADAPTER_COUNT
    assert examples["examples"]["one_adapter_detail"]["adapter_function"]
    assert len(examples["examples"]["list_subset_size_2"]) == api.EXPECTED_PAIRWISE_COUNT
    assert examples["examples"]["one_pairwise_comparison"]["subset_size"] == "2"
    assert examples["examples"]["validation_summary"]["no_db_open_write"] is True


def test_validation_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.validation_rows[0]) == api.VALIDATION_COLUMNS
    assert all(row["status"] == "PASS" for row in first.validation_rows)
    names = {row["check_name"] for row in first.validation_rows}
    assert any(name.startswith("required_artifact_exists:artifacts/P363_") for name in names)
    assert any(name.startswith("json_artifact_parses:artifacts/P366_") for name in names)
    assert any(name.startswith("csv_artifact_parses:artifacts/P365_") for name in names)
    assert any(name.startswith("html_markdown_artifact_exists:artifacts/P366_") for name in names)
    assert "source_sha256_values_available" in names
    assert "adapter_count_matches_expected_evidence" in names
    assert "generated_p367_forbidden_claim_phrases_absent" in names


def test_manifest_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.manifest_rows[0]) == api.MANIFEST_COLUMNS
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    output_rows = [row for row in first.manifest_rows if row["artifact_group"] == "output"]
    statement_rows = [row for row in first.manifest_rows if row["artifact_group"] == "statement"]
    assert len(source_rows) == len(api.SOURCE_ARTIFACTS)
    assert len(output_rows) == len(api.P367_ARTIFACT_BASENAMES)
    assert len(statement_rows) == 2
    assert {row["no_db_open_write"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_adapter_calls"] for row in first.manifest_rows} == {"YES"}
    assert {row["no_new_scoring"] for row in first.manifest_rows} == {"YES"}
    assert all(len(row["sha256"]) == 64 for row in source_rows)


def test_readme_contains_scope_statements(double_run):
    first, _ = double_run
    readme = first.readme_md
    assert "python3 -m recovered_strategies.biglotto.no_db_evidence_api --validate" in readme
    assert "Historical descriptive evidence only." in readme
    assert "No future prediction guarantee." in readme
    assert "No betting advice." in readme
    assert "No DB open/write." in readme
    assert "No production registry import." in readme
    assert "No deploy." in readme
    assert "No adapter calls." in readme
    assert "No new scoring cohort." in readme
    assert "No blended leaderboard." in readme
    assert "Shape-only and blocked targets remain excluded." in readme


def test_deterministic_double_run_equality_and_write_artifacts(tmp_path, double_run):
    first, second = double_run
    assert first.contract == second.contract
    assert first.examples == second.examples
    assert first.validation_rows == second.validation_rows
    assert first.manifest_rows == second.manifest_rows
    assert first.readme_md == second.readme_md

    first_paths = api.write_artifacts(first, tmp_path / "first")
    second_paths = api.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_markdown_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = api.write_artifacts(first, tmp_path)
    with open(paths["contract"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == api.TASK
    with open(paths["examples"], encoding="utf-8") as handle:
        assert json.load(handle)["examples"]["list_adapters"]
    with open(paths["validation"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.validation_rows)
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.manifest_rows)
    assert paths["readme"].read_text(encoding="utf-8").startswith("# P367 Big Lotto no-DB evidence API")


def test_default_cli_generates_artifacts(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_api",
            "--artifacts-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in result.stdout
    assert "No DB was opened or written; no adapters were called; no new scoring cohort was created." in result.stdout
    for basename in api.P367_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()


def test_no_db_import_open_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = api.run_api()
    assert output.contract["statements"]["db_opened"] is False
    assert output.contract["statements"]["db_written"] is False


def test_no_adapter_execution_guard_if_practical(double_run):
    first, _ = double_run
    source_text = api.__file__ and open(api.__file__, encoding="utf-8").read()
    assert "import sqlite3" not in source_text
    assert "recovered_strategies.biglotto.adapters" not in source_text
    assert first.contract["statements"]["adapter_calls"] is False
    assert "No adapters were called" in first.contract["no_adapter_calls_statement"]
