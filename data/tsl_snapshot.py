from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TSL_SNAPSHOT_PATH = ROOT / "data" / "tsl_odds_snapshot.json"
TSL_HISTORY_PATH = ROOT / "data" / "tsl_odds_history.jsonl"
TAIPEI_TZ = timezone(timedelta(hours=8))

TEAM_NAME_TO_CODE = {
    "中華台北": "TPE",
    "澳洲": "AUS",
    "捷克": "CZE",
    "韓國": "KOR",
    "南韓": "KOR",
    "日本": "JPN",
    "古巴": "CUB",
    "巴拿馬": "PAN",
    "波多黎各": "PUR",
    "哥倫比亞": "COL",
    "加拿大": "CAN",
    "墨西哥": "MEX",
    "英國": "GBR",
    "美國": "USA",
    "巴西": "BRA",
    "義大利": "ITA",
    "荷蘭": "NED",
    "委內瑞拉": "VEN",
    "尼加拉瓜": "NIC",
    "多明尼加": "DOM",
    "以色列": "ISR",
}

# MLB 30 隊中文名稱 → 標準 3 字母縮寫（供 tsl_odds_history.jsonl 落地使用）
MLB_ZH_TO_CODE: dict[str, str] = {
    "亞利桑那響尾蛇": "ARI",
    "亞歷桑那響尾蛇": "ARI",
    "亞特蘭大勇士": "ATL",
    "巴爾的摩金鶯": "BAL",
    "波士頓紅襪": "BOS",
    "芝加哥小熊": "CHC",
    "芝加哥白襪": "CWS",
    "辛辛那堤紅人": "CIN",
    "辛辛那提紅人": "CIN",
    "克里夫蘭守護者": "CLE",
    "科羅拉多洛磯": "COL",
    "底特律老虎": "DET",
    "休士頓太空人": "HOU",
    "堪薩斯皇家": "KCR",
    "洛杉磯天使": "LAA",
    "洛杉磯道奇": "LAD",
    "邁阿密馬林魚": "MIA",
    "密爾瓦基釀酒人": "MIL",
    "明尼蘇達雙城": "MIN",
    "紐約大都會": "NYM",
    "紐約洋基": "NYY",
    "運動家": "OAK",
    "奧克蘭運動家": "OAK",
    "費城費城人": "PHI",
    "匹茲堡海盜": "PIT",
    "聖地牙哥教士": "SDP",
    "聖路易紅雀": "STL",
    "西雅圖水手": "SEA",
    "舊金山巨人": "SFG",
    "坦帕灣光芒": "TBR",
    "德州遊騎兵": "TEX",
    "多倫多藍鳥": "TOR",
    "華盛頓國民": "WSN",
}

MARKET_MAP = {
    "MNL": "ML",
    "HDC": "RL",
    "OU": "OU",
    "OE": "OE",
    "FMNL": "F5",
    "TTO": "TT",
}


@dataclass(frozen=True)
class TSLMarketSnapshot:
    match_id: str
    away_code: str
    home_code: str
    game_time: str
    fetched_at: str
    source: str
    market: str
    home_odds: float
    away_odds: float
    line: float | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_datetime(value: str, *, assume_tz: timezone) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=assume_tz)
    return parsed


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_team_name(value: str) -> str:
    name = value.strip()
    # Check WBC/international national teams first, then MLB 30 teams
    return TEAM_NAME_TO_CODE.get(name) or MLB_ZH_TO_CODE.get(name, "")


def _detect_sport_league(home_name: str, away_name: str) -> str:
    """Classify game into sport/league based on team names.

    Returns one of: "MLB", "WBC", "INTL", "UNKNOWN"
    """
    home = home_name.strip()
    away = away_name.strip()
    if home in MLB_ZH_TO_CODE or away in MLB_ZH_TO_CODE:
        return "MLB"
    if home in TEAM_NAME_TO_CODE or away in TEAM_NAME_TO_CODE:
        return "WBC"
    if home or away:
        return "INTL"
    return "UNKNOWN"


