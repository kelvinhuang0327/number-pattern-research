from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from wbc_backend.domain.schemas import OddsLine


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import data.wbc_pool_a as wbc_pool_a  # noqa: E402
import data.wbc_pool_b as wbc_pool_b  # noqa: E402
import data.wbc_pool_c as wbc_pool_c  # noqa: E402
import data.wbc_pool_d as wbc_pool_d  # noqa: E402


POOL_MODULES: list[tuple[object, str, str]] = [
    (wbc_pool_a, "_TEAM_FACTORIES_A", "_POOL_A_SCHEDULE"),
    (wbc_pool_b, "_TEAM_FACTORIES_B", "_POOL_B_SCHEDULE"),
    (wbc_pool_c, "_TEAM_FACTORIES", "_POOL_C_SCHEDULE"),
    (wbc_pool_d, "_TEAM_FACTORIES_D", "_POOL_D_SCHEDULE"),
]


def _team_profile_rows() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for mod, factories_name, _ in POOL_MODULES:
        factories = getattr(mod, factories_name)
        for code, factory in factories.items():
            team, pitchers = factory()
            avg_stuff = sum(p.stuff_plus for p in pitchers.values()) / max(len(pitchers), 1)
            avg_fip = sum(p.fip for p in pitchers.values()) / max(len(pitchers), 1)
            avg_whip = sum(p.whip for p in pitchers.values()) / max(len(pitchers), 1)
            roster_vol = team.roster_vol
            top50 = len(roster_vol.confirmed_stars) if roster_vol else 0
            prior = (roster_vol.roster_strength_index if roster_vol else 70.0) / 4.0
            rows.append(
                {
                    "team": code,
                    "woba": team.team_woba,
                    "ops_plus": team.lineup_wrc_plus,
                    "fip": round(avg_fip, 4),
                    "whip": round(avg_whip, 4),
                    "stuff_plus": round(avg_stuff, 4),
                    "der": team.defense_efficiency,
                    "bullpen_depth": float(len(pitchers)),
                    "elo": team.elo,
                    "runs_per_game": team.runs_per_game,
                    "runs_allowed_per_game": team.runs_allowed_per_game,
                    "bullpen_era": team.bullpen_era,
                    "bullpen_pitches_3d": team.bullpen_pitches_3d,
                    "clutch_woba": team.clutch_woba,
                    "roster_strength_index": float(roster_vol.roster_strength_index) if roster_vol else 80.0,
                    "top50_stars": float(top50),
                    "sample_size": float(120 + top50 * 8),
                    "league_prior_strength": float(prior),
                    "win_pct_last_10": round(team.runs_per_game / max(team.runs_per_game + team.runs_allowed_per_game, 1.0), 4),
                    "rest_days": 1.0,
                }
            )
    return rows


def load_team_profiles() -> pd.DataFrame:
    return pd.DataFrame(_team_profile_rows())


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def load_pitcher_profiles() -> dict[str, dict[str, dict[str, float]]]:
    profiles: dict[str, dict[str, dict[str, float]]] = {}
    for mod, factories_name, _ in POOL_MODULES:
        factories = getattr(mod, factories_name)
        for code, factory in factories.items():
            _, pitchers = factory()
            team_map = profiles.setdefault(code, {})
            for pitcher in pitchers.values():
                team_map[_normalize_name(pitcher.name)] = {
                    "name": pitcher.name,
                    "team": pitcher.team,
                    "era": pitcher.era,
                    "fip": pitcher.fip,
                    "whip": pitcher.whip,
                    "k_per_9": pitcher.k_per_9,
                    "bb_per_9": pitcher.bb_per_9,
                    "stuff_plus": pitcher.stuff_plus,
                    "ip_last_30": pitcher.ip_last_30,
                    "era_last_3": pitcher.era_last_3,
                    "pitch_count_last_3d": pitcher.pitch_count_last_3d,
                    "fastball_velo": pitcher.fastball_velo,
                    "high_leverage_era": pitcher.high_leverage_era,
                    "role": pitcher.role,
                    "pitch_mix": {},
                    "recent_fastball_velos": [pitcher.fastball_velo],
                    "career_fastball_velo": pitcher.fastball_velo,
                    "woba_vs_left": pitcher.vs_left_ba * 1.25,
                    "woba_vs_right": pitcher.vs_right_ba * 1.25,
                    "innings_last_14d": min(pitcher.ip_last_30, 14.0),
                    "season_avg_innings_per_14d": max(5.0, pitcher.ip_last_30 / 2.0),
                    "recent_spin_rate": 2200.0 + pitcher.stuff_plus * 3.0,
                    "career_spin_rate_mean": 2200.0 + pitcher.stuff_plus * 2.8,
                    "career_spin_rate_std": 35.0,
                }
    return profiles


def load_game_odds() -> dict[str, list[OddsLine]]:
    output: dict[str, list[OddsLine]] = {}
    for mod, _, schedule_name in POOL_MODULES:
        for game in getattr(mod, schedule_name):
            odds_params = game.get("odds_params", {})
            away = game["away_code"]
            home = game["home_code"]
            game_id = game["game_id"]
            if not odds_params:
                continue

            lines = [
                OddsLine("LegacySeed", "ML", away, None, float(odds_params["ml_away"]), "seed"),
                OddsLine("LegacySeed", "ML", home, None, float(odds_params["ml_home"]), "seed"),
                OddsLine("LegacySeed", "RL", odds_params["rl_fav"], float(odds_params["rl_spread"]), float(odds_params["rl_fav_odds"]), "seed"),
                OddsLine("LegacySeed", "OU", "Over", float(odds_params["ou_line"]), float(odds_params["ou_over"]), "seed"),
                OddsLine("LegacySeed", "OU", "Under", float(odds_params["ou_line"]), float(odds_params["ou_under"]), "seed"),
                OddsLine("LegacySeed", "F5", away, None, float(odds_params["f5_away"]), "seed"),
                OddsLine("LegacySeed", "F5", home, None, float(odds_params["f5_home"]), "seed"),
            ]
            rl_dog = home if odds_params["rl_fav"] == away else away
            lines.append(
                OddsLine("LegacySeed", "RL", rl_dog, -float(odds_params["rl_spread"]), float(odds_params["rl_dog_odds"]), "seed")
            )
            output[game_id] = lines
    return output
