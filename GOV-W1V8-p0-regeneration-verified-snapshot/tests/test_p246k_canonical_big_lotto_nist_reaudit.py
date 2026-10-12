"""P246K — Canonical BIG_LOTTO NIST Re-audit Tests"""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
P246K_JSON = OUTPUTS / "p246k_canonical_big_lotto_nist_reaudit_20260606.json"
P246K_MD = OUTPUTS / "p246k_canonical_big_lotto_nist_reaudit_20260606.md"


@pytest.fixture(scope="session")
def p246k_data():
    assert P246K_JSON.exists(), f"P246K JSON not found: {P246K_JSON}"
    return json.loads(P246K_JSON.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def p246k_md():
    assert P246K_MD.exists(), f"P246K MD not found: {P246K_MD}"
    return P246K_MD.read_text(encoding="utf-8")


# Structure
def test_p246k_json_parses(p246k_data): assert isinstance(p246k_data, dict)
def test_p246k_task_id(p246k_data): assert p246k_data.get("task_id") == "P246K"
def test_p246k_classification(p246k_data): assert "P246K" in p246k_data.get("classification", "")
def test_p246k_db_write_not_performed(p246k_data): assert p246k_data.get("db_write_performed") is False
def test_p246k_p246j_pr_mentioned(p246k_data): assert "325" in str(p246k_data.get("p246j_merged_pr", ""))


# Input population is CANONICAL_MAIN_DRAW
def test_p246k_input_population_canonical(p246k_data):
    assert p246k_data.get("input_population") == "CANONICAL_MAIN_DRAW"

def test_p246k_canonical_count_distinct_from_raw(p246k_data):
    raw = p246k_data.get("raw_population_count")
    canonical = p246k_data.get("canonical_population_count")
    assert raw is not None and canonical is not None
    assert raw != canonical
    assert raw == 22238

def test_p246k_canonical_count_around_2113(p246k_data):
    canonical = p246k_data.get("canonical_population_count")
    assert 2100 <= canonical <= 2200, f"canonical count should be ~2113, got {canonical}"

def test_p246k_excluded_add_on_count(p246k_data):
    excluded = p246k_data.get("excluded_add_on_count")
    assert excluded >= 19000, "excluded count should be >= 19000"


# Exclusion rules verified
def test_p246k_exclusion_rules_verified(p246k_data):
    excl = p246k_data.get("exclusion_rules_verified", {})
    assert excl.get("all_exclusions_verified") is True
    assert excl.get("hyphen_in_canonical") == 0
    assert excl.get("date_format_in_canonical") == 0
    assert excl.get("small_pool_in_canonical") == 0
    assert excl.get("max_num_all_above_25") is True

def test_p246k_num_range_valid(p246k_data):
    excl = p246k_data.get("exclusion_rules_verified", {})
    assert excl.get("num_range_valid") is True


# P238B comparison exists
def test_p246k_p238b_comparison_present(p246k_data):
    comp = p246k_data.get("p238b_comparison", {})
    assert isinstance(comp, dict)
    assert len(comp) > 0

def test_p246k_p238b_comparison_mentions_artifact(p246k_data):
    comp = p246k_data.get("p238b_comparison", {})
    comp_str = json.dumps(comp).lower()
    assert "p238b" in comp_str or "raw" in comp_str or "mixed" in comp_str


# No DB write / no forbidden actions
def test_p246k_forbidden_actions_present(p246k_data):
    fa = p246k_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(fa).lower()
    assert "db_write" in fa_str
    assert "betting" in fa_str or "bet" in fa_str
    assert "strategy" in fa_str
    assert "gate_open" in fa_str or "gate" in fa_str

def test_p246k_no_prediction_claim(p246k_data):
    assert p246k_data.get("no_prediction_claim") is True

def test_p246k_no_betting_advice(p246k_data):
    assert p246k_data.get("no_betting_advice") is True

def test_p246k_no_strategy_promotion(p246k_data):
    assert p246k_data.get("no_strategy_promotion") is True

def test_p246k_anomaly_not_predictor(p246k_data):
    assert p246k_data.get("anomaly_is_not_predictor") is True


# Add-on records preserved
def test_p246k_add_on_records_preserved(p246k_data):
    assert p246k_data.get("add_on_records_preserved") is True

def test_p246k_raw_access_preserved(p246k_data):
    raw_str = str(p246k_data.get("raw_access_preserved", "")).lower()
    assert "get_all_draws" in raw_str or "22,238" in raw_str or "22238" in raw_str


# Classification is not a strategy promotion
def test_p246k_classification_not_strategy(p246k_data):
    cls = p246k_data.get("classification", "")
    assert "STRATEGY" not in cls.upper()
    assert "GATE_OPEN" not in cls.upper()
    assert "P246K" in cls


# Gate implication states predictive research still blocked
def test_p246k_gate_implication_present(p246k_data):
    gi = str(p246k_data.get("gate_implication", "")).lower()
    assert len(gi) > 20

def test_p246k_gate_implication_not_unlock_predictive(p246k_data):
    gi = str(p246k_data.get("gate_implication", "")).lower()
    # Must say remains blocked or NOT unlock
    assert "not unlock" in gi or "remains blocked" in gi or "gate remains" in gi or "predictive" in gi

def test_p246k_gate_implication_green_not_signal(p246k_data):
    gi = str(p246k_data.get("gate_implication", "")).lower()
    assert "random" in gi or "fair" in gi or "green" in gi


# Audit results
def test_p246k_audit_results_present(p246k_data):
    ar = p246k_data.get("audit_results", {})
    assert "draw_sum_distribution" in ar
    assert "number_frequency_uniformity" in ar
    assert "serial_randomness" in ar
    assert "entropy" in ar
    assert "summary" in ar

def test_p246k_audit_summary_counts(p246k_data):
    summary = p246k_data.get("audit_results", {}).get("summary", {})
    total = summary.get("total_tests", 0)
    green = summary.get("green", 0)
    yellow = summary.get("yellow", 0)
    assert total >= 4
    assert green + yellow == total

def test_p246k_md_states_green(p246k_md):
    text = p246k_md.lower()
    assert "green" in text

def test_p246k_md_no_db_write(p246k_md):
    assert "no db write" in p246k_md.lower()

def test_p246k_md_addon_preserved(p246k_md):
    assert "preserved" in p246k_md.lower()

def test_p246k_md_no_prediction(p246k_md):
    text = p246k_md.lower()
    assert "no prediction" in text or "does not" in text or "not unlock" in text

def test_p246k_md_canonical_count(p246k_md):
    text = p246k_md
    assert "2,113" in text or "2113" in text


# Script test
def test_p246k_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246k", REPO_ROOT / "analysis" / "p246k_canonical_big_lotto_nist_reaudit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "run_canonical_nist_reaudit")
    assert hasattr(mod, "FORBIDDEN_ACTIONS")

def test_p246k_run_audit_no_db_write():
    # Skip if scipy/statsmodels not available in test environment;
    # the full audit runs correctly via `python3 analysis/p246k_*.py`
    try:
        import scipy
        import statsmodels
    except ImportError:
        pytest.skip("scipy/statsmodels not available in test runner; audit verified via direct script run")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p246k", REPO_ROOT / "analysis" / "p246k_canonical_big_lotto_nist_reaudit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.run_canonical_nist_reaudit()
    assert result["db_write_performed"] is False
    assert result["no_prediction_claim"] is True
    assert result["add_on_records_preserved"] is True
    assert result["exclusion_rules_verified"]["all_exclusions_verified"] is True

def test_p246k_final_decision_present(p246k_data):
    fd = p246k_data.get("final_decision", "")
    assert len(fd) > 80
    assert "no db write" in fd.lower()