def _is_pregame(fetched_at: str, game_time: str) -> bool | None:
    """Return True if the snapshot was fetched before the game started.

    Returns None when either timestamp cannot be parsed.
    """
    fetched_dt = _parse_iso_datetime(fetched_at, assume_tz=timezone.utc)
    game_dt = _parse_iso_datetime(game_time, assume_tz=TAIPEI_TZ)
    if fetched_dt is None or game_dt is None:
        return None
    return fetched_dt < game_dt.astimezone(timezone.utc)


def _normalize_market(market: str) -> str | None:
    code = str(market or "").strip().upper()
    if code in MARKET_MAP:
        return MARKET_MAP[code]
    if code in MARKET_MAP.values():
        return code
    return None


def _normalize_outcome_side(raw_name: str) -> str:
    name = str(raw_name or "").strip()
    if name == "大":
        return "Over"
    if name == "小":
        return "Under"
    if name == "單":
        return "Odd"
    if name == "雙":
        return "Even"
    return _map_team_name(name) or name


def _history_record_from_game(
    game: dict[str, Any],
    *,
    source: str,
    fetched_at: str,
) -> dict[str, Any]:
    home_name = str(game.get("homeTeamName", ""))
    away_name = str(game.get("awayTeamName", ""))
    game_time = str(game.get("gameTime", ""))
    pregame = _is_pregame(fetched_at, game_time)
    return {
        "source": source,
        "fetched_at": fetched_at,
        "match_id": str(game.get("gameId", "")),
        "game_time": game_time,
        "home_team_name": home_name,
        "away_team_name": away_name,
        "home_code": _map_team_name(home_name),
        "away_code": _map_team_name(away_name),
        "sport_league": _detect_sport_league(home_name, away_name),
        "is_pregame": pregame,
        "markets": game.get("markets", []) or [],
    }


_DEDUP_STATE_PATH = ROOT / "data" / ".live_cache" / "tsl_dedup_state.json"


