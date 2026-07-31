"""
scripts/_p69_ceo_decision_memo_path_a_authorization.py
=======================================================
P69 — CEO Decision Memo: P61 PATH_A Authorization for The Odds API Historical Pull

GOVERNANCE (immutable throughout P69):
  - PAPER_ONLY = True
  - DIAGNOSTIC_ONLY = True
  - PROMOTION_FREEZE = True
  - KELLY_DEPLOY_ALLOWED = False
  - LIVE_API_CALLS = 0
  - PAID_API_CALLED = False      ← The Odds API NOT called in P69
  - TSL_CRAWLER_CALLED = False
  - BULK_SCRAPING_PERFORMED = False
  - ANTI_BOT_BYPASS_ATTEMPTED = False
  - RUNTIME_RECOMMENDATION_LOGIC_CHANGED = False
  - REAL_BET_ALLOWED = False
  - PRODUCTION_READY = False

P69 is a memo-drafting task only. No data is downloaded. No API is called.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Governance constants (NEVER modify these)
# ---------------------------------------------------------------------------
PAPER_ONLY: bool = True
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
KELLY_DEPLOY_ALLOWED: bool = False
LIVE_API_CALLS: int = 0
PAID_API_CALLED: bool = False          # The Odds API NOT called in P69
TSL_CRAWLER_CALLED: bool = False
BULK_SCRAPING_PERFORMED: bool = False
ANTI_BOT_BYPASS_ATTEMPTED: bool = False
RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = False
REAL_BET_ALLOWED: bool = False
PRODUCTION_READY: bool = False

# Platt calibration constants — locked at P45
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

# P69 version
P69_VERSION: str = "p69_v1"
MEMO_DATE: str = "2026-05-26"

# Evidence trail classifications (read from prior phase summaries)
P61_CLASSIFICATION_EXPECTED: str = "P61_DATA_GAP_RESOLVABLE_MEDIUM_EFFORT"
P67_CLASSIFICATION_EXPECTED: str = "P67_PATH_B_PARTIAL_SOURCE_FOUND_NEEDS_REVIEW"
P68_CLASSIFICATION_EXPECTED: str = "P68_ODDSPORTAL_BLOCKED_BY_TOS"
DATA_YEAR_2024_GAP_REMAINS: bool = True

# ---------------------------------------------------------------------------
# Valid classification sets (allow-list for validation)
# ---------------------------------------------------------------------------
VALID_P69_CLASSIFICATIONS: frozenset[str] = frozenset({
    "P69_CEO_DECISION_MEMO_READY",
    "P69_BLOCKED_BY_MISSING_EVIDENCE",
    "P69_BLOCKED_BY_COST_UNCERTAINTY",
    "P69_BLOCKED_BY_GOVERNANCE_RISK",
    "P69_BLOCKED_BY_TEST_FAILURE",
})

# ---------------------------------------------------------------------------
# Evidence trail paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
P61_SUMMARY_PATH = REPO_ROOT / "data" / "mlb_2025" / "derived" / "p61_2024_data_gap_resolution_plan_summary.json"
P67_SUMMARY_PATH = REPO_ROOT / "data" / "mlb_2025" / "derived" / "p67_2024_data_gap_free_source_search_summary.json"
P68_SUMMARY_PATH = REPO_ROOT / "data" / "mlb_2025" / "derived" / "p68_oddsportal_tos_scraping_feasibility_summary.json"

# ---------------------------------------------------------------------------
# PATH_A specification (from P61 resolution plan)
# ---------------------------------------------------------------------------
PATH_A_SPEC: dict[str, Any] = {
    "path_id": "PATH_A",
    "name": "The Odds API — one-time historical pull for 2024 MLB closing-line moneyline",
    "source_url": "https://the-odds-api.com",
    "cost_estimate": "$30–50 one-time",
    "cost_low_usd": 30,
    "cost_high_usd": 50,
    "effort": "MEDIUM",
    "data_quality": "HIGH",
    "schema_match": "HIGH — requires conversion script (~50 lines)",
    "timeline_after_authorization": "1–2 days",
    "governance_requirement": "Explicit CEO authorization required for one-time paid API call",
    "recommended": True,
    "the_odds_api_called_in_p69": False,   # NEVER in P69 — memo only
}

# ---------------------------------------------------------------------------
# Required data fields for 2024 validation
# ---------------------------------------------------------------------------
REQUIRED_FIELDS: list[dict[str, str]] = [
    {"field": "game_date",               "description": "Date of game (ISO 8601)", "source": "The Odds API event timestamp"},
    {"field": "home_team",               "description": "Home team name (standardised)", "source": "The Odds API home_team field"},
    {"field": "away_team",               "description": "Away team name (standardised)", "source": "The Odds API away_team field"},
    {"field": "home_ml",                 "description": "Home moneyline (American format)", "source": "Convert from decimal/fractional"},
    {"field": "away_ml",                 "description": "Away moneyline (American format)", "source": "Convert from decimal/fractional"},
    {"field": "bookmaker",               "description": "Bookmaker / market source label", "source": "The Odds API bookmaker key"},
    {"field": "odds_timestamp",          "description": "Timestamp of odds snapshot", "source": "The Odds API last_update or commence_time"},
    {"field": "closing_indicator",       "description": "Closing or near-closing flag", "source": "Inferred from final snapshot before game_start"},
    {"field": "source_trace",            "description": "Provenance chain: source, pull date, script version", "source": "Injected at pull time"},
]

# ---------------------------------------------------------------------------
# Free-source exhaustion record (from P67 + P68)
# ---------------------------------------------------------------------------
FREE_SOURCE_EXHAUSTION: list[dict[str, str]] = [
    {"source": "Kaggle datasets (2024 MLB search)",  "result": "27 datasets found — all game stats, no moneyline odds",       "classification": "SOURCE_NO_MONEYLINE"},
    {"source": "GitHub repositories (3 queries)",   "result": "0 public repos with 2024 MLB odds data",                      "classification": "SOURCE_UNUSABLE"},
    {"source": "Kaggle synthetic dataset",           "result": "Generated via Faker — fake data, unusable",                   "classification": "SOURCE_UNUSABLE"},
    {"source": "SBRO (SportsBookReviewsOnline)",     "result": "Archive frozen at 2021 — no 2024 data",                      "classification": "SOURCE_NO_2024"},
    {"source": "aussportsbetting.com",               "result": "HTTP 403 — access blocked",                                  "classification": "SOURCE_LICENSE_UNCLEAR"},
    {"source": "OddsPortal.com",                     "result": "ToS Section 2.11 prohibits scraping; robots.txt Disallow: *-2024*", "classification": "SOURCE_TOS_BLOCKED"},
]
FREE_SOURCE_PATHS_EXHAUSTED: bool = True

# ---------------------------------------------------------------------------
# OddsPortal block summary (from P68)
# ---------------------------------------------------------------------------
ODDSPORTAL_BLOCK: dict[str, Any] = {
    "source": "OddsPortal.com — MLB 2024",
    "p68_classification": "P68_ODDSPORTAL_BLOCKED_BY_TOS",
    "tos_section_2_11": "Prohibits scraping and automated requests — 'you are not permitted to use our content … by embedding, aggregating, scraping or recreating it without our express consent'",
    "tos_section_2_10": "Prohibits database extraction — 'no extraction (copying) or exploitation of the Database Content … is permitted without our express consent'",
    "robots_txt_disallow": "Disallow: *-2024* for User-agent: * covers /baseball/usa/mlb-2024/results/",
    "scraping_prohibited": True,
    "data_visible_in_ui": True,
    "legally_accessible": False,
}

# ---------------------------------------------------------------------------
# CEO decision options and phrases
# ---------------------------------------------------------------------------
CEO_DECISION_OPTIONS: list[dict[str, str]] = [
    {
        "option": "APPROVE",
        "description": "Authorize P61 PATH_A — The Odds API one-time historical pull for 2024 MLB moneyline closing-line data",
        "next_task": "P70 — The Odds API Historical Pull: authorized one-time paid API call for 2024 MLB data",
        "exact_phrase": "YES authorize P61 PATH_A The Odds API historical 2024 MLB moneyline pull for paper-only validation",
    },
    {
        "option": "REJECT",
        "description": "Decline PATH_A — freeze 2024 closing-line scope; accept P43 blocked status as final",
        "next_task": "P70 — 2024 scope freeze: document final gap, accept P43_BLOCKED_BY_DATA_GAP as permanent",
        "exact_phrase": "NO reject P61 PATH_A and freeze 2024 closing-line scope",
    },
    {
        "option": "DEFER",
        "description": "Defer decision — request more information before committing",
        "next_task": "P70 — CEO information request: define open questions and request answers before re-presenting PATH_A",
        "exact_phrase": "DEFER P61 PATH_A pending more information",
    },
]

# ---------------------------------------------------------------------------
# Allowed / prohibited use
# ---------------------------------------------------------------------------
ALLOWED_USE: list[str] = [
    "paper-only simulation using 2024 closing-line data as model input",
    "diagnostic-only validation of P43 cross-year edge stability",
    "research-internal use only — no commercial distribution",
    "joining 2024 closing-line odds to 2024 model predictions for edge calculation",
    "P43 cross-year bootstrap CI on 2024+2025 combined rows (~3856 quality rows if 2024 resolved)",
]

PROHIBITED_USE: list[str] = [
    "live betting or real money wagering",
    "production recommendation output",
    "Kelly criterion staking deployment",
    "champion strategy replacement",
    "commercial redistribution of The Odds API data",
    "aggregation or re-publication of odds data",
    "any claim of profitability or production readiness",
]

# ---------------------------------------------------------------------------
# Governance block for summary JSON
# ---------------------------------------------------------------------------
GOVERNANCE_BLOCK: dict[str, Any] = {
    "paper_only": PAPER_ONLY,
    "diagnostic_only": DIAGNOSTIC_ONLY,
    "promotion_freeze": PROMOTION_FREEZE,
    "kelly_deploy_allowed": KELLY_DEPLOY_ALLOWED,
    "live_api_calls": LIVE_API_CALLS,
    "paid_api_called": PAID_API_CALLED,
    "the_odds_api_called_in_p69": False,
    "tsl_crawler_called": TSL_CRAWLER_CALLED,
    "bulk_scraping_performed": BULK_SCRAPING_PERFORMED,
    "anti_bot_bypass_attempted": ANTI_BOT_BYPASS_ATTEMPTED,
    "runtime_recommendation_logic_changed": RUNTIME_RECOMMENDATION_LOGIC_CHANGED,
    "real_bet_allowed": REAL_BET_ALLOWED,
    "production_ready": PRODUCTION_READY,
    "platt_a": PLATT_A,
    "platt_b": PLATT_B,
}

# ---------------------------------------------------------------------------
# Evidence trail loader
# ---------------------------------------------------------------------------

def load_evidence_trail() -> dict[str, Any]:
    """Load and verify P61 / P67 / P68 summaries from disk."""
    evidence: dict[str, Any] = {}

    for label, path in [
        ("p61", P61_SUMMARY_PATH),
        ("p67", P67_SUMMARY_PATH),
        ("p68", P68_SUMMARY_PATH),
    ]:
        if not path.exists():
            raise FileNotFoundError(f"Evidence file missing: {path}")
        with open(path, encoding="utf-8") as f:
            evidence[label] = json.load(f)

    # Verify classifications
    p61_cls = evidence["p61"].get("p61_classification", "")
    p67_cls = evidence["p67"].get("p67_classification", "")
    p68_cls = evidence["p68"].get("p68_classification", "")

    assert p61_cls == P61_CLASSIFICATION_EXPECTED, (
        f"P61 classification mismatch: expected {P61_CLASSIFICATION_EXPECTED!r}, got {p61_cls!r}"
    )
    assert p67_cls == P67_CLASSIFICATION_EXPECTED, (
        f"P67 classification mismatch: expected {P67_CLASSIFICATION_EXPECTED!r}, got {p67_cls!r}"
    )
    assert p68_cls == P68_CLASSIFICATION_EXPECTED, (
        f"P68 classification mismatch: expected {P68_CLASSIFICATION_EXPECTED!r}, got {p68_cls!r}"
    )

    # Verify governance (no paid/live API in any prior phase)
    for label in ("p61", "p67", "p68"):
        gov = evidence[label].get("governance", {})
        assert gov.get("paid_api_called", False) is False, (
            f"{label} governance shows paid_api_called=True — this violates P69 evidence trail"
        )
        assert gov.get("live_api_calls", 0) == 0, (
            f"{label} governance shows live_api_calls != 0"
        )

    return evidence


def determine_p69_classification(evidence: dict[str, Any]) -> str:
    """Determine P69 classification from evidence trail."""
    # All required summaries present and verified by load_evidence_trail()
    # Check gap is still unresolved
    gap_status = evidence["p68"].get("data_year_2024_gap_status", "")
    if "UNRESOLVED" not in gap_status:
        return "P69_BLOCKED_BY_MISSING_EVIDENCE"

    # PATH_A cost is known and within reasonable bounds
    cost_low = PATH_A_SPEC["cost_low_usd"]
    cost_high = PATH_A_SPEC["cost_high_usd"]
    if cost_low <= 0 or cost_high > 500:
        return "P69_BLOCKED_BY_COST_UNCERTAINTY"

    # Free sources confirmed exhausted
    if not FREE_SOURCE_PATHS_EXHAUSTED:
        return "P69_BLOCKED_BY_MISSING_EVIDENCE"

    # All governance flags correct
    if PAID_API_CALLED or LIVE_API_CALLS != 0 or BULK_SCRAPING_PERFORMED:
        return "P69_BLOCKED_BY_GOVERNANCE_RISK"

    return "P69_CEO_DECISION_MEMO_READY"


def build_summary(evidence: dict[str, Any], p69_cls: str) -> dict[str, Any]:
    """Build the complete P69 summary dict."""
    return {
        "p69_version": P69_VERSION,
        "p69_classification": p69_cls,
        "memo_date": MEMO_DATE,
        # Evidence trail
        "p61_classification_verified": evidence["p61"]["p61_classification"],
        "p67_classification_verified": evidence["p67"]["p67_classification"],
        "p68_classification_verified": evidence["p68"]["p68_classification"],
        "data_year_2024_gap_status": evidence["p68"]["data_year_2024_gap_status"],
        # Free source exhaustion
        "free_source_paths_exhausted": FREE_SOURCE_PATHS_EXHAUSTED,
        "free_sources_evaluated": FREE_SOURCE_EXHAUSTION,
        # OddsPortal block
        "oddsportal_block": ODDSPORTAL_BLOCK,
        # PATH_A recommendation
        "path_a_spec": PATH_A_SPEC,
        # Required fields
        "required_fields": REQUIRED_FIELDS,
        # Allowed / prohibited use
        "allowed_use": ALLOWED_USE,
        "prohibited_use": PROHIBITED_USE,
        # CEO decision options (with exact phrases)
        "ceo_decision_options": CEO_DECISION_OPTIONS,
        "ceo_approval_phrase": CEO_DECISION_OPTIONS[0]["exact_phrase"],
        "ceo_rejection_phrase": CEO_DECISION_OPTIONS[1]["exact_phrase"],
        "ceo_defer_phrase": CEO_DECISION_OPTIONS[2]["exact_phrase"],
        # Governance
        "governance": GOVERNANCE_BLOCK,
    }


def write_summary(summary: dict[str, Any], output_path: Path | None = None) -> Path:
    """Write summary JSON to disk."""
    if output_path is None:
        output_path = (
            REPO_ROOT
            / "data"
            / "mlb_2025"
            / "derived"
            / "p69_ceo_decision_memo_path_a_authorization_summary.json"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return output_path


def run_p69(output_path: Path | None = None) -> dict[str, Any]:
    """Full P69 pipeline entry point."""
    # Governance assertions
    assert PAPER_ONLY is True, "PAPER_ONLY must be True"
    assert DIAGNOSTIC_ONLY is True, "DIAGNOSTIC_ONLY must be True"
    assert PAID_API_CALLED is False, "PAID_API_CALLED must be False — P69 is memo-only"
    assert LIVE_API_CALLS == 0, "LIVE_API_CALLS must be 0"
    assert BULK_SCRAPING_PERFORMED is False, "BULK_SCRAPING_PERFORMED must be False"
    assert DATA_YEAR_2024_GAP_REMAINS is True, "2024 data gap must still be unresolved at P69 start"

    evidence = load_evidence_trail()
    p69_cls = determine_p69_classification(evidence)
    summary = build_summary(evidence, p69_cls)
    written_path = write_summary(summary, output_path)

    print(f"[P69] Summary written → {written_path}")
    print(f"[P69] Classification: {p69_cls}")
    print(f"[P69] CEO approval phrase  : {CEO_DECISION_OPTIONS[0]['exact_phrase']}")
    print(f"[P69] CEO rejection phrase : {CEO_DECISION_OPTIONS[1]['exact_phrase']}")
    print(f"[P69] CEO defer phrase     : {CEO_DECISION_OPTIONS[2]['exact_phrase']}")
    print(f"[P69] 2024 gap status: {summary['data_year_2024_gap_status']}")
    return summary


if __name__ == "__main__":
    run_p69()
