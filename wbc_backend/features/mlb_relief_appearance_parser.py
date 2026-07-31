"""
wbc_backend/features/mlb_relief_appearance_parser.py
=====================================================
Phase 58 — Relief Appearance Parser

功能：
  parse_relief_appearances(game_data) -> list[ReliefAppearance]

資料來源策略：
  - Tier 1（未實作）：MLB StatsAPI boxscore JSON
  - Tier 2（本 Phase）：schedule proxy fallback
    → 使用 ScheduleGameRecord 建立估計出賽記錄
    → estimated = True, source = "schedule_proxy_fallback"

Hard Rules (NEVER violate):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - DIAGNOSTIC_ONLY = True
  - 不可使用 home_win / final_score / game_date 當天資料作為 feature
  - 不可使用當場 box score 結果
  - point_in_time_safe = True（所有 proxy 記錄）
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
FEATURE_VERSION: str = "phase58_relief_parser_v1"

# ─── Proxy Estimation Constants ───────────────────────────────────────────────
# Average MLB game: ~3 relief pitchers, ~3 innings total bullpen usage
# = ~9 outs. Using 9.0 as deterministic proxy.
_PROXY_BULLPEN_OUTS_PER_GAME: float = 9.0
_PROXY_ERA: float = 4.10          # League average ERA proxy
_PROXY_EARNED_RUNS: float = 1.5   # 4.10 ERA × 3.0 IP / 9 ≈ 1.37, rounded to 1.5
_PROXY_APPEARANCES: int = 3       # Typical 3 relief pitchers per game
_PROXY_PITCHER_ID_OFFSET: int = 9_000_000  # Proxy pitcher IDs start here

# ─── Forbidden leakage fields ─────────────────────────────────────────────────
_FORBIDDEN_INPUT_FIELDS: frozenset[str] = frozenset({
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
class ReliefAppearance:
    """
    Single relief pitcher appearance record.

    若 estimated=True，表示此記錄為 schedule-derived proxy，
    不是來自真實 boxscore。
    """
    game_id: str
    game_date: str
    team: str
    pitcher_id: int
    pitcher_name: str
    appearance_order: int        # 1 = starter, 2+ = reliever
    is_starter: bool
    is_reliever: bool
    outs_recorded: float         # IP × 3
    earned_runs: float
    runs_allowed: float
    pitches: int
    leverage_proxy: float        # 0.0 if unavailable
    source: str
    estimated: bool              # True = proxy/estimated; False = real data
    point_in_time_safe: bool
    audit_hash: str
    feature_version: str = FEATURE_VERSION
    # Hard rules
    candidate_patch_created: bool = False
    production_modified: bool = False


def _compute_appearance_hash(
    game_id: str,
    team: str,
    pitcher_id: int,
    source: str,
) -> str:
    payload = f"{game_id}|{team}|{pitcher_id}|{source}|{FEATURE_VERSION}"
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def _parse_from_statsapi_boxscore(game_data: dict) -> list[ReliefAppearance]:
    """
    （未實作）從 MLB StatsAPI boxscore JSON 解析真實中繼投手記錄。

    此函數為 Phase 59 的實作目標。
    當有真實 boxscore cache 時，此函數取代 _parse_from_schedule_proxy。

    boxscore 格式：
      game_data["teams"]["home"]["pitchers"]  →  list of pitcher IDs
      game_data["teams"]["home"]["players"]   →  dict of player stats

    先發判斷：pitcher["pitchOrder"] == 1 或 first pitcher in list
    中繼判斷：pitcher["pitchOrder"] >= 2
    """
    raise NotImplementedError(
        "MLB StatsAPI boxscore parser 未實作。"
        "Phase 59 將實作真實資料解析。"
        "目前使用 schedule proxy fallback。"
    )


def _parse_from_schedule_proxy(
    game_id: str,
    game_date: str,
    home_team: str,
    away_team: str,
) -> list[ReliefAppearance]:
    """
    從賽程資料建立 schedule-proxy 牛棚記錄。

    Proxy 規則：
    - 每隊估計 3 個中繼投手（9 outs / 3 appearances）
    - ERA proxy = 聯盟平均 4.10
    - Leverage proxy = 0.0（未知）
    - estimated = True

    PIT 規則：
    - 此函數建立的記錄代表「過去已完成比賽的牛棚使用估計值」
    - game_id 對應過去比賽（非當場）
    - point_in_time_safe = True（歷史記錄，無未來資訊）
    """
    appearances: list[ReliefAppearance] = []

    for team in (home_team, away_team):
        for i in range(_PROXY_APPEARANCES):
            pitcher_id = (
                _PROXY_PITCHER_ID_OFFSET
                + abs(hash(f"{game_id}_{team}_{i}")) % 100_000
            )
            outs_per_appearance = _PROXY_BULLPEN_OUTS_PER_GAME / _PROXY_APPEARANCES
            er_per_appearance = _PROXY_EARNED_RUNS / _PROXY_APPEARANCES

            appearance = ReliefAppearance(
                game_id=game_id,
                game_date=game_date,
                team=team,
                pitcher_id=pitcher_id,
                pitcher_name=f"PROXY_{team.replace(' ','_')}_{i+1}",
                appearance_order=i + 2,   # 2+ = reliever
                is_starter=False,
                is_reliever=True,
                outs_recorded=round(outs_per_appearance, 2),
                earned_runs=round(er_per_appearance, 2),
                runs_allowed=round(er_per_appearance, 2),
                pitches=int(outs_per_appearance * 5),  # rough proxy
                leverage_proxy=0.0,       # unavailable
                source="schedule_proxy_fallback",
                estimated=True,
                point_in_time_safe=True,
                audit_hash=_compute_appearance_hash(
                    game_id, team, pitcher_id, "schedule_proxy_fallback"
                ),
                feature_version=FEATURE_VERSION,
                candidate_patch_created=False,
                production_modified=False,
            )
            appearances.append(appearance)

    return appearances


def parse_relief_appearances(
    game_data: Any,
    game_id: str = "",
    game_date: str = "",
    home_team: str = "",
    away_team: str = "",
) -> list[ReliefAppearance]:
    """
    解析一場比賽的中繼投手出賽記錄。

    Args:
        game_data: 若為 dict 且含 'teams' key → 嘗試 MLB StatsAPI boxscore 解析
                   否則 → 使用 schedule proxy fallback
        game_id:   比賽唯一識別碼
        game_date: 比賽日期 YYYY-MM-DD
        home_team: 主場球隊名稱
        away_team: 客場球隊名稱

    Returns:
        list[ReliefAppearance]

    注意：
        所有記錄均 point_in_time_safe = True（歷史已完成比賽的回溯記錄）。
        若 estimated=True，表示為估計值，需在 feature 中標記。
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    # 檢查是否傳入 real boxscore
    if isinstance(game_data, dict):
        # 檢查 forbidden 欄位
        for forbidden in _FORBIDDEN_INPUT_FIELDS:
            if forbidden in game_data and game_data[forbidden] is not None:
                logger.warning(
                    "Relief parser: 偵測到禁止欄位 '%s' — 使用 proxy fallback",
                    forbidden,
                )
                break
        else:
            if "teams" in game_data and "home" in game_data.get("teams", {}):
                # Real boxscore format detected — but not yet implemented
                logger.info(
                    "偵測到 StatsAPI boxscore 格式，但 Phase58 尚未實作真實解析"
                    "，回退至 proxy。"
                )

    # 使用 schedule proxy fallback
    if not game_id:
        game_id = f"PROXY_{game_date}_{home_team}_{away_team}".replace(" ", "_")

    return _parse_from_schedule_proxy(
        game_id=game_id,
        game_date=game_date,
        home_team=home_team,
        away_team=away_team,
    )


def parse_relief_appearances_batch(
    games: list[dict],
) -> dict[str, list[ReliefAppearance]]:
    """
    批次解析多場比賽的中繼投手記錄。

    Args:
        games: list of dicts, each with:
               game_id, game_date, home_team, away_team

    Returns:
        dict: game_id -> list[ReliefAppearance]
    """
    result: dict[str, list[ReliefAppearance]] = {}
    for game in games:
        gid = game.get("game_id", "")
        gdate = game.get("game_date", "")
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        appearances = parse_relief_appearances(
            game_data=None,
            game_id=gid,
            game_date=gdate,
            home_team=home,
            away_team=away,
        )
        result[gid] = appearances
    return result
