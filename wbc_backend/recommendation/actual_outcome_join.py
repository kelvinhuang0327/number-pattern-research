"""
P7_ACTUAL_OUTCOMES_INGESTION_AND_PNL_RECOMPUTE
actual_outcome_join.py
=======================
將 P5 artifact 與 mlb_odds_2025_real.csv 的實際比賽結果進行 join，
填入 actual_home_win / home_score / away_score 等欄位。

硬性約束：
- 不偽造 actual_home_win
- paper_only 永遠 True
- 不呼叫 live odds API
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict


# ══════════════════════════════════════════════════════════════════════════════
# Dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OutcomeJoinResult:
    game_id: str
    game_date: str
    home_team: str
    away_team: str
    side: str
    actual_home_win: Optional[int]       # 0 or 1
    actual_away_win: Optional[int]       # 0 or 1
    selected_side_win: Optional[int]     # 0 or 1, 依 side 決定
    home_score: Optional[float]
    away_score: Optional[float]
    outcome_join_status: str  # "JOINED" | "MISSING_SCORE" | "DUPLICATE_KEY" | "NO_MATCH" | "INVALID_SCORE"
    outcome_source: str       # "mlb_odds_2025_real_csv"
    paper_only: bool = True


# ══════════════════════════════════════════════════════════════════════════════
# 工具函數
# ══════════════════════════════════════════════════════════════════════════════

# 常見縮寫映射（大寫簡稱 → 全名小寫）
_TEAM_ABBR_MAP: Dict[str, str] = {
    "LAD": "los angeles dodgers",
    "NYY": "new york yankees",
    "BOS": "boston red sox",
    "HOU": "houston astros",
    "ATL": "atlanta braves",
    "LAA": "los angeles angels",
    "CHC": "chicago cubs",
    "CWS": "chicago white sox",
    "CLE": "cleveland guardians",
    "DET": "detroit tigers",
    "KC":  "kansas city royals",
    "KCR": "kansas city royals",
    "MIN": "minnesota twins",
    "BAL": "baltimore orioles",
    "TB":  "tampa bay rays",
    "TBR": "tampa bay rays",
    "TOR": "toronto blue jays",
    "NYM": "new york mets",
    "PHI": "philadelphia phillies",
    "MIL": "milwaukee brewers",
    "STL": "st. louis cardinals",
    "CIN": "cincinnati reds",
    "PIT": "pittsburgh pirates",
    "CHW": "chicago white sox",
    "MIA": "miami marlins",
    "WSN": "washington nationals",
    "WSH": "washington nationals",
    "COL": "colorado rockies",
    "ARI": "arizona diamondbacks",
    "SDP": "san diego padres",
    "SD":  "san diego padres",
    "SFG": "san francisco giants",
    "SF":  "san francisco giants",
    "SEA": "seattle mariners",
    "OAK": "oakland athletics",
    "TEX": "texas rangers",
}


def normalize_team_name(name: str) -> str:
    """正規化隊名：去除空白、小寫、縮寫映射、移除特殊字元"""
    if not name:
        return ""
    stripped = name.strip()
    upper = stripped.upper()
    if upper in _TEAM_ABBR_MAP:
        return _TEAM_ABBR_MAP[upper]
    # 轉小寫、移除多餘空白
    normalized = re.sub(r"\s+", " ", stripped.lower().strip())
    # 移除縮寫句點（st. → st）
    normalized = normalized.replace(".", "")
    return normalized


def derive_actual_home_win(home_score: Optional[float], away_score: Optional[float]) -> Optional[int]:
    """home_score > away_score → 1; away > home → 0; tie or invalid → None"""
    if home_score is None or away_score is None:
        return None
    try:
        h = float(home_score)
        a = float(away_score)
    except (ValueError, TypeError):
        return None
    if h == a:
        return None  # 平局視為無效
    return 1 if h > a else 0


def derive_selected_side_win(side: str, actual_home_win: Optional[int]) -> Optional[int]:
    """依 side 與 actual_home_win 計算 selected_side_win"""
    if actual_home_win is None:
        return None
    bet_side = side.upper() if side else ""
    if bet_side == "HOME":
        return actual_home_win
    elif bet_side == "AWAY":
        return 1 - actual_home_win
    # side 為空（NO_BET）
    return None


def build_join_key(row: dict, key_type: str = "primary") -> Optional[str]:
    """
    key_type = "primary": 使用 game_id（artifact 側）
    key_type = "fallback": 使用 date + normalize(home_team) + normalize(away_team)
    """
    if key_type == "primary":
        gid = row.get("game_id", "")
        return gid if gid else None
    elif key_type == "fallback":
        date = row.get("game_date") or row.get("Date") or row.get("date") or ""
        home = row.get("home_team") or row.get("Home") or row.get("home") or ""
        away = row.get("away_team") or row.get("Away") or row.get("away") or ""
        if not date or not home or not away:
            return None
        # 日期正規化：YYYY-MM-DD
        date_str = str(date).strip()
        return f"{date_str}|{normalize_team_name(str(home))}|{normalize_team_name(str(away))}"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 建立 odds CSV 的 lookup table
# ══════════════════════════════════════════════════════════════════════════════

def _parse_score(val) -> Optional[float]:
    """解析比分，支援整數 / 浮點字串，非數值回傳 None"""
    if val is None:
        return None
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None


def build_odds_lookup(odds_rows: List[dict]) -> Tuple[Dict[str, dict], Dict[str, int]]:
    """
    建立 fallback key → odds_row 的 lookup，同時回傳 duplicate_counts。
    CSV 欄位：Date, Away, Home, Away Score, Home Score
    """
    lookup: Dict[str, dict] = {}
    duplicate_keys: Dict[str, int] = {}

    for row in odds_rows:
        key = build_join_key(
            {
                "game_date": row.get("Date", ""),
                "home_team": row.get("Home", ""),
                "away_team": row.get("Away", ""),
            },
            key_type="fallback",
        )
        if key is None:
            continue
        if key in lookup:
            duplicate_keys[key] = duplicate_keys.get(key, 1) + 1
        else:
            lookup[key] = row

    return lookup, duplicate_keys


# ══════════════════════════════════════════════════════════════════════════════
# P1 — Doubleheader-aware lookup
# ══════════════════════════════════════════════════════════════════════════════

def build_odds_lookup_with_game_number(odds_rows: List[dict]) -> Dict[Tuple[str, str, str, int], dict]:
    """
    建立 (date, home, away, game_number) → odds_row 的 lookup。
    CSV row 在檔案中出現的順序即為當日時間順序（已驗證 Start Time 排序）。
    對單場日 game_number=1；雙重賽兩場分別 game_number=1, 2。
    """
    by_key: Dict[Tuple[str, str, str], List[dict]] = {}
    for row in odds_rows:
        date = str(row.get("Date", "")).strip()
        home = normalize_team_name(str(row.get("Home", "")))
        away = normalize_team_name(str(row.get("Away", "")))
        if not date or not home or not away:
            continue
        k = (date, home, away)
        by_key.setdefault(k, []).append(row)

    lookup: Dict[Tuple[str, str, str, int], dict] = {}
    for (date, home, away), rows in by_key.items():
        for idx, r in enumerate(rows, start=1):
            lookup[(date, home, away, idx)] = r
    return lookup


def group_artifact_by_matchup(artifact_rows: List[dict]) -> Dict[Tuple[str, str, str], List[dict]]:
    """依 (date, normalised home, normalised away) 對 artifact 分組。"""
    g: Dict[Tuple[str, str, str], List[dict]] = {}
    for row in artifact_rows:
        date = str(row.get("game_date", "")).strip()
        home = normalize_team_name(str(row.get("home_team", "")))
        away = normalize_team_name(str(row.get("away_team", "")))
        if not date or not home or not away:
            continue
        g.setdefault((date, home, away), []).append(row)
    return g


def assign_artifact_game_numbers(
    artifact_rows: List[dict],
    csv_group_sizes: Dict[Tuple[str, str, str], int],
) -> Dict[id, Tuple[Optional[int], bool]]:
    """
    對每筆 artifact 推斷 game_number。
    - CSV 該對戰僅 1 場：game_number=1，非 ambiguous
    - CSV 該對戰 N 場、artifact 同分組數量 == N：依 game_id 字典序對應 game_number=1..N，
      此為啟發式推斷（artifact 無 start_time），依 CEO P1 規範標 ambiguous_doubleheader=true，
      不進入 PnL，但仍提供推斷 game_number 供下游審查
    - artifact 同分組數量 != CSV：完全 ambiguous，game_number=None
    回傳 {id(row): (game_number, ambiguous_doubleheader_flag)}
    """
    result: Dict[id, Tuple[Optional[int], bool]] = {}
    art_groups = group_artifact_by_matchup(artifact_rows)
    for key, art_rows in art_groups.items():
        csv_n = csv_group_sizes.get(key, 0)
        if csv_n <= 1:
            # 單場日（或 CSV 沒這場）：game_number=1，非 ambiguous
            for r in art_rows:
                result[id(r)] = (1 if csv_n == 1 else None, False)
        else:
            # CSV 多場
            if len(art_rows) == csv_n:
                # 依 game_id 字典序對應
                ordered = sorted(art_rows, key=lambda r: str(r.get("game_id", "")))
                for idx, r in enumerate(ordered, start=1):
                    # CEO 規範：artifact 無 start_time，game_number 是啟發式推斷 → ambiguous
                    result[id(r)] = (idx, True)
            else:
                # 數量不匹配：完全無法推斷
                for r in art_rows:
                    result[id(r)] = (None, True)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 主 join 函數
# ══════════════════════════════════════════════════════════════════════════════

def join_outcomes_to_artifact(
    artifact_rows: List[dict],
    odds_df_rows: List[dict],
    join_key_order: List[str] = ["primary", "fallback"],
) -> Tuple[List[dict], dict]:
    """
    join P5 artifact 與 odds CSV，回傳 (enriched_rows, summary_dict)

    summary 包含：
        total_rows, joined_rows, missing_outcome_rows, duplicate_key_rows,
        invalid_score_rows, no_match_rows, join_coverage_rate, outcome_source
    """
    # 建立 odds fallback lookup
    fallback_lookup, duplicate_keys = build_odds_lookup(odds_df_rows)

    stats = {
        "total_rows": len(artifact_rows),
        "joined_rows": 0,
        "missing_outcome_rows": 0,
        "duplicate_key_rows": 0,
        "invalid_score_rows": 0,
        "no_match_rows": 0,
        "outcome_source": "mlb_odds_2025_real_csv",
    }

    enriched_rows: List[dict] = []

    for row in artifact_rows:
        enriched = dict(row)
        enriched["paper_only"] = True
        enriched["outcome_source"] = "mlb_odds_2025_real_csv"

        matched_odds_row: Optional[dict] = None
        join_status = "NO_MATCH"

        # 嘗試 fallback join（primary key 在 CSV 中不存在）
        if "fallback" in join_key_order:
            fkey = build_join_key(
                {
                    "game_date": row.get("game_date", ""),
                    "home_team": row.get("home_team", ""),
                    "away_team": row.get("away_team", ""),
                },
                key_type="fallback",
            )
            if fkey and fkey in fallback_lookup:
                if fkey in duplicate_keys:
                    join_status = "DUPLICATE_KEY"
                    stats["duplicate_key_rows"] += 1
                else:
                    matched_odds_row = fallback_lookup[fkey]
                    join_status = "JOINED"
            elif fkey is None:
                join_status = "NO_MATCH"

        if matched_odds_row is not None:
            home_score = _parse_score(matched_odds_row.get("Home Score"))
            away_score = _parse_score(matched_odds_row.get("Away Score"))

            if home_score is None or away_score is None:
                join_status = "MISSING_SCORE"
                stats["missing_outcome_rows"] += 1
                enriched["actual_home_win"] = None
                enriched["actual_away_win"] = None
                enriched["selected_side_win"] = None
                enriched["home_score"] = None
                enriched["away_score"] = None
            else:
                actual_home_win = derive_actual_home_win(home_score, away_score)
                if actual_home_win is None:
                    join_status = "INVALID_SCORE"
                    stats["invalid_score_rows"] += 1
                else:
                    join_status = "JOINED"
                    stats["joined_rows"] += 1

                actual_away_win = (1 - actual_home_win) if actual_home_win is not None else None
                selected_side_win = derive_selected_side_win(
                    row.get("side", row.get("bet_side", "")), actual_home_win
                )

                enriched["actual_home_win"] = actual_home_win
                enriched["actual_away_win"] = actual_away_win
                enriched["selected_side_win"] = selected_side_win
                enriched["home_score"] = home_score
                enriched["away_score"] = away_score
        else:
            if join_status not in ("DUPLICATE_KEY",):
                stats["no_match_rows"] += 1
            enriched["actual_home_win"] = None
            enriched["actual_away_win"] = None
            enriched["selected_side_win"] = None
            enriched["home_score"] = None
            enriched["away_score"] = None

        enriched["outcome_join_status"] = join_status
        enriched_rows.append(enriched)

    # coverage rate = joined / total
    stats["join_coverage_rate"] = round(
        stats["joined_rows"] / max(stats["total_rows"], 1), 4
    )

    return enriched_rows, stats


# ══════════════════════════════════════════════════════════════════════════════
# P1 — v2 主 join 函數：doubleheader-aware
# ══════════════════════════════════════════════════════════════════════════════

def join_outcomes_to_artifact_v2(
    artifact_rows: List[dict],
    odds_df_rows: List[dict],
) -> Tuple[List[dict], dict]:
    """
    Doubleheader-aware join。
    join key = (date, home, away, game_number)
    game_number 依 CSV in-file order（=當日時間順序）對 artifact 依 game_id 字典序對應。
    多場匹配時標 ambiguous_doubleheader=true，並從 PnL 排除（selected_side_win 仍填入以供審計）。

    回傳 (enriched_rows, summary)
    """
    # 建立 (date,home,away,gnum) → odds 與 csv group sizes
    lookup = build_odds_lookup_with_game_number(odds_df_rows)
    csv_group_sizes: Dict[Tuple[str, str, str], int] = {}
    for (d, h, a, _g) in lookup:
        csv_group_sizes[(d, h, a)] = csv_group_sizes.get((d, h, a), 0) + 1

    # 對 artifact 分配 game_number
    gnum_map = assign_artifact_game_numbers(artifact_rows, csv_group_sizes)

    stats = {
        "total_rows": len(artifact_rows),
        "joined_rows": 0,
        "missing_outcome_rows": 0,
        "duplicate_key_rows": 0,
        "invalid_score_rows": 0,
        "no_match_rows": 0,
        "ambiguous_doubleheader_rows": 0,
        "pnl_excluded_rows": 0,
        "outcome_source": "mlb_odds_2025_real_csv",
        "join_key": "(date, home, away, game_number)",
    }

    enriched_rows: List[dict] = []
    for row in artifact_rows:
        enriched = dict(row)
        enriched["paper_only"] = True
        enriched["outcome_source"] = "mlb_odds_2025_real_csv"

        gnum, ambiguous = gnum_map.get(id(row), (None, False))
        enriched["game_number"] = gnum
        enriched["ambiguous_doubleheader"] = ambiguous

        date = str(row.get("game_date", "")).strip()
        home = normalize_team_name(str(row.get("home_team", "")))
        away = normalize_team_name(str(row.get("away_team", "")))

        matched = None
        if gnum is not None and date and home and away:
            matched = lookup.get((date, home, away, gnum))

        if matched is None:
            stats["no_match_rows"] += 1
            enriched["actual_home_win"] = None
            enriched["actual_away_win"] = None
            enriched["selected_side_win"] = None
            enriched["home_score"] = None
            enriched["away_score"] = None
            enriched["outcome_join_status"] = "NO_MATCH"
            enriched["pnl_eligible"] = False
            if ambiguous:
                stats["ambiguous_doubleheader_rows"] += 1
                stats["pnl_excluded_rows"] += 1
            enriched_rows.append(enriched)
            continue

        home_score = _parse_score(matched.get("Home Score"))
        away_score = _parse_score(matched.get("Away Score"))

        if home_score is None or away_score is None:
            stats["missing_outcome_rows"] += 1
            enriched["actual_home_win"] = None
            enriched["actual_away_win"] = None
            enriched["selected_side_win"] = None
            enriched["home_score"] = None
            enriched["away_score"] = None
            enriched["outcome_join_status"] = "MISSING_SCORE"
            enriched["pnl_eligible"] = False
            if ambiguous:
                stats["ambiguous_doubleheader_rows"] += 1
                stats["pnl_excluded_rows"] += 1
            enriched_rows.append(enriched)
            continue

        actual_home_win = derive_actual_home_win(home_score, away_score)
        if actual_home_win is None:
            stats["invalid_score_rows"] += 1
            status = "INVALID_SCORE"
            sel_win = None
        else:
            stats["joined_rows"] += 1
            status = "JOINED"
            sel_win = derive_selected_side_win(
                row.get("side", row.get("bet_side", "")), actual_home_win
            )

        actual_away_win = (1 - actual_home_win) if actual_home_win is not None else None
        enriched["actual_home_win"] = actual_home_win
        enriched["actual_away_win"] = actual_away_win
        enriched["selected_side_win"] = sel_win
        enriched["home_score"] = home_score
        enriched["away_score"] = away_score
        enriched["outcome_join_status"] = status

        # PnL 排除規則：ambiguous_doubleheader 或非 JOINED
        pnl_eligible = (status == "JOINED") and (not ambiguous)
        enriched["pnl_eligible"] = pnl_eligible
        if ambiguous:
            stats["ambiguous_doubleheader_rows"] += 1
            stats["pnl_excluded_rows"] += 1

        enriched_rows.append(enriched)

    stats["join_coverage_rate"] = round(
        stats["joined_rows"] / max(stats["total_rows"], 1), 4
    )
    stats["duplicate_key_rows"] = 0  # v2 不再有 DUPLICATE_KEY
    return enriched_rows, stats
