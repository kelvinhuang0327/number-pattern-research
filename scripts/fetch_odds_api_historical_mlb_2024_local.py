"""
fetch_odds_api_historical_mlb_2024_local.py
============================================
Fetches historical MLB h2h (moneyline) odds from The Odds API and saves
raw JSON to data/research_odds/local_only/the_odds_api_2024/ (gitignored).

USAGE
-----
  # Dry run (no API call, no key required):
  python3 scripts/fetch_odds_api_historical_mlb_2024_local.py --dry-run --limit-days 2

  # Execute a specific date range (API key required in .env):
  python3 scripts/fetch_odds_api_historical_mlb_2024_local.py \
    --start-date 2024-04-01 --end-date 2024-04-10 --execute

  # Full 2024 season:
  python3 scripts/fetch_odds_api_historical_mlb_2024_local.py \
    --start-date 2024-04-01 --end-date 2024-09-30 --execute

SECURITY RULES (non-negotiable)
---------------------------------
  - API key is read ONLY from .env file (THE_ODDS_API_KEY)
  - Key is NEVER printed, logged, or committed
  - Raw JSON output goes to local_only/ (gitignored)
  - Default mode is --dry-run; --execute must be explicit

LICENSE / DATA POLICY
-----------------------
  - Output license_status = local_only_paid_provider_no_redistribution
  - Do NOT redistribute The Odds API data as a standalone product
  - Research / analytical use only (see The Odds API ToS: NSW, Australia)
  - Do NOT commit raw JSON to git

CREDIT USAGE (The Odds API, h2h market, us region, 20K plan)
--------------------------------------------------------------
  - Each historical snapshot request = 10 credits
  - Per day ≈ 1 request = 10 credits
  - Full 2024 season (~183 days) ≈ 1,830 credits
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SPORT_KEY = "baseball_mlb"
REGIONS = "us"
MARKETS = "h2h"
ODDS_FORMAT = "american"
DATE_FORMAT = "american"
API_BASE = "https://api.the-odds-api.com"
ENV_FILE = Path(__file__).parent.parent / ".env"
OUT_DIR_DEFAULT = Path("data/research_odds/local_only/the_odds_api_2024")
MANIFEST_FILENAME = "MANIFEST.json"
LICENSE_STATUS = "local_only_paid_provider_no_redistribution"
SOURCE_NAME = "the_odds_api_historical_h2h"
RETRY_DELAY_SECONDS = 3
MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# .env reader — never prints key
# ---------------------------------------------------------------------------
def load_api_key(env_path: Path) -> str | None:
    """Read THE_ODDS_API_KEY from .env file. Returns None if not found."""
    if not env_path.exists():
        return None
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == "THE_ODDS_API_KEY":
                val = val.strip()
                if val and val not in ("replace_me", "your_key_here", ""):
                    return val
    return None


def redact(api_key: str) -> str:
    """Produce a safe-to-log redacted version of the key."""
    if not api_key or len(api_key) <= 4:
        return "***REDACTED***"
    return api_key[:4] + "***REDACTED***"


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
def date_range(start: date, end: date) -> list[date]:
    """Return list of dates from start to end inclusive."""
    out: list[date] = []
    current = start
    while current <= end:
        out.append(current)
        current += timedelta(days=1)
    return out


def iso_snapshot_for_date(d: date) -> str:
    """
    Return the ISO 8601 UTC timestamp for the historical snapshot.
    Uses 21:00 UTC which covers all MLB day/night games in America.
    """
    return f"{d.strftime('%Y-%m-%d')}T21:00:00Z"


# ---------------------------------------------------------------------------
# API caller
# ---------------------------------------------------------------------------
def fetch_historical_odds(
    api_key: str,
    snapshot_utc: str,
    out_path: Path,
    verbose: bool = True,
) -> dict:
    """
    Fetch historical h2h odds for a single UTC snapshot timestamp.
    Saves raw JSON to out_path. Returns the parsed JSON dict.

    Raises RuntimeError on API error or non-200 response.
    """
    endpoint = f"{API_BASE}/v4/historical/sports/{SPORT_KEY}/odds"
    params = {
        "apiKey": api_key,  # never logged
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
        "date": snapshot_utc,
    }

    safe_params = {k: v for k, v in params.items() if k != "apiKey"}
    if verbose:
        print(f"  → GET {endpoint}")
        print(f"    params: {json.dumps(safe_params)}")

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            response = requests.get(endpoint, params=params, timeout=30)
        except requests.RequestException as exc:
            if attempt <= MAX_RETRIES:
                print(f"  ⚠ Network error (attempt {attempt}): {exc}. Retrying in {RETRY_DELAY_SECONDS}s...")
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            raise RuntimeError(f"Network error after {attempt} attempts: {exc}") from exc

        if response.status_code == 401:
            # Key is invalid — fail fast, never print key
            raise RuntimeError(
                "HTTP 401 Unauthorized. The Odds API key is invalid or expired. "
                f"Key (redacted): {redact(api_key)}"
            )
        if response.status_code == 422:
            raise RuntimeError(
                f"HTTP 422 Unprocessable Entity. Snapshot date may be out of range or invalid: {snapshot_utc}. "
                "Historical data available from 2020-06-06 onwards."
            )
        if response.status_code == 429:
            if attempt <= MAX_RETRIES:
                print(f"  ⚠ HTTP 429 Rate limited (attempt {attempt}). Retrying in {RETRY_DELAY_SECONDS}s...")
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            raise RuntimeError("HTTP 429 Rate limited after retries.")
        if response.status_code != 200:
            raise RuntimeError(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )

        data = response.json()

        # Inject provenance metadata before saving
        provenance = {
            "_fetch_meta": {
                "snapshot_utc": snapshot_utc,
                "sport_key": SPORT_KEY,
                "regions": REGIONS,
                "markets": MARKETS,
                "odds_format": ODDS_FORMAT,
                "source_name": SOURCE_NAME,
                "license_status": LICENSE_STATUS,
                "remaining_requests": response.headers.get("x-requests-remaining", "unknown"),
                "used_requests": response.headers.get("x-requests-used", "unknown"),
                "fetched_at_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                "do_not_redistribute": True,
                "research_use_only": True,
            }
        }

        if isinstance(data, list):
            result = {"data": data, **provenance}
        else:
            result = {**data, **provenance}

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        remaining = response.headers.get("x-requests-remaining", "unknown")
        if verbose:
            print(f"  ✓ Saved → {out_path} (credits remaining: {remaining})")

        return result

    raise RuntimeError("Exhausted retries.")


# ---------------------------------------------------------------------------
# Manifest management
# ---------------------------------------------------------------------------
def load_manifest(out_dir: Path) -> dict:
    manifest_path = out_dir / MANIFEST_FILENAME
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"fetched_dates": [], "failed_dates": [], "source": SOURCE_NAME, "license_status": LICENSE_STATUS}


def save_manifest(out_dir: Path, manifest: dict) -> None:
    manifest_path = out_dir / MANIFEST_FILENAME
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch historical MLB h2h odds from The Odds API to local-only storage.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--start-date",
        default="2024-04-01",
        metavar="YYYY-MM-DD",
        help="Start date inclusive (default: 2024-04-01).",
    )
    parser.add_argument(
        "--end-date",
        default="2024-04-10",
        metavar="YYYY-MM-DD",
        help="End date inclusive (default: 2024-04-10).",
    )
    parser.add_argument(
        "--sport",
        default=SPORT_KEY,
        metavar="SPORT_KEY",
        help=f"The Odds API sport key (default: {SPORT_KEY}).",
    )
    parser.add_argument(
        "--regions",
        default=REGIONS,
        metavar="REGIONS",
        help=f"Comma-separated regions (default: {REGIONS}).",
    )
    parser.add_argument(
        "--markets",
        default=MARKETS,
        metavar="MARKETS",
        help=f"Comma-separated markets (default: {MARKETS}).",
    )
    parser.add_argument(
        "--odds-format",
        default=ODDS_FORMAT,
        choices=["american", "decimal", "fractional"],
        help=f"Odds format (default: {ODDS_FORMAT}).",
    )
    parser.add_argument(
        "--out-dir",
        default=str(OUT_DIR_DEFAULT),
        metavar="PATH",
        help=f"Output directory (default: {OUT_DIR_DEFAULT}).",
    )
    parser.add_argument(
        "--limit-days",
        type=int,
        default=None,
        metavar="N",
        help="Limit to first N days of the date range.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip dates that already have a JSON file (default: True).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without making any API calls (no key required).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually fetch data. Requires THE_ODDS_API_KEY in .env.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose output (default: True).",
    )

    args = parser.parse_args()

    # Must specify at least one mode
    if not args.dry_run and not args.execute:
        print("ERROR: Specify --dry-run or --execute.", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Both specified: --dry-run takes precedence with a warning
    if args.dry_run and args.execute:
        print("WARNING: Both --dry-run and --execute specified. Running --dry-run only.")
        args.execute = False

    # Parse dates
    try:
        start = date.fromisoformat(args.start_date)
        end = date.fromisoformat(args.end_date)
    except ValueError as exc:
        print(f"ERROR: Invalid date format: {exc}", file=sys.stderr)
        sys.exit(1)

    if start > end:
        print(f"ERROR: start-date ({start}) must be <= end-date ({end}).", file=sys.stderr)
        sys.exit(1)

    dates = date_range(start, end)
    if args.limit_days:
        dates = dates[: args.limit_days]

    out_dir = Path(args.out_dir)

    # ---------- DRY RUN ----------
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN — No API calls will be made")
        print("=" * 60)
        print(f"  Sport:       {args.sport}")
        print(f"  Regions:     {args.regions}")
        print(f"  Markets:     {args.markets}")
        print(f"  Odds format: {args.odds_format}")
        print(f"  Date range:  {start} → {end}")
        print(f"  Total days:  {len(dates)}")
        print(f"  Est. credits: {len(dates) * 10} (@ 10 per snapshot)")
        print(f"  Output dir:  {out_dir}")
        print(f"  License:     {LICENSE_STATUS}")
        print()
        print("  Dates to fetch:")
        for d in dates:
            snapshot = iso_snapshot_for_date(d)
            out_path = out_dir / f"{d}.json"
            already = "(ALREADY EXISTS)" if out_path.exists() else ""
            print(f"    {d} → {out_path} {already}")
        print()
        print("  To execute, run with --execute instead of --dry-run")
        print("  API key must be set in .env as: THE_ODDS_API_KEY=<your_key>")
        print()
        print("DRY_RUN_COMPLETE")
        return

    # ---------- EXECUTE ----------
    print("=" * 60)
    print("EXECUTE MODE — Real API calls")
    print("=" * 60)

    # Load API key — fail fast if not present
    api_key = load_api_key(ENV_FILE)
    if not api_key:
        print(
            f"ERROR: THE_ODDS_API_KEY not found in {ENV_FILE}\n"
            f"  Create .env with: THE_ODDS_API_KEY=your_actual_key\n"
            f"  See: 00-BettingPlan/20260513/p32_paid_provider_operator_action_packet_20260515.md",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"  API key loaded: {redact(api_key)}")
    print(f"  Date range:  {start} → {end}")
    print(f"  Total days:  {len(dates)}")
    print(f"  Est. credits: {len(dates) * 10}")
    print(f"  Output dir:  {out_dir}")
    print()

    manifest = load_manifest(out_dir)
    fetched_dates_set = set(manifest.get("fetched_dates", []))
    failed: list[str] = []
    fetched: list[str] = []
    skipped: list[str] = []

    for d in dates:
        date_str = str(d)
        out_path = out_dir / f"{date_str}.json"

        if args.skip_existing and date_str in fetched_dates_set:
            print(f"  SKIP {date_str} (already in manifest)")
            skipped.append(date_str)
            continue
        if args.skip_existing and out_path.exists():
            print(f"  SKIP {date_str} (file exists: {out_path})")
            skipped.append(date_str)
            continue

        snapshot_utc = iso_snapshot_for_date(d)
        print(f"  FETCH {date_str} (snapshot: {snapshot_utc})")

        try:
            fetch_historical_odds(
                api_key=api_key,
                snapshot_utc=snapshot_utc,
                out_path=out_path,
                verbose=args.verbose,
            )
            fetched.append(date_str)
            if date_str not in fetched_dates_set:
                manifest.setdefault("fetched_dates", []).append(date_str)
                fetched_dates_set.add(date_str)
        except RuntimeError as exc:
            print(f"  ✗ ERROR on {date_str}: {exc}", file=sys.stderr)
            failed.append(date_str)
            manifest.setdefault("failed_dates", []).append(date_str)
        finally:
            save_manifest(out_dir, manifest)

        # Small delay to avoid hammering the API
        if len(dates) > 1:
            time.sleep(0.5)

    print()
    print("=" * 60)
    print("FETCH SUMMARY")
    print("=" * 60)
    print(f"  Fetched:  {len(fetched)}")
    print(f"  Skipped:  {len(skipped)}")
    print(f"  Failed:   {len(failed)}")

    if failed:
        print(f"\n  FAILED DATES: {failed}")
        print("  Check .env key validity and API quota.", file=sys.stderr)

    if len(failed) > 0 and len(fetched) == 0:
        print("\nFATAL: No data fetched. Check API key and quota.", file=sys.stderr)
        sys.exit(1)

    print("\nFETCH_COMPLETE")
    print(f"  Output: {out_dir}")
    print(f"  Next step: python3 scripts/transform_odds_api_to_research_contract.py --in-dir {out_dir} --out-file data/research_odds/local_only/research_contract_2024.csv")


if __name__ == "__main__":
    main()
