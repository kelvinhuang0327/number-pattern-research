"""
scripts/_p70_path_a_the_odds_api_historical_pull.py
=====================================================
P70 — PATH_A: The Odds API One-Time Historical Pull for 2024 MLB Closing-Line
Moneyline Data (CEO-Authorized)

GOVERNANCE (immutable throughout P70):
  - CEO_AUTHORIZATION_PHRASE must match exactly
  - PAPER_ONLY = True
  - DIAGNOSTIC_ONLY = True
  - PROMOTION_FREEZE = True
  - KELLY_DEPLOY_ALLOWED = False
  - REAL_BET_ALLOWED = False
  - PRODUCTION_READY = False
  - RUNTIME_RECOMMENDATION_LOGIC_CHANGED = False
  - TSL_CRAWLER_CALLED = False
  - BULK_SCRAPING_PERFORMED = False
  - ANTI_BOT_BYPASS_ATTEMPTED = False

PAID API CALL POLICY:
  - PAID_API_CALLED = True ONLY when API key is present and live pull executes
  - In DRY_RUN mode (no key), PAID_API_CALLED = False
  - The Odds API is called ONLY once, for historical data, never for live odds

DATA USE POLICY:
  - Paper-only: validation and diagnostic use only
  - No live betting, no production recommendation, no Kelly staking
  - No commercial redistribution of The Odds API data
  - P45 Platt constants unchanged: A=0.435432, B=0.245464

EXECUTION MODES:
  - DRY_RUN  (no API key): validates schema, reports what would be fetched
  - LIVE     (key present): executes The Odds API historical pull, writes CSV
"""

from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# CEO Authorization (must match exactly)
# ---------------------------------------------------------------------------
CEO_AUTHORIZATION_PHRASE: str = (
    "YES authorize P61 PATH_A The Odds API historical 2024 MLB moneyline pull "
    "for paper-only validation"
)
CEO_AUTHORIZATION_CONFIRMED: bool = True  # CEO phrase received 2026-05-26

# ---------------------------------------------------------------------------
# Governance constants (NEVER modify)
# ---------------------------------------------------------------------------
PAPER_ONLY: bool = True
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
KELLY_DEPLOY_ALLOWED: bool = False
REAL_BET_ALLOWED: bool = False
PRODUCTION_READY: bool = False
RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = False
TSL_CRAWLER_CALLED: bool = False
BULK_SCRAPING_PERFORMED: bool = False
ANTI_BOT_BYPASS_ATTEMPTED: bool = False

# Platt calibration constants — locked at P45
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

# P70 version
P70_VERSION: str = "p70_v1"
PULL_DATE: str = "2026-05-26"

# ---------------------------------------------------------------------------
# Valid classifications
# ---------------------------------------------------------------------------
VALID_P70_CLASSIFICATIONS: frozenset[str] = frozenset({
    "P70_PATH_A_PULL_COMPLETE",
    "P70_PATH_A_AUTHORIZED_AWAITING_API_KEY",
    "P70_PATH_A_BLOCKED_BY_API_ERROR",
    "P70_PATH_A_PULL_DATA_QUALITY_FAIL",
    "P70_PATH_A_BLOCKED_BY_GOVERNANCE_RISK",
    "P70_PATH_A_BLOCKED_BY_MISSING_AUTHORIZATION",
    "P70_PATH_A_BLOCKED_BY_TEST_FAILURE",
})

# ---------------------------------------------------------------------------
# Pull configuration
# ---------------------------------------------------------------------------
PULL_CONFIG: dict[str, Any] = {
    "sport": "baseball_mlb",
    "season_start": "2024-03-20",
    "season_end": "2024-09-29",
    "market": "h2h",           # moneyline only
    "regions": "us",
    "bookmakers": ["pinnacle", "draftkings", "fanduel", "betmgm"],
    "preferred_bookmaker": "pinnacle",
    "odds_format": "american",
    "target_rows_estimate": 2430,
    "api_endpoint_base": "https://api.the-odds-api.com/v4",
    "rate_limit_seconds": 1.0,  # 1 req/sec conservative
    "max_retries": 3,
    "retry_backoff_seconds": 5.0,
}

