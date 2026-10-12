"""
wbc_backend/prediction/mlb_independent_feature_builder.py

P10/P11: Independent baseball feature builder.

build_independent_features() — produces MlbIndependentFeatureRow objects from
a list of game rows using only historical pre-game information.

merge_independent_features_into_rows() — joins features back into game dicts.

P11 fix: Column alias resolution + game_id-based context lookup.
- P9 CSV uses capitalised column names ("Date", "Home", "Away", "Home Starter")
  while the builder previously expected lowercase ("date", "home_team", etc.).
  _resolve_col() auto-detects the actual column name from the first row.
- Win rates now computed from as-played CSV (not P9 rows) — avoids outcome
  column aliasing issue.
- Context lookup now uses game_id directly (canonical YYYY-MM-DD_HOME_AWAY
  format matches the index keys built from context files).

Leakage safety (unchanged from P10):
- win rates use only games BEFORE the current row's date.
- starter ERA proxy uses only prior starts.
- rest days come from context files that record pre-game state.
"""
from __future__ import annotations

import json
import math
import pathlib
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from wbc_backend.prediction.mlb_game_key import (
    build_mlb_game_id,
    normalize_mlb_team,
    parse_context_game_id,
)
from wbc_backend.prediction.mlb_feature_context_keys import (
    index_context_rows,
    lookup_context_for_game,
)
from wbc_backend.prediction.mlb_feature_context_loader import load_context_rows
from wbc_backend.prediction.mlb_independent_features import MlbIndependentFeatureRow

_FEATURE_VERSION = "p11_context_reconciled_v1"
_DEFAULT_BULLPEN_PATH = "data/mlb_context/bullpen_usage_3d.jsonl"
_DEFAULT_REST_PATH = "data/mlb_context/injury_rest.jsonl"
_DEFAULT_WEATHER_PATH = "data/mlb_context/weather_wind.jsonl"
_DEFAULT_ASPLAYED_PATH = "data/mlb_2025/mlb-2025-asplayed.csv"


# ---------------------------------------------------------------------------
# § 0  Column alias resolution (P11 fix)
# ---------------------------------------------------------------------------

def _resolve_col(rows: list[dict], *candidates: str) -> str:
    """
    Return the first candidate column name present in the first row.

    If none of the candidates are present, returns the first candidate as
    a fallback (builder will get empty values, no crash).

    Parameters
    ----------
    rows : list[dict]
        Non-empty list of data rows (only the first row is inspected).
    *candidates : str
        Column name candidates in priority order.

    Returns
    -------
    str
        The first matching column name, or the first candidate if none match.
    """
    if not rows or not candidates:
        return candidates[0] if candidates else ""
    sample = rows[0]
    for c in candidates:
        if c in sample:
            return c
    return candidates[0]


def _parse_game_id_parts(gid: str) -> tuple[str, str, str] | None:
    """
    Parse a canonical game_id ``YYYY-MM-DD_HOME_AWAY`` into (date, home, away).

    Returns None if the format does not match.
    """
    if not gid:
        return None
    parts = gid.split("_")
    if len(parts) >= 3 and len(parts[0]) == 10 and parts[0][4] == "-":
        return parts[0], parts[1], parts[2]
    return None


# ---------------------------------------------------------------------------
# § 1  Context file loaders (legacy + new unified path)
# ---------------------------------------------------------------------------

def _load_context_jsonl(path: str | None) -> dict[str, dict]:
    """
    Load a context JSONL and return a lookup dict indexed by all candidate keys.

    P11: Uses index_context_rows() which builds canonical + variant keys so that
    game_id-based lookups (YYYY-MM-DD_HOME_AWAY) match the MLB-format context keys.
    """
    if path is None:
        return {}
    rows = load_context_rows(path)
    if not rows:
        return {}
    return index_context_rows(rows)


