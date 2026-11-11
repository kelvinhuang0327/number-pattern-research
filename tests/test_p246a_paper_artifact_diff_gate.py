"""P246-A result-only paper artifact diff gate tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_artifact_diff_gate as gate
from wbc_backend.recommendation import paper_artifact_catalog_diff as diff


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_mlb_paper_artifact_diff.py"
FIXED_TIME = "2026-07-08T00:00:00Z"
REQUIRED_OUTPUTS = (
    "gate_summary.json",
    "gate_checks.csv",
    "gate_report.md",
)
SOURCE_ARTIFACTS = (
    diff.DEFAULT_BASELINE_CATALOG_JSON,
    diff.DEFAULT_BASELINE_CATALOG_CSV,
    gate.DEFAULT_DIFF_SUMMARY,
    gate.DEFAULT_DIFF_ENTRIES,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_diff_fixture(
    tmp_path: Path,
    *,
    summary_overrides: dict | None = None,
    rows: list[dict[str, str]] | None = None,
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    summary = _json(gate.DEFAULT_DIFF_SUMMARY)
    summary.update(summary_overrides or {})
    summary_path = tmp_path / "diff_summary.json"
    entries_path = tmp_path / "diff_entries.csv"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with entries_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=diff.DIFF_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows or [])
    return summary_path, entries_path


def _gate_fixture(
    tmp_path: Path,
    *,
    summary_overrides: dict | None = None,
    rows: list[dict[str, str]] | None = None,
    policy: gate.PaperArtifactDiffGatePolicy | None = None,
) -> gate.PaperArtifactDiffGateResult:
    summary_path, entries_path = _write_diff_fixture(
        tmp_path,
        summary_overrides=summary_overrides,
        rows=rows,
    )
    return gate.gate_paper_artifact_diff(
        diff_summary_path=summary_path,
        diff_entries_path=entries_path,
        output_dir=tmp_path / "gate",
        policy=policy,
        generated_at_utc=FIXED_TIME,
    )


def _changed_row(field_changes: str = "hash-changed") -> dict[str, str]:
    return {
        "change_type": field_changes,
        "artifact_group": "fixture",
        "relative_path": "report/fixture/changed.json",
        "baseline_sha256": "old",
        "current_sha256": "new",
        "baseline_status": "PASS",
        "current_status": "PASS",
        "baseline_detected_role": "status",
        "current_detected_role": "status",
        "baseline_file_type": "json",
        "current_file_type": "json",
        "field_changes": field_changes,
        "notes": "changed fields: " + field_changes,
    }


def test_default_gate_reads_committed_p245_diff_outputs_and_writes_outputs(tmp_path):
    result = gate.gate_paper_artifact_diff(
        output_dir=tmp_path / "gate",
        generated_at_utc=FIXED_TIME,
    )

    for name in REQUIRED_OUTPUTS:
        assert (tmp_path / "gate" / name).is_file()
    assert result.summary == _json(tmp_path / "gate" / "gate_summary.json")
    checks = _csv(tmp_path / "gate" / "gate_checks.csv")
    assert checks
    assert list(checks[0]) == gate.GATE_CHECK_FIELDNAMES
    markdown = (tmp_path / "gate" / "gate_report.md").read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Inputs",
        "## Policy",
        "## Gate Checks",
        "## Warnings / Failures",
        "## Safety Boundaries",
        "## Not Claims",
    ):
        assert section in markdown


def test_default_gate_returns_pass_for_current_committed_self_compare(tmp_path):
    result = gate.gate_paper_artifact_diff(
        output_dir=tmp_path / "gate",
        generated_at_utc=FIXED_TIME,
    )

    assert result.summary["gate_status"] == "PASS"
    assert result.summary["observed_counts"]["added_count"] == 0
    assert result.summary["observed_counts"]["removed_count"] == 0
    assert result.summary["observed_counts"]["changed_count"] == 0
    assert result.summary["warning_count"] == 0
    assert result.summary["failure_count"] == 0


def test_synthetic_added_artifact_exceeds_max_and_fails(tmp_path):
    result = _gate_fixture(tmp_path, summary_overrides={"added_count": 1})

    assert result.summary["gate_status"] == "FAIL"
    assert "threshold.added_count" in result.summary["failed_checks"]


def test_synthetic_removed_artifact_exceeds_max_and_fails(tmp_path):
    result = _gate_fixture(tmp_path, summary_overrides={"removed_count": 1})

    assert result.summary["gate_status"] == "FAIL"
    assert "threshold.removed_count" in result.summary["failed_checks"]


def test_synthetic_changed_artifact_exceeds_max_and_fails(tmp_path):
    result = _gate_fixture(
        tmp_path,
        summary_overrides={"changed_count": 1},
        rows=[_changed_row()],
    )

    assert result.summary["gate_status"] == "FAIL"
    assert "threshold.changed_count" in result.summary["failed_checks"]


def test_synthetic_warning_exceeds_max_and_fails(tmp_path):
    result = _gate_fixture(
        tmp_path,
        summary_overrides={
            "warning_count": 1,
            "warnings": [{"check_id": "fixture.warning", "message": "fixture warning"}],
        },
    )

    assert result.summary["gate_status"] == "FAIL"
    assert "threshold.warning_count" in result.summary["failed_checks"]


def test_synthetic_status_role_file_type_and_notes_changes_fail_unless_allowed(tmp_path):
    changes = "status-changed,role-changed,type-changed,notes-changed"
    overrides = {
        "changed_count": 1,
        "status_changed_count": 1,
        "role_changed_count": 1,
        "file_type_changed_count": 1,
        "notes_changed_count": 1,
    }

    blocked = _gate_fixture(tmp_path, summary_overrides=overrides, rows=[_changed_row(changes)])

    assert blocked.summary["gate_status"] == "FAIL"
    assert "change.status_allowed" in blocked.summary["failed_checks"]
    assert "change.role_allowed" in blocked.summary["failed_checks"]
    assert "change.file_type_allowed" in blocked.summary["failed_checks"]
    assert "change.notes_allowed" in blocked.summary["failed_checks"]

    allowed = _gate_fixture(
        tmp_path / "allowed",
        summary_overrides=overrides,
        rows=[_changed_row(changes)],
        policy=gate.PaperArtifactDiffGatePolicy(
            max_changed=1,
            allow_status_changes=True,
            allow_role_changes=True,
            allow_file_type_changes=True,
            allow_notes_changes=True,
        ),
    )

    assert allowed.summary["gate_status"] == "PASS"


def test_missing_or_corrupt_diff_input_fails_clearly(tmp_path):
    with pytest.raises(gate.PaperArtifactDiffGateError, match="MISSING_INPUT"):
        gate.gate_paper_artifact_diff(
            diff_summary_path=tmp_path / "missing.json",
            diff_entries_path=gate.DEFAULT_DIFF_ENTRIES,
            output_dir=tmp_path / "gate",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_json = tmp_path / "corrupt.json"
    corrupt_json.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(gate.PaperArtifactDiffGateError, match="CORRUPT_INPUT"):
        gate.gate_paper_artifact_diff(
            diff_summary_path=corrupt_json,
            diff_entries_path=gate.DEFAULT_DIFF_ENTRIES,
            output_dir=tmp_path / "gate",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_csv = tmp_path / "corrupt.csv"
    corrupt_csv.write_text("relative_path,status\nx,PASS\n", encoding="utf-8")
    with pytest.raises(gate.PaperArtifactDiffGateError, match="missing required columns"):
        gate.gate_paper_artifact_diff(
            diff_summary_path=gate.DEFAULT_DIFF_SUMMARY,
            diff_entries_path=corrupt_csv,
            output_dir=tmp_path / "gate",
            generated_at_utc=FIXED_TIME,
        )


def test_output_json_csv_and_markdown_are_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "gate"

    first = gate.gate_paper_artifact_diff(output_dir=output_dir, generated_at_utc=FIXED_TIME)
    assert first.summary["gate_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = gate.gate_paper_artifact_diff(output_dir=output_dir, generated_at_utc=FIXED_TIME)

    assert second.summary["gate_status"] == "PASS"
    assert first_hashes == {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}


def test_gate_output_does_not_mutate_p237_p245_source_artifacts(tmp_path):
    before = {path: _digest(path) for path in SOURCE_ARTIFACTS}

    gate.gate_paper_artifact_diff(output_dir=tmp_path / "gate", generated_at_utc=FIXED_TIME)

    assert before == {path: _digest(path) for path in SOURCE_ARTIFACTS}


def test_cli_gate_builds_outputs_and_returns_nonzero_on_fail(tmp_path):
    output_dir = tmp_path / "gate"

    passed = subprocess.run(
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

    assert passed.returncode == 0, passed.stderr
    assert _json(output_dir / "gate_summary.json")["gate_status"] == "PASS"

    summary_path, entries_path = _write_diff_fixture(
        tmp_path / "fail",
        summary_overrides={"added_count": 1},
    )
    failed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--diff-summary",
            str(summary_path),
            "--diff-entries",
            str(entries_path),
            "--output-dir",
            str(tmp_path / "failed_gate"),
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert failed.returncode == 1
    assert _json(tmp_path / "failed_gate" / "gate_summary.json")["gate_status"] == "FAIL"
