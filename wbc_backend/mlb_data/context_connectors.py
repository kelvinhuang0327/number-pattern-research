from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .normalization import parse_ts


def _load_jsonl_latest(path: Path, key_field: str = "game_id") -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    latest: dict[str, dict[str, Any]] = {}
    latest_ts: dict[str, datetime | None] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        game_id = str(obj.get(key_field, "")).strip()
        if not game_id:
            continue
        ts = parse_ts(obj.get("fetched_at"))
        prev = latest_ts.get(game_id)
        if game_id not in latest or (ts is not None and (prev is None or ts >= prev)):
            latest[game_id] = obj
            latest_ts[game_id] = ts
    return latest


@dataclass(frozen=True)
class ConnectorBundle:
    lineups: dict[str, dict[str, Any]]
    bullpen: dict[str, dict[str, Any]]
    odds_timeline: dict[str, dict[str, Any]]
    weather_wind: dict[str, dict[str, Any]]
    injury_rest: dict[str, dict[str, Any]]


def load_connectors(context_dir: str | Path = "data/mlb_context") -> ConnectorBundle:
    root = Path(context_dir)
    return ConnectorBundle(
        lineups=_load_jsonl_latest(root / "lineups.jsonl"),
        bullpen=_load_jsonl_latest(root / "bullpen_usage_3d.jsonl"),
        odds_timeline=_load_jsonl_latest(root / "odds_timeline.jsonl"),
        weather_wind=_load_jsonl_latest(root / "weather_wind.jsonl"),
        injury_rest=_load_jsonl_latest(root / "injury_rest.jsonl"),
    )


def get_confirmed_lineups(bundle: ConnectorBundle, game_id: str) -> dict[str, Any]:
    return bundle.lineups.get(game_id, {})


def get_bullpen_usage_last_3d(bundle: ConnectorBundle, game_id: str) -> dict[str, Any]:
    return bundle.bullpen.get(game_id, {})


def get_odds_timeline(bundle: ConnectorBundle, game_id: str) -> dict[str, Any]:
    return bundle.odds_timeline.get(game_id, {})


def get_weather_wind(bundle: ConnectorBundle, game_id: str) -> dict[str, Any]:
    return bundle.weather_wind.get(game_id, {})


def get_injury_rest_status(bundle: ConnectorBundle, game_id: str) -> dict[str, Any]:
    return bundle.injury_rest.get(game_id, {})


def record_age_hours(record: dict[str, Any], now_utc: datetime | None = None) -> float | None:
    ts = parse_ts(record.get("fetched_at"))
    if ts is None:
        return None
    now = now_utc or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() / 3600.0


def is_stale_record(record: dict[str, Any], *, max_age_hours: float = 24.0, now_utc: datetime | None = None) -> bool:
    age = record_age_hours(record, now_utc=now_utc)
    if age is None:
        return True
    return age > max_age_hours