def _load_asplayed_rows(path: str) -> list[dict]:
    """Load as-played CSV rows. Returns list sorted by date (lowercase 'date' col)."""
    import csv
    p = pathlib.Path(path)
    if not p.exists():
        return []
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    # as-played CSV has both "Date" and "date" columns — always use lowercase "date"
    rows.sort(key=lambda r: str(r.get("date") or r.get("Date") or ""))
    return rows


# ---------------------------------------------------------------------------
# Starter ERA proxy (leakage-safe rolling)
# ---------------------------------------------------------------------------

def _build_starter_era_proxies(
    asplayed_rows: list[dict],
    min_starts: int = 2,
) -> dict[tuple[str, str], float]:
    """
    For each (date, pitcher_name) pair, return average runs-allowed per start
    using only starts BEFORE this date.

    Returns dict: (date_str, pitcher_name) → avg_runs_per_start
    """
    # Accumulate: pitcher → list of (date, runs_allowed)
    pitcher_history: dict[str, list[tuple[str, float]]] = defaultdict(list)
    era_proxy: dict[tuple[str, str], float] = {}

    for row in asplayed_rows:
        date = str(row.get("date") or "")
        home_team = str(row.get("home_team") or "")
        away_team = str(row.get("away_team") or "")
        home_starter = str(row.get("home_starter") or "").strip()
        away_starter = str(row.get("away_starter") or "").strip()

        try:
            home_score = float(row.get("home_score") or 0)
            away_score = float(row.get("away_score") or 0)
        except (ValueError, TypeError):
            home_score = 0.0
            away_score = 0.0

        # Compute ERA proxy (runs-allowed) for each starter BEFORE adding current game
        # home starter: runs allowed = away_score
        if home_starter and date:
            prior = pitcher_history[home_starter]
            if len(prior) >= min_starts:
                era_proxy[(date, home_starter)] = sum(r for _, r in prior) / len(prior)
            pitcher_history[home_starter].append((date, away_score))

        # away starter: runs allowed = home_score
        if away_starter and date:
            prior = pitcher_history[away_starter]
            if len(prior) >= min_starts:
                era_proxy[(date, away_starter)] = sum(r for _, r in prior) / len(prior)
            pitcher_history[away_starter].append((date, home_score))

    return era_proxy


# ---------------------------------------------------------------------------
# Rolling win rate (leakage-safe)
# ---------------------------------------------------------------------------

