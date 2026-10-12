import csv
import sqlite3

import pytest

from recovered_strategies.biglotto import no_db_coverage_utility as utility
from recovered_strategies.biglotto import no_db_multiwindow_validation as p360


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P361 coverage utility")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = utility.run_coverage_utility()
        second = utility.run_coverage_utility()
    finally:
        patcher.undo()
    return first, second


def test_uses_p360_no_db_fixture_and_adapter_cohort(double_run):
    first, _ = double_run
    assert first.fixture_sha256 == p360.EXPECTED_FIXTURE_SHA256
    assert first.draw_count == p360.EXPECTED_BIG_LOTTO_ROWS
    assert first.scoreable_period_count == 1619
    assert first.adapter_names == p360.ALLOWLISTED_ADAPTERS
    manifest = {row["key"]: row["value"] for row in first.manifest_rows}
    assert manifest["db_opened"] == "NO"
    assert manifest["production_registry_imported"] == "NO"
    assert manifest["strategy_status_changed"] == "NO"
    assert manifest["future_prediction_claim"] == "NO"
    assert manifest["betting_advice"] == "NO"


def test_subset_metrics_cover_every_non_empty_adapter_subset(double_run):
    first, _ = double_run
    assert utility.SUBSET_METRICS_COLUMNS == (
        "subset_size",
        "rank_within_subset_size",
        "best_subset_for_size",
        "adapter_subset",
        "period_count",
        "any_hit_count",
        "coverage_rate",
        "total_adapter_hit_events",
        "duplicate_hit_events",
        "multi_adapter_hit_period_count",
        "single_adapter_hit_period_count",
        "mean_pairwise_jaccard",
        "max_pairwise_jaccard",
        "fixture_sha256",
    )
    assert len(first.subset_metrics_rows) == (2 ** len(first.adapter_names)) - 1 == 31
    for row in first.subset_metrics_rows:
        assert set(row) == set(utility.SUBSET_METRICS_COLUMNS)
        assert row["fixture_sha256"] == p360.EXPECTED_FIXTURE_SHA256
        assert int(row["period_count"]) == first.scoreable_period_count
        assert 0 <= int(row["any_hit_count"]) <= first.scoreable_period_count
    full_rows = [
        row for row in first.subset_metrics_rows
        if int(row["subset_size"]) == len(first.adapter_names)
    ]
    assert len(full_rows) == 1
    assert full_rows[0]["any_hit_count"] == "171"
    assert full_rows[0]["adapter_subset"] == ";".join(first.adapter_names)


def test_marginal_contribution_is_comprehensive_and_matches_p360_unique_counts(double_run):
    first, _ = double_run
    assert len(first.marginal_contribution_rows) == len(first.adapter_names) * (2 ** 4) == 80
    p360_unique = {
        row["adapter_a"]: row["unique_hit_count"]
        for row in p360.run_validation().coverage_rows
        if row["row_type"] == "unique_contribution"
    }
    for adapter_name in first.adapter_names:
        empty_context = [
            row for row in first.marginal_contribution_rows
            if row["candidate_adapter"] == adapter_name and row["context_size"] == "0"
        ]
        assert len(empty_context) == 1
        assert empty_context[0]["candidate_total_hit_count"] == empty_context[0]["marginal_unique_hit_count"]
        full_context = [
            row for row in first.marginal_contribution_rows
            if row["candidate_adapter"] == adapter_name
            and row["context_size"] == str(len(first.adapter_names) - 1)
        ]
        assert len(full_context) == 1
        assert full_context[0]["marginal_unique_hit_count"] == p360_unique[adapter_name]


def test_hit_matrix_has_period_level_binary_hits(double_run):
    first, _ = double_run
    expected_columns = (
        utility.HIT_MATRIX_BASE_COLUMNS
        + first.adapter_names
        + utility.HIT_MATRIX_TRAILING_COLUMNS
    )
    assert len(first.hit_matrix_rows) == first.scoreable_period_count == 1619
    assert tuple(first.hit_matrix_rows[0]) == expected_columns
    periods = [int(row["period"]) for row in first.hit_matrix_rows]
    assert periods == sorted(periods)
    assert len(set(periods)) == len(periods)
    assert first.hit_matrix_rows[0]["period"] == "100000103"
    assert first.hit_matrix_rows[-1]["period"] == "115000057"
    for row in first.hit_matrix_rows:
        hits = [int(row[name]) for name in first.adapter_names]
        assert set(hits) <= {0, 1}
        assert int(row["cohort_hit_count"]) == sum(hits)
        assert row["cohort_any_hit"] == ("1" if sum(hits) else "0")
        assert row["fixture_sha256"] == p360.EXPECTED_FIXTURE_SHA256


def test_deterministic_double_run_equality(double_run):
    first, second = double_run
    assert first.subset_metrics_rows == second.subset_metrics_rows
    assert first.marginal_contribution_rows == second.marginal_contribution_rows
    assert first.hit_matrix_rows == second.hit_matrix_rows
    assert first.manifest_rows == second.manifest_rows


def test_csv_artifacts_are_written_and_parseable(tmp_path, double_run):
    first, _ = double_run
    paths = utility.write_artifacts(first, tmp_path)
    with open(paths["subset_metrics"], newline="", encoding="utf-8") as handle:
        subset_rows = list(csv.DictReader(handle))
    assert len(subset_rows) == len(first.subset_metrics_rows)
    assert set(subset_rows[0]) == set(utility.SUBSET_METRICS_COLUMNS)
    with open(paths["marginal_contribution"], newline="", encoding="utf-8") as handle:
        marginal_rows = list(csv.DictReader(handle))
    assert len(marginal_rows) == len(first.marginal_contribution_rows)
    assert set(marginal_rows[0]) == set(utility.MARGINAL_CONTRIBUTION_COLUMNS)
    with open(paths["hit_matrix"], newline="", encoding="utf-8") as handle:
        matrix_rows = list(csv.DictReader(handle))
    assert len(matrix_rows) == len(first.hit_matrix_rows)
    assert set(matrix_rows[0]) == set(
        utility.HIT_MATRIX_BASE_COLUMNS
        + first.adapter_names
        + utility.HIT_MATRIX_TRAILING_COLUMNS
    )
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        manifest = {row["key"]: row["value"] for row in csv.DictReader(handle)}
    assert manifest["task"] == utility.TASK
    assert manifest["source_task"] == "P360_biglotto_no_db_multiwindow_validation"
    assert manifest["db_opened"] == "NO"
    assert paths["report"].is_file()
    assert paths["report"].stat().st_size > 0


def test_report_contains_required_statements(double_run):
    first, _ = double_run
    report = utility.render_report(first)
    assert "historical descriptive coverage utility only" in report
    assert "No future prediction guarantee" in report
    assert "No betting advice" in report
    assert "No DB was opened or written" in report
    assert "No production registry import" in report
    assert "Shape/safety-only adapters and blocked targets were excluded from scoring" in report
    assert p360.EXPECTED_FIXTURE_SHA256 in report
    assert "Best subset by size" in report
    assert "Full-cohort marginal contribution" in report
