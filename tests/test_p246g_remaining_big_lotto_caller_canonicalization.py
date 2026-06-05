"""
P246G — Remaining BIG_LOTTO Research Caller Canonicalization Tests
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"

P246G_JSON = OUTPUTS / "p246g_remaining_big_lotto_caller_canonicalization_20260605.json"
P246G_MD = OUTPUTS / "p246g_remaining_big_lotto_caller_canonicalization_20260605.md"

ALLOWED_CLASSIFICATIONS = {
    "UPDATED_TO_CANONICAL", "ALREADY_CANONICAL", "RAW_DISPLAY_ALLOWED",
    "POSSIBLY_AFFECTED_NEEDS_SCOPE", "NOT_AFFECTED", "UNKNOWN_NEEDS_MANUAL_REVIEW",
}


@pytest.fixture(scope="session")
def p246g_data():
    assert P246G_JSON.exists(), f"P246G JSON not found: {P246G_JSON}"
    return json.loads(P246G_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def p246g_md():
    assert P246G_MD.exists(), f"P246G MD not found: {P246G_MD}"
    return P246G_MD.read_text(encoding="utf-8")


# Structure
def test_p246g_json_parses(p246g_data):
    assert isinstance(p246g_data, dict)

def test_p246g_task_id(p246g_data):
    assert p246g_data.get("task_id") == "P246G"

def test_p246g_classification(p246g_data):
    assert "P246G" in p246g_data.get("classification", "")

def test_p246g_db_write_not_performed(p246g_data):
    assert p246g_data.get("db_write_performed") is False

def test_p246g_p246f_pr_mentioned(p246g_data):
    assert "321" in str(p246g_data.get("p246f_merged_pr", ""))


# Classification enum
def test_p246g_all_classifications_valid(p246g_data):
    for entry in p246g_data.get("caller_classifications", []):
        cls = entry.get("classification", "")
        assert cls in ALLOWED_CLASSIFICATIONS, f"Unknown class: {cls!r}"


# Drift detector updated
def test_p246g_drift_detector_updated_in_json(p246g_data):
    updated = p246g_data.get("updated_paths", [])
    files_str = json.dumps(updated).lower()
    assert "drift_detector" in files_str, "drift_detector must be in updated_paths"

def test_p246g_drift_detector_has_hyphen_filter():
    dd_file = REPO_ROOT / "lottery_api" / "engine" / "drift_detector.py"
    assert dd_file.exists()
    content = dd_file.read_text(encoding="utf-8")
    assert "draw NOT LIKE '%-%'" in content, \
        "drift_detector must have hyphen filter for BIG_LOTTO"

def test_p246g_drift_detector_has_date_filter():
    dd_file = REPO_ROOT / "lottery_api" / "engine" / "drift_detector.py"
    content = dd_file.read_text(encoding="utf-8")
    has_filter = "LENGTH(draw)=8" in content or "LENGTH(draw) = 8" in content
    assert has_filter, "drift_detector must filter 8-digit YYYYMMDD draw IDs"

def test_p246g_drift_detector_has_small_pool_filter():
    dd_file = REPO_ROOT / "lottery_api" / "engine" / "drift_detector.py"
    content = dd_file.read_text(encoding="utf-8")
    assert "max(parsed)" in content or "<= 25" in content, \
        "drift_detector must have SMALL_POOL_ALIEN Python post-filter"

def test_p246g_drift_detector_preserves_non_big_lotto():
    dd_file = REPO_ROOT / "lottery_api" / "engine" / "drift_detector.py"
    content = dd_file.read_text(encoding="utf-8")
    assert "lottery_type == 'BIG_LOTTO'" in content, \
        "drift_detector must use BIG_LOTTO branch (not break non-BIG_LOTTO)"

def test_p246g_drift_detector_verification_passes(p246g_data):
    dd_v = p246g_data.get("verification", {}).get("drift_detector", {})
    assert dd_v.get("has_hyphen_filter") is True
    assert dd_v.get("has_big_lotto_branch") is True


# Backtest framework updated
def test_p246g_backtest_framework_updated_in_json(p246g_data):
    updated = p246g_data.get("updated_paths", [])
    files_str = json.dumps(updated).lower()
    assert "backtest_framework" in files_str, "backtest_framework must be in updated_paths"

def test_p246g_backtest_framework_uses_canonical():
    bf_file = REPO_ROOT / "lottery_api" / "backtest_framework.py"
    assert bf_file.exists()
    content = bf_file.read_text(encoding="utf-8")
    assert "get_canonical_draws" in content, \
        "backtest_framework.py must use get_canonical_draws()"

def test_p246g_backtest_framework_verification_passes(p246g_data):
    bf_v = p246g_data.get("verification", {}).get("backtest_framework", {})
    assert bf_v.get("uses_canonical") is True


# Advanced learning deferred
def test_p246g_advanced_learning_is_deferred(p246g_data):
    deferred = p246g_data.get("deferred_paths", [])
    deferred_str = json.dumps(deferred).lower()
    assert "advanced_learning" in deferred_str, \
        "advanced_learning.py must be in deferred_paths"

def test_p246g_advanced_learning_has_deferred_reason(p246g_data):
    deferred = p246g_data.get("deferred_paths", [])
    al_entry = next((d for d in deferred if "advanced_learning" in str(d).lower()), None)
    assert al_entry is not None
    assert "reason" in al_entry, "deferred advanced_learning entry must include reason"

def test_p246g_advanced_learning_classification_explicit(p246g_data):
    callers = p246g_data.get("caller_classifications", [])
    al = next((c for c in callers if "advanced_learning" in str(c.get("file","")).lower()), None)
    assert al is not None, "advanced_learning must be in caller_classifications"
    assert al.get("classification") in ALLOWED_CLASSIFICATIONS


# No DB write / forbidden actions
def test_p246g_forbidden_actions_present(p246g_data):
    fa = p246g_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(fa).lower()
    assert "db_write" in fa_str
    assert "delet" in fa_str
    assert "registry" in fa_str
    assert "strategy" in fa_str
    assert "betting" in fa_str or "bet" in fa_str


# Add-on rows preserved and excluded
def test_p246g_states_addon_preserved(p246g_data):
    full_text = json.dumps(p246g_data, ensure_ascii=False).lower()
    assert "preserv" in full_text

def test_p246g_states_addon_excluded_from_research(p246g_data):
    full_text = json.dumps(p246g_data, ensure_ascii=False).lower()
    assert "add-on" in full_text or "add_on_prize_excluded" in full_text or "excluded" in full_text

def test_p246g_raw_access_preserved_field(p246g_data):
    raw = p246g_data.get("raw_access_preserved", {})
    assert isinstance(raw, dict)
    assert "get_all_draws" in str(raw).lower() or "preserved" in str(raw).lower()

def test_p246g_md_no_db_write(p246g_md):
    assert "no db write" in p246g_md.lower()

def test_p246g_md_addon_preserved(p246g_md):
    assert "preserved" in p246g_md.lower()


# Deferred paths listed with reason
def test_p246g_deferred_paths_present(p246g_data):
    deferred = p246g_data.get("deferred_paths", [])
    assert len(deferred) >= 2

def test_p246g_each_deferred_has_reason(p246g_data):
    for entry in p246g_data.get("deferred_paths", []):
        assert "reason" in entry, f"Deferred entry must include reason: {entry}"


# Script import and execution
def test_p246g_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246g", REPO_ROOT / "analysis" / "p246g_remaining_big_lotto_caller_canonicalization.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "run_canonicalization_audit")
    assert hasattr(mod, "CALLER_CLASSIFICATIONS")
    assert hasattr(mod, "FORBIDDEN_ACTIONS")

def test_p246g_run_audit_returns_correct_fields():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246g", REPO_ROOT / "analysis" / "p246g_remaining_big_lotto_caller_canonicalization.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.run_canonicalization_audit()
    assert result["task_id"] == "P246G"
    assert result["db_write_performed"] is False
    assert result["all_p246g_updates_verified"] is True

def test_p246g_all_updates_verified(p246g_data):
    assert p246g_data.get("all_p246g_updates_verified") is True

def test_p246g_final_decision_present(p246g_data):
    fd = p246g_data.get("final_decision", "")
    assert len(fd) > 50
    assert "no db write" in fd.lower()
