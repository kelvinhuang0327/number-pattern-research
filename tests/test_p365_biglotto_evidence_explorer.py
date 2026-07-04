import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_explorer as explorer


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P365 evidence explorer")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = explorer.run_explorer()
        second = explorer.run_explorer()
    finally:
        patcher.undo()
    return first, second


def test_required_p363_p364_artifacts_exist():
    paths = explorer.verify_required_artifacts()
    assert len(paths) == len(explorer.P365_SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)


def test_source_artifact_sha256_manifest_generation(double_run):
    first, _ = double_run
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    assert len(source_rows) == len(explorer.P365_SOURCE_ARTIFACTS)
    by_role = {row["artifact_role"]: row for row in source_rows}
    assert by_role["p363_adapter_cards"]["row_count"] == "5"
    assert by_role["p363_subset_cards"]["row_count"] == "31"
    assert by_role["p364_adapter_table"]["row_count"] == "5"
    assert by_role["p364_subset_table"]["row_count"] == "31"
    assert by_role["p364_index"]["object_count"] == "1"
    for row in source_rows:
        assert len(row["sha256"]) == 64
        assert row["no_db_open_write"] == "YES"
        assert row["no_adapter_calls"] == "YES"


def test_adapter_detail_card_schema(double_run):
    first, _ = double_run
    assert len(first.adapter_detail_cards) == 5
    card = first.adapter_detail_cards[0]
    assert {
        "adapter_function",
        "strategy_id",
        "bet_count",
        "scope",
        "p360_performance_summary",
        "p361_contribution_redundancy",
        "p362_stability",
        "caveats",
        "source_caveat",
    } == set(card)
    assert card["adapter_function"] == "adapt_predict_biglotto_echo_mixed_3bet"
    assert card["scope"]["historical_descriptive_evidence_only"] is True
    assert card["scope"]["adapter_calls"] is False
    assert card["p360_performance_summary"]["windows_present"] == "30;150;750;1500"
    assert set(card["p360_performance_summary"]["windows"]) == {"30", "150", "750", "1500"}
    assert card["p361_contribution_redundancy"]["redundancy_note"]
    assert card["p362_stability"]["stability_note"]
    assert "No betting advice." in card["caveats"]


def test_subset_detail_card_schema(double_run):
    first, _ = double_run
    assert len(first.subset_detail_cards) == 31
    card = first.subset_detail_cards[0]
    assert {
        "adapter_subset",
        "subset_size",
        "scope",
        "p361_coverage_utility",
        "p362_stability",
        "compact_candidate_flags",
        "caveats",
        "source_caveat",
    } == set(card)
    assert card["adapter_subset"] == "adapt_predict_biglotto_echo_mixed_3bet"
    assert card["subset_size"] == "1"
    assert card["p361_coverage_utility"]["period_count"] == "1619"
    assert card["p362_stability"]["windows_evaluated"] == "4"
    assert card["compact_candidate_flags"]["row_types"]
    assert card["scope"]["db_opened"] is False


def test_pairwise_comparison_schema(double_run):
    first, _ = double_run
    assert len(first.pairwise_rows) == 10
    assert tuple(first.pairwise_rows[0]) == explorer.PAIRWISE_COLUMNS
    assert tuple(row["display_rank"] for row in first.pairwise_rows) == tuple(str(i) for i in range(1, 11))
    for row in first.pairwise_rows:
        assert row["subset_size"] == "2"
        assert row["adapter_a"] < row["adapter_b"]
        assert row["p361_pair_mean_pairwise_jaccard"] != ""
        assert "P363/P364" in row["redundancy_scope"]
        assert "no new scoring" in row["caveat"]


def test_compact_shortlist_schema(double_run):
    first, _ = double_run
    assert len(first.compact_shortlist_rows) == 8
    assert tuple(first.compact_shortlist_rows[0]) == explorer.SHORTLIST_COLUMNS
    for row in first.compact_shortlist_rows:
        assert row["why_compact_historically"]
        assert "Does not prove future performance" in row["what_it_does_not_prove"]
        assert "No recommendation language" in row["caveat"]


def test_query_snapshots_schema(double_run):
    first, _ = double_run
    snapshots = first.query_snapshots
    assert snapshots["task"] == explorer.TASK
    assert snapshots["generated_at"] == explorer.GENERATED_AT
    assert snapshots["scope"]["new_scoring_cohort"] is False
    assert len(snapshots["source_sha256"]) == len(explorer.P365_SOURCE_ARTIFACTS)
    assert snapshots["counts"]["adapter_detail_cards"] == 5
    assert snapshots["counts"]["subset_detail_cards"] == 31
    assert snapshots["counts"]["pairwise_comparison_rows"] == 10
    examples = snapshots["query_examples"]
    assert len(examples["list_adapters"]) == 5
    assert examples["show_adapter"]["adapter_function"]
    assert examples["show_subset"]["adapter_subset"]
    assert examples["compare_two_adapters"]["subset_size"] == "2"
    assert examples["compact_shortlist"]


