"""
P246B — BIG_LOTTO Taxonomy Correction Tests

Verifies:
- P246B JSON artifact parses and contains required fields
- P247 plan JSON artifact parses and contains required fields
- ADD_ON_PRIZE_EXCLUDED is not labeled fake, simulated, synthetic, or invalid
- Report states hyphenated rows are add-on/special prize records
- Report states add-on records are valid but out-of-scope for canonical research
- Corrected taxonomy includes ADD_ON_PRIZE_EXCLUDED or SPECIAL_ADDON_DRAW_EXCLUDED
- Forbidden actions include DB write, migration, registry mutation, etc.
- P247 plan requires separate explicit authorization
- P247 plan preserves records and does not delete add-on rows
- BIG_LOTTO research remains blocked until canonical dataset separation
"""

import json
import os
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"

P246B_JSON = OUTPUTS / "p246b_big_lotto_taxonomy_correction_20260605.json"
P246B_MD = OUTPUTS / "p246b_big_lotto_taxonomy_correction_20260605.md"
P247_JSON = OUTPUTS / "p247_big_lotto_corrected_exclusion_plan_20260605.json"
P247_MD = OUTPUTS / "p247_big_lotto_corrected_exclusion_plan_20260605.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def p246b_data():
    assert P246B_JSON.exists(), f"P246B JSON not found: {P246B_JSON}"
    return json.loads(P246B_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def p247_data():
    assert P247_JSON.exists(), f"P247 JSON not found: {P247_JSON}"
    return json.loads(P247_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def p246b_md():
    assert P246B_MD.exists(), f"P246B MD not found: {P246B_MD}"
    return P246B_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def p247_md():
    assert P247_MD.exists(), f"P247 MD not found: {P247_MD}"
    return P247_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# P246B JSON — structure
# ---------------------------------------------------------------------------

def test_p246b_json_parses(p246b_data):
    assert isinstance(p246b_data, dict)


def test_p246b_task_id(p246b_data):
    assert p246b_data.get("task_id") == "P246B"


def test_p246b_schema_version(p246b_data):
    assert "schema_version" in p246b_data


def test_p246b_classification_present(p246b_data):
    assert "classification" in p246b_data
    assert "P246B" in p246b_data["classification"]


def test_p246b_supersedes_p246(p246b_data):
    assert "supersedes" in p246b_data
    supersedes = p246b_data["supersedes"]
    assert isinstance(supersedes, dict)
    assert supersedes.get("task") == "P246"


def test_p246b_corrected_taxonomy_present(p246b_data):
    assert "corrected_taxonomy" in p246b_data
    ct = p246b_data["corrected_taxonomy"]
    assert isinstance(ct, dict)
    # Must include ADD_ON_PRIZE_EXCLUDED or SPECIAL_ADDON_DRAW_EXCLUDED
    has_addon = (
        "ADD_ON_PRIZE_EXCLUDED" in ct
        or "SPECIAL_ADDON_DRAW_EXCLUDED" in ct
    )
    assert has_addon, "corrected_taxonomy must include ADD_ON_PRIZE_EXCLUDED or SPECIAL_ADDON_DRAW_EXCLUDED"


def test_p246b_row_family_counts_present(p246b_data):
    assert "row_family_counts" in p246b_data
    counts = p246b_data["row_family_counts"]
    assert isinstance(counts, dict)
    has_addon = (
        "ADD_ON_PRIZE_EXCLUDED" in counts
        or "SPECIAL_ADDON_DRAW_EXCLUDED" in counts
    )
    assert has_addon


def test_p246b_canonical_research_population(p246b_data):
    assert "canonical_research_population" in p246b_data


def test_p246b_excluded_but_valid_records(p246b_data):
    assert "excluded_but_valid_records" in p246b_data
    evr = p246b_data["excluded_but_valid_records"]
    addon_key = (
        "ADD_ON_PRIZE_EXCLUDED"
        if "ADD_ON_PRIZE_EXCLUDED" in evr
        else "SPECIAL_ADDON_DRAW_EXCLUDED"
    )
    assert addon_key in evr, "excluded_but_valid_records must contain ADD_ON_PRIZE_EXCLUDED"


def test_p246b_forbidden_actions_present(p246b_data):
    assert "forbidden_actions" in p246b_data
    fa = p246b_data["forbidden_actions"]
    assert isinstance(fa, list)
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "db_write" in fa_str or "db write" in fa_str
    assert "migration" in fa_str
    assert "registry" in fa_str
    assert "production" in fa_str or "recommendation" in fa_str


def test_p246b_final_decision_present(p246b_data):
    assert "final_decision" in p246b_data
    assert len(p246b_data["final_decision"]) > 20


# ---------------------------------------------------------------------------
# P246B — ADD_ON_PRIZE_EXCLUDED must NOT be labeled fake/simulated/etc.
# ---------------------------------------------------------------------------

def test_add_on_not_described_as_fake(p246b_data):
    ct = p246b_data.get("corrected_taxonomy", {})
    addon = ct.get("ADD_ON_PRIZE_EXCLUDED", ct.get("SPECIAL_ADDON_DRAW_EXCLUDED", {}))
    if isinstance(addon, dict):
        assert addon.get("is_fake") is not True, "ADD_ON must not be labeled is_fake=True"
        assert addon.get("is_simulated") is not True, "ADD_ON must not be labeled is_simulated=True"
        assert addon.get("is_invalid") is not True, "ADD_ON must not be labeled is_invalid=True"


def test_add_on_not_described_as_fake_in_excluded_valid(p246b_data):
    evr = p246b_data.get("excluded_but_valid_records", {})
    addon = evr.get("ADD_ON_PRIZE_EXCLUDED", evr.get("SPECIAL_ADDON_DRAW_EXCLUDED", {}))
    if isinstance(addon, dict):
        assert addon.get("valid_lottery_related") is not False, \
            "excluded_but_valid_records ADD_ON entry must not mark valid_lottery_related=False"


def test_add_on_not_described_as_fake_in_full_json(p246b_data):
    # Check that forbidden phrases don't appear outside of the forbidden_phrases_or_claims list itself.
    # The list documents what must NOT be used; its presence there is correct.
    import copy
    data_copy = copy.deepcopy(p246b_data)
    data_copy.pop("forbidden_phrases_or_claims", None)
    full_text = json.dumps(data_copy, ensure_ascii=False).lower()
    forbidden = [
        "add_on_prize_excluded rows are simulated",
        "add_on_prize_excluded rows are fake",
        "add_on_prize_excluded rows are synthetic",
        "add_on_prize_excluded rows are invalid",
        "add_on_prize_excluded rows are contaminated",
        "hyphenated rows are not real lottery data",
    ]
    for phrase in forbidden:
        assert phrase not in full_text, f"Forbidden phrase found outside forbidden_phrases_or_claims in P246B JSON: {phrase!r}"


def test_add_on_is_lottery_related(p246b_data):
    ct = p246b_data.get("corrected_taxonomy", {})
    addon = ct.get("ADD_ON_PRIZE_EXCLUDED", ct.get("SPECIAL_ADDON_DRAW_EXCLUDED", {}))
    if isinstance(addon, dict) and "is_lottery_related" in addon:
        assert addon["is_lottery_related"] is True, \
            "ADD_ON_PRIZE_EXCLUDED must be marked is_lottery_related=True"


# ---------------------------------------------------------------------------
# P246B — hyphenated rows described as add-on/special prize records
# ---------------------------------------------------------------------------

def test_p246b_states_hyphenated_are_addon_records(p246b_data):
    full_text = json.dumps(p246b_data, ensure_ascii=False).lower()
    has_addon = "add-on" in full_text or "add_on" in full_text or "special prize" in full_text
    assert has_addon, "P246B must state hyphenated rows are add-on or special prize records"


def test_p246b_md_states_hyphenated_are_addon(p246b_md):
    text = p246b_md.lower()
    assert "add-on" in text or "special prize" in text, \
        "P246B MD must describe hyphenated rows as add-on or special prize records"


def test_p246b_states_addon_are_valid_lottery_related(p246b_data):
    full_text = json.dumps(p246b_data, ensure_ascii=False).lower()
    assert "valid lottery-related" in full_text or "valid lottery related" in full_text or \
           "lottery-related records" in full_text, \
        "P246B must state add-on records are valid lottery-related records"


def test_p246b_states_exclusion_due_to_population_mismatch(p246b_data):
    full_text = json.dumps(p246b_data, ensure_ascii=False).lower()
    assert "population mismatch" in full_text, \
        "P246B must state exclusion reason is population mismatch, not data falseness"


def test_p246b_states_out_of_scope_for_canonical_research(p246b_data):
    full_text = json.dumps(p246b_data, ensure_ascii=False).lower()
    has_out_of_scope = (
        "out-of-scope" in full_text
        or "out of scope" in full_text
        or "outside the canonical" in full_text
        or "excluded from canonical" in full_text
        or "excluded from research" in full_text
    )
    assert has_out_of_scope, \
        "P246B must state add-on records are out-of-scope for canonical main-draw research"


# ---------------------------------------------------------------------------
# P246B — corrected taxonomy has ADD_ON_PRIZE_EXCLUDED
# ---------------------------------------------------------------------------

def test_corrected_taxonomy_has_addon_excluded_label(p246b_data):
    ct = p246b_data.get("corrected_taxonomy", {})
    has_label = (
        "ADD_ON_PRIZE_EXCLUDED" in ct
        or "SPECIAL_ADDON_DRAW_EXCLUDED" in ct
    )
    assert has_label, \
        "corrected_taxonomy must include ADD_ON_PRIZE_EXCLUDED or SPECIAL_ADDON_DRAW_EXCLUDED"


def test_old_sim_hyphen_label_is_superseded(p246b_data):
    ct = p246b_data.get("corrected_taxonomy", {})
    addon = ct.get("ADD_ON_PRIZE_EXCLUDED", ct.get("SPECIAL_ADDON_DRAW_EXCLUDED", {}))
    if isinstance(addon, dict):
        old = addon.get("old_label", "")
        assert "SIM_HYPHEN" in old or "SIM" in old, \
            "ADD_ON_PRIZE_EXCLUDED entry should reference old SIM_HYPHEN label"


# ---------------------------------------------------------------------------
# P246B — forbidden actions check
# ---------------------------------------------------------------------------

def test_p246b_forbidden_actions_include_db_write(p246b_data):
    fa = p246b_data.get("forbidden_actions", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "db_write" in fa_str or "db write" in fa_str


def test_p246b_forbidden_actions_include_migration(p246b_data):
    fa = p246b_data.get("forbidden_actions", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "migration" in fa_str


def test_p246b_forbidden_actions_include_registry(p246b_data):
    fa = p246b_data.get("forbidden_actions", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "registry" in fa_str


def test_p246b_forbidden_actions_include_production_recommendation(p246b_data):
    fa = p246b_data.get("forbidden_actions", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "production" in fa_str or "recommendation" in fa_str


def test_p246b_forbidden_actions_include_strategy_promotion(p246b_data):
    fa = p246b_data.get("forbidden_actions", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "strategy" in fa_str


def test_p246b_forbidden_actions_include_betting_advice(p246b_data):
    fa = p246b_data.get("forbidden_actions", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "betting" in fa_str or "bet" in fa_str


# ---------------------------------------------------------------------------
# P247 JSON — structure
# ---------------------------------------------------------------------------

def test_p247_json_parses(p247_data):
    assert isinstance(p247_data, dict)


def test_p247_task_id(p247_data):
    assert p247_data.get("task_id") == "P247_PLAN"


def test_p247_schema_version(p247_data):
    assert "schema_version" in p247_data


def test_p247_depends_on_p246b(p247_data):
    dep = p247_data.get("depends_on", "")
    assert "P246B" in str(dep), "P247 plan must depend on P246B"


def test_p247_apply_authorization_required(p247_data):
    auth = p247_data.get("apply_authorization_required", {})
    if isinstance(auth, dict):
        assert auth.get("required") is True, "P247 must require separate explicit authorization"
        type_str = str(auth.get("type", "")).lower()
        assert "type d" in type_str or "type_d" in type_str, \
            "P247 authorization must be Type D"
    else:
        assert auth is True or str(auth).lower() in ("true", "required")


def test_p247_preservation_policy_present(p247_data):
    assert "preservation_policy" in p247_data
    pp = p247_data["preservation_policy"]
    addon_key = (
        "ADD_ON_PRIZE_EXCLUDED"
        if "ADD_ON_PRIZE_EXCLUDED" in pp
        else "SPECIAL_ADDON_DRAW_EXCLUDED"
    )
    assert addon_key in pp, "preservation_policy must address ADD_ON_PRIZE_EXCLUDED"


def test_p247_preservation_policy_does_not_delete(p247_data):
    pp = p247_data.get("preservation_policy", {})
    addon = pp.get("ADD_ON_PRIZE_EXCLUDED", pp.get("SPECIAL_ADDON_DRAW_EXCLUDED", {}))
    if isinstance(addon, dict):
        policy = str(addon.get("policy", "")).upper()
        assert "PRESERVE" in policy or "DO NOT DELETE" in policy, \
            "ADD_ON preservation policy must say PRESERVE or DO NOT DELETE"
        # forbidden_operations lists things that are NOT allowed.
        # It is CORRECT for it to contain "DELETE ..." entries because those are forbidden.
        # We just verify that the policy field itself says PRESERVE.
        forbidden_ops = [str(x).lower() for x in addon.get("forbidden_operations", [])]
        # Verify that direct unconditional delete (not requiring backup) is in forbidden_ops
        # — this confirms the plan explicitly forbids deleting add-on rows.
        full_forbidden = " ".join(forbidden_ops)
        assert "delete" in full_forbidden, \
            "forbidden_operations must mention delete (to forbid unconditional deletion)"


def test_p247_forbidden_actions_include_db_write_without_auth(p247_data):
    fa = p247_data.get("forbidden_actions", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    has = "db_write" in fa_str or "db write" in fa_str
    assert has, "P247 forbidden_actions must include DB write"


def test_p247_forbidden_actions_include_deleting_addon(p247_data):
    fa = p247_data.get("forbidden_actions", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "delet" in fa_str, "P247 must forbid deleting ADD_ON rows"


def test_p247_forbidden_actions_include_betting_advice(p247_data):
    fa = p247_data.get("forbidden_actions", [])
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "betting" in fa_str or "bet" in fa_str


def test_p247_final_decision_present(p247_data):
    assert "final_decision" in p247_data
    assert len(p247_data["final_decision"]) > 20


def test_p247_operation_name_does_not_use_contamination_language(p247_data):
    op_name = str(p247_data.get("operation_name", "")).lower()
    forbidden = ["contaminate", "contamination", "quarantine contaminated", "fake", "simulated"]
    for phrase in forbidden:
        assert phrase not in op_name, \
            f"P247 operation_name must not use contamination language: found {phrase!r}"


def test_p247_operation_name_uses_segregation_or_exclusion(p247_data):
    op_name = str(p247_data.get("operation_name", "")).lower()
    has_safe_lang = (
        "segregat" in op_name
        or "exclusion" in op_name
        or "separation" in op_name
    )
    assert has_safe_lang, \
        "P247 operation_name should use segregation/exclusion/separation language"


# ---------------------------------------------------------------------------
# BIG_LOTTO research gate remains blocked
# ---------------------------------------------------------------------------

def test_p246b_big_lotto_research_blocked(p246b_data):
    gate = str(p246b_data.get("big_lotto_research_status", {}).get("gate_state", "")).upper()
    if not gate:
        gate = str(p246b_data.get("big_lotto_gate", "")).upper()
    assert "RED" in gate or "BLOCKED" in gate or "PENDING" in gate, \
        "P246B must show BIG_LOTTO research is blocked/GATE_RED"


def test_p246b_research_blocked_field(p246b_data):
    # Either a direct research_blocked bool or stated in gate state
    research_blocked = p246b_data.get("research_blocked")
    gate_state = str(
        p246b_data.get("big_lotto_research_status", {}).get("gate_state", "")
        or p246b_data.get("big_lotto_gate", "")
    ).upper()
    if research_blocked is not None:
        assert research_blocked is True, "research_blocked must be True"
    else:
        assert "BLOCKED" in gate_state or "RED" in gate_state or "PENDING" in gate_state


def test_p247_what_plan_does_not_authorize(p247_data):
    wdna = p247_data.get("what_this_plan_does_not_authorize", [])
    wdna_str = " ".join(str(x) for x in wdna).lower()
    assert "strategy" in wdna_str or "research" in wdna_str, \
        "P247 must explicitly state research/strategy is not authorized by this plan"


# ---------------------------------------------------------------------------
# Script-level import test
# ---------------------------------------------------------------------------

def test_analysis_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246b_taxonomy",
        REPO_ROOT / "analysis" / "p246b_big_lotto_taxonomy_correction.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "CORRECTED_TAXONOMY")
    assert hasattr(mod, "FORBIDDEN_PHRASES")
    assert hasattr(mod, "FORBIDDEN_ACTIONS")
    assert hasattr(mod, "run_taxonomy_correction")


def test_corrected_taxonomy_add_on_not_fake():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246b_taxonomy",
        REPO_ROOT / "analysis" / "p246b_big_lotto_taxonomy_correction.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ct = mod.CORRECTED_TAXONOMY
    addon = ct.get("ADD_ON_PRIZE_EXCLUDED", {})
    assert addon.get("is_fake") is False
    assert addon.get("is_simulated") is False
    assert addon.get("is_invalid") is False
    assert addon.get("is_lottery_related") is True


def test_forbidden_phrases_include_simulated():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246b_taxonomy",
        REPO_ROOT / "analysis" / "p246b_big_lotto_taxonomy_correction.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    phrases = " ".join(mod.FORBIDDEN_PHRASES).lower()
    assert "simulated" in phrases
    assert "fake" in phrases
