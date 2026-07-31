"""
Tests for P269B: Calendar Regime Pre-Registration Design

Verifies that the design artifact is present, correctly structured,
and upholds all governance constraints (no test run, no DB write,
no registry write, no strategy, p-hacking controls documented).
"""
import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs" / "research" / "p269b_calendar_regime_pre_registration_design_20260611.json"
ARTIFACT_MD = REPO_ROOT / "outputs" / "research" / "p269b_calendar_regime_pre_registration_design_20260611.md"


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
# P269A-Lite NO_GO boundary
# ---------------------------------------------------------------------------

def test_p269a_lite_no_go_boundary_present():
    data = _load_json()
    boundaries = data.get("inherited_boundaries", {})
    p269a = boundaries.get("p269a_lite_no_go", {})
    assert p269a, "inherited_boundaries.p269a_lite_no_go must be present"
    assert p269a.get("status") == "NO_GO", "P269A-Lite status must be NO_GO"


def test_p268d4_closure_present():
    data = _load_json()
    boundaries = data.get("inherited_boundaries", {})
    p268 = boundaries.get("p268d4_closure", {})
    assert p268, "inherited_boundaries.p268d4_closure must be present"
    assert p268.get("status") == "CLOSED", "P268D4 must be CLOSED"
    assert p268.get("strategy_authorized") is False, "P268D4 strategy_authorized must be False"


def test_markdown_states_no_go_boundary():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    assert "NO_GO" in content, "Markdown must reference P269A-Lite NO_GO"
    assert "P268D4" in content or "P268" in content, "Markdown must reference P268 closure"


# ---------------------------------------------------------------------------
# C05/C06 referenced
# ---------------------------------------------------------------------------

def test_c05_referenced_in_json():
    data = _load_json()
    scope = data.get("candidate_scope", {})
    primary = scope.get("primary", {})
    assert primary.get("id") == "C05", "C05 must be the primary candidate"


def test_c06_referenced_in_json():
    data = _load_json()
    scope = data.get("candidate_scope", {})
    secondary = scope.get("secondary_optional", {})
    assert secondary.get("id") == "C06", "C06 must be the secondary candidate"


def test_c05_and_c06_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    assert "C05" in content, "Markdown must reference C05"
    assert "C06" in content, "Markdown must reference C06"
    assert "Saturday" in content or "weekday" in content.lower(), \
        "Markdown must describe weekday regime"


# ---------------------------------------------------------------------------
# LOW plausibility warning
# ---------------------------------------------------------------------------

def test_low_plausibility_warning_present():
    data = _load_json()
    warning = data.get("low_plausibility_warning", {})
    assert warning, "low_plausibility_warning section must be present"
    assert warning.get("plausibility_rating") == "LOW", "plausibility_rating must be LOW"


def test_low_plausibility_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    lower = content.lower()
    assert "low" in lower and ("plausibility" in lower or "plausible" in lower), \
        "Markdown must state LOW plausibility"


# ---------------------------------------------------------------------------
# No statistical test run
# ---------------------------------------------------------------------------

def test_no_statistical_test_run():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_statistical_test_run") is True, \
        "explicit_non_claims.no_statistical_test_run must be True"
    assert claims.get("no_h1_test_run") is True, \
        "explicit_non_claims.no_h1_test_run must be True"


def test_markdown_states_no_test_run():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    lower = content.lower()
    assert "no statistical test" in lower or "no h1 test" in lower or \
           "no test has been run" in lower or "not been run" in lower or \
           "not run" in lower, \
        "Markdown must state no statistical test was run"


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


def test_registry_write_deferred_to_p269c():
    data = _load_json()
    scope = data.get("proposed_p269c_scope", {})
    assert scope, "proposed_p269c_scope must be present"
    authorized = scope.get("authorized_actions", [])
    has_registry = any("registry" in a.lower() or "hypothesis_registry" in a.lower()
                       for a in authorized)
    assert has_registry, "P269C scope must authorize the registry write (deferred)"


# ---------------------------------------------------------------------------
# No strategy / no picks
# ---------------------------------------------------------------------------

def test_no_strategy():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_strategy") is True, "no_strategy must be True"


def test_no_picks():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_picks") is True or \
           claims.get("no_numbers_generated") is True, \
        "no_picks or no_numbers_generated must be True"


def test_no_strategy_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    forbidden = ["recommended numbers", "betting strategy", "place a bet",
                 "strategy is authorized", "win rate improvement"]
    for phrase in forbidden:
        assert phrase.lower() not in content.lower(), \
            f"Markdown must not contain: '{phrase}'"
    lower = content.lower()
    no_claim_markers = ["no strategy", "no betting advice", "does not authorize",
                        "does not constitute"]
    assert any(m in lower for m in no_claim_markers), \
        "Markdown must include at least one no-claim marker"


# ---------------------------------------------------------------------------
# No hit-rate improvement claim
# ---------------------------------------------------------------------------

def test_no_hit_rate_improvement_claim():
    data = _load_json()
    claims = data.get("explicit_non_claims", {})
    assert claims.get("no_hit_rate_improvement_claim") is True, \
        "no_hit_rate_improvement_claim must be True"


