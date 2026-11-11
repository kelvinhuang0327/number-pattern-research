"""P241-A deterministic paper workflow review-pack tests."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_strategy_workflow_review_pack as review_pack


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_paper_strategy_workflow_review_pack.py"
P239_DIR = ROOT / "report" / "p239a_paper_strategy_workflow"
P240_DIR = ROOT / "report" / "p240a_paper_strategy_workflow_inspector"
FIXED_TIME = "2026-07-08T00:00:00Z"
P239_FILES = (
    "workflow_summary.json",
    "workflow_manifest.json",
    "decisions.csv",
    "learning_summary.json",
    "learning_segments.csv",
)
P240_FILES = ("inspection_summary.json", "inspection_checks.csv")
REVIEW_OUTPUTS = ("review_summary.json", "review_artifacts.csv", "review_report.md")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rewrite_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _copy_inputs(tmp_path: Path) -> tuple[Path, Path]:
    workflow_dir = tmp_path / "workflow"
    inspection_dir = tmp_path / "inspection"
    shutil.copytree(P239_DIR, workflow_dir)
    shutil.copytree(P240_DIR, inspection_dir)
    return workflow_dir, inspection_dir


def _run_cli(workflow_dir: Path, inspection_dir: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--workflow-dir",
            str(workflow_dir),
            "--inspection-dir",
            str(inspection_dir),
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


def test_review_pack_reads_committed_artifacts_and_produces_all_outputs(tmp_path):
    output_dir = tmp_path / "review"
    result = review_pack.build_paper_strategy_workflow_review_pack(
        workflow_dir=P239_DIR,
        inspection_dir=P240_DIR,
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
    )

    for filename in REVIEW_OUTPUTS:
        assert (output_dir / filename).is_file()
    summary = _json(output_dir / "review_summary.json")
    assert result.summary == summary
    assert summary["workflow_dir"] == "report/p239a_paper_strategy_workflow"
    assert summary["inspection_dir"] == "report/p240a_paper_strategy_workflow_inspector"
    assert summary["decisions_count"] == 25
    assert summary["learning_segments_count"] == 18
    report_text = (output_dir / "review_report.md").read_text(encoding="utf-8")
    for heading in (
        "## Summary",
        "## Source Artifacts",
        "## Verification Status",
        "## Safety Boundaries",
        "## Limitations",
        "## Not Claims",
    ):
        assert heading in report_text


def test_review_summary_passes_when_p240_inspection_and_required_checks_pass(tmp_path):
    result = review_pack.build_paper_strategy_workflow_review_pack(
        workflow_dir=P239_DIR,
        inspection_dir=P240_DIR,
        output_dir=tmp_path / "review",
        generated_at_utc=FIXED_TIME,
    )

    summary = result.summary
    assert summary["review_status"] == "PASS"
    assert summary["inspection_overall_status"] == "PASS"
    assert summary["manifest_hash_check_status"] == "PASS"
    assert summary["forbidden_field_check_status"] == "PASS"
    assert summary["limitation_label_check_status"] == "PASS"
    assert summary["roi_status"] == "ROI_UNAVAILABLE"
    assert summary["generates_new_predictions"] is False
    assert summary["workflow_status"] == "RESULT_ONLY_PAPER_WORKFLOW"
    assert summary["failures"] == []
    assert summary["warnings"] == []


def test_source_artifact_sha256_values_are_recorded(tmp_path):
    output_dir = tmp_path / "review"
    review_pack.build_paper_strategy_workflow_review_pack(
        workflow_dir=P239_DIR,
        inspection_dir=P240_DIR,
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
    )

    summary = _json(output_dir / "review_summary.json")
    source_files = {item["path"]: item["sha256"] for item in summary["source_files"]}
    assert source_files["report/p239a_paper_strategy_workflow/workflow_summary.json"] == _digest(
        P239_DIR / "workflow_summary.json"
    )
    assert source_files[
        "report/p240a_paper_strategy_workflow_inspector/inspection_summary.json"
    ] == _digest(P240_DIR / "inspection_summary.json")

    with (output_dir / "review_artifacts.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == review_pack.ARTIFACT_FIELDNAMES
        rows = list(reader)
    assert len(rows) == 7
    assert {row["sha256"] for row in rows}


def test_missing_or_corrupt_p240_inspection_summary_fails_clearly(tmp_path):
    workflow_dir, inspection_dir = _copy_inputs(tmp_path)
    (inspection_dir / "inspection_summary.json").write_text("{bad json\n", encoding="utf-8")

    with pytest.raises(review_pack.ReviewPackError, match="CORRUPT_INPUT"):
        review_pack.build_paper_strategy_workflow_review_pack(
            workflow_dir=workflow_dir,
            inspection_dir=inspection_dir,
            output_dir=tmp_path / "review",
            generated_at_utc=FIXED_TIME,
        )

    result = _run_cli(workflow_dir, inspection_dir, tmp_path / "cli-review")
    assert result.returncode != 0
    assert "CORRUPT_INPUT" in result.stderr


def test_forbidden_field_audit_fails_for_pnl_units_ev_kelly_and_recommendation_keys(tmp_path):
    workflow_dir, inspection_dir = _copy_inputs(tmp_path)

    decisions_path = workflow_dir / "decisions.csv"
    with decisions_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    fieldnames.append("pnl_units")
    for row in rows:
        row["pnl_units"] = ""
    with decisions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    learning_summary_path = workflow_dir / "learning_summary.json"
    learning_summary = _json(learning_summary_path)
    learning_summary["EV"] = 0.01
    learning_summary["kelly"] = 0.0
    learning_summary["recommended_bet"] = "FORBIDDEN_SYNTHETIC_FIELD"
    _rewrite_json(learning_summary_path, learning_summary)

    result = review_pack.build_paper_strategy_workflow_review_pack(
        workflow_dir=workflow_dir,
        inspection_dir=inspection_dir,
        output_dir=tmp_path / "review",
        generated_at_utc=FIXED_TIME,
    )

    assert result.summary["review_status"] == "FAIL"
    assert result.summary["forbidden_field_check_status"] == "FAIL"
    failure_ids = {failure["check_id"] for failure in result.summary["failures"]}
    assert "forbidden_fields.p239_decisions" in failure_ids
    assert "forbidden_fields.p239_learning_summary" in failure_ids


def test_required_limitation_labels_and_no_new_predictions_are_verified(tmp_path):
    workflow_dir, inspection_dir = _copy_inputs(tmp_path)
    summary_path = workflow_dir / "workflow_summary.json"
    summary = _json(summary_path)
    summary["generates_new_predictions"] = True
    summary["limitation_labels"] = [
        label for label in summary["limitation_labels"] if label != "2025-only"
    ]
    _rewrite_json(summary_path, summary)

    result = review_pack.build_paper_strategy_workflow_review_pack(
        workflow_dir=workflow_dir,
        inspection_dir=inspection_dir,
        output_dir=tmp_path / "review",
        generated_at_utc=FIXED_TIME,
    )

    assert result.summary["review_status"] == "FAIL"
    assert result.summary["limitation_label_check_status"] == "FAIL"
    assert result.summary["generates_new_predictions"] is False
    failure_ids = {failure["check_id"] for failure in result.summary["failures"]}
    assert "contract.limitation_labels" in failure_ids
    assert "contract.generates_new_predictions" in failure_ids


def test_review_pack_does_not_mutate_p239_or_p240_source_artifacts(tmp_path):
    before_p239 = {filename: _digest(P239_DIR / filename) for filename in P239_FILES}
    before_p240 = {filename: _digest(P240_DIR / filename) for filename in P240_FILES}

    result = review_pack.build_paper_strategy_workflow_review_pack(
        workflow_dir=P239_DIR,
        inspection_dir=P240_DIR,
        output_dir=tmp_path / "review",
        generated_at_utc=FIXED_TIME,
    )

    assert result.summary["review_status"] == "PASS"
    assert before_p239 == {filename: _digest(P239_DIR / filename) for filename in P239_FILES}
    assert before_p240 == {filename: _digest(P240_DIR / filename) for filename in P240_FILES}


def test_output_json_csv_and_markdown_are_deterministic_with_fixed_generated_at(tmp_path):
    workflow_dir, inspection_dir = _copy_inputs(tmp_path)
    output_dir = tmp_path / "review"

    first = _run_cli(workflow_dir, inspection_dir, output_dir)
    assert first.returncode == 0, first.stderr
    first_hashes = {filename: _digest(output_dir / filename) for filename in REVIEW_OUTPUTS}
    second = _run_cli(workflow_dir, inspection_dir, output_dir)
    assert second.returncode == 0, second.stderr
    second_hashes = {filename: _digest(output_dir / filename) for filename in REVIEW_OUTPUTS}
    assert first_hashes == second_hashes
