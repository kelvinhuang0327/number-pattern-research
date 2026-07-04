import csv
import sqlite3

import pytest

from recovered_strategies.biglotto import historical_adapters
from recovered_strategies.biglotto import no_db_multiwindow_validation as p360
from recovered_strategies.biglotto import no_db_subset_stability as stability


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P362 subset stability")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = stability.run_subset_stability()
        second = stability.run_subset_stability()
    finally:
        patcher.undo()
    return first, second


def test_required_p360_p361_evidence_exists():
    evidence_paths = stability.verify_required_evidence()
    assert len(evidence_paths) == len(stability.REQUIRED_EVIDENCE_RELPATHS)
    assert all(path.is_file() for path in evidence_paths)


def test_exact_5_adapter_allowlist(double_run):
    first, _ = double_run
    assert first.adapter_names == p360.ALLOWLISTED_ADAPTERS
    assert len(first.adapter_names) == 5
    specs = stability.resolve_scoring_adapters()
    assert tuple(spec.name for spec in specs) == p360.ALLOWLISTED_ADAPTERS
    assert all(spec.parity_status == p360.REQUIRED_PARITY_STATUS for spec in specs)


def test_shape_only_blocked_and_non_allowlisted_adapters_fail_closed():
    non_allowlisted = [
        name for name in historical_adapters.ADAPTER_METADATA if name not in p360.ALLOWLISTED_ADAPTERS
    ]
    assert non_allowlisted
    for name in non_allowlisted[:10]:
        with pytest.raises(p360.AdapterSelectionError):
            stability.resolve_scoring_adapters(p360.ALLOWLISTED_ADAPTERS + (name,))
        with pytest.raises(p360.AdapterSelectionError):
            stability.resolve_scoring_adapters((name,))
    with pytest.raises(p360.AdapterSelectionError):
        stability.resolve_scoring_adapters(p360.ALLOWLISTED_ADAPTERS[:4])
    with pytest.raises(p360.AdapterSelectionError):
        stability.resolve_scoring_adapters(("adapter_that_does_not_exist",))


def test_subset_enumeration_count_is_31(double_run):
    first, _ = double_run
    subsets = stability.enumerate_adapter_subsets(first.adapter_names)
    assert len(subsets) == (2 ** len(first.adapter_names)) - 1 == 31
    assert subsets[0] == (p360.ALLOWLISTED_ADAPTERS[0],)
    assert subsets[-1] == p360.ALLOWLISTED_ADAPTERS
    assert len(first.window_metrics_rows) == 31 * len(stability.WINDOWS)
    for window in stability.WINDOWS:
        window_rows = [row for row in first.window_metrics_rows if row["window_size"] == str(window)]
        assert len(window_rows) == 31


def test_window_metrics_schema_and_values(double_run):
    first, _ = double_run
    assert stability.WINDOW_METRICS_COLUMNS == (
        "subset_size",
        "adapter_subset",
        "total_ticket_count",
        "window_size",
        "period_count",
        "any_hit_count",
        "coverage_rate",
        "duplicate_hit_events",
        "mean_pairwise_jaccard",
        "same_total_bet_count_baseline",
        "edge_vs_same_total_bet_baseline",
        "rank_by_coverage_rate",
        "rank_by_any_hit_count",
        "within_1_hit_of_full_cohort",
        "within_3_hits_of_full_cohort",
        "fixture_sha256",
    )
    for row in first.window_metrics_rows:
        assert set(row) == set(stability.WINDOW_METRICS_COLUMNS)
        assert row["fixture_sha256"] == p360.EXPECTED_FIXTURE_SHA256
        assert int(row["period_count"]) == int(row["window_size"])
        assert int(row["window_size"]) in stability.WINDOWS
        assert 1 <= int(row["subset_size"]) <= len(first.adapter_names)
        assert 0 <= int(row["any_hit_count"]) <= int(row["period_count"])
        assert 1 <= int(row["rank_by_coverage_rate"]) <= 31
        assert 1 <= int(row["rank_by_any_hit_count"]) <= 31
        assert row["within_1_hit_of_full_cohort"] in {"true", "false"}
        assert row["within_3_hits_of_full_cohort"] in {"true", "false"}


