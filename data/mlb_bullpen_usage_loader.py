"""
data/mlb_bullpen_usage_loader.py
=================================
Phase 58 — Bullpen Usage Data Loader

功能：
  load_bullpen_usage_inputs(...) -> BullpenUsageInputBundle

資料來源（本 Phase 使用 schedule proxy fallback）：
  - data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl  (baseline rows)
  - data/mlb_2025/mlb-2025-asplayed.csv                        (schedule / results)

Proxy Fallback 策略：
  由於目前無 MLB StatsAPI boxscore cache，本 loader 使用 asplayed 賽程
  建立 schedule-derived proxy 牛棚記錄：
    - 每場已完成比賽 → 估計 9 個 bullpen outs（3 innings，聯盟平均）
    - B2B 估計來自賽程連續性
    - ERA proxy = 聯盟平均 4.10（無實際 ER/IP 資料）
    - Leverage proxy = 0.0（無 play-by-play 資料）
    - ALL records marked: estimated=True, source="schedule_proxy_fallback"

Hard Rules (NEVER violate):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - DIAGNOSTIC_ONLY = True
  - 不可使用 home_win 作為 feature
  - 不可使用當場 final_score 作為 feature
  - PIT: entry_date < game_date (strict <)
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
FEATURE_VERSION: str = "phase58_bullpen_usage_v1"

# ─── Proxy Estimation Constants ───────────────────────────────────────────────
# Average MLB game uses ~9 bullpen outs (3 innings of relief)
_PROXY_BULLPEN_OUTS_PER_GAME: float = 9.0
# League average bullpen ERA (MLB 2024 reference)
_LEAGUE_AVG_ERA: float = 4.10
# League average bullpen FIP proxy (fallback)
_LEAGUE_AVG_FIP: float = 4.05

# ─── Forbidden leakage fields ─────────────────────────────────────────────────
_FORBIDDEN_FEATURE_FIELDS: frozenset[str] = frozenset({
    "home_win",
    "final_score",
    "home_score",
    "away_score",
    "result",
    "box_score",
    "post_game_stats",
    "closing_odds_after_game",
    "innings_pitched_today",
    "era_after_game",
    "game_score",
    "actual_starter_ip_today",
    "same_game_boxscore",
    "box_score_result",
})


@dataclass
class ScheduleGameRecord:
    """
    Single game record from asplayed schedule.
    賽後分數資料被記錄但不用於建立 feature（PIT 要求）。
    """
    game_date: str           # YYYY-MM-DD
    home_team: str
    away_team: str
    status: str              # Final / Postponed / etc.
    home_starter: str = ""
    away_starter: str = ""
    # 注意：以下分數欄位僅用於 source 識別，不得作為預測 feature
    _home_score_internal: str = ""   # INTERNAL ONLY — never used as feature
    _away_score_internal: str = ""   # INTERNAL ONLY — never used as feature

    @property
    def is_completed(self) -> bool:
        return self.status.lower() in ("final", "completed", "f")


@dataclass
class BullpenUsageInputBundle:
    """載入結果 Bundle，傳遞給 snapshot builder。"""
    baseline_rows: list[dict] = field(default_factory=list)
    schedule_rows: list[ScheduleGameRecord] = field(default_factory=list)
    team_game_history: dict[str, list[ScheduleGameRecord]] = field(default_factory=dict)
    source_summary: dict = field(default_factory=dict)
    audit_hash: str = ""
    loader_version: str = FEATURE_VERSION
    # Hard rules
    candidate_patch_created: bool = False
    production_modified: bool = False
    diagnostic_only: bool = True


def _compute_bundle_hash(
    baseline_count: int,
    schedule_count: int,
    source_tag: str,
) -> str:
    payload = f"{baseline_count}|{schedule_count}|{source_tag}|{FEATURE_VERSION}"
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def _load_baseline_jsonl(path: Path) -> list[dict]:
    """載入 baseline prediction JSONL。"""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    logger.info("Baseline JSONL 載入：%d 筆", len(rows))
    return rows


def _load_asplayed_csv(path: Path) -> list[ScheduleGameRecord]:
    """
    載入 asplayed CSV 並轉換為 ScheduleGameRecord 列表。
    只保留 status=Final 的比賽記錄。
    """
    records: list[ScheduleGameRecord] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game_date = row.get("date", "") or row.get("Date", "")
            home_team = row.get("home_team", "") or row.get("Home", "")
            away_team = row.get("away_team", "") or row.get("Away", "")
            status = row.get("status", "") or row.get("Status", "")
            home_starter = row.get("home_starter", "") or row.get("Home Starter", "")
            away_starter = row.get("away_starter", "") or row.get("Away Starter", "")
            home_score = row.get("home_score", "") or row.get("Home Score", "")
            away_score = row.get("away_score", "") or row.get("Away Score", "")

            if not game_date or not home_team or not away_team:
                continue

            rec = ScheduleGameRecord(
                game_date=game_date,
                home_team=home_team,
                away_team=away_team,
                status=status,
                home_starter=home_starter,
                away_starter=away_starter,
                _home_score_internal=home_score,
                _away_score_internal=away_score,
            )
            records.append(rec)

    logger.info("Asplayed CSV 載入：%d 筆（all statuses）", len(records))
    return records


def _build_team_game_history(
    schedule_rows: list[ScheduleGameRecord],
) -> dict[str, list[ScheduleGameRecord]]:
    """
    建立 team → [ScheduleGameRecord, ...] 的歷史記錄。
    只包含已完成的比賽，按 game_date 升序排列。
    """
    history: dict[str, list[ScheduleGameRecord]] = {}
    for rec in schedule_rows:
        if not rec.is_completed:
            continue
        for team in (rec.home_team, rec.away_team):
            if team not in history:
                history[team] = []
            history[team].append(rec)

    # Sort by date
    for team in history:
        history[team].sort(key=lambda r: r.game_date)

    total_entries = sum(len(v) for v in history.values())
    logger.info(
        "Team game history 建立：%d 球隊，%d 筆記錄",
        len(history),
        total_entries,
    )
    return history


def load_bullpen_usage_inputs(
    baseline_path: Optional[Path] = None,
    asplayed_path: Optional[Path] = None,
) -> BullpenUsageInputBundle:
    """
    載入牛棚使用資料所需的所有輸入。

    Args:
        baseline_path: mlb_2025_per_game_predictions.jsonl 路徑
        asplayed_path: mlb-2025-asplayed.csv 路徑

    Returns:
        BullpenUsageInputBundle

    注意：
        本 loader 使用 schedule proxy fallback（無真實 boxscore data）。
        所有 proxy 特徵標記 estimated=True, source="schedule_proxy_fallback"。
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    _root = Path(__file__).parent.parent

    if baseline_path is None:
        baseline_path = (
            _root / "data" / "mlb_2025" / "derived"
            / "mlb_2025_per_game_predictions.jsonl"
        )
    if asplayed_path is None:
        asplayed_path = _root / "data" / "mlb_2025" / "mlb-2025-asplayed.csv"

    baseline_rows = _load_baseline_jsonl(baseline_path)
    schedule_rows = _load_asplayed_csv(asplayed_path)
    team_game_history = _build_team_game_history(schedule_rows)

    completed_count = sum(1 for r in schedule_rows if r.is_completed)
    source_summary = {
        "baseline_source": str(baseline_path),
        "schedule_source": str(asplayed_path),
        "baseline_row_count": len(baseline_rows),
        "schedule_row_count": len(schedule_rows),
        "schedule_completed_count": completed_count,
        "teams_in_history": len(team_game_history),
        "data_source_mode": "schedule_proxy_fallback",
        "has_real_boxscore": False,
        "proxy_bullpen_outs_per_game": _PROXY_BULLPEN_OUTS_PER_GAME,
        "league_avg_era": _LEAGUE_AVG_ERA,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_version": FEATURE_VERSION,
        "candidate_patch_created": CANDIDATE_PATCH_CREATED,
        "production_modified": PRODUCTION_MODIFIED,
        "diagnostic_only": DIAGNOSTIC_ONLY,
    }

    audit_hash = _compute_bundle_hash(
        baseline_count=len(baseline_rows),
        schedule_count=len(schedule_rows),
        source_tag="schedule_proxy_fallback",
    )

    bundle = BullpenUsageInputBundle(
        baseline_rows=baseline_rows,
        schedule_rows=schedule_rows,
        team_game_history=team_game_history,
        source_summary=source_summary,
        audit_hash=audit_hash,
        loader_version=FEATURE_VERSION,
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
    )

    logger.info(
        "BullpenUsageInputBundle 建立完成："
        " baseline=%d, schedule=%d, completed=%d, teams=%d",
        len(baseline_rows),
        len(schedule_rows),
        completed_count,
        len(team_game_history),
    )
    return bundle
