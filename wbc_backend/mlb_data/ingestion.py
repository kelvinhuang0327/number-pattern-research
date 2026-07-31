from __future__ import annotations

import pandas as pd

from .context_connectors import (
    ConnectorBundle,
    get_bullpen_usage_last_3d,
    get_confirmed_lineups,
    get_injury_rest_status,
    get_odds_timeline,
    get_weather_wind,
    load_connectors,
)
from .ids import make_mlb_game_id
from .schema import (
    AvailabilityField,
    MLBFeatureBundle,
    MLBGameData,
    MLBInjuryRestStatus,
    MLBOddsSnapshot,
)


def _available(value, source: str = "", reason_if_missing: str = "missing", observed_at: str = "") -> AvailabilityField:
    missing = value is None or (isinstance(value, float) and pd.isna(value)) or value == ""
    if missing:
        return AvailabilityField(value=None, available=False, reason=reason_if_missing, source=source, observed_at=observed_at)
    return AvailabilityField(value=value, available=True, reason="", source=source, observed_at=observed_at)


def load_mlb_game_data(
    csv_path: str | Path = "data/mlb_2025/mlb_odds_2025_real.csv",
    context_path: str | Path | None = "data/mlb_context",
) -> list[MLBGameData]:
    df = pd.read_csv(csv_path)
    bundle: ConnectorBundle = load_connectors(context_path or "data/mlb_context")
    rows: list[MLBGameData] = []

    for _, row in df.iterrows():
        game_id = make_mlb_game_id(
            str(row.get("Date", "")),
            str(row.get("Start Time (EDT)", "")),
            str(row.get("Away", "")),
            str(row.get("Home", "")),
        )
        lineup_pack = get_confirmed_lineups(bundle, game_id)
        bullpen_pack = get_bullpen_usage_last_3d(bundle, game_id)
        odds_pack = get_odds_timeline(bundle, game_id)
        weather_pack = get_weather_wind(bundle, game_id)
        injury_pack = get_injury_rest_status(bundle, game_id)
        lineup_ts = str(lineup_pack.get("fetched_at", ""))
        bullpen_ts = str(bullpen_pack.get("fetched_at", ""))
        odds_ts = str(odds_pack.get("fetched_at", ""))
        weather_ts = str(weather_pack.get("fetched_at", ""))
        injury_ts = str(injury_pack.get("fetched_at", ""))
        injury_status = MLBInjuryRestStatus(
            injury_report=_available(injury_pack.get("injury_report"), source="injury_rest_connector", reason_if_missing="injury_report_unavailable", observed_at=injury_ts),
            rest_days_home=_available(injury_pack.get("rest_days_home"), source="injury_rest_connector", reason_if_missing="rest_days_home_unavailable", observed_at=injury_ts),
            rest_days_away=_available(injury_pack.get("rest_days_away"), source="injury_rest_connector", reason_if_missing="rest_days_away_unavailable", observed_at=injury_ts),
        )
        odds = MLBOddsSnapshot(
            opening_home_ml=_available(odds_pack.get("opening_home_ml"), source="odds_timeline_connector", reason_if_missing="opening_line_unavailable", observed_at=odds_ts),
            opening_away_ml=_available(odds_pack.get("opening_away_ml"), source="odds_timeline_connector", reason_if_missing="opening_line_unavailable", observed_at=odds_ts),
            decision_home_ml=_available(odds_pack.get("decision_home_ml"), source="odds_timeline_connector", reason_if_missing="decision_line_unavailable", observed_at=str(odds_pack.get("decision_ts", odds_ts))),
            decision_away_ml=_available(odds_pack.get("decision_away_ml"), source="odds_timeline_connector", reason_if_missing="decision_line_unavailable", observed_at=str(odds_pack.get("decision_ts", odds_ts))),
            latest_pregame_home_ml=_available(odds_pack.get("latest_pregame_home_ml"), source="odds_timeline_connector", reason_if_missing="latest_pregame_line_unavailable", observed_at=str(odds_pack.get("latest_pregame_ts", odds_ts))),
            latest_pregame_away_ml=_available(odds_pack.get("latest_pregame_away_ml"), source="odds_timeline_connector", reason_if_missing="latest_pregame_line_unavailable", observed_at=str(odds_pack.get("latest_pregame_ts", odds_ts))),
            closing_home_ml=_available(odds_pack.get("closing_home_ml"), source="odds_timeline_connector", reason_if_missing="closing_home_ml_missing", observed_at=str(odds_pack.get("closing_ts", odds_ts))),
            closing_away_ml=_available(odds_pack.get("closing_away_ml"), source="odds_timeline_connector", reason_if_missing="closing_away_ml_missing", observed_at=str(odds_pack.get("closing_ts", odds_ts))),
            odds_history=_available(odds_pack.get("odds_history"), source="odds_timeline_connector", reason_if_missing="odds_history_unavailable", observed_at=odds_ts),
        )
        features = MLBFeatureBundle(
            probable_home_starter=_available(row.get("Home Starter"), source="mlb_odds_csv", reason_if_missing="probable_home_starter_missing"),
            probable_away_starter=_available(row.get("Away Starter"), source="mlb_odds_csv", reason_if_missing="probable_away_starter_missing"),
            confirmed_home_starter=_available(lineup_pack.get("confirmed_home_starter"), source="lineups_connector", reason_if_missing="confirmed_home_starter_unavailable", observed_at=lineup_ts),
            confirmed_away_starter=_available(lineup_pack.get("confirmed_away_starter"), source="lineups_connector", reason_if_missing="confirmed_away_starter_unavailable", observed_at=lineup_ts),
            confirmed_home_lineup=_available(lineup_pack.get("confirmed_home_lineup"), source="lineups_connector", reason_if_missing="confirmed_home_lineup_unavailable", observed_at=lineup_ts),
            confirmed_away_lineup=_available(lineup_pack.get("confirmed_away_lineup"), source="lineups_connector", reason_if_missing="confirmed_away_lineup_unavailable", observed_at=lineup_ts),
            bullpen_usage_last_3d_home=_available(bullpen_pack.get("bullpen_usage_last_3d_home"), source="bullpen_3d_connector", reason_if_missing="bullpen_usage_home_unavailable", observed_at=bullpen_ts),
            bullpen_usage_last_3d_away=_available(bullpen_pack.get("bullpen_usage_last_3d_away"), source="bullpen_3d_connector", reason_if_missing="bullpen_usage_away_unavailable", observed_at=bullpen_ts),
            home_away_splits=_available(lineup_pack.get("home_away_splits"), source="lineups_connector", reason_if_missing="home_away_splits_unavailable", observed_at=lineup_ts),
            platoon_splits=_available(lineup_pack.get("platoon_splits"), source="lineups_connector", reason_if_missing="platoon_splits_unavailable", observed_at=lineup_ts),
            park_factors=_available(weather_pack.get("park_factors"), source="weather_wind_connector", reason_if_missing="park_factors_unavailable", observed_at=weather_ts),
            weather=_available(weather_pack.get("weather"), source="weather_wind_connector", reason_if_missing="weather_unavailable", observed_at=weather_ts),
            wind=_available(weather_pack.get("wind"), source="weather_wind_connector", reason_if_missing="wind_unavailable", observed_at=weather_ts),
            injury_rest=injury_status,
            odds=odds,
        )
        rows.append(
            MLBGameData(
                game_id=game_id,
                game_date=str(row.get("Date", "")),
                home_team=str(row.get("Home", "")),
                away_team=str(row.get("Away", "")),
                status=str(row.get("Status", "")),
                home_score=int(row["Home Score"]) if pd.notna(row.get("Home Score")) else None,
                away_score=int(row["Away Score"]) if pd.notna(row.get("Away Score")) else None,
                features=features,
                metadata={
                    "source_file": row.get("source_file", ""),
                    "source_type": row.get("source_type", ""),
                    "is_verified_real": bool(row.get("is_verified_real", False)),
                },
            )
        )
    return rows
