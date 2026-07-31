from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from .ids import make_mlb_game_id
from .normalization import canonical_team_name, iso_to_et_date_time


MLB_STATS_API = "https://statsapi.mlb.com/api/v1"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"


@dataclass(frozen=True)
class ExternalFetchSummary:
    fetched_at: str
    lineups_written: int
    bullpen_written: int
    odds_timeline_written: int
    weather_written: int
    injury_rest_written: int
    failures: int


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _http_json(url: str, timeout: int = 8) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "betting-pool-mlb-context/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _safe_http_json(url: str) -> Any | None:
    try:
        return _http_json(url)
    except Exception:
        return None


@lru_cache(maxsize=256)
def _venue_meta(venue_id: int | None) -> dict[str, Any] | None:
    if not venue_id:
        return None
    data = _safe_http_json(f"{MLB_STATS_API}/venues/{venue_id}?hydrate=location,timeZone,fieldInfo,xrefId,metadata") or {}
    venues = data.get("venues", [])
    return venues[0] if venues else None


@lru_cache(maxsize=2048)
def _historical_weather(lat: float | None, lon: float | None, game_date: str) -> dict[str, Any] | None:
    if lat is None or lon is None or not game_date:
        return None
    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        + urllib.parse.urlencode(
            {
                "latitude": f"{lat}",
                "longitude": f"{lon}",
                "start_date": game_date,
                "end_date": game_date,
                "hourly": "temperature_2m,wind_speed_10m",
                "timezone": "UTC",
            }
        )
    )
    data = _safe_http_json(url) or {}
    hourly = data.get("hourly", {})
    temps = hourly.get("temperature_2m", []) or []
    winds = hourly.get("wind_speed_10m", []) or []
    if not temps or not winds:
        return None
    return {
        "temp_c_avg": round(float(sum(temps) / len(temps)), 2),
        "wind_kmh_avg": round(float(sum(winds) / len(winds)), 2),
        "provider": "open-meteo-archive",
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    existing: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing.append(json.loads(line))
            except Exception:
                continue
    by_gid: dict[str, dict[str, Any]] = {}
    for rec in existing + rows:
        gid = str(rec.get("game_id", "")).strip()
        if not gid:
            continue
        cur = by_gid.get(gid)
        if cur is None or str(rec.get("fetched_at", "")) >= str(cur.get("fetched_at", "")):
            by_gid[gid] = rec
    merged = list(by_gid.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged), encoding="utf-8")


def _load_index(csv_path: str | Path) -> set[str]:
    df = pd.read_csv(csv_path)
    ids: set[str] = set()
    for _, r in df.iterrows():
        ids.add(
            make_mlb_game_id(
                str(r.get("Date", "")),
                str(r.get("Start Time (EDT)", "")),
                str(r.get("Away", "")),
                str(r.get("Home", "")),
            )
        )
    return ids


def _build_game_lookup(csv_path: str | Path) -> dict[tuple[str, str, str], str]:
    df = pd.read_csv(csv_path)
    lookup: dict[tuple[str, str, str], str] = {}
    for _, r in df.iterrows():
        d = str(r.get("Date", "")).strip()
        away = canonical_team_name(str(r.get("Away", "")))
        home = canonical_team_name(str(r.get("Home", "")))
        gid = make_mlb_game_id(
            d,
            str(r.get("Start Time (EDT)", "")),
            str(r.get("Away", "")),
            str(r.get("Home", "")),
        )
        lookup[(d, away, home)] = gid
    return lookup