def test_html_explorer_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    html = first.html_text
    assert "<!doctype html>" in html
    assert "Scope / disclaimer banner" in html
    assert "Adapter Detail Section" in html
    assert "Subset Detail Section" in html
    assert "Compact Shortlist Section" in html
    assert "Pairwise Comparison Section" in html
    assert "Query Snapshot Section" in html
    assert "Source Artifact Inventory" in html
    for text in explorer.DISCLAIMER_LINES:
        assert text in html


def test_cli_list_show_filter_compare_shortlist_snapshots_work():
    list_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_explorer", "list-adapters"],
        check=True,
        text=True,
        capture_output=True,
    )
    adapters = list_result.stdout.splitlines()
    assert len(adapters) == 5
    adapter = adapters[0]

    show_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_explorer",
            "show-adapter",
            adapter,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(show_result.stdout)["adapter_function"] == adapter

    subset_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_explorer",
            "list-subsets",
            "--subset-size",
            "2",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    subsets = json.loads(subset_result.stdout)
    assert len(subsets) == 10
    assert {row["subset_size"] for row in subsets} == {"2"}

    subset_name = subsets[0]["adapter_subset"]
    show_subset_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_explorer",
            "show-subset",
            subset_name,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(show_subset_result.stdout)["adapter_subset"] == subset_name

    pair = subset_name.split(";")
    compare_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_explorer",
            "compare",
            pair[1],
            pair[0],
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    rows = list(csv.DictReader(compare_result.stdout.splitlines()))
    assert len(rows) == 1
    assert rows[0]["subset_size"] == "2"

    shortlist_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_explorer", "shortlist"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert len(list(csv.DictReader(shortlist_result.stdout.splitlines()))) == 8

    snapshots_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_explorer", "snapshots"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(snapshots_result.stdout)["counts"]["source_artifacts"] == len(
        explorer.P365_SOURCE_ARTIFACTS
    )


def test_cli_generate_command_produces_all_artifacts(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_explorer",
            "--artifacts-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in result.stdout
    assert "No DB was opened or written; no adapters were called." in result.stdout
    for basename in explorer.ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert first.adapter_detail_cards == second.adapter_detail_cards
    assert first.subset_detail_cards == second.subset_detail_cards
    assert first.pairwise_rows == second.pairwise_rows
    assert first.compact_shortlist_rows == second.compact_shortlist_rows
    assert first.query_snapshots == second.query_snapshots
    assert first.html_text == second.html_text
    assert first.manifest_rows == second.manifest_rows
    first_paths = explorer.write_artifacts(first, tmp_path / "first")
    second_paths = explorer.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_json_csv_html_artifacts_parse_and_readback(tmp_path, double_run):
    first, _ = double_run
    paths = explorer.write_artifacts(first, tmp_path)
    adapter_cards = json.loads(paths["adapter_detail_cards"].read_text(encoding="utf-8"))
    assert len(adapter_cards) == len(first.adapter_detail_cards)
    subset_cards = json.loads(paths["subset_detail_cards"].read_text(encoding="utf-8"))
    assert len(subset_cards) == len(first.subset_detail_cards)
    snapshots = json.loads(paths["query_snapshots"].read_text(encoding="utf-8"))
    assert snapshots["task"] == explorer.TASK
    with open(paths["pairwise_comparison"], newline="", encoding="utf-8") as handle:
        pairwise_rows = list(csv.DictReader(handle))
    assert len(pairwise_rows) == len(first.pairwise_rows)
    assert tuple(pairwise_rows[0]) == explorer.PAIRWISE_COLUMNS
    with open(paths["compact_shortlist"], newline="", encoding="utf-8") as handle:
        shortlist_rows = list(csv.DictReader(handle))
    assert len(shortlist_rows) == len(first.compact_shortlist_rows)
    assert tuple(shortlist_rows[0]) == explorer.SHORTLIST_COLUMNS
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        manifest_rows = list(csv.DictReader(handle))
    assert len(manifest_rows) == len(first.manifest_rows)
    assert tuple(manifest_rows[0]) == explorer.MANIFEST_COLUMNS
    html = paths["html"].read_text(encoding="utf-8")
    assert "P365 Big Lotto no-DB Evidence Explorer" in html


def test_no_db_import_open_and_no_adapter_execution_guard(double_run):
    first, _ = double_run
    statements = {row["artifact_role"]: row for row in first.manifest_rows if row["artifact_group"] == "statement"}
    assert statements["no_db_open_write"]["no_db_open_write"] == "YES"
    assert statements["no_db_open_write"]["no_adapter_calls"] == "YES"
    assert "no DB open/write" in statements["no_db_open_write"]["details"]
    assert "no adapter calls" in statements["no_db_open_write"]["details"]
    assert "no future prediction guarantee" in statements["scope_disclaimer"]["details"]