# ---------------------------------------------------------------------------
# P-hacking controls
# ---------------------------------------------------------------------------

def test_p_hacking_controls_present():
    data = _load_json()
    controls = data.get("p_hacking_controls", {})
    assert controls, "p_hacking_controls section must be present"
    assert len(controls) >= 3, "p_hacking_controls must cover at least 3 risk dimensions"


def test_weekday_selection_lock():
    data = _load_json()
    controls = data.get("p_hacking_controls", {})
    # Must mention binary boundary lock (no best-weekday selection)
    controls_str = json.dumps(controls).lower()
    assert "binary" in controls_str or "sat" in controls_str or \
           "weekday" in controls_str, \
        "p_hacking_controls must address weekday boundary lock"


def test_metric_lock_present():
    data = _load_json()
    controls = data.get("p_hacking_controls", {})
    controls_str = json.dumps(controls).lower()
    assert "metric" in controls_str or "m3+" in controls_str.lower(), \
        "p_hacking_controls must address metric lock"


def test_p_hacking_mentioned_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    lower = content.lower()
    assert "p-hacking" in lower or "p_hacking" in lower or \
           "bonferroni" in lower or "multiple testing" in lower, \
        "Markdown must address p-hacking / multiple testing correction"


# ---------------------------------------------------------------------------
# Leakage controls
# ---------------------------------------------------------------------------

def test_leakage_controls_present():
    data = _load_json()
    controls = data.get("leakage_controls", [])
    assert isinstance(controls, list), "leakage_controls must be a list"
    assert len(controls) >= 3, "Must have at least 3 leakage controls"


def test_oos_split_defined():
    data = _load_json()
    oos = data.get("oos_split_design", {})
    assert oos, "oos_split_design section must be present"
    assert oos.get("method") is not None, "oos_split_design.method must be present"
    assert oos.get("split_ratio") is not None, "oos_split_design.split_ratio must be present"


def test_leakage_controls_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    lower = content.lower()
    assert "leakage" in lower or "oos" in lower, \
        "Markdown must reference leakage controls or OOS design"


# ---------------------------------------------------------------------------
# Proposed H1 present and structured
# ---------------------------------------------------------------------------

def test_proposed_h1_present():
    data = _load_json()
    h1 = data.get("proposed_h1", {})
    assert h1, "proposed_h1 section must be present"
    assert h1.get("h1_statement"), "proposed_h1.h1_statement must be present"
    assert h1.get("lottery_type") == "DAILY_539", "H1 must target DAILY_539"
    assert h1.get("direction") == "two-tailed", "H1 must be two-tailed"


def test_h1_not_yet_registered():
    data = _load_json()
    h1 = data.get("proposed_h1", {})
    status = h1.get("status", "")
    assert "NOT_REGISTERED" in status or "not_registered" in status.lower() or \
           "requires" in status.lower(), \
        "H1 status must indicate it is NOT YET REGISTERED"


# ---------------------------------------------------------------------------
# Design verdict
# ---------------------------------------------------------------------------

def test_design_verdict_present():
    data = _load_json()
    verdict = data.get("design_verdict", {})
    assert verdict, "design_verdict section must be present"
    assert verdict.get("verdict") in {"READY_FOR_REGISTRY", "NO_GO_DESIGN_TOO_WEAK"}, \
        "design_verdict.verdict must be READY_FOR_REGISTRY or NO_GO_DESIGN_TOO_WEAK"


def test_design_verdict_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    assert "READY_FOR_REGISTRY" in content or "NO_GO_DESIGN_TOO_WEAK" in content, \
        "Markdown must state design verdict"


# ---------------------------------------------------------------------------
# Final classification allowed
# ---------------------------------------------------------------------------

def test_final_classification_allowed():
    allowed = {
        "P269B_CALENDAR_REGIME_PRE_REGISTRATION_DESIGN_COMPLETE_READY_FOR_REGISTRY",
        "P269B_CALENDAR_REGIME_PRE_REGISTRATION_DESIGN_COMPLETE_NO_GO",
        "P269B_CALENDAR_REGIME_PRE_REGISTRATION_DESIGN_BLOCKED_STATE_MISMATCH",
        "P269B_CALENDAR_REGIME_PRE_REGISTRATION_DESIGN_BLOCKED_SCOPE_CONFLICT",
    }
    data = _load_json()
    fc = data.get("final_classification")
    assert fc in allowed, \
        f"final_classification '{fc}' is not in allowed set"


def test_final_classification_consistent_with_verdict():
    data = _load_json()
    fc = data.get("final_classification", "")
    verdict = data.get("design_verdict", {}).get("verdict", "")
    if verdict == "READY_FOR_REGISTRY":
        assert "READY_FOR_REGISTRY" in fc, \
            "If verdict is READY_FOR_REGISTRY, final_classification must contain READY_FOR_REGISTRY"
    elif verdict == "NO_GO_DESIGN_TOO_WEAK":
        assert "NO_GO" in fc, \
            "If verdict is NO_GO_DESIGN_TOO_WEAK, final_classification must contain NO_GO"
