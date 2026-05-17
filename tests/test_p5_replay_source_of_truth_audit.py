"""Compatibility tests for the P5 replay source-of-truth audit artifact."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = REPO_ROOT.parent / "LotteryNew" / ".venv" / "bin" / "python3"
P5_JSON = REPO_ROOT / "outputs" / "replay" / "p5_replay_source_of_truth_audit_20260517.json"


def _read_json_or_git(path: Path, git_ref: str) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    rel = str(path.relative_to(REPO_ROOT))
    completed = subprocess.run(
        ["git", "show", f"{git_ref}:{rel}"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def _walk_no_placeholders(value):
    if isinstance(value, dict):
        for item in value.values():
            _walk_no_placeholders(item)
    elif isinstance(value, list):
        for item in value:
            _walk_no_placeholders(item)
    elif isinstance(value, str):
        assert value not in {"TBD", "TODO", "null"}


def test_p5_audit_json_schema_and_sources():
    payload = _read_json_or_git(P5_JSON, "235b271")
    assert payload["repo_root"] == str(REPO_ROOT)
    assert isinstance(payload["db_files"], list) and payload["db_files"]
    assert isinstance(payload["artifact_sources"], list) and payload["artifact_sources"]
    assert isinstance(payload["runtime_read_paths"], list) and payload["runtime_read_paths"]
    assert payload["source_of_truth_assessment"]["canonical_runtime_source"] == "DB"

    artifact_paths = {item["path"] for item in payload["artifact_sources"]}
    assert "outputs/replay/p0_strategy_universe_inventory_20260517.json" in artifact_paths
    assert "outputs/replay/p1_lifecycle_formalization_fixture_20260517.json" in artifact_paths
    assert "outputs/replay/p3_replay_pipeline_split_20260517.json" in artifact_paths

    runtime_sources = {(item["component"], item["source"]) for item in payload["runtime_read_paths"]}
    assert ("replay_api", "lottery_api/data/lottery_v2.db") in runtime_sources
    assert ("replay_api_fixture_mode", "outputs/replay/non_online_replay_fixture_20260511.json") in runtime_sources


def test_no_placeholder_text_and_p3_artifact_readable():
    payload = _read_json_or_git(P5_JSON, "235b271")
    _walk_no_placeholders(payload)

    p3_path = REPO_ROOT / "outputs" / "replay" / "p3_replay_pipeline_split_20260517.json"
    p3_payload = _read_json_or_git(p3_path, "480c554")
    assert p3_payload["total_strategies"] == 506
    assert p3_payload["by_pipeline"]["HISTORICAL_RECONSTRUCTION"] == 97


def test_drift_guard_remains_pass():
    result = subprocess.run(
        [
            str(PYTHON),
            str(REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py"),
            "--strict",
            "--json-out",
            "/tmp/p5_post_source_of_truth_drift_guard.json",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in result.stdout
