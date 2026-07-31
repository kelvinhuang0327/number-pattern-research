#!/usr/bin/env python3
"""MLB Pregame Snapshot Collection — 手動或排程執行入口

功能：
1. 從 TSL BLOB3RD 抓取當前棒球場次
2. 落地至 data/tsl_odds_history.jsonl（含 sport_league / is_pregame / MLB team codes）
3. 產出 MLB-specific 覆蓋率 QA 報告

用法：
    python3 scripts/run_mlb_snapshot_collection.py [--dry-run] [--report-path PATH]

選項：
    --dry-run       抓取資料但不寫入 JSONL，僅顯示結果
    --report-path   QA 報告輸出路徑（預設：data/wbc_backend/reports/mlb_pregame_coverage_report.json）
    --qa-only       不抓取新資料，只重新生成 QA 報告
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

DEFAULT_REPORT_PATH = ROOT / "data" / "wbc_backend" / "reports" / "mlb_pregame_coverage_report.json"
TSL_HISTORY_PATH = ROOT / "data" / "tsl_odds_history.jsonl"


def _count_existing_records() -> int:
    if not TSL_HISTORY_PATH.exists():
        return 0
    count = 0
    for line in TSL_HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            count += 1
    return count


def run_collection(*, dry_run: bool = False) -> dict:
    """Fetch TSL baseball games and save to JSONL history."""
    from data.tsl_crawler_v2 import TSLCrawlerV2

    records_before = _count_existing_records()
    logger.info("TSL JSONL records before fetch: %d", records_before)

    crawler = TSLCrawlerV2(use_mock=False)
    try:
        games = crawler.fetch_baseball_games()
    except Exception as exc:
        logger.error("TSL fetch failed: %s", exc)
        return {"success": False, "error": str(exc), "games": []}

    logger.info("Fetched %d baseball games from TSL", len(games))

    # Classify games
    from data.tsl_snapshot import _detect_sport_league, _is_pregame, _utc_now

    mlb_games = []
    wbc_games = []
    intl_games = []
    pregame_mlb = 0

    for g in games:
        home = str(g.get("homeTeamName", ""))
        away = str(g.get("awayTeamName", ""))
        game_time = str(g.get("gameTime", ""))
        league = _detect_sport_league(home, away)
        fetched_at_now = _utc_now()
        pregame_flag = _is_pregame(fetched_at_now, game_time)

        if league == "MLB":
            mlb_games.append(g)
            if pregame_flag is True:
                pregame_mlb += 1
        elif league == "WBC":
            wbc_games.append(g)
        else:
            intl_games.append(g)

        logger.debug(
            "  %s @ %s | league=%s is_pregame=%s game_time=%s",
            away, home, league, pregame_flag, game_time,
        )

    logger.info(
        "Classification: MLB=%d (pregame=%d) | WBC=%d | INTL=%d",
        len(mlb_games), pregame_mlb, len(wbc_games), len(intl_games),
    )

    if dry_run:
        logger.info("[DRY-RUN] Skipping JSONL write. No data persisted.")
    else:
        records_after = _count_existing_records()
        new_records = records_after - records_before
        logger.info("JSONL records after fetch: %d (+%d)", records_after, new_records)

    return {
        "success": True,
        "total_fetched": len(games),
        "mlb_games": len(mlb_games),
        "mlb_pregame": pregame_mlb,
        "wbc_games": len(wbc_games),
        "intl_games": len(intl_games),
        "dry_run": dry_run,
    }


def run_qa_report(*, report_path: Path) -> dict:
    """Generate MLB pregame coverage QA report from current JSONL history."""
    from wbc_backend.mlb_data.odds_timeline_asset import build_tsl_mlb_pregame_coverage_report

    today = datetime.now(timezone.utc).date().isoformat()
    logger.info("Generating MLB pregame coverage QA report (as_of_date=%s)...", today)

    report = build_tsl_mlb_pregame_coverage_report(
        source_path=TSL_HISTORY_PATH,
        report_path=report_path,
        as_of_date=today,
    )

    t = report["totals"]
    cov = report["pregame_coverage"]
    mv = report["line_movement"]

    logger.info("── MLB Pregame Coverage QA Report ──────────────────────")
    logger.info("  Total MLB games in history:    %d", t["mlb_games"])
    logger.info("  MLB records (total):           %d", t["mlb_records"])
    logger.info("  Pregame records:               %d", t["pregame_records"])
    logger.info("  New records today:             %d", t["new_records_today"])
    logger.info("  Dedup rate:                    %.1f%%", t["dedup_rate"] * 100)
    logger.info("  ── Coverage breakdown ──────────────────────────────")
    logger.info("  0 pregame snapshots:           %d games", cov["games_with_0_pregame_snapshots"])
    logger.info("  1 pregame snapshot:            %d games", cov["games_with_1_pregame_snapshot"])
    logger.info("  2 pregame snapshots:           %d games", cov["games_with_2_pregame_snapshots"])
    logger.info("  3+ pregame snapshots:          %d games", cov["games_with_3plus_pregame_snapshots"])
    logger.info("  Pregame coverage rate:         %.1f%%", cov["pregame_coverage_rate"] * 100)
    logger.info("  Multi-snapshot rate:           %.1f%%", cov["multi_snapshot_rate"] * 100)
    logger.info("  ── Line movement ───────────────────────────────────")
    logger.info("  Games with movement:           %d (%.1f%%)", mv["games_with_movement"], mv["movement_rate"] * 100)
    logger.info("  Data status:                   %s", report["data_status"])
    logger.info("  Report saved to:               %s", report_path)
    logger.info("────────────────────────────────────────────────────────")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="MLB TSL Pregame Snapshot Collection")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not write to JSONL")
    parser.add_argument(
        "--report-path",
        default=str(DEFAULT_REPORT_PATH),
        help="Output path for QA JSON report",
    )
    parser.add_argument("--qa-only", action="store_true", help="Skip fetch, only regenerate QA report")
    args = parser.parse_args()

    report_path = Path(args.report_path)

    if not args.qa_only:
        result = run_collection(dry_run=args.dry_run)
        if not result["success"]:
            logger.error("Collection failed: %s", result.get("error"))
            return 1
        logger.info(
            "Collection result: %d total fetched, %d MLB (%d pregame)",
            result["total_fetched"],
            result["mlb_games"],
            result["mlb_pregame"],
        )
    else:
        logger.info("[QA-ONLY] Skipping fetch, regenerating report from existing JSONL.")

    if not TSL_HISTORY_PATH.exists() or TSL_HISTORY_PATH.stat().st_size == 0:
        logger.warning("No JSONL history found at %s — QA report will show empty state.", TSL_HISTORY_PATH)

    run_qa_report(report_path=report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