def test_compact_candidate_logic(double_run):
    first, _ = double_run
    best_rows = [
        row for row in first.compact_candidate_rows if row["row_type"] == "best_subset_for_size"
    ]
    assert len(best_rows) == len(stability.WINDOWS) * len(first.adapter_names)
    threshold_rows = [
        row
        for row in first.compact_candidate_rows
        if row["row_type"].startswith("smallest_within_")
    ]
    assert len(threshold_rows) == len(stability.WINDOWS) * 2
    focus_rows = [
        row for row in first.compact_candidate_rows if row["row_type"] == "p361_compact_pair_check"
    ]
    assert len(focus_rows) == len(stability.WINDOWS)
    assert {row["adapter_subset"] for row in focus_rows} == {";".join(stability.FOCUS_COMPACT_SUBSET)}
    for row in threshold_rows:
        assert int(row["hit_gap_to_full_cohort"]) <= (
            1 if row["row_type"] == "smallest_within_1_hit_of_full_cohort" else 3
        )
    for window in stability.WINDOWS:
        full_rows = [
            row
            for row in first.window_metrics_rows
            if row["window_size"] == str(window)
            and int(row["subset_size"]) == len(first.adapter_names)
        ]
        assert len(full_rows) == 1
        compact_full = [
            row
            for row in first.compact_candidate_rows
            if row["window_size"] == str(window)
            and row["adapter_subset"] == full_rows[0]["adapter_subset"]
            and row["row_type"] == "best_subset_for_size"
        ]
        assert compact_full[0]["hit_gap_to_full_cohort"] == "0"


def test_same_total_bet_count_baseline_formula(double_run):
    first, _ = double_run
    for row in first.window_metrics_rows:
        total_ticket_count = int(row["total_ticket_count"])
        expected = 1 - (1 - p360.BASELINE_SINGLE_TICKET_P) ** total_ticket_count
        assert float(row["same_total_bet_count_baseline"]) == pytest.approx(expected, abs=5e-9)
        expected_coverage = int(row["any_hit_count"]) / int(row["period_count"])
        expected_edge = expected_coverage - expected
        assert float(row["edge_vs_same_total_bet_baseline"]) == pytest.approx(expected_edge, abs=5e-9)


def test_rank_stability_summary(double_run):
    first, _ = double_run
    assert len(first.rank_summary_rows) == 31
    assert set(first.rank_summary_rows[0]) == set(stability.RANK_SUMMARY_COLUMNS)
    for row in first.rank_summary_rows:
        assert row["fixture_sha256"] == p360.EXPECTED_FIXTURE_SHA256
        assert row["windows_evaluated"] == str(len(stability.WINDOWS))
        assert 0 <= int(row["top_1_window_count"]) <= len(stability.WINDOWS)
        assert 0 <= int(row["top_3_window_count"]) <= len(stability.WINDOWS)
        assert 0 <= int(row["within_3_hits_of_full_cohort_window_count"]) <= len(stability.WINDOWS)


def test_deterministic_double_run_equality(double_run):
    first, second = double_run
    assert first.window_metrics_rows == second.window_metrics_rows
    assert first.rank_summary_rows == second.rank_summary_rows
    assert first.compact_candidate_rows == second.compact_candidate_rows
    assert first.manifest_rows == second.manifest_rows
    assert first.fixture_sha256 == second.fixture_sha256 == p360.EXPECTED_FIXTURE_SHA256


def test_csv_artifacts_are_written_and_parseable(tmp_path, double_run):
    first, _ = double_run
    paths = stability.write_artifacts(first, tmp_path)
    with open(paths["window_metrics"], newline="", encoding="utf-8") as handle:
        window_rows = list(csv.DictReader(handle))
    assert len(window_rows) == len(first.window_metrics_rows)
    assert set(window_rows[0]) == set(stability.WINDOW_METRICS_COLUMNS)
    with open(paths["rank_summary"], newline="", encoding="utf-8") as handle:
        rank_rows = list(csv.DictReader(handle))
    assert len(rank_rows) == len(first.rank_summary_rows)
    assert set(rank_rows[0]) == set(stability.RANK_SUMMARY_COLUMNS)
    with open(paths["compact_candidates"], newline="", encoding="utf-8") as handle:
        compact_rows = list(csv.DictReader(handle))
    assert len(compact_rows) == len(first.compact_candidate_rows)
    assert set(compact_rows[0]) == set(stability.COMPACT_CANDIDATES_COLUMNS)
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        manifest = {row["key"]: row["value"] for row in csv.DictReader(handle)}
    assert manifest["task"] == stability.TASK
    assert manifest["db_opened"] == "NO"
    assert manifest["db_written"] == "NO"
    assert manifest["blended_leaderboard"] == "NO"
    assert paths["report"].is_file()
    assert paths["report"].stat().st_size > 0


def test_report_contains_required_statements(double_run):
    first, _ = double_run
    report = stability.render_report(first)
    assert "historical descriptive subset stability only" in report
    assert "No DB was opened or written" in report
    assert "No betting advice" in report
    assert "No future prediction guarantee" in report
    assert "No blended leaderboard" in report
    assert "Shape/safety-only adapters and blocked targets were excluded from scoring" in report
    assert p360.EXPECTED_FIXTURE_SHA256 in report
    assert "P361 compact pair check" in report
