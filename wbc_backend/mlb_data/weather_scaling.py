from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .ids import make_mlb_game_id
from .ingestion import load_mlb_game_data
from .normalization import canonical_team_name
from .validator import MLBValidityTier, validate_mlb_game_data


MLB_STATS_API = "https://statsapi.mlb.com/api/v1"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _http_json(url: str, timeout: int = 12, retries: int = 3) -> Any | None:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mlb-weather-scaler/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if i == retries - 1:
                return None
            time.sleep(0.25 * (i + 1))
    return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _write_jsonl_latest(path: Path, rows: list[dict[str, Any]]) -> None:
    by_gid: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(path) + rows:
        gid = str(rec.get("game_id", "")).strip()
        if not gid:
            continue
        prev = by_gid.get(gid)
        if prev is None or str(rec.get("fetched_at", "")) >= str(prev.get("fetched_at", "")):
            by_gid[gid] = rec
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(v, ensure_ascii=False) for v in by_gid.values()), encoding="utf-8")


def _load_cache(path: Path) -> dict[str, dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(path):
        key = str(rec.get("cache_key", "")).strip()
        if key:
            by_key[key] = rec
    return by_key


def _append_cache(path: Path, rows: list[dict[str, Any]]) -> None:
    existing = _load_cache(path)
    for r in rows:
        existing[r["cache_key"]] = r
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(v, ensure_ascii=False) for v in existing.values()), encoding="utf-8")


@dataclass(frozen=True)
class CandidateGame:
    game_id: str
    game_date: str
    away: str
    home: str


@dataclass
class WeatherScaleResult:
    strict_before: int
    strict_after: int
    batches_run: int
    api_calls: int
    cache_hits: int
    cache_misses: int
    avg_latency_ms: float
    newly_strict: int
    status: str
    top_remaining_blocker: str
    batch_history: list[dict[str, Any]]


