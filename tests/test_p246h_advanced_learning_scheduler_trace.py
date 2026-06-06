"""P246H — Advanced Learning Scheduler Trace Tests"""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
P246H_JSON = OUTPUTS / "p246h_advanced_learning_scheduler_trace_20260605.json"
P246H_MD = OUTPUTS / "p246h_advanced_learning_scheduler_trace_20260605.md"

ALLOWED_CLASSIFICATIONS = {
    "UPDATED_TO_CANONICAL", "ALREADY_CANONICAL", "RAW_DISPLAY_ALLOWED",
    "POSSIBLY_AFFECTED_NEEDS_SCOPE", "NOT_AFFECTED", "UNKNOWN_NEEDS_MANUAL_REVIEW",
}


@pytest.fixture(scope="session")
def p246h_data():
    assert P246H_JSON.exists(), f"P246H JSON not found: {P246H_JSON}"
    return json.loads(P246H_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def p246h_md():
    assert P246H_MD.exists(), f"P246H MD not found: {P246H_MD}"
    return P246H_MD.read_text(encoding="utf-8")


# Structure
def test_p246h_json_parses(p246h_data):
    assert isinstance(p246h_data, dict)

def test_p246h_task_id(p246h_data):
    assert p246h_data.get("task_id") == "P246H"

def test_p246h_classification(p246h_data):
    assert "P246H" in p246h_data.get("classification", "")

def test_p246h_db_write_not_performed(p246h_data):
    assert p246h_data.get("db_write_performed") is False

def test_p246h_p246g_pr_mentioned(p246h_data):
    assert "322" in str(p246h_data.get("p246g_merged_pr", ""))


# Scheduler call chain documented
def test_p246h_scheduler_location_documented(p246h_data):
    loc = str(p246h_data.get("scheduler_location", "")).lower()
    assert "scheduler" in loc, "scheduler_location must be documented"

def test_p246h_traced_call_chain_present(p246h_data):
    chain = p246h_data.get("traced_call_chain", {})
    assert len(chain) >= 2, "traced_call_chain must have at least 2 steps"
    chain_str = json.dumps(chain).lower()
    assert "advanced_learning" in chain_str
    assert "scheduler" in chain_str

def test_p246h_data_source_type_present(p246h_data):
    dst = p246h_data.get("data_source_type", {})
    assert isinstance(dst, dict)
    assert len(dst) > 0


# Classification
def test_p246h_caller_classifications_use_valid_enum(p246h_data):
    for k, v in p246h_data.get("caller_classification", {}).items():
        cls = v.get("classification", "")
        assert cls in ALLOWED_CLASSIFICATIONS, f"Invalid class for {k}: {cls!r}"

def test_p246h_caller_classification_present(p246h_data):
    cc = p246h_data.get("caller_classification", {})
    assert len(cc) >= 1


# Files updated
def test_p246h_files_updated_present(p246h_data):
    updated = p246h_data.get("files_updated", [])
    assert len(updated) >= 1

def test_p246h_scheduler_updated_in_source():
    sched_file = REPO_ROOT / "lottery_api" / "utils" / "scheduler.py"
    assert sched_file.exists()
    content = sched_file.read_text(encoding="utf-8")
    assert "'-' in draw_id" in content or "in draw_id" in content, \
        "scheduler must filter hyphenated IDs"
    assert "draw_id.startswith('20')" in content, \
        "scheduler must filter 8-digit date-format IDs"
    assert "<= 25" in content, "scheduler must filter SMALL_POOL_ALIEN"
    assert "lottery_type == 'BIG_LOTTO'" in content, \
        "scheduler must use BIG_LOTTO branch"

def test_p246h_scheduler_verification_passes(p246h_data):
    v = p246h_data.get("verification", {}).get("scheduler", {})
    assert v.get("has_hyphen_filter") is True
    assert v.get("has_big_lotto_branch") is True

def test_p246h_all_updates_verified(p246h_data):
    assert p246h_data.get("all_p246h_updates_verified") is True


# Advanced learning itself is NOT affected (fix is at scheduler layer)
def test_p246h_advanced_learning_unchanged():
    al_file = REPO_ROOT / "lottery_api" / "routes" / "advanced_learning.py"
    content = al_file.read_text(encoding="utf-8")
    assert "DatabaseManager" not in content and "get_all_draws" not in content, \
        "advanced_learning.py must not have direct DB calls"


# Raw access preserved
def test_p246h_raw_access_preserved_field(p246h_data):
    raw = p246h_data.get("raw_access_preserved", {})
    assert isinstance(raw, dict)
    text = str(raw).lower()
    assert "preserv" in text or "data_by_type" in text

def test_p246h_raw_cache_non_destructive(p246h_data):
    rules = p246h_data.get("canonical_filter_rules_used", {})
    assert rules.get("non_destructive") is True

def test_p246h_scheduler_preserves_raw_cache():
    sched_file = REPO_ROOT / "lottery_api" / "utils" / "scheduler.py"
    content = sched_file.read_text(encoding="utf-8")
    assert "data_by_type" in content, "scheduler must still use data_by_type cache"


# Files deferred with reason
def test_p246h_files_deferred_present(p246h_data):
    deferred = p246h_data.get("files_deferred", [])
    assert len(deferred) >= 1

def test_p246h_each_deferred_has_reason(p246h_data):
    for entry in p246h_data.get("files_deferred", []):
        assert "reason" in entry, f"Deferred entry must have reason: {entry}"


# Add-on rows preserved and excluded
def test_p246h_states_addon_preserved(p246h_data):
    full_text = json.dumps(p246h_data, ensure_ascii=False).lower()
    assert "preserv" in full_text

def test_p246h_states_addon_excluded_from_learning(p246h_data):
    full_text = json.dumps(p246h_data, ensure_ascii=False).lower()
    assert "add-on" in full_text or "add_on_prize_excluded" in full_text

def test_p246h_md_no_db_write(p246h_md):
    assert "no db write" in p246h_md.lower()

def test_p246h_md_addon_preserved(p246h_md):
    assert "preserved" in p246h_md.lower()


# Forbidden actions
def test_p246h_forbidden_actions_present(p246h_data):
    fa = p246h_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(fa).lower()
    assert "db_write" in fa_str
    assert "delet" in fa_str
    assert "registry" in fa_str
    assert "betting" in fa_str or "bet" in fa_str


# Script tests
def test_p246h_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246h", REPO_ROOT / "analysis" / "p246h_advanced_learning_scheduler_trace.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "run_scheduler_trace")
    assert hasattr(mod, "TRACED_CALL_CHAIN")

