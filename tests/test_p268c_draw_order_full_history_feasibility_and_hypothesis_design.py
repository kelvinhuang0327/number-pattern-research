"""Tests for the P268C draw-order full-history feasibility & hypothesis design artifact.

This is a DESIGN ARTIFACT ONLY task: no code execution, no full-history fetch,
no DB write, no Hypothesis Registry write, no strategy proposed. These tests
check the produced artifacts (read-only).
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_JSON = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p268c_draw_order_full_history_feasibility_and_hypothesis_design_20260610.json"
)
ARTIFACT_MD = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p268c_draw_order_full_history_feasibility_and_hypothesis_design_20260610.md"
)

ALLOWED_FINAL_CLASSIFICATIONS = {
    "P268C_DRAW_ORDER_FULL_HISTORY_FEASIBILITY_AND_HYPOTHESIS_DESIGN_COMPLETE",
    "P268C_DRAW_ORDER_FULL_HISTORY_FEASIBILITY_BLOCKED_STATE_MISMATCH",
    "P268C_DRAW_ORDER_FULL_HISTORY_FEASIBILITY_BLOCKED_INSUFFICIENT_P268B_ARTIFACT",
    "P268C_DRAW_ORDER_FULL_HISTORY_FEASIBILITY_BLOCKED_SCOPE_CONFLICT",
}

BANNED_HIT_RATE_CLAIMS = [
    "hit-rate improved",
    "hit rate improved",
    "success rate improved",
    "validated edge",
    "proven edge",
]


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_JSON.exists(), f"Artifact not found: {ARTIFACT_JSON}"
    with open(ARTIFACT_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def test_json_artifact_exists_and_valid(artifact):
    assert isinstance(artifact, dict)
    assert artifact.get("task_id") == "P268C_DRAW_ORDER_FULL_HISTORY_FEASIBILITY_AND_HYPOTHESIS_DESIGN_ARTIFACT"
    assert artifact.get("type") == "DESIGN_ARTIFACT_ONLY"


def test_markdown_artifact_exists():
    assert ARTIFACT_MD.exists(), f"Markdown artifact not found: {ARTIFACT_MD}"
    text = ARTIFACT_MD.read_text(encoding="utf-8")
    assert "P268C" in text
    assert len(text) > 500


def test_no_db_write_authorization_claimed(artifact):
    db_plan = artifact.get("db_alignment_plan", {})
    assert db_plan.get("no_db_write_in_p268d") is True
    backfill_plan = artifact.get("artifact_store_backfill_plan", {})
    assert backfill_plan.get("no_production_db_write") is True

    text_blob = json.dumps(artifact, ensure_ascii=False).lower()
    # Future DB write must be explicitly scoped as a later/separate phase.
    assert "later phase" in text_blob or "later-phase" in text_blob
    assert "no_db_write_in_p268d" in text_blob


def test_no_registry_write_claimed(artifact):
    registry = artifact.get("hypothesis_registry_draft", {})
    assert registry, "hypothesis_registry_draft must be present"
    note = registry.get("note", "").lower()
    assert "draft only" in note
    assert "not written to" in note

    non_claims = artifact.get("explicit_non_claims", [])
    assert any("registry write" in c.lower() for c in non_claims)


def test_no_hit_rate_improvement_claim(artifact):
    text_blob = json.dumps(artifact, ensure_ascii=False).lower()
    for claim in BANNED_HIT_RATE_CLAIMS:
        assert claim not in text_blob, f"Banned hit-rate claim found: {claim!r}"

    non_claims = artifact.get("explicit_non_claims", [])
    assert any("hit-rate" in c.lower() or "success-rate" in c.lower() or "success rate" in c.lower() for c in non_claims)


def test_h1_h2_h3_present(artifact):
    registry = artifact.get("hypothesis_registry_draft", {})
    hypotheses = registry.get("hypotheses", [])
    ids = {h["id"] for h in hypotheses}
    assert "H1" in ids
    assert "H2" in ids
    assert "H3" in ids
    assert "H1_holdout" in ids

    h1 = next(h for h in hypotheses if h["id"] == "H1")
    assert h1["role"] == "primary"

    h2 = next(h for h in hypotheses if h["id"] == "H2")
    assert "gated" in h2["role"].lower()


def test_70_30_split_present(artifact):
    windows = artifact.get("hypothesis_registry_draft", {}).get("windows", {})
    split = windows.get("split", "")
    assert "70%" in split
    assert "30%" in split


def test_2026_04_05_exclusion_present(artifact):
    text_blob = json.dumps(artifact, ensure_ascii=False)
    assert "2026-04" in text_blob
    assert "2026-05" in text_blob
    # Must explicitly state exclusion, not just mention the months.
    windows = artifact.get("hypothesis_registry_draft", {}).get("windows", {})
    full_history_range = windows.get("full_history_range", "")
    assert "exclud" in full_history_range.lower()


def test_p268d_ten_step_plan_present(artifact):
    plan = artifact.get("p268d_implementation_order", {})
    steps = plan.get("steps", [])
    assert 1 <= len(steps) <= 10
    assert plan.get("max_steps") == 10

    step_names = [s["name"] for s in steps]
    assert "freeze_registry_artifact" in step_names
    assert step_names[0] == "freeze_registry_artifact"
    assert "h1_estimation_window_test" in step_names
    assert "governance_closeout" in step_names


def test_track_b_isolation_documented(artifact):
    boundaries = artifact.get("boundaries", {})
    track_b = boundaries.get("track_b_isolation", "")
    assert "winnerCount" in track_b
    assert "out of scope" in track_b.lower() or "out-of-scope" in track_b.lower()


def test_final_classification_is_allowed(artifact):
    final_classification = artifact.get("final_classification")
    assert final_classification in ALLOWED_FINAL_CLASSIFICATIONS
