import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_dashboard as dashboard


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P364 evidence dashboard")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = dashboard.run_dashboard()
        second = dashboard.run_dashboard()
    finally:
        patcher.undo()
    return first, second


def test_required_p363_artifacts_exist():
    paths = dashboard.verify_required_artifacts()
    assert len(paths) == len(dashboard.P363_SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)


def test_source_artifact_sha256_manifest_generation(double_run):
    first, _ = double_run
    source_rows = [row for row in first.manifest_rows if row["artifact_group"] == "source"]
    assert len(source_rows) == len(dashboard.P363_SOURCE_ARTIFACTS)
    by_role = {row["artifact_role"]: row for row in source_rows}
    assert by_role["p363_adapter_cards"]["row_count"] == "5"
    assert by_role["p363_subset_cards"]["row_count"] == "31"
    assert by_role["p363_consistency_checks"]["row_count"] == "9"
    for row in source_rows:
        assert len(row["sha256"]) == 64
        assert row["no_db_open_write"] == "YES"


def test_json_index_schema(double_run):
    first, _ = double_run
    index = first.index
    assert index["task"] == dashboard.TASK
    assert index["generated_at"] == dashboard.GENERATED_AT
    assert index["adapter_card_count"] == 5
    assert index["subset_card_count"] == 31
    assert set(index["source_sha256"]) == {relpath for _role, relpath in dashboard.P363_SOURCE_ARTIFACTS}
    scope = index["scope"]
    assert scope["historical_descriptive_evidence_only"] is True
    assert scope["db_opened"] is False
    assert scope["db_written"] is False
    assert scope["adapter_calls"] is False
    assert scope["new_scoring_cohort"] is False
    assert scope["blended_leaderboard"] is False
    assert scope["shape_only_and_blocked_targets_excluded"] is True
    assert index["top_compact_candidates"]


def test_adapter_table_schema(double_run):
    first, _ = double_run
    assert len(first.adapter_rows) == 5
    assert tuple(first.adapter_rows[0]) == dashboard.ADAPTER_TABLE_COLUMNS
    assert tuple(row["display_rank"] for row in first.adapter_rows) == ("1", "2", "3", "4", "5")
    assert first.adapter_rows[0]["adapter_function"] == "adapt_predict_biglotto_echo_mixed_3bet"
    for row in first.adapter_rows:
        assert "Historical descriptive evidence only" in row["caveat"]


def test_subset_table_schema(double_run):
    first, _ = double_run
    assert len(first.subset_rows) == 31
    assert tuple(first.subset_rows[0]) == dashboard.SUBSET_TABLE_COLUMNS
    assert tuple(row["display_rank"] for row in first.subset_rows) == tuple(str(i) for i in range(1, 32))
    assert {row["subset_size"] for row in first.subset_rows} == {"1", "2", "3", "4", "5"}
    full_rows = [row for row in first.subset_rows if row["subset_is_full_cohort"] == "true"]
    assert len(full_rows) == 1
    for row in first.subset_rows:
        assert "no new scoring" in row["caveat"]


def test_html_dashboard_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    html = first.html_text
    assert "<!doctype html>" in html
    assert "Scope / disclaimer banner" in html
    assert "Adapter Table" in html
    assert "Subset Table" in html
    assert "Compact Candidate Section" in html
    assert "Consistency Check Section" in html
    assert "Source Artifact Inventory" in html
    for text in dashboard.DISCLAIMER_LINES:
        assert text in html


def test_cli_generate_command_produces_all_artifacts(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_dashboard",
            "--artifacts-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in result.stdout
    for basename in dashboard.ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()


def test_cli_filter_by_subset_size_works():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_dashboard",
            "--top-subsets",
            "100",
            "--subset-size",
            "2",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    rows = list(csv.DictReader(result.stdout.splitlines()))
    assert len(rows) == 10
    assert {row["subset_size"] for row in rows} == {"2"}


def test_consistency_check_summary_is_present(double_run):
    first, _ = double_run
    summary = first.index["consistency_check_summary"]
    assert summary["total"] == 9
    assert summary["pass"] == 9
    assert summary["fail"] == 0
    assert summary["warning"] == 0
    assert summary["failures"] == []
    assert summary["warnings"] == []


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert first.index == second.index
    assert first.adapter_rows == second.adapter_rows
    assert first.subset_rows == second.subset_rows
    assert first.consistency_rows == second.consistency_rows
    assert first.manifest_rows == second.manifest_rows
    assert first.html_text == second.html_text
    first_paths = dashboard.write_artifacts(first, tmp_path / "first")
    second_paths = dashboard.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_csv_json_html_artifacts_parse_and_readback(tmp_path, double_run):
    first, _ = double_run
    paths = dashboard.write_artifacts(first, tmp_path)
    with open(paths["index"], encoding="utf-8") as handle:
        index = json.load(handle)
    assert index["task"] == dashboard.TASK
    with open(paths["adapter_table"], newline="", encoding="utf-8") as handle:
        adapter_rows = list(csv.DictReader(handle))
    assert len(adapter_rows) == len(first.adapter_rows)
    assert tuple(adapter_rows[0]) == dashboard.ADAPTER_TABLE_COLUMNS
    with open(paths["subset_table"], newline="", encoding="utf-8") as handle:
        subset_rows = list(csv.DictReader(handle))
    assert len(subset_rows) == len(first.subset_rows)
    assert tuple(subset_rows[0]) == dashboard.SUBSET_TABLE_COLUMNS
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        manifest_rows = list(csv.DictReader(handle))
    assert len(manifest_rows) == len(first.manifest_rows)
    assert tuple(manifest_rows[0]) == dashboard.MANIFEST_COLUMNS
    html = paths["html"].read_text(encoding="utf-8")
    assert "P364 Big Lotto no-DB Evidence Dashboard" in html


def test_no_db_import_open_guard(double_run):
    first, _ = double_run
    statement = [row for row in first.manifest_rows if row["artifact_role"] == "no_db_open_write"]
    assert len(statement) == 1
    assert statement[0]["no_db_open_write"] == "YES"
    assert "no DB open/write" in statement[0]["details"]
