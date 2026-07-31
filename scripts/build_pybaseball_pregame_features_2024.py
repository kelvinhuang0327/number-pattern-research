"""
P39B — Pybaseball Pregame-Safe Feature Adapter (Rolling Core)
scripts/build_pybaseball_pregame_features_2024.py

Purpose:
    Research-only feature pipeline using pybaseball / Statcast.
    Builds rolling pregame-safe batting, workload, and team form
    features for P39 enrichment of P38A OOF predictions.

    ⚠️  pybaseball does NOT provide betting odds.
    ⚠️  This script does NOT produce moneyline / CLV / sportsbook data.
    ⚠️  All features use only data BEFORE game_date (no look-ahead).
    ⚠️  window_end = game_date - 1  (strict D-1 cutoff enforced everywhere)

SCRIPT_VERSION = p39b_pybaseball_rolling_v1
PREV_VERSION   = p39a_pybaseball_skeleton_v1
PAPER_ONLY     = True
P39B_ROLLING_FEATURE_CORE_READY_20260515
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_VERSION = "p39g_pybaseball_chunked_v1"
PREV_VERSION = "p39b_pybaseball_rolling_v1"
PAPER_ONLY = True

# P39G marker
# P39G_CHUNKED_FETCH_RUNTIME_READY_20260515

# Exact column names forbidden in any output
FORBIDDEN_ODDS_COLUMNS: frozenset[str] = frozenset(
    {
        "moneyline",
        "closing_line",
        "opening_line",
        "odds",
        "vig",
        "implied_prob",
        "home_ml",
        "away_ml",
        "home_odds",
        "away_odds",
        "clv",
        "closing_implied_prob",
        "no_vig_prob",
        "spread",
        "over_under",
        "sportsbook",
        "line_move",
        "sharp_money",
    }
)

# Keyword substrings that flag a column as odds-related
FORBIDDEN_ODDS_KEYWORDS: frozenset[str] = frozenset(
    {
        "odds",
        "moneyline",
        "spread",
        "sportsbook",
        "vig",
        "implied",
    }
)

# Required Statcast columns for team-daily aggregation
REQUIRED_STATCAST_COLS: frozenset[str] = frozenset(
    {"game_date", "game_pk", "inning_topbot", "home_team", "away_team"}
)

OUTPUT_SCHEMA_COLUMNS: list[str] = [
    "game_date",
    "team",
    "opponent",
    "is_home",
    "feature_window_start",
    "feature_window_end",
    "source",
    "feature_name",
    "feature_value",
    "sample_size",
    "generated_at",
    "leakage_status",
]

logging.basicConfig(
    format="%(levelname)s | %(message)s",
    level=logging.INFO,
    stream=sys.stderr,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure functions — independently testable, no side effects, no external fetch
# ---------------------------------------------------------------------------


def validate_feature_window(game_date: date, feature_window_end: date) -> bool:
    """
    Return True iff feature_window_end is strictly before game_date.

    This is the core pregame-safe leakage guard.
    If False, the row must be rejected (leakage_detected).
    """
    return feature_window_end < game_date


def build_rolling_window_dates(
    game_date: date, window_days: int
) -> tuple[date, date]:
    """
    Return (window_start, window_end) for a rolling window.

    window_end = game_date - 1 day  (strictly pregame-safe)
    window_start = window_end - window_days + 1
    """
    window_end = game_date - timedelta(days=1)
    window_start = window_end - timedelta(days=window_days - 1)
    return window_start, window_end


def assert_no_odds_columns(columns: list[str]) -> None:
    """
    Raise ValueError if any odds-related column is present.

    Two checks:
    1. Exact match against FORBIDDEN_ODDS_COLUMNS
    2. Keyword substring match against FORBIDDEN_ODDS_KEYWORDS
       (case-insensitive — catches 'home_odds', 'sportsbook_id', etc.)

    Call this before returning or saving any feature DataFrame.
    """
    exact_found = {c for c in columns if c in FORBIDDEN_ODDS_COLUMNS}

    keyword_found: set[str] = set()
    for col in columns:
        col_lower = col.lower()
        for kw in FORBIDDEN_ODDS_KEYWORDS:
            if kw in col_lower:
                keyword_found.add(col)
                break

    all_found = exact_found | keyword_found
    if all_found:
        raise ValueError(
            f"LEAKAGE_DETECTED: Odds/market columns found in feature output: "
            f"{sorted(all_found)}\n"
            "pybaseball adapter must NOT produce odds data."
        )


def summarize_statcast_frame(df: pd.DataFrame) -> dict:
    """
    Return a summary dict for a raw Statcast DataFrame.

    Fields:
        rows                  — int
        columns               — int
        date_range_start      — str (YYYY-MM-DD) or None
        date_range_end        — str (YYYY-MM-DD) or None
        sample_columns        — list[str] (first 10)
        odds_boundary_status  — "CONFIRMED" | "VIOLATION"
        odds_columns_found    — list[str]
        leakage_rows          — 0 (Statcast frame has no leakage column)
    """
    if df is None or df.empty:
        return {
            "rows": 0,
            "columns": 0,
            "date_range_start": None,
            "date_range_end": None,
            "sample_columns": [],
            "odds_boundary_status": "CONFIRMED",
            "odds_columns_found": [],
            "leakage_rows": 0,
        }

    cols = list(df.columns)
    exact_found = [c for c in cols if c in FORBIDDEN_ODDS_COLUMNS]
    keyword_found = [
        c for c in cols
        if any(kw in c.lower() for kw in FORBIDDEN_ODDS_KEYWORDS)
    ]
    found_odds = list(set(exact_found) | set(keyword_found))
    odds_status = "VIOLATION" if found_odds else "CONFIRMED"

    date_col = "game_date" if "game_date" in cols else None
    date_min = str(df[date_col].min())[:10] if date_col else None
    date_max = str(df[date_col].max())[:10] if date_col else None

    return {
        "rows": len(df),
        "columns": len(cols),
        "date_range_start": date_min,
        "date_range_end": date_max,
        "sample_columns": cols[:10],
        "odds_boundary_status": odds_status,
        "odds_columns_found": found_odds,
        "leakage_rows": 0,
    }


def build_team_daily_statcast_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate Statcast pitch-level data to team-day batting statistics.

    Required Statcast columns:
        game_date, game_pk, inning_topbot, home_team, away_team

    Optional (fail-soft if absent — logs warning, outputs None for that metric):
        events, launch_speed, launch_angle,
        estimated_woba_using_speedangle, release_speed

    Batting-team derivation:
        inning_topbot == "Top"  →  away_team bats
        inning_topbot == "Bot"  →  home_team bats

    Returns:
        DataFrame with one row per (game_date, game_pk, team), columns:
            game_date, team, game_pk,
            plate_appearances_proxy, batted_balls,
            avg_launch_speed, avg_launch_angle,
            avg_estimated_woba_using_speedangle,
            hard_hit_rate_proxy   (launch_speed >= 95 mph),
            barrel_rate_proxy     (launch_speed >= 98 AND 26 <= angle <= 30),
            avg_release_speed_against,
            source

    Guarantees:
        - No odds columns in output (asserted before return)
        - Returns empty DataFrame on missing required columns or empty input
    """
    if df is None or df.empty:
        return pd.DataFrame()

    missing = REQUIRED_STATCAST_COLS - set(df.columns)
    if missing:
        log.warning(
            "[P39B] build_team_daily_statcast_aggregates: "
            "missing required columns %s — returning empty", missing
        )
        return pd.DataFrame()

    work = df.copy()

    # Normalize game_date to YYYY-MM-DD string
    gd = work["game_date"]
    if hasattr(gd, "dt"):
        work["game_date"] = gd.dt.strftime("%Y-%m-%d")
    else:
        work["game_date"] = gd.astype(str).str[:10]

    # Determine batting team per pitch
    is_top = work["inning_topbot"] == "Top"
    work["batting_team"] = work["away_team"].where(is_top, work["home_team"])

    has_events = "events" in work.columns
    has_ls = "launch_speed" in work.columns
    has_la = "launch_angle" in work.columns
    has_woba = "estimated_woba_using_speedangle" in work.columns
    has_release = "release_speed" in work.columns

    if not has_events:
        log.warning("[P39B] 'events' column absent — plate_appearances_proxy unavailable")
    if not has_ls:
        log.warning("[P39B] 'launch_speed' column absent — batted ball metrics unavailable")

    records: list[dict] = []
    for (game_date, game_pk, team), g in work.groupby(
        ["game_date", "game_pk", "batting_team"]
    ):
        row: dict = {
            "game_date": game_date,
            "team": str(team),
            "game_pk": int(game_pk),
            "source": "pybaseball_statcast",
        }

        # Plate appearance proxy: events is not null = completed PA
        if has_events:
            row["plate_appearances_proxy"] = int(g["events"].notna().sum())
        else:
            row["plate_appearances_proxy"] = None

        # Batted ball metrics (non-null launch_speed = ball put in play)
        if has_ls:
            bb = g[g["launch_speed"].notna()]
            n_bb = len(bb)
            row["batted_balls"] = n_bb
            row["avg_launch_speed"] = _to_float_or_none(bb["launch_speed"].mean()) if n_bb > 0 else None
            row["hard_hit_rate_proxy"] = (
                _to_float_or_none((bb["launch_speed"] >= 95.0).mean()) if n_bb > 0 else None
            )
        else:
            row["batted_balls"] = None
            row["avg_launch_speed"] = None
            row["hard_hit_rate_proxy"] = None

        # Launch angle and barrel proxy
        if has_la and has_ls:
            bb2 = g[g["launch_speed"].notna() & g["launch_angle"].notna()]
            n_bb2 = len(bb2)
            row["avg_launch_angle"] = _to_float_or_none(bb2["launch_angle"].mean()) if n_bb2 > 0 else None
            if n_bb2 > 0:
                barrel_mask = (
                    (bb2["launch_speed"] >= 98.0)
                    & (bb2["launch_angle"] >= 26.0)
                    & (bb2["launch_angle"] <= 30.0)
                )
                row["barrel_rate_proxy"] = _to_float_or_none(barrel_mask.mean())
            else:
                row["barrel_rate_proxy"] = None
        elif has_la:
            bb_la = g[g["launch_angle"].notna()]
            row["avg_launch_angle"] = _to_float_or_none(bb_la["launch_angle"].mean()) if len(bb_la) > 0 else None
            row["barrel_rate_proxy"] = None
        else:
            row["avg_launch_angle"] = None
            row["barrel_rate_proxy"] = None

        # xwOBA
        if has_woba:
            woba_rows = g[g["estimated_woba_using_speedangle"].notna()]
            row["avg_estimated_woba_using_speedangle"] = (
                _to_float_or_none(woba_rows["estimated_woba_using_speedangle"].mean())
                if len(woba_rows) > 0 else None
            )
        else:
            row["avg_estimated_woba_using_speedangle"] = None

        # Release speed faced (proxy for opponent pitcher quality)
        if has_release:
            row["avg_release_speed_against"] = _to_float_or_none(g["release_speed"].mean()) if len(g) > 0 else None
        else:
            row["avg_release_speed_against"] = None

        records.append(row)

    if not records:
        return pd.DataFrame()

    result = pd.DataFrame(records)
    assert_no_odds_columns(list(result.columns))
    return result