def _schedule_games(start_date: str, end_date: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cur = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    while cur <= end:
        qs = urllib.parse.urlencode({"sportId": "1", "date": cur.isoformat()})
        data = _safe_http_json(f"{MLB_STATS_API}/schedule?{qs}") or {}
        for d in data.get("dates", []):
            out.extend(d.get("games", []))
        cur += timedelta(days=1)
    return out


def _lineup_and_context_from_boxscore(
    *,
    box: dict[str, Any],
    schedule_game: dict[str, Any],
    fetched_at: str,
    game_lookup: dict[tuple[str, str, str], str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    teams = schedule_game.get("teams", {})
    home = canonical_team_name(teams.get("home", {}).get("team", {}).get("name", ""))
    away = canonical_team_name(teams.get("away", {}).get("team", {}).get("name", ""))
    game_dt = schedule_game.get("gameDate", "")
    et_date, et_time = iso_to_et_date_time(game_dt) if game_dt else ("", "")
    gid = game_lookup.get((et_date, away, home), make_mlb_game_id(et_date, et_time, away, home) if (et_date and away and home) else "")

    teams_box = box.get("teams", {})
    h_box = teams_box.get("home", {})
    a_box = teams_box.get("away", {})
    h_players = h_box.get("players", {})
    a_players = a_box.get("players", {})
    h_order = h_box.get("battingOrder", []) or []
    a_order = a_box.get("battingOrder", []) or []

    def _name(players: dict[str, Any], pid: Any) -> str:
        key = f"ID{pid}"
        return str(players.get(key, {}).get("person", {}).get("fullName", ""))

    home_lineup = [_name(h_players, pid) for pid in h_order if _name(h_players, pid)]
    away_lineup = [_name(a_players, pid) for pid in a_order if _name(a_players, pid)]
    home_pitchers = h_box.get("pitchers", []) or []
    away_pitchers = a_box.get("pitchers", []) or []
    home_sp = _name(h_players, home_pitchers[0]) if home_pitchers else None
    away_sp = _name(a_players, away_pitchers[0]) if away_pitchers else None

    def _platoon(players: dict[str, Any], order: list[Any]) -> dict[str, int]:
        counts = {"L": 0, "R": 0, "S": 0}
        for pid in order:
            key = f"ID{pid}"
            bat = str(players.get(key, {}).get("batSide", {}).get("code", "")).upper()
            if bat in counts:
                counts[bat] += 1
        return counts

    lineup_rec = {
        "game_id": gid,
        "game_pk": schedule_game.get("gamePk"),
        "confirmed_home_starter": home_sp,
        "confirmed_away_starter": away_sp,
        "confirmed_home_lineup": home_lineup if home_lineup else None,
        "confirmed_away_lineup": away_lineup if away_lineup else None,
        "home_away_splits": {
            "home_record": teams.get("home", {}).get("record", {}),
            "away_record": teams.get("away", {}).get("record", {}),
        },
        "platoon_splits": {"home_bat_side": _platoon(h_players, h_order), "away_bat_side": _platoon(a_players, a_order)} if (home_lineup or away_lineup) else None,
        "fetched_at": fetched_at,
        "source": "mlb_stats_api_boxscore",
    }

    weather = schedule_game.get("weather") or {}
    venue = schedule_game.get("venue") or {}
    venue_meta = _venue_meta(venue.get("id"))
    loc = (venue_meta or {}).get("location", {})
    hist_weather = _historical_weather(loc.get("defaultCoordinates", {}).get("latitude"), loc.get("defaultCoordinates", {}).get("longitude"), et_date)
    weather_rec = {
        "game_id": gid,
        "game_pk": schedule_game.get("gamePk"),
        "weather": hist_weather or (weather if weather else None),
        "wind": {"condition": weather.get("wind")} if weather.get("wind") else ({"wind_kmh_avg": hist_weather.get("wind_kmh_avg")} if hist_weather else None),
        "park_factors": {
            "venue_id": venue.get("id"),
            "venue_name": venue.get("name"),
            "roof_type": (venue_meta or {}).get("roofType"),
            "turf_type": (venue_meta or {}).get("turfType"),
        }
        if venue
        else None,
        "fetched_at": fetched_at,
        "source": "mlb_stats_api_boxscore",
    }

    h_inj = [p.get("person", {}).get("fullName") for p in h_players.values() if str(p.get("status", {}).get("code", "")).upper().startswith("I")]
    a_inj = [p.get("person", {}).get("fullName") for p in a_players.values() if str(p.get("status", {}).get("code", "")).upper().startswith("I")]
    injury_rec = {
        "game_id": gid,
        "game_pk": schedule_game.get("gamePk"),
        "injury_report": {"home_inactive": [x for x in h_inj if x], "away_inactive": [x for x in a_inj if x]},
        "rest_days_home": None,
        "rest_days_away": None,
        "fetched_at": fetched_at,
        "source": "mlb_stats_api_boxscore",
    }
    return lineup_rec, weather_rec, injury_rec


def _bullpen_from_schedule(games: list[dict[str, Any]], fetched_at: str, game_lookup: dict[tuple[str, str, str], str]) -> list[dict[str, Any]]:
    by_team_by_date: dict[str, dict[str, float]] = defaultdict(dict)
    game_rows: list[tuple[str, str, str]] = []
    for g in games:
        game_pk = g.get("gamePk")
        game_time = g.get("gameDate", "")
        if not game_pk or not game_time:
            continue
        date_key = game_time[:10]
        home = canonical_team_name(g.get("teams", {}).get("home", {}).get("team", {}).get("name", ""))
        away = canonical_team_name(g.get("teams", {}).get("away", {}).get("team", {}).get("name", ""))
        et_date, et_time = iso_to_et_date_time(game_time)
        gid = game_lookup.get((et_date, away, home), make_mlb_game_id(et_date, et_time, away, home))
        game_rows.append((gid, home, away))
        box = _safe_http_json(f"{MLB_STATS_API}/game/{game_pk}/boxscore")
        if not box:
            continue
        teams_box = box.get("teams", {})
        for side, team in (("home", home), ("away", away)):
            tbox = teams_box.get(side, {})
            pitchers = tbox.get("pitchers", []) or []
            probable_id = pitchers[0] if pitchers else None
            workload = 0.0
            for pid in pitchers:
                if probable_id and int(pid) == int(probable_id):
                    continue
                p = tbox.get("players", {}).get(f"ID{pid}", {})
                ip = p.get("stats", {}).get("pitching", {}).get("inningsPitched")
                try:
                    workload += float(str(ip).replace(".1", ".333").replace(".2", ".667"))
                except Exception:
                    continue
            by_team_by_date[team][date_key] = by_team_by_date[team].get(date_key, 0.0) + workload

    rows = []
    for gid, home, away in game_rows:
        date_token = gid.split("-")[1].replace("_", "-")
        d = date.fromisoformat(date_token)
        recent = [(d - timedelta(days=i)).isoformat() for i in (1, 2, 3)]
        home_usage = sum(by_team_by_date.get(home, {}).get(k, 0.0) for k in recent)
        away_usage = sum(by_team_by_date.get(away, {}).get(k, 0.0) for k in recent)
        rows.append(
            {
                "game_id": gid,
                "bullpen_usage_last_3d_home": round(home_usage, 3) if home_usage > 0 else None,
                "bullpen_usage_last_3d_away": round(away_usage, 3) if away_usage > 0 else None,
                "fetched_at": fetched_at,
                "source": "mlb_stats_api_boxscore",
            }
        )
    return rows


def _compute_rest_days(games: list[dict[str, Any]], injury_rows: list[dict[str, Any]], game_lookup: dict[tuple[str, str, str], str]) -> None:
    by_gid = {r["game_id"]: r for r in injury_rows if r.get("game_id")}
    appearances: dict[str, list[date]] = defaultdict(list)
    parsed_games: list[tuple[date, str, str, str]] = []
    for g in games:
        game_time = g.get("gameDate", "")
        if not game_time:
            continue
        et_date, et_time = iso_to_et_date_time(game_time)
        d = date.fromisoformat(et_date)
        home = canonical_team_name(g.get("teams", {}).get("home", {}).get("team", {}).get("name", ""))
        away = canonical_team_name(g.get("teams", {}).get("away", {}).get("team", {}).get("name", ""))
        gid = game_lookup.get((et_date, away, home), make_mlb_game_id(et_date, et_time, away, home))
        parsed_games.append((d, gid, home, away))
    parsed_games.sort(key=lambda x: x[0])
    for d, gid, home, away in parsed_games:
        rec = by_gid.get(gid)
        if not rec:
            continue
        h_prev = appearances.get(home, [])
        a_prev = appearances.get(away, [])
        rec["rest_days_home"] = max(0, (d - h_prev[-1]).days - 1) if h_prev else None
        rec["rest_days_away"] = max(0, (d - a_prev[-1]).days - 1) if a_prev else None
        appearances[home].append(d)
        appearances[away].append(d)


def _fetch_odds_timeline(start_date: str, end_date: str, fetched_at: str) -> list[dict[str, Any]]:
    api_key = os.getenv("ODDS_API_KEY", "").strip()
    if not api_key:
        return []
    params = urllib.parse.urlencode(
        {
            "apiKey": api_key,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "american",
            "bookmakers": "pinnacle,betonlineag",
        }
    )
    data = _safe_http_json(f"{ODDS_API_BASE}/sports/baseball_mlb/odds?{params}") or []
    rows = []
    for g in data:
        commence = str(g.get("commence_time", ""))
        if not commence:
            continue
        et_date, et_time = iso_to_et_date_time(commence)
        away = canonical_team_name(g.get("away_team", ""))
        home = canonical_team_name(g.get("home_team", ""))
        gid = make_mlb_game_id(et_date, et_time, away, home)
        book = (g.get("bookmakers") or [{}])[0]
        market = ((book.get("markets") or [{}])[0]).get("outcomes", [])
        home_ml = None
        away_ml = None
        for out in market:
            if canonical_team_name(str(out.get("name", ""))) == home:
                home_ml = out.get("price")
            elif canonical_team_name(str(out.get("name", ""))) == away:
                away_ml = out.get("price")
        rows.append(
            {
                "game_id": gid,
                "opening_home_ml": None,
                "opening_away_ml": None,
                "current_home_ml": home_ml,
                "current_away_ml": away_ml,
                "decision_home_ml": home_ml,
                "decision_away_ml": away_ml,
                "latest_pregame_home_ml": home_ml,
                "latest_pregame_away_ml": away_ml,
                "closing_home_ml": None,
                "closing_away_ml": None,
                "odds_history": [{"ts": fetched_at, "home_ml": home_ml, "away_ml": away_ml, "snapshot_type": "current"}] if (home_ml is not None or away_ml is not None) else None,
                "fetched_at": fetched_at,
                "source": "the-odds-api-v4",
            }
        )
    return rows


def fetch_and_materialize_external_context(
    *,
    csv_path: str | Path = "data/mlb_2025/mlb_odds_2025_real.csv",
    output_dir: str | Path = "data/mlb_context_sources",
    start_date: str | None = None,
    end_date: str | None = None,
    max_games: int = 50,
) -> ExternalFetchSummary:
    df = pd.read_csv(csv_path)
    game_lookup = _build_game_lookup(csv_path)
    if start_date is None:
        start_date = str(df["Date"].min())
    if end_date is None:
        end_date = str(df["Date"].max())
    selected_df = (
        df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]
        .sort_values(["Date", "Start Time (EDT)"], ascending=False)
        .head(max_games)
        .copy()
    )
    selected_ids = set(
        make_mlb_game_id(str(r.get("Date", "")), str(r.get("Start Time (EDT)", "")), str(r.get("Away", "")), str(r.get("Home", "")))
        for _, r in selected_df.iterrows()
    )
    expected_ids = selected_ids
    fetched_at = _now_iso()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    failures = 0

    min_sel = date.fromisoformat(str(selected_df["Date"].min()))
    max_sel = date.fromisoformat(str(selected_df["Date"].max()))
    games = _schedule_games((min_sel - timedelta(days=3)).isoformat(), max_sel.isoformat())
    lineups: list[dict[str, Any]] = []
    weather: list[dict[str, Any]] = []
    injury: list[dict[str, Any]] = []
    for g in games:
        pk = g.get("gamePk")
        if not pk:
            continue
        box = _safe_http_json(f"{MLB_STATS_API}/game/{pk}/boxscore")
        if not box:
            failures += 1
            continue
        l, w, i = _lineup_and_context_from_boxscore(
            box=box,
            schedule_game=g,
            fetched_at=fetched_at,
            game_lookup=game_lookup,
        )
        if l.get("game_id") in expected_ids:
            lineups.append(l)
            weather.append(w)
            injury.append(i)

    bullpen = _bullpen_from_schedule(games, fetched_at, game_lookup)
    bullpen = [r for r in bullpen if r.get("game_id") in expected_ids]
    _compute_rest_days(games, injury, game_lookup)

    odds = _fetch_odds_timeline(start_date, end_date, fetched_at)
    odds = [r for r in odds if r.get("game_id") in expected_ids]
    if not odds:
        # Bootstrap with real archived market snapshot from verified odds csv (no synthetic fill).
        odds = []
        for _, r in selected_df.iterrows():
            gid = make_mlb_game_id(str(r.get("Date", "")), str(r.get("Start Time (EDT)", "")), str(r.get("Away", "")), str(r.get("Home", "")))
            odds.append(
                {
                    "game_id": gid,
                    "opening_home_ml": None,
                    "opening_away_ml": None,
                    "current_home_ml": None,
                    "current_away_ml": None,
                    "decision_home_ml": None,
                    "decision_away_ml": None,
                    "latest_pregame_home_ml": None,
                    "latest_pregame_away_ml": None,
                    "closing_home_ml": r.get("Home ML"),
                    "closing_away_ml": r.get("Away ML"),
                    "odds_history": [{"ts": fetched_at, "home_ml": r.get("Home ML"), "away_ml": r.get("Away ML"), "source": "mlb_odds_2025_real.csv", "snapshot_type": "closing_fallback"}],
                    "fetched_at": fetched_at,
                    "source": "mlb_odds_2025_real.csv",
                }
            )

    def _latest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_gid: dict[str, dict[str, Any]] = {}
        for r in rows:
            gid = str(r.get("game_id", "")).strip()
            if not gid:
                continue
            cur = by_gid.get(gid)
            if cur is None or str(r.get("fetched_at", "")) >= str(cur.get("fetched_at", "")):
                by_gid[gid] = r
        return list(by_gid.values())

    lineups = _latest(lineups)
    bullpen = _latest(bullpen)
    odds = _latest(odds)
    weather = _latest(weather)
    injury = _latest(injury)

    _write_jsonl(out / "confirmed_lineups.jsonl", lineups)
    _write_jsonl(out / "bullpen_usage_3d.jsonl", bullpen)
    _write_jsonl(out / "odds_timeline.jsonl", odds)
    _write_jsonl(out / "weather_wind.jsonl", weather)
    _write_jsonl(out / "injury_rest.jsonl", injury)

    return ExternalFetchSummary(
        fetched_at=fetched_at,
        lineups_written=len(lineups),
        bullpen_written=len(bullpen),
        odds_timeline_written=len(odds),
        weather_written=len(weather),
        injury_rest_written=len(injury),
        failures=failures,
    )
