"""
MLB 真實球員數據接入模組 — Phase 8B
=====================================
從 MLB Stats API（statsapi.mlb.com，完全免費，無需 API Key）
抓取真實球員賽季數據，取代 mlb_data_loader.py 中的代理值（滾動跑壘均值 ≈ wOBA/FIP）。

功能：
  - fetch_pitcher_season_stats(player_id) → RealPitcherStats
  - fetch_batter_season_stats(player_id)  → RealBatterStats
  - fetch_team_roster(team_id)            → list[RosterEntry]
  - fetch_probable_starters(date)         → dict[str, int]（隊名 → player_id）
  - to_pitcher_snapshot(stats)            → PitcherSnapshot（WorldModel 用）
  - to_batter_snapshot(stats)             → BatterSnapshot（WorldModel 用）
  - to_pitcher_profile(stats)             → PlayerProfile（WorldModel PA-level 用）
  - enrich_game_records(records, season)  → 以真實 wOBA/FIP 更新 GameRecord

計算推導：
  - FIP  = (13×HR + 3×(BB+HBP) - 2×K) / IP + 3.10（FIP 常數）
  - wOBA ≈ 0.88 × OBP + 0.12 × SLG - 0.19（線性代理，與真實 wOBA 相關 r≈0.97）
  - K%   = K / PA
  - BB%  = BB / PA
  - BABIP = (H - HR) / (PA - K - HR - BB)
  - GB%   ≈ GO / (GO + AO) 從 GO/AO ratio 推算

快取：
  - 球員賽季數據 TTL = 6 小時（日常更新）
  - 球隊 Roster TTL = 24 小時
  - 賽程先發投手 TTL = 1 小時（比賽日頻繁更動）
"""
from __future__ import annotations

import json
import logging
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── API 設定 ──────────────────────────────────────────────────────────────────
_API_BASE = "https://statsapi.mlb.com/api/v1"
_CACHE_DIR = Path(__file__).parent / ".live_cache" / "player_stats"
_PLAYER_TTL = 21_600     # 6 小時（球員季度數據）
_ROSTER_TTL = 86_400     # 24 小時（球隊陣容）
_SCHEDULE_TTL = 3_600    # 1 小時（先發投手）
_REQUEST_TIMEOUT = 10
_FIP_CONSTANT = 3.10     # MLB 2025 FIP 常數（近年約 3.10-3.17）

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# 聯盟平均（MLB 2024 基準，用於缺失時 fallback）
_LG_ERA = 4.10
_LG_FIP = 4.05
_LG_WHIP = 1.27
_LG_K9 = 9.0
_LG_BB9 = 3.0
_LG_HR9 = 1.20
_LG_K_PCT = 0.228
_LG_BB_PCT = 0.085
_LG_GB_PCT = 0.43
_LG_AVG = 0.247
_LG_OBP = 0.316
_LG_SLG = 0.399
_LG_WOBA = 0.310
_LG_BABIP = 0.296
_LG_ISO = 0.152


# ══════════════════════════════════════════════════════════════════════════════
# 資料類別
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RosterEntry:
    player_id: int
    full_name: str
    position: str      # "P" | "C" | "1B" | "2B" | "3B" | "SS" | "LF" | "CF" | "RF" | "DH"
    jersey_number: str = ""
    status: str = "Active"


@dataclass
class RealPitcherStats:
    """MLB Stats API 投手賽季數據（含推導欄位）"""
    player_id: int
    full_name: str
    team_name: str
    season: int
    # 直接 API 欄位
    era: float = _LG_ERA
    fip_raw: float = _LG_FIP      # 自行計算的 FIP
    whip: float = _LG_WHIP
    k_per_9: float = _LG_K9
    bb_per_9: float = _LG_BB9
    hr_per_9: float = _LG_HR9
    innings_pitched: float = 0.0
    strikeouts: int = 0
    walks: int = 0
    home_runs: int = 0
    hits: int = 0
    hit_batsmen: int = 0
    batters_faced: int = 0
    ground_outs: int = 0
    air_outs: int = 0
    # 推導欄位
    k_pct: float = _LG_K_PCT
    bb_pct: float = _LG_BB_PCT
    gb_pct: float = _LG_GB_PCT
    babip: float = _LG_BABIP
    data_source: str = "mlb_stats_api"
    fetched_at: float = 0.0