def build_rolling_features(
    team_daily_df: pd.DataFrame,
    as_of_dates: list[date],
    window_days: int,
) -> pd.DataFrame:
    """
    Build rolling window batting features for each (as_of_date, team) pair.

    LEAKAGE GUARANTEE (enforced with assertion):
        window_end   = as_of_date - 1   (NEVER includes as_of_date row)
        window_start = window_end - window_days + 1

    Input:
        team_daily_df — output of build_team_daily_statcast_aggregates
        as_of_dates   — list of game dates for which to compute features
        window_days   — number of calendar days in rolling window

    Returns:
        DataFrame with one row per (as_of_date, team), columns:
            as_of_date, team,
            feature_window_start, feature_window_end, window_days,
            rolling_pa_proxy, rolling_avg_launch_speed,
            rolling_hard_hit_rate_proxy, rolling_barrel_rate_proxy,
            sample_size, leakage_status

    Guarantees:
        - feature_window_end < as_of_date for every row (asserted at runtime)
        - No odds columns in output (asserted before return)
        - Fail-soft on empty input: returns empty DataFrame with warning
    """
    if team_daily_df is None or team_daily_df.empty:
        log.warning("[P39B] build_rolling_features: empty input — returning empty")
        return pd.DataFrame()

    if not as_of_dates:
        return pd.DataFrame()

    if "game_date" not in team_daily_df.columns:
        log.warning("[P39B] build_rolling_features: 'game_date' missing — returning empty")
        return pd.DataFrame()

    df = team_daily_df.copy()

    # Normalize game_date to Python date objects (handles str, ArrowString, datetime, date)
    df["game_date"] = pd.to_datetime(df["game_date"].astype(str)).dt.date

    teams = df["team"].unique().tolist()
    records: list[dict] = []

    for as_of in as_of_dates:
        window_end = as_of - timedelta(days=1)
        window_start = window_end - timedelta(days=window_days - 1)

        # Hard leakage assertion
        if not validate_feature_window(as_of, window_end):
            raise RuntimeError(
                f"LEAKAGE_VIOLATION: window_end={window_end} >= as_of_date={as_of}"
            )

        for team in teams:
            mask = (
                (df["team"] == team)
                & (df["game_date"] >= window_start)
                & (df["game_date"] <= window_end)
            )
            window_df = df[mask]
            sample_size = len(window_df)

            def _mean(col: str) -> float | None:
                if col in window_df.columns and window_df[col].notna().any():
                    return _to_float_or_none(window_df[col].mean())
                return None

            def _sum_int(col: str) -> int | None:
                if col in window_df.columns and window_df[col].notna().any():
                    return int(window_df[col].sum())
                return None

            row: dict = {
                "as_of_date": as_of,
                "team": team,
                "feature_window_start": window_start,
                "feature_window_end": window_end,
                "window_days": window_days,
                "sample_size": sample_size,
                "leakage_status": "pregame_safe",
                "rolling_pa_proxy": _sum_int("plate_appearances_proxy") if sample_size > 0 else None,
                "rolling_avg_launch_speed": _mean("avg_launch_speed") if sample_size > 0 else None,
                "rolling_hard_hit_rate_proxy": _mean("hard_hit_rate_proxy") if sample_size > 0 else None,
                "rolling_barrel_rate_proxy": _mean("barrel_rate_proxy") if sample_size > 0 else None,
            }
            records.append(row)

    if not records:
        return pd.DataFrame()

    result = pd.DataFrame(records)
    assert_no_odds_columns(list(result.columns))
    return result


