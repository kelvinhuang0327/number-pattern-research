from __future__ import annotations

import pandas as pd

from wbc_backend.domain.schemas import Matchup, TeamSnapshot


def _to_team_snapshot(team_code: str, team_row: pd.Series, row: pd.Series, home_away_prefix: str) -> TeamSnapshot:
    p = home_away_prefix
    return TeamSnapshot(
        team=team_code,
        elo=float(team_row["elo"]),
        batting_woba=float(team_row["woba"]),
        batting_ops_plus=float(team_row["ops_plus"]),
        pitching_fip=float(team_row["fip"]),
        pitching_whip=float(team_row["whip"]),
        pitching_stuff_plus=float(team_row["stuff_plus"]),
        der=float(team_row["der"]),
        bullpen_depth=float(team_row["bullpen_depth"]),
        pitch_limit=int(row[f"{p}_pitch_limit"]),
        missing_core_batter=bool(row.get(f"{p}_missing_core_batter", False)),
        ace_pitch_count_limited=bool(row.get(f"{p}_ace_limited", False)),
        top50_stars=int(row.get(f"{p}_top50_stars", 0)),
        sample_size=int(row.get(f"{p}_sample_size", 120)),
        league_prior_strength=float(row.get(f"{p}_league_prior_strength", 0.0)),
    )


def build_matchups(metrics_df: pd.DataFrame, schedule_df: pd.DataFrame) -> list[Matchup]:
    lookup = metrics_df.set_index("team")
    matchups: list[Matchup] = []

    for _, row in schedule_df.iterrows():
        home_code = row["home"]
        away_code = row["away"]
        home = lookup.loc[home_code]
        away = lookup.loc[away_code]
        matchup = Matchup(
            game_id=row["game_id"],
            tournament=row["tournament"],
            game_time_utc=row["game_time_utc"],
            home=_to_team_snapshot(home_code, home, row, "home"),
            away=_to_team_snapshot(away_code, away, row, "away"),
        )
        matchups.append(matchup)

    return matchups
