"""
Tests for P269D: Calendar Regime H1 Null Closeout.

Validates the closeout artifact — no live-DB dependency, no statistical
computation in this test suite. Artifact / governance files only.
"""
import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs" / "research" / "p269d_calendar_regime_h1_null_closeout_20260611.json"
ARTIFACT_MD = REPO_ROOT / "outputs" / "research" / "p269d_calendar_regime_h1_null_closeout_20260611.md"


def _load():
    with open(ARTIFACT_JSON, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Artifact existence
# ---------------------------------------------------------------------------

def test_json_artifact_exists():
    assert ARTIFACT_JSON.exists(), f"JSON artifact missing: {ARTIFACT_JSON}"


def test_json_artifact_valid():
    data = _load()
    assert isinstance(data, dict)
    assert len(data) > 5


def test_markdown_artifact_exists():
    assert ARTIFACT_MD.exists(), f"Markdown artifact missing: {ARTIFACT_MD}"
    assert len(ARTIFACT_MD.read_text(encoding="utf-8")) > 500


# ---------------------------------------------------------------------------
# Closeout verdict
# ---------------------------------------------------------------------------

def test_closeout_verdict():
    data = _load()
    assert data["closeout_verdict"] == "CALENDAR_REGIME_DIAGNOSTICS_ONLY_NULL_CLOSURE"


def test_closeout_verdict_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    assert "CALENDAR_REGIME_DIAGNOSTICS_ONLY_NULL_CLOSURE" in content


# ---------------------------------------------------------------------------
# P269C H1 result recorded
# ---------------------------------------------------------------------------

def test_p269c_h1_primary_fail_recorded():
    data = _load()
    h1 = data["inherited_boundaries"]["p269c_formal_h1"]
    assert h1["status"] == "H1_PRIMARY_FAIL"


def test_p_value_recorded():
    data = _load()
    r = data["p269c_h1_result"]
    assert r["p_value"] == 0.8526


def test_saturday_events_recorded():
    data = _load()
    r = data["p269c_h1_result"]
    assert r["m3plus_events_saturday"] == 8
    assert r["n_saturday"] == 249


def test_weekday_events_recorded():
    data = _load()
    r = data["p269c_h1_result"]
    assert r["m3plus_events_weekday"] == 44
    assert r["n_weekday"] == 1245


def test_c06_not_run_recorded():
    data = _load()
    assert data["p269c_h1_result"]["c06_secondary"] == "NOT_RUN"


# ---------------------------------------------------------------------------
# Closed candidates
# ---------------------------------------------------------------------------

def test_c05_closed():
    data = _load()
    c05 = data["closed_candidates"]["C05"]
    assert c05["status"] == "CLOSED"
    assert c05["reopen_authorized"] is False


def test_c06_not_run_closed_for_arc():
    data = _load()
    c06 = data["closed_candidates"]["C06"]
    assert c06["status"] == "NOT_RUN_CLOSED_FOR_THIS_ARC"
    assert c06["reopen_authorized"] is False


def test_closed_candidates_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    assert "C05" in content
    assert "C06" in content
    assert "CLOSED" in content
    assert "NOT_RUN" in content


# ---------------------------------------------------------------------------
# Inherited boundaries
# ---------------------------------------------------------------------------

def test_p268_draw_order_already_null():
    data = _load()
    p268 = data["inherited_boundaries"]["p268_draw_order"]
    assert "ALREADY_NULL" in p268["status"]


def test_p269a_lite_no_go_boundary():
    data = _load()
    p269a = data["inherited_boundaries"]["p269a_lite_no_go"]
    assert p269a["status"] == "NO_GO"


def test_p269b_design_boundary():
    data = _load()
    p269b = data["inherited_boundaries"]["p269b_ready_for_registry"]
    assert p269b["design_verdict"] == "READY_FOR_REGISTRY"
    assert "p269b" in p269b["design_artifact"]


# ---------------------------------------------------------------------------
# Stop rule
# ---------------------------------------------------------------------------

def test_stop_rule_triggered():
    data = _load()
    sr = data["stop_rule_applied"]
    assert sr["triggered"] is True
    assert sr["p_observed"] == 0.8526
    assert sr["alpha_corrected"] == 0.01


# ---------------------------------------------------------------------------
# Non-claims (P269D is closeout only)
# ---------------------------------------------------------------------------

def test_no_statistical_test_run_in_p269d():
    data = _load()
    assert data["explicit_non_claims"]["no_statistical_test_run_in_p269d"] is True


def test_no_p269c_script_rerun():
    data = _load()
    assert data["explicit_non_claims"]["no_p269c_script_rerun"] is True


def test_no_db_write():
    data = _load()
    assert data["explicit_non_claims"]["no_db_write"] is True


def test_no_registry_write():
    data = _load()
    assert data["explicit_non_claims"]["no_registry_write"] is True


def test_no_strategy_no_picks():
    data = _load()
    nc = data["explicit_non_claims"]
    assert nc["no_strategy"] is True
    assert nc["no_picks"] is True
    assert nc["no_numbers_generated"] is True


def test_no_hit_rate_improvement_claim():
    data = _load()
    assert data["explicit_non_claims"]["no_hit_rate_improvement_claim"] is True


def test_no_claim_markers_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    forbidden = ["recommended numbers", "betting strategy", "place a bet",
                 "strategy is authorized", "win rate improvement"]
    lower = content.lower()
    for phrase in forbidden:
        assert phrase not in lower, f"forbidden phrase: '{phrase}'"
    assert "does not constitute" in lower or "not betting advice" in lower or \
           "not authorize" in lower


# ---------------------------------------------------------------------------
# Future reopen rule
# ---------------------------------------------------------------------------

def test_future_reopen_rule_present():
    data = _load()
    rule = data["future_reopen_rule"]
    assert rule["authorized"] is False
    assert len(rule["conditions"]) > 20
    assert len(rule["forbidden"]) >= 3


def test_future_reopen_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    lower = content.lower()
    assert "reopen" in lower or "re-test" in lower or "future" in lower


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------

def test_final_classification_allowed():
    allowed = {
        "P269D_CALENDAR_REGIME_H1_NULL_CLOSEOUT_COMPLETE",
        "P269D_CALENDAR_REGIME_H1_NULL_CLOSEOUT_BLOCKED_STATE_MISMATCH",
        "P269D_CALENDAR_REGIME_H1_NULL_CLOSEOUT_BLOCKED_SCOPE_CONFLICT",
        "P269D_CALENDAR_REGIME_H1_NULL_CLOSEOUT_BLOCKED_TEST_FAILURE",
    }
    data = _load()
    assert data["final_classification"] in allowed


def test_final_classification_is_complete():
    data = _load()
    assert data["final_classification"] == "P269D_CALENDAR_REGIME_H1_NULL_CLOSEOUT_COMPLETE"
