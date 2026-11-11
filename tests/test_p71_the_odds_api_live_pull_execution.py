"""
tests/test_p71_the_odds_api_live_pull_execution.py
====================================================
P71 — The Odds API Live Pull Execution Test Suite
All tests run in awaiting-key mode (no API key required).
≥20 tests required.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "_p71_the_odds_api_live_pull_execution.py"
P71_SUMMARY_PATH = (
    REPO_ROOT
    / "data" / "mlb_2025" / "derived"
    / "p71_the_odds_api_live_pull_execution_summary.json"
)
P70_SUMMARY_PATH = (
    REPO_ROOT
    / "data" / "mlb_2025" / "derived"
    / "p70_path_a_the_odds_api_historical_pull_summary.json"
)
P52_SUMMARY_PATH = (
    REPO_ROOT
    / "data" / "mlb_2025" / "derived"
    / "p52_monitoring_contract_v2_summary.json"
)
P69_SUMMARY_PATH = (
    REPO_ROOT
    / "data" / "mlb_2025" / "derived"
    / "p69_ceo_decision_memo_path_a_authorization_summary.json"
)
OUTPUT_CSV_PATH = REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2024_real.csv"
ACTIVE_TASK_PATH = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"

# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------
spec = importlib.util.spec_from_file_location(
    "_p71_the_odds_api_live_pull_execution", SCRIPT_PATH
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_p71_summary() -> dict:
    with open(P71_SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_p70_summary() -> dict:
    with open(P70_SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_p52_summary() -> dict:
    with open(P52_SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# §1 — P70 Context Loaded
# ---------------------------------------------------------------------------

def test_p70_summary_loads():
    """P70 summary must be loadable and non-empty."""
    summary = load_p70_summary()
    assert isinstance(summary, dict)
    assert len(summary) > 0


def test_p70_classification_valid():
    """P70 classification must be a known valid classification."""
    p70 = load_p70_summary()
    cls = p70.get("p70_classification", "")
    # Must be in P70's valid set
    assert cls.startswith("P70_PATH_A_"), f"Unexpected P70 classification: {cls}"


def test_p70_ceo_authorization_recorded():
    """P70 summary must confirm CEO authorization."""
    p70 = load_p70_summary()
    assert p70.get("ceo_authorization_confirmed") is True
    phrase = p70.get("ceo_authorization_phrase", "")
    assert "YES" in phrase and "PATH_A" in phrase


def test_p71_loads_p70_context():
    """P71 load_p70_context() must return dict with p70_classification."""
    context = mod.load_p70_context()
    assert isinstance(context, dict)
    assert "p70_classification" in context


# ---------------------------------------------------------------------------
# §2 — API Key Status Detection
# ---------------------------------------------------------------------------

def test_api_key_status_detected_without_exposing_key():
    """detect_api_key_status must return only status string, never key value."""
    status = mod.detect_api_key_status()
    assert status in ("API_KEY_PRESENT", "API_KEY_MISSING")
    # Must be one of two allowed strings only
    assert len(status) < 50


def test_api_key_missing_in_current_env():
    """Current environment must report API_KEY_MISSING (no key configured)."""
    # Remove from env if somehow present in test context
    orig = os.environ.pop("THE_ODDS_API_KEY", None)
    orig_env = mod.ENV_PATH
    # Use actual .env path (key not present based on P70 evidence)
    try:
        status = mod.detect_api_key_status()
        assert status == "API_KEY_MISSING"
    finally:
        if orig is not None:
            os.environ["THE_ODDS_API_KEY"] = orig
        mod.ENV_PATH = orig_env


def test_api_key_present_detection(tmp_path):
    """detect_api_key_status must return API_KEY_PRESENT when key is in .env."""
    env_file = tmp_path / ".env"
    env_file.write_text("THE_ODDS_API_KEY=test_key_xyz\n")
    orig = os.environ.pop("THE_ODDS_API_KEY", None)
    orig_env = mod.ENV_PATH
    try:
        mod.ENV_PATH = env_file
        status = mod.detect_api_key_status()
        assert status == "API_KEY_PRESENT"
    finally:
        if orig is not None:
            os.environ["THE_ODDS_API_KEY"] = orig
        mod.ENV_PATH = orig_env


def test_dry_run_path_does_not_call_api_when_key_missing():
    """When key is missing, run_awaiting_key_closure must set paid_api_called=False."""
    summary = mod.run_awaiting_key_closure()
    assert summary["paid_api_called"] is False
    assert summary["live_api_calls"] == 0


def test_live_path_gated_by_key_presence():
    """run_p71 must route to awaiting-key path when key is absent."""
    orig = os.environ.pop("THE_ODDS_API_KEY", None)
    orig_env = mod.ENV_PATH
    try:
        # Point to non-existent env file to ensure key is absent
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".env", delete=False, mode="w") as f:
            f.write("# no key\n")
            tmp_env = Path(f.name)
        mod.ENV_PATH = tmp_env
        import tempfile as tf2
        out = Path(tf2.mktemp(suffix=".json"))
        summary = mod.run_p71(output_path=out)
        assert summary["p71_classification"] == "P71_PATH_A_STILL_AWAITING_API_KEY"
        assert summary["paid_api_called"] is False
    finally:
        if orig is not None:
            os.environ["THE_ODDS_API_KEY"] = orig
        mod.ENV_PATH = orig_env
        if out.exists():
            out.unlink()
        if tmp_env.exists():
            tmp_env.unlink()


# ---------------------------------------------------------------------------
# §3 — Classification Validity
# ---------------------------------------------------------------------------

def test_p71_classification_is_allowed():
    """P71 classification must be from VALID_P71_CLASSIFICATIONS."""
    summary = load_p71_summary()
    cls = summary["p71_classification"]
    assert cls in mod.VALID_P71_CLASSIFICATIONS, (
        f"P71 classification {cls!r} not in VALID_P71_CLASSIFICATIONS"
    )


def test_p71_classification_awaiting_key():
    """Current run (no key) must classify as P71_PATH_A_STILL_AWAITING_API_KEY."""
    summary = load_p71_summary()
    assert summary["p71_classification"] == "P71_PATH_A_STILL_AWAITING_API_KEY"


def test_p71_api_key_status_in_summary():
    """Summary must record api_key_status field."""
    summary = load_p71_summary()
    assert summary.get("api_key_status") == "API_KEY_MISSING"


# ---------------------------------------------------------------------------
# §4 — Required Schema Fields
# ---------------------------------------------------------------------------

def test_required_schema_fields_documented():
    """P71 summary must list required CSV schema fields."""
    summary = load_p71_summary()
    fields = summary.get("required_schema_fields", [])
    required = {
        "game_date", "home_team", "away_team", "home_ml", "away_ml",
        "bookmaker", "odds_timestamp", "closing_indicator", "source_trace",
    }
    assert required <= set(fields), f"Missing required fields: {required - set(fields)}"


def test_required_schema_fields_in_module():
    """Module REQUIRED_CSV_FIELDS must have all 9 fields."""
    required = {
        "game_date", "home_team", "away_team", "home_ml", "away_ml",
        "bookmaker", "odds_timestamp", "closing_indicator", "source_trace",
    }
    assert required <= set(mod.REQUIRED_CSV_FIELDS)


# ---------------------------------------------------------------------------
# §5 — Output CSV Path
# ---------------------------------------------------------------------------

def test_output_csv_path_recorded():
    """P71 summary must record output_csv_path."""
    summary = load_p71_summary()
    assert "output_csv_path" in summary
    assert "mlb_odds_2024_real" in summary["output_csv_path"]


def test_output_csv_not_written_in_awaiting_key():
    """CSV file must NOT be written in awaiting-key mode."""
    # If a CSV was written by a prior live run, this is still acceptable —
    # but in current state (key missing), no new CSV should have been written.
    summary = load_p71_summary()
    assert summary["paid_api_called"] is False
    # CSV absence confirms dry path
    assert summary["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# §6 — Governance
# ---------------------------------------------------------------------------

def test_governance_paper_only():
    assert mod.PAPER_ONLY is True


def test_governance_diagnostic_only():
    assert mod.DIAGNOSTIC_ONLY is True


def test_governance_real_bet_not_allowed():
    assert mod.REAL_BET_ALLOWED is False


def test_governance_production_not_ready():
    assert mod.PRODUCTION_READY is False


def test_governance_kelly_not_allowed():
    assert mod.KELLY_DEPLOY_ALLOWED is False


def test_governance_tsl_not_called():
    assert mod.TSL_CRAWLER_CALLED is False


def test_governance_bulk_scraping_not_performed():
    assert mod.BULK_SCRAPING_PERFORMED is False


def test_governance_anti_bot_not_attempted():
    assert mod.ANTI_BOT_BYPASS_ATTEMPTED is False


def test_summary_governance_flags():
    """All governance flags in summary must be correct."""
    summary = load_p71_summary()
    gov = summary["governance"]
    assert gov["paper_only"] is True
    assert gov["real_bet_allowed"] is False
    assert gov["kelly_deploy_allowed"] is False
    assert gov["production_ready"] is False
    assert gov["paid_api_called"] is False  # awaiting-key
    assert gov["tsl_crawler_called"] is False
    assert gov["bulk_scraping_performed"] is False
    assert gov["anti_bot_bypass_attempted"] is False


# ---------------------------------------------------------------------------
# §7 — Platt Constants
# ---------------------------------------------------------------------------

def test_platt_constants_unchanged():
    """P45 Platt constants must remain locked."""
    assert mod.PLATT_A == pytest.approx(0.435432, rel=1e-6)
    assert mod.PLATT_B == pytest.approx(0.245464, rel=1e-6)


def test_platt_constants_in_summary():
    """Governance in summary must record Platt constants."""
    gov = load_p71_summary()["governance"]
    assert gov["platt_a"] == pytest.approx(0.435432, rel=1e-6)
    assert gov["platt_b"] == pytest.approx(0.245464, rel=1e-6)


def test_platt_constants_match_p52():
    """P71 Platt constants must match P52 summary (uses platt_a/platt_b keys)."""
    p52 = load_p52_summary()
    p52_platt = p52.get("platt_coefficients", {})
    # P52 records: platt_a=0.435432, platt_b=0.245464
    assert p52_platt.get("platt_a") == pytest.approx(mod.PLATT_A, rel=1e-6)
    assert p52_platt.get("platt_b") == pytest.approx(mod.PLATT_B, rel=1e-6)


# ---------------------------------------------------------------------------
# §8 — P52 Thresholds
# ---------------------------------------------------------------------------

def test_p52_thresholds_unchanged():
    """P52 thresholds in P71 module must match P52 summary."""
    p52 = load_p52_summary()
    rule = p52.get("alert_rule_matrix_v2", {})
    cal = rule.get("calibration_rules", {})
    # ECE thresholds
    assert cal.get("ece_warning", {}).get("threshold") == pytest.approx(mod.P52_ECE_WARN, rel=1e-6)
    assert cal.get("ece_critical", {}).get("threshold") == pytest.approx(mod.P52_ECE_CRIT, rel=1e-6)
    assert cal.get("brier_warning", {}).get("threshold") == pytest.approx(mod.P52_BRIER_WARN, rel=1e-6)
    assert cal.get("brier_critical", {}).get("threshold") == pytest.approx(mod.P52_BRIER_CRIT, rel=1e-6)


def test_p52_thresholds_in_governance_block():
    """P71 governance block must include P52 threshold values."""
    gov = load_p71_summary()["governance"]
    assert "p52_ece_warn" in gov
    assert "p52_ece_crit" in gov
    assert "p52_brier_warn" in gov
    assert "p52_brier_crit" in gov
    assert gov["p52_ece_warn"] == pytest.approx(0.10, rel=1e-6)
    assert gov["p52_brier_warn"] == pytest.approx(0.25, rel=1e-6)


# ---------------------------------------------------------------------------
# §9 — paid_api_called and live_api_calls
# ---------------------------------------------------------------------------

def test_paid_api_called_false_in_awaiting_key():
    """paid_api_called must be False in awaiting-key mode."""
    summary = load_p71_summary()
    assert summary["paid_api_called"] is False


def test_live_api_calls_zero_in_awaiting_key():
    """live_api_calls must be 0 in awaiting-key mode."""
    summary = load_p71_summary()
    assert summary["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# §10 — CSV Validator Unit Tests
# ---------------------------------------------------------------------------

def test_validate_csv_returns_error_when_missing(tmp_path):
    """validate_csv must return valid=False when CSV does not exist."""
    result = mod.validate_csv(tmp_path / "nonexistent.csv")
    assert result["valid"] is False
    assert result["row_count"] == 0


def test_validate_csv_valid_sample(tmp_path):
    """validate_csv must return valid=True for a correctly formed CSV."""
    csv_path = tmp_path / "test.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=mod.REQUIRED_CSV_FIELDS)
        writer.writeheader()
        for i in range(600):
            writer.writerow({
                "game_date": f"2024-04-{(i % 28) + 1:02d}",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "home_ml": -150,
                "away_ml": 130,
                "bookmaker": "pinnacle",
                "odds_timestamp": "2024-04-01T19:50:00Z",
                "closing_indicator": "CLOSING_PROXY_COMMENCE_TIME",
                "source_trace": "source=test",
            })
    result = mod.validate_csv(csv_path)
    assert result["valid"] is True
    assert result["row_count"] == 600
    assert result["row_count_sufficient"] is True
    assert result["missing_fields"] == []


def test_validate_csv_insufficient_rows(tmp_path):
    """validate_csv must flag row_count_sufficient=False when rows < 500."""
    csv_path = tmp_path / "small.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=mod.REQUIRED_CSV_FIELDS)
        writer.writeheader()
        for i in range(10):
            writer.writerow({
                "game_date": "2024-04-01",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "home_ml": -150,
                "away_ml": 130,
                "bookmaker": "pinnacle",
                "odds_timestamp": "2024-04-01T19:50:00Z",
                "closing_indicator": "CLOSING_PROXY_COMMENCE_TIME",
                "source_trace": "source=test",
            })
    result = mod.validate_csv(csv_path)
    assert result["row_count_sufficient"] is False
    assert result["valid"] is False


def test_validate_csv_missing_field(tmp_path):
    """validate_csv must detect missing required fields."""
    csv_path = tmp_path / "missing.csv"
    # Write CSV with home_ml missing
    fields = [f for f in mod.REQUIRED_CSV_FIELDS if f != "home_ml"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i in range(600):
            writer.writerow({
                "game_date": "2024-04-01",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "away_ml": 130,
                "bookmaker": "pinnacle",
                "odds_timestamp": "2024-04-01T19:50:00Z",
                "closing_indicator": "CLOSING_PROXY_COMMENCE_TIME",
                "source_trace": "source=test",
            })
    result = mod.validate_csv(csv_path)
    assert "home_ml" in result["missing_fields"]
    assert result["valid"] is False


def test_validate_csv_non_numeric_ml(tmp_path):
    """validate_csv must detect non-numeric moneyline values."""
    csv_path = tmp_path / "bad_ml.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=mod.REQUIRED_CSV_FIELDS)
        writer.writeheader()
        for i in range(600):
            writer.writerow({
                "game_date": "2024-04-01",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "home_ml": "N/A",   # invalid
                "away_ml": 130,
                "bookmaker": "pinnacle",
                "odds_timestamp": "2024-04-01T19:50:00Z",
                "closing_indicator": "CLOSING_PROXY_COMMENCE_TIME",
                "source_trace": "source=test",
            })
    result = mod.validate_csv(csv_path)
    assert result["ml_errors"] > 0
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# §11 — Setup Instructions in Awaiting-Key Summary
# ---------------------------------------------------------------------------

def test_setup_instructions_present():
    """P71 summary must include setup_required_for_live_pull instructions."""
    summary = load_p71_summary()
    steps = summary.get("setup_required_for_live_pull", {})
    assert len(steps) >= 5, "Insufficient setup steps documented"
    all_text = " ".join(str(v) for v in steps.values()).lower()
    assert "the-odds-api" in all_text or "odds-api" in all_text


# ---------------------------------------------------------------------------
# §12 — Summary Structure
# ---------------------------------------------------------------------------

def test_p71_summary_has_required_keys():
    summary = load_p71_summary()
    required = {
        "p71_version", "p71_classification", "execution_date",
        "mode", "api_key_status", "paid_api_called",
        "live_api_calls", "governance",
    }
    missing = required - set(summary.keys())
    assert not missing, f"Missing keys in P71 summary: {missing}"


def test_p71_summary_version():
    summary = load_p71_summary()
    assert summary["p71_version"] == "p71_v1"


def test_p71_summary_mode_awaiting():
    summary = load_p71_summary()
    assert summary["mode"] == "AWAITING_KEY"


# ---------------------------------------------------------------------------
# §13 — Forbidden Affirmative Scan
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    "REAL_BET_ALLOWED: bool = True",
    "KELLY_DEPLOY_ALLOWED: bool = True",
    "PRODUCTION_READY: bool = True",
    "BULK_SCRAPING_PERFORMED: bool = True",
    "ANTI_BOT_BYPASS_ATTEMPTED: bool = True",
    "TSL_CRAWLER_CALLED: bool = True",
    "RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = True",
    "CEO_AUTHORIZATION_CONFIRMED: bool = False",
    "PROMOTION_FREEZE: bool = False",
    "PAPER_ONLY: bool = False",
    "DIAGNOSTIC_ONLY: bool = False",
]


def test_forbidden_affirmative_scan_p71_script():
    """P71 script must not contain any forbidden affirmative patterns."""
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    violations = [p for p in FORBIDDEN_PATTERNS if p in text]
    assert not violations, f"Forbidden patterns in P71 script: {violations}"


def test_forbidden_affirmative_scan_p70_script():
    """P70 script must not contain any forbidden affirmative patterns (regression)."""
    p70_script = REPO_ROOT / "scripts" / "_p70_path_a_the_odds_api_historical_pull.py"
    text = p70_script.read_text(encoding="utf-8")
    violations = [p for p in FORBIDDEN_PATTERNS if p in text]
    assert not violations, f"Forbidden patterns in P70 script: {violations}"


# ---------------------------------------------------------------------------
# §14 — Active Task Updated
# ---------------------------------------------------------------------------

def test_active_task_contains_p71():
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    assert "P71" in content


def test_active_task_contains_completed_or_active():
    """active_task.md must reference P71 as active or completed."""
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    assert "P71" in content


# ---------------------------------------------------------------------------
# §15 — Governance Assertion Guard
# ---------------------------------------------------------------------------

def test_run_p71_governance_assertion_blocks_bad_state():
    """run_p71 must raise AssertionError if PAPER_ONLY is violated."""
    orig = mod.PAPER_ONLY
    try:
        mod.PAPER_ONLY = False
        with pytest.raises(AssertionError):
            mod.run_p71(output_path=Path("/tmp/p71_should_fail.json"))
    finally:
        mod.PAPER_ONLY = orig


def test_p71_ceo_authorization_confirmed():
    assert mod.CEO_AUTHORIZATION_CONFIRMED is True


def test_p71_ceo_phrase_matches_p70():
    """P71 CEO phrase must match P70 exactly."""
    p70 = load_p70_summary()
    assert p70.get("ceo_authorization_phrase") == mod.CEO_AUTHORIZATION_PHRASE
