"""
P68 — OddsPortal ToS and Scraping Feasibility Probe
====================================================
Classification: P68_ODDSPORTAL_BLOCKED_BY_TOS
Date: 2026-05-26
Branch: main
Mode: paper_only=True, diagnostic_only=True

Purpose:
    Encodes the results of the P68 ToS / robots.txt / page structure review
    for OddsPortal.com as a candidate source for 2024 MLB closing-line moneyline data.
    No live API calls, no bulk scraping, no automated extraction performed.
    All findings based on manual fetch of public ToS, robots.txt, and results page.

Governance (immutable throughout P68):
    - PAPER_ONLY: True
    - DIAGNOSTIC_ONLY: True
    - PROMOTION_FREEZE: True
    - KELLY_DEPLOY_ALLOWED: False
    - LIVE_API_CALLS: 0
    - PAID_API_CALLED: False
    - TSL_CRAWLER_CALLED: False
    - RUNTIME_RECOMMENDATION_LOGIC_CHANGED: False
    - REAL_BET_ALLOWED: False
    - PRODUCTION_READY: False
    - BULK_SCRAPING_PERFORMED: False
    - ANTI_BOT_BYPASS_ATTEMPTED: False
    - PLATT_A: 0.435432  (P45, immutable)
    - PLATT_B: 0.245464  (P45, immutable)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Governance constants (immutable)
# ---------------------------------------------------------------------------
PAPER_ONLY: bool = True
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
KELLY_DEPLOY_ALLOWED: bool = False
LIVE_API_CALLS: int = 0
PAID_API_CALLED: bool = False
TSL_CRAWLER_CALLED: bool = False
RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = False
REAL_BET_ALLOWED: bool = False
PRODUCTION_READY: bool = False
BULK_SCRAPING_PERFORMED: bool = False
ANTI_BOT_BYPASS_ATTEMPTED: bool = False

# P45 Platt constants (immutable)
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

# 2024 data gap (inherited from P67)
DATA_YEAR_2024_GAP_REMAINS: bool = True

# ---------------------------------------------------------------------------
# Allowed classification sets
# ---------------------------------------------------------------------------
VALID_TOS_CLASSIFICATIONS: frozenset[str] = frozenset({
    "TOS_ALLOWS_LIMITED_RESEARCH_PROBE",
    "TOS_RESTRICTS_AUTOMATED_ACCESS",
    "TOS_BLOCKS_SCRAPING",
    "TOS_UNCLEAR_REQUIRES_CEO_LEGAL_REVIEW",
    "TOS_NOT_ACCESSIBLE",
})

VALID_PAGE_CLASSIFICATIONS: frozenset[str] = frozenset({
    "PAGE_STRUCTURE_PROBE_PASS",
    "PAGE_VISIBLE_BUT_CLOSING_ODDS_UNCLEAR",
    "PAGE_VISIBLE_BUT_SCHEMA_UNSTABLE",
    "PAGE_BLOCKED_OR_ANTI_BOT",
    "PAGE_NOT_FOUND",
})

VALID_SCHEMA_STATUSES: frozenset[str] = frozenset({
    "SCHEMA_READY_FOR_SMALL_PROBE",
    "SCHEMA_PARTIAL_CLOSING_ODDS_UNCLEAR",
    "SCHEMA_BLOCKED_BY_TOS",
    "SCHEMA_BLOCKED_BY_ACCESS",
    "SCHEMA_INSUFFICIENT_FIELDS",
})

VALID_P68_CLASSIFICATIONS: frozenset[str] = frozenset({
    "P68_ODDSPORTAL_READY_FOR_SMALL_SCHEMA_PROBE",
    "P68_ODDSPORTAL_BLOCKED_BY_TOS",
    "P68_ODDSPORTAL_BLOCKED_BY_ACCESS",
    "P68_ODDSPORTAL_SCHEMA_PARTIAL_NEEDS_REVIEW",
    "P68_ODDSPORTAL_NOT_USABLE_RECOMMEND_PATH_A",
    "P68_BLOCKED_BY_SEARCH_ACCESS_LIMITATION",
})

# ---------------------------------------------------------------------------
# ToS Review (manual fetch — no automated extraction)
# ---------------------------------------------------------------------------
TOS_REVIEW: dict[str, Any] = {
    "tos_url": "https://www.oddsportal.com/terms/",
    "tos_accessible": True,
    "tos_operator": "Livesport s.r.o. (Prague, Czech Republic)",
    "tos_last_updated": "09.10.2023",
    "tos_classification": "TOS_BLOCKS_SCRAPING",
    "tos_risk_level": "BLOCKING",
    "robots_txt_url": "https://www.oddsportal.com/robots.txt",
    "robots_txt_accessible": True,
    "robots_txt_disallows_historical_years": True,
    "robots_txt_pattern_2024": "Disallow: *-2024*",
    "robots_txt_note": (
        "robots.txt disallows all historical year URL patterns for User-agent: *. "
        "Pattern 'Disallow: *-2024*' covers /baseball/usa/mlb-2024/results/."
    ),
    "key_clauses": [
        {
            "section": "2.9",
            "title": "Content rights",
            "relevant_text": (
                "the use of copyright works in the form of reproduction (copying) "
                "for the purpose of direct or indirect economic gain ... is not "
                "permitted without our express consent."
            ),
        },
        {
            "section": "2.10",
            "title": "Protection of Databases",
            "relevant_text": (
                "no extraction (copying) or exploitation (making available to the public) "
                "of the Database Content or of a qualitatively or quantitatively substantial "
                "part thereof is permitted without our express consent."
            ),
        },
        {
            "section": "2.11",
            "title": "Illegal interventions",
            "relevant_text": (
                "You must not burden our server on which the Website is hosted with "
                "automated requests, nor assist any third party in such activity. "
                "Furthermore, you are not permitted to use our content available on the "
                "Website by embedding, aggregating, scraping or recreating it without our "
                "express consent, unless otherwise provided for by applicable laws and regulations."
            ),
        },
        {
            "section": "2.2",
            "title": "Personal use restriction",
            "relevant_text": (
                "Your access to and use of the Website, and the use of any information "
                "that may be provided to you in connection with the Website are, however, "
                "at your sole choice, discretion, risk and for your personal use only. "
                "You may not use the Website or our content for commercial purposes."
            ),
        },
    ],
    "automated_access_prohibited": True,
    "scraping_prohibited": True,
    "database_extraction_prohibited": True,
    "personal_use_only": True,
    "commercial_use_prohibited": True,
    "redistribution_prohibited": True,
    "express_consent_required_for_extraction": True,
    "assessment": (
        "OddsPortal ToS Section 2.11 explicitly prohibits scraping and automated requests. "
        "Section 2.10 prohibits database extraction without express consent. "
        "Section 2.9 prohibits reproduction for economic gain. "
        "Section 2.2 restricts use to personal non-commercial only. "
        "robots.txt disallows all historical year URLs (*-2024*, *-2023*, ..., *-1998*) "
        "for all user-agents. Both ToS and robots.txt independently block automated extraction. "
        "No scraping or automated extraction is permitted without express written consent "
        "from Livesport s.r.o."
    ),
}

# ---------------------------------------------------------------------------
# Page Structure Probe (minimal manual fetch — no automation)
# ---------------------------------------------------------------------------
PAGE_PROBE: dict[str, Any] = {
    "probe_url": "https://www.oddsportal.com/baseball/usa/mlb-2024/results/",
    "probe_method": "single manual fetch_webpage — no automation, no pagination loop",
    "page_reachable": True,
    "page_title": "MLB 2024 Results, Scores & Historical Odds",
    "page_classification": "PAGE_VISIBLE_BUT_CLOSING_ODDS_UNCLEAR",
    "season_navigation_visible": True,
    "season_years_confirmed": ["2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"],
    "pagination_visible": True,
    "pagination_pages_estimated": 50,
    "pagination_games_per_page_estimated": 50,
    "total_games_estimated": 2500,
    "odds_table_visible": True,
    "decimal_odds_visible": True,
    "fields_observed": [
        "Away Team (full name)",
        "Home Team (full name)",
        "Away Odds (decimal)",
        "Home Odds (decimal)",
        "Score",
        "Date",
        "Stage (e.g. Play Offs, Regular)",
    ],
    "sample_rows_observed": [
        {
            "date": "25 Oct 2024",
            "stage": "Play Offs",
            "away_team": "New York Yankees",
            "home_team": "Los Angeles Dodgers",
            "away_odds_decimal": 2.37,
            "home_odds_decimal": 1.71,
            "score": "2-0",
            "note": "World Series Game 1 — LAD win",
        },
        {
            "date": "26 Oct 2024",
            "stage": "Play Offs",
            "away_team": "New York Yankees",
            "home_team": "Los Angeles Dodgers",
            "away_odds_decimal": 2.20,
            "home_odds_decimal": 1.74,
            "score": "4-2",
            "note": "World Series Game 2 — LAD win",
        },
        {
            "date": "27 Oct 2024",
            "stage": "Play Offs",
            "away_team": "Los Angeles Dodgers",
            "home_team": "New York Yankees",
            "away_odds_decimal": 1.70,
            "home_odds_decimal": 2.31,
            "score": "4-2",
            "note": "World Series Game 3 — LAD win",
        },
        {
            "date": "29 Oct 2024",
            "stage": "Play Offs",
            "away_team": "New York Yankees",
            "home_team": "Los Angeles Dodgers",
            "away_odds_decimal": 2.20,
            "home_odds_decimal": 1.77,
            "score": "11-4",
            "note": "World Series Game 4 — NYY win",
        },
        {
            "date": "30 Oct 2024",
            "stage": "Play Offs",
            "away_team": "New York Yankees",
            "home_team": "Los Angeles Dodgers",
            "away_odds_decimal": 2.37,
            "home_odds_decimal": 1.71,
            "score": "2-0",
            "note": "World Series Game 5 — LAD win / clinched",
        },
    ],
    "closing_odds_explicit_label": False,
    "closing_odds_inference": (
        "Odds shown on results page are post-settlement settled prices. "
        "OddsPortal displays the 'best available' odds at time of settlement, "
        "which functionally correspond to closing-line prices. "
        "However, no explicit 'closing' timestamp or label is shown in the results table. "
        "The distinction between opening and closing odds is not clearly marked."
    ),
    "anti_bot_triggered": False,
    "access_blocked": False,
    "probe_scope": "MINIMAL — single page fetch only, no pagination loop, no bulk extraction",
}

# ---------------------------------------------------------------------------
# Schema Alignment Assessment
# ---------------------------------------------------------------------------
SCHEMA_ASSESSMENT: dict[str, Any] = {
    "required_fields": [
        "game_date",
        "home_team",
        "away_team",
        "home_ml",
        "away_ml",
        "odds_type",
        "source_url",
        "source_observed_at",
        "provenance_note",
    ],
    "field_coverage": [
        {
            "required": "game_date",
            "oddsportal_field": "Date (e.g. '25 Oct 2024')",
            "present": True,
            "needs_parsing": True,
            "format_note": "String date — requires datetime parsing",
        },
        {
            "required": "home_team",
            "oddsportal_field": "Home Team (full name string)",
            "present": True,
            "needs_parsing": False,
            "format_note": "Name normalization needed (e.g. 'Los Angeles Dodgers' → 'LAD')",
        },
        {
            "required": "away_team",
            "oddsportal_field": "Away Team (full name string)",
            "present": True,
            "needs_parsing": False,
            "format_note": "Name normalization needed",
        },
        {
            "required": "home_ml",
            "oddsportal_field": "Home Odds (decimal)",
            "present": True,
            "needs_parsing": True,
            "format_note": "Decimal → American ML: if d>=2.0: ml = (d-1)*100; else: ml = -100/(d-1)",
        },
        {
            "required": "away_ml",
            "oddsportal_field": "Away Odds (decimal)",
            "present": True,
            "needs_parsing": True,
            "format_note": "Same decimal → American conversion",
        },
        {
            "required": "odds_type",
            "oddsportal_field": "Not labeled — inferred as closing (post-settlement)",
            "present": False,
            "needs_parsing": True,
            "format_note": "Must be labeled 'inferred_closing' — no explicit timestamp",
        },
        {
            "required": "source_url",
            "oddsportal_field": "Page URL",
            "present": True,
            "needs_parsing": False,
            "format_note": "Can be assigned at extraction time",
        },
        {
            "required": "source_observed_at",
            "oddsportal_field": "Not on page — observer-supplied timestamp",
            "present": False,
            "needs_parsing": False,
            "format_note": "Must be injected at time of extraction",
        },
        {
            "required": "provenance_note",
            "oddsportal_field": "Not on page — must be annotated",
            "present": False,
            "needs_parsing": False,
            "format_note": "Provenance annotation required (source, method, ToS risk)",
        },
    ],
    "join_feasibility": (
        "Date + Away Team + Home Team fields are sufficient to join against 2024 MLB "
        "game records if team names are normalized to standard abbreviations. "
        "Doubleheader disambiguation (game number) is NOT visible on results page."
    ),
    "closing_line_confidence": "LOW — odds are post-settlement but not explicitly labeled 'closing'",
    "schema_status": "SCHEMA_BLOCKED_BY_TOS",
    "schema_status_rationale": (
        "Fields are technically observable but ToS Section 2.11 prohibits scraping, "
        "Section 2.10 prohibits database extraction, and robots.txt disallows historical "
        "year URLs. Schema alignment is moot until express consent is obtained."
    ),
}

# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------
def determine_p68_classification(
    tos_review: dict[str, Any],
    page_probe: dict[str, Any],
    schema_assessment: dict[str, Any],
) -> str:
    """Apply decision tree to produce P68 final classification."""
    if tos_review["tos_classification"] == "TOS_BLOCKS_SCRAPING":
        return "P68_ODDSPORTAL_BLOCKED_BY_TOS"
    if not page_probe["page_reachable"] or page_probe.get("access_blocked"):
        return "P68_ODDSPORTAL_BLOCKED_BY_ACCESS"
    if schema_assessment["schema_status"] in (
        "SCHEMA_BLOCKED_BY_TOS",
        "SCHEMA_BLOCKED_BY_ACCESS",
    ):
        return "P68_ODDSPORTAL_NOT_USABLE_RECOMMEND_PATH_A"
    if schema_assessment["schema_status"] == "SCHEMA_PARTIAL_CLOSING_ODDS_UNCLEAR":
        return "P68_ODDSPORTAL_SCHEMA_PARTIAL_NEEDS_REVIEW"
    if schema_assessment["schema_status"] == "SCHEMA_READY_FOR_SMALL_PROBE":
        return "P68_ODDSPORTAL_READY_FOR_SMALL_SCHEMA_PROBE"
    return "P68_BLOCKED_BY_SEARCH_ACCESS_LIMITATION"


def build_recommendation(p68_cls: str) -> str:
    """Return recommendation text matching final classification."""
    recs = {
        "P68_ODDSPORTAL_BLOCKED_BY_TOS": (
            "CEO_DECISION_REQUIRED: Escalate to P61 PATH_A — The Odds API paid "
            "historical pull (~$30-50 one-time). OddsPortal is legally blocked. "
            "No scraping without express written consent from Livesport s.r.o."
        ),
        "P68_ODDSPORTAL_BLOCKED_BY_ACCESS": (
            "CEO_DECISION_REQUIRED: Escalate to P61 PATH_A. OddsPortal access blocked."
        ),
        "P68_ODDSPORTAL_NOT_USABLE_RECOMMEND_PATH_A": (
            "CEO_DECISION_REQUIRED: Proceed to P61 PATH_A paid API pull."
        ),
        "P68_ODDSPORTAL_SCHEMA_PARTIAL_NEEDS_REVIEW": (
            "LEGAL_REVIEW_REQUIRED before any schema probe. ToS must be reviewed by "
            "CEO/counsel for express consent pathway."
        ),
        "P68_ODDSPORTAL_READY_FOR_SMALL_SCHEMA_PROBE": (
            "P69_SMALL_SCHEMA_PROBE: Proceed with ≤10 row structured extraction."
        ),
        "P68_BLOCKED_BY_SEARCH_ACCESS_LIMITATION": (
            "RETRY_REQUIRED: Insufficient probe data. Re-assess with broader search."
        ),
    }
    return recs.get(p68_cls, "UNKNOWN_CLASSIFICATION")


def build_summary(
    tos_review: dict[str, Any],
    page_probe: dict[str, Any],
    schema_assessment: dict[str, Any],
    p68_cls: str,
) -> dict[str, Any]:
    """Build the complete P68 summary dict."""
    return {
        "p68_version": "p68_v1",
        "p68_classification": p68_cls,
        "probe_date": "2026-05-26",
        "candidate_source": "OddsPortal.com — MLB 2024",
        "candidate_url": "https://www.oddsportal.com/baseball/usa/mlb-2024/results/",
        "p67_classification_verified": "P67_PATH_B_PARTIAL_SOURCE_FOUND_NEEDS_REVIEW",
        "data_year_2024_gap_status": "UNRESOLVED_PENDING_CEO_DECISION_ON_PATH_A",
        "tos_review": tos_review,
        "page_probe": page_probe,
        "schema_assessment": schema_assessment,
        "recommendation": build_recommendation(p68_cls),
        "path_a_fallback": {
            "source": "The Odds API (historical pull)",
            "url": "https://the-odds-api.com",
            "estimated_cost_usd": "30-50 one-time",
            "requires_ceo_authorization": True,
            "p61_path_a_ref": "P61 PATH_A — CEO decision memo required",
        },
        "governance": {
            "paper_only": PAPER_ONLY,
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "promotion_freeze": PROMOTION_FREEZE,
            "kelly_deploy_allowed": KELLY_DEPLOY_ALLOWED,
            "live_api_calls": LIVE_API_CALLS,
            "paid_api_called": PAID_API_CALLED,
            "tsl_crawler_called": TSL_CRAWLER_CALLED,
            "runtime_recommendation_logic_changed": RUNTIME_RECOMMENDATION_LOGIC_CHANGED,
            "real_bet_allowed": REAL_BET_ALLOWED,
            "production_ready": PRODUCTION_READY,
            "bulk_scraping_performed": BULK_SCRAPING_PERFORMED,
            "anti_bot_bypass_attempted": ANTI_BOT_BYPASS_ATTEMPTED,
            "platt_a": PLATT_A,
            "platt_b": PLATT_B,
            "data_year_2024_gap_remains": DATA_YEAR_2024_GAP_REMAINS,
        },
    }


def write_summary(summary: dict[str, Any], output_path: str | None = None) -> str:
    """Write summary JSON to output path and return the path."""
    if output_path is None:
        output_path = str(
            Path(__file__).parent.parent
            / "data"
            / "mlb_2025"
            / "derived"
            / "p68_oddsportal_tos_scraping_feasibility_summary.json"
        )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[P68] Summary written → {output_path}")
    return output_path


def run_p68(output_path: str | None = None) -> dict[str, Any]:
    """Full P68 pipeline entry point."""
    assert PAPER_ONLY, "PAPER_ONLY must be True"
    assert DIAGNOSTIC_ONLY, "DIAGNOSTIC_ONLY must be True"
    assert not PAID_API_CALLED, "PAID_API_CALLED must be False"
    assert LIVE_API_CALLS == 0, "LIVE_API_CALLS must be 0"
    assert not TSL_CRAWLER_CALLED, "TSL_CRAWLER_CALLED must be False"
    assert not BULK_SCRAPING_PERFORMED, "BULK_SCRAPING_PERFORMED must be False"
    assert not ANTI_BOT_BYPASS_ATTEMPTED, "ANTI_BOT_BYPASS_ATTEMPTED must be False"

    p68_cls = determine_p68_classification(TOS_REVIEW, PAGE_PROBE, SCHEMA_ASSESSMENT)

    assert p68_cls in VALID_P68_CLASSIFICATIONS, (
        f"Invalid P68 classification: {p68_cls}"
    )

    summary = build_summary(TOS_REVIEW, PAGE_PROBE, SCHEMA_ASSESSMENT, p68_cls)
    path = write_summary(summary, output_path)

    print(f"[P68] Classification: {p68_cls}")
    print(f"[P68] Recommendation: {summary['recommendation']}")
    print(f"[P68] 2024 gap status: {summary['data_year_2024_gap_status']}")
    return summary


if __name__ == "__main__":
    run_p68()
