"""
tests/test_p68_oddsportal_tos_scraping_feasibility.py
=======================================================
P68 — OddsPortal ToS and Scraping Feasibility Probe
Test suite: ≥20 tests required.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "_p68_oddsportal_tos_scraping_feasibility.py"
SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "mlb_2025"
    / "derived"
    / "p68_oddsportal_tos_scraping_feasibility_summary.json"
)
P67_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "mlb_2025"
    / "derived"
    / "p67_2024_data_gap_free_source_search_summary.json"
)
ACTIVE_TASK_PATH = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
REPORT_PATH = REPO_ROOT / "report" / "p68_oddsportal_tos_scraping_feasibility_20260526.md"

# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------
import importlib.util

spec = importlib.util.spec_from_file_location(
    "_p68_oddsportal_tos_scraping_feasibility", SCRIPT_PATH
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_summary() -> dict:
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_p67_summary() -> dict:
    with open(P67_SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# §1 — P67 Context Verification
# ---------------------------------------------------------------------------

def test_p67_summary_loads():
    """P67 summary must be loadable."""
    summary = load_p67_summary()
    assert summary, "P67 summary is empty"


def test_p67_classification_valid():
    """P67 classification must be the expected value."""
    summary = load_p67_summary()
    assert summary["p67_classification"] == "P67_PATH_B_PARTIAL_SOURCE_FOUND_NEEDS_REVIEW"


def test_oddsportal_candidate_exists_in_p67():
    """OddsPortal must appear as a candidate in P67."""
    summary = load_p67_summary()
    sources = [s["source_name"] for s in summary["candidate_sources"]]
    assert any("OddsPortal" in name for name in sources), (
        f"OddsPortal not found in P67 candidate sources: {sources}"
    )


def test_p67_2024_data_gap_unresolved():
    """P67 must confirm 2024 data gap remains unresolved."""
    summary = load_p67_summary()
    status = summary.get("data_year_2024_gap_status", "")
    assert "UNRESOLVED" in status, (
        f"Expected 'UNRESOLVED' in data_year_2024_gap_status, got: {status}"
    )


# ---------------------------------------------------------------------------
# §2 — Classification Validation
# ---------------------------------------------------------------------------

def test_tos_classification_is_allowed():
    """ToS classification must be from the allowed set."""
    assert mod.TOS_REVIEW["tos_classification"] in mod.VALID_TOS_CLASSIFICATIONS, (
        f"Invalid ToS classification: {mod.TOS_REVIEW['tos_classification']}"
    )


def test_page_classification_is_allowed():
    """Page structure classification must be from the allowed set."""
    assert mod.PAGE_PROBE["page_classification"] in mod.VALID_PAGE_CLASSIFICATIONS, (
        f"Invalid page classification: {mod.PAGE_PROBE['page_classification']}"
    )


def test_schema_status_is_allowed():
    """Schema status must be from the allowed set."""
    assert mod.SCHEMA_ASSESSMENT["schema_status"] in mod.VALID_SCHEMA_STATUSES, (
        f"Invalid schema status: {mod.SCHEMA_ASSESSMENT['schema_status']}"
    )


def test_p68_final_classification_is_allowed():
    """P68 final classification must be from the allowed set."""
    summary = load_summary()
    assert summary["p68_classification"] in mod.VALID_P68_CLASSIFICATIONS, (
        f"Invalid P68 classification: {summary['p68_classification']}"
    )


# ---------------------------------------------------------------------------
# §3 — Governance Flags
# ---------------------------------------------------------------------------

def test_no_paid_api_called_module_flag():
    assert mod.PAID_API_CALLED is False


def test_no_live_api_called_module_flag():
    assert mod.LIVE_API_CALLS == 0


def test_no_tsl_crawler_called_module_flag():
    assert mod.TSL_CRAWLER_CALLED is False


def test_no_bulk_scraping_performed_module_flag():
    assert mod.BULK_SCRAPING_PERFORMED is False


def test_no_anti_bot_bypass_attempted_module_flag():
    assert mod.ANTI_BOT_BYPASS_ATTEMPTED is False


def test_no_runtime_recommendation_logic_changed():
    assert mod.RUNTIME_RECOMMENDATION_LOGIC_CHANGED is False


def test_platt_constants_unchanged():
    """P45 Platt constants must remain locked."""
    assert mod.PLATT_A == pytest.approx(0.435432, rel=1e-6)
    assert mod.PLATT_B == pytest.approx(0.245464, rel=1e-6)


def test_paper_and_diagnostic_flags_true():
    assert mod.PAPER_ONLY is True
    assert mod.DIAGNOSTIC_ONLY is True


# ---------------------------------------------------------------------------
# §4 — Summary Governance Block
# ---------------------------------------------------------------------------

def test_summary_governance_flags():
    """Summary governance block must have all required flags."""
    summary = load_summary()
    gov = summary["governance"]
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["paid_api_called"] is False
    assert gov["live_api_calls"] == 0
    assert gov["tsl_crawler_called"] is False
    assert gov["bulk_scraping_performed"] is False
    assert gov["anti_bot_bypass_attempted"] is False
    assert gov["runtime_recommendation_logic_changed"] is False
    assert gov["real_bet_allowed"] is False
    assert gov["production_ready"] is False


def test_summary_platt_constants_in_governance():
    """Platt constants must be recorded in governance block."""
    summary = load_summary()
    gov = summary["governance"]
    assert gov["platt_a"] == pytest.approx(0.435432, rel=1e-6)
    assert gov["platt_b"] == pytest.approx(0.245464, rel=1e-6)


# ---------------------------------------------------------------------------
# §5 — Recommendation Consistency
# ---------------------------------------------------------------------------

def test_recommendation_matches_blocked_classification():
    """When P68 is blocked, recommendation must reference CEO decision or PATH_A."""
    summary = load_summary()
    cls = summary["p68_classification"]
    rec = summary["recommendation"]
    if "BLOCKED" in cls:
        assert "CEO" in rec or "PATH_A" in rec, (
            f"Blocked classification {cls!r} must recommend CEO/PATH_A. Got: {rec!r}"
        )


def test_path_a_fallback_present_in_summary():
    """Summary must document PATH_A fallback when OddsPortal is blocked."""
    summary = load_summary()
    assert "path_a_fallback" in summary
    assert summary["path_a_fallback"]["requires_ceo_authorization"] is True


# ---------------------------------------------------------------------------
# §6 — ToS and robots.txt Findings
# ---------------------------------------------------------------------------

def test_tos_blocks_scraping_flag():
    """ToS review must confirm scraping is prohibited."""
    assert mod.TOS_REVIEW["scraping_prohibited"] is True


def test_robots_txt_disallows_historical_years():
    """robots.txt must be documented as disallowing historical year URLs."""
    assert mod.TOS_REVIEW["robots_txt_disallows_historical_years"] is True


def test_tos_database_extraction_prohibited():
    """Database extraction prohibition must be flagged."""
    assert mod.TOS_REVIEW["database_extraction_prohibited"] is True


def test_tos_risk_level_blocking():
    """ToS risk level must be BLOCKING."""
    assert mod.TOS_REVIEW["tos_risk_level"] == "BLOCKING"


# ---------------------------------------------------------------------------
# §7 — Page Probe Integrity
# ---------------------------------------------------------------------------

def test_page_probe_no_bulk_extraction():
    """Page probe must confirm no bulk extraction was performed."""
    probe = mod.PAGE_PROBE
    assert "no automation" in probe["probe_method"].lower() or \
           "no bulk" in probe["probe_method"].lower(), (
        f"probe_method should confirm no automation: {probe['probe_method']!r}"
    )


def test_page_probe_2024_data_confirmed():
    """Page probe must confirm 2024 data was observed."""
    assert mod.PAGE_PROBE["page_reachable"] is True
    assert "2024" in mod.PAGE_PROBE["season_years_confirmed"]


def test_sample_rows_present():
    """At least one sample row must be documented in the page probe."""
    assert len(mod.PAGE_PROBE["sample_rows_observed"]) >= 1


# ---------------------------------------------------------------------------
# §8 — Schema Assessment
# ---------------------------------------------------------------------------

def test_schema_field_coverage_complete():
    """Schema assessment must cover all 9 required fields."""
    required = {
        "game_date", "home_team", "away_team", "home_ml", "away_ml",
        "odds_type", "source_url", "source_observed_at", "provenance_note",
    }
    covered = {fc["required"] for fc in mod.SCHEMA_ASSESSMENT["field_coverage"]}
    missing = required - covered
    assert not missing, f"Missing required field coverage: {missing}"


def test_schema_status_blocked_when_tos_blocks():
    """Schema status must be BLOCKED when ToS classification is TOS_BLOCKS_SCRAPING."""
    if mod.TOS_REVIEW["tos_classification"] == "TOS_BLOCKS_SCRAPING":
        assert "BLOCKED" in mod.SCHEMA_ASSESSMENT["schema_status"], (
            f"Schema must be BLOCKED when ToS blocks scraping. Got: "
            f"{mod.SCHEMA_ASSESSMENT['schema_status']!r}"
        )


# ---------------------------------------------------------------------------
# §9 — Forbidden Affirmative Scan
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    "production_ready = True",
    "kelly_deploy_allowed = True",
    "real_bet_allowed = True",
    "paid_api_called = True",
    "LIVE_API_CALLS: int = 1",
    "TSL_CRAWLER_CALLED: bool = True",
    "BULK_SCRAPING_PERFORMED: bool = True",
    "ANTI_BOT_BYPASS_ATTEMPTED: bool = True",
    "RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = True",
    "PROMOTION_FREEZE: bool = False",
]


def test_forbidden_affirmative_scan_in_script():
    """Script must not contain any forbidden affirmative patterns."""
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")
    violations = [p for p in FORBIDDEN_PATTERNS if p in script_text]
    assert not violations, (
        f"Forbidden patterns found in P68 script: {violations}"
    )


# ---------------------------------------------------------------------------
# §10 — Data Year 2024 Gap
# ---------------------------------------------------------------------------

def test_data_year_2024_gap_remains_module_flag():
    """Module must flag 2024 data gap as remaining."""
    assert mod.DATA_YEAR_2024_GAP_REMAINS is True


def test_data_year_2024_gap_status_in_summary():
    """Summary must document 2024 gap status as unresolved."""
    summary = load_summary()
    status = summary.get("data_year_2024_gap_status", "")
    assert "UNRESOLVED" in status, f"Expected UNRESOLVED in gap status, got: {status!r}"


# ---------------------------------------------------------------------------
# §11 — Active Task Updated
# ---------------------------------------------------------------------------

def test_active_task_md_exists():
    """active_task.md must exist."""
    assert ACTIVE_TASK_PATH.exists(), f"active_task.md not found at {ACTIVE_TASK_PATH}"


def test_active_task_md_contains_p68_completed():
    """active_task.md must contain P68 and COMPLETED after task completion."""
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    assert "P68" in content and "COMPLETED" in content, (
        "active_task.md must contain both 'P68' and 'COMPLETED'"
    )


# ---------------------------------------------------------------------------
# §12 — Summary Structure
# ---------------------------------------------------------------------------

def test_summary_has_required_top_level_keys():
    """Summary JSON must have all required top-level keys."""
    summary = load_summary()
    required_keys = {
        "p68_version",
        "p68_classification",
        "probe_date",
        "candidate_source",
        "candidate_url",
        "p67_classification_verified",
        "data_year_2024_gap_status",
        "tos_review",
        "page_probe",
        "schema_assessment",
        "recommendation",
        "path_a_fallback",
        "governance",
    }
    missing = required_keys - set(summary.keys())
    assert not missing, f"Missing summary keys: {missing}"


def test_p68_blocked_by_tos_classification():
    """P68 final classification must be P68_ODDSPORTAL_BLOCKED_BY_TOS."""
    summary = load_summary()
    assert summary["p68_classification"] == "P68_ODDSPORTAL_BLOCKED_BY_TOS", (
        f"Expected P68_ODDSPORTAL_BLOCKED_BY_TOS, got: {summary['p68_classification']!r}"
    )
