"""
P246I — BIG_LOTTO Population Assertion Cleanup Tests

Verifies:
- P246I JSON parses
- raw count and canonical count are distinct
- add-on count represented as valid-but-excluded
- updated tests no longer imply 22,238 is canonical research sample
- historical artifacts left unchanged are documented
- no DB write/migration/deletion/quarantine claimed
- report states add-on records preserved and excluded from research
"""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
P246I_JSON = OUTPUTS / "p246i_big_lotto_population_assertion_cleanup_20260605.json"
P246I_MD = OUTPUTS / "p246i_big_lotto_population_assertion_cleanup_20260605.md"


@pytest.fixture(scope="session")
def p246i_data():
    assert P246I_JSON.exists(), f"P246I JSON not found: {P246I_JSON}"
    return json.loads(P246I_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def p246i_md():
    assert P246I_MD.exists(), f"P246I MD not found: {P246I_MD}"
    return P246I_MD.read_text(encoding="utf-8")


# Structure
def test_p246i_json_parses(p246i_data):
    assert isinstance(p246i_data, dict)

def test_p246i_task_id(p246i_data):
    assert p246i_data.get("task_id") == "P246I"

def test_p246i_classification(p246i_data):
    assert "P246I" in p246i_data.get("classification", "")

def test_p246i_db_write_not_performed(p246i_data):
    assert p246i_data.get("db_write_performed") is False

def test_p246i_p246h_pr_mentioned(p246i_data):
    assert "323" in str(p246i_data.get("p246h_merged_pr", ""))


# Raw vs canonical populations distinct
def test_p246i_raw_and_canonical_distinct(p246i_data):
    raw = p246i_data.get("raw_population_count")
    canonical = p246i_data.get("canonical_population_count")
    assert raw is not None and canonical is not None
    assert raw != canonical, "raw and canonical counts must be distinct"
    assert raw > canonical, "raw must be larger than canonical"

def test_p246i_raw_count_is_22238(p246i_data):
    assert p246i_data.get("raw_population_count") == 22238

def test_p246i_canonical_count_around_2113(p246i_data):
    canonical = p246i_data.get("canonical_population_count")
    assert 2100 <= canonical <= 2200, f"canonical count should be ~2113, got {canonical}"

def test_p246i_add_on_excluded_count(p246i_data):
    addon = p246i_data.get("add_on_excluded_count")
    assert addon == 19100


# Add-on count represented as valid-but-excluded
def test_p246i_add_on_described_as_valid(p246i_data):
    full_text = json.dumps(p246i_data, ensure_ascii=False).lower()
    assert "valid lottery-related" in full_text or "valid lottery related" in full_text

def test_p246i_add_on_excluded_from_research(p246i_data):
    full_text = json.dumps(p246i_data, ensure_ascii=False).lower()
    assert "excluded from" in full_text or "excluded from research" in full_text

def test_p246i_population_definitions_present(p246i_data):
    pd = p246i_data.get("population_definitions", {})
    assert "canonical_research" in pd or "raw_total" in pd


# Updated tests have P246I comments (not implying 22,238 is canonical)
def test_p238b_test_has_p246i_comment():
    p238b_file = REPO_ROOT / "tests" / "test_p238b_nist_randomness_audit_artifact_build.py"
    assert p238b_file.exists()
    content = p238b_file.read_text(encoding="utf-8")
    assert "P246I NOTE" in content or "canonical ~2,113" in content, \
        "test_p238b must have P246I inline comment distinguishing raw vs canonical"

def test_p243a_test_has_p246i_comment():
    p243a_file = REPO_ROOT / "tests" / "test_p243a_diagnostic_report_fixture_pack.py"
    assert p243a_file.exists()
    content = p243a_file.read_text(encoding="utf-8")
    assert "P246I NOTE" in content or "canonical ~2,113" in content, \
        "test_p243a must have P246I inline comment on sample_size=22238"

def test_p238b_assertion_value_preserved():
    """The >= 22238 assertion must still be present (value unchanged for current DB state)."""
    p238b_file = REPO_ROOT / "tests" / "test_p238b_nist_randomness_audit_artifact_build.py"
    content = p238b_file.read_text(encoding="utf-8")
    assert ">= 22238" in content, \
        "test_p238b must still have >= 22238 assertion (raw count; valid for current DB state)"

def test_p243a_fixture_value_preserved():
    """Historical fixture sample_size=22238 must be unchanged."""
    p243a_file = REPO_ROOT / "tests" / "test_p243a_diagnostic_report_fixture_pack.py"
    content = p243a_file.read_text(encoding="utf-8")
    assert "sample_size=22238" in content, \
        "test_p243a historical fixture sample_size=22238 must be preserved"

def test_p246i_updated_files_listed(p246i_data):
    updated = p246i_data.get("updated_files", [])
    files_str = json.dumps(updated).lower()
    assert "p238b" in files_str
    assert "p243a" in files_str

def test_p246i_assertion_values_unchanged(p246i_data):
    updated = p246i_data.get("updated_files", [])
    for f in updated:
        assert f.get("assertion_value_changed") is False, \
            f"No assertion value should be changed in P246I; found {f}"


# Historical artifacts documented
def test_p246i_superseded_historical_notes_present(p246i_data):
    notes = p246i_data.get("superseded_historical_notes", [])
    assert len(notes) >= 1

def test_p246i_historical_result_not_changed(p246i_data):
    for note in p246i_data.get("superseded_historical_notes", []):
        assert note.get("historical_result_changed") is False, \
            "Historical artifact results must not be changed"

def test_p246i_remaining_followups_listed(p246i_data):
    followups = p246i_data.get("remaining_followups", [])
    assert len(followups) >= 2
    followups_str = " ".join(followups).lower()
    assert "p247" in followups_str or "type d" in followups_str

def test_p246i_p238b_needs_canonical_rerun_noted(p246i_data):
    followups_str = " ".join(p246i_data.get("remaining_followups", [])).lower()
    assert "p238b" in followups_str or "nist" in followups_str or "re-run" in followups_str or "re_run" in followups_str


# Forbidden actions
def test_p246i_forbidden_actions_present(p246i_data):
    fa = p246i_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(fa).lower()
    assert "db_write" in fa_str
    assert "delet" in fa_str
    assert "strategy" in fa_str
    assert "betting" in fa_str or "bet" in fa_str


# Add-on preserved
def test_p246i_raw_access_preserved_field(p246i_data):
    raw = p246i_data.get("raw_access_preserved", {})
    desc = str(raw.get("description", "")).lower()
    assert "preserv" in desc or "get_all_draws" in desc


# Markdown
def test_p246i_md_no_db_write(p246i_md):
    assert "no db write" in p246i_md.lower()

def test_p246i_md_addon_preserved(p246i_md):
    assert "preserved" in p246i_md.lower()

def test_p246i_md_population_table(p246i_md):
    text = p246i_md.lower()
    assert "22,238" in text or "22238" in text
    assert "2,113" in text or "2113" in text


# Script
def test_p246i_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246i", REPO_ROOT / "analysis" / "p246i_big_lotto_population_assertion_cleanup.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "run_population_cleanup")
    assert hasattr(mod, "RAW_POPULATION_COUNT")
    assert hasattr(mod, "CANONICAL_POPULATION_COUNT")
    assert mod.RAW_POPULATION_COUNT == 22238
    assert mod.CANONICAL_POPULATION_COUNT == 2113

def test_p246i_run_cleanup_returns_verified():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246i", REPO_ROOT / "analysis" / "p246i_big_lotto_population_assertion_cleanup.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.run_population_cleanup()
    assert result["task_id"] == "P246I"
    assert result["db_write_performed"] is False
    v = result.get("verification", {})
    assert v.get("test_p238b_comment_added") is True
    assert v.get("test_p243a_comment_added") is True

def test_p246i_final_decision_present(p246i_data):
    fd = p246i_data.get("final_decision", "")
    assert len(fd) > 50
    assert "no db write" in fd.lower()
    assert "22238" in fd or "22,238" in fd
    assert "2113" in fd or "2,113" in fd
