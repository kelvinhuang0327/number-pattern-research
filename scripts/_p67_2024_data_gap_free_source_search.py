"""
P67 — 2024 Closing-Line Data Gap: Free-Source Search (PATH_B Execution)
======================================================================
Governance: paper_only=True, diagnostic_only=True, promotion_freeze=True
NO live API calls. NO paid API. NO TSL calls. NO web requests at runtime.
Encodes manual/agent-assisted search findings from P67 research session.

Search session date : 2026-05-26
Researcher          : Copilot Agent
Search tools used   : fetch_webpage (Kaggle, GitHub, OddsPortal, SBRO, etc.)
Output              : data/mlb_2025/derived/p67_2024_data_gap_free_source_search_summary.json
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import date

# ── Governance flags ──────────────────────────────────────────────────────────
PAPER_ONLY: bool = True
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
KELLY_DEPLOY_ALLOWED: bool = False
LIVE_API_CALLS: int = 0
PAID_API_CALLED: bool = False
RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = False
REAL_BET_ALLOWED: bool = False
PRODUCTION_READY: bool = False
TSL_CRAWLER_CALLED: bool = False
DATA_YEAR_2024_GAP_REMAINS: bool = True

# ── Allowed source-level classifications ──────────────────────────────────────
VALID_SOURCE_CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        "SOURCE_USABLE_FOR_2024_CLOSING_ML",
        "SOURCE_PARTIAL_NEEDS_SCHEMA_PROBE",
        "SOURCE_OPEN_ONLY_NOT_CLOSING",
        "SOURCE_NO_MONEYLINE",
        "SOURCE_NO_2024",
        "SOURCE_PAID_ONLY",
        "SOURCE_LICENSE_UNCLEAR",
        "SOURCE_UNUSABLE",
    }
)

# ── Allowed P67 final classifications ─────────────────────────────────────────
VALID_P67_CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        "P67_PATH_B_SOURCE_FOUND_READY_FOR_SCHEMA_PROBE",
        "P67_PATH_B_PARTIAL_SOURCE_FOUND_NEEDS_REVIEW",
        "P67_PATH_B_NO_USABLE_FREE_SOURCE_FOUND",
        "P67_PATH_B_BLOCKED_BY_LICENSE_UNCERTAINTY",
        "P67_BLOCKED_BY_SEARCH_ACCESS_LIMITATION",
    }
)

# ── Search scope (all terms used in research session) ────────────────────────
SEARCH_SCOPE: list[str] = [
    "Kaggle: 'MLB odds 2024 moneyline'",
    "Kaggle: 'mlb odds baseball betting'",
    "Kaggle: 'baseball odds betting'",
    "Kaggle: 'mlb baseball 2024'",
    "GitHub repositories: 'mlb odds 2024 moneyline csv'",
    "GitHub repositories: 'mlb baseball odds 2024 csv'",
    "GitHub repositories: 'mlb betting odds historical 2024'",
    "GitHub topic: 'mlb-betting'",
    "Web direct: SportsbookReviewsOnline.com MLB Archives",
    "Web direct: OddsPortal.com /baseball/usa/mlb-2024/results/",
    "Web direct: aussportsbetting.com /data/",
    "Kaggle specific: pratyushpuri/sports-betting-predictive-analysis-dataset",
    "Kaggle specific: garethflandro/major-league-baseball-games-2024",
]

# ── Candidate source inventory ────────────────────────────────────────────────
CANDIDATE_SOURCES: list[dict] = [
    {
        "source_name": "SportsbookReviewsOnline.com (SBRO) MLB Archive",
        "url": "https://sportsbookreviewsonline.com/scoresoddsarchives/mlb/mlboddsarchives.htm",
        "source_type": "Public historical odds archive",
        "availability": "Free direct XLSX download — confirmed for 2010–2021",
        "cost": "free",
        "license": "Public access; terms not explicitly stated; research use common",
        "fields_visible": [
            "VH", "Team", "Date", "Rot",
            "1st", "2nd", "3rd", "4th", "Final",
            "Open", "Close", "ML",
        ],
        "years_covered": "2010–2021",
        "market_coverage": "MLB regular season + postseason (2010–2021 only)",
        "home_ml_present": True,
        "away_ml_present": True,
        "odds_type": "open_and_closing",
        "join_keys_available": ["Date", "Home Team", "Away Team"],
        "expected_effort": "LOW — direct XLSX download if 2024 were available",
        "risk_score": 1,
        "notes": (
            "Archive page explicitly states: 'MLB scores and odds archive will not be "
            "updated.' Last available season confirmed: 2021. Direct XLSX download links "
            "confirmed for 2010–2021 seasons. No 2022, 2023, or 2024 data present. "
            "This source cannot resolve the 2024 closing-line data gap."
        ),
        "classification": "SOURCE_NO_2024",
    },
    {
        "source_name": "OddsPortal.com — MLB 2024",
        "url": "https://www.oddsportal.com/baseball/usa/mlb-2024/results/",
        "source_type": "Web odds aggregator — historical results with closing odds",
        "availability": (
            "Web UI only — no bulk CSV download. "
            "JavaScript-rendered pagination (~50 games/page)."
        ),
        "cost": "free to view; no subscription required",
        "license": (
            "ToS restricts automated extraction (Section 5). "
            "Manual viewing permitted. Scraping requires explicit ToS review."
        ),
        "fields_visible": [
            "Home Team", "Away Team", "Date",
            "Home Odds (decimal)", "Away Odds (decimal)",
            "Score", "Season navigation links",
        ],
        "years_covered": "2008–2026 (season navigation links confirm 2024)",
        "market_coverage": (
            "MLB regular season + postseason — 2024 confirmed. "
            "World Series Game 1 (LAD vs NYY) odds visible: 1.71 / 2.37."
        ),
        "home_ml_present": True,
        "away_ml_present": True,
        "odds_type": "closing (settled odds shown post-close)",
        "join_keys_available": ["Date", "Home Team", "Away Team"],
        "expected_effort": (
            "HIGH — ~2430 rows spread across ~49 paginated pages. "
            "Requires JS-rendered headless browser (Playwright/Selenium). "
            "ToS review mandatory before scraping."
        ),
        "risk_score": 7,
        "notes": (
            "2024 MLB data confirmed visible in web UI. Odds shown in decimal format; "
            "convertible to American ML via standard formula. "
            "Site shows: LAD 1.71 / NYY 2.37 for WS Game 1 (Oct 25 2024). "
            "Bulk scraping not trivially available — no public API, no CSV export. "
            "Pagination structure and schema need probe before committing to scrape. "
            "Risk: ToS Section 5 restricts automated extraction; "
            "anti-scraping measures possible."
        ),
        "classification": "SOURCE_PARTIAL_NEEDS_SCHEMA_PROBE",
    },
    {
        "source_name": "Kaggle — Sports Betting Predictive Analysis Dataset (pratyushpuri)",
        "url": "https://www.kaggle.com/datasets/pratyushpuri/sports-betting-predictive-analysis-dataset",
        "source_type": "Kaggle community synthetic dataset",
        "availability": "Free direct download",
        "cost": "free",
        "license": "CC0 Public Domain",
        "fields_visible": [
            "Date", "Sport", "Home_Team", "Away_Team",
            "Home_Odds", "Away_Odds", "Predicted_Winner", "Actual_Winner",
        ],
        "years_covered": "July 2023–July 2025 (synthetic, not real)",
        "market_coverage": "Multi-sport: Football, Basketball, Tennis, Baseball, Hockey",
        "home_ml_present": True,
        "away_ml_present": True,
        "odds_type": "synthetic — values in range 1.2–5.0 (Faker-generated)",
        "join_keys_available": ["Date", "Home_Team", "Away_Team"],
        "expected_effort": "N/A — disqualified",
        "risk_score": 10,
        "notes": (
            "Dataset is explicitly labelled 'Synthetic (generated using Faker library)' "
            "in the Kaggle dataset card. Not real market data. 1,369 rows total across "
            "5 sports; estimated ~274 baseball rows but team names are fictitious "
            "(city-based convention, not real MLB franchises). "
            "Cannot be used for market-edge validation. Confirmed disqualified."
        ),
        "classification": "SOURCE_UNUSABLE",
    },
    {
        "source_name": "Kaggle — Major League Baseball Games 2020–2024 (garethflandro)",
        "url": "https://www.kaggle.com/datasets/garethflandro/major-league-baseball-games-2024",
        "source_type": "Kaggle community dataset — Retrosheet game logs",
        "availability": "Free direct download (MIT license)",
        "cost": "free",
        "license": "MIT; Retrosheet attribution required (non-commercial)",
        "fields_visible": [
            "Date", "VT (Away Team)", "HT (Home Team)",
            "VT Score", "HT Score", "162+ performance stat columns",
        ],
        "years_covered": "2020–2024",
        "market_coverage": "All MLB regular season games 2020–2024",
        "home_ml_present": False,
        "away_ml_present": False,
        "odds_type": "none — game log / box score only",
        "join_keys_available": ["Date", "Away", "Home"],
        "expected_effort": "LOW to download; ZERO odds value",
        "risk_score": 2,
        "notes": (
            "162 columns of game performance statistics only (Retrosheet-derived). "
            "No moneyline odds, no spread, no totals. "
            "Source: retrosheet.org/gamelogs/ (publicly confirmed). "
            "Does have correct join keys (Date, Away, Home) and 2024 coverage, "
            "but cannot fill the 2024 odds gap."
        ),
        "classification": "SOURCE_NO_MONEYLINE",
    },
    {
        "source_name": "Kaggle — MLB 2024 dataset collection (all search results)",
        "url": "https://www.kaggle.com/datasets?search=mlb+baseball+2024",
        "source_type": "Kaggle platform search — 27 datasets",
        "availability": "27 datasets found; all freely downloadable",
        "cost": "free",
        "license": "Varies by dataset",
        "fields_visible": [
            "Bat tracking", "Statcast", "Pitch-by-pitch",
            "Batting stats", "Payrolls", "Salaries", "Umpires",
        ],
        "years_covered": "Various; 2024 coverage present in many",
        "market_coverage": "Game performance and team stats — NO betting odds across any dataset",
        "home_ml_present": False,
        "away_ml_present": False,
        "odds_type": "none",
        "join_keys_available": [],
        "expected_effort": "N/A — no odds data in any of the 27 datasets",
        "risk_score": 1,
        "notes": (
            "Exhaustive Kaggle search with 4 separate queries: "
            "'MLB odds 2024 moneyline', 'mlb odds baseball betting', "
            "'baseball odds betting', 'mlb baseball 2024'. "
            "Total 27 datasets returned. Titles include: MLB Bat Tracking, "
            "WBC 2026 Scouting, MLB Postseason Pitch-by-Pitch, Baseball Savant Leaderboards, "
            "Lahman Baseball Database, MLB Hitting Data, MLB Team Payrolls, MLB Player Salaries. "
            "None contain betting odds or moneyline data. "
            "No 2024 MLB closing-line dataset exists on Kaggle as of 2026-05-26."
        ),
        "classification": "SOURCE_NO_MONEYLINE",
    },
    {
        "source_name": "GitHub — MLB betting odds repositories (all search results)",
        "url": "https://github.com/search?q=mlb+odds+2024+moneyline+csv&type=repositories",
        "source_type": "GitHub repository search — 3 queries",
        "availability": "0 repositories found across all queries",
        "cost": "free",
        "license": "N/A — no repositories found",
        "fields_visible": [],
        "years_covered": "N/A",
        "market_coverage": "N/A",
        "home_ml_present": False,
        "away_ml_present": False,
        "odds_type": "none",
        "join_keys_available": [],
        "expected_effort": "N/A — no results",
        "risk_score": 1,
        "notes": (
            "Searched GitHub with 3 queries: "
            "'mlb odds 2024 moneyline csv' (0 repos), "
            "'mlb baseball odds 2024 csv' (0 repos), "
            "'mlb betting odds historical 2024' (0 repos). "
            "GitHub topic 'mlb-betting' has been used on 0 public repositories (topic page confirmed). "
            "No community-maintained 2024 MLB odds dataset found on GitHub as of 2026-05-26."
        ),
        "classification": "SOURCE_UNUSABLE",
    },
    {
        "source_name": "aussportsbetting.com — Historical MLB Results and Odds",
        "url": "https://www.aussportsbetting.com/data/historical-mlb-results-and-odds-data/",
        "source_type": "Historical sports betting data archive",
        "availability": "HTTP 403 Forbidden — blocked during search session",
        "cost": "unclear (possible free public archive)",
        "license": "unclear — could not access ToS",
        "fields_visible": [],
        "years_covered": "unknown — 2024 availability unconfirmed",
        "market_coverage": "unknown",
        "home_ml_present": None,
        "away_ml_present": None,
        "odds_type": "unknown",
        "join_keys_available": [],
        "expected_effort": "UNKNOWN — requires manual investigation after access is established",
        "risk_score": 8,
        "notes": (
            "Site returned HTTP 403 Forbidden during P67 search. "
            "Known historically as a public free data archive for multiple sports including MLB. "
            "Cannot confirm: 2024 availability, field coverage, download format, or license. "
            "Requires manual access investigation. "
            "Classified as SOURCE_LICENSE_UNCLEAR due to inaccessibility during search."
        ),
        "classification": "SOURCE_LICENSE_UNCLEAR",
    },
]


def load_candidates() -> list[dict]:
    """Return the embedded candidate source inventory."""
    return CANDIDATE_SOURCES


def classify_source(source: dict) -> str:
    """Return the source-level classification string (validated)."""
    cls = source.get("classification", "SOURCE_UNUSABLE")
    if cls not in VALID_SOURCE_CLASSIFICATIONS:
        raise ValueError(f"Invalid source classification: {cls!r}")
    return cls


def determine_p67_classification(sources: list[dict]) -> str:
    """
    Derive the overall P67 classification from per-source results.

    Decision tree:
    1. Any SOURCE_USABLE_FOR_2024_CLOSING_ML → SOURCE_FOUND_READY_FOR_SCHEMA_PROBE
    2. Any SOURCE_PARTIAL_NEEDS_SCHEMA_PROBE → PARTIAL_SOURCE_FOUND_NEEDS_REVIEW
    3. All sources are SOURCE_NO_2024 / SOURCE_NO_MONEYLINE / SOURCE_UNUSABLE
       and any SOURCE_LICENSE_UNCLEAR → BLOCKED_BY_LICENSE_UNCERTAINTY
    4. Otherwise → NO_USABLE_FREE_SOURCE_FOUND
    """
    classifications = [classify_source(s) for s in sources]

    if "SOURCE_USABLE_FOR_2024_CLOSING_ML" in classifications:
        return "P67_PATH_B_SOURCE_FOUND_READY_FOR_SCHEMA_PROBE"

    if "SOURCE_PARTIAL_NEEDS_SCHEMA_PROBE" in classifications:
        return "P67_PATH_B_PARTIAL_SOURCE_FOUND_NEEDS_REVIEW"

    # No partial source; check licence uncertainty
    actionable = {
        "SOURCE_NO_2024", "SOURCE_NO_MONEYLINE",
        "SOURCE_UNUSABLE", "SOURCE_PAID_ONLY",
        "SOURCE_OPEN_ONLY_NOT_CLOSING",
    }
    if all(c in actionable for c in classifications):
        return "P67_PATH_B_NO_USABLE_FREE_SOURCE_FOUND"

    if "SOURCE_LICENSE_UNCLEAR" in classifications:
        return "P67_PATH_B_BLOCKED_BY_LICENSE_UNCERTAINTY"

    return "P67_PATH_B_NO_USABLE_FREE_SOURCE_FOUND"


def build_summary(sources: list[dict], p67_cls: str) -> dict:
    """Build the full P67 summary dictionary."""
    partial_sources = [
        s["source_name"]
        for s in sources
        if s["classification"] == "SOURCE_PARTIAL_NEEDS_SCHEMA_PROBE"
    ]
    license_unclear = [
        s["source_name"]
        for s in sources
        if s["classification"] == "SOURCE_LICENSE_UNCLEAR"
    ]

    if p67_cls == "P67_PATH_B_PARTIAL_SOURCE_FOUND_NEEDS_REVIEW":
        recommendation = "P68_oddsportal_scrape_feasibility_probe"
        data_gap_status = "UNRESOLVED_PENDING_P68_SCRAPE_FEASIBILITY"
        recommendation_rationale = (
            "OddsPortal.com has 2024 MLB closing-line odds confirmed visible in the web UI. "
            "Decimal odds for individual games are accessible. "
            "P68 should: (1) review OddsPortal ToS Section 5 in detail, "
            "(2) probe pagination structure for a single month, "
            "(3) estimate total row count for the full 2024 MLB regular season, "
            "(4) confirm Home/Away team field alignment with target schema. "
            "If P68 confirms feasibility and ToS compliance, proceed with structured scrape. "
            "If blocked by ToS: escalate to P61 PATH_A (CEO decision for The Odds API paid pull)."
        )
    else:
        recommendation = "P61_PATH_A_CEO_decision_paid_api"
        data_gap_status = "STILL_UNRESOLVED"
        recommendation_rationale = (
            "No free downloadable source found for 2024 MLB closing-line moneyline data. "
            "CEO decision required to authorise one-time historical pull from The Odds API "
            "(estimated $30–50, PATH_A per P61 plan). "
            "Additionally investigate aussportsbetting.com manually (HTTP 403 during search)."
        )

    return {
        "p67_version": "p67_v1",
        "p67_classification": p67_cls,
        "search_date": str(date.today()),
        "internet_access_available": True,
        "search_scope": SEARCH_SCOPE,
        "total_sources_evaluated": len(sources),
        "candidate_sources": sources,
        "source_level_summary": {
            "SOURCE_USABLE_FOR_2024_CLOSING_ML": [
                s["source_name"]
                for s in sources
                if s["classification"] == "SOURCE_USABLE_FOR_2024_CLOSING_ML"
            ],
            "SOURCE_PARTIAL_NEEDS_SCHEMA_PROBE": partial_sources,
            "SOURCE_NO_2024": [
                s["source_name"]
                for s in sources
                if s["classification"] == "SOURCE_NO_2024"
            ],
            "SOURCE_NO_MONEYLINE": [
                s["source_name"]
                for s in sources
                if s["classification"] == "SOURCE_NO_MONEYLINE"
            ],
            "SOURCE_UNUSABLE": [
                s["source_name"]
                for s in sources
                if s["classification"] == "SOURCE_UNUSABLE"
            ],
            "SOURCE_LICENSE_UNCLEAR": license_unclear,
            "SOURCE_PAID_ONLY": [
                s["source_name"]
                for s in sources
                if s["classification"] == "SOURCE_PAID_ONLY"
            ],
            "SOURCE_OPEN_ONLY_NOT_CLOSING": [
                s["source_name"]
                for s in sources
                if s["classification"] == "SOURCE_OPEN_ONLY_NOT_CLOSING"
            ],
        },
        "data_year_2024_gap_status": data_gap_status,
        "recommendation": recommendation,
        "recommendation_rationale": recommendation_rationale,
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
            "data_year_2024_gap_remains": DATA_YEAR_2024_GAP_REMAINS,
        },
        "p61_context": {
            "p61_path_b_target": (
                "Kaggle/GitHub community dataset search — confirmed exhausted with no result"
            ),
            "p61_path_b_expansion": (
                "P67 additionally searched SBRO archive (stopped 2021), "
                "OddsPortal.com (has 2024 web UI data, no bulk CSV), "
                "aussportsbetting.com (HTTP 403 blocked)"
            ),
            "p61_path_a_status": "Pending CEO authorization",
        },
        "target_schema_required": {
            "file": "data/mlb_2025/mlb_odds_2024_real.csv",
            "required_columns": [
                "Date", "Away", "Home",
                "Away Score", "Home Score",
                "Away ML", "Home ML",
            ],
            "required_rows_estimate": "~2430 (full 2024 MLB regular season)",
            "date_range": "2024-03-20 to 2024-09-29",
        },
    }


def write_summary(summary: dict, output_path: pathlib.Path) -> None:
    """Write the summary dict as pretty-printed JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(f"[P67] Summary written → {output_path}")


def run_p67(output_path: pathlib.Path | None = None) -> dict:
    """
    Execute P67 pipeline:
    1. Load candidate source inventory (embedded, no live calls).
    2. Classify each source.
    3. Determine overall P67 classification.
    4. Build and write summary JSON.
    5. Return summary dict.
    """
    sources = load_candidates()

    # Validate all source classifications upfront
    for s in sources:
        classify_source(s)

    p67_cls = determine_p67_classification(sources)
    assert p67_cls in VALID_P67_CLASSIFICATIONS, (
        f"Unexpected P67 classification: {p67_cls!r}"
    )

    summary = build_summary(sources, p67_cls)

    if output_path is None:
        here = pathlib.Path(__file__).resolve().parent.parent
        output_path = (
            here / "data" / "mlb_2025" / "derived"
            / "p67_2024_data_gap_free_source_search_summary.json"
        )

    write_summary(summary, output_path)
    return summary


# ── CLI entry-point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = run_p67()
    print(f"[P67] Classification: {result['p67_classification']}")
    print(f"[P67] 2024 data gap: {result['data_year_2024_gap_status']}")
    print(f"[P67] Recommendation: {result['recommendation']}")
    sys.exit(0)
