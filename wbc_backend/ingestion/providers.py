from __future__ import annotations

from pathlib import Path

import pandas as pd

from wbc_backend.config.settings import AppConfig
from wbc_backend.data.wbc_verification import WBCAuthoritativeSnapshot


TEAM_METRIC_COLUMNS = {
    "team",
    "woba",
    "ops_plus",
    "fip",
    "whip",
    "stuff_plus",
    "der",
    "bullpen_depth",
    "elo",
}


class LeagueDataProvider:
    def __init__(self, config: AppConfig):
        self.config = config

    def _safe_read(self, path: str, fallback: list[dict]) -> pd.DataFrame:
        file_path = Path(path)
        if not file_path.exists():
            return pd.DataFrame(fallback)

        for encoding in ("utf-8", "utf-8-sig", "latin1"):
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                if TEAM_METRIC_COLUMNS.issubset(set(df.columns)):
                    return df
                return pd.DataFrame(fallback)
            except Exception:
                continue

        return pd.DataFrame(fallback)

    def load_mlb_2025(self) -> pd.DataFrame:
        fallback = [
            {"team": "JPN", "woba": 0.347, "ops_plus": 118, "fip": 3.38, "whip": 1.12, "stuff_plus": 108, "der": 0.713, "bullpen_depth": 8.8, "elo": 1575},
            {"team": "USA", "woba": 0.339, "ops_plus": 121, "fip": 3.51, "whip": 1.18, "stuff_plus": 111, "der": 0.706, "bullpen_depth": 8.4, "elo": 1560},
        ]
        return self._safe_read(self.config.sources.mlb_2025_csv, fallback)

    def load_npb_2025(self) -> pd.DataFrame:
        fallback = [{"team": "JPN", "woba": 0.352, "ops_plus": 122, "fip": 3.22, "whip": 1.09, "stuff_plus": 110, "der": 0.718, "bullpen_depth": 8.9, "elo": 1582}]
        return self._safe_read(self.config.sources.npb_2025_csv, fallback)

    def load_kbo_2025(self) -> pd.DataFrame:
        fallback = [{"team": "KOR", "woba": 0.336, "ops_plus": 111, "fip": 3.61, "whip": 1.21, "stuff_plus": 104, "der": 0.701, "bullpen_depth": 8.1, "elo": 1528}]
        return self._safe_read(self.config.sources.kbo_2025_csv, fallback)


class WBCDataProvider:
    def __init__(self, config: AppConfig):
        self.config = config

    def load_wbc_2025(self) -> pd.DataFrame:
        fallback = [
            {"team": "TPE", "woba": 0.328, "ops_plus": 106, "fip": 2.45, "whip": 0.81, "stuff_plus": 118, "der": 0.705, "bullpen_depth": 7.8, "elo": 1515},
            {"team": "AUS", "woba": 0.321, "ops_plus": 101, "fip": 5.85, "whip": 1.65, "stuff_plus": 98, "der": 0.695, "bullpen_depth": 7.2, "elo": 1478},
        ]
        path = Path(self.config.sources.wbc_2025_csv)
        if not path.exists():
            return pd.DataFrame(fallback)

        for encoding in ("utf-8", "utf-8-sig", "latin1"):
            try:
                df = pd.read_csv(path, encoding=encoding)
                if TEAM_METRIC_COLUMNS.issubset(set(df.columns)):
                    return df
            except Exception:
                continue

        return pd.DataFrame(fallback)

    def load_wbc_2026_live(self) -> pd.DataFrame:
        repo = WBCAuthoritativeSnapshot(self.config.sources.wbc_authoritative_snapshot_json)
        rows = repo.to_schedule_rows()
        if not rows:
            return pd.DataFrame(
                columns=[
                    "game_id",
                    "aliases",
                    "tournament",
                    "round_name",
                    "game_time_utc",
                    "game_time_local",
                    "venue",
                    "home",
                    "away",
                    "schedule_verified",
                    "rosters_verified",
                    "starters_verified",
                    "lineups_verified",
                    "last_verified_at",
                ]
            )
        return pd.DataFrame(rows)
