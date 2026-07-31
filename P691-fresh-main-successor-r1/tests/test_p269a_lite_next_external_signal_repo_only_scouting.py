"""
Tests for P269A-Lite: Next External Signal Family Repo-Only Scouting

Verifies that the scouting artifact is present, correctly structured,
and upholds all governance constraints.
"""
import json
import os
import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs" / "research" / "p269a_lite_next_external_signal_repo_only_scouting_20260611.json"
ARTIFACT_MD = REPO_ROOT / "outputs" / "research" / "p269a_lite_next_external_signal_repo_only_scouting_20260611.md"


def _load_json():
    with open(ARTIFACT_JSON, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Artifact existence
# ---------------------------------------------------------------------------

def test_json_artifact_exists():
    assert ARTIFACT_JSON.exists(), f"JSON artifact missing: {ARTIFACT_JSON}"


def test_json_artifact_valid():
    data = _load_json()
    assert isinstance(data, dict), "JSON must be a dict"
    assert len(data) > 5, "JSON must have substantive content"


def test_markdown_artifact_exists():
    assert ARTIFACT_MD.exists(), f"Markdown artifact missing: {ARTIFACT_MD}"


def test_markdown_artifact_non_empty():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    assert len(content) > 500, "Markdown must have substantive content"


# ---------------------------------------------------------------------------
# Repo-only limitation
# ---------------------------------------------------------------------------

def test_repo_only_limitation_present():
    data = _load_json()
    assert "repo_only_limitation" in data, "Must include repo_only_limitation section"
    limitation = data["repo_only_limitation"]
    description = limitation.get("description", "")
    assert "REPO-ONLY" in description or "repo-only" in description.lower(), \
        "Limitation section must state repo-only scope"


def test_markdown_states_repo_only():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    assert "repo-only" in content.lower() or "REPO-ONLY" in content, \
        "Markdown must state repo-only limitation"


# ---------------------------------------------------------------------------
# P268 draw-order explicitly excluded
# ---------------------------------------------------------------------------

def test_p268_draw_order_explicitly_excluded():
    data = _load_json()
    boundary = data.get("p268d4_closure_boundary", {})
    assert boundary.get("status") == "CLOSED", "P268D4 boundary must be CLOSED"
    strategy_authorized = boundary.get("strategy_authorized")
    assert strategy_authorized is False, "strategy_authorized must be False in P268D4 boundary"


def test_draw_order_candidate_rejected():
    data = _load_json()
    candidates = data.get("candidate_matrix", [])
    c01 = next((c for c in candidates if c.get("candidate_id") == "C01"), None)
    assert c01 is not None, "C01 draw-order candidate must be present"
    assert c01.get("recommendation") == "REJECT", "C01 must be REJECT"
    assert c01.get("prior_status") == "ALREADY_NULL", "C01 must be ALREADY_NULL"


def test_markdown_excludes_draw_order():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    assert "P268D4" in content, "Markdown must reference P268D4 closure"
    assert "CLOSED" in content, "Markdown must state P268D4 CLOSED"


# ---------------------------------------------------------------------------
# Candidate matrix
# ---------------------------------------------------------------------------

def test_candidate_matrix_exists():
    data = _load_json()
    candidates = data.get("candidate_matrix", [])
    assert isinstance(candidates, list), "candidate_matrix must be a list"
    assert len(candidates) >= 5, "Must have at least 5 candidates"


def test_candidate_required_fields():
    data = _load_json()
    required_fields = [
        "candidate_id", "signal_family", "source_hint_from_repo",
        "data_availability_status", "hit_rate_plausibility",
        "ev_only_or_popularity_risk", "leakage_risk", "oos_feasibility",
        "validation_difficulty", "prior_status", "recommendation", "reason"
    ]
    for c in data.get("candidate_matrix", []):
        for field in required_fields:
            assert field in c, f"Candidate {c.get('candidate_id','?')} missing field '{field}'"


def test_candidate_data_availability_values():
    valid_values = {"AVAILABLE_IN_REPO", "SOURCE_HINT_ONLY", "UNKNOWN"}
    data = _load_json()
    for c in data.get("candidate_matrix", []):
        val = c.get("data_availability_status")
        assert val in valid_values, \
            f"Candidate {c.get('candidate_id')}: invalid data_availability_status '{val}'"


def test_candidate_hit_rate_plausibility_values():
    valid_values = {"HIGH", "MEDIUM", "LOW"}
    data = _load_json()
    for c in data.get("candidate_matrix", []):
        val = c.get("hit_rate_plausibility")
        assert val in valid_values, \
            f"Candidate {c.get('candidate_id')}: invalid hit_rate_plausibility '{val}'"


def test_candidate_recommendation_values():
    valid_values = {"TOP_CANDIDATE", "WATCHLIST", "REJECT"}
    data = _load_json()
    for c in data.get("candidate_matrix", []):
        val = c.get("recommendation")
        assert val in valid_values, \
            f"Candidate {c.get('candidate_id')}: invalid recommendation '{val}'"


def test_candidate_classification_values():
    valid_values = {
        "HIT_RATE_PLAUSIBLE",
        "EV_ONLY_OR_POPULARITY_ONLY",
        "DATA_UNAVAILABLE",
        "LEAKAGE_RISK",
        "ALREADY_NULL"
    }
    data = _load_json()
    for c in data.get("candidate_matrix", []):
        val = c.get("classification")
        assert val in valid_values, \
            f"Candidate {c.get('candidate_id')}: invalid classification '{val}'"


# ---------------------------------------------------------------------------
# Top candidate recommendation or NO_GO
# ---------------------------------------------------------------------------

def test_top_candidate_or_no_go_present():
    data = _load_json()
    rec = data.get("top_candidate_recommendation", {})
    assert rec, "top_candidate_recommendation section must be present"
    status = rec.get("status")
    assert status in {"TOP_CANDIDATE", "NO_GO"}, \
        f"top_candidate_recommendation.status must be TOP_CANDIDATE or NO_GO, got '{status}'"


def test_no_top_candidate_without_evidence():
    data = _load_json()
    rec = data.get("top_candidate_recommendation", {})
    if rec.get("status") == "TOP_CANDIDATE":
        # If a top candidate was selected, it must have HIGH hit-rate plausibility
        top_id = rec.get("candidate_id")
        assert top_id is not None, "TOP_CANDIDATE must specify candidate_id"
        candidates = {c["candidate_id"]: c for c in data.get("candidate_matrix", [])}
        if top_id in candidates:
            assert candidates[top_id]["hit_rate_plausibility"] in {"HIGH", "MEDIUM"}, \
                "TOP_CANDIDATE must have HIGH or MEDIUM hit_rate_plausibility"


# ---------------------------------------------------------------------------
# No strategy / no picks / no hit-rate improvement claim
# ---------------------------------------------------------------------------

def test_no_strategy_claim():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_strategy") is True, "no_strategy must be True"


def test_no_picks_no_numbers():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_numbers_generated") is True or \
           claims.get("no_picks") is True, \
        "no_numbers_generated or no_picks must be True"


def test_no_hit_rate_improvement_claim():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_hit_rate_improvement_claim") is True, \
        "no_hit_rate_improvement_claim must be True"


def test_no_strategy_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    # These phrases must not appear in an affirmative (non-denial) context.
    # Check for definitive claims — use specific phrasing not present in denial sentences.
    forbidden_phrases = [
        "recommended numbers",
        "win rate improvement",
        "betting strategy",
        "place a bet",
        "strategy is authorized",
    ]
    for phrase in forbidden_phrases:
        assert phrase.lower() not in content.lower(), \
            f"Markdown must not contain forbidden phrase: '{phrase}'"
    # Ensure the artifact explicitly states no strategy / no betting advice
    no_claim_markers = ["no strategy", "no betting advice", "does not authorize"]
    lower = content.lower()
    assert any(m in lower for m in no_claim_markers), \
        "Markdown must include at least one no-claim marker (no strategy / no betting advice)"


# ---------------------------------------------------------------------------
# No DB write
# ---------------------------------------------------------------------------

def test_no_db_write():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_db_write") is True, "no_db_write must be True"


# ---------------------------------------------------------------------------
# No Hypothesis Registry write
# ---------------------------------------------------------------------------

def test_no_registry_write():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_registry_write") is True, "no_registry_write must be True"


# ---------------------------------------------------------------------------
# No H1 test run
# ---------------------------------------------------------------------------

def test_no_h1_test_run():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_h1_test_run") is True, "no_h1_test_run must be True"


def test_no_statistical_test():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_statistical_test") is True, "no_statistical_test must be True"


# ---------------------------------------------------------------------------
# Final classification allowed
# ---------------------------------------------------------------------------

def test_final_classification_allowed():
    allowed = {
        "P269A_LITE_NEXT_EXTERNAL_SIGNAL_REPO_ONLY_SCOUTING_COMPLETE_TOP_CANDIDATE_FOUND",
        "P269A_LITE_NEXT_EXTERNAL_SIGNAL_REPO_ONLY_SCOUTING_COMPLETE_NO_GO",
        "P269A_LITE_NEXT_EXTERNAL_SIGNAL_REPO_ONLY_SCOUTING_BLOCKED_STATE_MISMATCH",
        "P269A_LITE_NEXT_EXTERNAL_SIGNAL_REPO_ONLY_SCOUTING_BLOCKED_SCOPE_CONFLICT",
    }
    data = _load_json()
    fc = data.get("final_classification")
    assert fc in allowed, \
        f"final_classification '{fc}' is not in allowed set: {allowed}"


def test_final_classification_matches_top_candidate_status():
    data = _load_json()
    fc = data.get("final_classification", "")
    rec = data.get("top_candidate_recommendation", {})
    status = rec.get("status")
    if status == "NO_GO":
        assert "NO_GO" in fc, \
            "If top_candidate_recommendation is NO_GO, final_classification must contain NO_GO"
    elif status == "TOP_CANDIDATE":
        assert "TOP_CANDIDATE_FOUND" in fc, \
            "If status is TOP_CANDIDATE, final_classification must contain TOP_CANDIDATE_FOUND"
