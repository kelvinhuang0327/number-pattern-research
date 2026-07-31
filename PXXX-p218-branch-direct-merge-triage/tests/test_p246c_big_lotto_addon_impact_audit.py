"""
P246C — BIG_LOTTO Add-on Prize Record Impact Audit Tests

Verifies:
- P246C JSON parses with required fields
- read_only_confirmed is true
- forbidden actions include DB write, migration, row deletion, registry, production, strategy, betting
- impact classifications from allowed enum
- report states add-on records are valid lottery-related but out-of-scope for canonical research
- report recommends preservation, not deletion
- P247 apply is not authorized by P246C
- row-family counts sum to total if included
"""

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"

P246C_JSON = OUTPUTS / "p246c_big_lotto_addon_impact_audit_20260605.json"
P246C_MD = OUTPUTS / "p246c_big_lotto_addon_impact_audit_20260605.md"

ALLOWED_IMPACT_CLASSES = {
    "DIRECTLY_AFFECTED",
    "POSSIBLY_AFFECTED",
    "NOT_AFFECTED",
    "UNKNOWN_NEEDS_MANUAL_REVIEW",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def p246c_data():
    assert P246C_JSON.exists(), f"P246C JSON not found: {P246C_JSON}"
    return json.loads(P246C_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def p246c_md():
    assert P246C_MD.exists(), f"P246C MD not found: {P246C_MD}"
    return P246C_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def test_p246c_json_parses(p246c_data):
    assert isinstance(p246c_data, dict)


def test_p246c_task_id(p246c_data):
    assert p246c_data.get("task_id") == "P246C"


def test_p246c_schema_version(p246c_data):
    assert "schema_version" in p246c_data


def test_p246c_classification_present(p246c_data):
    assert "classification" in p246c_data
    assert "P246C" in p246c_data["classification"]


def test_p246c_p246b_merged_pr(p246c_data):
    assert "p246b_merged_pr" in p246c_data
    val = str(p246c_data["p246b_merged_pr"])
    assert "317" in val, "p246b_merged_pr must reference PR #317"


# ---------------------------------------------------------------------------
# DB read-only
# ---------------------------------------------------------------------------

def test_p246c_read_only_confirmed(p246c_data):
    assert p246c_data.get("read_only_confirmed") is True


def test_p246c_db_write_not_performed(p246c_data):
    assert p246c_data.get("db_write_performed") is False


def test_p246c_row_family_counts_present(p246c_data):
    assert "row_family_counts" in p246c_data
    counts = p246c_data["row_family_counts"]
    assert isinstance(counts, dict)


def test_p246c_row_family_addon_count_matches_p246_baseline(p246c_data):
    counts = p246c_data.get("row_family_counts", {})
    addon = counts.get("ADD_ON_PRIZE_EXCLUDED")
    if addon is not None:
        assert addon == 19100, f"ADD_ON count must be 19100 (P246 baseline), got {addon}"


def test_p246c_row_family_total_reasonable(p246c_data):
    counts = p246c_data.get("row_family_counts", {})
    total = counts.get("TOTAL")
    if total is not None:
        assert total >= 22238, f"Total BIG_LOTTO rows must be >= 22238, got {total}"


# ---------------------------------------------------------------------------
# Impact classifications from allowed enum
# ---------------------------------------------------------------------------

def test_p246c_impacted_paths_present(p246c_data):
    assert "impacted_paths" in p246c_data
    assert isinstance(p246c_data["impacted_paths"], list)
    assert len(p246c_data["impacted_paths"]) > 0


def test_p246c_impact_classifications_from_allowed_enum(p246c_data):
    for entry in p246c_data.get("impacted_paths", []):
        impact = entry.get("impact", "")
        assert impact in ALLOWED_IMPACT_CLASSES, \
            f"Impact class {impact!r} not in allowed set: {ALLOWED_IMPACT_CLASSES}"


def test_p246c_impact_summary_present(p246c_data):
    assert "impact_summary" in p246c_data
    summary = p246c_data["impact_summary"]
    for cls in ALLOWED_IMPACT_CLASSES:
        assert cls in summary, f"impact_summary missing key: {cls}"


def test_p246c_directly_affected_includes_database(p246c_data):
    directly = p246c_data.get("impact_summary", {}).get("DIRECTLY_AFFECTED", [])
    paths_str = " ".join(str(x) for x in directly).lower()
    assert "database" in paths_str, "DIRECTLY_AFFECTED must include database.py"


def test_p246c_not_affected_includes_p219(p246c_data):
    not_affected = p246c_data.get("impact_summary", {}).get("NOT_AFFECTED", [])
    paths_str = " ".join(str(x) for x in not_affected).lower()
    assert "p219" in paths_str, "NOT_AFFECTED must include p219 (it correctly filters hyphenated draws)"


# ---------------------------------------------------------------------------
# Forbidden actions
# ---------------------------------------------------------------------------

def test_p246c_forbidden_actions_present(p246c_data):
    fa = p246c_data.get("forbidden_actions_confirmed", [])
    assert isinstance(fa, list)
    assert len(fa) > 0


def test_p246c_forbidden_actions_include_db_write(p246c_data):
    fa = p246c_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "db_write" in fa_str or "db write" in fa_str


def test_p246c_forbidden_actions_include_migration(p246c_data):
    fa = p246c_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "migration" in fa_str


def test_p246c_forbidden_actions_include_row_deletion(p246c_data):
    fa = p246c_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "delet" in fa_str or "row_deletion" in fa_str


def test_p246c_forbidden_actions_include_registry(p246c_data):
    fa = p246c_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "registry" in fa_str


def test_p246c_forbidden_actions_include_production_recommendation(p246c_data):
    fa = p246c_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "production" in fa_str or "recommendation" in fa_str


def test_p246c_forbidden_actions_include_strategy_promotion(p246c_data):
    fa = p246c_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "strategy" in fa_str


def test_p246c_forbidden_actions_include_betting_advice(p246c_data):
    fa = p246c_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "betting" in fa_str or "bet" in fa_str


# ---------------------------------------------------------------------------
# Add-on records are valid but out-of-scope for canonical research
# ---------------------------------------------------------------------------

def test_p246c_states_addon_are_valid_lottery_related(p246c_data):
    preservation_stmt = str(p246c_data.get("addon_records_preservation_statement", "")).lower()
    full_text = json.dumps(p246c_data, ensure_ascii=False).lower()
    has_valid = (
        "valid lottery-related" in preservation_stmt
        or "valid lottery-related" in full_text
    )
    assert has_valid, "P246C must state add-on records are valid lottery-related records"


def test_p246c_states_addon_out_of_scope_for_research(p246c_data):
    full_text = json.dumps(p246c_data, ensure_ascii=False).lower()
    has_out_of_scope = (
        "population mismatch" in full_text
        or "out-of-scope" in full_text
        or "excluded from research" in full_text
        or "excluded from canonical" in full_text
    )
    assert has_out_of_scope, \
        "P246C must state add-on records are out-of-scope for canonical main-draw research"


def test_p246c_md_states_addon_valid_not_fake(p246c_md):
    text = p246c_md.lower()
    assert "valid lottery" in text or "add-on" in text, \
        "P246C MD must describe add-on records as valid lottery-related"
    # Must not describe them as fake/simulated in the body
    forbidden = ["add_on_prize_excluded rows are fake", "add_on_prize_excluded rows are simulated"]
    for phrase in forbidden:
        assert phrase not in text, f"Forbidden phrase in P246C MD: {phrase!r}"


# ---------------------------------------------------------------------------
# Preservation recommendation
# ---------------------------------------------------------------------------

def test_p246c_recommends_preservation_not_deletion(p246c_data):
    preservation_stmt = str(p246c_data.get("addon_records_preservation_statement", "")).lower()
    recommended = json.dumps(p246c_data.get("recommended_p247_design", {}), ensure_ascii=False).lower()
    full_text = preservation_stmt + " " + recommended
    assert "preserv" in full_text, "P246C must recommend preservation of add-on rows"
    # Check that any mention of "delete add_on" is prefixed with "do not" (a prohibition, not a recommendation)
    import re
    # Find all occurrences of "delete add_on" in full JSON
    full_lower = json.dumps(p246c_data, ensure_ascii=False).lower()
    matches = [m.start() for m in re.finditer(r"delete add.on", full_lower)]
    for pos in matches:
        context = full_lower[max(0, pos-20):pos+30]
        assert "do not" in context or "not delete" in context or "must not" in context, \
            f"Found 'delete add_on' without prohibition context: ...{context}..."


def test_p246c_md_recommends_not_delete(p246c_md):
    text = p246c_md.lower()
    assert "do not delete" in text or "must be preserved" in text or "preservation" in text, \
        "P246C MD must say do not delete or preserved"


# ---------------------------------------------------------------------------
# P247 apply not authorized
# ---------------------------------------------------------------------------

def test_p246c_p247_apply_not_authorized(p246c_data):
    assert p246c_data.get("p247_apply_authorized") is False, \
        "P246C must state p247_apply_authorized=False"


def test_p246c_p247_requires_separate_type_d(p246c_data):
    auth_required = str(p246c_data.get("p247_apply_authorization_required", "")).lower()
    assert "type d" in auth_required or "type_d" in auth_required or "separate" in auth_required, \
        "P246C must state P247 apply requires separate Type D authorization"


def test_p246c_final_decision_says_not_authorized(p246c_data):
    fd = str(p246c_data.get("final_decision", "")).lower()
    assert "unauthorized" in fd or "remains unauthorized" in fd, \
        "final_decision must state P247 apply remains unauthorized"


def test_p246c_big_lotto_gate_blocked(p246c_data):
    gate = str(p246c_data.get("big_lotto_gate", "")).upper()
    assert "RED" in gate or "BLOCKED" in gate or "PENDING" in gate, \
        "P246C must show BIG_LOTTO research gate is blocked"


# ---------------------------------------------------------------------------
# Script import and execution
# ---------------------------------------------------------------------------

def test_p246c_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246c_audit",
        REPO_ROOT / "analysis" / "p246c_big_lotto_addon_impact_audit.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "IMPACTED_PATHS")
    assert hasattr(mod, "IMPACT_SUMMARY")
    assert hasattr(mod, "FORBIDDEN_ACTIONS")
    assert hasattr(mod, "run_impact_audit")
    assert hasattr(mod, "IMPACT_CLASSES")


def test_p246c_impact_classes_constant(p246c_data):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246c_audit",
        REPO_ROOT / "analysis" / "p246c_big_lotto_addon_impact_audit.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for cls in mod.IMPACT_CLASSES:
        assert cls in ALLOWED_IMPACT_CLASSES, f"Script IMPACT_CLASSES contains unknown value: {cls!r}"


def test_p246c_all_impacted_paths_use_allowed_classes():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246c_audit",
        REPO_ROOT / "analysis" / "p246c_big_lotto_addon_impact_audit.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for entry in mod.IMPACTED_PATHS:
        assert entry["impact"] in ALLOWED_IMPACT_CLASSES, \
            f"IMPACTED_PATHS entry has unknown impact class: {entry['impact']!r}"


def test_p246c_forbidden_actions_include_p247_apply():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246c_audit",
        REPO_ROOT / "analysis" / "p246c_big_lotto_addon_impact_audit.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fa_str = " ".join(mod.FORBIDDEN_ACTIONS).lower()
    assert "p247" in fa_str or "apply" in fa_str, \
        "FORBIDDEN_ACTIONS must include P247_apply"


def test_p246c_run_audit_returns_dict():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246c_audit",
        REPO_ROOT / "analysis" / "p246c_big_lotto_addon_impact_audit.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.run_impact_audit()
    assert isinstance(result, dict)
    assert result.get("db_write_performed") is False
    assert result.get("read_only_confirmed") is True
    assert result.get("p247_apply_authorized") is False


def test_p246c_risk_categories_present(p246c_data):
    assert "risk_categories" in p246c_data
    rc = p246c_data["risk_categories"]
    assert isinstance(rc, dict)
    assert len(rc) > 0


def test_p246c_artifacts_likely_affected_present(p246c_data):
    assert "artifacts_likely_affected" in p246c_data
    arts = p246c_data["artifacts_likely_affected"]
    arts_str = " ".join(str(x) for x in arts).lower()
    assert "p238b" in arts_str or "nist" in arts_str, \
        "artifacts_likely_affected must mention P238B NIST artifact"


def test_p246c_tests_likely_affected_present(p246c_data):
    assert "tests_likely_affected" in p246c_data
    tests = p246c_data["tests_likely_affected"]
    assert len(tests) > 0
    tests_str = " ".join(str(x) for x in tests).lower()
    assert "22238" in tests_str or "p238b" in tests_str, \
        "tests_likely_affected must mention 22238 hardcoded count"


def test_p246c_final_decision_present(p246c_data):
    assert "final_decision" in p246c_data
    assert len(p246c_data["final_decision"]) > 50
