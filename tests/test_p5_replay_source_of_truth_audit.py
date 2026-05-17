"""Tests for the P5 replay source-of-truth audit."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from scripts import p5_replay_source_of_truth_audit as audit


REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = REPO_ROOT.parent / "LotteryNew" / ".venv" / "bin" / "python3"
P5_JSON = REPO_ROOT / "outputs" / "replay" / "p5_replay_source_of_truth_audit_20260517.json"
P3_GIT_REF = "480c554"


def _read_json_or_git(path: Path, git_ref: str | None = None) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if git_ref is None:
        raise FileNotFoundError(path)
    rel = str(path.relative_to(REPO_ROOT))
    completed = subprocess.run(
        ["git", "show", f"{git_ref}:{rel}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_audit_collect_is_read_only():
    connect_calls = []
    real_connect = audit.sqlite3.connect

    def _spy(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return real_connect(*args, **kwargs)

    with patch.object(audit.sqlite3, "connect", side_effect=_spy):
        payload = audit.collect_audit()

    assert connect_calls, "audit did not inspect any SQLite source"
    assert all("mode=ro" in args[0] for args, _ in connect_calls)
    assert payload["safety"] == {
        "db_write": False,
        "draw_import": False,
        "replay_row_generation": False,
        "prediction_update": False,
        "strategy_execution": False,
    }


def test_audit_json_schema_and_sources(tmp_path):
    out_json = tmp_path / "p5_audit.json"
    out_md = tmp_path / "p5_audit.md"
    out_policy = tmp_path / "p5_policy.md"

    rc = audit.main([
        "--output-json",
        str(out_json),
        "--output-md",
        str(out_md),
        "--policy-md",
        str(out_policy),
    ])
    assert rc == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["repo_root"] == str(REPO_ROOT)
    assert isinstance(payload["db_files"], list) and payload["db_files"]
    assert isinstance(payload["artifact_sources"], list) and payload["artifact_sources"]
    assert isinstance(payload["runtime_read_paths"], list) and payload["runtime_read_paths"]
    assert payload["source_of_truth_assessment"]["canonical_runtime_source"] == "DB"

    for item in payload["db_files"]:
        assert isinstance(item["tracked_by_git"], bool)
        assert isinstance(item["ignored_by_git"], bool)
        assert "path" in item and item["path"]

    artifact_paths = {item["path"] for item in payload["artifact_sources"]}
    assert "outputs/replay/p0_strategy_universe_inventory_20260517.json" in artifact_paths
    assert "outputs/replay/p1_lifecycle_formalization_fixture_20260517.json" in artifact_paths
    assert "outputs/replay/p3_replay_pipeline_split_20260517.json" in artifact_paths

    runtime_sources = {(item["component"], item["source"]) for item in payload["runtime_read_paths"]}
    assert ("replay_api", "lottery_api/data/lottery_v2.db") in runtime_sources
    assert ("replay_api_fixture_mode", "outputs/replay/non_online_replay_fixture_20260511.json") in runtime_sources


def test_no_placeholder_text_and_p3_artifact_readable():
    payload = json.loads(P5_JSON.read_text(encoding="utf-8")) if P5_JSON.exists() else audit.collect_audit()

    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            assert value not in {"TBD", "TODO", "null"}

    walk(payload)

    p3_path = REPO_ROOT / "outputs" / "replay" / "p3_replay_pipeline_split_20260517.json"
    p3_payload = _read_json_or_git(p3_path, P3_GIT_REF)
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
