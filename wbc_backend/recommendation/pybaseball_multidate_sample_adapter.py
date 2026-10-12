"""Deterministic read-only multi-date pybaseball sample adapter for P216-A."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import importlib
import importlib.metadata as importlib_metadata
import io
from typing import Any

import pandas as pd

DISCLAIMER = (
    "Historical pybaseball multi-date sample pack only. "
    "Not live predictions, not betting advice."
)
SOURCE_LIBRARY = "pybaseball"
SOURCE_FUNCTION = "pybaseball.statcast"
TASK_NAME = "P216-A pybaseball Multi-Date Historical Sample Pack"
FIXED_START_DATE = "2024-04-01"
FIXED_END_DATE = "2024-04-03"
FIXED_TEAM = "SEA"
PER_DATE_ROW_LIMIT = 8
TOTAL_ROW_LIMIT = 24
PREVIEW_ROW_LIMIT = 5
SAMPLE_COLUMNS = (
    "game_date",
    "game_pk",
    "home_team",
    "away_team",
    "inning",
    "inning_topbot",
    "at_bat_number",
    "pitch_number",
    "player_name",
    "batter",
    "pitcher",
    "pitch_type",
    "events",
    "description",
    "release_speed",
    "zone",
)
LIMITATIONS = (
    "One fixed three-day historical date range and one team filter only; this is a bounded sample pack, not a season-wide study.",
    "Output depends on the public historical pybaseball/statcast upstream response remaining available and schema-compatible for the fixed request.",
    "Sample rows are normalized into a deterministic, bounded CSV artifact for inspection only and are not production-ready data contracts.",
)
PROHIBITED_CLAIMS = (
    "No future prediction claim.",
    "No betting advice claim.",
    "No production readiness claim.",
    "No ROI, EV, Kelly, CLV, or edge claim.",
)
GUARDRAILS = (
    DISCLAIMER,
    "Read-only historical sample pack only; no live odds, no paid provider, and no production endpoint calls were made by this adapter.",
    "No database writes, model integration, or future-ticket mutation were performed.",
    "No custom MLB scraper or parser was implemented; data access is delegated to pybaseball.",
)


class MultiDateSampleError(RuntimeError):
    """Raised when the fixed multi-date pybaseball sample pack cannot be produced."""


@dataclass(frozen=True)
class MultiDateSampleConfig:
    start_date: str = FIXED_START_DATE
    end_date: str = FIXED_END_DATE
    team: str = FIXED_TEAM
    per_date_row_limit: int = PER_DATE_ROW_LIMIT
    total_row_limit: int = TOTAL_ROW_LIMIT
    preview_row_limit: int = PREVIEW_ROW_LIMIT
    sample_columns: tuple[str, ...] = SAMPLE_COLUMNS


def build_multidate_sample_payload(
    config: MultiDateSampleConfig | None = None,
    *,
    pybaseball_module: Any | None = None,
) -> dict[str, Any]:
    config = config or MultiDateSampleConfig()
    module = pybaseball_module or _load_pybaseball()
    frame = _fetch_statcast_frame(module, config)
    version = _distribution_version(SOURCE_LIBRARY)
    return _build_payload_from_frame(frame, config, version)


def _distribution_version(package_name: str) -> str | None:
    try:
        return importlib_metadata.version(package_name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _load_pybaseball() -> Any:
    try:
        return importlib.import_module(SOURCE_LIBRARY)
    except Exception as exc:  # pragma: no cover - import path depends on local interpreter.
        raise MultiDateSampleError(
            "pybaseball is not importable in the current interpreter for the P216-A "
            f"multi-date historical pack: {exc.__class__.__name__}: {exc}"
        ) from exc


def _fetch_statcast_frame(module: Any, config: MultiDateSampleConfig) -> pd.DataFrame:
    if not hasattr(module, "statcast"):
        raise MultiDateSampleError(f"{SOURCE_FUNCTION} is unavailable in this pybaseball install.")

    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            frame = module.statcast(
                start_dt=config.start_date,
                end_dt=config.end_date,
                team=config.team,
                verbose=False,
                parallel=False,
            )
    except Exception as exc:  # pragma: no cover - upstream/network failures are environment-specific.
        raise MultiDateSampleError(
            "Historical pybaseball multi-date sample pack fetch failed for fixed request "
            f"{config.start_date}..{config.end_date} team={config.team}: "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc

    if not isinstance(frame, pd.DataFrame):
        raise MultiDateSampleError(
            f"{SOURCE_FUNCTION} returned unexpected type {type(frame).__name__}; expected pandas.DataFrame."
        )
    if frame.empty:
        raise MultiDateSampleError(
            "Historical pybaseball multi-date sample pack fetch returned zero rows for the fixed request; "
            "no deterministic artifact can be produced."
        )

    required_columns = set(config.sample_columns) | {
        "game_date",
        "game_pk",
        "inning",
        "inning_topbot",
        "at_bat_number",
        "pitch_number",
        "batter",
        "pitcher",
    }
    missing_columns = sorted(column for column in required_columns if column not in frame.columns)
    if missing_columns:
        raise MultiDateSampleError(
            "Historical pybaseball multi-date sample pack fetch is missing required columns: "
            + ", ".join(missing_columns)
        )

    return frame.copy()


def _build_payload_from_frame(
    frame: pd.DataFrame,
    config: MultiDateSampleConfig,
    version: str | None,
) -> dict[str, Any]:
    working = frame.copy()
    working["_game_date_text"] = working["game_date"].map(_normalize_value)
    working["_inning_topbot_rank"] = working["inning_topbot"].map({"Top": 0, "Bottom": 1}).fillna(2)
    sorted_frame = working.sort_values(
        by=[
            "_game_date_text",
            "game_pk",
            "inning",
            "_inning_topbot_rank",
            "at_bat_number",
            "pitch_number",
            "batter",
            "pitcher",
        ],
        kind="mergesort",
        na_position="last",
    )

    observed_dates = [
        date_value
        for date_value in sorted_frame["_game_date_text"].dropna().drop_duplicates().tolist()
    ]
    if len(observed_dates) < 2:
        raise MultiDateSampleError(
            "Historical pybaseball multi-date sample pack request did not return multiple dates; "
            f"observed dates: {observed_dates!r}"
        )

    sampled_frames = []
    for observed_date in observed_dates:
        per_date = sorted_frame.loc[sorted_frame["_game_date_text"] == observed_date, list(config.sample_columns)]
        sampled_frames.append(per_date.head(config.per_date_row_limit))
    pack_frame = pd.concat(sampled_frames, ignore_index=True).head(config.total_row_limit)

    records = [
        {column: _normalize_value(value) for column, value in record.items()}
        for record in pack_frame.to_dict(orient="records")
    ]
    preview = records[: config.preview_row_limit]

    return {
        "task": TASK_NAME,
        "status": "PASS_FIXED_MULTIDATE_HISTORICAL_SAMPLE_PACK",
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "source_library": SOURCE_LIBRARY,
        "source_function": SOURCE_FUNCTION,
        "source_version": version,
        "source_request": {
            "start_date": config.start_date,
            "end_date": config.end_date,
            "team": config.team,
            "parallel": False,
            "verbose": False,
        },
        "sample_size_limits": {
            "per_date_row_limit": config.per_date_row_limit,
            "total_row_limit": config.total_row_limit,
            "preview_row_limit": config.preview_row_limit,
            "requested_date_count": _requested_date_count(config.start_date, config.end_date),
        },
        "fetched_row_count": int(len(sorted_frame)),
        "fetched_column_count": int(len(frame.columns)),
        "row_count": int(len(records)),
        "column_count": int(len(config.sample_columns)),
        "columns": list(config.sample_columns),
        "observed_dates": observed_dates,
        "sample_preview": preview,
        "limitations": list(LIMITATIONS),
        "guardrails": list(GUARDRAILS),
        "prohibited_claims": list(PROHIBITED_CLAIMS),
        "records": records,
    }


def _requested_date_count(start_date: str, end_date: str) -> int:
    return int((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days) + 1


def _normalize_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value
