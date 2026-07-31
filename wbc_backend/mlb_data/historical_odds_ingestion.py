from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .ids import make_mlb_game_id
from .normalization import canonical_team_name, parse_ts


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _american(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    if text.startswith("+"):
        text = text[1:]
    try:
        ml = int(float(text))
    except Exception:
        return None
    if abs(ml) < 100:
        return None
    return ml


def _utc_et_pair(date_text: str, start_text: str) -> tuple[datetime, str]:
    local = datetime.strptime(f"{date_text} {start_text}", "%Y-%m-%d %I:%M %p")
    et = local.replace(tzinfo=ZoneInfo("America/New_York"))
    return et.astimezone(timezone.utc), et.strftime("%I:%M %p").lstrip("0")


def _game_index(csv_path: str | Path) -> dict[str, dict[str, Any]]:
    df = pd.read_csv(csv_path)
    out: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        game_id = make_mlb_game_id(
            str(row.get("Date", "")),
            str(row.get("Start Time (EDT)", "")),
            str(row.get("Away", "")),
            str(row.get("Home", "")),
        )
        start_utc, start_et = _utc_et_pair(str(row.get("Date", "")), str(row.get("Start Time (EDT)", "")))
        out[game_id] = {
            "game_id": game_id,
            "date": str(row.get("Date", "")),
            "start_time_et": start_et,
            "start_utc": start_utc,
            "away": str(row.get("Away", "")),
            "home": str(row.get("Home", "")),
        }
    return out


def _safe_http_json(url: str) -> Any:
    try:
        with urllib.request.urlopen(url, timeout=20) as res:  # nosec - controlled URLs
            return json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def _normalize_history_item(item: dict[str, Any], *, default_source: str, default_book: str, row_fetched_at: str) -> dict[str, Any] | None:
    ts = parse_ts(str(item.get("ts") or item.get("timestamp") or item.get("captured_at") or item.get("fetched_at") or ""))
    if ts is None:
        return None
    home_ml = _american(item.get("home_ml"))
    away_ml = _american(item.get("away_ml"))
    if home_ml is None and away_ml is None:
        return None
    return {
        "ts": ts.isoformat().replace("+00:00", "Z"),
        "home_ml": home_ml,
        "away_ml": away_ml,
        "bookmaker": item.get("bookmaker") or item.get("book") or default_book,
        "market_type": "moneyline",
        "source": item.get("source") or default_source,
        "fetched_at": row_fetched_at,
        "snapshot_type": item.get("snapshot_type") or "snapshot",
    }


def _timeline_from_row(row: dict[str, Any], *, source_name: str) -> list[dict[str, Any]]:
    fetched_at = str(row.get("fetched_at", ""))
    snaps: list[dict[str, Any]] = []
    raw_history = row.get("odds_history")
    if isinstance(raw_history, list):
        for item in raw_history:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_history_item(
                item,
                default_source=source_name,
                default_book=str(row.get("book") or row.get("bookmaker") or source_name),
                row_fetched_at=fetched_at,
            )
            if normalized:
                snaps.append(normalized)
    if not snaps:
        ts = parse_ts(fetched_at)
        if ts is not None:
            home_ml = _american(row.get("decision_home_ml"))
            away_ml = _american(row.get("decision_away_ml"))
            if home_ml is None and away_ml is None:
                home_ml = _american(row.get("latest_pregame_home_ml"))
                away_ml = _american(row.get("latest_pregame_away_ml"))
            if home_ml is None and away_ml is None:
                home_ml = _american(row.get("opening_home_ml"))
                away_ml = _american(row.get("opening_away_ml"))
            if home_ml is None and away_ml is None:
                home_ml = _american(row.get("closing_home_ml"))
                away_ml = _american(row.get("closing_away_ml"))
            if home_ml is not None or away_ml is not None:
                snaps.append(
                    {
                        "ts": ts.isoformat().replace("+00:00", "Z"),
                        "home_ml": home_ml,
                        "away_ml": away_ml,
                        "bookmaker": str(row.get("book") or row.get("bookmaker") or source_name),
                        "market_type": "moneyline",
                        "source": source_name,
                        "fetched_at": fetched_at,
                        "snapshot_type": "single_point",
                    }
                )
    return snaps


def _load_local_source_rows(source_paths: list[Path] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if source_paths is None:
        source_paths = [
            Path("data/mlb_context_sources/odds_timeline_canonical.jsonl"),
            Path("data/mlb_context_sources/odds_timeline.jsonl"),
            Path("data/tsl_odds_history.jsonl"),
        ]
    for source_path in source_paths:
        source_name = source_path.name
        for r in _read_jsonl(source_path):
            if source_path.name == "tsl_odds_history.jsonl":
                # TSL raw feed usually does not overlap MLB-2025 IDs; keep only rows that can be keyed.
                gid = str(r.get("game_id", "")).strip()
                if not gid.startswith("MLB-"):
                    continue
                row = {"game_id": gid, "fetched_at": r.get("fetched_at"), "odds_history": r.get("odds_history"), "source": source_name}
            else:
                row = dict(r)
                row["source"] = row.get("source") or source_name
            rows.append(row)
    return rows


def _fetch_the_odds_api_live() -> list[dict[str, Any]]:
    api_key = os.getenv("ODDS_API_KEY", "").strip()
    if not api_key:
        return []
    params = urllib.parse.urlencode(
        {
            "apiKey": api_key,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "american",
        }
    )
    data = _safe_http_json(f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds?{params}")
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    fetched_at = _now_iso()
    for g in data:
        commence = parse_ts(str(g.get("commence_time", "")))
        if commence is None:
            continue
        et = commence.astimezone(ZoneInfo("America/New_York"))
        gid = make_mlb_game_id(
            et.date().isoformat(),
            et.strftime("%I:%M %p").lstrip("0"),
            canonical_team_name(str(g.get("away_team", ""))).title(),
            canonical_team_name(str(g.get("home_team", ""))).title(),
        )
        outcomes = (((g.get("bookmakers") or [{}])[0].get("markets") or [{}])[0].get("outcomes") or [])
        home_ml = away_ml = None
        for o in outcomes:
            team = canonical_team_name(str(o.get("name", "")))
            if team == canonical_team_name(str(g.get("home_team", ""))):
                home_ml = _american(o.get("price"))
            elif team == canonical_team_name(str(g.get("away_team", ""))):
                away_ml = _american(o.get("price"))
        out.append(
            {
                "game_id": gid,
                "fetched_at": fetched_at,
                "source": "the-odds-api-v4",
                "book": "unknown",
                "odds_history": [
                    {
                        "ts": fetched_at,
                        "home_ml": home_ml,
                        "away_ml": away_ml,
                        "source": "the-odds-api-v4",
                        "snapshot_type": "current",
                    }
                ],
            }
        )
    return out


def _fetch_sportsdataio_placeholder() -> list[dict[str, Any]]:
    # SportsDataIO integration requires paid historical endpoint + key.
    if not os.getenv("SPORTSDATAIO_API_KEY", "").strip():
        return []
    return []


def _resolve_game_id(raw: dict[str, Any], game_idx: dict[str, dict[str, Any]]) -> tuple[str, str]:
    gid = str(raw.get("game_id", "")).strip()
    if gid and gid in game_idx:
        return gid, "exact_game_id"
    return "", "unmatched"


def _select_decision_snapshot(valid: list[dict[str, Any]], *, game_start_utc: datetime, lead_minutes: int) -> dict[str, Any] | None:
    cutoff = game_start_utc - timedelta(minutes=max(0, int(lead_minutes)))
    candidates = [s for s in valid if parse_ts(s.get("ts")) is not None and parse_ts(s.get("ts")) <= cutoff]
    if not candidates:
        return None
    return candidates[-1]


def _strict_timepoints(opening: dict[str, Any] | None, decision: dict[str, Any] | None, pregame: dict[str, Any] | None, closing: dict[str, Any] | None) -> tuple[bool, list[str]]:
    flags: list[str] = []
    if opening is None:
        flags.append("missing_opening")
    if decision is None:
        flags.append("missing_decision")
    if pregame is None:
        flags.append("missing_latest_pregame")
    if closing is None:
        flags.append("missing_closing")
    if flags:
        return False, flags
    t_open = parse_ts(opening.get("ts"))
    t_dec = parse_ts(decision.get("ts"))
    t_pre = parse_ts(pregame.get("ts"))
    t_close = parse_ts(closing.get("ts"))
    if None in (t_open, t_dec, t_pre, t_close):
        return False, flags + ["missing_timepoint_timestamp"]
    if not (t_open < t_dec < t_pre < t_close):
        return False, flags + ["timepoints_not_strictly_increasing"]
    return True, flags


@dataclass(frozen=True)
class HistoricalOddsBuildResult:
    canonical_output_path: str
    qa_report_path: str
    coverage_rate: float
    mapping_success_rate: float
    games_strict_valid_count: int
    total_games: int


def build_mlb_2025_historical_odds_timeline_asset(
    *,
    csv_path: str | Path = "data/mlb_2025/mlb_odds_2025_real.csv",
    canonical_output_path: str | Path = "data/mlb_context_sources/odds_timeline_canonical.jsonl",
    qa_report_path: str | Path = "data/wbc_backend/reports/mlb_2025_odds_timeline_qa_report.json",
    decision_lead_minutes: int = 60,
    fetch_external: bool = False,
    local_source_paths: list[str] | None = None,
) -> HistoricalOddsBuildResult:
    game_idx = _game_index(csv_path)
    source_paths = [Path(p) for p in local_source_paths] if local_source_paths else None
    raw_rows = _load_local_source_rows(source_paths)
    if fetch_external:
        raw_rows.extend(_fetch_the_odds_api_live())
        raw_rows.extend(_fetch_sportsdataio_placeholder())

    mapped: dict[str, list[dict[str, Any]]] = {}
    mapping_mode_counts: dict[str, int] = {}
    unmatched_rows = 0
    source_rows = 0
    duplicate_matches = 0
    for raw in raw_rows:
        source_rows += 1
        gid, mode = _resolve_game_id(raw, game_idx)
        mapping_mode_counts[mode] = mapping_mode_counts.get(mode, 0) + 1
        if not gid:
            unmatched_rows += 1
            continue
        snaps = _timeline_from_row(raw, source_name=str(raw.get("source") or "unknown"))
        if gid in mapped and snaps:
            duplicate_matches += 1
        if snaps:
            mapped.setdefault(gid, []).extend(snaps)

    canonical_rows: list[dict[str, Any]] = []
    strict_valid = 0
    missing_by_timepoint = {"opening": 0, "decision": 0, "latest_pregame": 0, "closing": 0}
    monotonic_failures = 0
    duplicate_snapshots = 0
    post_start_snapshots = 0
    no_pregame_snapshots = 0

    for gid, meta in game_idx.items():
        snaps = mapped.get(gid, [])
        # Deduplicate by timestamp using latest fetched_at wins.
        by_ts: dict[str, dict[str, Any]] = {}
        for s in snaps:
            ts = str(s.get("ts", ""))
            if not ts:
                continue
            prev = by_ts.get(ts)
            if prev is not None:
                duplicate_snapshots += 1
            if prev is None or str(s.get("fetched_at", "")) >= str(prev.get("fetched_at", "")):
                by_ts[ts] = s
        ordered = sorted(by_ts.values(), key=lambda x: str(x.get("ts", "")))
        game_start_utc = meta["start_utc"]

        pregame = []
        for s in ordered:
            ts = parse_ts(str(s.get("ts", "")))
            if ts is None:
                continue
            if ts <= game_start_utc:
                pregame.append(s)
            else:
                post_start_snapshots += 1
        if not pregame and ordered:
            no_pregame_snapshots += 1

        opening = pregame[0] if len(pregame) >= 1 else None
        closing = pregame[-1] if len(pregame) >= 1 else None
        closing_any = ordered[-1] if ordered else None
        latest_pregame = pregame[-2] if len(pregame) >= 2 else None
        decision = _select_decision_snapshot(pregame, game_start_utc=game_start_utc, lead_minutes=decision_lead_minutes)

        strict_ok, flags = _strict_timepoints(opening, decision, latest_pregame, closing)
        if not strict_ok and "timepoints_not_strictly_increasing" in flags:
            monotonic_failures += 1

        if opening is None:
            missing_by_timepoint["opening"] += 1
        if decision is None:
            missing_by_timepoint["decision"] += 1
        if latest_pregame is None:
            missing_by_timepoint["latest_pregame"] += 1
        if closing_any is None:
            missing_by_timepoint["closing"] += 1
        if strict_ok:
            strict_valid += 1

        unavailable_fields = []
        if opening is None:
            unavailable_fields.extend(["opening_home_ml", "opening_away_ml", "opening_ts"])
        if decision is None:
            unavailable_fields.extend(["decision_home_ml", "decision_away_ml", "decision_ts"])
        if latest_pregame is None:
            unavailable_fields.extend(["latest_pregame_home_ml", "latest_pregame_away_ml", "latest_pregame_ts"])
        # closing is unavailable when no TRUE pregame snapshot exists — even if a post-game proxy is present.
        # Post-game proxy value remains accessible via odds_history for research; canonical closing_home_ml is None.
        if closing is None:
            unavailable_fields.extend(["closing_home_ml", "closing_away_ml", "closing_ts"])
        closing_ts = None
        if closing is not None:
            closing_ts = closing.get("ts")
        elif closing_any is not None:
            flags.append("closing_from_non_pregame_snapshot")
            closing_ts = None

        canonical_rows.append(
            {
                "game_id": gid,
                "source": "historical_odds_ingestion",
                "bookmaker": "mixed",
                "market_type": "moneyline",
                "opening_home_ml": opening.get("home_ml") if opening else None,
                "opening_away_ml": opening.get("away_ml") if opening else None,
                "decision_home_ml": decision.get("home_ml") if decision else None,
                "decision_away_ml": decision.get("away_ml") if decision else None,
                "latest_pregame_home_ml": latest_pregame.get("home_ml") if latest_pregame else None,
                "latest_pregame_away_ml": latest_pregame.get("away_ml") if latest_pregame else None,
                # closing_{home,away}_ml: only populated from TRUE pregame closing.
                # Post-game-only scrapes leave this None (listed in unavailable_fields).
                # The raw post-game odds remain in odds_history for research access.
                "closing_home_ml": closing.get("home_ml") if closing else None,
                "closing_away_ml": closing.get("away_ml") if closing else None,
                "opening_ts": opening.get("ts") if opening else None,
                "decision_ts": decision.get("ts") if decision else None,
                "latest_pregame_ts": latest_pregame.get("ts") if latest_pregame else None,
                "closing_ts": closing_ts,
                "odds_history": ordered,
                "pregame_snapshot_count": len(pregame),
                "fetched_at": _now_iso(),
                "unavailable_fields": sorted(set(unavailable_fields)),
                "validation_flags": sorted(set(flags)),
                "strict_valid": bool(strict_ok),
            }
        )

    canonical_rows.sort(key=lambda x: str(x.get("game_id", "")))
    _write_jsonl(Path(canonical_output_path), canonical_rows)

    mapped_rows = source_rows - unmatched_rows
    mapping_success_rate = (mapped_rows / source_rows) if source_rows else 0.0
    total_games = len(game_idx)
    coverage_rate = strict_valid / max(1, total_games)
    # closing_only_count: games with a TRUE pregame closing snapshot (not post-game proxy).
    # After the fix, closing_home_ml is only set from pregame snapshots; post-game-only games → None.
    closing_only_count = int(sum(1 for r in canonical_rows if r.get("closing_home_ml") is not None))
    any_data_count = int(sum(1 for r in canonical_rows if (r.get("odds_history") or [])))
    any_data_coverage_rate = round(any_data_count / max(1, total_games), 4)
    closing_only_coverage_rate = round(closing_only_count / max(1, total_games), 4)
    # Post-game proxy count: games that HAVE odds data but only from post-game scrape (no pregame snapshot).
    post_game_proxy_count = int(sum(
        1 for r in canonical_rows
        if r.get("pregame_snapshot_count", 0) == 0 and (r.get("odds_history") or [])
    ))
    # Root-cause classification of why strict_valid=0 (when applicable)
    post_game_only_games = int(sum(1 for r in canonical_rows if "closing_from_non_pregame_snapshot" in (r.get("validation_flags") or [])))
    # Timeline tier breakdown: how many games fall into each odds coverage tier.
    # Tiers are mutually exclusive and exhaustive over all games in the CSV universe.
    # strict_4point:        has opening < decision < latest_pregame < closing (all pregame, strictly ordered)
    # timeline_3plus_pregame: 3+ distinct pregame snapshots but not strict_4point
    # timeline_2plus_pregame: exactly 2 distinct pregame snapshots
    # closing_only_pregame:   exactly 1 true pregame snapshot (used as both opening and closing proxy)
    # post_game_proxy_only:  0 pregame snapshots; only post-game odds exist (captured after game start)
    # no_data:               no odds snapshot at all
    n_strict = strict_valid
    n_3plus = int(sum(1 for r in canonical_rows if r.get("pregame_snapshot_count", 0) >= 3 and not r.get("strict_valid", False)))
    n_2plus = int(sum(1 for r in canonical_rows if r.get("pregame_snapshot_count", 0) == 2))
    n_closing_pregame = int(sum(1 for r in canonical_rows if r.get("pregame_snapshot_count", 0) == 1))
    n_post_proxy = post_game_proxy_count
    n_no_data = int(sum(1 for r in canonical_rows if not (r.get("odds_history") or [])))
    timeline_tier_breakdown = {
        "strict_4point": n_strict,
        "timeline_3plus_pregame": n_3plus,
        "timeline_2plus_pregame": n_2plus,
        "closing_only_pregame": n_closing_pregame,
        "post_game_proxy_only": n_post_proxy,
        "no_data": n_no_data,
        "note": (
            "strict_4point: all 4 timepoints present and strictly ordered before game start. "
            "post_game_proxy_only: odds exist but captured AFTER game start (post-season scrape). "
            "closing_home_ml in canonical schema is NULL for post_game_proxy_only games. "
            "Research use: post-game odds remain in odds_history field."
        ),
    }
    qa = {
        "generated_at": _now_iso(),
        "csv_path": str(csv_path),
        "canonical_output_path": str(canonical_output_path),
        "source_rows_total": source_rows,
        "mapped_source_rows": mapped_rows,
        "unmatched_source_rows": unmatched_rows,
        "duplicate_matches": duplicate_matches,
        "mapping_mode_counts": mapping_mode_counts,
        "mapping_success_rate": round(mapping_success_rate, 4),
        "total_games": total_games,
        "games_with_any_snapshot": any_data_count,
        "games_strict_valid_count": strict_valid,
        # strict 4-timepoint coverage (opening < decision < latest_pregame < closing all present)
        "strict_4point_coverage_rate": round(coverage_rate, 4),
        # legacy alias kept for backward compat
        "coverage_rate": round(coverage_rate, 4),
        # games with at least one TRUE pregame closing snapshot (not post-game proxy)
        "closing_only_coverage_rate": closing_only_coverage_rate,
        "closing_only_count": closing_only_count,
        # games with ANY odds snapshot (including post-game)
        "any_data_coverage_rate": any_data_coverage_rate,
        "any_data_count": any_data_count,
        # games with only post-game odds (typical for post-season single scrape)
        "post_game_proxy_count": post_game_proxy_count,
        "post_game_proxy_rate": round(post_game_proxy_count / max(1, total_games), 4),
        # Granular tier breakdown — differentiates closing_only (pregame) from post_game_proxy_only
        "timeline_tier_breakdown": timeline_tier_breakdown,
        "missing_by_timepoint": missing_by_timepoint,
        "timestamp_monotonic_failures": monotonic_failures,
        "duplicate_snapshots": duplicate_snapshots,
        "post_start_snapshot_count": post_start_snapshots,
        "no_pregame_snapshot_games": no_pregame_snapshots,
        # Explains WHY strict_valid=0 (post-game scrape vs missing data)
        "data_limitation_summary": {
            "post_game_snapshot_only_games": post_game_only_games,
            "no_pregame_data_games": no_pregame_snapshots,
            "root_cause": "post_season_single_scrape" if no_pregame_snapshots >= total_games * 0.9 else "mixed",
            "clv_status": "closing_only_proxy" if post_game_proxy_count > 0 else ("pregame_closing_available" if closing_only_count > 0 else "no_data"),
            "note": (
                "All snapshots were captured after game dates (post-season scrape). "
                "Post-game odds remain in odds_history for research (CLV=0 honest proxy). "
                "canonical closing_home_ml is NULL because no true pregame snapshot exists. "
                "True opening/decision CLV requires multi-timepoint pregame data."
            ) if no_pregame_snapshots > 0 else "Data available for some timepoints.",
        },
        "acceptance_gate": {
            "strict_4point_coverage_gte_80pct": coverage_rate >= 0.80,
            "coverage_rate_gte_80pct": coverage_rate >= 0.80,
            "mapping_success_rate_gte_95pct": mapping_success_rate >= 0.95,
            "strict_validation_pass": strict_valid > 0,
            # closing_only_coverage now reflects TRUE pregame closing (0 for post-season scrape)
            "closing_only_coverage_gte_80pct": closing_only_coverage_rate >= 0.80,
            # post_game_proxy gate: can be used for research even without pregame timeline
            "post_game_proxy_gte_80pct": (post_game_proxy_count / max(1, total_games)) >= 0.80,
        },
    }
    _write_json(Path(qa_report_path), qa)
    return HistoricalOddsBuildResult(
        canonical_output_path=str(canonical_output_path),
        qa_report_path=str(qa_report_path),
        coverage_rate=round(coverage_rate, 4),
        mapping_success_rate=round(mapping_success_rate, 4),
        games_strict_valid_count=strict_valid,
        total_games=len(game_idx),
    )
