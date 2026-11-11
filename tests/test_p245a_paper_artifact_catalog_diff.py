"""P245-A result-only paper artifact catalog diff tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_artifact_catalog_diff as diff


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diff_mlb_paper_artifact_catalogs.py"
FIXED_TIME = "2026-07-08T00:00:00Z"
REQUIRED_OUTPUTS = (
    "diff_summary.json",
    "diff_entries.csv",
    "diff_report.md",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run_diff(output_dir: Path, **kwargs) -> diff.PaperArtifactCatalogDiffResult:
    return diff.diff_paper_artifact_catalogs(
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
        **kwargs,
    )


def _committed_rows() -> list[dict[str, str]]:
    return _csv(diff.DEFAULT_BASELINE_CATALOG_CSV)


def _write_fixture_catalog(
    tmp_path: Path,
    rows: list[dict[str, str]],
    *,
    name: str,
) -> tuple[Path, Path]:
    catalog_json = tmp_path / f"{name}_artifact_catalog.json"
    catalog_csv = tmp_path / f"{name}_artifact_catalog.csv"
    catalog_json.write_text(
        json.dumps(
            {
                "source_files": rows,
                "limitation_labels": list(diff.REQUIRED_LIMITATION_LABELS),
                "failures": [],
                "warnings": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with catalog_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=diff.CATALOG_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return catalog_json, catalog_csv


def _diff_fixture(
    tmp_path: Path,
    baseline_rows: list[dict[str, str]],
    current_rows: list[dict[str, str]],
    **kwargs,
) -> diff.PaperArtifactCatalogDiffResult:
    baseline_json, baseline_csv = _write_fixture_catalog(tmp_path, baseline_rows, name="baseline")
    current_json, current_csv = _write_fixture_catalog(tmp_path, current_rows, name="current")
    return diff.diff_paper_artifact_catalogs(
        baseline_catalog_json=baseline_json,
        baseline_catalog_csv=baseline_csv,
        current_catalog_json=current_json,
        current_catalog_csv=current_csv,
        output_dir=tmp_path / "diff",
        generated_at_utc=FIXED_TIME,
        **kwargs,
    )


def test_diff_reads_committed_p243_catalog_and_writes_outputs(tmp_path):
    output_dir = tmp_path / "diff"

    result = _run_diff(output_dir, include_unchanged=True)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.summary == _json(output_dir / "diff_summary.json")
    rows = _csv(output_dir / "diff_entries.csv")
    assert rows
    assert list(rows[0]) == diff.DIFF_CSV_FIELDNAMES
    markdown = (output_dir / "diff_report.md").read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Inputs",
        "## Diff Counts",
        "## Changed Artifacts",
        "## Warnings / Failures",
        "## Safety Boundaries",
        "## Not Claims",
    ):
        assert section in markdown


def test_default_self_compare_returns_pass_and_26_unchanged(tmp_path):
    result = _run_diff(tmp_path / "diff")

    assert result.summary["diff_status"] == "PASS"
    assert result.summary["baseline_entry_count"] == 26
    assert result.summary["current_entry_count"] == 26
    assert result.summary["unchanged_count"] == 26
    assert result.summary["added_count"] == 0
    assert result.summary["removed_count"] == 0
    assert result.summary["changed_count"] == 0


def test_synthetic_added_artifact_is_detected(tmp_path):
    baseline_rows = _committed_rows()
    current_rows = baseline_rows + [
        {
            "artifact_group": "fixture",
            "relative_path": "report/fixture/added.json",
            "file_type": "json",
            "size_bytes": "1",
            "sha256": "added",
            "detected_role": "status",
            "status": "PASS",
            "notes": "sha256 recorded",
        }
    ]

    result = _diff_fixture(tmp_path, baseline_rows, current_rows)

    assert result.summary["diff_status"] == "WARN"
    assert result.summary["added_count"] == 1
    assert result.rows[0]["change_type"] == "added"
    assert result.rows[0]["relative_path"] == "report/fixture/added.json"


def test_synthetic_removed_artifact_is_detected(tmp_path):
    baseline_rows = _committed_rows()
    current_rows = baseline_rows[1:]

    result = _diff_fixture(tmp_path, baseline_rows, current_rows)

    assert result.summary["diff_status"] == "WARN"
    assert result.summary["removed_count"] == 1
    assert result.rows[0]["change_type"] == "removed"
    assert result.rows[0]["relative_path"] == baseline_rows[0]["relative_path"]


def test_synthetic_hash_changed_artifact_is_detected(tmp_path):
    baseline_rows = _committed_rows()
    current_rows = [dict(row) for row in baseline_rows]
    current_rows[0]["sha256"] = "changed-hash"

    result = _diff_fixture(tmp_path, baseline_rows, current_rows)

    assert result.summary["diff_status"] == "WARN"
    assert result.summary["changed_count"] == 1
    assert result.summary["hash_changed_count"] == 1
    assert result.rows[0]["change_type"] == "hash-changed"


def test_synthetic_status_role_file_type_and_notes_changes_are_detected(tmp_path):
    baseline_rows = _committed_rows()
    current_rows = [dict(row) for row in baseline_rows]
    current_rows[0]["status"] = "FAIL"
    current_rows[0]["detected_role"] = "manifest"
    current_rows[0]["file_type"] = "md"
    current_rows[0]["notes"] = "changed note"

    result = _diff_fixture(tmp_path, baseline_rows, current_rows)

    assert result.summary["diff_status"] == "WARN"
    assert result.summary["changed_count"] == 1
    assert result.summary["status_changed_count"] == 1
    assert result.summary["role_changed_count"] == 1
    assert result.summary["file_type_changed_count"] == 1
    assert result.summary["notes_changed_count"] == 1
    assert result.rows[0]["field_changes"] == (
        "status-changed,role-changed,type-changed,notes-changed"
    )


def test_fail_on_changes_turns_detected_changes_into_fail(tmp_path):
    baseline_rows = _committed_rows()
    current_rows = [dict(row) for row in baseline_rows]
    current_rows[0]["sha256"] = "changed-hash"

    result = _diff_fixture(tmp_path, baseline_rows, current_rows, fail_on_changes=True)

    assert result.summary["diff_status"] == "FAIL"
    assert result.summary["failure_count"] == 1
    assert result.summary["warning_count"] == 0


def test_missing_or_corrupt_catalog_input_fails_clearly(tmp_path):
    with pytest.raises(diff.PaperArtifactCatalogDiffError, match="MISSING_INPUT"):
        diff.diff_paper_artifact_catalogs(
            baseline_catalog_json=tmp_path / "missing.json",
            baseline_catalog_csv=diff.DEFAULT_BASELINE_CATALOG_CSV,
            current_catalog_json=diff.DEFAULT_CURRENT_CATALOG_JSON,
            current_catalog_csv=diff.DEFAULT_CURRENT_CATALOG_CSV,
            output_dir=tmp_path / "diff",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_json = tmp_path / "corrupt.json"
    corrupt_json.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(diff.PaperArtifactCatalogDiffError, match="CORRUPT_INPUT"):
        diff.diff_paper_artifact_catalogs(
            baseline_catalog_json=corrupt_json,
            baseline_catalog_csv=diff.DEFAULT_BASELINE_CATALOG_CSV,
            current_catalog_json=diff.DEFAULT_CURRENT_CATALOG_JSON,
            current_catalog_csv=diff.DEFAULT_CURRENT_CATALOG_CSV,
            output_dir=tmp_path / "diff",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_csv = tmp_path / "corrupt.csv"
    corrupt_csv.write_text("relative_path,status\nx,PASS\n", encoding="utf-8")
    with pytest.raises(diff.PaperArtifactCatalogDiffError, match="missing required columns"):
        diff.diff_paper_artifact_catalogs(
            baseline_catalog_json=diff.DEFAULT_BASELINE_CATALOG_JSON,
            baseline_catalog_csv=corrupt_csv,
            current_catalog_json=diff.DEFAULT_CURRENT_CATALOG_JSON,
            current_catalog_csv=diff.DEFAULT_CURRENT_CATALOG_CSV,
            output_dir=tmp_path / "diff",
            generated_at_utc=FIXED_TIME,
        )


def test_output_json_csv_and_markdown_are_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "diff"

    first = _run_diff(output_dir, include_unchanged=True)
    assert first.summary["diff_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_diff(output_dir, include_unchanged=True)

    assert second.summary["diff_status"] == "PASS"
    assert first_hashes == {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}


def test_cli_diff_builds_outputs(tmp_path):
    output_dir = tmp_path / "diff"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-dir",
            str(output_dir),
            "--include-unchanged",
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert _json(output_dir / "diff_summary.json")["diff_status"] == "PASS"
