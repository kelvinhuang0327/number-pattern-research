"""Replay pipeline split contract for Strategy Historical Replay.

This module formalizes the P3 split between historical reconstruction and
future waiting. It also carries a small lifecycle compatibility surface so
P1 lifecycle expectations can remain validated without reaching into DB or
strategy execution paths.
"""
from __future__ import annotations

from typing import Any, Iterable


FORMAL_LIFECYCLE_STATES: tuple[str, ...] = (
    "PRODUCTION",
    "WATCHING",
    "PROVISIONAL",
    "REJECTED",
    "OFFLINE",
    "EXPERIMENTAL",
    "UNKNOWN",
)

PIPELINE_STATES: tuple[str, ...] = (
    "HISTORICAL_RECONSTRUCTION",
    "FUTURE_WAITING",
    "DISPLAY_ONLY",
    "UNSUPPORTED",
)

_HISTORICAL_SOURCES = {"prediction_runs", "rejected_json", "simulation_log"}


def canonicalize_lifecycle_state(value: str | None) -> str:
    if value is None:
        return "UNKNOWN"
    canonical = value.upper()
    return canonical if canonical in FORMAL_LIFECYCLE_STATES else "UNKNOWN"


def can_production_apply_lifecycle(value: str | None) -> bool:
    return canonicalize_lifecycle_state(value) == "PRODUCTION"


def _get(candidate: Any, key: str, default: Any = None) -> Any:
    if isinstance(candidate, dict):
        return candidate.get(key, default)
    return getattr(candidate, key, default)


def _has_strategy_identity(candidate: Any) -> bool:
    strategy_id = _get(candidate, "strategy_id")
    source_paths = _get(candidate, "source_paths")
    return bool(strategy_id) and isinstance(source_paths, list) and bool(source_paths)


def _is_future_waiting_marker(candidate: Any) -> bool:
    if _get(candidate, "future_waiting"):
        return True
    if _get(candidate, "requires_future_draw"):
        return True
    if _get(candidate, "watcher_target"):
        return True
    if _get(candidate, "pipeline_hint") == "FUTURE_WAITING":
        return True
    if _get(candidate, "current_pipeline") == "FUTURE_WAITING":
        return True
    return False


def _has_historical_source(candidate: Any) -> bool:
    if _get(candidate, "has_historical_predictions") is True:
        return True
    source = _get(candidate, "historical_record_source")
    if source in _HISTORICAL_SOURCES:
        return True
    if _get(candidate, "has_replay_rows") is True:
        return True
    return False


def is_future_waiting_candidate(candidate: Any) -> bool:
    return _has_strategy_identity(candidate) and _is_future_waiting_marker(candidate)


def is_display_only_candidate(candidate: Any) -> bool:
    if not _has_strategy_identity(candidate):
        return False
    return not _has_historical_source(candidate)


def is_reconstruction_candidate(candidate: Any) -> bool:
    if not _has_strategy_identity(candidate):
        return False
    if _is_future_waiting_marker(candidate):
        return False
    return _has_historical_source(candidate)


def classify_pipeline(candidate: Any) -> str:
    if not _has_strategy_identity(candidate):
        return "UNSUPPORTED"
    if _is_future_waiting_marker(candidate):
        return "FUTURE_WAITING"
    if _has_historical_source(candidate):
        return "HISTORICAL_RECONSTRUCTION"
    if is_display_only_candidate(candidate):
        return "DISPLAY_ONLY"
    return "UNSUPPORTED"


def can_write_replay_rows(_pipeline_or_candidate: Any) -> bool:
    return False


def requires_future_draw(candidate: Any) -> bool:
    return classify_pipeline(candidate) == "FUTURE_WAITING"


def blocks_historical_coverage(candidate: Any) -> bool:
    return classify_pipeline(candidate) == "UNSUPPORTED"


def normalize_pipeline_state(value: str | None) -> str:
    if value is None:
        return "UNSUPPORTED"
    canonical = value.upper()
    return canonical if canonical in PIPELINE_STATES else "UNSUPPORTED"


def normalize_pipeline_sequence(values: Iterable[str | None]) -> list[str]:
    return [normalize_pipeline_state(value) for value in values]
