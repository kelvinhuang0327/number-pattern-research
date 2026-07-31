"""
transform_odds_api_to_research_contract.py
===========================================
Transforms raw JSON files fetched by fetch_odds_api_historical_mlb_2024_local.py
into the 23-column research contract CSV defined in:
  00-BettingPlan/20260513/research_odds_manual_import_contract_20260513.md

OUTPUT SCHEMA (23 columns)
---------------------------
game_id, game_date, season, away_team, home_team,
home_ml_american, away_ml_american, home_ml_decimal, away_ml_decimal,
home_implied_prob_raw, away_implied_prob_raw, vig_total,
home_no_vig_prob, away_no_vig_prob,
bookmaker_key, market_key, odds_timestamp_utc,
snapshot_type, source_name, source_row_number,
source_license_status, source_license_type, retrieval_method

SECURITY / DATA POLICY
-----------------------
  - Input: raw JSON from data/research_odds/local_only/ (gitignored)
  - Output: also stored in data/research_odds/local_only/ (gitignored)
  - Never committed to git
  - license_status = local_only_paid_provider_no_redistribution
  - For research / analytical use only (see The Odds API ToS)

LEAKAGE CLASSIFICATION
-----------------------
  - Odds timestamp is from The Odds API snapshot (21:00 UTC pre-game)
  - Explicitly tagged: snapshot_type = historical_pre_game (or historical_live)
  - Leakage risk: LOW for closing-line-equivalent snapshots
  - Leakage classification is written to output and report

USAGE
-----
  # Dry-run: print plan, no output file written
  python3 scripts/transform_odds_api_to_research_contract.py \
    --in-dir data/research_odds/local_only/the_odds_api_2024 \
    --dry-run

  # Execute: write contract CSV
  python3 scripts/transform_odds_api_to_research_contract.py \
    --in-dir data/research_odds/local_only/the_odds_api_2024 \
    --out-file data/research_odds/local_only/research_contract_2024.csv \
    --execute
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Team name → Retrosheet 3-letter code mapping
# The Odds API returns full team names; we normalize to Retrosheet codes.
# Source: p38a_odds_join_key_mapping_spec_20260514.md §3.1
# ---------------------------------------------------------------------------
FULL_NAME_TO_RETROSHEET: dict[str, str] = {
    # American League East
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "New York Yankees": "NYA",
    "Tampa Bay Rays": "TBA",
    "Toronto Blue Jays": "TOR",
    # American League Central
    "Chicago White Sox": "CHA",
    "Cleveland Guardians": "CLE",
    "Detroit Tigers": "DET",
    "Kansas City Royals": "KCA",
    "Minnesota Twins": "MIN",
    # American League West
    "Houston Astros": "HOU",
    "Los Angeles Angels": "ANA",
    "Oakland Athletics": "OAK",
    "Sacramento Athletics": "OAK",  # relocation alias
    "Athletics": "OAK",
    "Seattle Mariners": "SEA",
    "Texas Rangers": "TEX",
    # National League East
    "Atlanta Braves": "ATL",
    "Miami Marlins": "MIA",
    "New York Mets": "NYN",
    "Philadelphia Phillies": "PHI",
    "Washington Nationals": "WAS",
    # National League Central
    "Chicago Cubs": "CHN",
    "Cincinnati Reds": "CIN",
    "Milwaukee Brewers": "MIL",
    "Pittsburgh Pirates": "PIT",
    "St. Louis Cardinals": "SLN",
    # National League West
    "Arizona Diamondbacks": "ARI",
    "Colorado Rockies": "COL",
    "Los Angeles Dodgers": "LAN",
    "San Diego Padres": "SDN",
    "San Francisco Giants": "SFN",
}

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------
CONTRACT_COLUMNS = [
    "game_id",
    "game_date",
    "season",
    "away_team",
    "home_team",
    "home_ml_american",
    "away_ml_american",
    "home_ml_decimal",
    "away_ml_decimal",
    "home_implied_prob_raw",
    "away_implied_prob_raw",
    "vig_total",
    "home_no_vig_prob",
    "away_no_vig_prob",
    "bookmaker_key",
    "market_key",
    "odds_timestamp_utc",
    "snapshot_type",
    "source_name",
    "source_row_number",
    "source_license_status",
    "source_license_type",
    "retrieval_method",
]

LICENSE_STATUS = "local_only_paid_provider_no_redistribution"
LICENSE_TYPE = "paid_provider_historical_api"
RETRIEVAL_METHOD = "the_odds_api_historical_h2h"
SOURCE_NAME = "the_odds_api"
MARKET_KEY = "h2h"


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------
def american_to_decimal(american: int) -> float:
    """Convert American odds integer to decimal odds."""
    if american > 0:
        return round(1.0 + american / 100.0, 6)
    else:
        return round(1.0 + 100.0 / abs(american), 6)


def american_to_implied_prob(american: int) -> float:
    """Convert American odds integer to raw implied probability (includes vig)."""
    if american > 0:
        return round(100.0 / (100.0 + american), 6)
    else:
        return round(abs(american) / (abs(american) + 100.0), 6)


def no_vig_probs(raw_home: float, raw_away: float) -> tuple[float, float]:
    """
    Remove vig using proportional method.
    home_no_vig = raw_home / (raw_home + raw_away)
    away_no_vig = raw_away / (raw_home + raw_away)
    """
    total = raw_home + raw_away
    if total <= 0:
        return (0.5, 0.5)
    return (round(raw_home / total, 6), round(raw_away / total, 6))


def normalize_team(full_name: str) -> str:
    """Map full team name to Retrosheet code. Returns original if not found."""
    return FULL_NAME_TO_RETROSHEET.get(full_name, full_name)


def classify_snapshot_type(odds_timestamp_utc: str) -> str:
    """
    Classify whether the snapshot is pre-game (closing line) or during game.
    The Odds API 21:00 UTC snapshot is before most night games but after
    daytime doubleheaders. Classify as 'historical_pre_game' by default.
    
    A more rigorous classification requires game start time — not available
    from this API call. Mark as pre-game and note the assumption.
    """
    return "historical_pre_game_assumed"


def derive_game_id(home_retro: str, game_date_str: str, game_num: int = 0) -> str:
    """
    Derive game_id in Retrosheet format: {HOME}-{YYYYMMDD}-{N}
    Note: game_num=0 means first game (or only game) of the day.
    Doubleheader disambiguation requires additional data not available here.
    """
    date_compact = game_date_str.replace("-", "")
    return f"{home_retro}-{date_compact}-{game_num}"


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------
def parse_json_file(json_path: Path) -> Iterator[dict]:
    """
    Parse a single The Odds API historical JSON file.
    Yields one row dict per (bookmaker, home_team, away_team, game) combination.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    fetch_meta = raw.get("_fetch_meta", {})
    odds_timestamp_utc = fetch_meta.get("snapshot_utc", "")

    # The Odds API returns {"data": [...]} or a list directly
    games = raw.get("data", [])
    if isinstance(raw, list):
        games = raw

    for game in games:
        if not isinstance(game, dict):
            continue

        commence_time = game.get("commence_time", "")  # ISO 8601 UTC
        game_date_str = commence_time[:10] if commence_time else ""  # YYYY-MM-DD
        season = int(game_date_str[:4]) if game_date_str else 0

        home_team_full = game.get("home_team", "")
        away_team_full = game.get("away_team", "")
        home_retro = normalize_team(home_team_full)
        away_retro = normalize_team(away_team_full)

        bookmakers = game.get("bookmakers", [])
        for bookmaker in bookmakers:
            bk_key = bookmaker.get("key", "")
            markets = bookmaker.get("markets", [])
            for market in markets:
                if market.get("key") != "h2h":
                    continue
                outcomes = market.get("outcomes", [])

                # Parse outcomes into home/away
                home_price: int | None = None
                away_price: int | None = None
                for outcome in outcomes:
                    name = outcome.get("name", "")
                    price = outcome.get("price")
                    if price is None:
                        continue
                    price = int(round(float(price)))
                    if name == home_team_full:
                        home_price = price
                    elif name == away_team_full:
                        away_price = price

                if home_price is None or away_price is None:
                    continue  # skip incomplete rows

                home_decimal = american_to_decimal(home_price)
                away_decimal = american_to_decimal(away_price)
                home_raw_prob = american_to_implied_prob(home_price)
                away_raw_prob = american_to_implied_prob(away_price)
                vig_total = round(home_raw_prob + away_raw_prob, 6)
                home_no_vig, away_no_vig = no_vig_probs(home_raw_prob, away_raw_prob)
                snapshot_type = classify_snapshot_type(odds_timestamp_utc)
                game_id = derive_game_id(home_retro, game_date_str)

                yield {
                    "game_id": game_id,
                    "game_date": game_date_str,
                    "season": season,
                    "away_team": away_retro,
                    "home_team": home_retro,
                    "home_ml_american": home_price,
                    "away_ml_american": away_price,
                    "home_ml_decimal": home_decimal,
                    "away_ml_decimal": away_decimal,
                    "home_implied_prob_raw": home_raw_prob,
                    "away_implied_prob_raw": away_raw_prob,
                    "vig_total": vig_total,
                    "home_no_vig_prob": home_no_vig,
                    "away_no_vig_prob": away_no_vig,
                    "bookmaker_key": bk_key,
                    "market_key": MARKET_KEY,
                    "odds_timestamp_utc": odds_timestamp_utc,
                    "snapshot_type": snapshot_type,
                    "source_name": SOURCE_NAME,
                    "source_row_number": None,  # filled in below
                    "source_license_status": LICENSE_STATUS,
                    "source_license_type": LICENSE_TYPE,
                    "retrieval_method": RETRIEVAL_METHOD,
                }


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transform The Odds API raw JSON → 23-column research contract CSV.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--in-dir",
        default="data/research_odds/local_only/the_odds_api_2024",
        metavar="PATH",
        help="Directory containing raw JSON files (default: the_odds_api_2024/).",
    )
    parser.add_argument(
        "--out-file",
        default="data/research_odds/local_only/research_contract_2024.csv",
        metavar="PATH",
        help="Output CSV path (local-only, gitignored).",
    )
    parser.add_argument(
        "--bookmakers",
        default=None,
        metavar="KEYS",
        help="Comma-separated bookmaker keys to include (default: all). E.g. draftkings,fanduel",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without writing output file.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the output CSV.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose output.",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("ERROR: Specify --dry-run or --execute.", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.dry_run and args.execute:
        print("WARNING: Both --dry-run and --execute specified. Running --dry-run only.")
        args.execute = False

    in_dir = Path(args.in_dir)
    out_file = Path(args.out_file)

    if not in_dir.exists():
        print(f"ERROR: Input directory not found: {in_dir}", file=sys.stderr)
        sys.exit(1)

    json_files = sorted(in_dir.glob("*.json"))
    # Exclude MANIFEST.json
    json_files = [f for f in json_files if f.name != "MANIFEST.json" and not f.name.startswith("_")]

    if not json_files:
        print(f"ERROR: No raw JSON files found in {in_dir}", file=sys.stderr)
        print("  Run fetch_odds_api_historical_mlb_2024_local.py --execute first.", file=sys.stderr)
        sys.exit(1)

    bookmaker_filter = None
    if args.bookmakers:
        bookmaker_filter = set(args.bookmakers.split(","))

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN — No output file will be written")
        print("=" * 60)
        print(f"  Input dir:      {in_dir}")
        print(f"  JSON files:     {len(json_files)}")
        print(f"  Output file:    {out_file}")
        print(f"  Bookmaker filter: {bookmaker_filter or 'ALL'}")
        print(f"  Schema columns: {len(CONTRACT_COLUMNS)}")
        print(f"  License status: {LICENSE_STATUS}")
        print()
        print("  Files to process:")
        for f in json_files:
            print(f"    {f.name}")
        print()
        print("  Leakage classification:")
        print("    snapshot_type = historical_pre_game_assumed")
        print("    Assumption: 21:00 UTC snapshot is before most night games")
        print("    Caveat: daytime games may have started before snapshot")
        print("    Full leakage audit requires game start times from bridge table")
        print()
        print("DRY_RUN_COMPLETE")
        return

    # Execute
    print("=" * 60)
    print("TRANSFORM EXECUTE")
    print("=" * 60)

    rows: list[dict] = []
    errors: list[str] = []

    for json_path in json_files:
        if args.verbose:
            print(f"  Processing: {json_path.name}")
        try:
            for row in parse_json_file(json_path):
                if bookmaker_filter and row["bookmaker_key"] not in bookmaker_filter:
                    continue
                rows.append(row)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            err_msg = f"Parse error in {json_path.name}: {exc}"
            print(f"  ✗ {err_msg}", file=sys.stderr)
            errors.append(err_msg)

    # Assign source_row_number
    for i, row in enumerate(rows):
        row["source_row_number"] = i + 1

    if not rows:
        print("ERROR: No rows extracted. Check JSON file content.", file=sys.stderr)
        sys.exit(1)

    # Write output
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CONTRACT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print()
    print("=" * 60)
    print("TRANSFORM SUMMARY")
    print("=" * 60)
    print(f"  Rows written:   {len(rows)}")
    print(f"  Parse errors:   {len(errors)}")
    print(f"  Output file:    {out_file}")
    print(f"  License status: {LICENSE_STATUS}")
    print(f"  Leakage note:   snapshot_type=historical_pre_game_assumed")

    if errors:
        print("\n  PARSE ERRORS:")
        for e in errors:
            print(f"    {e}")

    # Warn if output is very small
    if len(rows) < 100:
        print(f"\n  ⚠ WARNING: Only {len(rows)} rows extracted. ≥100 rows required for join smoke.")
        print("    Consider expanding --start-date / --end-date range.")

    print("\nTRANSFORM_COMPLETE")
    print(f"  Next step: Run join smoke with the output CSV")


if __name__ == "__main__":
    main()
