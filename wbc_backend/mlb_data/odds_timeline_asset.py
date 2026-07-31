from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .ids import make_mlb_game_id


MLB_ZH_TO_EN = {
    "亞利桑那響尾蛇": "Arizona Diamondbacks",
    "亞歷桑那響尾蛇": "Arizona Diamondbacks",
    "亞特蘭大勇士": "Atlanta Braves",
    "巴爾的摩金鶯": "Baltimore Orioles",
    "波士頓紅襪": "Boston Red Sox",
    "芝加哥小熊": "Chicago Cubs",
    "芝加哥白襪": "Chicago White Sox",
    "辛辛那堤紅人": "Cincinnati Reds",
    "辛辛那提紅人": "Cincinnati Reds",
    "克里夫蘭守護者": "Cleveland Guardians",
    "科羅拉多洛磯": "Colorado Rockies",
    "底特律老虎": "Detroit Tigers",
    "休士頓太空人": "Houston Astros",
    "堪薩斯皇家": "Kansas City Royals",
    "洛杉磯天使": "Los Angeles Angels",
    "洛杉磯道奇": "Los Angeles Dodgers",
    "邁阿密馬林魚": "Miami Marlins",
    "密爾瓦基釀酒人": "Milwaukee Brewers",
    "明尼蘇達雙城": "Minnesota Twins",
    "紐約大都會": "New York Mets",
    "紐約洋基": "New York Yankees",
    "運動家": "Oakland Athletics",
    "費城費城人": "Philadelphia Phillies",
    "匹茲堡海盜": "Pittsburgh Pirates",
    "聖地牙哥教士": "San Diego Padres",
    "聖路易紅雀": "St. Louis Cardinals",
    "西雅圖水手": "Seattle Mariners",
    "舊金山巨人": "San Francisco Giants",
    "坦帕灣光芒": "Tampa Bay Rays",
    "德州遊騎兵": "Texas Rangers",
    "多倫多藍鳥": "Toronto Blue Jays",
    "華盛頓國民": "Washington Nationals",
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def _parse_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_et_date_time(game_time: str) -> tuple[str, str, datetime] | None:
    dt = _parse_ts(game_time)
    if dt is None:
        return None
    et = dt.astimezone(ZoneInfo("America/New_York"))
    return et.date().isoformat(), et.strftime("%I:%M %p").lstrip("0"), dt


def _decimal_to_american(value: Any) -> int | None:
    try:
        dec = float(value)
    except Exception:
        return None
    if dec <= 1.0:
        return None
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100.0))
    return int(round(-100.0 / (dec - 1.0)))


def _extract_mnl(record: dict[str, Any]) -> tuple[int | None, int | None]:
    home_name = str(record.get("home_team_name", ""))
    away_name = str(record.get("away_team_name", ""))
    for market in record.get("markets", []) or []:
        if str(market.get("marketCode", "")).upper() != "MNL":
            continue
        home_ml = None
        away_ml = None
        for out in market.get("outcomes", []) or []:
            name = str(out.get("outcomeName", ""))
            ml = _decimal_to_american(out.get("odds"))
            if name == home_name:
                home_ml = ml
            elif name == away_name:
                away_ml = ml
        return home_ml, away_ml
    return None, None


def _normalize_team_zh(name: str) -> str | None:
    return MLB_ZH_TO_EN.get(str(name).strip())


@dataclass(frozen=True)
class BuildSummary:
    source_records: int
    mlb_candidate_records: int
    canonical_games_written: int
    snapshots_written: int
    games_with_opening: int
    games_with_decision: int
    games_with_latest_pregame: int
    games_with_closing: int
    decision_lead_minutes: int
    output_path: str


