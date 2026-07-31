from __future__ import annotations

from enum import Enum
from typing import Any

from league_adapters.registry import normalize_league_name

from wbc_backend.intelligence.regime_classifier import RegimeClassifier, TournamentRegime


class GameType(str, Enum):
    WBC = "WBC"
    MLB_REGULAR = "MLB_REGULAR"
    SPRING_TRAINING = "SPRING_TRAINING"


_SPRING_MARKERS = {
    "SPRING",
    "SPRING_TRAINING",
    "SPRING TRAINING",
    "EXHIBITION",
    "WARMUP",
}

_REGULAR_MARKERS = {
    "REGULAR",
    "REGULAR_SEASON",
    "REGULAR SEASON",
    "MLB_REGULAR",
}

_WBC_MARKERS = {
    "WBC",
}


def _normalize_marker(value: Any) -> str:
    marker = str(value or "").strip().upper().replace("-", "_")
    marker = marker.replace("__", "_")
    return marker


def classify_game_type(record: Any) -> GameType:
    """Classify a baseball game into the current output taxonomy.

    Priority order:
    1. explicit game_type metadata
    2. round_name / regime hints
    3. normalized league / tournament fallback
    """
    explicit = _normalize_marker(
        getattr(record, "game_type", None)
        or getattr(record, "game_type_label", None)
        or getattr(record, "season_phase", None)
        or getattr(record, "stage", None)
    )
    if explicit:
        if explicit in _WBC_MARKERS or explicit.startswith("WBC"):
            return GameType.WBC
        if explicit in _SPRING_MARKERS or explicit.startswith("SPRING") or explicit.startswith("EXHIBITION"):
            return GameType.SPRING_TRAINING
        if explicit in _REGULAR_MARKERS or explicit.startswith("REGULAR"):
            return GameType.MLB_REGULAR

    league = normalize_league_name(getattr(record, "league", "") or getattr(record, "tournament", "WBC"))
    round_name = str(getattr(record, "round_name", "") or "").strip()
    round_marker = _normalize_marker(round_name)

    if league == "WBC" or round_marker.startswith("POOL") or round_marker in {"QF", "SF", "FINAL"}:
        return GameType.WBC

    if league == "MLB":
        if round_marker in _SPRING_MARKERS:
            return GameType.SPRING_TRAINING
        if RegimeClassifier.classify(round_name) == TournamentRegime.EXHIBITION:
            return GameType.SPRING_TRAINING
        return GameType.MLB_REGULAR

    if round_marker in _SPRING_MARKERS:
        return GameType.SPRING_TRAINING
    if round_marker in _WBC_MARKERS:
        return GameType.WBC

    return GameType.MLB_REGULAR if league == "MLB" else GameType.WBC


def is_spring_training_game(record: Any) -> bool:
    return classify_game_type(record) == GameType.SPRING_TRAINING

