from __future__ import annotations

from .schema import MLBGameData
from .validator import MLBValidationResult


def build_health_report(rows: list[MLBGameData], validation: MLBValidationResult) -> dict:
    n = max(1, len(rows))
    availability_counts = {
        "confirmed_home_starter": 0,
        "confirmed_away_starter": 0,
        "confirmed_home_lineup": 0,
        "confirmed_away_lineup": 0,
        "bullpen_usage_last_3d_home": 0,
        "bullpen_usage_last_3d_away": 0,
        "home_away_splits": 0,
        "platoon_splits": 0,
        "park_factors": 0,
        "weather": 0,
        "wind": 0,
        "injury_report": 0,
        "rest_days_home": 0,
        "rest_days_away": 0,
        "odds_history": 0,
        "closing_line_home": 0,
        "closing_line_away": 0,
    }
    for row in rows:
        f = row.features
        for key in (
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
        ):
            if getattr(f, key).available:
                availability_counts[key] += 1
        if f.injury_rest.injury_report.available:
            availability_counts["injury_report"] += 1
        if f.injury_rest.rest_days_home.available:
            availability_counts["rest_days_home"] += 1
        if f.injury_rest.rest_days_away.available:
            availability_counts["rest_days_away"] += 1
        if f.odds.odds_history.available:
            availability_counts["odds_history"] += 1
        if f.odds.closing_home_ml.available:
            availability_counts["closing_line_home"] += 1
        if f.odds.closing_away_ml.available:
            availability_counts["closing_line_away"] += 1
    return {
        "total_games": len(rows),
        "validation_is_valid": validation.is_valid,
        "strict_valid_games": validation.strict_valid_games,
        "research_valid_games": validation.research_valid_games,
        "invalid_games": validation.invalid_games,
        "strict_valid_rate": round(validation.strict_valid_games / n, 4),
        "status_distribution": {
            "STRICT_VALID": validation.strict_valid_games,
            "RESEARCH_VALID": validation.research_valid_games,
            "INVALID": validation.invalid_games,
        },
        "availability_pct": {k: round(v / n, 4) for k, v in availability_counts.items()},
        "top_issues": validation.issues[:20],
    }