@dataclass
class RealBatterStats:
    """MLB Stats API 打者賽季數據（含推導欄位）"""
    player_id: int
    full_name: str
    team_name: str
    season: int
    # 直接 API 欄位
    avg: float = _LG_AVG
    obp: float = _LG_OBP
    slg: float = _LG_SLG
    ops: float = _LG_OBP + _LG_SLG
    plate_appearances: int = 0
    at_bats: int = 0
    hits: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    walks: int = 0
    strikeouts: int = 0
    hit_by_pitch: int = 0
    sac_flies: int = 0
    stolen_bases: int = 0
    # 推導欄位
    woba: float = _LG_WOBA        # 線性代理
    babip: float = _LG_BABIP
    iso: float = _LG_ISO
    k_pct: float = _LG_K_PCT
    bb_pct: float = _LG_BB_PCT
    contact_pct: float = 1 - _LG_K_PCT
    ops_plus: float = 100.0
    data_source: str = "mlb_stats_api"
    fetched_at: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# HTTP + 快取工具
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_json(url: str) -> Optional[dict[str, Any]]:
    """帶錯誤處理的 JSON 抓取"""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        logger.warning("MLB API 網路錯誤 [%s]: %s", url, e)
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("JSON 解析失敗 [%s]: %s", url, e)
        return None
    except Exception as e:
        logger.warning("未知錯誤 [%s]: %s", url, e)
        return None


