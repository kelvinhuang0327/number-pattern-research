"""Deterministic read-only historical pybaseball sample adapter for P214-A."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import importlib
import importlib.metadata as importlib_metadata
import io
from typing import Any

import pandas as pd

DISCLAIMER = (
    "Historical pybaseball read-only sample smoke only. "
    "Not live predictions, not betting advice."
)
SOURCE_LIBRARY = "pybaseball"
SOURCE_FUNCTION = "pybaseball.statcast"
TASK_NAME = "P214-A pybaseball Historical Sample Smoke"
FIXED_START_DATE = "2024-04-01"
FIXED_END_DATE = "2024-04-01"
FIXED_TEAM = "SEA"
SNAPSHOT_ROW_LIMIT = 12
SNAPSHOT_COLUMNS = (
    "game_date",
    "game_pk",
    "home_team",
    "away_team",
    "inning",
    "inning_topbot",
    "at_bat_number",
    "pitch_number",
    "batter",
    "pitcher",
    "pitch_type",
    "events",
    "description",
    "release_speed",
    "zone",
)
LIMITATIONS = (
    "One fixed historical date and one team filter only; this is a bounded smoke sample, not a season-wide study.",
    "Output depends on the public historical pybaseball/statcast upstream response remaining available for the fixed request.",
    "Snapshot records are normalized to a small deterministic subset for inspection and are not production-ready data contracts.",
)
GUARDRAILS = (
    DISCLAIMER,
    "Read-only historical sample only; no live odds, no paid provider, and no production endpoint calls were made by this adapter.",
    "No database writes, model integration, or future-ticket mutation were performed.",
    "No custom MLB scraper or parser was implemented; data access is delegated to pybaseball.",
)


class HistoricalSampleError(RuntimeError):
    """Raised when the fixed historical pybaseball sample cannot be produced."""


@dataclass(frozen=True)
class HistoricalSampleConfig:
    start_date: str = FIXED_START_DATE
    end_date: str = FIXED_END_DATE
    team: str = FIXED_TEAM
    snapshot_row_limit: int = SNAPSHOT_ROW_LIMIT
    snapshot_columns: tuple[str, ...] = SNAPSHOT_COLUMNS


def build_historical_sample_payload(
    config: HistoricalSampleConfig | None = None,
    *,
    pybaseball_module: Any | None = None,
) -> dict[str, Any]:
    config = config or HistoricalSampleConfig()
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
        raise HistoricalSampleError(
            "pybaseball is not importable in the current interpreter for the P214-A "
            f"historical smoke: {exc.__class__.__name__}: {exc}"
        ) from exc


def _fetch_statcast_frame(module: Any, config: HistoricalSampleConfig) -> pd.DataFrame:
    if not hasattr(module, "statcast"):
        raise HistoricalSampleError(f"{SOURCE_FUNCTION} is unavailable in this pybaseball install.")

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
        raise HistoricalSampleError(
            "Historical pybaseball sample fetch failed for fixed request "
            f"{config.start_date}..{config.end_date} team={config.team}: "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc

    if not isinstance(frame, pd.DataFrame):
        raise HistoricalSampleError(
            f"{SOURCE_FUNCTION} returned unexpected type {type(frame).__name__}; expected pandas.DataFrame."
        )
    if frame.empty:
        raise HistoricalSampleError(
            "Historical pybaseball sample fetch returned zero rows for the fixed request; "
            "no deterministic artifact can be produced."
        )

    required_columns = set(config.snapshot_columns) | {
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
        raise HistoricalSampleError(
            "Historical pybaseball sample fetch is missing required columns: "
            + ", ".join(missing_columns)
        )

    return frame.copy()


def _build_payload_from_frame(
    frame: pd.DataFrame,
    config: HistoricalSampleConfig,
    version: str | None,
) -> dict[str, Any]:
    working = frame.copy()
    working["_inning_topbot_rank"] = working["inning_topbot"].map({"Top": 0, "Bottom": 1}).fillna(2)
    sorted_frame = working.sort_values(
        by=[
            "game_date",
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
    snapshot_frame = sorted_frame.loc[:, list(config.snapshot_columns)].head(config.snapshot_row_limit)
    records = [
        {
            column: _normalize_value(value)
            for column, value in record.items()
        }
        for record in snapshot_frame.to_dict(orient="records")
    ]

    normalized_dates = [
        _normalize_value(value)
        for value in sorted_frame["game_date"].tolist()
        if _normalize_value(value) is not None
    ]

    return {
        "task": TASK_NAME,
        "status": "PASS_FIXED_HISTORICAL_READ_ONLY_SAMPLE",
        "disclaimer": DISCLAIMER,
        "source_library": SOURCE_LIBRARY,
        "source_function": SOURCE_FUNCTION,
        "source_version": version,
        "request": {
            "start_date": config.start_date,
            "end_date": config.end_date,
            "team": config.team,
            "parallel": False,
            "verbose": False,
        },
        "result_summary": {
            "fetched_row_count": int(len(sorted_frame)),
            "fetched_column_count": int(len(frame.columns)),
            "snapshot_row_count": int(len(records)),
            "snapshot_columns": list(config.snapshot_columns),
            "observed_date_range": {
                "start": normalized_dates[0],
                "end": normalized_dates[-1],
            },
        },
        "limitations": list(LIMITATIONS),
        "guardrails": list(GUARDRAILS),
        "records": records,
    }


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
