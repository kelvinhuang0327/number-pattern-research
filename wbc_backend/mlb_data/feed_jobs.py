from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .ids import make_mlb_game_id
from .ingestion import load_mlb_game_data
from .validator import validate_mlb_game_data
from .health_report import build_health_report
from .external_sources import fetch_and_materialize_external_context
from .normalization import parse_ts


@dataclass(frozen=True)
class FeedResult:
    feed_name: str
    output_file: str
    total_records_written: int
    matched_game_id_count: int
    unmatched_count: int
    stale_count: int
    duplicate_resolution_count: int
    missing_required_field_count: int
    failures: int


@dataclass(frozen=True)
class SourceAuditRow:
    feed_name: str
    source: str
    source_type: str
    in_repo: bool
    available: bool
    coverage_estimate: float
    reliability: str
    historical_availability: str
    notes: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_game_index(csv_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    for col in ("Date", "Start Time (EDT)", "Away", "Home"):
        if col not in df.columns:
            raise ValueError(f"missing column in mlb csv: {col}")
    df = df.copy()
    df["game_id"] = df.apply(
        lambda r: make_mlb_game_id(
            str(r.get("Date", "")),
            str(r.get("Start Time (EDT)", "")),
            str(r.get("Away", "")),
            str(r.get("Home", "")),
        ),
        axis=1,
    )
    return df


def _dedupe_latest(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_id: dict[str, dict[str, Any]] = {}
    dupes = 0
    for rec in records:
        gid = rec["game_id"]
        if gid in by_id:
            dupes += 1
            prev_ts = by_id[gid].get("fetched_at", "")
            cur_ts = rec.get("fetched_at", "")
            if cur_ts >= prev_ts:
                by_id[gid] = rec
        else:
            by_id[gid] = rec
    return list(by_id.values()), dupes


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


def _resolve_game_id(record: dict[str, Any]) -> str:
    gid = str(record.get("game_id", "")).strip()
    if gid:
        return gid
    game_date = str(record.get("game_date", "") or record.get("date", "")).strip()
    start = str(record.get("start_time", "") or record.get("game_time", "")).strip()
    away = str(record.get("away_team", "") or record.get("away_team_name", "")).strip()
    home = str(record.get("home_team", "") or record.get("home_team_name", "")).strip()
    if not (game_date and away and home):
        return ""
    return make_mlb_game_id(game_date[:10], start[11:19] if "T" in start else start, away, home)


def _parse_american_ml(value: Any) -> int | None:
    if value is None:
        return None
    token = str(value).strip()
    if token == "":
        return None
    if token.startswith("+"):
        token = token[1:]
    try:
        ml = int(float(token))
    except Exception:
        return None
    # American odds typically have magnitude >= 100. We do not coerce decimal odds.
    if abs(ml) < 100:
        return None
    return ml


def _derive_game_start_utc(row: pd.Series) -> datetime | None:
    game_date = str(row.get("Date", "")).strip()
    start_time = str(row.get("Start Time (EDT)", "")).strip()
    if not game_date or not start_time:
        return None
    try:
        # Dataset is explicitly EDT in source column name.
        local = datetime.strptime(f"{game_date} {start_time}", "%Y-%m-%d %I:%M %p")
        return local.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_odds_history(raw_history: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(raw_history, list):
        return [], ["history_missing_or_not_list"]
    normalized: list[dict[str, Any]] = []
    issues: list[str] = []
    for item in raw_history:
        if not isinstance(item, dict):
            issues.append("history_item_not_object")
            continue
        ts = item.get("ts") or item.get("captured_at") or item.get("fetched_at")
        ts_parsed = parse_ts(str(ts)) if ts else None
        if ts_parsed is None:
            issues.append("history_missing_ts")
            continue
        home_ml = _parse_american_ml(item.get("home_ml"))
        away_ml = _parse_american_ml(item.get("away_ml"))
        if home_ml is None and away_ml is None:
            issues.append("history_missing_ml")
            continue
        normalized.append(
            {
                "ts": ts_parsed.isoformat().replace("+00:00", "Z"),
                "home_ml": home_ml,
                "away_ml": away_ml,
                "source": item.get("source"),
                "snapshot_type": item.get("snapshot_type"),
            }
        )
    normalized.sort(key=lambda x: x["ts"])
    for i in range(1, len(normalized)):
        if normalized[i]["ts"] < normalized[i - 1]["ts"]:
            issues.append("history_out_of_order")
            break
    return normalized, sorted(set(issues))


def _source_candidates() -> dict[str, list[Path]]:
    return {
        "lineups": [
            Path("data/mlb_context_sources/confirmed_lineups.jsonl"),
        ],
        "bullpen_usage_3d": [
            Path("data/mlb_context_sources/bullpen_usage_3d.jsonl"),
        ],
        "odds_timeline": [
            Path("data/mlb_context/odds_timeline.jsonl"),
            Path("data/mlb_context_sources/odds_timeline_canonical.jsonl"),
            Path("data/mlb_context_sources/odds_timeline.jsonl"),
            Path("data/tsl_odds_history.jsonl"),
        ],
        "weather_wind": [
            Path("data/mlb_context_sources/weather_wind.jsonl"),
        ],
        "injury_rest": [
            Path("data/mlb_context_sources/injury_rest.jsonl"),
        ],
    }


def build_source_audit(df: pd.DataFrame) -> list[dict[str, Any]]:
    total_games = max(1, len(df))
    results: list[SourceAuditRow] = []
    for feed, paths in _source_candidates().items():
        for p in paths:
            exists = p.exists()
            rows = _load_jsonl(p) if exists else []
            matched = 0
            for r in rows:
                if _resolve_game_id(r):
                    matched += 1
            coverage = min(1.0, matched / total_games) if rows else 0.0
            if not exists:
                reliability = "missing"
                hist = "none"
                notes = "missing upstream source; external integration required"
            elif rows and coverage >= 0.85:
                reliability = "high"
                hist = "good"
                notes = "ready for strict-tier feed generation"
            elif rows and coverage >= 0.4:
                reliability = "medium"
                hist = "partial"
                notes = "partial coverage; strict tier may remain blocked"
            else:
                reliability = "low"
                hist = "limited"
                notes = "insufficient matched historical records"
            results.append(
                SourceAuditRow(
                    feed_name=feed,
                    source=str(p),
                    source_type="jsonl_file",
                    in_repo=True,
                    available=exists,
                    coverage_estimate=round(coverage, 4),
                    reliability=reliability,
                    historical_availability=hist,
                    notes=notes,
                )
            )
    return [r.__dict__ for r in results]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")


def _feed_summary(
    *,
    feed_name: str,
    output_file: Path,
    records: list[dict[str, Any]],
    required_fields: tuple[str, ...],
    duplicate_resolution_count: int,
    failures: int,
) -> FeedResult:
    missing_required = 0
    unmatched = 0
    stale = 0
    now = datetime.now(timezone.utc)
    for rec in records:
        if not rec.get("game_id"):
            unmatched += 1
        for field in required_fields:
            if rec.get(field) in (None, "", [], {}):
                missing_required += 1
        ts = rec.get("fetched_at")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if (now - dt).total_seconds() > 24 * 3600:
                    stale += 1
            except Exception:
                stale += 1
        else:
            stale += 1
    return FeedResult(
        feed_name=feed_name,
        output_file=str(output_file),
        total_records_written=len(records),
        matched_game_id_count=len(records) - unmatched,
        unmatched_count=unmatched,
        stale_count=stale,
        duplicate_resolution_count=duplicate_resolution_count,
        missing_required_field_count=missing_required,
        failures=failures,
    )


def generate_lineups_feed(df: pd.DataFrame, output_path: Path) -> FeedResult:
    fetched_at = _now_iso()
    records = []
    external_rows = _load_jsonl(Path("data/mlb_context_sources/confirmed_lineups.jsonl"))
    external_by_gid = {}
    for r in external_rows:
        gid = _resolve_game_id(r)
        if gid:
            external_by_gid[gid] = r
    for _, row in df.iterrows():
        ext = external_by_gid.get(row["game_id"], {})
        records.append(
            {
                "game_id": row["game_id"],
                "confirmed_home_starter": ext.get("confirmed_home_starter"),
                "confirmed_away_starter": ext.get("confirmed_away_starter"),
                "confirmed_home_lineup": ext.get("confirmed_home_lineup"),
                "confirmed_away_lineup": ext.get("confirmed_away_lineup"),
                "home_away_splits": ext.get("home_away_splits"),
                "platoon_splits": ext.get("platoon_splits"),
                "fetched_at": ext.get("fetched_at") or fetched_at,
                "source": ext.get("source", "mlb_context_sources/confirmed_lineups.jsonl"),
                "unavailable_fields": [
                    field
                    for field in (
                        "confirmed_home_starter",
                        "confirmed_away_starter",
                        "confirmed_home_lineup",
                        "confirmed_away_lineup",
                        "home_away_splits",
                        "platoon_splits",
                    )
                    if ext.get(field) in (None, "", [], {})
                ],
            }
        )
    deduped, dupes = _dedupe_latest(records)
    _write_jsonl(output_path, deduped)
    return _feed_summary(
        feed_name="lineups",
        output_file=output_path,
        records=deduped,
        required_fields=("game_id", "fetched_at"),
        duplicate_resolution_count=dupes,
        failures=0,
    )


def generate_bullpen_usage_feed(df: pd.DataFrame, output_path: Path) -> FeedResult:
    fetched_at = _now_iso()
    records = []
    external_rows = _load_jsonl(Path("data/mlb_context_sources/bullpen_usage_3d.jsonl"))
    external_by_gid = {}
    for r in external_rows:
        gid = _resolve_game_id(r)
        if gid:
            external_by_gid[gid] = r
    for _, row in df.iterrows():
        ext = external_by_gid.get(row["game_id"], {})
        records.append(
            {
                "game_id": row["game_id"],
                "bullpen_usage_last_3d_home": ext.get("bullpen_usage_last_3d_home"),
                "bullpen_usage_last_3d_away": ext.get("bullpen_usage_last_3d_away"),
                "fetched_at": ext.get("fetched_at") or fetched_at,
                "source": ext.get("source", "mlb_context_sources/bullpen_usage_3d.jsonl"),
                "unavailable_fields": [
                    field
                    for field in ("bullpen_usage_last_3d_home", "bullpen_usage_last_3d_away")
                    if ext.get(field) in (None, "", [], {})
                ],
            }
        )
    deduped, dupes = _dedupe_latest(records)
    _write_jsonl(output_path, deduped)
    return _feed_summary(
        feed_name="bullpen_usage_3d",
        output_file=output_path,
        records=deduped,
        required_fields=("game_id", "fetched_at"),
        duplicate_resolution_count=dupes,
        failures=0,
    )


def generate_odds_timeline_feed(df: pd.DataFrame, output_path: Path, tsl_history_path: str | Path = "data/tsl_odds_history.jsonl") -> FeedResult:
    fetched_at = _now_iso()
    records = []
    timeline_by_game: dict[str, dict[str, Any]] = {}

    # Priority 1: canonical (static) — base layer
    canonical_timeline = Path("data/mlb_context_sources/odds_timeline_canonical.jsonl")
    if canonical_timeline.exists():
        for obj in _load_jsonl(canonical_timeline):
            gid = _resolve_game_id(obj)
            if not gid:
                continue
            prev = timeline_by_game.get(gid)
            if prev is None or str(obj.get("fetched_at", "")) >= str(prev.get("fetched_at", "")):
                timeline_by_game[gid] = obj

    # Priority 2: live collector — overrides canonical when richer data exists
    live_timeline = Path("data/mlb_context/odds_timeline.jsonl")
    if live_timeline.exists():
        for obj in _load_jsonl(live_timeline):
            gid = _resolve_game_id(obj)
            if not gid:
                continue
            live_history = obj.get("odds_history") or []
            prev = timeline_by_game.get(gid)
            prev_history = (prev.get("odds_history") or []) if prev else []
            # Use live data if it has more snapshots or has decision_ts
            if (len(live_history) > len(prev_history)
                    or (obj.get("decision_ts") and not (prev or {}).get("decision_ts"))):
                timeline_by_game[gid] = obj
    for _, row in df.iterrows():
        key = row["game_id"]
        ext = timeline_by_game.get(key, {})
        ext_history, ext_issues = _normalize_odds_history(ext.get("odds_history"))
        time_issues = list(ext_issues)
        rec = {
            "game_id": key,
            "opening_home_ml": _parse_american_ml(ext.get("opening_home_ml")),
            "opening_away_ml": _parse_american_ml(ext.get("opening_away_ml")),
            "current_home_ml": _parse_american_ml(ext.get("current_home_ml")),
            "current_away_ml": _parse_american_ml(ext.get("current_away_ml")),
            "decision_home_ml": _parse_american_ml(ext.get("decision_home_ml")),
            "decision_away_ml": _parse_american_ml(ext.get("decision_away_ml")),
            "latest_pregame_home_ml": _parse_american_ml(ext.get("latest_pregame_home_ml")),
            "latest_pregame_away_ml": _parse_american_ml(ext.get("latest_pregame_away_ml")),
            "closing_home_ml": _parse_american_ml(ext.get("closing_home_ml")),
            "closing_away_ml": _parse_american_ml(ext.get("closing_away_ml")),
            "odds_history": ext_history if ext_history else None,
            "opening_ts": ext.get("opening_ts"),
            "decision_ts": ext.get("decision_ts"),
            "latest_pregame_ts": ext.get("latest_pregame_ts"),
            "closing_ts": ext.get("closing_ts"),
            "fetched_at": ext.get("fetched_at") or fetched_at,
            "source": ext.get("source", "mlb_context_sources/odds_timeline_canonical.jsonl"),
        }
        if not ext:
            time_issues.append("canonical_timeline_unavailable")
        rec["unavailable_fields"] = [
            field
            for field in (
                "opening_home_ml",
                "opening_away_ml",
                "decision_home_ml",
                "decision_away_ml",
                "latest_pregame_home_ml",
                "latest_pregame_away_ml",
                "current_home_ml",
                "current_away_ml",
                "odds_history",
            )
            if rec.get(field) in (None, "", [], {})
        ]
        rec["timeline_issues"] = time_issues
        records.append(rec)
    deduped, dupes = _dedupe_latest(records)
    _write_jsonl(output_path, deduped)
    return _feed_summary(
        feed_name="odds_timeline",
        output_file=output_path,
        records=deduped,
        required_fields=("game_id", "fetched_at", "closing_home_ml", "closing_away_ml"),
        duplicate_resolution_count=dupes,
        failures=0,
    )


def generate_weather_wind_feed(df: pd.DataFrame, output_path: Path) -> FeedResult:
    fetched_at = _now_iso()
    records = []
    external_rows = _load_jsonl(Path("data/mlb_context_sources/weather_wind.jsonl"))
    external_by_gid = {}
    for r in external_rows:
        gid = _resolve_game_id(r)
        if gid:
            external_by_gid[gid] = r
    for _, row in df.iterrows():
        ext = external_by_gid.get(row["game_id"], {})
        records.append(
            {
                "game_id": row["game_id"],
                "weather": ext.get("weather"),
                "wind": ext.get("wind"),
                "park_factors": ext.get("park_factors"),
                "fetched_at": ext.get("fetched_at") or fetched_at,
                "source": ext.get("source", "mlb_context_sources/weather_wind.jsonl"),
                "unavailable_fields": [
                    field for field in ("weather", "wind", "park_factors") if ext.get(field) in (None, "", [], {})
                ],
            }
        )
    deduped, dupes = _dedupe_latest(records)
    _write_jsonl(output_path, deduped)
    return _feed_summary(
        feed_name="weather_wind",
        output_file=output_path,
        records=deduped,
        required_fields=("game_id", "fetched_at"),
        duplicate_resolution_count=dupes,
        failures=0,
    )


def generate_injury_rest_feed(df: pd.DataFrame, output_path: Path) -> FeedResult:
    fetched_at = _now_iso()
    records = []
    external_rows = _load_jsonl(Path("data/mlb_context_sources/injury_rest.jsonl"))
    external_by_gid = {}
    for r in external_rows:
        gid = _resolve_game_id(r)
        if gid:
            external_by_gid[gid] = r
    team_last_date: dict[str, str] = {}
    for _, row in df.sort_values("Date").iterrows():
        date = str(row.get("Date", ""))
        home = str(row.get("Home", ""))
        away = str(row.get("Away", ""))
        ext = external_by_gid.get(row["game_id"], {})
        home_rest = None
        away_rest = None
        if team_last_date.get(home):
            home_rest = max(0, (pd.to_datetime(date) - pd.to_datetime(team_last_date[home])).days - 1)
        if team_last_date.get(away):
            away_rest = max(0, (pd.to_datetime(date) - pd.to_datetime(team_last_date[away])).days - 1)
        records.append(
            {
                "game_id": row["game_id"],
                "injury_report": ext.get("injury_report"),
                "rest_days_home": ext.get("rest_days_home", home_rest),
                "rest_days_away": ext.get("rest_days_away", away_rest),
                "fetched_at": ext.get("fetched_at") or fetched_at,
                "source": ext.get("source", "mlb_context_sources/injury_rest.jsonl + schedule_rest_calc"),
                "unavailable_fields": [
                    field
                    for field in ("injury_report", "rest_days_home", "rest_days_away")
                    if (
                        (field == "injury_report" and ext.get("injury_report") in (None, "", [], {}))
                        or (field == "rest_days_home" and (ext.get("rest_days_home", home_rest) is None))
                        or (field == "rest_days_away" and (ext.get("rest_days_away", away_rest) is None))
                    )
                ],
            }
        )
        team_last_date[home] = date
        team_last_date[away] = date
    deduped, dupes = _dedupe_latest(records)
    _write_jsonl(output_path, deduped)
    return _feed_summary(
        feed_name="injury_rest",
        output_file=output_path,
        records=deduped,
        required_fields=("game_id", "fetched_at", "rest_days_home", "rest_days_away"),
        duplicate_resolution_count=dupes,
        failures=0,
    )


def _validation_snapshot(csv_path: str | Path, context_dir: Path) -> dict[str, Any]:
    rows = load_mlb_game_data(csv_path=csv_path, context_path=context_dir)
    validation = validate_mlb_game_data(rows)
    report = build_health_report(rows, validation)
    return {
        "strict_valid_games": validation.strict_valid_games,
        "research_valid_games": validation.research_valid_games,
        "invalid_games": validation.invalid_games,
        "strict_valid_rate": report["strict_valid_rate"],
        "availability_pct": report["availability_pct"],
    }


def run_all_feed_jobs(
    csv_path: str | Path = "data/mlb_2025/mlb_odds_2025_real.csv",
    output_dir: str | Path = "data/mlb_context",
    refresh_external: bool = False,
) -> dict[str, Any]:
    df = _build_game_index(csv_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    external_summary = None
    if refresh_external:
        external_summary = fetch_and_materialize_external_context(
            csv_path=csv_path,
            output_dir="data/mlb_context_sources",
            start_date=str(df["Date"].min()),
            end_date=str(df["Date"].max()),
        ).__dict__
    source_audit = build_source_audit(df)
    ordered_jobs = [
        ("lineups", generate_lineups_feed, out / "lineups.jsonl"),
        ("bullpen_usage_3d", generate_bullpen_usage_feed, out / "bullpen_usage_3d.jsonl"),
        ("odds_timeline", generate_odds_timeline_feed, out / "odds_timeline.jsonl"),
        ("weather_wind", generate_weather_wind_feed, out / "weather_wind.jsonl"),
        ("injury_rest", generate_injury_rest_feed, out / "injury_rest.jsonl"),
    ]
    results: list[FeedResult] = []
    before = _validation_snapshot(csv_path, out)
    impact: list[dict[str, Any]] = []
    prev = before
    for name, fn, path in ordered_jobs:
        if name == "odds_timeline":
            res = fn(df, path)
        else:
            res = fn(df, path)
        results.append(res)
        after = _validation_snapshot(csv_path, out)
        impact.append(
            {
                "feed": name,
                "strict_valid_rate_before": prev["strict_valid_rate"],
                "strict_valid_rate_after": after["strict_valid_rate"],
                "strict_valid_delta": round(after["strict_valid_rate"] - prev["strict_valid_rate"], 4),
                "strict_valid_games_before": prev["strict_valid_games"],
                "strict_valid_games_after": after["strict_valid_games"],
                "newly_unlocked_fields": [
                    k
                    for k, v in after["availability_pct"].items()
                    if v > prev["availability_pct"].get(k, 0.0)
                ],
                "remaining_blockers": [
                    k for k, v in after["availability_pct"].items() if v < 0.85
                ],
            }
        )
        prev = after
    final_snapshot = _validation_snapshot(csv_path, out)
    summary = {
        "fetched_at": _now_iso(),
        "csv_path": str(csv_path),
        "output_dir": str(output_dir),
        "external_refresh": external_summary,
        "source_audit": source_audit,
        "feeds": [r.__dict__ for r in results],
        "strict_validation_recovery": {
            "before": before,
            "after": final_snapshot,
        },
        "feed_impact_tracking": impact,
        "total_failures": int(sum(r.failures for r in results)),
    }
    return summary
