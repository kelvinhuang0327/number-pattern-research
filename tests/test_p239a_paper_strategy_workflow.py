"""P239-A result-only paper strategy workflow tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_strategy_workflow as workflow
from wbc_backend.recommendation.paper_strategy_simulator import ExplorerError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_mlb_paper_strategy_workflow.py"
FIXED_TIME = "2026-07-08T00:00:00Z"
REQUIRED_OUTPUTS = (
    "decisions.csv",
    "learning_summary.json",
    "learning_segments.csv",
    "workflow_summary.json",
    "workflow_manifest.json",
)
FORBIDDEN_KEYS = {
    "ev",
    "kelly",
    "pnl",
    "profit",
    "bankroll",
    "best_strategy",
    "best_threshold",
    "recommended_bet",
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_normalized_fixture(path: Path, rows: list[dict[str, object]]) -> None:
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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _fixture_rows() -> list[dict[str, object]]:
    return [
        {
            "game_id": "g1",
            "game_date": "2025-07-01",
            "home_team": "Home A",
            "away_team": "Away A",
            "line_value": "-1.5",
            "model_name": "poisson_team_rate_model",
            "predicted_home_probability": 0.6,
            "predicted_side": "HOME",
            "predicted_side_probability": 0.6,
            "actual_side": "HOME",
            "correct": 1,
        },
        {
            "game_id": "g2",
            "game_date": "2025-07-02",
            "home_team": "Home B",
            "away_team": "Away B",
            "line_value": "1.5",
            "model_name": "poisson_team_rate_model",
            "predicted_home_probability": 0.3,
            "predicted_side": "AWAY",
            "predicted_side_probability": 0.7,
            "actual_side": "HOME",
            "correct": 0,
        },
        {
            "game_id": "g3",
            "game_date": "2025-07-03",
            "home_team": "Home C",
            "away_team": "Away C",
            "line_value": "-1.5",
            "model_name": "poisson_team_rate_model",
            "predicted_home_probability": 0.8,
            "predicted_side": "HOME",
            "predicted_side_probability": 0.8,
            "actual_side": "AWAY",
            "correct": 0,
        },
    ]


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


def _json_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).casefold()
            yield from _json_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_keys(child)


def test_cli_and_module_produce_all_required_outputs(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "workflow"
    _write_normalized_fixture(source, _fixture_rows())

    result = _run_cli(source, output_dir)
    assert result.returncode == 0, result.stderr
    for filename in REQUIRED_OUTPUTS:
        assert (output_dir / filename).is_file()

    module_dir = tmp_path / "module-workflow"
    module_result = workflow.run_paper_strategy_workflow(
        source_csv=source,
        output_dir=module_dir,
        min_confidence=0.6,
        thresholds=(0.5, 0.6, 0.7),
        generated_at_utc=FIXED_TIME,
    )
    assert module_result.summary["decisions_count"] == 3
    assert module_result.summary["learning_segments_count"] == len(
        list(csv.DictReader((module_dir / "learning_segments.csv").open(encoding="utf-8")))
    )


def test_workflow_summary_required_fields_and_result_only_labels(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "workflow"
    _write_normalized_fixture(source, _fixture_rows())
    assert _run_cli(source, output_dir).returncode == 0

    summary = _json(output_dir / "workflow_summary.json")
    assert summary["source_csv"] == str(source)
    assert summary["source_sha256"] == _digest(source)
    assert summary["output_dir"] == str(output_dir)
    assert summary["generated_at_utc"] == FIXED_TIME
    assert summary["min_confidence"] == 0.6
    assert summary["thresholds"] == [0.5, 0.6, 0.7]
    assert summary["decisions_count"] == 3
    assert summary["learning_segments_count"] > 0
    assert summary["roi"] is None
    assert summary["roi_status"] == "ROI_UNAVAILABLE"
    assert summary["generates_new_predictions"] is False
    assert summary["workflow_status"] == "RESULT_ONLY_PAPER_WORKFLOW"
    assert summary["interpretation"] == "IN_SAMPLE_DESCRIPTIVE_ONLY"
    for label in workflow.LIMITATION_LABELS:
        assert label in summary["limitation_labels"]


def test_manifest_records_input_output_paths_and_hashes(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "workflow"
    _write_normalized_fixture(source, _fixture_rows())
    assert _run_cli(source, output_dir).returncode == 0

    manifest = _json(output_dir / "workflow_manifest.json")
    assert manifest["inputs"] == [
        {"name": "source_csv", "path": str(source), "sha256": _digest(source)}
    ]
    outputs = {item["name"]: item for item in manifest["outputs"]}
    for name, filename in (
        ("decisions_csv", "decisions.csv"),
        ("learning_summary_json", "learning_summary.json"),
        ("learning_segments_csv", "learning_segments.csv"),
        ("workflow_summary_json", "workflow_summary.json"),
    ):
        assert outputs[name]["path"] == str(output_dir / filename)
        assert outputs[name]["sha256"] == _digest(output_dir / filename)
    assert outputs["workflow_manifest_json"]["path"] == str(output_dir / "workflow_manifest.json")
    assert outputs["workflow_manifest_json"]["sha256"] is None
    assert manifest["side_effects"] == {
        "db_writes": False,
        "provider_calls": False,
        "sports_api_calls": False,
        "live_transport": False,
        "live_output": False,
    }


def test_output_json_trees_do_not_contain_forbidden_keys(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "workflow"
    _write_normalized_fixture(source, _fixture_rows())
    assert _run_cli(source, output_dir).returncode == 0

    for filename in ("learning_summary.json", "workflow_summary.json", "workflow_manifest.json"):
        keys = set(_json_keys(_json(output_dir / filename)))
        assert not (FORBIDDEN_KEYS & keys)
    with (output_dir / "decisions.csv").open(newline="", encoding="utf-8") as handle:
        fieldnames = {name.casefold() for name in (csv.DictReader(handle).fieldnames or [])}
    assert not (FORBIDDEN_KEYS & fieldnames)


def test_workflow_writes_only_inside_specified_output_dir(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "workflow"
    sibling = tmp_path / "sibling.txt"
    _write_normalized_fixture(source, _fixture_rows())
    sibling.write_text("unchanged\n", encoding="utf-8")

    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    assert _run_cli(source, output_dir).returncode == 0
    after = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    expected_new = {Path("workflow") / filename for filename in REQUIRED_OUTPUTS}
    assert after - before == expected_new
    assert sibling.read_text(encoding="utf-8") == "unchanged\n"


def test_workflow_does_not_mutate_existing_p237_p238_report_artifacts(tmp_path):
    tracked = [
        ROOT / "report" / "p237a_paper_strategy_decisions.csv",
        ROOT / "report" / "p238a_paper_strategy_learning_summary.json",
        ROOT / "report" / "p238a_paper_strategy_learning_segments.csv",
    ]
    before = {path: _digest(path) for path in tracked if path.exists()}
    source = tmp_path / "source.csv"
    _write_normalized_fixture(source, _fixture_rows())
    assert _run_cli(source, tmp_path / "workflow").returncode == 0
    assert before == {path: _digest(path) for path in before}


def test_determinism_same_command_same_generated_at_produces_identical_hashes(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "workflow"
    _write_normalized_fixture(source, _fixture_rows())

    assert _run_cli(source, output_dir).returncode == 0
    first = {filename: _digest(output_dir / filename) for filename in REQUIRED_OUTPUTS}
    assert _run_cli(source, output_dir).returncode == 0
    second = {filename: _digest(output_dir / filename) for filename in REQUIRED_OUTPUTS}
    assert first == second


def test_synthetic_fixture_passes_decision_and_learning_segment_counts(tmp_path):
    source = tmp_path / "source.csv"
    output_dir = tmp_path / "workflow"
    _write_normalized_fixture(source, _fixture_rows())
    result = workflow.run_paper_strategy_workflow(
        source_csv=source,
        output_dir=output_dir,
        min_confidence=0.7,
        thresholds=(0.7,),
        generated_at_utc=FIXED_TIME,
    )
    assert result.summary["decisions_count"] == 2
    assert result.summary["learning_segments_count"] == _json(
        output_dir / "learning_summary.json"
    )["segments_count"]


def test_invalid_thresholds_or_min_confidence_fail_clearly(tmp_path):
    source = tmp_path / "source.csv"
    _write_normalized_fixture(source, _fixture_rows())
    with pytest.raises(ExplorerError, match="min-confidence"):
        workflow.run_paper_strategy_workflow(
            source_csv=source,
            output_dir=tmp_path / "bad-confidence",
            min_confidence=0.49,
            generated_at_utc=FIXED_TIME,
        )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-csv",
            str(source),
            "--output-dir",
            str(tmp_path / "bad-threshold"),
            "--thresholds",
            "0.5,1.1",
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "thresholds must be between 0.5 and 1.0" in result.stderr
