import csv
import sqlite3

import pytest

from recovered_strategies.biglotto import no_db_evidence_pack as pack
from recovered_strategies.biglotto import no_db_multiwindow_validation as p360


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P363 evidence pack")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = pack.run_evidence_pack()
        second = pack.run_evidence_pack()
    finally:
        patcher.undo()
    return first, second


def test_required_p360_p361_p362_artifacts_exist():
    paths = pack.verify_required_artifacts()
    assert len(paths) == len(pack.SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)


def test_source_artifact_sha256_and_row_count_manifest_generation(double_run):
    first, _ = double_run
    assert len(first.source_manifest_rows) == len(pack.SOURCE_ARTIFACTS)
    assert set(first.source_manifest_rows[0]) == set(pack.SOURCE_MANIFEST_COLUMNS)
    by_role = {row["artifact_role"]: row for row in first.source_manifest_rows}
    assert by_role["p360_results"]["data_row_count"] == "20"
    assert by_role["p361_subset_metrics"]["data_row_count"] == "31"
    assert by_role["p361_hit_matrix"]["data_row_count"] == "1619"
    assert by_role["p362_window_metrics"]["data_row_count"] == "124"
    for row in first.source_manifest_rows:
        assert len(row["sha256"]) == 64
        assert int(row["line_count"]) > 0
    manifest_checked = [
        row for row in first.source_manifest_rows if row["row_count_matches_manifest"]
    ]
    assert manifest_checked
    assert all(row["row_count_matches_manifest"] == "true" for row in manifest_checked)


def test_exact_5_parity_adapter_consistency_across_artifacts(double_run):
    first, _ = double_run
    adapter_check = next(
        row
        for row in first.consistency_check_rows
        if row["check_name"] == "exact_5_parity_adapter_names_consistent"
    )
    assert adapter_check["status"] == "PASS"
    assert set(first.adapter_card_rows[0]) == set(pack.ADAPTER_CARD_COLUMNS)
    assert tuple(row["adapter_function"] for row in first.adapter_card_rows) == p360.ALLOWLISTED_ADAPTERS
    assert len(first.adapter_card_rows) == 5


def test_expected_window_set_consistency(double_run):
    first, _ = double_run
    window_check = next(
        row for row in first.consistency_check_rows if row["check_name"] == "expected_windows_present"
    )
    assert window_check["status"] == "PASS"
    for row in first.adapter_card_rows:
        assert row["p360_windows_present"] == "30;150;750;1500"


def test_p361_subset_count_is_31(double_run):
    first, _ = double_run
    subset_check = next(
        row for row in first.consistency_check_rows if row["check_name"] == "p361_subset_count"
    )
    assert subset_check["status"] == "PASS"
    assert len(first.subset_card_rows) == 31


def test_p361_hit_matrix_period_count_is_1619(double_run):
    first, _ = double_run
    matrix_check = next(
        row
        for row in first.consistency_check_rows
        if row["check_name"] == "p361_hit_matrix_period_count"
    )
    assert matrix_check["status"] == "PASS"
    summary = {(row["section"], row["key"]): row["value"] for row in first.summary_rows}
    assert summary[("dimensions", "p361_hit_matrix_period_count")] == "1619"


def test_adapter_card_schema(double_run):
    first, _ = double_run
    for row in first.adapter_card_rows:
        assert set(row) == set(pack.ADAPTER_CARD_COLUMNS)
        assert row["bet_count"] in {"2", "3"}
        assert row["p361_redundancy_note"]
        assert row["p362_stability_note"]
        assert "Historical descriptive evidence only" in row["caveat"]


def test_subset_card_schema(double_run):
    first, _ = double_run
    full_rows = [row for row in first.subset_card_rows if row["subset_is_full_cohort"] == "true"]
    assert len(full_rows) == 1
    for row in first.subset_card_rows:
        assert set(row) == set(pack.SUBSET_CARD_COLUMNS)
        assert 1 <= int(row["subset_size"]) <= 5
        assert row["p361_period_count"] == "1619"
        assert row["p362_windows_evaluated"] == "4"
        assert row["p362_stability_note"]
        assert "no new scoring" in row["caveat"]


def test_consistency_check_output_schema(double_run):
    first, _ = double_run
    assert first.consistency_check_rows
    for row in first.consistency_check_rows:
        assert set(row) == set(pack.CONSISTENCY_CHECK_COLUMNS)
        assert row["status"] == "PASS"
    assert {
        "source_artifact_row_counts_match_manifests",
        "p362_compact_candidates_reference_valid_subsets",
    } <= {row["check_name"] for row in first.consistency_check_rows}


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert first.summary_rows == second.summary_rows
    assert first.source_manifest_rows == second.source_manifest_rows
    assert first.adapter_card_rows == second.adapter_card_rows
    assert first.subset_card_rows == second.subset_card_rows
    assert first.consistency_check_rows == second.consistency_check_rows
    first_paths = pack.write_artifacts(first, tmp_path / "first")
    second_paths = pack.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_csv_artifacts_parse_and_read_back(tmp_path, double_run):
    first, _ = double_run
    paths = pack.write_artifacts(first, tmp_path)
    with open(paths["summary"], newline="", encoding="utf-8") as handle:
        summary_rows = list(csv.DictReader(handle))
    assert len(summary_rows) == len(first.summary_rows)
    assert set(summary_rows[0]) == set(pack.SUMMARY_COLUMNS)
    with open(paths["adapter_cards"], newline="", encoding="utf-8") as handle:
        adapter_rows = list(csv.DictReader(handle))
    assert len(adapter_rows) == len(first.adapter_card_rows)
    assert set(adapter_rows[0]) == set(pack.ADAPTER_CARD_COLUMNS)
    with open(paths["subset_cards"], newline="", encoding="utf-8") as handle:
        subset_rows = list(csv.DictReader(handle))
    assert len(subset_rows) == len(first.subset_card_rows)
    assert set(subset_rows[0]) == set(pack.SUBSET_CARD_COLUMNS)
    with open(paths["consistency_checks"], newline="", encoding="utf-8") as handle:
        check_rows = list(csv.DictReader(handle))
    assert len(check_rows) == len(first.consistency_check_rows)
    assert set(check_rows[0]) == set(pack.CONSISTENCY_CHECK_COLUMNS)
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        manifest_rows = list(csv.DictReader(handle))
    assert len(manifest_rows) == len(first.source_manifest_rows)
    assert set(manifest_rows[0]) == set(pack.SOURCE_MANIFEST_COLUMNS)
    assert paths["report"].is_file()
    assert paths["report"].stat().st_size > 0


def test_report_contains_required_no_db_and_no_claim_statements(double_run):
    first, _ = double_run
    report = pack.render_report(first)
    assert "historical descriptive evidence only" in report
    assert "No future prediction guarantee" in report
    assert "No betting advice" in report
    assert "No DB was opened or written" in report
    assert "No production registry import" in report
    assert "no deploy" in report
    assert "No blended leaderboard" in report
    assert "Shape-only and blocked targets remain excluded" in report
    assert "P363 does not call adapters, re-score strategies, or create a new scoring cohort" in report
