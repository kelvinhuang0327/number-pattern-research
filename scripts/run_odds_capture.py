#!/usr/bin/env python3
"""
MLB Odds Capture CLI

Usage:
  python scripts/run_odds_capture.py --mode live       # One-shot capture from TSL
  python scripts/run_odds_capture.py --mode scheduled  # Smart capture (only if games in window)
  python scripts/run_odds_capture.py --mode status     # Show capture pipeline status
  python scripts/run_odds_capture.py --mode clv        # Compute CLV for all games
  python scripts/run_odds_capture.py --mode backfill   # Re-process tsl_odds_history.jsonl

Designed to be called by cron every 15 minutes:
  */15 * * * * cd /path/to/Betting-pool && python scripts/run_odds_capture.py --mode scheduled
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_live() -> int:
    from wbc_backend.mlb_data.live_odds_collector import capture_live_odds
    result = capture_live_odds(
        odds_api_key=os.environ.get("ODDS_API_KEY"),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_scheduled() -> int:
    from wbc_backend.mlb_data.odds_capture_scheduler import run_scheduled_capture
    result = run_scheduled_capture(
        odds_api_key=os.environ.get("ODDS_API_KEY"),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_status() -> int:
    from wbc_backend.mlb_data.odds_capture_scheduler import get_capture_status
    status = get_capture_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))

    # Quick assessment
    clv_ready = status.get("games_clv_ready", 0)
    total = status.get("total_games", 0)
    if clv_ready >= 30:
        print(f"\n✓ CLV READY: {clv_ready}/{total} games have decision+closing timestamps")
    elif clv_ready > 0:
        print(f"\n⚠ CLV PARTIAL: {clv_ready}/{total} games — need 30 for meaningful analysis")
    else:
        print(f"\n✗ CLV BLOCKED: 0/{total} games have real decision+closing timestamps")
    return 0


def _run_clv() -> int:
    from wbc_backend.mlb_data.clv_calculator import compute_clv_batch
    result = compute_clv_batch()
    # Print summary without per-game details
    summary = {k: v for k, v in result.items() if k != "results"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if result.get("clv_available", 0) > 0:
        print(f"\n✓ Real CLV available for {result['clv_available']} games")
        print(f"  Avg CLV: {result['avg_clv']:.4f}")
        print(f"  Positive CLV rate: {result['positive_clv_rate']:.1%}")
    else:
        print("\n✗ No games with real CLV yet — run captures first")
    return 0


def _run_backfill() -> int:
    """Re-process existing tsl_odds_history.jsonl into the live timeline format."""
    from wbc_backend.mlb_data.live_odds_collector import (
        update_timeline_from_snapshots,
        TIMELINE_PATH,
    )
    from wbc_backend.mlb_data.odds_timeline_asset import (
        MLB_ZH_TO_EN,
        _decimal_to_american,
        _extract_mnl,
    )

    source_path = Path("data/tsl_odds_history.jsonl")
    if not source_path.exists():
        print(f"Source file not found: {source_path}")
        return 1

    snapshots: list[dict] = []
    for line in source_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        home_zh = str(row.get("home_team_name", ""))
        away_zh = str(row.get("away_team_name", ""))
        home_en = MLB_ZH_TO_EN.get(home_zh.strip())
        away_en = MLB_ZH_TO_EN.get(away_zh.strip())
        if not home_en or not away_en:
            continue

        game_time = str(row.get("game_time", ""))
        if not game_time:
            continue

        home_ml, away_ml = _extract_mnl(row)
        if home_ml is None:
            continue

        snapshots.append({
            "home_team": home_en,
            "away_team": away_en,
            "game_time": game_time,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "ou_line": None,
            "fetched_at": str(row.get("fetched_at", "")),
            "source": "TSL_backfill",
        })

    print(f"Found {len(snapshots)} MLB snapshots in tsl_odds_history.jsonl")
    result = update_timeline_from_snapshots(snapshots, TIMELINE_PATH)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MLB Odds Capture Pipeline CLI"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["live", "scheduled", "status", "clv", "backfill"],
        help="Capture mode",
    )
    args = parser.parse_args(argv)

    handlers = {
        "live": _run_live,
        "scheduled": _run_scheduled,
        "status": _run_status,
        "clv": _run_clv,
        "backfill": _run_backfill,
    }
    return handlers[args.mode]()


if __name__ == "__main__":
    raise SystemExit(main())