def _load_dedup_state() -> dict[str, Any]:
    """Load persisted per-match odds state for cross-fetch dedup."""
    try:
        if _DEDUP_STATE_PATH.exists():
            return json.loads(_DEDUP_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_dedup_state(state: dict[str, Any]) -> None:
    _DEDUP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DEDUP_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_mnl_odds_key(game: dict[str, Any]) -> str | None:
    """Return a stable odds fingerprint for the MNL market, or None if unavailable."""
    for market in game.get("markets", []) or []:
        if str(market.get("marketCode", "")).upper() == "MNL":
            odds_parts = sorted(
                f"{str(o.get('outcomeName', ''))}:{str(o.get('odds', ''))}"
                for o in (market.get("outcomes") or [])
                if o.get("odds") not in (None, "")
            )
            if odds_parts:
                return "|".join(odds_parts)
    return None


def append_tsl_history(
    *,
    games: list[dict[str, Any]],
    source: str,
    fetched_at: str,
    force_closing: bool = False,
) -> None:
    """Append games to the JSONL history, skipping entries with unchanged MNL odds.

    Cross-fetch dedup: if the same match_id was already appended with identical MNL
    odds in a previous fetch, we skip the new entry to avoid inflating the JSONL with
    zero-information duplicate rows.  When odds change, we always append.

    P26F — force_closing bypass:
    When force_closing=True (set when the capture window is in closing mode,
    i.e., game_time ±2h), the MNL dedup filter is bypassed and the snapshot is
    always written.  This guarantees a closing snapshot exists for CLV pair
    construction even when odds are stable.  The record carries audit fields:
      - force_closing_snapshot=True
      - capture_reason="closing_window"
      - dedup_bypassed=True

    Note: games without MNL markets are always appended (no odds to compare).
    """
    if not games:
        return
    dedup_state = _load_dedup_state()
    TSL_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    state_updated = False
    with TSL_HISTORY_PATH.open("a", encoding="utf-8") as handle:
        for game in games:
            match_id = str(game.get("gameId", ""))
            odds_key = _extract_mnl_odds_key(game)
            if odds_key is not None and not force_closing and dedup_state.get(match_id) == odds_key:
                # Same MNL odds as last persisted snapshot — skip to avoid inflation.
                # Bypass is disabled when force_closing=True (closing window capture).
                continue
            record = _history_record_from_game(game, source=source, fetched_at=fetched_at)
            if force_closing:
                # Audit fields so analysts can distinguish closing-forced rows
                record["force_closing_snapshot"] = True
                record["capture_reason"] = "closing_window"
                record["dedup_bypassed"] = odds_key is not None and dedup_state.get(match_id) == odds_key
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            if odds_key is not None:
                dedup_state[match_id] = odds_key
                state_updated = True
    if state_updated:
        _save_dedup_state(dedup_state)


def save_tsl_snapshot(
    *,
    games: list[dict[str, Any]],
    source: str,
    force_closing: bool = False,
) -> None:
    fetched_at = _utc_now()
    payload = {
        "source": source,
        "fetched_at": fetched_at,
        "games": games,
    }
    TSL_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TSL_SNAPSHOT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    append_tsl_history(games=games, source=source, fetched_at=fetched_at, force_closing=force_closing)


def load_tsl_snapshot() -> dict[str, Any]:
    if not TSL_SNAPSHOT_PATH.exists():
        return {}
    try:
        return json.loads(TSL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_tsl_history(
    *,
    away_code: str | None = None,
    home_code: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if not TSL_HISTORY_PATH.exists():
        return []

    rows: list[dict[str, Any]] = []
    with TSL_HISTORY_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if away_code and record.get("away_code") != away_code:
                continue
            if home_code and record.get("home_code") != home_code:
                continue
            rows.append(record)

    rows.sort(key=lambda row: str(row.get("fetched_at", "")))
    if limit is not None:
        return rows[-limit:]
    return rows


def _extract_market_snapshot(
    record: dict[str, Any],
    *,
    market: str,
) -> TSLMarketSnapshot | None:
    canonical_market = _normalize_market(market)
    if not canonical_market:
        return None

    home_code = str(record.get("home_code", ""))
    away_code = str(record.get("away_code", ""))
    home_team_name = str(record.get("home_team_name", ""))
    away_team_name = str(record.get("away_team_name", ""))

    for market_obj in record.get("markets", []) or []:
        market_code = _normalize_market(str(market_obj.get("marketCode", "")))
        if market_code != canonical_market:
            continue

        home_odds = None
        away_odds = None
        shared_line = None
        for outcome in market_obj.get("outcomes", []) or []:
            side = _normalize_outcome_side(str(outcome.get("outcomeName", "")))
            odds = _parse_float(outcome.get("odds"))
            if odds is None:
                continue
            parsed_line = _parse_float(outcome.get("specialBetValue"))
            if parsed_line is not None and shared_line is None:
                shared_line = parsed_line

            if side in {home_code, home_team_name, "HOME"}:
                home_odds = odds
                continue
            if side in {away_code, away_team_name, "AWAY"}:
                away_odds = odds

        if home_odds is None or away_odds is None:
            return None

        return TSLMarketSnapshot(
            match_id=str(record.get("match_id", "")),
            away_code=away_code,
            home_code=home_code,
            game_time=str(record.get("game_time", "")),
            fetched_at=str(record.get("fetched_at", "")),
            source=str(record.get("source", "")),
            market=canonical_market,
            home_odds=home_odds,
            away_odds=away_odds,
            line=shared_line,
        )

    return None


def get_tsl_market_history(
    away_code: str,
    home_code: str,
    *,
    market: str = "ML",
    limit: int | None = None,
    max_snapshot_age_hours: float | None = None,
) -> list[TSLMarketSnapshot]:
    snapshots: list[TSLMarketSnapshot] = []
    now_dt = _utc_now_dt() if max_snapshot_age_hours is not None else None
    for record in load_tsl_history(away_code=away_code, home_code=home_code):
        snapshot = _extract_market_snapshot(record, market=market)
        if snapshot is not None:
            if max_snapshot_age_hours is not None:
                fetched_dt = _parse_iso_datetime(snapshot.fetched_at, assume_tz=timezone.utc)
                if fetched_dt is None:
                    continue
                age_hours = (now_dt - fetched_dt.astimezone(timezone.utc)).total_seconds() / 3600.0
                if age_hours > max_snapshot_age_hours:
                    continue
            snapshots.append(snapshot)

    deduped: dict[tuple[str, str, str, str], TSLMarketSnapshot] = {}
    for snapshot in snapshots:
        key = (snapshot.fetched_at, snapshot.source, snapshot.match_id, snapshot.market)
        deduped[key] = snapshot

    ordered = sorted(deduped.values(), key=lambda item: item.fetched_at)
    if limit is not None:
        return ordered[-limit:]
    return ordered


def build_tsl_line_movement_context(
    away_code: str,
    home_code: str,
    *,
    market: str = "ML",
    game_time: str = "",
    max_snapshots: int = 12,
    max_snapshot_age_hours: float | None = None,
) -> dict[str, Any]:
    from wbc_backend.intelligence.line_movement_predictor import LineSnapshot

    market_history = get_tsl_market_history(
        away_code,
        home_code,
        market=market,
        limit=max_snapshots,
        max_snapshot_age_hours=max_snapshot_age_hours,
    )
    if not market_history:
        return {
            "opening_home_odds": 0.0,
            "current_home_odds": 0.0,
            "current_away_odds": 0.0,
            "current_market_line": None,
            "line_history": [],
            "total_line_moves": 0,
            "line_movement_velocity": 0.0,
            "recent_velocity": 0.0,
            "odds_acceleration": 0.0,
            "historical_home_implied_probs": [],
        }

    reference_game_time = game_time or market_history[-1].game_time
    game_dt = _parse_iso_datetime(reference_game_time, assume_tz=TAIPEI_TZ)
    line_history: list[LineSnapshot] = []
    for index, snapshot in enumerate(market_history):
        fetched_dt = _parse_iso_datetime(snapshot.fetched_at, assume_tz=timezone.utc)
        if fetched_dt is not None and game_dt is not None:
            minutes_to_game = max(
                0.0,
                (game_dt.astimezone(timezone.utc) - fetched_dt.astimezone(timezone.utc)).total_seconds() / 60.0,
            )
        else:
            minutes_to_game = float(max(len(market_history) - index - 1, 0) * 60)

        line_history.append(
            LineSnapshot(
                timestamp_minutes_to_game=minutes_to_game,
                home_odds=snapshot.home_odds,
                away_odds=snapshot.away_odds,
            )
        )

    def _implied_prob(decimal_odds: float) -> float:
        if decimal_odds <= 1.0:
            return 0.99
        return 1.0 / decimal_odds

    def _velocity(prev_snap: LineSnapshot, next_snap: LineSnapshot) -> float:
        dt_hours = abs(prev_snap.timestamp_minutes_to_game - next_snap.timestamp_minutes_to_game) / 60.0
        if dt_hours <= 0:
            return 0.0
        return (_implied_prob(next_snap.home_odds) - _implied_prob(prev_snap.home_odds)) / dt_hours

    line_movement_velocity = 0.0
    recent_velocity = 0.0
    odds_acceleration = 0.0
    if len(line_history) >= 2:
        line_movement_velocity = _velocity(line_history[0], line_history[-1])
        recent_velocity = _velocity(line_history[-2], line_history[-1])
    if len(line_history) >= 3:
        previous_velocity = _velocity(line_history[-3], line_history[-2])
        odds_acceleration = recent_velocity - previous_velocity

    return {
        "opening_home_odds": line_history[0].home_odds,
        "current_home_odds": line_history[-1].home_odds,
        "current_away_odds": line_history[-1].away_odds,
        "current_market_line": market_history[-1].line,
        "line_history": line_history,
        "total_line_moves": max(0, len(line_history) - 1),
        "line_movement_velocity": line_movement_velocity,
        "recent_velocity": recent_velocity,
        "odds_acceleration": odds_acceleration,
        "historical_home_implied_probs": [
            round(_implied_prob(snapshot.home_odds), 6)
            for snapshot in line_history
        ],
    }


def build_tsl_odds_time_series(
    away_code: str,
    home_code: str,
    *,
    markets: tuple[str, ...] = ("ML",),
    max_snapshots: int = 12,
    max_snapshot_age_hours: float | None = None,
) -> dict[str, "OddsTimeSeries"]:
    from wbc_backend.domain.schemas import OddsTimeSeries

    time_series: dict[str, OddsTimeSeries] = {}
    for market in markets:
        history = get_tsl_market_history(
            away_code,
            home_code,
            market=market,
            limit=max_snapshots,
            max_snapshot_age_hours=max_snapshot_age_hours,
        )
        if len(history) < 2:
            continue

        series = OddsTimeSeries(
            sportsbook="TSL",
            market=market,
            side=home_code if market == "ML" else market,
            snapshots=[
                {
                    "timestamp": snap.fetched_at,
                    "odds": snap.home_odds,
                    "away_odds": snap.away_odds,
                    "line": snap.line,
                }
                for snap in history
            ],
        )
        time_series[f"TSL_{market}_{home_code}"] = series

    return time_series


def _format_market(game: dict[str, Any], market_code: str) -> str:
    markets = game.get("markets", []) or []
    for market in markets:
        if market.get("marketCode") != market_code:
            continue
        outcomes = market.get("outcomes", []) or []
        parts: list[str] = []
        for outcome in outcomes[:2]:
            name = str(outcome.get("outcomeName", "")).strip()
            odds = outcome.get("odds")
            line = outcome.get("specialBetValue")
            if name == "大":
                label = f"Over {line}" if line not in (None, "") else "Over"
            elif name == "小":
                label = f"Under {line}" if line not in (None, "") else "Under"
            elif name == "單":
                label = "單"
            elif name == "雙":
                label = "雙"
            else:
                label = name
                if market_code == "HDC" and line not in (None, ""):
                    try:
                        label = f"{label} {float(line):+.1f}"
                    except (TypeError, ValueError):
                        label = f"{label} {line}"
            if odds in (None, ""):
                continue
            parts.append(f"{label} {float(odds):.2f}")
        return " / ".join(parts) if parts else "無資料"
    return "無資料"


def get_tsl_summary(away_code: str, home_code: str) -> dict[str, str]:
    snapshot = load_tsl_snapshot()
    for game in snapshot.get("games", []) or []:
        game_home = _map_team_name(str(game.get("homeTeamName", "")))
        game_away = _map_team_name(str(game.get("awayTeamName", "")))
        if game_home == home_code and game_away == away_code:
            return {
                "ML": _format_market(game, "MNL"),
                "RL": _format_market(game, "HDC"),
                "OU": _format_market(game, "OU"),
                "source": str(snapshot.get("source", "")),
                "fetched_at": str(snapshot.get("fetched_at", "")),
            }
    return {}


def get_tsl_odds_lines(away_code: str, home_code: str) -> list["OddsLine"]:
    from data.wbc_data import OddsLine

    snapshot = load_tsl_snapshot()
    fetched_at = str(snapshot.get("fetched_at", ""))
    for game in snapshot.get("games", []) or []:
        game_home = _map_team_name(str(game.get("homeTeamName", "")))
        game_away = _map_team_name(str(game.get("awayTeamName", "")))
        if game_home != home_code or game_away != away_code:
            continue

        odds_lines: list[OddsLine] = []
        for market in game.get("markets", []) or []:
            market_code = MARKET_MAP.get(str(market.get("marketCode", "")).strip())
            if not market_code:
                continue
            for outcome in market.get("outcomes", []) or []:
                raw_name = str(outcome.get("outcomeName", "")).strip()
                odds = outcome.get("odds")
                if odds in (None, ""):
                    continue
                side = raw_name
                if raw_name == "大":
                    side = "Over"
                elif raw_name == "小":
                    side = "Under"
                elif raw_name == "單":
                    side = "Odd"
                elif raw_name == "雙":
                    side = "Even"
                else:
                    mapped = _map_team_name(raw_name)
                    if mapped:
                        side = mapped
                line = outcome.get("specialBetValue")
                parsed_line = None
                if line not in (None, ""):
                    try:
                        parsed_line = float(line)
                    except (TypeError, ValueError):
                        parsed_line = None
                if market_code == "TT" and side in {away_code, home_code}:
                    odds_lines.append(
                        OddsLine(
                            book="TSL",
                            market="TT",
                            side=f"{side}_Over",
                            price=float(odds),
                            line=parsed_line,
                            timestamp=fetched_at,
                        )
                    )
                    continue
                odds_lines.append(
                    OddsLine(
                        book="TSL",
                        market=market_code,
                        side=side,
                        price=float(odds),
                        line=parsed_line,
                        timestamp=fetched_at,
                    )
                )
        return odds_lines
    return []
