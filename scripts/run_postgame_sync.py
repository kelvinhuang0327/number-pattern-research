#!/usr/bin/env python3
"""
賽後閉環同步腳本 — Postgame Sync
==================================
讀取 wbc_2026_live_scores.json 中的已完賽比賽，
與 postgame_results.jsonl 比對，對尚未記錄的場次
呼叫 record_postgame_outcome()，完成：

  已完賽結果
    ↓
  record_postgame_outcome()
    ↓ (已存在)
  run_retraining_cycle()        ← 模型權重更新
    ↓
  summarize_market_support_performance()
    ↓
  update_review_report()        ← WBC_Review_Meeting_Latest.md

使用方式：
  python scripts/run_postgame_sync.py            # 同步所有尚未記錄的場次
  python scripts/run_postgame_sync.py --dry-run  # 僅列出待同步場次，不寫入

排程整合：
  由 wbc_backend/scheduler/jobs.py 每 2 小時自動呼叫 sync_completed_games()
  或透過 cron：
    */120 * * * * cd /path/to/Betting-pool && python scripts/run_postgame_sync.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# 讓 scripts/ 目錄可以找到專案根目錄的模組
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wbc_backend.config.settings import AppConfig
from wbc_backend.reporting.postgame_learning import record_postgame_outcome

logger = logging.getLogger(__name__)

_WBC_LIVE_SCORES_PATH = Path("data/wbc_2026_live_scores.json")
_FINAL_STATUSES = {"Final", "Game Over", "Completed Early"}


def _load_completed_games(scores_path: Path) -> list[dict]:
    """從 wbc_2026_live_scores.json 讀取所有已完賽場次。"""
    if not scores_path.exists():
        logger.warning("Live scores file not found: %s", scores_path)
        return []
    payload = json.loads(scores_path.read_text(encoding="utf-8"))
    return [
        g for g in payload.get("games", [])
        if g.get("status") in _FINAL_STATUSES
        and g.get("home_score") is not None
        and g.get("away_score") is not None
    ]


def _load_recorded_game_ids(postgame_jsonl: Path) -> set[str]:
    """從 postgame_results.jsonl 讀取已記錄的 game_id 集合。"""
    if not postgame_jsonl.exists():
        return set()
    ids: set[str] = set()
    for raw in postgame_jsonl.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
            ids.add(str(row.get("game_id", "")))
        except json.JSONDecodeError:
            continue
    return ids


def sync_completed_games(
    *,
    config: AppConfig | None = None,
    scores_path: Path | None = None,
    dry_run: bool = False,
) -> list[dict]:
    """
    同步已完賽場次至 postgame_results.jsonl。

    Returns:
        list of recorded game outcome dicts (only newly synced ones).
    """
    config = config or AppConfig()
    scores_path = scores_path or _WBC_LIVE_SCORES_PATH

    completed = _load_completed_games(scores_path)
    recorded_ids = _load_recorded_game_ids(Path(config.sources.postgame_results_jsonl))

    pending = [g for g in completed if str(g.get("game_id", "")) not in recorded_ids]

    if not pending:
        logger.info("Postgame sync: no new completed games to record.")
        return []

    logger.info("Postgame sync: %d new completed game(s) found.", len(pending))

    if dry_run:
        for g in pending:
            logger.info(
                "[DRY-RUN] Would record: %s — %s %s vs %s %s",
                g.get("game_id"),
                g.get("away"), g.get("away_score"),
                g.get("home"), g.get("home_score"),
            )
        return pending

    synced: list[dict] = []
    for g in pending:
        game_id = str(g.get("game_id", ""))
        home_team = str(g.get("home", ""))
        away_team = str(g.get("away", ""))
        home_score = int(g.get("home_score", 0))
        away_score = int(g.get("away_score", 0))
        try:
            result = record_postgame_outcome(
                config=config,
                game_id=game_id,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                source_urls=[],
                notes=[f"auto-synced from {scores_path}"],
            )
            synced.append(result)
            applied = result.get("learning", {}).get("applied", False)
            logger.info(
                "Recorded %s (%s %d - %s %d) | learning_applied=%s",
                game_id, away_team, away_score, home_team, home_score, applied,
            )
        except Exception as exc:
            logger.error("Failed to record game %s: %s", game_id, exc)

    return synced


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    parser = argparse.ArgumentParser(description="WBC 賽後閉環同步")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="僅列出待同步場次，不寫入",
    )
    parser.add_argument(
        "--scores",
        default=str(_WBC_LIVE_SCORES_PATH),
        help="wbc_2026_live_scores.json 路徑",
    )
    args = parser.parse_args()

    config = AppConfig()
    synced = sync_completed_games(
        config=config,
        scores_path=Path(args.scores),
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(json.dumps({"dry_run": True, "pending_count": len(synced)}, ensure_ascii=False))
    else:
        print(json.dumps({"synced_count": len(synced)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