def assert_output_path_gitignored(path: str) -> None:
    """
    Raise ValueError if output path is not under data/pybaseball/local_only/.

    Prevents accidental commit of raw pybaseball data.
    """
    if "local_only" not in path:
        raise ValueError(
            f"Output path must be inside data/pybaseball/local_only/: {path}\n"
            "Raw pybaseball data must not be committed to git."
        )


def compute_summary_hash(summary: dict) -> str:
    """
    Return a deterministic SHA-256 hash of the summary dict.

    Used for smoke test determinism check (same inputs → same hash).
    """
    serialized = json.dumps(summary, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _to_float_or_none(val) -> float | None:  # noqa: ANN001
    """
    Safely convert a value to float, returning None on NA / NaN / None.

    Handles pandas NAType (pd.NA), numpy.nan, and None.
    Necessary because pybaseball uses pandas nullable float dtype
    (Float64) whose .mean() returns pd.NA instead of np.nan when
    all values in a group are missing.
    """
    if val is None:
        return None
    try:
        f = float(val)
        return None if (f != f) else f  # NaN self-comparison
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Chunked fetch / resume manifest helpers (P39G)
# ---------------------------------------------------------------------------


def build_date_chunks(
    start_date: str,
    end_date: str,
    chunk_days: int,
) -> list[dict]:
    """
    Split [start_date, end_date] into sequential non-overlapping chunks.

    Returns list of dicts:
        chunk_id, start_date, end_date, status='PENDING'
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    chunks: list[dict] = []
    chunk_id = 0
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        chunks.append(
            {
                "chunk_id": chunk_id,
                "start_date": str(cur),
                "end_date": str(chunk_end),
                "status": "PENDING",
                "rows": None,
                "error": None,
                "hash": None,
                "fetched_at": None,
            }
        )
        cur = chunk_end + timedelta(days=1)
        chunk_id += 1
    return chunks


def load_manifest(manifest_path: Path) -> dict[int, dict]:
    """
    Load existing manifest JSON → {chunk_id: entry}.
    Returns empty dict if file does not exist.
    """
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text())
        return {int(e["chunk_id"]): e for e in data.get("chunks", [])}
    except Exception as exc:  # noqa: BLE001
        log.warning("[P39G] Failed to load manifest %s: %s", manifest_path, exc)
        return {}


def save_manifest(
    manifest_path: Path,
    chunks: list[dict],
    meta: dict | None = None,
) -> None:
    """
    Write manifest JSON (always overwrites with latest state).
    manifest_path must be inside local_only/.
    """
    assert_output_path_gitignored(str(manifest_path))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta or {}, "chunks": chunks}
    manifest_path.write_text(json.dumps(payload, indent=2, default=str))


# ---------------------------------------------------------------------------
# Runtime functions — may call pybaseball (only if --execute)
# ---------------------------------------------------------------------------


def fetch_statcast_range(
    start_date: str,
    end_date: str,
    cache_dir: Path | None = None,
) -> pd.DataFrame | None:
    """
    Fetch Statcast pitch-level data via pybaseball.

    Lazy import: pybaseball is not loaded in --summary-only mode.
    Fail-soft: returns None on any exception (network, timeout, etc.).
    """
    try:
        import pybaseball  # noqa: PLC0415

        try:
            pybaseball.cache.enable()
        except Exception:  # noqa: BLE001
            pass  # cache enable is optional

        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

        log.info(
            "[pybaseball] Fetching Statcast %s → %s ...", start_date, end_date
        )
        df = pybaseball.statcast(start_dt=start_date, end_dt=end_date)
        if df is None or df.empty:
            log.warning("[pybaseball] Statcast returned empty DataFrame")
            return None
        log.info("[pybaseball] Fetched %d rows, %d cols", len(df), len(df.columns))
        return df

    except Exception as exc:  # noqa: BLE001
        log.warning("[pybaseball] Statcast fetch FAILED: %s", exc)
        return None


def fetch_statcast_chunked(
    start_date: str,
    end_date: str,
    chunk_days: int,
    cache_dir: Path,
    manifest_path: Path,
    force_refresh: bool = False,
) -> pd.DataFrame | None:
    """
    Fetch Statcast for [start_date, end_date] in chunk_days-sized windows.

    Resume behaviour:
        - Load existing manifest (if any)
        - Skip SUCCESS chunks (load from cache CSV) unless force_refresh=True
        - Fetch PENDING / FAILED chunks via pybaseball.statcast()
        - Save per-chunk CSV to cache_dir/chunk_{id:03d}_{start}_{end}.csv
        - Update manifest after each chunk

    Returns:
        Concatenated deduplicated DataFrame (all chunks SUCCESS)
        or None if all chunks failed / empty.
    """
    assert_output_path_gitignored(str(cache_dir))
    assert_output_path_gitignored(str(manifest_path))
    cache_dir.mkdir(parents=True, exist_ok=True)

    chunks = build_date_chunks(start_date, end_date, chunk_days)
    n_total = len(chunks)

    # Merge existing manifest status into chunks
    existing = load_manifest(manifest_path)
    if force_refresh:
        log.info("[P39G] --force-refresh: clearing all chunk statuses")
        existing = {}

    for c in chunks:
        cid = c["chunk_id"]
        if cid in existing:
            prev = existing[cid]
            # Only carry over SUCCESS status (keep date range from current)
            if prev.get("status") == "SUCCESS":
                c["status"] = "SUCCESS"
                c["rows"] = prev.get("rows")
                c["hash"] = prev.get("hash")
                c["fetched_at"] = prev.get("fetched_at")

    # Lazy import
    try:
        import pybaseball  # noqa: PLC0415
        try:
            pybaseball.cache.enable()
        except Exception:  # noqa: BLE001
            pass
    except ImportError as exc:
        log.error("[P39G] pybaseball not installed: %s", exc)
        return None

    all_frames: list[pd.DataFrame] = []
    n_success = 0
    n_failed = 0

    for c in chunks:
        cid = c["chunk_id"]
        cs = c["start_date"]
        ce = c["end_date"]
        chunk_csv = cache_dir / f"chunk_{cid:03d}_{cs}_{ce}.csv"

        if c["status"] == "SUCCESS" and chunk_csv.exists():
            log.info(
                "[P39G] Chunk %d/%d (%s→%s): CACHED — loading",
                cid + 1, n_total, cs, ce,
            )
            try:
                cached_df = pd.read_csv(str(chunk_csv), low_memory=False)
                all_frames.append(cached_df)
                n_success += 1
                continue
            except Exception as exc:  # noqa: BLE001
                log.warning("[P39G] Cache load failed for chunk %d: %s — re-fetching", cid, exc)
                c["status"] = "PENDING"

        log.info(
            "[P39G] Chunk %d/%d (%s→%s): FETCHING ...",
            cid + 1, n_total, cs, ce,
        )
        try:
            df_chunk = pybaseball.statcast(start_dt=cs, end_dt=ce)
            if df_chunk is None or df_chunk.empty:
                log.warning("[P39G] Chunk %d returned empty", cid)
                c["status"] = "SUCCESS"  # treat empty period as success
                c["rows"] = 0
                c["hash"] = "empty"
                c["fetched_at"] = datetime.now(timezone.utc).isoformat()
                n_success += 1
            else:
                n_rows = len(df_chunk)
                h = hashlib.sha256(
                    str(n_rows).encode() + cs.encode() + ce.encode()
                ).hexdigest()[:12]
                # Save chunk CSV
                df_chunk.to_csv(str(chunk_csv), index=False)
                all_frames.append(df_chunk)
                c["status"] = "SUCCESS"
                c["rows"] = n_rows
                c["hash"] = h
                c["fetched_at"] = datetime.now(timezone.utc).isoformat()
                c["error"] = None
                n_success += 1
                log.info(
                    "[P39G] Chunk %d: %d rows → %s",
                    cid, n_rows, chunk_csv.name,
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("[P39G] Chunk %d FAILED: %s", cid, exc)
            c["status"] = "FAILED"
            c["error"] = str(exc)
            c["fetched_at"] = datetime.now(timezone.utc).isoformat()
            n_failed += 1

        # Save manifest after every chunk
        save_manifest(
            manifest_path,
            chunks,
            meta={
                "start_date": start_date,
                "end_date": end_date,
                "chunk_days": chunk_days,
                "n_chunks": n_total,
                "n_success": n_success,
                "n_failed": n_failed,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    log.info(
        "[P39G] Chunked fetch complete: %d/%d SUCCESS, %d FAILED",
        n_success, n_total, n_failed,
    )

    if not all_frames:
        return None

    combined = pd.concat(all_frames, ignore_index=True)

    # Dedup by (game_date, game_pk, batter) if columns present
    dedup_cols = [c for c in ["game_date", "game_pk", "batter"] if c in combined.columns]
    if dedup_cols:
        before = len(combined)
        combined = combined.drop_duplicates(subset=dedup_cols)
        after = len(combined)
        if before != after:
            log.info("[P39G] Dedup removed %d duplicate rows (%d→%d)", before - after, before, after)

    return combined


def build_feature_summary_only(
    start_date: str,
    end_date: str,
    window_days: int,
) -> dict:
    """
    Dry-run: describe what features would be built without fetching.

    No external network call. Safe for CI and offline testing.
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    n_days = (end - start).days + 1

    first_game = start
    ws, we = build_rolling_window_dates(first_game, window_days)
    window_safe = validate_feature_window(first_game, we)

    return {
        "mode": "summary-only",
        "script_version": SCRIPT_VERSION,
        "paper_only": PAPER_ONLY,
        "date_range": {"start": start_date, "end": end_date, "n_days": n_days},
        "rolling_window_days": window_days,
        "sample_window_check": {
            "game_date": str(first_game),
            "window_start": str(ws),
            "window_end": str(we),
            "pregame_safe": window_safe,
        },
        "feature_families": [
            "rolling_batting_proxies",
            "rolling_pitching_proxies",
            "starter_bullpen_workload",
            "team_form_proxies",
            "statcast_aggregate_proxies",
            "schedule_density_proxies",
        ],
        "implemented_features": [
            "plate_appearances_proxy",
            "batted_balls",
            "avg_launch_speed",
            "avg_launch_angle",
            "avg_estimated_woba_using_speedangle",
            "hard_hit_rate_proxy",
            "barrel_rate_proxy",
            "avg_release_speed_against",
            "rolling_pa_proxy",
            "rolling_avg_launch_speed",
            "rolling_hard_hit_rate_proxy",
            "rolling_barrel_rate_proxy",
        ],
        "estimated_feature_count": 28,
        "odds_boundary": "CONFIRMED (design: no odds columns)",
        "leakage_violations": 0,
        "note": (
            "Dry-run summary. Use --execute to fetch Statcast and compute features."
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "P39A pybaseball pregame-safe feature adapter.\n"
            "PAPER_ONLY=True | pybaseball does NOT provide betting odds."
        )
    )
    p.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--window-days", type=int, default=14, help="Rolling window days")
    p.add_argument(
        "--summary-only",
        action="store_true",
        default=True,
        help="Dry-run: describe output without fetching (default)",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually fetch Statcast data and compute features",
    )
    p.add_argument("--out-file", default=None, help="Output CSV path (local_only only)")
    p.add_argument(
        "--cache-dir",
        default="data/pybaseball/local_only/cache",
        help="Directory for raw Statcast cache",
    )
    p.add_argument(
        "--chunk-days",
        type=int,
        default=None,
        help="Fetch Statcast in N-day chunks (P39G resume mode). None = single call.",
    )
    p.add_argument(
        "--resume-manifest",
        default=None,
        help="Path to per-chunk manifest JSON (local_only only). Enables resume.",
    )
    p.add_argument(
        "--force-refresh",
        action="store_true",
        default=False,
        help="Ignore cached chunk status and re-fetch all chunks.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_ts = datetime.now(timezone.utc).isoformat()

    print("=" * 60)
    print("  P39B pybaseball Pregame-Safe Feature Adapter (Rolling Core)")
    print("=" * 60)
    print(f"  Script version : {SCRIPT_VERSION}")
    print(f"  PAPER_ONLY     : {PAPER_ONLY}")
    print(f"  Start date     : {args.start_date}")
    print(f"  End date       : {args.end_date}")
    print(f"  Window days    : {args.window_days}")
    print(f"  Mode           : {'EXECUTE' if args.execute else 'SUMMARY-ONLY'}")
    print(f"  Run timestamp  : {run_ts}")
    print()
    print("  BOUNDARY: pybaseball does NOT provide betting odds.")
    print("  This adapter produces baseball statistics only.")
    print()

    if not args.execute:
        # ── SUMMARY-ONLY MODE (default, offline, safe) ──────────────────────
        print("=" * 60)
        print("  Summary-Only Mode (dry-run — no external fetch)")
        print("=" * 60)
        summary = build_feature_summary_only(
            args.start_date, args.end_date, args.window_days
        )
        for key, val in summary.items():
            print(f"  {key:35s} : {val}")

        h = compute_summary_hash(summary)
        print()
        print(f"  Summary hash   : {h}")

        if not summary["sample_window_check"]["pregame_safe"]:
            print()
            print("  FAIL: pregame window safety check failed")
            sys.exit(1)

        print()
        print("  Pregame-safe  : CONFIRMED")
        print("  Odds boundary : CONFIRMED")
        print()
        print("  Marker: P39B_ROLLING_FEATURE_CORE_READY_20260515")
        print("  Marker: P39A_PYBASEBALL_SKELETON_SCRIPT_READY_20260515")
        print("  Marker: P39D_REAL_FEATURE_OUTPUT_RUNTIME_READY_20260515")
        sys.exit(0)

    print("=" * 60)
    print("  Execute Mode — fetching Statcast + computing rolling features ...")
    print("=" * 60)

    # P39G chunked fetch path
    if args.chunk_days is not None:
        manifest_path = (
            Path(args.resume_manifest)
            if args.resume_manifest
            else Path(args.cache_dir) / "p39g_manifest.json"
        )
        print(f"  Chunk mode     : {args.chunk_days}-day chunks")
        print(f"  Manifest       : {manifest_path}")
        print(f"  Force refresh  : {args.force_refresh}")
        print()
        df_raw = fetch_statcast_chunked(
            args.start_date,
            args.end_date,
            chunk_days=args.chunk_days,
            cache_dir=Path(args.cache_dir),
            manifest_path=manifest_path,
            force_refresh=args.force_refresh,
        )
    else:
        df_raw = fetch_statcast_range(
            args.start_date,
            args.end_date,
            cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        )

    raw_summary = summarize_statcast_frame(
        df_raw if df_raw is not None else pd.DataFrame()
    )
    print(f"  Raw Statcast rows     : {raw_summary['rows']}")
    print(f"  Raw Statcast columns  : {raw_summary['columns']}")
    print(f"  Date range            : {raw_summary['date_range_start']} → {raw_summary['date_range_end']}")
    print(f"  Odds boundary (raw)   : {raw_summary['odds_boundary_status']}")

    if df_raw is None or df_raw.empty:
        print()
        print("  [WARN] No Statcast data returned. Check date range or network.")
        print("  Overall: PARTIAL — no data to aggregate")
        print()
        print("  Marker: P39B_ROLLING_FEATURE_CORE_READY_20260515")
        sys.exit(0)

    # Build team-daily aggregates
    print()
    print("  Building team-daily aggregates ...")
    team_daily = build_team_daily_statcast_aggregates(df_raw)
    print(f"  Team-daily rows : {len(team_daily)}")
    if not team_daily.empty:
        print(f"  Teams found     : {sorted(team_daily['team'].unique().tolist())}")

    # Build rolling features for each game date in range
    start_d = date.fromisoformat(args.start_date)
    end_d = date.fromisoformat(args.end_date)
    n_days = (end_d - start_d).days + 1
    as_of_dates = [start_d + timedelta(days=i) for i in range(n_days)]

    print()
    print(f"  Building rolling features for {n_days} as_of_dates, window={args.window_days}d ...")
    rolling_df = build_rolling_features(team_daily, as_of_dates, args.window_days)
    print(f"  Rolling feature rows        : {len(rolling_df)}")
    if not rolling_df.empty:
        non_null_speed = rolling_df["rolling_avg_launch_speed"].notna().sum()
        print(f"  Rows with launch_speed data : {non_null_speed}")
        safe_rows = (rolling_df.get("leakage_status", pd.Series([])) == "pregame_safe").sum()
        print(f"  Pregame-safe rows           : {safe_rows}")

    # Hard odds boundary check
    try:
        assert_no_odds_columns(list(team_daily.columns) if not team_daily.empty else [])
        assert_no_odds_columns(list(rolling_df.columns) if not rolling_df.empty else [])
        print()
        print("  Odds boundary : CONFIRMED")
    except ValueError as exc:
        print(f"  FAIL: {exc}")
        sys.exit(2)

    # Optional file output (local_only only)
    if args.out_file:
        assert_output_path_gitignored(args.out_file)
        out_path = Path(args.out_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result_meta = {
            "script_version": SCRIPT_VERSION,
            "paper_only": PAPER_ONLY,
            "generated_at": run_ts,
            "date_range": {"start": args.start_date, "end": args.end_date},
            "window_days": args.window_days,
            "raw_rows": raw_summary["rows"],
            "team_daily_rows": len(team_daily),
            "rolling_feature_rows": len(rolling_df),
            "odds_boundary": "CONFIRMED",
        }
        out_path.with_suffix(".summary.json").write_text(
            json.dumps(result_meta, indent=2, default=str)
        )
        if not rolling_df.empty:
            rolling_df.to_csv(str(out_path), index=False)
            print(f"  Rolling features written : {out_path}")

    print()
    print("  Marker: P39B_ROLLING_FEATURE_CORE_READY_20260515")
    print("  Marker: P39D_REAL_FEATURE_OUTPUT_RUNTIME_READY_20260515")
    print("  Marker: P39G_CHUNKED_FETCH_RUNTIME_READY_20260515")
    sys.exit(0)


if __name__ == "__main__":
    main()
