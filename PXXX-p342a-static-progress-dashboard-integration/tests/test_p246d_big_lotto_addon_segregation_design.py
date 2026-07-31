"""
P246D — BIG_LOTTO Add-on Record Segregation Design Tests

Verifies:
- P246D JSON parses with required fields
- recommended design preserves raw add-on records
- report rejects direct deletion
- add-on records are valid lottery-related records
- add-on records are excluded from canonical main-draw research
- recommended design includes canonical view/helper or metadata segregation
- forbidden actions include DB write, migration, row deletion, registry, production, strategy, betting
- P247 apply requires separate explicit authorization
- API/frontend display policy distinguishes display from research
- strategy/replay required changes are listed
"""

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"

P246D_JSON = OUTPUTS / "p246d_big_lotto_addon_segregation_design_20260605.json"
P246D_MD = OUTPUTS / "p246d_big_lotto_addon_segregation_design_20260605.md"


@pytest.fixture(scope="session")
def p246d_data():
    assert P246D_JSON.exists(), f"P246D JSON not found: {P246D_JSON}"
    return json.loads(P246D_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def p246d_md():
    assert P246D_MD.exists(), f"P246D MD not found: {P246D_MD}"
    return P246D_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def test_p246d_json_parses(p246d_data):
    assert isinstance(p246d_data, dict)


def test_p246d_task_id(p246d_data):
    assert p246d_data.get("task_id") == "P246D"


def test_p246d_schema_version(p246d_data):
    assert "schema_version" in p246d_data


def test_p246d_classification_present(p246d_data):
    assert "P246D" in p246d_data.get("classification", "")


def test_p246d_db_write_not_performed(p246d_data):
    assert p246d_data.get("db_write_performed") is False


def test_p246d_read_only_confirmed(p246d_data):
    db_status = p246d_data.get("db_read_status", {})
    assert db_status.get("read_only") is True
    assert db_status.get("write_performed") is False


def test_p246d_row_family_counts_present(p246d_data):
    counts = p246d_data.get("row_family_counts", {})
    assert isinstance(counts, dict)


def test_p246d_addon_count_matches_baseline(p246d_data):
    counts = p246d_data.get("row_family_counts", {})
    addon = counts.get("ADD_ON_PRIZE_EXCLUDED")
    if addon is not None:
        assert addon == 19100


# ---------------------------------------------------------------------------
# Recommended design preserves add-on records
# ---------------------------------------------------------------------------

def test_p246d_recommended_design_present(p246d_data):
    assert "recommended_design" in p246d_data
    rd = p246d_data["recommended_design"]
    assert isinstance(rd, dict)


def test_p246d_recommended_design_preserves_addon(p246d_data):
    rd = p246d_data.get("recommended_design", {})
    rd_str = json.dumps(rd, ensure_ascii=False).lower()
    assert "preserv" in rd_str, "Recommended design must mention preservation of add-on rows"


def test_p246d_recommended_design_includes_canonical_helper_or_view(p246d_data):
    rd = p246d_data.get("recommended_design", {})
    rd_str = json.dumps(rd, ensure_ascii=False).lower()
    has_mechanism = (
        "canonical" in rd_str
        or "view" in rd_str
        or "helper" in rd_str
        or "get_canonical" in rd_str
        or "not like" in rd_str
    )
    assert has_mechanism, "Recommended design must include canonical view/helper mechanism"


def test_p246d_recommended_design_has_phases(p246d_data):
    rd = p246d_data.get("recommended_design", {})
    phases = rd.get("phases", [])
    assert len(phases) >= 2, "Recommended design must have at least 2 phases"


def test_p246d_phase1_requires_no_db_write(p246d_data):
    rd = p246d_data.get("recommended_design", {})
    phases = rd.get("phases", [])
    p1 = next((p for p in phases if p.get("phase") == 1), None)
    if p1:
        auth = str(p1.get("authorization_required", "")).lower()
        assert "no db" in auth or "none" in auth or "no type d" in auth or "no db write" in auth, \
            "Phase 1 must not require a DB write"


# ---------------------------------------------------------------------------
# Report rejects direct deletion
# ---------------------------------------------------------------------------

def test_p246d_rejected_options_includes_delete(p246d_data):
    rejected_ids = p246d_data.get("rejected_options", [])
    rejected_detail = p246d_data.get("rejected_options_detail", [])
    full_str = json.dumps(rejected_ids, ensure_ascii=False).lower() + " " + json.dumps(rejected_detail, ensure_ascii=False).lower()
    has_delete = "delet" in full_str or "direct" in full_str
    assert has_delete, "rejected_options must include direct deletion option"


def test_p246d_evaluated_options_contains_rejected_delete(p246d_data):
    opts = p246d_data.get("evaluated_options", [])
    delete_opt = next((o for o in opts if o.get("rejected") is True), None)
    assert delete_opt is not None, "evaluated_options must contain a rejected (deletion) option"
    reason = str(delete_opt.get("rejection_reason", "")).lower()
    assert "preserv" in reason or "valid" in reason or "must not" in reason, \
        "Rejection reason must cite preservation / valid records"


def test_p246d_md_rejects_deletion(p246d_md):
    text = p246d_md.lower()
    assert "reject" in text and "delet" in text, "MD must explicitly reject deletion approach"


# ---------------------------------------------------------------------------
# Add-on records are valid lottery-related records
# ---------------------------------------------------------------------------

def test_p246d_states_addon_are_valid(p246d_data):
    full_text = json.dumps(p246d_data, ensure_ascii=False).lower()
    assert "valid lottery-related" in full_text or "valid lottery related" in full_text, \
        "P246D must state add-on records are valid lottery-related records"


def test_p246d_states_exclusion_is_population_mismatch(p246d_data):
    full_text = json.dumps(p246d_data, ensure_ascii=False).lower()
    assert "population mismatch" in full_text, \
        "P246D must cite population mismatch as the exclusion reason"


def test_p246d_md_states_addon_valid_not_fake(p246d_md):
    text = p246d_md.lower()
    assert "valid lottery" in text or "add-on" in text
    forbidden = ["add_on_prize_excluded rows are fake", "add_on_prize_excluded rows are simulated"]
    for phrase in forbidden:
        assert phrase not in text, f"Forbidden phrase in P246D MD: {phrase!r}"


# ---------------------------------------------------------------------------
# Add-on records excluded from canonical research
# ---------------------------------------------------------------------------

def test_p246d_states_exclusion_from_canonical_research(p246d_data):
    full_text = json.dumps(p246d_data, ensure_ascii=False).lower()
    assert "excluded from canonical" in full_text or "excluded from research" in full_text or \
           "canonical main-draw research" in full_text or "canonical 6/49" in full_text, \
        "P246D must state add-on records are excluded from canonical main-draw research"


def test_p246d_isolation_requirements_present(p246d_data):
    reqs = p246d_data.get("isolation_requirements", [])
    assert len(reqs) >= 3, "isolation_requirements must list at least 3 requirements"


def test_p246d_isolation_requirement_no_deletion(p246d_data):
    reqs = p246d_data.get("isolation_requirements", [])
    reqs_str = json.dumps(reqs, ensure_ascii=False).lower()
    assert "no direct deletion" in reqs_str or "must not be deleted" in reqs_str or "delet" in reqs_str, \
        "isolation_requirements must include no-deletion requirement"


# ---------------------------------------------------------------------------
# Forbidden actions
# ---------------------------------------------------------------------------

def test_p246d_forbidden_actions_present(p246d_data):
    fa = p246d_data.get("forbidden_actions_confirmed", [])
    assert isinstance(fa, list)
    assert len(fa) > 0


def test_p246d_forbidden_db_write(p246d_data):
    fa_str = " ".join(p246d_data.get("forbidden_actions_confirmed", [])).lower()
    assert "db_write" in fa_str or "db write" in fa_str


def test_p246d_forbidden_migration(p246d_data):
    fa_str = " ".join(p246d_data.get("forbidden_actions_confirmed", [])).lower()
    assert "migration" in fa_str


def test_p246d_forbidden_row_deletion(p246d_data):
    fa_str = " ".join(p246d_data.get("forbidden_actions_confirmed", [])).lower()
    assert "row_deletion" in fa_str or "delet" in fa_str


def test_p246d_forbidden_registry(p246d_data):
    fa_str = " ".join(p246d_data.get("forbidden_actions_confirmed", [])).lower()
    assert "registry" in fa_str


def test_p246d_forbidden_production_recommendation(p246d_data):
    fa_str = " ".join(p246d_data.get("forbidden_actions_confirmed", [])).lower()
    assert "production" in fa_str or "recommendation" in fa_str


def test_p246d_forbidden_strategy_promotion(p246d_data):
    fa_str = " ".join(p246d_data.get("forbidden_actions_confirmed", [])).lower()
    assert "strategy" in fa_str


def test_p246d_forbidden_betting_advice(p246d_data):
    fa_str = " ".join(p246d_data.get("forbidden_actions_confirmed", [])).lower()
    assert "betting" in fa_str or "bet" in fa_str


# ---------------------------------------------------------------------------
# P247 requires separate authorization
# ---------------------------------------------------------------------------

def test_p246d_p247_not_authorized(p246d_data):
    assert p246d_data.get("p247_apply_authorized") is False


def test_p246d_p247_requires_type_d(p246d_data):
    auth = str(p246d_data.get("p247_apply_authorization_required", "")).lower()
    assert "type d" in auth or "type_d" in auth or "explicit" in auth


# ---------------------------------------------------------------------------
# API/frontend display policy
# ---------------------------------------------------------------------------

def test_p246d_api_frontend_display_policy_present(p246d_data):
    assert "api_frontend_display_policy" in p246d_data
    policy = p246d_data["api_frontend_display_policy"]
    assert isinstance(policy, dict)


def test_p246d_display_policy_distinguishes_display_from_research(p246d_data):
    policy = p246d_data.get("api_frontend_display_policy", {})
    policy_str = json.dumps(policy, ensure_ascii=False).lower()
    has_display = "display" in policy_str or "history" in policy_str or "show" in policy_str
    has_research = "research" in policy_str or "canonical" in policy_str or "filter" in policy_str
    assert has_display and has_research, \
        "Display policy must distinguish display callers from research callers"


def test_p246d_display_policy_permits_addon_display(p246d_data):
    policy = p246d_data.get("api_frontend_display_policy", {})
    policy_str = json.dumps(policy, ensure_ascii=False).lower()
    assert "label" in policy_str or "labeling" in policy_str or "display" in policy_str, \
        "Display policy must permit showing add-on records with labeling"


# ---------------------------------------------------------------------------
# Strategy/replay required changes listed
# ---------------------------------------------------------------------------

def test_p246d_strategy_replay_changes_present(p246d_data):
    changes = p246d_data.get("strategy_replay_required_changes", [])
    assert len(changes) >= 2, "strategy_replay_required_changes must list at least 2 callers"


def test_p246d_strategy_replay_changes_include_quick_predict(p246d_data):
    changes = p246d_data.get("strategy_replay_required_changes", [])
    changes_str = json.dumps(changes, ensure_ascii=False).lower()
    assert "quick_predict" in changes_str, \
        "strategy_replay_required_changes must mention quick_predict.py"


def test_p246d_test_validation_plan_present(p246d_data):
    tvp = p246d_data.get("test_validation_plan", [])
    assert len(tvp) >= 2


def test_p246d_test_plan_mentions_22238(p246d_data):
    tvp = p246d_data.get("test_validation_plan", [])
    tvp_str = json.dumps(tvp, ensure_ascii=False).lower()
    assert "22238" in tvp_str, "test_validation_plan must mention the 22238 hardcoded assertion"


def test_p246d_future_type_d_requirements_present(p246d_data):
    ftd = p246d_data.get("future_type_d_apply_requirements", {})
    assert isinstance(ftd, dict)
    assert len(ftd) > 0


def test_p246d_future_type_d_never_deletes(p246d_data):
    ftd = p246d_data.get("future_type_d_apply_requirements", {})
    never = ftd.get("never_allowed", [])
    never_str = " ".join(str(x) for x in never).lower()
    assert "delete" in never_str, "future_type_d_apply_requirements must explicitly list DELETE as never_allowed"


# ---------------------------------------------------------------------------
# Script import test
# ---------------------------------------------------------------------------

def test_p246d_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246d_design",
        REPO_ROOT / "analysis" / "p246d_big_lotto_addon_segregation_design.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "RECOMMENDED_DESIGN")
    assert hasattr(mod, "REJECTED_OPTIONS")
    assert hasattr(mod, "FORBIDDEN_ACTIONS")
    assert hasattr(mod, "run_segregation_design")
    assert hasattr(mod, "ISOLATION_REQUIREMENTS")


def test_p246d_run_design_returns_correct_fields():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246d_design",
        REPO_ROOT / "analysis" / "p246d_big_lotto_addon_segregation_design.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.run_segregation_design()
    assert result["task_id"] == "P246D"
    assert result["db_write_performed"] is False
    assert result["db_read_status"]["write_performed"] is False
    assert result["p247_apply_authorized"] is False


def test_p246d_rejected_options_constant_includes_deletion():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246d_design",
        REPO_ROOT / "analysis" / "p246d_big_lotto_addon_segregation_design.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    has_rejected = len(mod.REJECTED_OPTIONS) > 0
    assert has_rejected
    rejected_str = json.dumps(mod.REJECTED_OPTIONS, ensure_ascii=False).lower()
    assert "delet" in rejected_str or "delete" in rejected_str


def test_p246d_final_decision_present(p246d_data):
    fd = p246d_data.get("final_decision", "")
    assert len(fd) > 50
    assert "no db write" in fd.lower() or "no db write performed" in fd.lower() or \
           "not performed" in fd.lower()
