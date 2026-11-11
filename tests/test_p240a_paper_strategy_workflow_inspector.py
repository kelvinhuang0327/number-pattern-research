"""P240-A read-only paper strategy workflow inspector tests."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_strategy_workflow_inspector as inspector


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect_mlb_paper_strategy_workflow.py"
P239_DIR = ROOT / "report" / "p239a_paper_strategy_workflow"
FIXED_TIME = "2026-07-08T00:00:00Z"
P239_FILES = (
    "workflow_summary.json",
    "workflow_manifest.json",
    "decisions.csv",
    "learning_summary.json",
    "learning_segments.csv",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_checks(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _copy_p239_fixture(tmp_path: Path) -> Path:
    workflow_dir = tmp_path / "workflow"
    shutil.copytree(P239_DIR, workflow_dir)
    return workflow_dir


def _rewrite_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rewrite_manifest_hash(workflow_dir: Path, output_name: str, target_file: str) -> None:
    manifest_path = workflow_dir / "workflow_manifest.json"
    manifest = _json(manifest_path)
    for item in manifest["outputs"]:
        if item["name"] == output_name:
            item["sha256"] = _digest(workflow_dir / target_file)
            break
    _rewrite_json(manifest_path, manifest)


def _run_cli(workflow_dir: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--workflow-dir",
            str(workflow_dir),
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


def test_inspector_reads_committed_p239_and_writes_summary_and_checks(tmp_path):
    output_dir = tmp_path / "inspection"
    result = inspector.inspect_paper_strategy_workflow(
        workflow_dir=P239_DIR,
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
    )

    summary_path = output_dir / "inspection_summary.json"
    checks_path = output_dir / "inspection_checks.csv"
    assert summary_path.is_file()
    assert checks_path.is_file()
    summary = _json(summary_path)
    assert result.summary == summary
    assert summary["overall_status"] == "PASS"
    assert summary["workflow_dir"] == "report/p239a_paper_strategy_workflow"
    assert summary["generated_at_utc"] == FIXED_TIME
    assert summary["decisions_count"] == 25
    assert summary["learning_segments_count"] == 18

    with checks_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == inspector.CHECK_FIELDNAMES
        checks = list(reader)
    assert checks
    assert {row["status"] for row in checks} == {"PASS"}


def test_manifest_hash_verification_passes_on_committed_p239_artifacts(tmp_path):
    result = inspector.inspect_paper_strategy_workflow(
        workflow_dir=P239_DIR,
        output_dir=tmp_path / "inspection",
        generated_at_utc=FIXED_TIME,
    )

    assert result.summary["manifest_hash_check_status"] == "PASS"
    checks = {row["check_id"]: row for row in result.checks}
    assert checks["manifest.decisions_csv.sha256"]["status"] == "PASS"
    assert checks["manifest.learning_summary_json.sha256"]["status"] == "PASS"
    assert checks["manifest.learning_segments_csv.sha256"]["status"] == "PASS"
    assert checks["manifest.workflow_summary_json.sha256"]["status"] == "PASS"
    assert checks["manifest.workflow_manifest_json.self_hash_marker"]["status"] == "PASS"
    assert result.summary["inspected_file_sha256"][
        "report/p239a_paper_strategy_workflow/workflow_manifest.json"
    ] == _digest(P239_DIR / "workflow_manifest.json")


def test_forbidden_field_audit_fails_for_synthetic_pnl_ev_kelly_or_recommendation_fields(tmp_path):
    workflow_dir = _copy_p239_fixture(tmp_path)

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
    _rewrite_manifest_hash(workflow_dir, "decisions_csv", "decisions.csv")
    _rewrite_manifest_hash(workflow_dir, "learning_summary_json", "learning_summary.json")

    result = inspector.inspect_paper_strategy_workflow(
        workflow_dir=workflow_dir,
        output_dir=tmp_path / "inspection",
        generated_at_utc=FIXED_TIME,
    )

    assert result.summary["overall_status"] == "FAIL"
    assert result.summary["forbidden_field_check_status"] == "FAIL"
    failed = {row["check_id"]: row for row in result.checks if row["status"] == "FAIL"}
    assert "forbidden_fields.decisions.csv" in failed
    assert "pnl_units" in failed["forbidden_fields.decisions.csv"]["observed"]
    assert "forbidden_fields.learning_summary.json" in failed
    assert "recommended_bet" in failed["forbidden_fields.learning_summary.json"]["observed"]


def test_required_limitation_labels_and_no_new_predictions_are_verified(tmp_path):
    workflow_dir = _copy_p239_fixture(tmp_path)
    summary_path = workflow_dir / "workflow_summary.json"
    summary = _json(summary_path)
    summary["generates_new_predictions"] = True
    summary["limitation_labels"] = [
        label for label in summary["limitation_labels"] if label != "historical paper-only"
    ]
    _rewrite_json(summary_path, summary)
    _rewrite_manifest_hash(workflow_dir, "workflow_summary_json", "workflow_summary.json")

    result = inspector.inspect_paper_strategy_workflow(
        workflow_dir=workflow_dir,
        output_dir=tmp_path / "inspection",
        generated_at_utc=FIXED_TIME,
    )

    assert result.summary["overall_status"] == "FAIL"
    assert result.summary["limitation_label_check_status"] == "FAIL"
    failed = {row["check_id"]: row for row in result.checks if row["status"] == "FAIL"}
    assert "contract.limitation_labels.workflow_summary.json" in failed
    assert "historical paper-only" in failed[
        "contract.limitation_labels.workflow_summary.json"
    ]["observed"]
    assert failed["contract.generates_new_predictions_false"]["status"] == "FAIL"


def test_missing_or_corrupt_workflow_manifest_fails_clearly(tmp_path):
    workflow_dir = _copy_p239_fixture(tmp_path)
    (workflow_dir / "workflow_manifest.json").unlink()
    with pytest.raises(inspector.PaperWorkflowInspectorError, match="MISSING_INPUT"):
        inspector.inspect_paper_strategy_workflow(
            workflow_dir=workflow_dir,
            output_dir=tmp_path / "missing-inspection",
            generated_at_utc=FIXED_TIME,
        )

    workflow_dir = _copy_p239_fixture(tmp_path / "corrupt")
    (workflow_dir / "workflow_manifest.json").write_text("{bad json\n", encoding="utf-8")
    with pytest.raises(inspector.PaperWorkflowInspectorError, match="CORRUPT_INPUT"):
        inspector.inspect_paper_strategy_workflow(
            workflow_dir=workflow_dir,
            output_dir=tmp_path / "corrupt-inspection",
            generated_at_utc=FIXED_TIME,
        )


def test_inspector_does_not_mutate_p239_workflow_files(tmp_path):
    before = {filename: _digest(P239_DIR / filename) for filename in P239_FILES}
    result = inspector.inspect_paper_strategy_workflow(
        workflow_dir=P239_DIR,
        output_dir=tmp_path / "inspection",
        generated_at_utc=FIXED_TIME,
    )
    assert result.summary["overall_status"] == "PASS"
    assert before == {filename: _digest(P239_DIR / filename) for filename in P239_FILES}


def test_output_json_and_csv_are_deterministic_with_fixed_generated_at(tmp_path):
    workflow_dir = _copy_p239_fixture(tmp_path)
    output_dir = tmp_path / "inspection"

    first = _run_cli(workflow_dir, output_dir)
    assert first.returncode == 0, first.stderr
    first_hashes = {
        filename: _digest(output_dir / filename)
        for filename in ("inspection_summary.json", "inspection_checks.csv")
    }
    second = _run_cli(workflow_dir, output_dir)
    assert second.returncode == 0, second.stderr
    second_hashes = {
        filename: _digest(output_dir / filename)
        for filename in ("inspection_summary.json", "inspection_checks.csv")
    }
    assert first_hashes == second_hashes


def test_cli_exits_nonzero_on_invalid_workflow_dir(tmp_path):
    result = _run_cli(tmp_path / "missing-workflow", tmp_path / "inspection")
    assert result.returncode != 0
    assert "MISSING_INPUT: workflow dir not found" in result.stderr


def test_inspection_checks_csv_uses_stable_column_order(tmp_path):
    result = inspector.inspect_paper_strategy_workflow(
        workflow_dir=P239_DIR,
        output_dir=tmp_path / "inspection",
        generated_at_utc=FIXED_TIME,
    )
    checks = _read_checks(tmp_path / "inspection" / "inspection_checks.csv")
    assert checks
    assert tuple(result.checks[0].keys()) == tuple(inspector.CHECK_FIELDNAMES)