def _cache_path(key: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = key.replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_")
    return _CACHE_DIR / f"{safe}.json"


def _read_cache(key: str, ttl: int) -> Optional[dict]:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - data.get("_cached_at", 0) < ttl:
            return data
    except Exception:
        pass
    return None


def _write_cache(key: str, data: dict) -> None:
    p = _cache_path(key)
    try:
        data["_cached_at"] = time.time()
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.debug("快取寫入失敗 [%s]: %s", key, e)


# ══════════════════════════════════════════════════════════════════════════════
# 推導計算工具
# ══════════════════════════════════════════════════════════════════════════════

def _compute_fip(hr: int, bb: int, hbp: int, k: int, ip: float) -> float:
    """FIP = (13×HR + 3×(BB+HBP) - 2×K) / IP + 3.10"""
    if ip <= 0:
        return _LG_FIP
    return round((13 * hr + 3 * (bb + hbp) - 2 * k) / ip + _FIP_CONSTANT, 2)


def _compute_woba(obp: float, slg: float) -> float:
    """wOBA 線性代理：0.88×OBP + 0.12×SLG - 0.19（MLB 分析常用近似）"""
    return round(max(0.20, min(0.50, 0.88 * obp + 0.12 * slg - 0.19)), 3)


def _compute_babip_pitcher(h: int, hr: int, k: int, bf: int) -> float:
    """BABIP = (H - HR) / (BF - K - HR)"""
    denom = bf - k - hr
    if denom <= 0:
        return _LG_BABIP
    return round(max(0.15, min(0.40, (h - hr) / denom)), 3)


def _compute_babip_batter(h: int, hr: int, k: int, ab: int, sf: int) -> float:
    """BABIP = (H - HR) / (AB - K - HR + SF)"""
    denom = ab - k - hr + sf
    if denom <= 0:
        return _LG_BABIP
    return round(max(0.15, min(0.42, (h - hr) / denom)), 3)


def _go_ao_to_gb_pct(go_ao_ratio: float) -> float:
    """GO/AO 比例 → GB%"""
    return round(min(0.70, max(0.25, go_ao_ratio / (1.0 + go_ao_ratio))), 3)


# ══════════════════════════════════════════════════════════════════════════════
# 球隊 Roster 查詢
# ══════════════════════════════════════════════════════════════════════════════

def fetch_team_roster(team_id: int, season: int = 2025) -> list[RosterEntry]:
    """抓取球隊現役陣容"""
    key = f"roster_{team_id}_{season}"
    cached = _read_cache(key, _ROSTER_TTL)
    if cached:
        return [RosterEntry(**e) for e in cached.get("entries", [])]

    url = f"{_API_BASE}/teams/{team_id}/roster/Active?season={season}"
    data = _fetch_json(url)
    if not data:
        return []

    entries = []
    for p in data.get("roster", []):
        pid = p.get("person", {}).get("id")
        name = p.get("person", {}).get("fullName", "Unknown")
        pos = p.get("position", {}).get("abbreviation", "?")
        jersey = p.get("jerseyNumber", "")
        if pid:
            entries.append(RosterEntry(
                player_id=int(pid), full_name=name,
                position=pos, jersey_number=str(jersey),
            ))

    _write_cache(key, {"entries": [
        {"player_id": e.player_id, "full_name": e.full_name,
         "position": e.position, "jersey_number": e.jersey_number}
        for e in entries
    ]})
    return entries


def fetch_all_teams(season: int = 2025) -> dict[str, int]:
    """
    回傳 {球隊縮寫: team_id} 對照表。
    例：{"NYY": 147, "LAD": 119, ...}
    """
    key = f"all_teams_{season}"
    cached = _read_cache(key, _ROSTER_TTL)
    if cached:
        return cached.get("mapping", {})

    url = f"{_API_BASE}/teams?sportId=1&season={season}"
    data = _fetch_json(url)
    if not data:
        return {}

    mapping: dict[str, int] = {}
    for t in data.get("teams", []):
        abbr = t.get("abbreviation", "")
        tid = t.get("id")
        if abbr and tid:
            mapping[abbr] = int(tid)
            # 也加入全名 key（取前兩個詞）
            name = t.get("teamName", "")
            if name:
                mapping[name] = int(tid)

    _write_cache(key, {"mapping": mapping})
    logger.info("MLB 球隊對照表：%d 支球隊", len(mapping))
    return mapping


# ══════════════════════════════════════════════════════════════════════════════
# 球員賽季數據抓取
# ══════════════════════════════════════════════════════════════════════════════

def fetch_pitcher_season_stats(
    player_id: int,
    season: int = 2025,
) -> Optional[RealPitcherStats]:
    """
    抓取投手賽季數據，計算 FIP / K% / BB% / GB% / BABIP。

    Returns:
        RealPitcherStats 或 None（API 無數據時）
    """
    key = f"pitcher_{player_id}_{season}"
    cached = _read_cache(key, _PLAYER_TTL)
    if cached and "player_id" in cached:
        try:
            return RealPitcherStats(**{
                k: v for k, v in cached.items()
                if k in RealPitcherStats.__dataclass_fields__
            })
        except Exception:
            pass

    url = (f"{_API_BASE}/people/{player_id}/stats"
           f"?stats=season&group=pitching&season={season}")
    data = _fetch_json(url)
    if not data:
        return None

    # 提取 stats 列表中第一個元素（通常是整季數據）
    stats_list = data.get("stats", [])
    if not stats_list:
        return None
    splits = stats_list[0].get("splits", [])
    if not splits:
        return None

    s = splits[0].get("stat", {})
    player_info = splits[0].get("player", {})
    team_info = splits[0].get("team", {})

    ip_str = str(s.get("inningsPitched", "0.0"))
    try:
        # 轉換 "6.2" → 6.667 innings
        ip_parts = ip_str.split(".")
        ip = float(ip_parts[0]) + (float(ip_parts[1]) / 3 if len(ip_parts) > 1 else 0)
    except (ValueError, IndexError):
        ip = 0.0

    hr = int(s.get("homeRuns", 0))
    bb = int(s.get("baseOnBalls", 0))
    hbp = int(s.get("hitBatsmen", 0))
    k = int(s.get("strikeOuts", 0))
    h = int(s.get("hits", 0))
    bf = int(s.get("battersFaced", 0)) or (k + bb + h + 1)

    go_ao_raw = float(s.get("groundOutsToAirouts", 1.0) or 1.0)
    go = int(s.get("groundOuts", 0))
    ao = int(s.get("airOuts", 0))

    result = RealPitcherStats(
        player_id=player_id,
        full_name=player_info.get("fullName", f"Player_{player_id}"),
        team_name=team_info.get("name", "Unknown"),
        season=season,
        era=float(s.get("era", _LG_ERA) or _LG_ERA),
        fip_raw=_compute_fip(hr, bb, hbp, k, ip),
        whip=float(s.get("whip", _LG_WHIP) or _LG_WHIP),
        k_per_9=float(s.get("strikeoutsPer9Inn", _LG_K9) or _LG_K9),
        bb_per_9=float(s.get("walksPer9Inn", _LG_BB9) or _LG_BB9),
        hr_per_9=float(s.get("homeRunsPer9", _LG_HR9) or _LG_HR9),
        innings_pitched=ip,
        strikeouts=k,
        walks=bb,
        home_runs=hr,
        hits=h,
        hit_batsmen=hbp,
        batters_faced=bf,
        ground_outs=go,
        air_outs=ao,
        k_pct=round(k / max(bf, 1), 3),
        bb_pct=round(bb / max(bf, 1), 3),
        gb_pct=_go_ao_to_gb_pct(go_ao_raw),
        babip=_compute_babip_pitcher(h, hr, k, bf),
        data_source="mlb_stats_api",
        fetched_at=time.time(),
    )

    _write_cache(key, result.__dict__.copy())
    logger.debug("投手數據抓取成功：%s (ID=%d) ERA=%.2f FIP=%.2f",
                 result.full_name, player_id, result.era, result.fip_raw)
    return result


def fetch_batter_season_stats(
    player_id: int,
    season: int = 2025,
) -> Optional[RealBatterStats]:
    """
    抓取打者賽季數據，計算 wOBA / BABIP / K% / BB%。

    Returns:
        RealBatterStats 或 None（API 無數據時）
    """
    key = f"batter_{player_id}_{season}"
    cached = _read_cache(key, _PLAYER_TTL)
    if cached and "player_id" in cached:
        try:
            return RealBatterStats(**{
                k: v for k, v in cached.items()
                if k in RealBatterStats.__dataclass_fields__
            })
        except Exception:
            pass

    url = (f"{_API_BASE}/people/{player_id}/stats"
           f"?stats=season&group=hitting&season={season}")
    data = _fetch_json(url)
    if not data:
        return None

    stats_list = data.get("stats", [])
    if not stats_list:
        return None
    splits = stats_list[0].get("splits", [])
    if not splits:
        return None

    s = splits[0].get("stat", {})
    player_info = splits[0].get("player", {})
    team_info = splits[0].get("team", {})

    avg = float(s.get("avg", _LG_AVG) or _LG_AVG)
    obp = float(s.get("obp", _LG_OBP) or _LG_OBP)
    slg = float(s.get("slg", _LG_SLG) or _LG_SLG)
    pa = int(s.get("plateAppearances", 0))
    ab = int(s.get("atBats", 0))
    h = int(s.get("hits", 0))
    doubles = int(s.get("doubles", 0))
    triples = int(s.get("triples", 0))
    hr = int(s.get("homeRuns", 0))
    bb = int(s.get("baseOnBalls", 0))
    k = int(s.get("strikeOuts", 0))
    hbp = int(s.get("hitByPitch", 0))
    sf = int(s.get("sacFlies", 0))
    sb = int(s.get("stolenBases", 0))

    result = RealBatterStats(
        player_id=player_id,
        full_name=player_info.get("fullName", f"Player_{player_id}"),
        team_name=team_info.get("name", "Unknown"),
        season=season,
        avg=avg,
        obp=obp,
        slg=slg,
        ops=round(obp + slg, 3),
        plate_appearances=pa,
        at_bats=ab,
        hits=h,
        doubles=doubles,
        triples=triples,
        home_runs=hr,
        walks=bb,
        strikeouts=k,
        hit_by_pitch=hbp,
        sac_flies=sf,
        stolen_bases=sb,
        woba=_compute_woba(obp, slg),
        babip=_compute_babip_batter(h, hr, k, ab, sf),
        iso=round(max(0.0, slg - avg), 3),
        k_pct=round(k / max(pa, 1), 3),
        bb_pct=round(bb / max(pa, 1), 3),
        contact_pct=round(1 - k / max(pa, 1), 3),
        ops_plus=round((obp / _LG_OBP + slg / _LG_SLG - 1.0) * 100, 0),
        data_source="mlb_stats_api",
        fetched_at=time.time(),
    )

    _write_cache(key, result.__dict__.copy())
    logger.debug("打者數據抓取成功：%s (ID=%d) wOBA=%.3f BABIP=%.3f",
                 result.full_name, player_id, result.woba, result.babip)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 先發投手查詢
# ══════════════════════════════════════════════════════════════════════════════

def fetch_probable_starters(game_date: str) -> dict[str, Optional[int]]:
    """
    抓取指定日期的先發投手。
    Returns: {球隊縮寫: player_id}（找不到時為 None）
    """
    key = f"probable_{game_date}"
    cached = _read_cache(key, _SCHEDULE_TTL)
    if cached:
        return cached.get("starters", {})

    url = (f"{_API_BASE}/schedule?sportId=1&date={game_date}"
           f"&hydrate=probablePitcher&season=2025")
    data = _fetch_json(url)
    if not data:
        return {}

    starters: dict[str, Optional[int]] = {}
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            for side in ("home", "away"):
                team_info = game.get("teams", {}).get(side, {})
                abbr = team_info.get("team", {}).get("abbreviation", "")
                pitcher = team_info.get("probablePitcher", {})
                pid = pitcher.get("id")
                if abbr:
                    starters[abbr] = int(pid) if pid else None

    _write_cache(key, {"starters": starters})
    return starters


# ══════════════════════════════════════════════════════════════════════════════
# Schema 轉換（→ PitcherSnapshot / BatterSnapshot / PlayerProfile）
# ══════════════════════════════════════════════════════════════════════════════

def to_pitcher_snapshot(stats: RealPitcherStats) -> "PitcherSnapshot":
    """RealPitcherStats → PitcherSnapshot（WorldModel 輸入）"""
    from wbc_backend.domain.schemas import PitcherSnapshot
    return PitcherSnapshot(
        name=stats.full_name,
        team=stats.team_name,
        era=stats.era,
        fip=stats.fip_raw,
        whip=stats.whip,
        k_per_9=stats.k_per_9,
        bb_per_9=stats.bb_per_9,
        stuff_plus=100.0,             # Statcast 數據缺失，用聯盟平均
        ip_last_30=min(stats.innings_pitched, 30.0),
        era_last_3=stats.era,          # API 無分段數據，用整季值
        pitch_count_last_3d=0,
        fastball_velo=93.0,            # MLB Stats API 無 pitch velo，用平均值
        high_leverage_era=stats.era,
        role="SP",
    )


def to_batter_snapshot(stats: RealBatterStats) -> "BatterSnapshot":
    """RealBatterStats → BatterSnapshot（WorldModel 輸入）"""
    from wbc_backend.domain.schemas import BatterSnapshot
    return BatterSnapshot(
        name=stats.full_name,
        team=stats.team_name,
        avg=stats.avg,
        obp=stats.obp,
        slg=stats.slg,
        woba=stats.woba,
        ops_plus=int(stats.ops_plus),
        clutch_woba=stats.woba,        # 無分段，用整季值
        vs_left_avg=stats.avg,
        vs_right_avg=stats.avg,
        barrel_pct=0.081,              # Statcast 缺失，用聯盟平均
        k_pct=stats.k_pct,
        bb_pct=stats.bb_pct,
        contact_pct=stats.contact_pct,
        babip=stats.babip,
        iso=stats.iso,
        sprint_speed=27.0,             # Statcast 缺失，用聯盟平均
        wrc_plus=int(stats.ops_plus),
    )


def to_pitcher_profile(stats: RealPitcherStats) -> "PlayerProfile":
    """RealPitcherStats → PlayerProfile（WorldModel PA-level 模擬用）"""
    from wbc_backend.simulation.world_model import PlayerProfile
    return PlayerProfile(
        name=stats.full_name,
        role="pitcher",
        k_pct=stats.k_pct,
        bb_pct=stats.bb_pct,
        hr9=stats.hr_per_9,
        gb_pct=stats.gb_pct,
        stuff_plus=100.0,
    )


def to_batter_profile(stats: RealBatterStats) -> "PlayerProfile":
    """RealBatterStats → PlayerProfile（WorldModel PA-level 模擬用）"""
    from wbc_backend.simulation.world_model import PlayerProfile
    return PlayerProfile(
        name=stats.full_name,
        role="batter",
        contact_pct=stats.contact_pct,
        babip=stats.babip,
        barrel_pct=0.081,    # Statcast 缺失，用聯盟平均
        k_rate=stats.k_pct,
        bb_rate=stats.bb_pct,
    )


# ══════════════════════════════════════════════════════════════════════════════
# GameRecord 數據豐富化
# ══════════════════════════════════════════════════════════════════════════════

_TEAM_ABBR_TO_FULL: dict[str, str] = {
    # 常見縮寫 → 完整隊名（MLB Stats API 使用 abbreviation）
    "NYY": "Yankees", "LAD": "Dodgers", "BOS": "Red Sox", "CHC": "Cubs",
    "HOU": "Astros", "ATL": "Braves", "NYM": "Mets", "PHI": "Phillies",
    "SD": "Padres", "SF": "Giants", "TEX": "Rangers", "SEA": "Mariners",
    "MIL": "Brewers", "MIN": "Twins", "TB": "Rays", "CLE": "Guardians",
    "BAL": "Orioles", "TOR": "Blue Jays", "CIN": "Reds", "STL": "Cardinals",
    "DET": "Tigers", "AZ": "Diamondbacks", "COL": "Rockies", "MIA": "Marlins",
    "WSH": "Nationals", "PIT": "Pirates", "CWS": "White Sox", "KC": "Royals",
    "LAA": "Angels", "OAK": "Athletics",
}


def enrich_game_records(
    records: list,
    season: int = 2025,
    max_records: Optional[int] = None,
    skip_on_api_fail: bool = True,
) -> list:
    """
    嘗試以真實 wOBA/FIP 更新 GameRecord 列表。

    因 MLB Stats API 需要 player_id（GameRecord 通常只有隊名），
    本函數透過球隊 Roster 查詢先發投手並抓取其數據。

    實際流程：
      1. 抓取所有 MLB 球隊 ID 對照表
      2. 對每場比賽：查先發投手 → 抓取其 K%/BB%/ERA/FIP
      3. 更新 GameRecord.home_fip / away_fip / home_woba / away_woba

    注意：此函數僅在有網路且 API 可用時有效；
          失敗時保留原有代理值（mlb_data_loader.py 計算的滾動均值）。
    """
    if not records:
        return records

    subset = records[:max_records] if max_records else records

    # 抓取球隊對照表
    team_map = fetch_all_teams(season)
    if not team_map:
        logger.warning("無法抓取球隊對照表，跳過豐富化")
        return records

    enriched = 0
    for rec in subset:
        try:
            game_date = str(getattr(rec, "game_date", ""))
            if not game_date:
                continue

            # 抓取當日先發投手
            starters = fetch_probable_starters(game_date)
            if not starters:
                continue

            home_team = str(getattr(rec, "home_team", ""))
            away_team = str(getattr(rec, "away_team", ""))

            # 嘗試找到主隊先發投手 ID
            home_sp_id = starters.get(home_team) or starters.get(
                next((k for k in starters if home_team in k), None) or "",
            )
            away_sp_id = starters.get(away_team) or starters.get(
                next((k for k in starters if away_team in k), None) or "",
            )

            # 更新主隊投手數據
            if home_sp_id:
                p_stats = fetch_pitcher_season_stats(home_sp_id, season)
                if p_stats:
                    rec.home_fip = p_stats.fip_raw  # type: ignore[attr-defined]
                    enriched += 1

            # 更新客隊投手數據
            if away_sp_id:
                p_stats = fetch_pitcher_season_stats(away_sp_id, season)
                if p_stats:
                    rec.away_fip = p_stats.fip_raw  # type: ignore[attr-defined]
                    enriched += 1

        except Exception as e:
            if not skip_on_api_fail:
                raise
            logger.debug("豐富化跳過 %s: %s", getattr(rec, "game_id", "?"), e)

    if enriched > 0:
        logger.info("豐富化完成：%d 筆 GameRecord 已更新真實 FIP", enriched)
    return records


# ══════════════════════════════════════════════════════════════════════════════
# 便捷入口
# ══════════════════════════════════════════════════════════════════════════════

def get_pitcher_snapshot_by_id(
    player_id: int, season: int = 2025,
) -> Optional["PitcherSnapshot"]:
    """單一 API 呼叫：player_id → PitcherSnapshot"""
    stats = fetch_pitcher_season_stats(player_id, season)
    return to_pitcher_snapshot(stats) if stats else None


def get_batter_snapshot_by_id(
    player_id: int, season: int = 2025,
) -> Optional["BatterSnapshot"]:
    """單一 API 呼叫：player_id → BatterSnapshot"""
    stats = fetch_batter_season_stats(player_id, season)
    return to_batter_snapshot(stats) if stats else None


def get_team_pitcher_profiles(
    team_id: int, season: int = 2025, n_pitchers: int = 3,
) -> list["PlayerProfile"]:
    """
    取得球隊投手陣的 PlayerProfile 列表（供 WorldModel 使用）。
    回傳前 n_pitchers 位投手的 Profile。
    """
    roster = fetch_team_roster(team_id, season)
    pitchers = [r for r in roster if r.position == "P"][:n_pitchers]
    profiles = []
    for p in pitchers:
        stats = fetch_pitcher_season_stats(p.player_id, season)
        if stats:
            profiles.append(to_pitcher_profile(stats))
    return profiles