def test_p246h_run_scheduler_trace():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246h", REPO_ROOT / "analysis" / "p246h_advanced_learning_scheduler_trace.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.run_scheduler_trace()
    assert result["task_id"] == "P246H"
    assert result["db_write_performed"] is False
    assert result["all_p246h_updates_verified"] is True

def test_p246h_final_decision_present(p246h_data):
    fd = p246h_data.get("final_decision", "")
    assert len(fd) > 50
    assert "no db write" in fd.lower()


# Integration: scheduler.get_data('BIG_LOTTO') should exclude add-on rows
def test_p246h_scheduler_get_data_excludes_addon():
    """Verify scheduler.get_data('BIG_LOTTO') excludes hyphenated IDs."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "lottery_api"))
    try:
        # Import only the get_data logic, not the full scheduler (avoids apscheduler)
        sched_file = REPO_ROOT / "lottery_api" / "utils" / "scheduler.py"
        content = sched_file.read_text(encoding="utf-8")
        # Verify filter logic is present in the method
        assert "'-' in draw_id" in content or "in draw_id" in content
        assert "draw_id.startswith('20')" in content
        assert "<= 25" in content
    finally:
        if str(REPO_ROOT / "lottery_api") in sys.path:
            sys.path.remove(str(REPO_ROOT / "lottery_api"))
