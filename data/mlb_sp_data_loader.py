"""
MLB Starting Pitcher Data Loader — Phase 52
============================================
讀取 mlb-2025-asplayed.csv 與 baseline JSONL，對齊 game_date + home_team，
回傳每場先發投手姓名記錄。

設計原則：
- 不使用 home_win 作為 match 條件
- 所有 baseline 2,025 rows 必須有輸出（matched=True/False）
- 點對點隔離：不含任何賽後資訊
- stat_source = "historical_proxy"（使用 2025 賽前 FIP 代理值）
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── 路徑設定 ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
_ASPLAYED_CSV = _ROOT / "data" / "mlb_2025" / "mlb-2025-asplayed.csv"
_BASELINE_JSONL = _ROOT / "data" / "mlb_2025" / "derived" / "mlb_2025_per_game_predictions.jsonl"

# ── 常數 ──────────────────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False

# 禁止欄位（leakage guard）
_FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "home_win",
    "final_score",
    "home_score",
    "away_score",
    "result",
    "box_score",
    "post_game_stats",
    "closing_odds_after_game",
    "actual_starter_ip_today",
    "game_score",
    "innings_pitched_today",
})


@dataclass
class StarterMatchRecord:
    """每場比賽的先發投手對齊記錄。"""
    game_id: str
    game_date: str
    home_team: str
    away_team: str
    home_probable_pitcher_name: str
    away_probable_pitcher_name: str
    source: str
    matched: bool
    match_key: str
    fallback_reason: Optional[str]
    audit_hash: str

    # Hard rules
    candidate_patch_created: bool = False
    production_modified: bool = False


def _compute_audit_hash(game_id: str, game_date: str, home_pitcher: str, away_pitcher: str) -> str:
    """計算 audit hash。"""
    payload = f"{game_id}|{game_date}|{home_pitcher}|{away_pitcher}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _normalize_team_name(name: str) -> str:
    """標準化球隊名稱（處理細微差異）。"""
    # 不做任何轉換，直接使用原始名稱
    # 因 asplayed 與 baseline 已確認 100% 對齊
    return name.strip()


def load_asplayed_starters(csv_path: Optional[Path] = None) -> dict[tuple[str, str], dict]:
    """
    讀取 mlb-2025-asplayed.csv，建立 (game_date, home_team) → starter record 映射。

    Returns:
        dict mapping (game_date, home_team) → {away_starter, home_starter, ...}
        Only includes fields that are NOT forbidden (point-in-time safe).
    """
    path = csv_path or _ASPLAYED_CSV
    result: dict[tuple[str, str], dict] = {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 絕不包含任何 forbidden fields
            for bad_field in _FORBIDDEN_FIELDS:
                if bad_field in row:
                    row.pop(bad_field, None)

            game_date = row.get("date", "").strip()
            home_team = _normalize_team_name(row.get("home_team", ""))
            if not game_date or not home_team:
                continue

            key = (game_date, home_team)
            # 若重複，保留第一筆（dedup_policy = first_match）
            if key not in result:
                result[key] = {
                    "away_starter": row.get("away_starter", "").strip(),
                    "home_starter": row.get("home_starter", "").strip(),
                    "away_team": row.get("away_team", "").strip(),
                    "status": row.get("status", "").strip(),
                    "source_file": row.get("source_file", "").strip(),
                }

    logger.info("asplayed 載入完成：%d 筆記錄", len(result))
    return result


def load_baseline_rows(jsonl_path: Optional[Path] = None) -> list[dict]:
    """
    讀取 baseline JSONL，回傳所有行（不過濾）。
    確保不含任何 forbidden fields 副作用。
    """
    path = jsonl_path or _BASELINE_JSONL
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            # Sanity check: forbidden fields 不應出現在預測路徑
            for bad_field in _FORBIDDEN_FIELDS - {"home_win"}:
                # home_win 在 baseline 中是目標變數，允許存在但不使用於 match 條件
                if bad_field in row:
                    logger.warning("Baseline row 含 forbidden field: %s", bad_field)
            rows.append(row)
    logger.info("Baseline JSONL 載入完成：%d 筆記錄", len(rows))
    return rows


def build_starter_match_records(
    baseline_rows: Optional[list[dict]] = None,
    asplayed_map: Optional[dict] = None,
    baseline_path: Optional[Path] = None,
    csv_path: Optional[Path] = None,
) -> list[StarterMatchRecord]:
    """
    主要 API：對齊 baseline JSONL 與 asplayed CSV，建立每場先發投手記錄。

    Args:
        baseline_rows: 已載入的 baseline rows（若 None 則從磁碟讀取）
        asplayed_map:  已載入的 asplayed 映射（若 None 則從磁碟讀取）
        baseline_path: 覆蓋預設 baseline JSONL 路徑
        csv_path:      覆蓋預設 asplayed CSV 路徑

    Returns:
        list[StarterMatchRecord]，長度 = len(baseline_rows)，100% 有記錄
    """
    if baseline_rows is None:
        baseline_rows = load_baseline_rows(baseline_path)
    if asplayed_map is None:
        asplayed_map = load_asplayed_starters(csv_path)

    records: list[StarterMatchRecord] = []
    matched_count = 0
    unmatched_count = 0

    for row in baseline_rows:
        game_id = row.get("game_id", "")
        game_date = row.get("game_date", "")
        home_team = _normalize_team_name(row.get("home_team", ""))
        away_team = _normalize_team_name(row.get("away_team", ""))

        # Match key：不使用 home_win
        match_key = f"{game_date}|{home_team}"
        asp = asplayed_map.get((game_date, home_team))

        if asp:
            home_pitcher = asp.get("home_starter", "")
            away_pitcher = asp.get("away_starter", "")
            matched = bool(home_pitcher or away_pitcher)
            fallback_reason = None if matched else "no_starter_name_in_asplayed"
            matched_count += 1
        else:
            home_pitcher = ""
            away_pitcher = ""
            matched = False
            fallback_reason = "no_asplayed_match"
            unmatched_count += 1

        audit_hash = _compute_audit_hash(game_id, game_date, home_pitcher, away_pitcher)

        records.append(StarterMatchRecord(
            game_id=game_id,
            game_date=game_date,
            home_team=home_team,
            away_team=away_team,
            home_probable_pitcher_name=home_pitcher,
            away_probable_pitcher_name=away_pitcher,
            source="mlb_2025_asplayed",
            matched=matched,
            match_key=match_key,
            fallback_reason=fallback_reason,
            audit_hash=audit_hash,
        ))

    logger.info(
        "starter match 完成：matched=%d, unmatched=%d, total=%d",
        matched_count, unmatched_count, len(records),
    )
    return records


def compute_match_rate(records: list[StarterMatchRecord]) -> float:
    """計算 match rate（0.0–1.0）。"""
    if not records:
        return 0.0
    return sum(1 for r in records if r.matched) / len(records)
