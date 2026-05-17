"""Policy tests for the P5A replay source promotion plan."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = REPO_ROOT.parent / "LotteryNew" / ".venv" / "bin" / "python3"
P5A_JSON = REPO_ROOT / "outputs" / "replay" / "p5a_replay_source_promotion_policy_20260517.json"
P5_AUDIT_GIT_REF = "235b271"
P3_GIT_REF = "480c554"

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import p5a_replay_source_promotion_policy as policy  # noqa: E402


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


def test_policy_json_schema_and_dependency(tmp_path):
    out_json = tmp_path / "p5a_policy.json"
    out_md = tmp_path / "p5a_policy.md"
    rc = policy.main([
        "--source-audit",
        str(REPO_ROOT / "outputs" / "replay" / "p5_replay_source_of_truth_audit_20260517.json"),
        "--pipeline-split",
        str(REPO_ROOT / "outputs" / "replay" / "p3_replay_pipeline_split_20260517.json"),
        "--output-json",
        str(out_json),
        "--output-md",
        str(out_md),
    ])
    assert rc == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["p4_acceptance_dependency"]["can_run_p4_before_policy"] is False
    assert payload["recommended_policy"]["primary_method"] == "ARTIFACT_PROMOTION"
    assert payload["recommended_policy"]["secondary_method"] == "CONTROLLED_DB_APPLY"
    assert payload["safety"] == {
        "db_write": False,
        "draw_import": False,
        "replay_row_generation": False,
        "prediction_update": False,
        "strategy_execution": False,
        "promotion_executed": False,
    }
    _walk_no_placeholders(payload)


def test_policy_uses_p5_audit_and_p3_pipeline_inputs():
    audit_payload = _read_json_or_git(
        REPO_ROOT / "outputs" / "replay" / "p5_replay_source_of_truth_audit_20260517.json",
        P5_AUDIT_GIT_REF,
    )
    pipeline_payload = _read_json_or_git(
        REPO_ROOT / "outputs" / "replay" / "p3_replay_pipeline_split_20260517.json",
        P3_GIT_REF,
    )
    payload = policy.collect_policy(
        REPO_ROOT / "outputs" / "replay" / "p5_replay_source_of_truth_audit_20260517.json",
        REPO_ROOT / "outputs" / "replay" / "p3_replay_pipeline_split_20260517.json",
    )
    assert payload["input_summary"]["canonical_runtime_source"] == audit_payload["source_of_truth_assessment"]["canonical_runtime_source"]
    assert payload["input_summary"]["historical_reconstruction_candidates"] == len(pipeline_payload["historical_reconstruction_candidates"])
    assert payload["input_summary"]["future_waiting_candidates"] == len(pipeline_payload["future_waiting_candidates"])
    assert payload["input_summary"]["display_only_candidates"] == len(pipeline_payload["display_only_candidates"])


def test_no_todo_tbd_null_in_output():
    payload = json.loads(P5A_JSON.read_text(encoding="utf-8")) if P5A_JSON.exists() else policy.collect_policy(
        REPO_ROOT / "outputs" / "replay" / "p5_replay_source_of_truth_audit_20260517.json",
        REPO_ROOT / "outputs" / "replay" / "p3_replay_pipeline_split_20260517.json",
    )
    _walk_no_placeholders(payload)


def test_drift_guard_remains_pass():
    result = subprocess.run(
        [
            str(PYTHON),
            str(REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py"),
            "--strict",
            "--json-out",
            "/tmp/p5a_post_source_promotion_drift_guard.json",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in result.stdout
