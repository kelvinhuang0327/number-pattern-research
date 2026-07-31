"""
P8-D — 2026 TSL Forward Collection Dry-Run Scaffold

不修改 TSL crawler。只讀現有 data/tsl_odds_history.jsonl。
不做網路呼叫。產出 collection manifest。

paper_only=true。不代表任何實盤獲利能力。
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from wbc_backend.recommendation.odds_contract import OddsSourceType

DRY_RUN_BANNER = (
    "*** DRY-RUN PLAN — No network calls. No crawler modification. "
    "No production writes. paper_only=true ***"
)

JSONL_PATH = Path(__file__).parent.parent / "data" / "tsl_odds_history.jsonl"

# Thresholds (must match P7)
MIN_TIMESTAMP_COVERAGE_PCT: float = 95.0
MIN_PAIR_COVERAGE_PCT: float = 90.0
MIN_PAIRS_FOR_CLV: int = 200

SCHEDULE_WINDOWS: list[dict] = [
    {
        "label": "early",
        "offset_hours_before_game": (24, 72),
        "priority": "NICE_TO_HAVE",
        "snapshot_type": "early",
    },
    {
        "label": "pregame_d1",
        "offset_hours_before_game": (6, 24),
        "priority": "HIGH",
        "snapshot_type": "pregame",
    },
    {
        "label": "pregame_d2",
        "offset_hours_before_game": (2, 6),
        "priority": "CRITICAL",
        "snapshot_type": "pregame",
    },
    {
        "label": "decision",
        "offset_hours_before_game": (0.5, 2),
        "priority": "CRITICAL",
        "snapshot_type": "decision",
    },
    {
        "label": "closing_final",
        "offset_hours_before_game": (1 / 12, 1),
        "priority": "CRITICAL",
        "snapshot_type": "closing",
        "note": "captured_at must be < game_start_utc; closing_window_sec=3600",
    },
]

TARGET_MARKETS: list[dict] = [
    {
        "market_code": "ML",
        "tsl_code": "MNL",
        "description": "Moneyline",
        "priority": "CRITICAL",
        "minimum_viable": True,
    },
    {
        "market_code": "RL",
        "tsl_code": "HDP",
        "description": "Run Line / Handicap",
        "priority": "MEDIUM",
        "minimum_viable": False,
    },
    {
        "market_code": "OU",
        "tsl_code": "OU",
        "description": "Over/Under Total Runs",
        "priority": "MEDIUM",
        "minimum_viable": False,
    },
]


class ForwardCollectionError(ValueError):
    """Raised when forward collection plan validation fails."""


def _parse_fetched_at(record: dict) -> Optional[datetime]:
    """Parse fetched_at field to UTC datetime; return None on failure."""
    raw = record.get("fetched_at")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _parse_game_time(record: dict) -> Optional[datetime]:
    """Parse game_time field to UTC datetime; return None on failure."""
    raw = record.get("game_time")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _classify_snapshot_type(
    fetched_at: Optional[datetime],
    game_start: Optional[datetime],
    closing_window_sec: int = 3600,
    pregame_min_sec: int = 60,
) -> str:
    """Classify snapshot type based on timing."""
    if fetched_at is None or game_start is None:
        return OddsSourceType.UNKNOWN.value
    delta = (game_start - fetched_at).total_seconds()
    if delta < 0:
        return OddsSourceType.POST_GAME_PROXY.value
    if delta <= closing_window_sec:
        return OddsSourceType.CLOSING.value
    return OddsSourceType.PREGAME.value


def summarize_existing_timeline(
    jsonl_path: Path,
) -> dict:
    """
    Summarize the existing TSL odds timeline from JSONL file.

    Does NOT make network calls. Does NOT modify any files.
    Returns a summary dict for use in the collection manifest.
    """
    if not jsonl_path.exists():
        return {
            "file_found": False,
            "total_records": 0,
            "date_range_start": None,
            "date_range_end": None,
            "match_ids_seen": 0,
            "snapshot_type_counts": {},
            "market_counts": {},
            "timestamp_coverage_pct": 0.0,
            "pregame_closing_pairs": 0,
            "pregame_closing_pair_coverage_pct": 0.0,
        }

    records: list[dict] = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not records:
        return {
            "file_found": True,
            "total_records": 0,
            "date_range_start": None,
            "date_range_end": None,
            "match_ids_seen": 0,
            "snapshot_type_counts": {},
            "market_counts": {},
            "timestamp_coverage_pct": 0.0,
            "pregame_closing_pairs": 0,
            "pregame_closing_pair_coverage_pct": 0.0,
        }

    fetched_dates: list[datetime] = []
    match_ids: set[str] = set()
    type_counts: dict[str, int] = defaultdict(int)
    market_counts: dict[str, int] = defaultdict(int)
    match_snapshot_types: dict[str, set[str]] = defaultdict(set)
    records_with_timestamp = 0

    for rec in records:
        fa = _parse_fetched_at(rec)
        gt = _parse_game_time(rec)
        mid = rec.get("match_id", "")

        if fa:
            fetched_dates.append(fa)
            records_with_timestamp += 1

        if mid:
            match_ids.add(mid)

        stype = _classify_snapshot_type(fa, gt)
        type_counts[stype] += 1

        if mid and stype in (OddsSourceType.PREGAME.value, OddsSourceType.CLOSING.value):
            match_snapshot_types[mid].add(stype)

        for mkt in rec.get("markets", []):
            code = mkt.get("marketCode", "UNKNOWN")
            market_counts[code] += 1

    # Pairs: match_ids that have BOTH pregame and closing
    pairs = sum(
        1
        for types in match_snapshot_types.values()
        if OddsSourceType.PREGAME.value in types and OddsSourceType.CLOSING.value in types
    )

    total_records = len(records)
    ts_coverage = (records_with_timestamp / total_records * 100) if total_records > 0 else 0.0
    total_matches = len(match_ids)
    pair_coverage = (pairs / total_matches * 100) if total_matches > 0 else 0.0

    return {
        "file_found": True,
        "total_records": total_records,
        "date_range_start": min(fetched_dates).isoformat() if fetched_dates else None,
        "date_range_end": max(fetched_dates).isoformat() if fetched_dates else None,
        "match_ids_seen": total_matches,
        "snapshot_type_counts": dict(type_counts),
        "market_counts": dict(market_counts),
        "timestamp_coverage_pct": round(ts_coverage, 2),
        "pregame_closing_pairs": pairs,
        "pregame_closing_pair_coverage_pct": round(pair_coverage, 2),
    }


def build_collection_manifest(
    timeline_summary: dict,
    paper_only: bool = True,
) -> dict:
    """
    Build the forward collection manifest from timeline summary.
    Validates paper_only=true.
    """
    if paper_only is not True:
        raise ForwardCollectionError(
            "build_collection_manifest: paper_only must be True. "
            "Production planning not permitted via this script."
        )

    ts_cov = timeline_summary.get("timestamp_coverage_pct", 0.0)
    pair_cov = timeline_summary.get("pregame_closing_pair_coverage_pct", 0.0)
    pairs = timeline_summary.get("pregame_closing_pairs", 0)

    ts_status = "PASS" if ts_cov >= MIN_TIMESTAMP_COVERAGE_PCT else "FAIL"
    pair_status = "PASS" if pair_cov >= MIN_PAIR_COVERAGE_PCT else "NEAR_THRESHOLD"
    clv_status = (
        "CLV_ACCUMULATING" if (pair_cov >= MIN_PAIR_COVERAGE_PCT and pairs >= MIN_PAIRS_FOR_CLV)
        else "BELOW_CLV_THRESHOLD"
    )

    return {
        "task": "P8-D",
        "title": "2026 TSL Forward Collection Manifest",
        "plan_date": datetime.now(timezone.utc).isoformat(),
        "paper_only": True,
        "is_live_crawler": False,
        "is_production_write": False,
        "is_dry_run_plan": True,
        "crawler_modified": False,
        "timeline_summary": timeline_summary,
        "snapshot_schedule": SCHEDULE_WINDOWS,
        "target_markets": TARGET_MARKETS,
        "pairing_rule": {
            "definition": "pregame_d2 OR decision (captured_at < game_start) paired with closing_final",
            "closing_window_sec": 3600,
            "pregame_min_sec": 60,
            "minimum_viable_pair": ["pregame_d2", "closing_final"],
        },
        "minimum_coverage_thresholds": {
            "timestamp_coverage_pct": MIN_TIMESTAMP_COVERAGE_PCT,
            "pair_coverage_pct": MIN_PAIR_COVERAGE_PCT,
            "minimum_pairs_for_clv": MIN_PAIRS_FOR_CLV,
        },
        "current_status": {
            "timestamp_coverage": {
                "value": ts_cov,
                "target": MIN_TIMESTAMP_COVERAGE_PCT,
                "status": ts_status,
            },
            "pair_coverage": {
                "value": pair_cov,
                "target": MIN_PAIR_COVERAGE_PCT,
                "status": pair_status,
            },
            "clv_readiness": clv_status,
        },
        "failure_handling": {
            "crawler_failure": "SKIP record; retry on next cron cycle",
            "missing_snapshot_type": "infer from classify_source_type(fetched_at, game_time)",
            "api_timeout": "3 retries, exponential backoff; mark FAILED_SNAPSHOT after max retries",
            "paper_only_guard": "PaperOnlyViolationError raised on paper_only=false",
        },
        "engineering_notes": [
            "TSL crawler must NOT be modified per P8 hard constraints",
            "This script is a read-only dry-run plan — no writes performed",
            "match_id → MLB gamePk bridge required for full CLV analysis (P9 task)",
            "Chinese team name normalization required for gamePk lookup",
        ],
        "annotation": (
            "paper_only=true。此計劃不呼叫任何網路 API。"
            "TSL crawler 未修改。不代表任何實盤獲利能力。"
        ),
    }


def run_forward_collection_plan(output_path: Optional[str] = None) -> dict:
    """Main entrypoint for P8-D dry-run plan."""
    print(DRY_RUN_BANNER)
    print(f"\nReading timeline from: {JSONL_PATH}")

    summary = summarize_existing_timeline(JSONL_PATH)

    print(f"Records found  : {summary['total_records']}")
    print(f"Match IDs      : {summary['match_ids_seen']}")
    print(f"Date range     : {summary['date_range_start']} → {summary['date_range_end']}")
    print(f"TS coverage    : {summary['timestamp_coverage_pct']:.1f}%")
    print(f"Pair coverage  : {summary['pregame_closing_pair_coverage_pct']:.1f}%")
    print(f"Pairs confirmed: {summary['pregame_closing_pairs']}")

    manifest = build_collection_manifest(summary, paper_only=True)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
        print(f"\nManifest written to: {output_path}")

    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="P8-D 2026 TSL Forward Collection Dry-Run — no network, no crawler modification"
    )
    parser.add_argument("--output", default=None, help="Output JSON manifest path")
    args = parser.parse_args()
    run_forward_collection_plan(output_path=args.output)
