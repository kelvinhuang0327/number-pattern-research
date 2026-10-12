from __future__ import annotations

import pandas as pd

from wbc_backend.config.settings import AppConfig
from wbc_backend.ingestion.legacy_wbc_seed import (
    load_game_odds,
    load_pitcher_profiles,
    load_team_profiles,
)
from wbc_backend.ingestion.providers import LeagueDataProvider, WBCDataProvider


class UnifiedDataLoader:
    def __init__(self, config: AppConfig):
        self.config = config
        self.league_provider = LeagueDataProvider(config)
        self.wbc_provider = WBCDataProvider(config)

    def load_team_metrics(self) -> pd.DataFrame:
        mlb = self.league_provider.load_mlb_2025()
        npb = self.league_provider.load_npb_2025()
        kbo = self.league_provider.load_kbo_2025()
        wbc = self.wbc_provider.load_wbc_2025()
        legacy_wbc = load_team_profiles()

        stacked = pd.concat([mlb, npb, kbo, wbc, legacy_wbc], ignore_index=True)
        metric_columns = [
            "woba",
            "ops_plus",
            "fip",
            "whip",
            "stuff_plus",
            "der",
            "bullpen_depth",
            "elo",
            "runs_per_game",
            "runs_allowed_per_game",
            "bullpen_era",
            "bullpen_pitches_3d",
            "clutch_woba",
            "roster_strength_index",
            "top50_stars",
            "sample_size",
            "league_prior_strength",
            "win_pct_last_10",
            "rest_days",
        ]
        for column in metric_columns:
            if column not in stacked.columns:
                stacked[column] = pd.NA
        agg = (
            stacked.groupby("team", as_index=False)
            .agg(
                {
                    column: "mean" for column in metric_columns
                }
            )
            .round(4)
        )
        return agg

    def load_wbc_2026_matchups(self) -> pd.DataFrame:
        return self.wbc_provider.load_wbc_2026_live()

    def load_wbc_pitcher_profiles(self):
        return load_pitcher_profiles()

    def load_wbc_seed_odds(self):
        return load_game_odds()
