"""P242-A isolated paper workflow bundle tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_strategy_workflow_bundle as bundle


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_mlb_paper_strategy_workflow_bundle.py"
FIXED_TIME = "2026-07-08T00:00:00Z"
P239_DIR = ROOT / "report" / "p239a_paper_strategy_workflow"
P240_DIR = ROOT / "report" / "p240a_paper_strategy_workflow_inspector"
P241_DIR = ROOT / "report" / "p241a_paper_strategy_workflow_review_pack"
P239_FILES = (
    "workflow_summary.json",
    "workflow_manifest.json",
    "decisions.csv",
    "learning_summary.json",
    "learning_segments.csv",
)
P240_FILES = ("inspection_summary.json", "inspection_checks.csv")
P241_FILES = ("review_summary.json", "review_artifacts.csv", "review_report.md")
REQUIRED_OUTPUTS = (
    "bundle_summary.json",
    "bundle_manifest.json",
    "workflow/decisions.csv",
    "workflow/learning_summary.json",
    "workflow/learning_segments.csv",
    "workflow/workflow_summary.json",
    "workflow/workflow_manifest.json",
    "inspection/inspection_summary.json",
    "inspection/inspection_checks.csv",
    "review/review_summary.json",
    "review/review_artifacts.csv",
    "review/review_report.md",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rewrite_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_source(path: Path) -> None:
    fieldnames = [
        "game_id",
        "game_date",
        "home_team",
        "away_team",
        "line_value",
        "model_name",
        "predicted_home_probability",
        "predicted_side",
        "predicted_side_probability",
        "actual_side",
        "correct",
    ]
    rows = [
        {
            "game_id": "g1",
            "game_date": "2025-07-01",
            "home_team": "Home A",
            "away_team": "Away A",
            "line_value": "-1.5",
            "model_name": "poisson_team_rate_model",
            "predicted_home_probability": "0.60",
            "predicted_side": "HOME",
            "predicted_side_probability": "0.60",
            "actual_side": "HOME",
            "correct": "1",
        },
        {
            "game_id": "g2",
            "game_date": "2025-07-02",
            "home_team": "Home B",
            "away_team": "Away B",
            "line_value": "1.5",
            "model_name": "poisson_team_rate_model",
            "predicted_home_probability": "0.30",
            "predicted_side": "AWAY",
            "predicted_side_probability": "0.70",
            "actual_side": "HOME",
            "correct": "0",
        },
        {
            "game_id": "g3",
            "game_date": "2025-07-03",
            "home_team": "Home C",
            "away_team": "Away C",
            "line_value": "-1.5",
            "model_name": "poisson_team_rate_model",
            "predicted_home_probability": "0.80",
            "predicted_side": "HOME",
            "predicted_side_probability": "0.80",
            "actual_side": "AWAY",
            "correct": "0",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _run_bundle(source_csv: Path, output_dir: Path) -> bundle.PaperWorkflowBundleResult:
    return bundle.run_bundle_or_raise(
        source_csv=source_csv,
        output_dir=output_dir,
        min_confidence=0.6,
        thresholds=(0.5, 0.6, 0.7),
        generated_at_utc=FIXED_TIME,
    )


def _run_cli(source_csv: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-csv",
            str(source_csv),
            "--output-dir",
            str(output_dir),
            "--min-confidence",
            "0.6",
            "--thresholds",
            "0.5,0.6,0.7",
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_bundle_runner_creates_isolated_subdirs_and_required_outputs(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "bundle"
    _write_source(source)

    result = _run_bundle(source, output_dir)

    assert (output_dir / "workflow").is_dir()
    assert (output_dir / "inspection").is_dir()
    assert (output_dir / "review").is_dir()
    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.summary == _json(output_dir / "bundle_summary.json")


def test_bundle_summary_reports_pass_when_nested_statuses_pass(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "bundle"
    _write_source(source)

    summary = _run_bundle(source, output_dir).summary

    assert summary["bundle_status"] == "PASS"
    assert summary["workflow_status"] == "RESULT_ONLY_PAPER_WORKFLOW"
    assert summary["inspection_overall_status"] == "PASS"
    assert summary["review_status"] == "PASS"
    assert summary["decisions_count"] == 3
    assert summary["learning_segments_count"] > 0
    assert summary["roi_status"] == "ROI_UNAVAILABLE"
    assert summary["generates_new_predictions"] is False
    assert summary["failures"] == []


def test_bundle_manifest_records_output_paths_and_sha256_values(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "bundle"
    _write_source(source)
    _run_bundle(source, output_dir)

    manifest = _json(output_dir / "bundle_manifest.json")
    assert manifest["inputs"] == [
        {"name": "source_csv", "path": str(source), "sha256": _digest(source)}
    ]
    assert manifest["no_side_effects"] == {
        "no_db_writes": True,
        "no_provider_api_calls": True,
        "no_remote_fetch": True,
        "no_pybaseball": True,
        "no_live_output": True,
        "no_real_betting": True,
        "no_sports_api_calls": True,
    }
    outputs = {item["name"]: item for item in manifest["outputs"]}
    for name in REQUIRED_OUTPUTS:
        assert name in outputs
        assert outputs[name]["path"] == str(output_dir / name)
        if name == "bundle_manifest.json":
            assert outputs[name]["sha256"] is None
            assert outputs[name]["sha256_status"] == "SELF_HASH_NOT_EMBEDDED"
        else:
            assert outputs[name]["sha256"] == _digest(output_dir / name)


def test_p240_and_p241_read_isolated_p242_subdirectories(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "bundle"
    _write_source(source)
    _run_bundle(source, output_dir)

    inspection_summary = _json(output_dir / "inspection" / "inspection_summary.json")
    review_summary = _json(output_dir / "review" / "review_summary.json")
    assert inspection_summary["workflow_dir"] == str(output_dir / "workflow")
    assert all(str(output_dir / "workflow") in path for path in inspection_summary["inspected_files"])
    assert review_summary["workflow_dir"] == str(output_dir / "workflow")
    assert review_summary["inspection_dir"] == str(output_dir / "inspection")
    assert {
        item["path"].split("/")[-2] for item in review_summary["source_files"]
    } == {"workflow", "inspection"}


def test_forbidden_field_audit_fails_for_synthetic_bundle_outputs(tmp_path, monkeypatch):
    source = tmp_path / "source.csv"
    source.write_text("synthetic\n", encoding="utf-8")
    output_dir = tmp_path / "bundle"
    workflow_dir = output_dir / "workflow"
    inspection_dir = output_dir / "inspection"
    review_dir = output_dir / "review"

    def fake_workflow(**kwargs):
        workflow_dir.mkdir(parents=True, exist_ok=True)
        (workflow_dir / "decisions.csv").write_text("game_id,pnl_units\n1,\n", encoding="utf-8")
        (workflow_dir / "learning_segments.csv").write_text("segment_type,roi_status\nx,ROI_UNAVAILABLE\n", encoding="utf-8")
        _rewrite_json(
            workflow_dir / "learning_summary.json",
            {
                "segments_count": 1,
                "EV": 0.01,
                "kelly": 0.0,
                "recommended_bet": "FORBIDDEN",
                "roi_status": "ROI_UNAVAILABLE",
                "generates_new_predictions": False,
                "limitation_labels": list(bundle.REQUIRED_LIMITATION_LABELS),
            },
        )
        summary = {
            "workflow_status": "RESULT_ONLY_PAPER_WORKFLOW",
            "decisions_count": 1,
            "learning_segments_count": 1,
            "roi_status": "ROI_UNAVAILABLE",
            "generates_new_predictions": False,
            "limitation_labels": list(bundle.REQUIRED_LIMITATION_LABELS),
        }
        _rewrite_json(workflow_dir / "workflow_summary.json", summary)
        _rewrite_json(workflow_dir / "workflow_manifest.json", {"outputs": []})
        return bundle.PaperWorkflowBundleResult(summary, {}, {}, {})

    def fake_inspection(**kwargs):
        inspection_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "overall_status": "PASS",
            "failures": [],
            "warnings": [],
        }
        _rewrite_json(inspection_dir / "inspection_summary.json", summary)
        (inspection_dir / "inspection_checks.csv").write_text(
            "check_id,status\nsynthetic,PASS\n", encoding="utf-8"
        )
        return bundle.PaperWorkflowBundleResult(summary, {}, {}, {})

    def fake_review(**kwargs):
        review_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "review_status": "PASS",
            "failures": [],
            "warnings": [],
        }
        _rewrite_json(review_dir / "review_summary.json", summary)
        (review_dir / "review_artifacts.csv").write_text(
            "artifact_type,status\nsynthetic,PASS\n", encoding="utf-8"
        )
        (review_dir / "review_report.md").write_text("# Synthetic Review\n", encoding="utf-8")
        return bundle.PaperWorkflowBundleResult(summary, {}, {}, {})

    monkeypatch.setattr(bundle, "run_paper_strategy_workflow", fake_workflow)
    monkeypatch.setattr(bundle, "inspect_paper_strategy_workflow", fake_inspection)
    monkeypatch.setattr(bundle, "build_paper_strategy_workflow_review_pack", fake_review)

    result = bundle.run_paper_strategy_workflow_bundle(
        source_csv=source,
        output_dir=output_dir,
        min_confidence=0.5,
        thresholds=(0.5,),
        generated_at_utc=FIXED_TIME,
    )

    assert result.summary["bundle_status"] == "FAIL"
    observed = "\n".join(failure["observed"] for failure in result.summary["failures"])
    assert "pnl_units" in observed
    assert "$.EV" in observed
    assert "$.kelly" in observed
    assert "$.recommended_bet" in observed


def test_required_limitation_labels_and_no_new_predictions_are_present(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "bundle"
    _write_source(source)

    summary = _run_bundle(source, output_dir).summary

    for label in bundle.REQUIRED_LIMITATION_LABELS:
        assert label in summary["limitation_labels"]
    assert summary["generates_new_predictions"] is False


def test_bundle_runner_does_not_mutate_committed_p239_p240_p241_artifact_dirs(tmp_path):
    tracked = {
        **{P239_DIR / filename: _digest(P239_DIR / filename) for filename in P239_FILES},
        **{P240_DIR / filename: _digest(P240_DIR / filename) for filename in P240_FILES},
        **{P241_DIR / filename: _digest(P241_DIR / filename) for filename in P241_FILES},
    }
    source = tmp_path / "source.csv"
    _write_source(source)

    result = _run_bundle(source, tmp_path / "bundle")

    assert result.summary["bundle_status"] == "PASS"
    assert tracked == {path: _digest(path) for path in tracked}


def test_output_json_csv_and_markdown_are_deterministic_with_fixed_generated_at(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "bundle"
    _write_source(source)

    first = _run_cli(source, output_dir)
    assert first.returncode == 0, first.stderr
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_cli(source, output_dir)
    assert second.returncode == 0, second.stderr
    second_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    assert first_hashes == second_hashes


def test_cli_exits_nonzero_when_intermediate_inspection_fails(tmp_path):
    source = tmp_path / "source.csv"
    _write_source(source)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-csv",
            str(source),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--min-confidence",
            "0.49",
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "min-confidence" in result.stderr
