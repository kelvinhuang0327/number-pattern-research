"""P253-A result-only paper toolchain pack integrity verifier tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_toolchain_pack_integrity as integrity


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_mlb_paper_toolchain_pack_integrity.py"
FIXED_TIME = "2026-07-09T00:00:00Z"
REQUIRED_OUTPUTS = (
    "integrity_summary.json",
    "integrity_checks.csv",
    "integrity_report.md",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run_integrity(output_dir: Path, **kwargs) -> integrity.PaperToolchainPackIntegrityResult:
    return integrity.build_paper_toolchain_pack_integrity(
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
        **kwargs,
    )


def _write_manifest_fixture(
    base: Path,
    *,
    relative_path: str = "pack/sample.txt",
    expected_sha256: str | None = None,
    target_exists: str = "True",
    statuses: dict[str, str] | None = None,
) -> dict[str, Path]:
    target = base / relative_path
    if not relative_path.startswith("/") and ".." not in relative_path and "://" not in relative_path:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("sample payload\n", encoding="utf-8")

    digest = expected_sha256 if expected_sha256 is not None else _digest(target)
    summary_path = base / "operator_pack_summary.json"
    files_path = base / "operator_pack_files.csv"
    payload = {
        "operator_pack_status": "PASS",
        "dashboard_status": "PASS",
        "index_status": "PASS",
        "cli_help_smoke_status": "PASS",
        "quickstart_status": "PASS",
        "file_count": 1,
    }
    if statuses:
        payload.update(statuses)
    summary_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with files_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "file_id",
                "category",
                "title",
                "relative_path",
                "target_exists",
                "sha256",
                "source_artifact",
                "safe_to_view",
                "notes",
            ]
        )
        writer.writerow(
            [
                "sample",
                "fixture",
                "Sample",
                relative_path,
                target_exists,
                digest,
                "fixture",
                "True",
                "",
            ]
        )
    return {
        "operator_pack_summary_json": summary_path,
        "operator_pack_files_csv": files_path,
    }


def test_default_integrity_produces_json_csv_and_markdown_outputs(tmp_path):
    output_dir = tmp_path / "integrity"

    result = _run_integrity(output_dir)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.summary == _json(output_dir / "integrity_summary.json")
    rows = _csv(output_dir / "integrity_checks.csv")
    assert len(rows) == len(result.check_rows)
    assert list(rows[0]) == integrity.CHECK_CSV_FIELDNAMES
    markdown = (output_dir / "integrity_report.md").read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Integrity Checks",
        "## Hash Matches",
        "## Missing / Unsafe / Mismatch Findings",
        "## Status Snapshot",
        "## Safety Boundaries",
        "## Limitations",
        "## Not Claims",
    ):
        assert section in markdown


def test_default_integrity_returns_pass_over_current_committed_p252_artifacts(tmp_path):
    payload = _run_integrity(tmp_path / "integrity").summary

    assert payload["integrity_status"] == "PASS"
    assert payload["operator_pack_status"] == "PASS"
    assert payload["dashboard_status"] == "PASS"
    assert payload["index_status"] == "PASS"
    assert payload["cli_help_smoke_status"] == "PASS"
    assert payload["quickstart_status"] == "PASS"
    assert payload["file_count"] == 12
    assert payload["checked_file_count"] == 12
    assert payload["hash_match_count"] == 12
    assert payload["hash_mismatch_count"] == 0
    assert payload["missing_file_count"] == 0
    assert payload["unsafe_path_count"] == 0
    assert payload["warning_count"] == 0
    assert payload["failure_count"] == 0
    assert payload["warnings"] == []
    assert payload["failures"] == []
    for label in integrity.LIMITATION_LABELS:
        assert label in payload["limitation_labels"]
    assert payload["no_side_effects"]["read_existing_p252_artifacts_only"] is True
    assert payload["no_side_effects"]["executed_p239_to_p252_scripts"] is False
    assert payload["no_side_effects"]["executed_operator_scripts"] is False
    assert payload["no_side_effects"]["computed_roi_pnl_ev_kelly"] is False


def test_integrity_checks_csv_contains_safe_repo_local_relative_paths(tmp_path):
    output_dir = tmp_path / "integrity"
    _run_integrity(output_dir)

    rows = _csv(output_dir / "integrity_checks.csv")
    for row in rows:
        assert row["path_safe"] == "True"
        assert row["target_exists"] == "True"
        assert row["hash_matches"] == "True"
        path = row["relative_path"]
        assert not path.startswith("/")
        assert "http://" not in path
        assert "https://" not in path
        assert ".." not in path
        assert len(row["expected_sha256"]) == 64
        assert row["expected_sha256"] == row["actual_sha256"]


def test_missing_input_fails_clearly_without_outputs(tmp_path):
    with pytest.raises(integrity.PaperToolchainPackIntegrityError, match="not found"):
        integrity.build_paper_toolchain_pack_integrity(
            operator_pack_summary_json=tmp_path / "does_not_exist.json",
            operator_pack_files_csv=integrity.DEFAULT_OPERATOR_PACK_FILES_CSV,
            output_dir=tmp_path / "integrity",
            generated_at_utc=FIXED_TIME,
        )


def test_corrupt_summary_json_fails_clearly(tmp_path):
    summary_path = tmp_path / "operator_pack_summary.json"
    files_path = tmp_path / "operator_pack_files.csv"
    summary_path.write_text("{not valid json", encoding="utf-8")
    files_path.write_text("file_id,category,relative_path,target_exists,sha256\n", encoding="utf-8")

    with pytest.raises(integrity.PaperToolchainPackIntegrityError, match="not valid JSON"):
        integrity.build_paper_toolchain_pack_integrity(
            operator_pack_summary_json=summary_path,
            operator_pack_files_csv=files_path,
            output_dir=tmp_path / "integrity",
            generated_at_utc=FIXED_TIME,
            repo_root=tmp_path,
        )


def test_missing_target_makes_integrity_fail(tmp_path):
    paths = _write_manifest_fixture(tmp_path, relative_path="pack/missing.txt")
    (tmp_path / "pack" / "missing.txt").unlink()

    result = integrity.build_paper_toolchain_pack_integrity(
        output_dir=tmp_path / "integrity",
        generated_at_utc=FIXED_TIME,
        repo_root=tmp_path,
        **paths,
    )

    assert result.summary["integrity_status"] == "FAIL"
    assert result.summary["missing_file_count"] == 1
    assert result.summary["failure_count"] > 0
    assert result.check_rows[0]["status"] == "FAIL"
    assert "target file is missing" in result.check_rows[0]["notes"]


def test_unsafe_path_makes_integrity_fail_without_hashing_target(tmp_path):
    paths = _write_manifest_fixture(
        tmp_path,
        relative_path="../outside.txt",
        expected_sha256="0" * 64,
    )

    result = integrity.build_paper_toolchain_pack_integrity(
        output_dir=tmp_path / "integrity",
        generated_at_utc=FIXED_TIME,
        repo_root=tmp_path,
        **paths,
    )

    assert result.summary["integrity_status"] == "FAIL"
    assert result.summary["unsafe_path_count"] == 1
    assert result.check_rows[0]["path_safe"] is False
    assert result.check_rows[0]["actual_sha256"] == ""
    assert "relative_path contains .." in result.check_rows[0]["notes"]


def test_invalid_expected_hash_makes_integrity_fail(tmp_path):
    paths = _write_manifest_fixture(tmp_path, expected_sha256="not-a-sha")

    result = integrity.build_paper_toolchain_pack_integrity(
        output_dir=tmp_path / "integrity",
        generated_at_utc=FIXED_TIME,
        repo_root=tmp_path,
        **paths,
    )

    assert result.summary["integrity_status"] == "FAIL"
    assert result.summary["failure_count"] > 0
    assert "expected_sha256 is not" in result.check_rows[0]["notes"]


def test_hash_mismatch_makes_integrity_fail(tmp_path):
    paths = _write_manifest_fixture(tmp_path, expected_sha256="0" * 64)

    result = integrity.build_paper_toolchain_pack_integrity(
        output_dir=tmp_path / "integrity",
        generated_at_utc=FIXED_TIME,
        repo_root=tmp_path,
        **paths,
    )

    assert result.summary["integrity_status"] == "FAIL"
    assert result.summary["hash_mismatch_count"] == 1
    assert result.check_rows[0]["hash_matches"] is False
    assert "does not match" in result.check_rows[0]["notes"]


def test_non_pass_p252_status_makes_integrity_fail(tmp_path):
    paths = _write_manifest_fixture(tmp_path, statuses={"dashboard_status": "FAIL"})

    result = integrity.build_paper_toolchain_pack_integrity(
        output_dir=tmp_path / "integrity",
        generated_at_utc=FIXED_TIME,
        repo_root=tmp_path,
        **paths,
    )

    assert result.summary["integrity_status"] == "FAIL"
    assert result.summary["dashboard_status"] == "FAIL"
    assert any("dashboard_status" in failure for failure in result.summary["failures"])


def test_output_json_csv_and_markdown_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "integrity"

    first = _run_integrity(output_dir)
    assert first.summary["integrity_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_integrity(output_dir)
    assert second.summary["integrity_status"] == "PASS"
    second_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}

    assert first_hashes == second_hashes


def test_verifier_does_not_mutate_p252_source_artifacts(tmp_path):
    source_files = [
        integrity.DEFAULT_OPERATOR_PACK_SUMMARY_JSON,
        integrity.DEFAULT_OPERATOR_PACK_FILES_CSV,
        ROOT / "report" / "p252a_paper_toolchain_operator_pack" / "operator_pack.md",
    ]
    before = {path: _digest(path) for path in source_files}

    result = _run_integrity(tmp_path / "integrity")

    assert result.summary["integrity_status"] == "PASS"
    after = {path: _digest(path) for path in source_files}
    assert before == after


def test_cli_builds_integrity_outputs_and_exit_code(tmp_path):
    output_dir = tmp_path / "integrity"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-dir",
            str(output_dir),
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert _json(output_dir / "integrity_summary.json")["integrity_status"] == "PASS"


def test_cli_returns_nonzero_for_integrity_failure(tmp_path):
    paths = _write_manifest_fixture(tmp_path, expected_sha256="0" * 64)
    output_dir = tmp_path / "integrity"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--operator-pack-summary-json",
            str(paths["operator_pack_summary_json"]),
            "--operator-pack-files-csv",
            str(paths["operator_pack_files_csv"]),
            "--output-dir",
            str(output_dir),
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert _json(output_dir / "integrity_summary.json")["integrity_status"] == "FAIL"


def test_cli_rejects_missing_input_with_nonzero_exit(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--operator-pack-summary-json",
            str(tmp_path / "does_not_exist.json"),
            "--output-dir",
            str(tmp_path / "integrity"),
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "not found" in result.stderr