def scan_weather_only_candidates(csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv") -> list[CandidateGame]:
    rows = load_mlb_game_data(csv_path=csv_path, context_path="data/mlb_context")
    validation = validate_mlb_game_data(rows)
    df = pd.read_csv(csv_path)
    by_gid = {
        make_mlb_game_id(str(r.get("Date", "")), str(r.get("Start Time (EDT)", "")), str(r.get("Away", "")), str(r.get("Home", ""))): r
        for _, r in df.iterrows()
    }
    candidates: list[CandidateGame] = []
    for row in rows:
        status = validation.status_by_game.get(row.game_id, MLBValidityTier.INVALID)
        if status == MLBValidityTier.STRICT_VALID:
            continue
        f = row.features
        other_ok = (
            f.confirmed_home_lineup.available
            and f.confirmed_away_lineup.available
            and f.bullpen_usage_last_3d_home.available
            and f.bullpen_usage_last_3d_away.available
            and f.injury_rest.injury_report.available
            and f.injury_rest.rest_days_home.available
            and f.injury_rest.rest_days_away.available
            and f.odds.odds_history.available
            and f.odds.closing_home_ml.available
            and f.odds.closing_away_ml.available
        )
        weather_missing = (not f.weather.available) or (not f.wind.available) or (not f.park_factors.available)
        if not (other_ok and weather_missing):
            continue
        src = by_gid.get(row.game_id)
        if src is None:
            continue
        candidates.append(
            CandidateGame(
                game_id=row.game_id,
                game_date=str(src.get("Date", "")),
                away=canonical_team_name(str(src.get("Away", ""))),
                home=canonical_team_name(str(src.get("Home", ""))),
            )
        )
    return candidates


def _schedule_map_by_date(game_dates: list[str]) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for d in sorted(set(game_dates)):
        qs = urllib.parse.urlencode({"sportId": "1", "date": d})
        data = _http_json(f"{MLB_STATS_API}/schedule?{qs}") or {}
        for day in data.get("dates", []):
            for g in day.get("games", []):
                away = canonical_team_name(g.get("teams", {}).get("away", {}).get("team", {}).get("name", ""))
                home = canonical_team_name(g.get("teams", {}).get("home", {}).get("team", {}).get("name", ""))
                out[(d, away, home)] = g
    return out


def _fetch_venue_meta(venue_id: int) -> dict[str, Any] | None:
    return _http_json(f"{MLB_STATS_API}/venues/{venue_id}?hydrate=location,timeZone,fieldInfo,xrefId,metadata")


def _daily_from_hourly(times: list[str], vals: list[float]) -> dict[str, float]:
    by_date: dict[str, list[float]] = {}
    for t, v in zip(times, vals):
        d = str(t)[:10]
        by_date.setdefault(d, []).append(float(v))
    return {d: float(sum(xs) / len(xs)) for d, xs in by_date.items() if xs}


def _mode_from_hourly(times: list[str], vals: list[int | float]) -> dict[str, int]:
    by_date: dict[str, dict[int, int]] = {}
    for t, v in zip(times, vals):
        d = str(t)[:10]
        iv = int(v)
        by_date.setdefault(d, {})
        by_date[d][iv] = by_date[d].get(iv, 0) + 1
    out: dict[str, int] = {}
    for d, freq in by_date.items():
        out[d] = max(freq.items(), key=lambda kv: kv[1])[0]
    return out


def _fetch_weather_for_venue_dates(
    venue_id: int,
    lat: float,
    lon: float,
    dates: set[str],
) -> tuple[int, dict[str, dict[str, Any]], float]:
    t0 = time.perf_counter()
    start = min(dates)
    end = max(dates)
    qs = urllib.parse.urlencode(
        {
            "latitude": f"{lat}",
            "longitude": f"{lon}",
            "start_date": start,
            "end_date": end,
            "hourly": "temperature_2m,wind_speed_10m,weather_code",
            "timezone": "auto",
        }
    )
    data = _http_json(f"{OPEN_METEO_ARCHIVE}?{qs}") or {}
    hourly = data.get("hourly", {})
    times = hourly.get("time", []) or []
    temps = hourly.get("temperature_2m", []) or []
    winds = hourly.get("wind_speed_10m", []) or []
    codes = hourly.get("weather_code", []) or []
    d_temp = _daily_from_hourly(times, temps) if (times and temps) else {}
    d_wind = _daily_from_hourly(times, winds) if (times and winds) else {}
    d_code = _mode_from_hourly(times, codes) if (times and codes) else {}
    rows: dict[str, dict[str, Any]] = {}
    for d in dates:
        if d not in d_temp or d not in d_wind:
            continue
        rows[d] = {
            "temp_c_avg": round(d_temp[d], 2),
            "wind_kmh_avg": round(d_wind[d], 2),
            "weather_code_mode": d_code.get(d),
            "provider": "open-meteo-archive",
        }
    latency_ms = (time.perf_counter() - t0) * 1000.0
    return 1, rows, latency_ms


def scale_weather_coverage(
    *,
    target_strict: int = 200,
    max_batches: int = 8,
    batch_size: int = 200,
    min_gain_per_batch: int = 20,
    csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv",
) -> WeatherScaleResult:
    rows0 = load_mlb_game_data(csv_path=csv_path, context_path="data/mlb_context")
    val0 = validate_mlb_game_data(rows0)
    strict_before = val0.strict_valid_games
    api_calls = 0
    cache_hits = 0
    cache_misses = 0
    latencies: list[float] = []

    cache_path = Path("data/mlb_context_sources/weather_cache.jsonl")
    weather_path = Path("data/mlb_context_sources/weather_wind.jsonl")
    cached = _load_cache(cache_path)
    batches_run = 0
    batch_history: list[dict[str, Any]] = []

    for _ in range(max_batches):
        cur_rows = load_mlb_game_data(csv_path=csv_path, context_path="data/mlb_context")
        cur_val = validate_mlb_game_data(cur_rows)
        if cur_val.strict_valid_games >= target_strict:
            break
        strict_before_batch = cur_val.strict_valid_games
        candidates = scan_weather_only_candidates(csv_path=csv_path)
        if not candidates:
            break
        batch = candidates[:batch_size]
        batches_run += 1
        schedule_map = _schedule_map_by_date([c.game_date for c in batch])

        venue_groups: dict[int, dict[str, Any]] = {}
        game_rows: list[dict[str, Any]] = []
        for c in batch:
            g = schedule_map.get((c.game_date, c.away, c.home))
            if not g:
                continue
            venue = g.get("venue", {}) or {}
            venue_id = venue.get("id")
            venue_name = venue.get("name")
            if not venue_id:
                continue
            venue_groups.setdefault(venue_id, {"dates": set(), "name": venue_name, "meta": None})
            venue_groups[venue_id]["dates"].add(c.game_date)
            game_rows.append({"game_id": c.game_id, "date": c.game_date, "venue_id": venue_id, "venue_name": venue_name})

        for vid in list(venue_groups.keys()):
            meta = _fetch_venue_meta(vid)
            api_calls += 1
            if not meta or not meta.get("venues"):
                continue
            v = meta["venues"][0]
            loc = v.get("location", {}).get("defaultCoordinates", {})
            if "latitude" not in loc or "longitude" not in loc:
                continue
            venue_groups[vid]["meta"] = {
                "lat": float(loc["latitude"]),
                "lon": float(loc["longitude"]),
                "roof_type": v.get("roofType"),
                "turf_type": v.get("turfType"),
                "venue_name": v.get("name", venue_groups[vid]["name"]),
            }

        weather_by_venue_date: dict[tuple[int, str], dict[str, Any]] = {}
        tasks = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            for vid, info in venue_groups.items():
                meta = info.get("meta")
                if not meta:
                    continue
                missing_dates = set()
                for d in info["dates"]:
                    key = f"{vid}|{d}"
                    if key in cached:
                        cache_hits += 1
                        weather_by_venue_date[(vid, d)] = cached[key]["weather_payload"]
                    else:
                        cache_misses += 1
                        missing_dates.add(d)
                if not missing_dates:
                    continue
                tasks.append(
                    ex.submit(
                        _fetch_weather_for_venue_dates,
                        vid,
                        meta["lat"],
                        meta["lon"],
                        missing_dates,
                    )
                )
            new_cache_rows: list[dict[str, Any]] = []
            for fut in as_completed(tasks):
                calls, result_map, latency = fut.result()
                api_calls += calls
                latencies.append(latency)
                for vid, info in venue_groups.items():
                    for d in info["dates"]:
                        if d not in result_map:
                            continue
                        payload = result_map[d]
                        weather_by_venue_date[(vid, d)] = payload
                        new_cache_rows.append(
                            {
                                "cache_key": f"{vid}|{d}",
                                "venue_id": vid,
                                "date": d,
                                "weather_payload": payload,
                                "fetched_at": _now_iso(),
                            }
                        )
            if new_cache_rows:
                _append_cache(cache_path, new_cache_rows)
                for r in new_cache_rows:
                    cached[r["cache_key"]] = r

        weather_rows: list[dict[str, Any]] = []
        for g in game_rows:
            p = weather_by_venue_date.get((g["venue_id"], g["date"]))
            meta = venue_groups.get(g["venue_id"], {}).get("meta")
            if not p or not meta:
                continue
            weather_rows.append(
                {
                    "game_id": g["game_id"],
                    "weather": {
                        "temp_c_avg": p["temp_c_avg"],
                        "weather_code_mode": p.get("weather_code_mode"),
                        "provider": p["provider"],
                    },
                    "wind": {
                        "wind_kmh_avg": p["wind_kmh_avg"],
                        "provider": p["provider"],
                    },
                    "park_factors": {
                        "venue_id": g["venue_id"],
                        "venue_name": meta["venue_name"],
                        "roof_type": meta["roof_type"],
                        "turf_type": meta["turf_type"],
                    },
                    "fetched_at": _now_iso(),
                    "source": "statsapi+open-meteo-batch",
                }
            )
        if weather_rows:
            _write_jsonl_latest(weather_path, weather_rows)

        # Rebuild feeds after each batch.
        from wbc_backend.mlb_data.feed_jobs import run_all_feed_jobs

        run_all_feed_jobs(csv_path=csv_path, output_dir="data/mlb_context")
        nxt_rows = load_mlb_game_data(csv_path=csv_path, context_path="data/mlb_context")
        nxt_val = validate_mlb_game_data(nxt_rows)
        strict_after_batch = nxt_val.strict_valid_games
        gain = strict_after_batch - strict_before_batch
        remaining_weather_missing = 0
        for rr in nxt_rows:
            if nxt_val.status_by_game.get(rr.game_id) == MLBValidityTier.STRICT_VALID:
                continue
            ff = rr.features
            if not (ff.weather.available and ff.wind.available and ff.park_factors.available):
                remaining_weather_missing += 1
        batches_remaining_to_85 = max(0, int((2066 - strict_after_batch + max(1, gain) - 1) / max(1, gain)))
        hit_rate = cache_hits / max(1, cache_hits + cache_misses)
        batch_history.append(
            {
                "batch": batches_run,
                "strict_valid_count": strict_after_batch,
                "strict_coverage_pct": round(strict_after_batch / max(1, len(nxt_rows)), 4),
                "added_games_this_batch": gain,
                "remaining_weather_missing": remaining_weather_missing,
                "cache_hit_rate": round(hit_rate, 4),
                "estimated_batches_remaining_to_85pct": batches_remaining_to_85,
            }
        )
        if gain < min_gain_per_batch:
            break
        if nxt_val.strict_valid_games >= target_strict:
            break

    rows1 = load_mlb_game_data(csv_path=csv_path, context_path="data/mlb_context")
    val1 = validate_mlb_game_data(rows1)
    strict_after = val1.strict_valid_games

    # Remaining blocker breakdown
    blocker_counts: dict[str, int] = {"weather_missing": 0, "lineup_missing": 0, "odds_missing": 0, "injury_missing": 0, "bullpen_missing": 0}
    for r in rows1:
        if val1.status_by_game.get(r.game_id) == MLBValidityTier.STRICT_VALID:
            continue
        f = r.features
        if not (f.weather.available and f.wind.available and f.park_factors.available):
            blocker_counts["weather_missing"] += 1
        elif not (f.confirmed_home_lineup.available and f.confirmed_away_lineup.available):
            blocker_counts["lineup_missing"] += 1
        elif not (f.odds.odds_history.available and f.odds.closing_home_ml.available and f.odds.closing_away_ml.available):
            blocker_counts["odds_missing"] += 1
        elif not (f.injury_rest.injury_report.available and f.injury_rest.rest_days_home.available and f.injury_rest.rest_days_away.available):
            blocker_counts["injury_missing"] += 1
        elif not (f.bullpen_usage_last_3d_home.available and f.bullpen_usage_last_3d_away.available):
            blocker_counts["bullpen_missing"] += 1
        else:
            blocker_counts["weather_missing"] += 1

    top_blocker = max(blocker_counts.items(), key=lambda kv: kv[1])[0]
    avg_latency = float(sum(latencies) / len(latencies)) if latencies else 0.0

    return WeatherScaleResult(
        strict_before=strict_before,
        strict_after=strict_after,
        batches_run=batches_run,
        api_calls=api_calls,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        avg_latency_ms=round(avg_latency, 2),
        newly_strict=max(0, strict_after - strict_before),
        status="TARGET_REACHED" if strict_after >= target_strict else "PARTIAL_PROGRESS",
        top_remaining_blocker=top_blocker,
        batch_history=batch_history,
    )
