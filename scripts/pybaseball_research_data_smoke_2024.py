"""
P3.7A — pybaseball Research Data Smoke Test
============================================
PURPOSE:
    Verify pybaseball can fetch MLB Statcast / summary data for a small date range.
    This is a research-only baseball statistics adapter.

IMPORTANT:
    - pybaseball does NOT provide betting odds.
    - This script does NOT output moneyline, closing odds, CLV, or sportsbook data.
    - Raw data written only to data/pybaseball/local_only/ (gitignored).
    - Default mode: --summary-only (no raw data written).

USAGE:
    .venv/bin/python scripts/pybaseball_research_data_smoke_2024.py \\
        --start-date 2024-04-01 \\
        --end-date 2024-04-03 \\
        --summary-only

    .venv/bin/python scripts/pybaseball_research_data_smoke_2024.py \\
        --start-date 2024-04-01 \\
        --end-date 2024-04-03 \\
        --write-local    # writes to data/pybaseball/local_only/ (gitignored)

MARKER: P3.7A_PYBASEBALL_SMOKE_SCRIPT
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_ONLY_DIR = REPO_ROOT / "data" / "pybaseball" / "local_only"
SCRIPT_VERSION = "p37a_pybaseball_smoke_v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _header(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print("=" * 60)


def _ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"  [INFO] {msg}")


# ---------------------------------------------------------------------------
# Statcast smoke
# ---------------------------------------------------------------------------
def smoke_statcast(start_date: str, end_date: str, write_local: bool) -> dict:
    """Fetch a small Statcast slice and return summary stats."""
    try:
        from pybaseball import statcast  # type: ignore[import-untyped]
    except ImportError:
        return {
            "status": "FAIL",
            "error": "pybaseball not installed — run: .venv/bin/pip install pybaseball",
        }

    _info(f"Fetching Statcast {start_date} → {end_date} …")
    try:
        df = statcast(start_dt=start_date, end_dt=end_date, verbose=False)
    except Exception as exc:
        return {
            "status": "FAIL",
            "error": f"statcast() raised: {type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }

    if df is None or (hasattr(df, "__len__") and len(df) == 0):
        return {"status": "FAIL", "error": "statcast() returned empty DataFrame"}

    rows = len(df)
    cols = list(df.columns) if hasattr(df, "columns") else []
    col_count = len(cols)

    # Confirm no odds columns are present
    FORBIDDEN_COLUMNS = {
        "moneyline", "closing_line", "odds", "vig", "implied_prob",
        "home_ml", "away_ml", "home_odds", "away_odds", "clv",
    }
    odds_cols_found = [c for c in cols if any(f in c.lower() for f in FORBIDDEN_COLUMNS)]

    date_range_actual: Optional[str] = None
    if "game_date" in cols:
        try:
            dates = df["game_date"].dropna().astype(str)
            date_range_actual = f"{dates.min()} → {dates.max()}"
        except Exception:
            date_range_actual = "PARSE_ERROR"

    sample_cols = cols[:10]

    summary = {
        "status": "PASS",
        "rows": rows,
        "columns": col_count,
        "sample_columns": sample_cols,
        "date_range_actual": date_range_actual,
        "odds_columns_found": odds_cols_found,
        "odds_boundary_confirmed": len(odds_cols_found) == 0,
    }

    if write_local:
        LOCAL_ONLY_DIR.mkdir(parents=True, exist_ok=True)
        out_path = LOCAL_ONLY_DIR / f"statcast_{start_date}_{end_date}.parquet"
        try:
            df.to_parquet(out_path, index=False)
            summary["written_to"] = str(out_path)
            _ok(f"Raw data written to: {out_path}")
        except Exception as exc:
            summary["write_error"] = str(exc)
            _warn(f"Could not write parquet: {exc}")

    return summary


# ---------------------------------------------------------------------------
# Team batting smoke (simple standings / batting aggregate)
# ---------------------------------------------------------------------------
def smoke_team_batting(season: int) -> dict:
    """Attempt a simple team batting summary via pybaseball."""
    try:
        from pybaseball import team_batting  # type: ignore[import-untyped]
    except ImportError:
        return {"status": "SKIP", "reason": "team_batting not in this pybaseball version"}

    _info(f"Fetching team batting for season {season} …")
    try:
        df = team_batting(season)
    except Exception as exc:
        return {
            "status": "FAIL",
            "error": f"team_batting() raised: {type(exc).__name__}: {exc}",
        }

    if df is None or (hasattr(df, "__len__") and len(df) == 0):
        return {"status": "FAIL", "error": "team_batting() returned empty"}

    return {
        "status": "PASS",
        "rows": len(df),
        "columns": len(df.columns) if hasattr(df, "columns") else 0,
        "sample_columns": list(df.columns)[:8] if hasattr(df, "columns") else [],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="P3.7A pybaseball research data smoke test"
    )
    parser.add_argument("--start-date", default="2024-04-01", help="Statcast start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2024-04-03", help="Statcast end date (YYYY-MM-DD)")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        default=True,
        help="Only print summary, do not write raw data (default: True)",
    )
    parser.add_argument(
        "--write-local",
        action="store_true",
        default=False,
        help="Write raw data to data/pybaseball/local_only/ (gitignored)",
    )
    args = parser.parse_args()

    write_local = args.write_local and not args.summary_only

    _header("P3.7A pybaseball Research Data Smoke")
    print(f"  Script version : {SCRIPT_VERSION}")
    print(f"  Start date     : {args.start_date}")
    print(f"  End date       : {args.end_date}")
    print(f"  Write local    : {write_local}")
    print(f"  Run timestamp  : {datetime.utcnow().isoformat()}Z")
    print()
    print("  BOUNDARY: pybaseball does NOT provide betting odds.")
    print("  This script produces baseball statistics only.")

    # --- Statcast smoke ---
    _header("Statcast Smoke")
    statcast_result = smoke_statcast(args.start_date, args.end_date, write_local)

    if statcast_result["status"] == "PASS":
        _ok(f"Statcast rows     : {statcast_result['rows']}")
        _ok(f"Statcast columns  : {statcast_result['columns']}")
        _ok(f"Date range actual : {statcast_result.get('date_range_actual', 'N/A')}")
        _ok(f"Sample columns    : {statcast_result.get('sample_columns', [])}")
        if statcast_result["odds_boundary_confirmed"]:
            _ok("Odds boundary     : CONFIRMED (no odds columns present)")
        else:
            _warn(f"Unexpected odds columns: {statcast_result['odds_columns_found']}")
    else:
        _fail(f"Statcast FAILED: {statcast_result.get('error', 'unknown')}")

    # --- Team batting smoke ---
    _header("Team Batting Smoke (2024)")
    batting_result = smoke_team_batting(2024)
    if batting_result["status"] == "PASS":
        _ok(f"Team batting rows : {batting_result['rows']}")
        _ok(f"Team batting cols : {batting_result['columns']}")
        _ok(f"Sample columns    : {batting_result.get('sample_columns', [])}")
    elif batting_result["status"] == "SKIP":
        _info(f"Skipped: {batting_result.get('reason', '')}")
    else:
        _fail(f"Team batting FAILED: {batting_result.get('error', 'unknown')}")

    # --- Final summary ---
    _header("Summary")
    statcast_pass = statcast_result["status"] == "PASS"
    batting_pass = batting_result["status"] in ("PASS", "SKIP")
    overall = "PASS" if statcast_pass else "FAIL"

    print(f"  Statcast smoke  : {statcast_result['status']}")
    print(f"  Team batting    : {batting_result['status']}")
    print(f"  Overall         : {overall}")
    print()
    if overall == "PASS":
        print("  Marker: PYBASEBALL_RESEARCH_DATA_SMOKE_PASS_20260515")
    else:
        print("  Marker: PYBASEBALL_RESEARCH_DATA_SMOKE_FAILED_20260515")
    print()
    print("  NOTE: pybaseball does NOT provide betting odds.")
    print("        This output is baseball statistics only.")

    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
