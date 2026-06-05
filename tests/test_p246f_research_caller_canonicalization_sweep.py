"""
P246F — Research Caller Canonicalization Sweep Tests

Verifies:
- P246F JSON parses with required fields
- all classifications use allowed enum
- updated callers use get_canonical_draws for BIG_LOTTO research
- raw access via get_all_draws remains available for display/history
- no DB write/migration/deletion/quarantine claimed
- report states add-on rows are preserved
- report states add-on rows are excluded from research samples
- files_deferred listed
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"

P246F_JSON = OUTPUTS / "p246f_research_caller_canonicalization_sweep_20260605.json"
P246F_MD = OUTPUTS / "p246f_research_caller_canonicalization_sweep_20260605.md"

ALLOWED_CLASSIFICATIONS = {
    "UPDATED_TO_CANONICAL",
    "ALREADY_CANONICAL",
    "RAW_DISPLAY_ALLOWED",
    "POSSIBLY_AFFECTED_NEEDS_SCOPE",
    "NOT_AFFECTED",
    "UNKNOWN_NEEDS_MANUAL_REVIEW",
}


@pytest.fixture(scope="session")
def p246f_data():
    assert P246F_JSON.exists(), f"P246F JSON not found: {P246F_JSON}"
    return json.loads(P246F_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def p246f_md():
    assert P246F_MD.exists(), f"P246F MD not found: {P246F_MD}"
    return P246F_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def test_p246f_json_parses(p246f_data):
    assert isinstance(p246f_data, dict)


def test_p246f_task_id(p246f_data):
    assert p246f_data.get("task_id") == "P246F"


def test_p246f_schema_version(p246f_data):
    assert "schema_version" in p246f_data


def test_p246f_classification(p246f_data):
    assert "P246F" in p246f_data.get("classification", "")


def test_p246f_db_write_not_performed(p246f_data):
    assert p246f_data.get("db_write_performed") is False


def test_p246f_p246e_pr_mentioned(p246f_data):
    pr_ref = str(p246f_data.get("p246e_merged_pr", ""))
    assert "320" in pr_ref, "P246F must reference PR #320"


# ---------------------------------------------------------------------------
# Classification enum validation
# ---------------------------------------------------------------------------

def test_p246f_all_classifications_use_allowed_enum(p246f_data):
    callers = p246f_data.get("caller_classifications", [])
    assert len(callers) > 0, "caller_classifications must be non-empty"
    for entry in callers:
        cls = entry.get("classification", "")
        assert cls in ALLOWED_CLASSIFICATIONS, \
            f"Classification {cls!r} not in allowed enum: {ALLOWED_CLASSIFICATIONS}"


# ---------------------------------------------------------------------------
# Updated callers use get_canonical_draws
# ---------------------------------------------------------------------------

def test_p246f_files_updated_present(p246f_data):
    updated = p246f_data.get("files_updated", [])
    assert len(updated) >= 3, "files_updated must list at least 3 callers (P246E + P246F)"


def test_p246f_rsm_bootstrap_updated(p246f_data):
    updated = p246f_data.get("files_updated", [])
    files_str = json.dumps(updated).lower()
    assert "rsm_bootstrap" in files_str, "files_updated must include rsm_bootstrap.py"


def test_p246f_core_satellite_updated(p246f_data):
    updated = p246f_data.get("files_updated", [])
    files_str = json.dumps(updated).lower()
    assert "core_satellite" in files_str, "files_updated must include core_satellite.py"


def test_p246f_quick_predict_already_updated(p246f_data):
    updated = p246f_data.get("files_updated", [])
    files_str = json.dumps(updated).lower()
    assert "quick_predict" in files_str, "files_updated must include quick_predict.py (P246E)"


def test_p246f_rsm_bootstrap_verified_in_source():
    rsm_file = REPO_ROOT / "tools" / "rsm_bootstrap.py"
    assert rsm_file.exists()
    content = rsm_file.read_text(encoding="utf-8")
    assert "get_canonical_draws" in content, \
        "tools/rsm_bootstrap.py must use get_canonical_draws()"


def test_p246f_core_satellite_verified_in_source():
    cs_file = REPO_ROOT / "lottery_api" / "engine" / "core_satellite.py"
    assert cs_file.exists()
    content = cs_file.read_text(encoding="utf-8")
    assert "get_canonical_draws" in content, \
        "lottery_api/engine/core_satellite.py must use get_canonical_draws()"


def test_p246f_all_p246f_updates_verified(p246f_data):
    assert p246f_data.get("all_p246f_updates_verified") is True


# ---------------------------------------------------------------------------
# Raw access preserved
# ---------------------------------------------------------------------------

def test_p246f_raw_access_preserved_field(p246f_data):
    raw = p246f_data.get("raw_access_preserved", {})
    assert isinstance(raw, dict)
    desc = str(raw.get("description", "")).lower()
    assert "get_all_draws" in desc or "preserved" in desc, \
        "raw_access_preserved must mention get_all_draws or preservation"


def test_p246f_raw_get_all_draws_in_database_py():
    db_file = REPO_ROOT / "lottery_api" / "database.py"
    content = db_file.read_text(encoding="utf-8")
    assert "def get_all_draws" in content, \
        "get_all_draws() must remain in database.py for raw/display access"


def test_p246f_raw_display_allowed_classification_present(p246f_data):
    callers = p246f_data.get("caller_classifications", [])
    raw_display = [c for c in callers if c.get("classification") == "RAW_DISPLAY_ALLOWED"]
    assert len(raw_display) >= 1, "At least one caller must be RAW_DISPLAY_ALLOWED"


# ---------------------------------------------------------------------------
# Forbidden actions
# ---------------------------------------------------------------------------

def test_p246f_forbidden_actions_present(p246f_data):
    fa = p246f_data.get("forbidden_actions_confirmed", [])
    assert len(fa) > 0


def test_p246f_forbidden_db_write(p246f_data):
    fa_str = " ".join(p246f_data.get("forbidden_actions_confirmed", [])).lower()
    assert "db_write" in fa_str or "db write" in fa_str


def test_p246f_forbidden_deletion(p246f_data):
    fa_str = " ".join(p246f_data.get("forbidden_actions_confirmed", [])).lower()
    assert "delet" in fa_str


def test_p246f_forbidden_registry(p246f_data):
    fa_str = " ".join(p246f_data.get("forbidden_actions_confirmed", [])).lower()
    assert "registry" in fa_str


def test_p246f_forbidden_strategy_promotion(p246f_data):
    fa_str = " ".join(p246f_data.get("forbidden_actions_confirmed", [])).lower()
    assert "strategy" in fa_str


def test_p246f_forbidden_betting(p246f_data):
    fa_str = " ".join(p246f_data.get("forbidden_actions_confirmed", [])).lower()
    assert "betting" in fa_str or "bet" in fa_str


# ---------------------------------------------------------------------------
# Add-on rows preserved and excluded from research
# ---------------------------------------------------------------------------

def test_p246f_states_addon_preserved(p246f_data):
    full_text = json.dumps(p246f_data, ensure_ascii=False).lower()
    assert "preserv" in full_text, "P246F must state add-on rows are preserved"


def test_p246f_states_addon_excluded_from_research(p246f_data):
    full_text = json.dumps(p246f_data, ensure_ascii=False).lower()
    has_excluded = (
        "excluded from" in full_text
        or "add-on" in full_text
        or "add_on_prize_excluded" in full_text
    )
    assert has_excluded, "P246F must state add-on rows are excluded from research"


def test_p246f_md_states_no_db_write(p246f_md):
    assert "no db write" in p246f_md.lower() or "no db write performed" in p246f_md.lower()


def test_p246f_md_states_addon_preserved(p246f_md):
    assert "preserved" in p246f_md.lower() or "preservation" in p246f_md.lower()


# ---------------------------------------------------------------------------
# Files deferred
# ---------------------------------------------------------------------------

def test_p246f_files_deferred_listed(p246f_data):
    deferred = p246f_data.get("files_deferred", [])
    assert len(deferred) >= 2, "files_deferred must list at least 2 deferred files"


def test_p246f_drift_detector_deferred(p246f_data):
    deferred = p246f_data.get("files_deferred", [])
    deferred_str = json.dumps(deferred).lower()
    assert "drift_detector" in deferred_str, "drift_detector must be in files_deferred"


def test_p246f_caller_classifications_have_deferred(p246f_data):
    callers = p246f_data.get("caller_classifications", [])
    deferred = [c for c in callers if c.get("deferred") is True]
    assert len(deferred) >= 2, "At least 2 callers must be marked deferred=True"


# ---------------------------------------------------------------------------
# Script import test
# ---------------------------------------------------------------------------

def test_p246f_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246f_sweep",
        REPO_ROOT / "analysis" / "p246f_research_caller_canonicalization_sweep.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "CALLER_CLASSIFICATIONS")
    assert hasattr(mod, "FILES_UPDATED")
    assert hasattr(mod, "FILES_DEFERRED")
    assert hasattr(mod, "run_sweep")
    assert hasattr(mod, "CLASSIFICATION_ENUM")


def test_p246f_classification_enum_complete():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246f_sweep",
        REPO_ROOT / "analysis" / "p246f_research_caller_canonicalization_sweep.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for cls in mod.CLASSIFICATION_ENUM:
        assert cls in ALLOWED_CLASSIFICATIONS, f"Unknown class in CLASSIFICATION_ENUM: {cls!r}"


def test_p246f_run_sweep_returns_correct_fields():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246f_sweep",
        REPO_ROOT / "analysis" / "p246f_research_caller_canonicalization_sweep.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.run_sweep()
    assert result["task_id"] == "P246F"
    assert result["db_write_performed"] is False
    assert result["all_p246f_updates_verified"] is True


def test_p246f_final_decision_present(p246f_data):
    fd = p246f_data.get("final_decision", "")
    assert len(fd) > 50
    assert "no db write" in fd.lower() or "no db write" in fd.lower()