# Required output fields (from P61 spec)
REQUIRED_OUTPUT_FIELDS: list[str] = [
    "game_date",
    "home_team",
    "away_team",
    "home_ml",
    "away_ml",
    "bookmaker",
    "odds_timestamp",
    "closing_indicator",
    "source_trace",
]

# ---------------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
P70_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "mlb_2025"
    / "derived"
    / "p70_path_a_the_odds_api_historical_pull_summary.json"
)
OUTPUT_CSV_PATH = REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2024_real.csv"
ENV_PATH = REPO_ROOT / ".env"


# ---------------------------------------------------------------------------
# API Key loader
# ---------------------------------------------------------------------------

def load_api_key() -> Optional[str]:
    """
    Load The Odds API key from environment or .env file.
    Returns None if not configured (triggers DRY_RUN mode).
    NEVER prints or logs the key value.
    """
    # Check environment variable first
    key = os.environ.get("THE_ODDS_API_KEY", "").strip()
    if key:
        return key

    # Fall back to .env file
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("THE_ODDS_API_KEY=") and not line.startswith("#"):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    return None


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _fetch_json(url: str, retries: int = 3) -> tuple[dict | list, dict]:
    """
    Fetch JSON from url with retry + backoff.
    Returns (data, response_headers).
    """
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            ctx = urllib.request.ssl.create_default_context()  # type: ignore[attr-defined]
            req = urllib.request.Request(url, headers={"User-Agent": "mlb-research/p70 (paper-only)"})
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                headers = dict(resp.headers)
                data = json.loads(resp.read().decode("utf-8"))
                return data, headers
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code in (401, 403):
                raise RuntimeError(f"API auth error {e.code}: check THE_ODDS_API_KEY in .env") from e
            if e.code == 429:
                time.sleep(PULL_CONFIG["retry_backoff_seconds"] * (attempt + 1))
        except Exception as e:
            last_error = e
            time.sleep(PULL_CONFIG["retry_backoff_seconds"])
    raise RuntimeError(f"HTTP fetch failed after {retries} retries: {last_error}") from last_error


def _american_odds(decimal: float) -> int:
    """Convert decimal odds to American moneyline (integer)."""
    if decimal >= 2.0:
        return round((decimal - 1) * 100)
    else:
        return round(-100 / (decimal - 1))


# ---------------------------------------------------------------------------
# Historical odds fetcher
# ---------------------------------------------------------------------------

