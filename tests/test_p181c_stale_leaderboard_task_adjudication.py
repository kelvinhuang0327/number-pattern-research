"""Tests for P181C — Stale leaderboard task adjudication."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"

ALLOWED_CLASSIFICATIONS = {
    "FOUND_AND_PUBLISHABLE",
    "MISSING_BUT_RECREATE_NEEDED",
    "SUPERSEDED_BY_LATER_ARTIFACTS",
    "OBSOLETE_CLOSE",
    "UNKNOWN_NEEDS_USER_INPUT",
}


def _find_artifact() -> Path:
    candidates = sorted(OUTPUTS_DIR.glob("p181c_stale_leaderboard_task_adjudication_*.json"))
    assert candidates, "No p181c JSON artifact found; run analysis/p181c_stale_leaderboard_task_adjudication.py first"
    return candidates[-1]


def _load() -> dict:
    return json.loads(_find_artifact().read_text(encoding="utf-8"))


# ── Artifact existence ────────────────────────────────────────────────────────

def test_json_artifact_exists_and_parses():
    path = _find_artifact()
    assert path.exists()
    report = _load()
    assert isinstance(report, dict)


def test_md_artifact_exists():
    candidates = sorted(OUTPUTS_DIR.glob("p181c_stale_leaderboard_task_adjudication_*.md"))
    assert candidates, "No p181c Markdown artifact found"
    text = candidates[-1].read_text(encoding="utf-8")
    assert len(text) > 300


# ── Schema fields ─────────────────────────────────────────────────────────────

def test_required_top_level_fields():
    report = _load()
    required = {
        "schema_version", "task_id", "classification", "phase0_summary",
        "referenced_commits", "refs_search_result", "artifact_overlap_analysis",
        "supersession_analysis", "recommendation",
        "no_db_write_confirmed", "no_registry_mutation_confirmed",
        "no_strategy_promotion_confirmed", "no_betting_advice_confirmed",
        "final_decision",
    }
    missing = required - set(report.keys())
    assert not missing, f"Missing required fields: {missing}"


def test_task_id():
    assert _load()["task_id"] == "P181C"


def test_classification_is_allowed():
    classification = _load()["classification"]
    assert classification in ALLOWED_CLASSIFICATIONS, (
        f"Classification {classification!r} not in allowed set {ALLOWED_CLASSIFICATIONS}"
    )


# ── Referenced commits marked missing ─────────────────────────────────────────

def test_referenced_commit_0f99d00_marked_missing():
    report = _load()
    result = report["refs_search_result"]["commit_0f99d00"]
    assert result["exists"] is False, (
        "Commit 0f99d00 must be marked as not existing — "
        "if it were found the classification would change"
    )


def test_referenced_commit_93fbd3d_marked_missing():
    report = _load()
    result = report["refs_search_result"]["commit_93fbd3d"]
    assert result["exists"] is False, "Commit 93fbd3d must be marked as not existing"


def test_refs_search_has_conclusion():
    result = _load()["refs_search_result"]
    assert "conclusion" in result
    assert len(result["conclusion"]) > 10


# ── No publishability claimed when commits are missing ────────────────────────

def test_not_classified_as_publishable_when_commits_missing():
    report = _load()
    # If both commits are missing, must NOT claim FOUND_AND_PUBLISHABLE
    c0 = report["refs_search_result"]["commit_0f99d00"]
    c1 = report["refs_search_result"]["commit_93fbd3d"]
    if not c0["exists"] and not c1["exists"]:
        assert report["classification"] != "FOUND_AND_PUBLISHABLE", (
            "Cannot be FOUND_AND_PUBLISHABLE when both referenced commits are missing"
        )


# ── Supersession analysis ─────────────────────────────────────────────────────

def test_supersession_analysis_present():
    report = _load()
    s = report["supersession_analysis"]
    assert isinstance(s, dict)
    assert "overall_supersession" in s
    assert "overall_reasoning" in s
    assert len(s["overall_reasoning"]) > 20


def test_supersession_references_later_artifacts():
    s = _load()["supersession_analysis"]
    reasoning = s["overall_reasoning"].lower()
    # Must reference at least some later superseding work
    assert any(term in reasoning for term in ["p188", "p232a", "p250a", "p251b", "migration", "supersede"]), (
        "Supersession reasoning must reference at least one later artifact"
    )


# ── Recommendation ────────────────────────────────────────────────────────────

def test_recommendation_exists():
    report = _load()
    rec = report["recommendation"]
    assert isinstance(rec, dict)
    assert "action" in rec
    assert "rationale" in rec
    assert len(rec["rationale"]) > 10


def test_recommendation_action_is_valid():
    report = _load()
    action = report["recommendation"]["action"]
    valid_actions = {"OBSOLETE_CLOSE", "MISSING_BUT_RECREATE_NEEDED", "HOLD", "FOUND_AND_PUBLISHABLE", "UNKNOWN_NEEDS_USER_INPUT"}
    assert action in valid_actions, f"Recommendation action {action!r} not in {valid_actions}"


def test_recommendation_has_do_not_do_list():
    rec = _load()["recommendation"]
    assert "do_not_do" in rec
    assert isinstance(rec["do_not_do"], list)
    assert len(rec["do_not_do"]) >= 1


# ── No-claim flags ────────────────────────────────────────────────────────────

def test_no_db_write():
    assert _load()["no_db_write_confirmed"] is True


def test_no_registry_mutation():
    assert _load()["no_registry_mutation_confirmed"] is True


def test_no_strategy_promotion():
    assert _load()["no_strategy_promotion_confirmed"] is True


def test_no_betting_advice():
    assert _load()["no_betting_advice_confirmed"] is True


# ── Artifact overlap analysis ─────────────────────────────────────────────────

def test_artifact_overlap_has_original_p179():
    overlap = _load()["artifact_overlap_analysis"]
    assert "original_p179" in overlap
    # P179 plan artifact is present in outputs/research/power_lotto/
    assert overlap["original_p179"]["found"] is True


def test_artifact_overlap_has_later_artifacts():
    overlap = _load()["artifact_overlap_analysis"]
    for key in ["p232a_scoreboard", "p250a_inventory"]:
        assert key in overlap, f"Missing key {key!r} in artifact_overlap_analysis"
        assert overlap[key].get("found") is True, f"{key} must be found (it exists in outputs/research/)"


# ── Markdown checks ───────────────────────────────────────────────────────────

def test_md_contains_no_db_write():
    candidates = sorted(OUTPUTS_DIR.glob("p181c_stale_leaderboard_task_adjudication_*.md"))
    text = candidates[-1].read_text(encoding="utf-8")
    assert "no db write" in text.lower()


def test_md_contains_no_betting_advice():
    candidates = sorted(OUTPUTS_DIR.glob("p181c_stale_leaderboard_task_adjudication_*.md"))
    text = candidates[-1].read_text(encoding="utf-8")
    assert "betting" in text.lower()


def test_md_contains_superseded_language():
    candidates = sorted(OUTPUTS_DIR.glob("p181c_stale_leaderboard_task_adjudication_*.md"))
    text = candidates[-1].read_text(encoding="utf-8")
    assert "supersed" in text.lower()


# ── Rerun ─────────────────────────────────────────────────────────────────────

def test_rerun_produces_valid_artifact():
    from analysis import p181c_stale_leaderboard_task_adjudication as p181c
    report = p181c.main()
    assert report["task_id"] == "P181C"
    assert report["classification"] in ALLOWED_CLASSIFICATIONS
    assert report["no_db_write_confirmed"] is True
    assert report["no_betting_advice_confirmed"] is True
    assert report["refs_search_result"]["commit_0f99d00"]["exists"] is False
    assert report["refs_search_result"]["commit_93fbd3d"]["exists"] is False