def build_canonical_mlb_odds_timeline(
    *,
    source_path: str | Path = "data/tsl_odds_history.jsonl",
    output_path: str | Path = "data/mlb_context_sources/odds_timeline_canonical.jsonl",
    decision_lead_minutes: int = 60,
) -> BuildSummary:
    src = _load_jsonl(Path(source_path))
    grouped: dict[str, list[dict[str, Any]]] = {}
    mlb_candidates = 0
    snapshots = 0
    for row in src:
        home_en = _normalize_team_zh(str(row.get("home_team_name", "")))
        away_en = _normalize_team_zh(str(row.get("away_team_name", "")))
        if not home_en or not away_en:
            continue
        game_key = _to_et_date_time(str(row.get("game_time", "")))
        if game_key is None:
            continue
        et_date, et_start, game_start_utc = game_key
        ts = _parse_ts(row.get("fetched_at"))
        if ts is None:
            continue
        home_ml, away_ml = _extract_mnl(row)
        if home_ml is None or away_ml is None:
            continue
        mlb_candidates += 1
        gid = make_mlb_game_id(et_date, et_start, away_en, home_en)
        grouped.setdefault(gid, []).append(
            {
                "timestamp": ts.isoformat().replace("+00:00", "Z"),
                "home_ml": home_ml,
                "away_ml": away_ml,
                "source": str(row.get("source", "")),
                "book": "TSL",
                "market_type": "moneyline",
                "game_start_utc": game_start_utc.isoformat().replace("+00:00", "Z"),
                "home_team": home_en,
                "away_team": away_en,
            }
        )
        snapshots += 1

    records: list[dict[str, Any]] = []
    c_open = c_dec = c_pre = c_close = 0
    decision_cut = timedelta(minutes=max(0, int(decision_lead_minutes)))
    for gid, snaps in grouped.items():
        deduped = {
            (s["timestamp"], s["home_ml"], s["away_ml"], s["source"]): s
            for s in snaps
        }
        ordered = sorted(deduped.values(), key=lambda x: x["timestamp"])
        if not ordered:
            continue
        game_start = _parse_ts(ordered[0]["game_start_utc"])
        pregame = [s for s in ordered if game_start is None or _parse_ts(s["timestamp"]) <= game_start]
        if not pregame:
            pregame = ordered
        opening = pregame[0] if pregame else None
        latest = pregame[-1] if pregame else None
        decision = None
        if game_start is not None:
            cutoff = game_start - decision_cut
            candidates = [s for s in pregame if _parse_ts(s["timestamp"]) and _parse_ts(s["timestamp"]) <= cutoff]
            if candidates:
                decision = candidates[-1]
        unavailable: list[str] = []
        if opening is None:
            unavailable.append("opening_home_ml")
        if decision is None:
            unavailable.append("decision_home_ml")
        if latest is None:
            unavailable.append("latest_pregame_home_ml")
        if latest is None:
            unavailable.append("closing_home_ml")
        rec = {
            "game_id": gid,
            "source": "tsl_odds_history.jsonl",
            "book": "TSL",
            "market_type": "moneyline",
            "opening_home_ml": opening["home_ml"] if opening else None,
            "opening_away_ml": opening["away_ml"] if opening else None,
            "decision_home_ml": decision["home_ml"] if decision else None,
            "decision_away_ml": decision["away_ml"] if decision else None,
            "latest_pregame_home_ml": latest["home_ml"] if latest else None,
            "latest_pregame_away_ml": latest["away_ml"] if latest else None,
            "closing_home_ml": latest["home_ml"] if latest else None,
            "closing_away_ml": latest["away_ml"] if latest else None,
            "opening_ts": opening["timestamp"] if opening else None,
            "decision_ts": decision["timestamp"] if decision else None,
            "latest_pregame_ts": latest["timestamp"] if latest else None,
            "closing_ts": latest["timestamp"] if latest else None,
            "odds_history": [
                {
                    "ts": s["timestamp"],
                    "home_ml": s["home_ml"],
                    "away_ml": s["away_ml"],
                    "source": s["source"],
                    "book": s["book"],
                    "snapshot_type": "pregame",
                }
                for s in pregame
            ],
            "fetched_at": latest["timestamp"] if latest else ordered[-1]["timestamp"],
            "snapshot_count": len(ordered),
            "pregame_snapshot_count": len(pregame),
            "unavailable_fields": unavailable,
        }
        records.append(rec)
        c_open += int(rec["opening_home_ml"] is not None)
        c_dec += int(rec["decision_home_ml"] is not None)
        c_pre += int(rec["latest_pregame_home_ml"] is not None)
        c_close += int(rec["closing_home_ml"] is not None)

    records.sort(key=lambda r: str(r.get("game_id", "")))
    _write_jsonl(Path(output_path), records)
    return BuildSummary(
        source_records=len(src),
        mlb_candidate_records=mlb_candidates,
        canonical_games_written=len(records),
        snapshots_written=snapshots,
        games_with_opening=c_open,
        games_with_decision=c_dec,
        games_with_latest_pregame=c_pre,
        games_with_closing=c_close,
        decision_lead_minutes=int(decision_lead_minutes),
        output_path=str(output_path),
    )


