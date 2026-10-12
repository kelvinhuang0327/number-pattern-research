"""P246J — BIG_LOTTO Add-on Isolation Arc Closure Tests"""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
P246J_JSON = OUTPUTS / "p246j_big_lotto_addon_isolation_closure_20260606.json"
P246J_MD = OUTPUTS / "p246j_big_lotto_addon_isolation_closure_20260606.md"


@pytest.fixture(scope="session")
def p246j_data():
    assert P246J_JSON.exists(), f"P246J JSON not found: {P246J_JSON}"
    return json.loads(P246J_JSON.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def p246j_md():
    assert P246J_MD.exists(), f"P246J MD not found: {P246J_MD}"
    return P246J_MD.read_text(encoding="utf-8")


# Structure
def test_p246j_json_parses(p246j_data): assert isinstance(p246j_data, dict)
def test_p246j_task_id(p246j_data): assert p246j_data.get("task_id") == "P246J"
def test_p246j_classification(p246j_data): assert "P246J" in p246j_data.get("classification", "")
def test_p246j_db_write_confirmed_false(p246j_data): assert p246j_data.get("no_db_write_confirmed") is True
def test_p246j_no_deletion(p246j_data): assert p246j_data.get("no_deletion_confirmed") is True
def test_p246j_p246i_pr_mentioned(p246j_data): assert "324" in str(p246j_data.get("p246i_merged_pr", ""))


# P246B-I dependencies listed
def test_p246j_arc_timeline_present(p246j_data):
    timeline = p246j_data.get("arc_timeline", [])
    assert len(timeline) >= 8, "arc_timeline must list P246B through P246I"
    tasks = [t.get("task") for t in timeline]
    for task in ["P246B", "P246C", "P246D", "P246E", "P246F", "P246G", "P246H", "P246I"]:
        assert task in tasks, f"arc_timeline missing {task}"


# Canonicalized callers
def test_p246j_canonicalized_callers_present(p246j_data):
    callers = p246j_data.get("canonicalized_callers", [])
    assert len(callers) >= 6

def test_p246j_quick_predict_in_callers(p246j_data):
    callers_str = json.dumps(p246j_data.get("canonicalized_callers", [])).lower()
    assert "quick_predict" in callers_str

def test_p246j_rsm_bootstrap_in_callers(p246j_data):
    callers_str = json.dumps(p246j_data.get("canonicalized_callers", [])).lower()
    assert "rsm_bootstrap" in callers_str

def test_p246j_core_satellite_in_callers(p246j_data):
    callers_str = json.dumps(p246j_data.get("canonicalized_callers", [])).lower()
    assert "core_satellite" in callers_str

def test_p246j_drift_detector_in_callers(p246j_data):
    callers_str = json.dumps(p246j_data.get("canonicalized_callers", [])).lower()
    assert "drift_detector" in callers_str

def test_p246j_backtest_framework_in_callers(p246j_data):
    callers_str = json.dumps(p246j_data.get("canonicalized_callers", [])).lower()
    assert "backtest_framework" in callers_str

def test_p246j_scheduler_in_callers(p246j_data):
    callers_str = json.dumps(p246j_data.get("canonicalized_callers", [])).lower()
    assert "scheduler" in callers_str

def test_p246j_all_callers_verified_from_source(p246j_data):
    v = p246j_data.get("caller_verification", {})
    assert v.get("all_verified") is True, "All callers must be verified in source code"


# Raw access preserved
def test_p246j_raw_access_preserved(p246j_data):
    raw = p246j_data.get("raw_access_preserved", {})
    assert raw.get("confirmed") is True

def test_p246j_raw_access_mentions_get_all_draws(p246j_data):
    raw_str = json.dumps(p246j_data.get("raw_access_preserved", {})).lower()
    assert "get_all_draws" in raw_str or "raw" in raw_str


# Add-on records valid but excluded
def test_p246j_addon_not_fake(p246j_data):
    addon = p246j_data.get("add_on_records_status", {})
    assert addon.get("is_fake") is False
    assert addon.get("valid_lottery_related") is True
    assert addon.get("preserved_in_db") is True

def test_p246j_addon_excluded_by_canonical_filter(p246j_data):
    addon = p246j_data.get("add_on_records_status", {})
    excluded_by = addon.get("excluded_from_research_by", [])
    assert len(excluded_by) >= 2


# Population counts
def test_p246j_population_semantics_present(p246j_data):
    ps = p246j_data.get("population_semantics", {})
    assert "canonical_main_draw" in ps
    assert "add_on_prize_excluded" in ps

def test_p246j_raw_count_22238(p246j_data):
    ps = p246j_data.get("population_semantics", {})
    raw = ps.get("raw_total", {})
    assert raw.get("count") == 22238

def test_p246j_canonical_count_2113(p246j_data):
    ps = p246j_data.get("population_semantics", {})
    canonical = ps.get("canonical_main_draw", {})
    count = canonical.get("count")
    assert 2100 <= count <= 2200, f"canonical count should be ~2113, got {count}"

def test_p246j_md_has_both_populations(p246j_md):
    text = p246j_md.lower()
    assert "22,238" in text or "22238" in text
    assert "2,113" in text or "2113" in text


# Remaining risks include no DB-level view
def test_p246j_remaining_risks_present(p246j_data):
    risks = p246j_data.get("remaining_deferred_risks", [])
    assert len(risks) >= 3

def test_p246j_remaining_risks_include_no_canonical_view(p246j_data):
    risks_str = json.dumps(p246j_data.get("remaining_deferred_risks", [])).lower()
    assert "view" in risks_str or "phase 2" in risks_str or "canonical view" in risks_str


# Gate status
def test_p246j_gate_status_present(p246j_data):
    gate = p246j_data.get("gate_status", {})
    assert "RED" in str(gate.get("current", "")).upper() or "GATE_RED" in str(gate.get("current", ""))

def test_p246j_gate_research_protection_in_place(p246j_data):
    gate = p246j_data.get("gate_status", {})
    assert gate.get("research_protection_in_place") is True


# Recommended next task requires authorization if Type D
def test_p246j_recommended_next_task_present(p246j_data):
    rnt = p246j_data.get("recommended_next_task", {})
    assert isinstance(rnt, dict)
    assert len(rnt) > 0

def test_p246j_recommended_type_d_requires_authorization(p246j_data):
    rnt = p246j_data.get("recommended_next_task", {})
    alt = rnt.get("alternative", {})
    auth = str(alt.get("authorization_required", "")).lower()
    assert "type d" in auth or "explicit" in auth or "authorization" in auth


# Forbidden actions
def test_p246j_forbidden_actions_present(p246j_data):
    fa = p246j_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(fa).lower()
    assert "db_write" in fa_str
    assert "create_view" in fa_str or "create view" in fa_str
    assert "betting" in fa_str or "bet" in fa_str
    assert "gate_open" in fa_str or "gate" in fa_str


# Markdown
def test_p246j_md_no_db_write(p246j_md): assert "no db write" in p246j_md.lower()
def test_p246j_md_no_deletion(p246j_md): assert "no deletion" in p246j_md.lower()
def test_p246j_md_addon_preserved(p246j_md): assert "preserved" in p246j_md.lower()


# Script
def test_p246j_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246j", REPO_ROOT / "analysis" / "p246j_big_lotto_addon_isolation_closure.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "run_closure_audit")
    assert hasattr(mod, "CANONICALIZED_CALLERS")
    assert hasattr(mod, "REMAINING_DEFERRED_RISKS")

def test_p246j_run_closure_audit():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246j", REPO_ROOT / "analysis" / "p246j_big_lotto_addon_isolation_closure.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.run_closure_audit()
    assert result["task_id"] == "P246J"
    assert result["no_db_write_confirmed"] is True
    assert result["caller_verification"]["all_verified"] is True

def test_p246j_final_decision_present(p246j_data):
    fd = p246j_data.get("final_decision", "")
    assert len(fd) > 80
    assert "no db write" in fd.lower()
