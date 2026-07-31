from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AvailabilityField:
    value: Any
    available: bool
    reason: str = ""
    source: str = ""
    observed_at: str = ""


@dataclass(frozen=True)
class MLBInjuryRestStatus:
    injury_report: AvailabilityField
    rest_days_home: AvailabilityField
    rest_days_away: AvailabilityField


@dataclass(frozen=True)
class MLBOddsSnapshot:
    opening_home_ml: AvailabilityField
    opening_away_ml: AvailabilityField
    decision_home_ml: AvailabilityField
    decision_away_ml: AvailabilityField
    latest_pregame_home_ml: AvailabilityField
    latest_pregame_away_ml: AvailabilityField
    closing_home_ml: AvailabilityField
    closing_away_ml: AvailabilityField
    odds_history: AvailabilityField


@dataclass(frozen=True)
class MLBFeatureBundle:
    probable_home_starter: AvailabilityField
    probable_away_starter: AvailabilityField
    confirmed_home_starter: AvailabilityField
    confirmed_away_starter: AvailabilityField
    confirmed_home_lineup: AvailabilityField
    confirmed_away_lineup: AvailabilityField
    bullpen_usage_last_3d_home: AvailabilityField
    bullpen_usage_last_3d_away: AvailabilityField
    home_away_splits: AvailabilityField
    platoon_splits: AvailabilityField
    park_factors: AvailabilityField
    weather: AvailabilityField
    wind: AvailabilityField
    injury_rest: MLBInjuryRestStatus
    odds: MLBOddsSnapshot


@dataclass(frozen=True)
class MLBGameData:
    game_id: str
    game_date: str
    home_team: str
    away_team: str
    status: str
    home_score: int | None
    away_score: int | None
    features: MLBFeatureBundle
    metadata: dict[str, Any] = field(default_factory=dict)
