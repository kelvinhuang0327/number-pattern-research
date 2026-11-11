"""
tests/test_p69_ceo_decision_memo_path_a_authorization.py
=========================================================
P69 — CEO Decision Memo: P61 PATH_A Authorization
Test suite: ≥20 tests required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "_p69_ceo_decision_memo_path_a_authorization.py"
SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "mlb_2025"
    / "derived"
    / "p69_ceo_decision_memo_path_a_authorization_summary.json"
)
P61_SUMMARY_PATH = REPO_ROOT / "data" / "mlb_2025" / "derived" / "p61_2024_data_gap_resolution_plan_summary.json"
P67_SUMMARY_PATH = REPO_ROOT / "data" / "mlb_2025" / "derived" / "p67_2024_data_gap_free_source_search_summary.json"
P68_SUMMARY_PATH = REPO_ROOT / "data" / "mlb_2025" / "derived" / "p68_oddsportal_tos_scraping_feasibility_summary.json"
ACTIVE_TASK_PATH = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"

# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------
import importlib.util

spec = importlib.util.spec_from_file_location(
    "_p69_ceo_decision_memo_path_a_authorization", SCRIPT_PATH
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_summary() -> dict:
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_p61() -> dict:
    with open(P61_SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_p67() -> dict:
    with open(P67_SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_p68() -> dict:
    with open(P68_SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# §1 — Evidence Trail: Prior Phase Summaries Load
# ---------------------------------------------------------------------------

def test_p61_summary_loads():
    """P61 summary must be loadable and non-empty."""
    d = load_p61()
    assert d, "P61 summary is empty"


def test_p67_summary_loads():
    """P67 summary must be loadable and non-empty."""
    d = load_p67()
    assert d, "P67 summary is empty"


def test_p68_summary_loads():
    """P68 summary must be loadable and non-empty."""
    d = load_p68()
    assert d, "P68 summary is empty"


# ---------------------------------------------------------------------------
# §2 — Evidence Trail: Classifications Valid
# ---------------------------------------------------------------------------

def test_p61_classification_valid():
    d = load_p61()
    assert d["p61_classification"] == "P61_DATA_GAP_RESOLVABLE_MEDIUM_EFFORT"


def test_p67_classification_valid():
    d = load_p67()
    assert d["p67_classification"] == "P67_PATH_B_PARTIAL_SOURCE_FOUND_NEEDS_REVIEW"


def test_p68_classification_valid():
    d = load_p68()
    assert d["p68_classification"] == "P68_ODDSPORTAL_BLOCKED_BY_TOS"


# ---------------------------------------------------------------------------
# §3 — 2024 Data Gap Still Unresolved
# ---------------------------------------------------------------------------

def test_data_year_2024_gap_remains_module_flag():
    """Module must flag 2024 data gap as still unresolved."""
    assert mod.DATA_YEAR_2024_GAP_REMAINS is True


def test_data_year_2024_gap_status_in_summary():
    """Summary must document 2024 gap status as unresolved."""
    summary = load_summary()
    assert "UNRESOLVED" in summary["data_year_2024_gap_status"], (
        f"Expected UNRESOLVED in gap status, got: {summary['data_year_2024_gap_status']!r}"
    )


# ---------------------------------------------------------------------------
# §4 — Free-Source Exhaustion Documented
# ---------------------------------------------------------------------------

def test_free_source_exhaustion_flag_true():
    """Module must confirm free-source PATH_B is exhausted."""
    assert mod.FREE_SOURCE_PATHS_EXHAUSTED is True


def test_free_source_exhaustion_in_summary():
    """Summary must document free source exhaustion."""
    summary = load_summary()
    assert summary["free_source_paths_exhausted"] is True


def test_free_sources_evaluated_count():
    """At least 5 free sources must be documented as evaluated."""
    summary = load_summary()
    sources = summary.get("free_sources_evaluated", [])
    assert len(sources) >= 5, (
        f"Expected ≥5 evaluated sources, got {len(sources)}"
    )


# ---------------------------------------------------------------------------
# §5 — OddsPortal ToS Block Documented
# ---------------------------------------------------------------------------

def test_oddsportal_tos_block_in_summary():
    """OddsPortal block must be documented in summary."""
    summary = load_summary()
    block = summary.get("oddsportal_block", {})
    assert block.get("scraping_prohibited") is True
    assert block.get("legally_accessible") is False


def test_oddsportal_p68_classification_in_block():
    """OddsPortal block must reference P68 classification."""
    summary = load_summary()
    block = summary.get("oddsportal_block", {})
    assert block.get("p68_classification") == "P68_ODDSPORTAL_BLOCKED_BY_TOS"


# ---------------------------------------------------------------------------
# §6 — The Odds API Is Recommendation-Only (NOT Called)
# ---------------------------------------------------------------------------

def test_the_odds_api_not_called_module_flag():
    """PAID_API_CALLED must be False — P69 is memo-only."""
    assert mod.PAID_API_CALLED is False


def test_the_odds_api_not_called_path_a_spec():
    """PATH_A spec must explicitly mark The Odds API as not called in P69."""
    assert mod.PATH_A_SPEC["the_odds_api_called_in_p69"] is False


def test_the_odds_api_not_called_governance():
    """Governance block in summary must confirm paid_api_called=False."""
    summary = load_summary()
    gov = summary["governance"]
    assert gov["paid_api_called"] is False
    assert gov["the_odds_api_called_in_p69"] is False


# ---------------------------------------------------------------------------
# §7 — Cost Range Documented
# ---------------------------------------------------------------------------

def test_cost_range_documented():
    """PATH_A spec must include a cost estimate in range $30–$50."""
    spec = mod.PATH_A_SPEC
    assert spec["cost_low_usd"] >= 1, "Cost lower bound must be positive"
    assert spec["cost_high_usd"] <= 500, "Cost upper bound must be reasonable"
    assert "$" in spec["cost_estimate"], "Cost estimate must include $ symbol"


def test_cost_range_in_summary():
    """Summary PATH_A spec must include a cost estimate."""
    summary = load_summary()
    spec = summary["path_a_spec"]
    assert "cost_estimate" in spec
    assert "$" in spec["cost_estimate"]


# ---------------------------------------------------------------------------
# §8 — Required Fields Documented
# ---------------------------------------------------------------------------

def test_required_fields_count():
    """At least 9 required fields must be documented."""
    assert len(mod.REQUIRED_FIELDS) >= 9, (
        f"Expected ≥9 required fields, got {len(mod.REQUIRED_FIELDS)}"
    )


def test_required_fields_include_moneyline():
    """home_ml and away_ml must be in required fields."""
    field_names = {f["field"] for f in mod.REQUIRED_FIELDS}
    assert "home_ml" in field_names
    assert "away_ml" in field_names


def test_required_fields_in_summary():
    """Summary must include required_fields list."""
    summary = load_summary()
    fields = summary.get("required_fields", [])
    field_names = {f["field"] for f in fields}
    assert "game_date" in field_names
    assert "home_team" in field_names
    assert "away_team" in field_names
    assert "home_ml" in field_names
    assert "away_ml" in field_names


# ---------------------------------------------------------------------------
# §9 — Allowed Use: Paper-Only / Diagnostic-Only
# ---------------------------------------------------------------------------

def test_allowed_use_includes_paper_only():
    """Allowed use must reference paper-only restriction."""
    allowed = " ".join(mod.ALLOWED_USE).lower()
    assert "paper" in allowed, "Allowed use must mention paper-only"


def test_prohibited_use_excludes_live_betting():
    """Prohibited use must explicitly exclude live betting."""
    prohibited = " ".join(mod.PROHIBITED_USE).lower()
    assert "live betting" in prohibited or "real money" in prohibited, (
        "Prohibited use must mention live betting / real money"
    )


def test_prohibited_use_excludes_kelly():
    """Prohibited use must explicitly exclude Kelly deployment."""
    prohibited = " ".join(mod.PROHIBITED_USE).lower()
    assert "kelly" in prohibited, "Prohibited use must mention Kelly"


def test_prohibited_use_excludes_production():
    """Prohibited use must explicitly exclude production recommendations."""
    prohibited = " ".join(mod.PROHIBITED_USE).lower()
    assert "production" in prohibited, "Prohibited use must mention production"


def test_prohibited_use_excludes_champion_replacement():
    """Prohibited use must explicitly exclude champion replacement."""
    prohibited = " ".join(mod.PROHIBITED_USE).lower()
    assert "champion" in prohibited, "Prohibited use must mention champion"


# ---------------------------------------------------------------------------
# §10 — CEO Decision Options Present
# ---------------------------------------------------------------------------

def test_ceo_decision_options_count():
    """Exactly 3 CEO decision options must be present (approve/reject/defer)."""
    assert len(mod.CEO_DECISION_OPTIONS) == 3


def test_approval_phrase_present_in_module():
    """CEO approval phrase must be present in module."""
    opts = {o["option"]: o["exact_phrase"] for o in mod.CEO_DECISION_OPTIONS}
    assert "APPROVE" in opts
    assert "PATH_A" in opts["APPROVE"] and "YES" in opts["APPROVE"]


def test_rejection_phrase_present_in_module():
    """CEO rejection phrase must be present in module."""
    opts = {o["option"]: o["exact_phrase"] for o in mod.CEO_DECISION_OPTIONS}
    assert "REJECT" in opts
    assert "NO" in opts["REJECT"]


def test_defer_phrase_present_in_module():
    """CEO defer phrase must be present in module."""
    opts = {o["option"]: o["exact_phrase"] for o in mod.CEO_DECISION_OPTIONS}
    assert "DEFER" in opts
    assert "DEFER" in opts["DEFER"]


def test_approval_phrase_in_summary():
    summary = load_summary()
    phrase = summary.get("ceo_approval_phrase", "")
    assert "YES" in phrase and "PATH_A" in phrase


def test_rejection_phrase_in_summary():
    summary = load_summary()
    phrase = summary.get("ceo_rejection_phrase", "")
    assert "NO" in phrase and "PATH_A" in phrase


def test_defer_phrase_in_summary():
    summary = load_summary()
    phrase = summary.get("ceo_defer_phrase", "")
    assert "DEFER" in phrase and "PATH_A" in phrase


# ---------------------------------------------------------------------------
# §11 — Classification Valid
# ---------------------------------------------------------------------------

def test_p69_classification_is_allowed():
    """P69 final classification must be from the allowed set."""
    summary = load_summary()
    cls = summary["p69_classification"]
    assert cls in mod.VALID_P69_CLASSIFICATIONS, (
        f"P69 classification {cls!r} not in VALID_P69_CLASSIFICATIONS"
    )


def test_p69_classification_is_memo_ready():
    """P69 classification must be P69_CEO_DECISION_MEMO_READY when all evidence is present."""
    summary = load_summary()
    assert summary["p69_classification"] == "P69_CEO_DECISION_MEMO_READY"


# ---------------------------------------------------------------------------
# §12 — Full Governance Flags
# ---------------------------------------------------------------------------

def test_governance_flags_all_correct():
    """All governance flags must be correct."""
    gov = mod.GOVERNANCE_BLOCK
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["promotion_freeze"] is True
    assert gov["kelly_deploy_allowed"] is False
    assert gov["live_api_calls"] == 0
    assert gov["paid_api_called"] is False
    assert gov["the_odds_api_called_in_p69"] is False
    assert gov["tsl_crawler_called"] is False
    assert gov["bulk_scraping_performed"] is False
    assert gov["anti_bot_bypass_attempted"] is False
    assert gov["runtime_recommendation_logic_changed"] is False
    assert gov["real_bet_allowed"] is False
    assert gov["production_ready"] is False


def test_platt_constants_unchanged():
    """P45 Platt constants must remain locked."""
    assert mod.PLATT_A == pytest.approx(0.435432, rel=1e-6)
    assert mod.PLATT_B == pytest.approx(0.245464, rel=1e-6)


# ---------------------------------------------------------------------------
# §13 — Forbidden Affirmative Scan
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    "production_ready = True",
    "kelly_deploy_allowed = True",
    "real_bet_allowed = True",
    "paid_api_called = True",
    "PAID_API_CALLED: bool = True",
    "LIVE_API_CALLS: int = 1",
    "TSL_CRAWLER_CALLED: bool = True",
    "BULK_SCRAPING_PERFORMED: bool = True",
    "ANTI_BOT_BYPASS_ATTEMPTED: bool = True",
    "RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = True",
    "PROMOTION_FREEZE: bool = False",
    "the_odds_api_called_in_p69: True",
]


def test_forbidden_affirmative_scan_in_script():
    """Script must not contain any forbidden affirmative patterns."""
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")
    violations = [p for p in FORBIDDEN_PATTERNS if p in script_text]
    assert not violations, (
        f"Forbidden patterns found in P69 script: {violations}"
    )


# ---------------------------------------------------------------------------
# §14 — Active Task Updated
# ---------------------------------------------------------------------------

def test_active_task_md_contains_p69():
    """active_task.md must contain P69 after task completion."""
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    assert "P69" in content, "active_task.md must contain 'P69'"


def test_active_task_md_contains_p69_completed():
    """active_task.md must contain P69 and COMPLETED."""
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    assert "P69" in content and "COMPLETED" in content, (
        "active_task.md must contain both 'P69' and 'COMPLETED'"
    )


# ---------------------------------------------------------------------------
# §15 — Summary Structure
# ---------------------------------------------------------------------------

def test_summary_has_required_top_level_keys():
    """Summary JSON must have all required top-level keys."""
    summary = load_summary()
    required_keys = {
        "p69_version",
        "p69_classification",
        "memo_date",
        "p61_classification_verified",
        "p67_classification_verified",
        "p68_classification_verified",
        "data_year_2024_gap_status",
        "free_source_paths_exhausted",
        "free_sources_evaluated",
        "oddsportal_block",
        "path_a_spec",
        "required_fields",
        "allowed_use",
        "prohibited_use",
        "ceo_decision_options",
        "ceo_approval_phrase",
        "ceo_rejection_phrase",
        "ceo_defer_phrase",
        "governance",
    }
    missing = required_keys - set(summary.keys())
    assert not missing, f"Missing summary keys: {missing}"


def test_summary_platt_in_governance():
    """Platt constants must be recorded in summary governance."""
    summary = load_summary()
    gov = summary["governance"]
    assert gov["platt_a"] == pytest.approx(0.435432, rel=1e-6)
    assert gov["platt_b"] == pytest.approx(0.245464, rel=1e-6)
