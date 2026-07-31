"""
MLB 實時資料管道 — P0-2 解決靜態 CSV 問題
==========================================
使用 MLB Stats API（statsapi.mlb.com，完全免費，無需 API Key）
自動抓取今日/歷史賽事資料並轉換為 GameRecord。

功能：
  - fetch_today()：抓取今日比賽（含即時分數）
  - fetch_date_range()：批次抓取指定日期範圍的完成賽事
  - fetch_recent_completed()：抓取最近 N 天的完成場次 → GameRecord 列表
  - 本地 JSON 快取（TTL 可設定，避免重複抓取）
  - 與 mlb_data_loader.py 整合（可合並歷史 CSV + 即時 API 數據）

API Endpoint（免費，無需認證）：
  https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=YYYY-MM-DD
  https://statsapi.mlb.com/api/v1/game/{gamePk}/linescore

資料來源標記：data_source = "mlb_stats_api_live"（通過機構驗證）
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── 設定 ──────────────────────────────────────────────────────────────────────
_API_BASE = "https://statsapi.mlb.com/api/v1"
_CACHE_DIR = Path(__file__).parent / ".live_cache"
_CACHE_TTL_SECONDS = 300   # 5 分鐘快取（進行中比賽）
_FINAL_CACHE_TTL = 86400   # 24 小時快取（完成比賽，不再變動）
_REQUEST_TIMEOUT = 10
_SPORT_ID_MLB = "1"        # MLB sportId
_SPORT_ID_WBC = "51"       # WBC sportId

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ══════════════════════════════════════════════════════════════════════════════
# HTTP 工具
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_json(url: str) -> Optional[dict[str, Any]]:
    """帶錯誤處理的 JSON 抓取"""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        logger.warning("網路錯誤 [%s]: %s", url, e)
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("JSON 解析失敗 [%s]: %s", url, e)
        return None
    except Exception as e:
        logger.warning("未知錯誤 [%s]: %s", url, e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 快取層
# ══════════════════════════════════════════════════════════════════════════════

def _cache_path(key: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace(":", "_")
    return _CACHE_DIR / f"{safe_key}.json"


def _load_cache(key: str, ttl: int) -> Optional[Any]:
    """載入快取（TTL 內有效）"""
    p = _cache_path(key)
    if not p.exists():
        return None
    age = datetime.now().timestamp() - p.stat().st_mtime
    if age > ttl:
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(key: str, data: Any) -> None:
    """儲存到快取"""
    p = _cache_path(key)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.debug("快取寫入失敗: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# API 呼叫
# ══════════════════════════════════════════════════════════════════════════════

def fetch_schedule(
    target_date: str,
    sport_id: str = _SPORT_ID_MLB,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    抓取指定日期的比賽清單。

    Args:
        target_date: "YYYY-MM-DD" 格式日期
        sport_id: "1" = MLB, "51" = WBC
        use_cache: 是否使用快取

    Returns:
        list of game dicts（原始 API 格式）
    """
    cache_key = f"schedule_{sport_id}_{target_date}"
    # 完成日期使用長快取
    is_past = target_date < datetime.now().strftime("%Y-%m-%d")
    ttl = _FINAL_CACHE_TTL if is_past else _CACHE_TTL_SECONDS

    if use_cache:
        cached = _load_cache(cache_key, ttl)
        if cached is not None:
            logger.debug("快取命中: %s", cache_key)
            return cached

    url = f"{_API_BASE}/schedule?sportId={sport_id}&date={target_date}"
    data = _fetch_json(url)
    if not data:
        return []

    games = []
    for date_entry in data.get("dates", []):
        games.extend(date_entry.get("games", []))

    if use_cache:
        _save_cache(cache_key, games)
    return games


def fetch_linescore(game_pk: int, use_cache: bool = True) -> Optional[dict[str, Any]]:
    """
    抓取單場比賽的逐局得分（linescore）。
    用於驗證最終比分。
    """
    cache_key = f"linescore_{game_pk}"
    if use_cache:
        cached = _load_cache(cache_key, _FINAL_CACHE_TTL)
        if cached is not None:
            return cached

    url = f"{_API_BASE}/game/{game_pk}/linescore"
    data = _fetch_json(url)
    if data and use_cache:
        _save_cache(cache_key, data)
    return data


# ══════════════════════════════════════════════════════════════════════════════
# 轉換為 GameRecord（輕量代理指標）
# ══════════════════════════════════════════════════════════════════════════════