def fetch_season_events(api_key: str) -> list[dict]:
    """
    Fetch all 2024 MLB regular season event IDs via the events endpoint.
    Each event has: id, home_team, away_team, commence_time.
    """
    all_events: list[dict] = []
    start = datetime.strptime(PULL_CONFIG["season_start"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(PULL_CONFIG["season_end"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

    current = start
    print(f"[P70] Fetching event list: {PULL_CONFIG['season_start']} → {PULL_CONFIG['season_end']}")

    while current <= end:
        date_str = current.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = (
            f"{PULL_CONFIG['api_endpoint_base']}/historical/sports/{PULL_CONFIG['sport']}/events"
            f"?apiKey={api_key}&date={date_str}"
        )
        try:
            data, headers = _fetch_json(url, retries=PULL_CONFIG["max_retries"])
            events = data if isinstance(data, list) else data.get("data", [])
            remaining = headers.get("x-requests-remaining", "?")
            print(f"[P70]   {current.date()} — {len(events)} events (remaining credits: {remaining})")
            all_events.extend(events)
            time.sleep(PULL_CONFIG["rate_limit_seconds"])
        except RuntimeError as e:
            print(f"[P70]   WARN: {current.date()} fetch failed: {e}")

        current += timedelta(days=7)  # Weekly sweep (season events persist in endpoint)

    # Deduplicate by event id, keep within season window
    seen: set[str] = set()
    filtered: list[dict] = []
    for ev in all_events:
        eid = ev.get("id", "")
        ct = ev.get("commence_time", "")
        if eid and eid not in seen and PULL_CONFIG["season_start"] <= ct[:10] <= PULL_CONFIG["season_end"]:
            seen.add(eid)
            filtered.append(ev)

    print(f"[P70] Total unique events found: {len(filtered)}")
    return filtered


def fetch_event_historical_odds(api_key: str, event_id: str, commence_time: str) -> Optional[dict]:
    """
    Fetch historical odds for a single event, using commence_time as the
    snapshot date (best proxy for closing line).
    Returns the raw event dict with bookmakers, or None on failure.
    """
    # Use commence_time as the snapshot date (closing-line proxy)
    url = (
        f"{PULL_CONFIG['api_endpoint_base']}/historical/sports/{PULL_CONFIG['sport']}/events/{event_id}/odds"
        f"?apiKey={api_key}"
        f"&regions={PULL_CONFIG['regions']}"
        f"&markets={PULL_CONFIG['market']}"
        f"&oddsFormat=decimal"
        f"&date={commence_time}"
    )
    try:
        data, _ = _fetch_json(url, retries=PULL_CONFIG["max_retries"])
        return data if isinstance(data, dict) else None
    except RuntimeError as e:
        print(f"[P70]   WARN: event {event_id} odds fetch failed: {e}")
        return None


def _extract_row_from_event(event_data: dict, source_trace: str) -> Optional[dict]:
    """
    Convert raw The Odds API event dict to one row per preferred bookmaker.
    Falls back to first available bookmaker with h2h market.
    Returns None if no usable h2h market found.
    """
    home_team: str = event_data.get("home_team", "")
    away_team: str = event_data.get("away_team", "")
    commence_time: str = event_data.get("commence_time", "")
    game_date: str = commence_time[:10] if commence_time else ""

    bookmakers: list[dict] = event_data.get("bookmakers", [])
    preferred_order = PULL_CONFIG["bookmakers"]

    # Sort by preferred bookmaker order
    def bm_rank(bm: dict) -> int:
        key = bm.get("key", "")
        try:
            return preferred_order.index(key)
        except ValueError:
            return len(preferred_order)

    bookmakers_sorted = sorted(bookmakers, key=bm_rank)

    for bm in bookmakers_sorted:
        bm_key: str = bm.get("key", "unknown")
        markets: list[dict] = bm.get("markets", [])
        for market in markets:
            if market.get("key") != "h2h":
                continue
            outcomes: list[dict] = market.get("outcomes", [])
            home_dec: Optional[float] = None
            away_dec: Optional[float] = None
            odds_ts: str = market.get("last_update", commence_time)

            for outcome in outcomes:
                name = outcome.get("name", "")
                price = outcome.get("price")
                if price is None:
                    continue
                if name == home_team:
                    home_dec = float(price)
                elif name == away_team:
                    away_dec = float(price)

            if home_dec is not None and away_dec is not None:
                return {
                    "game_date": game_date,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_ml": _american_odds(home_dec),
                    "away_ml": _american_odds(away_dec),
                    "bookmaker": bm_key,
                    "odds_timestamp": odds_ts,
                    "closing_indicator": "CLOSING_PROXY_COMMENCE_TIME",
                    "source_trace": source_trace,
                }
    return None


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict], output_path: Path) -> None:
    """Write rows to CSV with required field order."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[P70] CSV written → {output_path} ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Dry-run mode (no API key)
# ---------------------------------------------------------------------------

def run_dry_run() -> dict[str, Any]:
    """
    Dry-run mode: validates configuration, reports what would be fetched.
    No API call is made. Returns a summary dict.
    """
    print("[P70] DRY_RUN mode — no API key configured, no actual API call")
    print(f"[P70] Would pull: {PULL_CONFIG['sport']} "
          f"{PULL_CONFIG['season_start']} → {PULL_CONFIG['season_end']}")
    print(f"[P70] Market: {PULL_CONFIG['market']}, Regions: {PULL_CONFIG['regions']}")
    print(f"[P70] Estimated rows: ~{PULL_CONFIG['target_rows_estimate']}")
    print(f"[P70] Would write to: {OUTPUT_CSV_PATH}")
    print()
    print("[P70] To execute the actual pull:")
    print("[P70]   1. Register at https://the-odds-api.com and purchase historical data access")
    print("[P70]   2. Add to .env:  THE_ODDS_API_KEY=<your_key>")
    print("[P70]   3. Re-run this script: .venv/bin/python scripts/_p70_path_a_the_odds_api_historical_pull.py")

    return {
        "p70_version": P70_VERSION,
        "p70_classification": "P70_PATH_A_AUTHORIZED_AWAITING_API_KEY",
        "pull_date": PULL_DATE,
        "mode": "DRY_RUN",
        "ceo_authorization_confirmed": CEO_AUTHORIZATION_CONFIRMED,
        "ceo_authorization_phrase": CEO_AUTHORIZATION_PHRASE,
        "api_key_configured": False,
        "paid_api_called": False,
        "dry_run": True,
        "pull_config": PULL_CONFIG,
        "output_csv_path": str(OUTPUT_CSV_PATH),
        "rows_written": 0,
        "api_key_acquisition_instructions": {
            "step_1": "Register at https://the-odds-api.com",
            "step_2": "Subscribe to a plan with historical data access (~$30-50 one-time or monthly)",
            "step_3": "Locate your API key in the account dashboard",
            "step_4": "Add to .env: THE_ODDS_API_KEY=<your_key>",
            "step_5": "Re-run: .venv/bin/python scripts/_p70_path_a_the_odds_api_historical_pull.py",
            "step_6": "Script will automatically detect key and switch to LIVE mode",
        },
        "governance": _build_governance(paid_api_called=False),
    }


# ---------------------------------------------------------------------------
# Live pull mode (API key present)
# ---------------------------------------------------------------------------

def run_live_pull(api_key: str) -> dict[str, Any]:
    """
    LIVE mode: executes The Odds API historical pull for 2024 MLB moneyline.
    Writes CSV to OUTPUT_CSV_PATH. Returns summary dict.

    This function is only called when CEO_AUTHORIZATION_CONFIRMED=True AND
    API key is present in environment.
    """
    assert CEO_AUTHORIZATION_CONFIRMED, "CEO authorization must be confirmed before live pull"
    assert PAPER_ONLY is True, "PAPER_ONLY must be True — no production use"
    assert REAL_BET_ALLOWED is False, "REAL_BET_ALLOWED must be False"

    source_trace = (
        f"source=the-odds-api.com|pull_date={PULL_DATE}|script=_p70_path_a_the_odds_api_historical_pull.py"
    )

    print("[P70] LIVE mode — executing authorized one-time historical pull")
    print(f"[P70] GOVERNANCE: paper_only=True, real_bet_allowed=False, production_ready=False")
    print(f"[P70] Data: {PULL_CONFIG['sport']} {PULL_CONFIG['season_start']} → {PULL_CONFIG['season_end']}")

    # Step 1: Fetch event list
    events = fetch_season_events(api_key)

    if not events:
        return {
            "p70_version": P70_VERSION,
            "p70_classification": "P70_PATH_A_BLOCKED_BY_API_ERROR",
            "pull_date": PULL_DATE,
            "mode": "LIVE",
            "api_key_configured": True,
            "paid_api_called": True,
            "error": "No events returned from The Odds API — check API key credits and plan",
            "rows_written": 0,
            "governance": _build_governance(paid_api_called=True),
        }

    # Step 2: Fetch historical odds per event
    rows: list[dict] = []
    print(f"[P70] Fetching historical odds for {len(events)} events …")

    for i, event in enumerate(events):
        event_id = event.get("id", "")
        commence_time = event.get("commence_time", "")
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")

        if not event_id or not commence_time:
            continue

        event_data = fetch_event_historical_odds(api_key, event_id, commence_time)
        if event_data is None:
            continue

        row = _extract_row_from_event(event_data, source_trace)
        if row:
            rows.append(row)

        if (i + 1) % 100 == 0:
            print(f"[P70]   Processed {i + 1}/{len(events)} events — {len(rows)} rows collected")

        time.sleep(PULL_CONFIG["rate_limit_seconds"])

    print(f"[P70] Pull complete: {len(rows)} rows collected from {len(events)} events")

    # Step 3: Validate row count
    classification: str
    if len(rows) < 500:
        classification = "P70_PATH_A_PULL_DATA_QUALITY_FAIL"
        print(f"[P70] WARN: only {len(rows)} rows — expected ~2430. Classification: {classification}")
    else:
        classification = "P70_PATH_A_PULL_COMPLETE"

    # Step 4: Write CSV
    if rows:
        write_csv(rows, OUTPUT_CSV_PATH)

    return {
        "p70_version": P70_VERSION,
        "p70_classification": classification,
        "pull_date": PULL_DATE,
        "mode": "LIVE",
        "ceo_authorization_confirmed": CEO_AUTHORIZATION_CONFIRMED,
        "ceo_authorization_phrase": CEO_AUTHORIZATION_PHRASE,
        "api_key_configured": True,
        "paid_api_called": True,
        "dry_run": False,
        "events_fetched": len(events),
        "rows_written": len(rows),
        "output_csv_path": str(OUTPUT_CSV_PATH),
        "pull_config": PULL_CONFIG,
        "governance": _build_governance(paid_api_called=True),
    }


# ---------------------------------------------------------------------------
# Governance block builder
# ---------------------------------------------------------------------------

def _build_governance(paid_api_called: bool) -> dict[str, Any]:
    return {
        "paper_only": PAPER_ONLY,
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "promotion_freeze": PROMOTION_FREEZE,
        "kelly_deploy_allowed": KELLY_DEPLOY_ALLOWED,
        "real_bet_allowed": REAL_BET_ALLOWED,
        "production_ready": PRODUCTION_READY,
        "runtime_recommendation_logic_changed": RUNTIME_RECOMMENDATION_LOGIC_CHANGED,
        "tsl_crawler_called": TSL_CRAWLER_CALLED,
        "bulk_scraping_performed": BULK_SCRAPING_PERFORMED,
        "anti_bot_bypass_attempted": ANTI_BOT_BYPASS_ATTEMPTED,
        "paid_api_called": paid_api_called,
        "platt_a": PLATT_A,
        "platt_b": PLATT_B,
    }


# ---------------------------------------------------------------------------
# Summary writer
# ---------------------------------------------------------------------------

def write_summary(summary: dict[str, Any], output_path: Path | None = None) -> Path:
    if output_path is None:
        output_path = P70_SUMMARY_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return output_path


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_p70(output_path: Path | None = None) -> dict[str, Any]:
    """Full P70 pipeline entry point."""
    # Governance pre-checks
    assert PAPER_ONLY is True, "PAPER_ONLY must be True"
    assert DIAGNOSTIC_ONLY is True, "DIAGNOSTIC_ONLY must be True"
    assert KELLY_DEPLOY_ALLOWED is False, "KELLY_DEPLOY_ALLOWED must be False"
    assert REAL_BET_ALLOWED is False, "REAL_BET_ALLOWED must be False"
    assert PRODUCTION_READY is False, "PRODUCTION_READY must be False"
    assert CEO_AUTHORIZATION_CONFIRMED is True, "CEO authorization must be confirmed"

    api_key = load_api_key()

    if api_key is None:
        summary = run_dry_run()
    else:
        summary = run_live_pull(api_key)

    written_path = write_summary(summary, output_path)
    print(f"[P70] Summary written → {written_path}")
    print(f"[P70] Classification: {summary['p70_classification']}")
    return summary


if __name__ == "__main__":
    run_p70()