def _build_rolling_win_rates(
    rows: list[dict],
    date_col: str,
    home_col: str,
    away_col: str,
    outcome_col: str,
    lookback: int = 15,
) -> dict[tuple[str, str], float]:
    """
    Returns dict: (date_str, team_name) → recent win rate (PRIOR to this game).
    Also returns game count in the window.
    """
    from collections import deque

    team_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=lookback))
    win_rate_map: dict[tuple[str, str], tuple[float, int]] = {}

    for row in rows:
        date = str(row.get(date_col) or "")
        home = str(row.get(home_col) or "")
        away = str(row.get(away_col) or "")

        try:
            outcome = float(row.get(outcome_col) or 0)  # 1.0 = home win
        except (ValueError, TypeError):
            outcome = None

        # Compute win rate for both teams BEFORE adding current game
        for team in (home, away):
            hist = team_history[team]
            if hist:
                wins = sum(hist)
                win_rate_map[(date, team)] = (wins / len(hist), len(hist))

        # Update history for both teams (after recording current pre-game state)
        if outcome is not None:
            team_history[home].append(1.0 if outcome >= 0.5 else 0.0)
            team_history[away].append(0.0 if outcome >= 0.5 else 1.0)

    return win_rate_map


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_independent_features(
    rows: list[dict],
    *,
    date_col: str = "date",
    home_team_col: str = "home_team",
    away_team_col: str = "away_team",
    outcome_col: str = "home_win",
    lookback_games: int = 15,
    bullpen_context_path: str | None = _DEFAULT_BULLPEN_PATH,
    rest_context_path: str | None = _DEFAULT_REST_PATH,
    weather_context_path: str | None = _DEFAULT_WEATHER_PATH,
    asplayed_path: str = _DEFAULT_ASPLAYED_PATH,
    extra_context_paths: list[str] | None = None,
) -> tuple[list[MlbIndependentFeatureRow], dict]:
    """
    Build P11 independent baseball features for each row.

    P11 fixes vs P10:
    - Column alias resolution: auto-detects capitalised column names
      ("Date", "Home", "Away", "Home Starter") present in P9 CSV.
    - Win rates computed from as-played CSV (which has ``home_win`` column)
      instead of from P9 rows (which lack a reliable outcome column).
    - Context lookup uses ``game_id`` directly as the index key, since
      game_id in P9 CSV (``YYYY-MM-DD_HOME_AWAY``) already matches the
      canonical keys built by ``index_context_rows()`` from the MLB-format
      context file keys.
    - Starter ERA proxy lookup uses date from game_id when the date column
      is capitalized and not detected by the legacy date_col.

    Uses only pre-game information:
    - rolling win rate (from prior as-played games)
    - rest days (from context files, pre-game state)
    - bullpen usage 3d (from context files)
    - starter ERA proxy (from historical starts before this date)
    - weather (from pre-game weather context)

    Parameters
    ----------
    rows : list[dict]
        Game prediction rows (P9 CSV format).
    date_col : str
        Primary date column name (tried first; aliases auto-detected).
    home_team_col : str
        Primary home team column name (tried first; aliases auto-detected).
    away_team_col : str
        Primary away team column name (tried first; aliases auto-detected).
    outcome_col : str
        Outcome column for rolling win rate (P9 rows; fallback to as-played).
    lookback_games : int
        Rolling win rate window size.
    bullpen_context_path : str | None
        Path to bullpen_usage_3d.jsonl.
    rest_context_path : str | None
        Path to injury_rest.jsonl.
    weather_context_path : str | None
        Path to weather_wind.jsonl.
    asplayed_path : str
        Path to mlb-2025-asplayed.csv.
    extra_context_paths : list[str] | None
        Additional context file paths to merge into lookups.

    Returns
    -------
    tuple[list[MlbIndependentFeatureRow], dict]
        (feature_rows, metadata)
    """
    if not rows:
        return [], {"input_count": 0, "feature_count": 0, "leakage_safe": True}

    # ------------------------------------------------------------------
    # P11: Auto-detect column aliases from first row
    # ------------------------------------------------------------------
    date_col_actual = _resolve_col(rows, date_col, "Date", "game_date", "date")
    home_col_actual = _resolve_col(rows, home_team_col, "Home", "home", "home_team")
    away_col_actual = _resolve_col(rows, away_team_col, "Away", "away", "away_team")
    home_starter_col = _resolve_col(rows, "Home Starter", "home_starter", "starter_home")
    away_starter_col = _resolve_col(rows, "Away Starter", "away_starter", "starter_away")

    # Sort chronologically using the detected date column
    sorted_rows = sorted(rows, key=lambda r: str(r.get(date_col_actual) or r.get("game_id") or ""))

    # ------------------------------------------------------------------
    # Load context lookups (P11: uses index_context_rows for multi-key indexing)
    # ------------------------------------------------------------------
    bullpen_ctx = _load_context_jsonl(bullpen_context_path)
    rest_ctx = _load_context_jsonl(rest_context_path)
    weather_ctx = _load_context_jsonl(weather_context_path)

    # Merge extra context files into respective lookups
    if extra_context_paths:
        from wbc_backend.prediction.mlb_feature_context_loader import load_context_rows
        from wbc_backend.prediction.mlb_feature_context_keys import index_context_rows as _idx
        for cp in extra_context_paths:
            extra_rows = load_context_rows(cp)
            if not extra_rows:
                continue
            extra_idx = _idx(extra_rows)
            pname = pathlib.Path(cp).name.lower()
            if "bullpen" in pname or "fatigue" in pname:
                bullpen_ctx.update(extra_idx)
            elif "rest" in pname or "injury" in pname:
                rest_ctx.update(extra_idx)
            elif "weather" in pname or "wind" in pname:
                weather_ctx.update(extra_idx)

    # ------------------------------------------------------------------
    # Build rolling win rate from AS-PLAYED CSV (P11 fix)
    # as-played has lowercase columns (date, home_team, away_team, home_win)
    # which are reliable — avoids P9 CSV outcome column aliasing issue.
    # ------------------------------------------------------------------
    asplayed_rows = _load_asplayed_rows(asplayed_path)
    win_rate_map = _build_rolling_win_rates(
        asplayed_rows,
        date_col="date",
        home_col="home_team",
        away_col="away_team",
        outcome_col="home_win",
        lookback=lookback_games,
    )

    # ------------------------------------------------------------------
    # Build starter ERA proxy from as-played historical data
    # ------------------------------------------------------------------
    starter_era_map = _build_starter_era_proxies(asplayed_rows, min_starts=2)

    # Track coverage
    coverage: dict[str, int] = defaultdict(int)
    missing_reasons: list[str] = []
    context_hit_count = 0
    context_miss_count = 0

    feature_rows: list[MlbIndependentFeatureRow] = []

    for row in sorted_rows:
        # ------------------------------------------------------------------
        # P11: Extract date / home / away with alias fallback + game_id parsing
        # ------------------------------------------------------------------
        gid = str(row.get("game_id") or "")
        date = str(row.get(date_col_actual) or "")
        home_raw = str(row.get(home_col_actual) or "")
        away_raw = str(row.get(away_col_actual) or "")

        # Fallback: parse from game_id (YYYY-MM-DD_HOME_AWAY)
        if (not date or not home_raw or not away_raw) and gid:
            parsed = _parse_game_id_parts(gid)
            if parsed:
                gid_date, gid_home_abbr, gid_away_abbr = parsed
                if not date:
                    date = gid_date
                if not home_raw:
                    home_raw = gid_home_abbr
                if not away_raw:
                    away_raw = gid_away_abbr

        home = normalize_mlb_team(home_raw)
        away = normalize_mlb_team(away_raw)

        # Ensure gid is set (build from detected fields if missing)
        if not gid:
            gid = build_mlb_game_id(date, home, away)

        # ------------------------------------------------------------------
        # Rolling win rate lookup (using full team name from as-played)
        # The as-played win_rate_map keys: (date_str, "Chicago Cubs")
        # P9 CSV home_raw after alias fix: "Chicago Cubs"
        # Try raw name first, then normalized abbreviation
        # ------------------------------------------------------------------
        home_wr_entry = win_rate_map.get((date, home_raw)) or win_rate_map.get((date, home))
        away_wr_entry = win_rate_map.get((date, away_raw)) or win_rate_map.get((date, away))
        home_wr: float | None = home_wr_entry[0] if home_wr_entry else None
        away_wr: float | None = away_wr_entry[0] if away_wr_entry else None
        home_games: int | None = home_wr_entry[1] if home_wr_entry else None
        away_games: int | None = away_wr_entry[1] if away_wr_entry else None
        wr_delta: float | None = (
            (home_wr - away_wr)
            if (home_wr is not None and away_wr is not None)
            else None
        )

        if home_wr is not None:
            coverage["home_recent_win_rate"] += 1
        if away_wr is not None:
            coverage["away_recent_win_rate"] += 1

        # ------------------------------------------------------------------
        # Context lookups (P11: use game_id as primary key)
        # The context index keys are YYYY-MM-DD_HOME_AWAY (canonical)
        # which matches the game_id column in P9 CSV exactly.
        # ------------------------------------------------------------------

        # --- Rest days ---
        rest_row = rest_ctx.get(gid) or rest_ctx.get(gid.lower())
        if rest_row is None and date and home != "UNK" and away != "UNK":
            # Try rebuilt canonical key
            alt_key = f"{date}_{home}_{away}"
            rest_row = rest_ctx.get(alt_key)
        home_rest: float | None = None
        away_rest: float | None = None
        rest_delta: float | None = None
        if rest_row:
            context_hit_count += 1
            try:
                v = rest_row.get("rest_days_home")
                if v is not None:
                    home_rest = max(0.0, float(v))
            except (ValueError, TypeError):
                pass
            try:
                v = rest_row.get("rest_days_away")
                if v is not None:
                    away_rest = max(0.0, float(v))
            except (ValueError, TypeError):
                pass
            if home_rest is not None and away_rest is not None:
                rest_delta = home_rest - away_rest
        else:
            context_miss_count += 1

        if home_rest is not None:
            coverage["home_rest_days"] += 1
        if away_rest is not None:
            coverage["away_rest_days"] += 1

        # --- Bullpen usage ---
        bullpen_row = bullpen_ctx.get(gid) or bullpen_ctx.get(gid.lower())
        if bullpen_row is None and date and home != "UNK" and away != "UNK":
            alt_key = f"{date}_{home}_{away}"
            bullpen_row = bullpen_ctx.get(alt_key)
        home_bullpen: float | None = None
        away_bullpen: float | None = None
        bullpen_delta: float | None = None
        if bullpen_row:
            try:
                v = bullpen_row.get("bullpen_usage_last_3d_home")
                if v is not None:
                    home_bullpen = float(v)
            except (ValueError, TypeError):
                pass
            try:
                v = bullpen_row.get("bullpen_usage_last_3d_away")
                if v is not None:
                    away_bullpen = float(v)
            except (ValueError, TypeError):
                pass
            if home_bullpen is not None and away_bullpen is not None:
                bullpen_delta = home_bullpen - away_bullpen

        if home_bullpen is not None:
            coverage["bullpen_proxy"] += 1

        # --- Starter ERA proxy ---
        home_starter = str(row.get(home_starter_col) or "").strip()
        away_starter = str(row.get(away_starter_col) or "").strip()
        home_era: float | None = starter_era_map.get((date, home_starter))
        away_era: float | None = starter_era_map.get((date, away_starter))
        era_delta: float | None = (
            (home_era - away_era)
            if (home_era is not None and away_era is not None)
            else None
        )

        if home_era is not None:
            coverage["starter_era_proxy_home"] += 1
        if away_era is not None:
            coverage["starter_era_proxy_away"] += 1

        if not home_starter or not away_starter:
            missing_reasons.append(f"{gid}: missing starter name(s)")

        # --- Weather ---
        weather_row = weather_ctx.get(gid) or weather_ctx.get(gid.lower())
        if weather_row is None and date and home != "UNK" and away != "UNK":
            alt_key = f"{date}_{home}_{away}"
            weather_row = weather_ctx.get(alt_key)
        wind_kmh: float | None = None
        temp_c: float | None = None
        roof_type: str | None = None
        if weather_row:
            wind_data = weather_row.get("wind") or {}
            weather_data = weather_row.get("weather") or {}
            park_data = weather_row.get("park_factors") or {}
            if wind_data and wind_data.get("wind_kmh_avg") is not None:
                try:
                    wind_kmh = float(wind_data["wind_kmh_avg"])
                except (ValueError, TypeError):
                    pass
            if weather_data and weather_data.get("temp_c_avg") is not None:
                try:
                    temp_c = float(weather_data["temp_c_avg"])
                except (ValueError, TypeError):
                    pass
            roof_type = park_data.get("roof_type")

        if wind_kmh is not None:
            coverage["wind_kmh"] += 1
        if temp_c is not None:
            coverage["temp_c"] += 1

        source_trace: dict = {
            "win_rate_lookback": lookback_games,
            "home_games_in_window": home_games,
            "away_games_in_window": away_games,
            "home_starter": home_starter or None,
            "away_starter": away_starter or None,
            "bullpen_context_hit": bullpen_row is not None,
            "rest_context_hit": rest_row is not None,
            "weather_context_hit": weather_row is not None,
            "era_proxy_source": "asplayed_rolling" if (home_era or away_era) else "unavailable",
            "date_col_used": date_col_actual,
            "home_col_used": home_col_actual,
            "away_col_used": away_col_actual,
            "context_lookup_key": gid,
        }

        feat = MlbIndependentFeatureRow(
            game_id=gid,
            date=date,
            home_team=home_raw,
            away_team=away_raw,
            home_rest_days=home_rest,
            away_rest_days=away_rest,
            rest_days_delta=rest_delta,
            home_recent_win_rate=home_wr,
            away_recent_win_rate=away_wr,
            recent_win_rate_delta=wr_delta,
            home_recent_games_count=home_games,
            away_recent_games_count=away_games,
            starter_era_delta=era_delta,
            home_starter_era_proxy=home_era,
            away_starter_era_proxy=away_era,
            bullpen_proxy_delta=bullpen_delta,
            home_bullpen_usage_3d=home_bullpen,
            away_bullpen_usage_3d=away_bullpen,
            wind_kmh=wind_kmh,
            temp_c=temp_c,
            park_roof_type=str(roof_type) if roof_type else None,
            feature_version=_FEATURE_VERSION,
            feature_source="p11_baseball_stats",
            leakage_safe=True,
            source_trace=source_trace,
        )
        feature_rows.append(feat)

    # Build coverage report
    n = len(sorted_rows)
    coverage_by_feature = {
        k: {"hit": v, "total": n, "pct": round(v / n, 4)}
        for k, v in coverage.items()
    }

    # Document missing sources
    starter_era_miss = n - coverage.get("starter_era_proxy_home", 0)
    if starter_era_miss > 0:
        missing_reasons.append(
            f"starter_era_proxy: {starter_era_miss}/{n} rows missing "
            f"(requires ≥2 prior starts in as-played data)"
        )

    # De-duplicate reasons
    missing_reasons_dedup = list(dict.fromkeys(missing_reasons))

    metadata: dict = {
        "input_count": n,
        "feature_count": len(feature_rows),
        "coverage_by_feature": coverage_by_feature,
        "missing_feature_reasons": missing_reasons_dedup[:20],
        "leakage_safe": True,
        "lookback_games": lookback_games,
        "feature_version": _FEATURE_VERSION,
        "bullpen_context_rows": len(bullpen_ctx),
        "rest_context_rows": len(rest_ctx),
        "weather_context_rows": len(weather_ctx),
        "asplayed_rows": len(asplayed_rows),
        "starter_era_proxy_available": len(starter_era_map) > 0,
        "context_hit_count": context_hit_count,
        "context_miss_count": context_miss_count,
        "context_hit_rate": round(
            context_hit_count / max(context_hit_count + context_miss_count, 1),
            4,
        ),
        "context_key_examples": [],  # populated by callers if needed
        "context_match_strategies": [],
        "date_col_resolved": date_col_actual,
        "home_col_resolved": home_col_actual,
        "away_col_resolved": away_col_actual,
        "home_starter_col_resolved": home_starter_col,
        "away_starter_col_resolved": away_starter_col,
    }
    return feature_rows, metadata

# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------

def merge_independent_features_into_rows(
    rows: list[dict],
    features: list[MlbIndependentFeatureRow],
) -> list[dict]:
    """
    Left-join independent features into game rows by game_id.

    Adds all MlbIndependentFeatureRow fields as flat columns.
    Preserves all existing model/market columns.
    """
    feat_by_gid: dict[str, MlbIndependentFeatureRow] = {}
    for f in features:
        feat_by_gid[f.game_id] = f

    out: list[dict] = []
    for row in rows:
        gid = str(row.get("game_id") or "")
        feat = feat_by_gid.get(gid)
        merged = dict(row)
        if feat is not None:
            fd = feat.to_dict()
            for k, v in fd.items():
                if k not in ("game_id", "source_trace"):
                    merged[f"indep_{k}"] = v
            merged["indep_source_trace"] = json.dumps(feat.source_trace)
            merged["independent_feature_version"] = feat.feature_version
            merged["independent_feature_source"] = feat.feature_source
        else:
            merged["independent_feature_version"] = None
            merged["independent_feature_source"] = None
        out.append(merged)
    return out
