from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .schema import MLBGameData


class MLBValidityTier(str, Enum):
    STRICT_VALID = "STRICT_VALID"
    RESEARCH_VALID = "RESEARCH_VALID"
    INVALID = "INVALID"


@dataclass
class MLBValidationResult:
    total_games: int
    strict_valid_games: int
    research_valid_games: int
    invalid_games: int
    status_by_game: dict[str, MLBValidityTier] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.invalid_games == 0 and self.strict_valid_games == self.total_games


def validate_mlb_game_data(rows: list[MLBGameData]) -> MLBValidationResult:
    issues: list[str] = []
    strict_count = 0
    research_count = 0
    status_by_game: dict[str, MLBValidityTier] = {}

    strict_context_fields = (
        "confirmed_home_starter",
        "confirmed_away_starter",
        "confirmed_home_lineup",
        "confirmed_away_lineup",
        "bullpen_usage_last_3d_home",
        "bullpen_usage_last_3d_away",
        "home_away_splits",
        "platoon_splits",
        "park_factors",
        "weather",
        "wind",
    )
    research_core_fields = (
        "probable_home_starter",
        "probable_away_starter",
    )

    now = datetime.now(timezone.utc)
    freshness_limit = now - timedelta(hours=24)

    def _is_fresh(observed_at: str) -> bool:
        if not observed_at:
            return False
        try:
            ts = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts >= freshness_limit
        except Exception:
            return False

    for row in rows:
        missing_strict = []
        missing_research = []
        stale_strict = []
        for name in strict_context_fields:
            field_obj = getattr(row.features, name)
            if not field_obj.available:
                missing_strict.append(name)
            elif not _is_fresh(field_obj.observed_at):
                stale_strict.append(name)
        for name in research_core_fields:
            field_obj = getattr(row.features, name)
            if not field_obj.available:
                missing_research.append(name)
        if not row.features.odds.closing_home_ml.available or not row.features.odds.closing_away_ml.available:
            missing_strict.append("closing_line")
            missing_research.append("closing_line")
        elif not _is_fresh(row.features.odds.closing_home_ml.observed_at) and row.features.odds.closing_home_ml.observed_at:
            stale_strict.append("closing_line")
        if not row.features.odds.odds_history.available:
            missing_strict.append("odds_history")
        elif not _is_fresh(row.features.odds.odds_history.observed_at):
            stale_strict.append("odds_history")
        if not row.features.injury_rest.injury_report.available:
            missing_strict.append("injury_report")
        elif not _is_fresh(row.features.injury_rest.injury_report.observed_at):
            stale_strict.append("injury_report")
        if not row.features.injury_rest.rest_days_home.available or not row.features.injury_rest.rest_days_away.available:
            missing_strict.append("rest_days")
        elif not _is_fresh(row.features.injury_rest.rest_days_home.observed_at) or not _is_fresh(row.features.injury_rest.rest_days_away.observed_at):
            stale_strict.append("rest_days")
        if row.home_team == "" or row.away_team == "" or row.game_date == "":
            missing_research.append("game_identity")

        if not missing_strict and not stale_strict:
            status_by_game[row.game_id] = MLBValidityTier.STRICT_VALID
            strict_count += 1
        elif not missing_research:
            status_by_game[row.game_id] = MLBValidityTier.RESEARCH_VALID
            research_count += 1
            issues.append(
                f"{row.game_id}: tier=RESEARCH_VALID missing_strict={','.join(sorted(set(missing_strict)))} stale_strict={','.join(sorted(set(stale_strict)))}"
            )
        else:
            status_by_game[row.game_id] = MLBValidityTier.INVALID
            issues.append(
                f"{row.game_id}: tier=INVALID missing_research={','.join(sorted(set(missing_research)))} missing_strict={','.join(sorted(set(missing_strict)))} stale_strict={','.join(sorted(set(stale_strict)))}"
            )

    return MLBValidationResult(
        total_games=len(rows),
        strict_valid_games=strict_count,
        research_valid_games=research_count,
        invalid_games=len(rows) - strict_count - research_count,
        status_by_game=status_by_game,
        issues=issues,
    )