def _parse_game_to_dict(game: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    將 MLB Stats API 的 game dict 解析為標準化格式。
    Returns None 若比賽未完成或資料不完整。
    """
    try:
        status = game.get("status", {}).get("detailedState", "")
        if "Final" not in status:
            return None

        game_pk = game.get("gamePk", 0)
        game_date = game.get("gameDate", "")[:10]   # YYYY-MM-DD
        teams = game.get("teams", {})
        home = teams.get("home", {})
        away = teams.get("away", {})

        home_team = home.get("team", {}).get("name", "Unknown")
        away_team = away.get("team", {}).get("name", "Unknown")
        home_score = int(home.get("score", 0) or 0)
        away_score = int(away.get("score", 0) or 0)

        return {
            "game_pk": game_pk,
            "game_date": game_date,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "status": status,
        }
    except (KeyError, TypeError, ValueError):
        return None


def fetch_today_scores(
    sport_id: str = _SPORT_ID_MLB,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    抓取今日所有（含進行中/完成）比賽分數。

    Returns:
        list of {game_date, home_team, away_team, home_score, away_score, status}
    """
    today = datetime.now().strftime("%Y-%m-%d")
    games = fetch_schedule(today, sport_id, use_cache)
    results = []
    for g in games:
        parsed = _parse_game_to_dict(g)
        if parsed is None:
            # 包含進行中的比賽
            try:
                teams = g.get("teams", {})
                home = teams.get("home", {})
                away = teams.get("away", {})
                results.append({
                    "game_date": today,
                    "home_team": home.get("team", {}).get("name", "?"),
                    "away_team": away.get("team", {}).get("name", "?"),
                    "home_score": int(home.get("score", 0) or 0),
                    "away_score": int(away.get("score", 0) or 0),
                    "status": g.get("status", {}).get("detailedState", "Unknown"),
                })
            except Exception:
                pass
        else:
            results.append(parsed)
    return results


def fetch_recent_completed(
    n_days: int = 7,
    sport_id: str = _SPORT_ID_MLB,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    抓取最近 n_days 天內已完成的比賽。

    Returns:
        list of parsed game dicts（只含 Final 狀態）
    """
    results = []
    today = date.today()
    for i in range(n_days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        games = fetch_schedule(d, sport_id, use_cache)
        for g in games:
            parsed = _parse_game_to_dict(g)
            if parsed:
                results.append(parsed)
    results.sort(key=lambda x: x["game_date"])
    logger.info("近 %d 天完成比賽：%d 場", n_days, len(results))
    return results


def fetch_completed_to_game_records(
    n_days: int = 7,
    sport_id: str = _SPORT_ID_MLB,
    use_cache: bool = True,
) -> list:
    """
    抓取最近 n_days 天的完成比賽並轉換為 GameRecord 列表。
    使用 Elo = 1500（無歷史資料時的默認值），其餘代理指標從
    mlb_data_loader.load_mlb_records() 繼承或使用聯盟平均值。

    適合：快速確認 API 管道是否正常工作。
    生產使用：建議先 load_mlb_records()，再用 merge_with_live() 合併。

    Returns:
        list[GameRecord]
    """
    from wbc_backend.evaluation.institutional_backtest import GameRecord

    completed = fetch_recent_completed(n_days, sport_id, use_cache)
    records = []

    for i, g in enumerate(completed):
        home_score = g["home_score"]
        away_score = g["away_score"]
        home_win = 1 if home_score > away_score else 0

        record = GameRecord(
            game_id=f"LIVE_{g['game_date']}_{g.get('game_pk', i):06d}",
            game_date=g["game_date"],
            tournament="MLB_LIVE",
            round_name="REG",
            home_team=g["home_team"],
            away_team=g["away_team"],
            # 無滾動 Elo 時使用聯盟平均（1500）
            home_elo=1500.0,
            away_elo=1500.0,
            home_woba=0.317,  # MLB 2025 聯盟平均
            away_woba=0.317,
            home_fip=4.20,
            away_fip=4.20,
            home_rest_days=1,
            away_rest_days=1,
            home_rsi=80.0,
            away_rsi=80.0,
            market_home_prob=0.50,   # 無賠率時使用 50/50
            ou_line=8.5,             # 2025 MLB 聯盟平均大小分
            actual_home_score=home_score,
            actual_away_score=away_score,
            actual_home_win=home_win,
            actual_total_runs=home_score + away_score,
            data_source="mlb_stats_api_live",
        )
        records.append(record)

    return records


# ══════════════════════════════════════════════════════════════════════════════
# 合併 CSV + API 資料
# ══════════════════════════════════════════════════════════════════════════════

def merge_with_live(
    historical_records: list,
    live_records: list,
    dedup: bool = True,
) -> list:
    """
    合併歷史 CSV GameRecord 與即時 API GameRecord。
    自動去重（by game_date + home_team + away_team）。

    Args:
        historical_records: load_mlb_records() 的結果
        live_records: fetch_completed_to_game_records() 的結果
        dedup: 是否去重（去除日期+球隊重複的場次）

    Returns:
        合併且去重後的 GameRecord 列表（按日期排序）
    """
    seen: set[str] = set()
    merged: list = []

    for r in historical_records + live_records:
        key = f"{r.game_date}_{r.home_team}_{r.away_team}"
        if dedup and key in seen:
            continue
        seen.add(key)
        merged.append(r)

    merged.sort(key=lambda r: r.game_date)
    logger.info(
        "合併完成：歷史 %d + 即時 %d = %d 筆（去重後）",
        len(historical_records), len(live_records), len(merged),
    )
    return merged


# ══════════════════════════════════════════════════════════════════════════════
# CLI 快速測試
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 50)
    print("📡 MLB Stats API 即時資料管道測試")
    print("=" * 50)

    print("\n[1] 今日比賽分數：")
    today_scores = fetch_today_scores()
    if today_scores:
        for g in today_scores[:5]:
            print(f"  {g['status']:12} | {g['away_team']:<25} {g['away_score']} : {g['home_score']}  {g['home_team']}")
    else:
        print("  （今日無比賽或 API 連線失敗）")

    print("\n[2] 近 3 天完成比賽：")
    recent = fetch_recent_completed(n_days=3)
    print(f"  共 {len(recent)} 場完成比賽")
    for g in recent[:3]:
        print(f"  {g['game_date']} | {g['away_team']:<25} {g['away_score']} : {g['home_score']}  {g['home_team']}")

    print("\n[3] 轉換為 GameRecord：")
    recs = fetch_completed_to_game_records(n_days=3)
    print(f"  共 {len(recs)} 筆 GameRecord（data_source='{recs[0].data_source if recs else 'N/A'}'）")

    print("\n✅ 管道測試完成")
