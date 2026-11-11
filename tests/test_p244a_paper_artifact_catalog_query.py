"""P244-A result-only paper artifact catalog query tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_artifact_catalog_query as query


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "query_mlb_paper_artifact_catalog.py"
FIXED_TIME = "2026-07-08T00:00:00Z"
REQUIRED_OUTPUTS = (
    "query_summary.json",
    "query_results.csv",
    "query_report.md",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run_query(
    output_dir: Path,
    filters: query.PaperArtifactCatalogQueryFilters | None = None,
) -> query.PaperArtifactCatalogQueryResult:
    return query.query_paper_artifact_catalog(
        output_dir=output_dir,
        filters=filters,
        generated_at_utc=FIXED_TIME,
    )


def _write_fixture_catalog(
    tmp_path: Path,
    rows: list[dict[str, str]],
    *,
    warnings: list[dict[str, str]] | None = None,
    failures: list[dict[str, str]] | None = None,
) -> tuple[Path, Path]:
    catalog_json = tmp_path / "artifact_catalog.json"
    catalog_csv = tmp_path / "artifact_catalog.csv"
    catalog_json.write_text(
        json.dumps(
            {
                "source_files": rows,
                "limitation_labels": list(query.REQUIRED_LIMITATION_LABELS),
                "failures": failures or [],
                "warnings": warnings or [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with catalog_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=query.CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return catalog_json, catalog_csv


def test_query_reads_committed_p243_catalog_and_writes_outputs(tmp_path):
    output_dir = tmp_path / "query"

    result = _run_query(output_dir)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.summary == _json(output_dir / "query_summary.json")
    rows = _csv(output_dir / "query_results.csv")
    assert rows
    assert list(rows[0]) == query.CSV_FIELDNAMES
    markdown = (output_dir / "query_report.md").read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Filters",
        "## Matched Artifact Groups",
        "## Warnings / Failures",
        "## Safety Boundaries",
        "## Not Claims",
    ):
        assert section in markdown


def test_default_query_returns_pass_and_all_catalog_entries(tmp_path):
    result = _run_query(tmp_path / "query")

    assert result.summary["query_status"] == "PASS"
    assert result.summary["matched_entries"] == result.summary["total_catalog_entries"]
    assert result.summary["matched_status_counts"]["PASS"] > 0
    assert result.summary["warning_count"] == 1
    assert result.summary["failure_count"] == 0


def test_filtering_by_artifact_group_returns_only_matching_rows(tmp_path):
    result = _run_query(
        tmp_path / "query",
        query.PaperArtifactCatalogQueryFilters(artifact_groups=("p242_bundle",)),
    )

    assert result.rows
    assert {row["artifact_group"] for row in result.rows} == {"p242_bundle"}
    assert result.summary["matched_groups"] == ["p242_bundle"]


def test_filtering_by_role_status_and_file_type_on_synthetic_fixture(tmp_path):
    rows = [
        {
            "artifact_group": "alpha",
            "relative_path": "report/alpha/a.json",
            "file_type": "json",
            "size_bytes": "10",
            "sha256": "a",
            "detected_role": "manifest",
            "status": "PASS",
            "notes": "sha256 recorded",
        },
        {
            "artifact_group": "beta",
            "relative_path": "report/beta/b.csv",
            "file_type": "csv",
            "size_bytes": "20",
            "sha256": "b",
            "detected_role": "status",
            "status": "WARN",
            "notes": "empty forbidden fields: pnl_units",
        },
    ]
    catalog_json, catalog_csv = _write_fixture_catalog(
        tmp_path,
        rows,
        warnings=[
            {
                "check_id": "warn",
                "message": "fixture warning",
                "file_path": "report/beta/b.csv",
                "observed": "[]",
            }
        ],
    )

    result = query.query_paper_artifact_catalog(
        catalog_json=catalog_json,
        catalog_csv=catalog_csv,
        output_dir=tmp_path / "query",
        generated_at_utc=FIXED_TIME,
        filters=query.PaperArtifactCatalogQueryFilters(
            file_types=("csv",),
            detected_roles=("status",),
            statuses=("WARN",),
        ),
    )

    assert [row["relative_path"] for row in result.rows] == ["report/beta/b.csv"]
    assert result.summary["matched_status_counts"] == {"WARN": 1}


def test_only_warnings_surfaces_existing_p237_pnl_units_warning(tmp_path):
    result = _run_query(
        tmp_path / "query",
        query.PaperArtifactCatalogQueryFilters(only_warnings=True),
    )

    assert result.summary["query_status"] == "PASS"
    assert result.summary["matched_entries"] == 1
    assert result.rows[0]["relative_path"] == "report/p237a_paper_strategy_decisions.csv"
    assert result.rows[0]["status"] == "WARN"
    assert "pnl_units" in result.rows[0]["notes"]


def test_empty_query_results_are_deterministic_and_non_crashing(tmp_path):
    output_dir = tmp_path / "query"
    filters = query.PaperArtifactCatalogQueryFilters(artifact_groups=("missing_group",))

    first = query.query_paper_artifact_catalog(
        output_dir=output_dir,
        filters=filters,
        generated_at_utc=FIXED_TIME,
    )
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = query.query_paper_artifact_catalog(
        output_dir=output_dir,
        filters=filters,
        generated_at_utc=FIXED_TIME,
    )

    assert first.summary["query_status"] == "PASS"
    assert first.summary["matched_entries"] == 0
    assert second.summary["matched_entries"] == 0
    assert first_hashes == {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}


def test_missing_or_corrupt_catalog_input_fails_clearly(tmp_path):
    with pytest.raises(query.PaperArtifactCatalogQueryError, match="MISSING_INPUT"):
        query.query_paper_artifact_catalog(
            catalog_json=tmp_path / "missing.json",
            catalog_csv=query.DEFAULT_CATALOG_CSV,
            output_dir=tmp_path / "query",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_json = tmp_path / "corrupt.json"
    corrupt_json.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(query.PaperArtifactCatalogQueryError, match="CORRUPT_INPUT"):
        query.query_paper_artifact_catalog(
            catalog_json=corrupt_json,
            catalog_csv=query.DEFAULT_CATALOG_CSV,
            output_dir=tmp_path / "query",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_csv = tmp_path / "corrupt.csv"
    corrupt_csv.write_text("relative_path,status\nx,PASS\n", encoding="utf-8")
    with pytest.raises(query.PaperArtifactCatalogQueryError, match="missing required columns"):
        query.query_paper_artifact_catalog(
            catalog_json=query.DEFAULT_CATALOG_JSON,
            catalog_csv=corrupt_csv,
            output_dir=tmp_path / "query",
            generated_at_utc=FIXED_TIME,
        )


def test_query_does_not_mutate_p237_to_p243_source_artifacts(tmp_path):
    guarded = [
        ROOT / "report" / "p243a_paper_artifact_catalog" / "artifact_catalog.json",
        ROOT / "report" / "p243a_paper_artifact_catalog" / "artifact_catalog.csv",
        ROOT / "report" / "p243a_paper_artifact_catalog" / "artifact_catalog.md",
    ]
    catalog_payload = _json(guarded[0])
    guarded.extend(ROOT / item["relative_path"] for item in catalog_payload["source_files"])
    before = {path: _digest(path) for path in guarded}

    result = _run_query(tmp_path / "query")

    assert result.summary["query_status"] == "PASS"
    assert before == {path: _digest(path) for path in before}


def test_output_json_csv_and_markdown_are_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "query"

    first = _run_query(output_dir)
    assert first.summary["query_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_query(output_dir)

    assert second.summary["query_status"] == "PASS"
    assert first_hashes == {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}


def test_cli_query_builds_outputs(tmp_path):
    output_dir = tmp_path / "query"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-dir",
            str(output_dir),
            "--include-warnings",
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert _json(output_dir / "query_summary.json")["query_status"] == "PASS"