def build_tsl_mlb_pregame_coverage_report(
    *,
    source_path: str | Path = "data/tsl_odds_history.jsonl",
    report_path: str | Path | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """Generate a MLB-specific pregame snapshot coverage QA report from tsl_odds_history.jsonl.

    Reads the raw JSONL, filters for MLB games only (using MLB_ZH_TO_EN mapping),
    and produces:
    - Total MLB games seen
    - Pregame vs postgame snapshot counts
    - Per-game pregame snapshot count distribution (0 / 1 / 2+)
    - Games with line movement (odds changed across pregame snapshots)
    - Today's new snapshots (if as_of_date provided)
    - Dedup stats (unique vs total records)
    """
    src = _load_jsonl(Path(source_path))
    total_records = len(src)

    # Filter to MLB-only records using MLB_ZH_TO_EN as the detection mechanism
    mlb_records = [
        r for r in src
        if _normalize_team_zh(str(r.get("home_team_name", ""))) is not None
        or _normalize_team_zh(str(r.get("away_team_name", ""))) is not None
    ]

    # Group by canonical match key: (home_en, away_en, game_time_date)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in mlb_records:
        home_en = _normalize_team_zh(str(row.get("home_team_name", ""))) or str(row.get("home_team_name", ""))
        away_en = _normalize_team_zh(str(row.get("away_team_name", ""))) or str(row.get("away_team_name", ""))
        game_key = _to_et_date_time(str(row.get("game_time", "")))
        if game_key is None:
            continue
        et_date = game_key[0]
        key = f"{et_date}|{away_en}@{home_en}"
        grouped.setdefault(key, []).append(row)

    # Per-game analysis
    per_game: list[dict[str, Any]] = []
    total_postgame = 0
    total_pregame_records = 0
    games_with_movement = 0
    snapshot_count_dist: dict[str, int] = {"0": 0, "1": 0, "2": 0, "3+": 0}

    for game_key, rows in grouped.items():
        game_time_str = str(rows[0].get("game_time", ""))
        game_start_utc = _parse_ts(game_time_str)

        pregame_rows = []
        postgame_rows = []
        for row in rows:
            ts = _parse_ts(str(row.get("fetched_at", "")))
            if ts is None:
                continue
            if game_start_utc is None or ts <= game_start_utc:
                pregame_rows.append(row)
            else:
                postgame_rows.append(row)

        total_pregame_records += len(pregame_rows)
        total_postgame += len(postgame_rows)

        # Dedup pregame by (timestamp, home_ml, away_ml) to count unique price events
        unique_prices: set[tuple[int | None, int | None]] = set()
        for row in pregame_rows:
            home_ml, away_ml = _extract_mnl(row)
            if home_ml is not None:
                unique_prices.add((home_ml, away_ml))

        unique_pregame_count = len(unique_prices)
        has_movement = unique_pregame_count >= 2

        if unique_pregame_count == 0:
            snapshot_count_dist["0"] += 1
        elif unique_pregame_count == 1:
            snapshot_count_dist["1"] += 1
        elif unique_pregame_count == 2:
            snapshot_count_dist["2"] += 1
        else:
            snapshot_count_dist["3+"] += 1

        if has_movement:
            games_with_movement += 1

        et_date, game_label = game_key.split("|")
        per_game.append({
            "game_key": game_key,
            "game_date_et": et_date,
            "matchup": game_label,
            "game_time_utc": game_start_utc.isoformat().replace("+00:00", "Z") if game_start_utc else None,
            "total_records": len(rows),
            "pregame_records": len(pregame_rows),
            "postgame_records": len(postgame_rows),
            "unique_pregame_price_events": unique_pregame_count,
            "has_line_movement": has_movement,
        })

    total_games = len(grouped)
    today_new = 0
    if as_of_date:
        today_new = sum(
            1 for r in mlb_records
            if str(r.get("fetched_at", "")).startswith(as_of_date)
        )

    # Unique records across all (match_id, fetched_at, home_ml) combos for dedup rate
    seen_keys: set[tuple[str, str]] = set()
    dupes = 0
    for r in mlb_records:
        home_ml, _ = _extract_mnl(r)
        key_tuple = (str(r.get("match_id", "")), str(r.get("fetched_at", "")))
        if key_tuple in seen_keys:
            dupes += 1
        seen_keys.add(key_tuple)

    per_game.sort(key=lambda x: x["game_date_et"])

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_path": str(source_path),
        "scope": "MLB_only",
        "as_of_date": as_of_date,
        "totals": {
            "total_jsonl_records": total_records,
            "mlb_records": len(mlb_records),
            "mlb_games": total_games,
            "pregame_records": total_pregame_records,
            "postgame_records": total_postgame,
            "new_records_today": today_new,
            "duplicate_records": dupes,
            "dedup_rate": round(1.0 - dupes / max(1, len(mlb_records)), 4),
        },
        "pregame_coverage": {
            "games_with_0_pregame_snapshots": snapshot_count_dist["0"],
            "games_with_1_pregame_snapshot": snapshot_count_dist["1"],
            "games_with_2_pregame_snapshots": snapshot_count_dist["2"],
            "games_with_3plus_pregame_snapshots": snapshot_count_dist["3+"],
            "games_with_any_pregame": total_games - snapshot_count_dist["0"],
            "games_with_multi_snapshot": snapshot_count_dist["2"] + snapshot_count_dist["3+"],
            "pregame_coverage_rate": round(
                (total_games - snapshot_count_dist["0"]) / max(1, total_games), 4
            ),
            "multi_snapshot_rate": round(
                (snapshot_count_dist["2"] + snapshot_count_dist["3+"]) / max(1, total_games), 4
            ),
        },
        "line_movement": {
            "games_with_movement": games_with_movement,
            "movement_rate": round(games_with_movement / max(1, total_games), 4),
        },
        "per_game": per_game,
        "data_status": (
            "NO_MLB_DATA" if total_games == 0
            else "COLLECTION_ACTIVE" if total_pregame_records > 0
            else "MLB_DETECTED_NO_PREGAME"
        ),
    }

    if report_path is not None:
        out = Path(report_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


def build_mlb_odds_timeline_qa_report(
    *,
    canonical_path: str | Path = "data/mlb_context_sources/odds_timeline_canonical.jsonl",
    csv_path: str | Path = "data/mlb_2025/mlb_odds_2025_real.csv",
) -> dict[str, Any]:
    rows = _load_jsonl(Path(canonical_path))
    total = len(rows)
    if total == 0:
        return {
            "total_games": 0,
            "availability": {},
            "timestamp_monotonic_failures": 0,
            "duplicate_snapshot_rows": 0,
            "mapping_success_rate_to_csv": 0.0,
        }
    avail = {
        "opening": sum(1 for r in rows if r.get("opening_home_ml") is not None),
        "decision": sum(1 for r in rows if r.get("decision_home_ml") is not None),
        "latest_pregame": sum(1 for r in rows if r.get("latest_pregame_home_ml") is not None),
        "closing": sum(1 for r in rows if r.get("closing_home_ml") is not None),
    }
    monotonic_fail = 0
    dupes = 0
    for r in rows:
        hist = r.get("odds_history") or []
        seen: set[tuple[Any, Any, Any]] = set()
        last_ts = ""
        for s in hist:
            key = (s.get("ts"), s.get("home_ml"), s.get("away_ml"))
            if key in seen:
                dupes += 1
            seen.add(key)
            ts = str(s.get("ts", ""))
            if last_ts and ts < last_ts:
                monotonic_fail += 1
                break
            last_ts = ts
    csv = pd.read_csv(csv_path)
    csv_ids = set(
        csv.apply(
            lambda r: make_mlb_game_id(
                str(r.get("Date", "")),
                str(r.get("Start Time (EDT)", "")),
                str(r.get("Away", "")),
                str(r.get("Home", "")),
            ),
            axis=1,
        )
    )
    mapped = sum(1 for r in rows if str(r.get("game_id", "")) in csv_ids)
    return {
        "total_games": total,
        "availability": {
            "opening_rate": round(avail["opening"] / total, 4),
            "decision_rate": round(avail["decision"] / total, 4),
            "latest_pregame_rate": round(avail["latest_pregame"] / total, 4),
            "closing_rate": round(avail["closing"] / total, 4),
            "opening_count": avail["opening"],
            "decision_count": avail["decision"],
            "latest_pregame_count": avail["latest_pregame"],
            "closing_count": avail["closing"],
        },
        "timestamp_monotonic_failures": monotonic_fail,
        "duplicate_snapshot_rows": dupes,
        "mapping_success_rate_to_csv": round(mapped / max(1, total), 4),
        "mapped_games_to_csv": mapped,
        "unmapped_games_to_csv": total - mapped,
    }
