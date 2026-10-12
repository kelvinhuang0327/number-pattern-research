"""
WBC 2026 Pool B — 10-game schedule (Houston, Texas).

Teams: USA, MEX, ITA, GBR, BRA
Venue: Minute Maid Park, Houston
Round: Pool B (pitch-count limit: 65 pitches)

Usage:
    from data.wbc_pool_b import fetch_wbc_match_b, list_wbc_matches_b
"""
from __future__ import annotations

import datetime
from typing import Dict, List, Optional, Tuple

from data.wbc_data import (
    PitcherStats, BatterStats, TeamStats, RosterVolatility,
    OddsLine, PitchCountRule, MatchData,
    _build_bullpen, _build_lineup,
)
from data.tsl_crawler import TSLCrawler


def _std_odds(away: str, home: str, ts: str,
              ml_away: float, ml_home: float,
              rl_spread: float, rl_fav: str, rl_fav_odds: float, rl_dog_odds: float,
              ou_line: float, ou_over: float, ou_under: float,
              f5_away: float, f5_home: float,
              tt_away_line: float, tt_home_line: float) -> List[OddsLine]:
    rl_dog = home if rl_fav == away else away
    return [
        OddsLine("TSL", "ML", away, ml_away, timestamp=ts),
        OddsLine("TSL", "ML", home, ml_home, timestamp=ts),
        OddsLine("TSL", "RL", rl_fav, rl_fav_odds, line=-rl_spread, timestamp=ts),
        OddsLine("TSL", "RL", rl_dog, rl_dog_odds, line=+rl_spread, timestamp=ts),
        OddsLine("TSL", "OU", "Over",  ou_over,  line=ou_line, timestamp=ts),
        OddsLine("TSL", "OU", "Under", ou_under, line=ou_line, timestamp=ts),
        OddsLine("TSL", "OE", "Odd",  1.90, timestamp=ts),
        OddsLine("TSL", "OE", "Even", 1.90, timestamp=ts),
        OddsLine("TSL", "F5", away, f5_away, timestamp=ts),
        OddsLine("TSL", "F5", home, f5_home, timestamp=ts),
        OddsLine("TSL", "TT", f"{away}_Over",  1.85, line=tt_away_line, timestamp=ts),
        OddsLine("TSL", "TT", f"{away}_Under", 1.95, line=tt_away_line, timestamp=ts),
        OddsLine("TSL", "TT", f"{home}_Over",  1.85, line=tt_home_line, timestamp=ts),
        OddsLine("TSL", "TT", f"{home}_Under", 1.95, line=tt_home_line, timestamp=ts),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM DEFINITIONS — POOL B
# ═══════════════════════════════════════════════════════════════════════════════

def _team_usa() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """United States — Defending champion contender. Elo 1600."""
    roster = RosterVolatility(
        roster_strength_index=96,
        confirmed_stars=["Aaron Judge", "Bryce Harper", "Bobby Witt Jr.",
                         "Gunnar Henderson", "Paul Goldschmidt", "Tarik Skubal"],
        uncertain_stars=["Corbin Burnes"],
        absent_stars=[],
        team_chemistry=0.86,
        mlb_player_count=28,
    )
    team = TeamStats(
        name="United States", code="USA", elo=1600,
        runs_per_game=5.5, runs_allowed_per_game=3.0,
        batting_avg=0.278, team_obp=0.352, team_slg=0.460,
        team_woba=0.360, bullpen_era=2.60,
        bullpen_pitches_3d=0,
        defense_efficiency=0.722, sb_success_rate=0.78,
        lineup_wrc_plus=135, clutch_woba=0.355,
        roster_vol=roster,
    )
    pitchers = {
        "skubal": PitcherStats(
            name="Tarik Skubal", team="USA",
            era=2.50, fip=2.70, whip=0.95, k_per_9=11.0, bb_per_9=1.8,
            stuff_plus=130, ip_last_30=28.0, era_last_3=2.20,
            spring_era=2.10, pitch_count_last_3d=0,
            vs_left_ba=0.195, vs_right_ba=0.205,
            high_leverage_era=2.40, fastball_velo=96.0, role="SP",
        ),
        "burnes": PitcherStats(
            name="Corbin Burnes", team="USA",
            era=2.92, fip=3.10, whip=1.08, k_per_9=9.5, bb_per_9=2.0,
            stuff_plus=122, ip_last_30=26.0, era_last_3=2.70,
            spring_era=2.50, pitch_count_last_3d=0,
            vs_left_ba=0.215, vs_right_ba=0.210,
            high_leverage_era=2.80, fastball_velo=96.5, role="SP",
        ),
        "webb": PitcherStats(
            name="Logan Webb", team="USA",
            era=3.20, fip=3.40, whip=1.15, k_per_9=7.8, bb_per_9=2.2,
            stuff_plus=110, ip_last_30=24.0, era_last_3=3.00,
            spring_era=2.90, pitch_count_last_3d=0,
            vs_left_ba=0.230, vs_right_ba=0.222,
            high_leverage_era=3.30, fastball_velo=93.5, role="SP",
        ),
        "miller_pb": PitcherStats(
            name="Mason Miller", team="USA",
            era=2.20, fip=2.10, whip=0.88, k_per_9=14.0, bb_per_9=3.0,
            stuff_plus=140, ip_last_30=8.0, era_last_3=1.80,
            spring_era=1.90, pitch_count_last_3d=0,
            vs_left_ba=0.160, vs_right_ba=0.155,
            high_leverage_era=2.00, fastball_velo=102.0, role="PB",
        ),
        "holmes_pb": PitcherStats(
            name="Clay Holmes", team="USA",
            era=3.00, fip=3.20, whip=1.10, k_per_9=9.0, bb_per_9=3.5,
            stuff_plus=118, ip_last_30=10.0, era_last_3=2.80,
            spring_era=2.60, pitch_count_last_3d=0,
            vs_left_ba=0.210, vs_right_ba=0.200,
            high_leverage_era=3.00, fastball_velo=98.0, role="PB",
        ),
    }
    return team, pitchers


def _team_mex() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Mexico — Strong MLB presence, dangerous offense. Elo 1440."""
    roster = RosterVolatility(
        roster_strength_index=82,
        confirmed_stars=["Randy Arozarena", "Andrés Muñoz", "Jarren Duran",
                         "Isaac Paredes", "Alejandro Kirk"],
        uncertain_stars=["Julio Urías"],
        absent_stars=[],
        team_chemistry=0.83,
        mlb_player_count=12,
    )
    team = TeamStats(
        name="Mexico", code="MEX", elo=1440,
        runs_per_game=4.8, runs_allowed_per_game=3.8,
        batting_avg=0.268, team_obp=0.335, team_slg=0.415,
        team_woba=0.332, bullpen_era=3.40,
        bullpen_pitches_3d=0,
        defense_efficiency=0.708, sb_success_rate=0.74,
        lineup_wrc_plus=112, clutch_woba=0.325,
        roster_vol=roster,
    )
    pitchers = {
        "assad": PitcherStats(
            name="Javier Assad", team="MEX",
            era=3.30, fip=3.50, whip=1.18, k_per_9=8.0, bb_per_9=2.5,
            stuff_plus=108, ip_last_30=22.0, era_last_3=3.10,
            spring_era=3.00, pitch_count_last_3d=0,
            vs_left_ba=0.235, vs_right_ba=0.230,
            high_leverage_era=3.40, fastball_velo=94.0, role="SP",
        ),
        "bradley": PitcherStats(
            name="Taj Bradley", team="MEX",
            era=3.60, fip=3.50, whip=1.20, k_per_9=9.5, bb_per_9=2.8,
            stuff_plus=115, ip_last_30=20.0, era_last_3=3.30,
            spring_era=3.20, pitch_count_last_3d=0,
            vs_left_ba=0.238, vs_right_ba=0.225,
            high_leverage_era=3.70, fastball_velo=96.0, role="SP",
        ),
        "walker": PitcherStats(
            name="Taijuan Walker", team="MEX",
            era=4.20, fip=4.30, whip=1.30, k_per_9=7.0, bb_per_9=2.8,
            stuff_plus=95, ip_last_30=16.0, era_last_3=4.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.250, vs_right_ba=0.245,
            high_leverage_era=4.50, fastball_velo=93.0, role="SP",
        ),
        "munoz_pb": PitcherStats(
            name="Andrés Muñoz", team="MEX",
            era=2.40, fip=2.30, whip=0.95, k_per_9=13.0, bb_per_9=3.2,
            stuff_plus=138, ip_last_30=8.0, era_last_3=2.00,
            spring_era=2.10, pitch_count_last_3d=0,
            vs_left_ba=0.170, vs_right_ba=0.165,
            high_leverage_era=2.20, fastball_velo=101.5, role="PB",
        ),
    }
    return team, pitchers


def _team_ita() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Italy — Surprising 2023 WBC darkhorse, MLB-heritage roster. Elo 1350."""
    roster = RosterVolatility(
        roster_strength_index=68,
        confirmed_stars=["Vinnie Pasquantino", "Jordan Romano", "Andre Pallante"],
        uncertain_stars=["Dominic Canzone"],
        absent_stars=[],
        team_chemistry=0.78,
        mlb_player_count=8,
    )
    team = TeamStats(
        name="Italy", code="ITA", elo=1350,
        runs_per_game=4.0, runs_allowed_per_game=4.2,
        batting_avg=0.255, team_obp=0.320, team_slg=0.390,
        team_woba=0.312, bullpen_era=3.80,
        bullpen_pitches_3d=0,
        defense_efficiency=0.700, sb_success_rate=0.70,
        lineup_wrc_plus=95, clutch_woba=0.305,
        roster_vol=roster,
    )
    pitchers = {
        "pallante": PitcherStats(
            name="Andre Pallante", team="ITA",
            era=3.50, fip=3.70, whip=1.22, k_per_9=7.5, bb_per_9=2.5,
            stuff_plus=105, ip_last_30=20.0, era_last_3=3.30,
            spring_era=3.20, pitch_count_last_3d=0,
            vs_left_ba=0.245, vs_right_ba=0.235,
            high_leverage_era=3.60, fastball_velo=95.0, role="SP",
        ),
        "biagini": PitcherStats(
            name="Joe Biagini", team="ITA",
            era=4.20, fip=4.30, whip=1.32, k_per_9=7.0, bb_per_9=3.0,
            stuff_plus=95, ip_last_30=14.0, era_last_3=4.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.258, vs_right_ba=0.250,
            high_leverage_era=4.50, fastball_velo=92.0, role="SP",
        ),
        "aldegheri": PitcherStats(
            name="Samuel Aldegheri", team="ITA",
            era=4.50, fip=4.60, whip=1.38, k_per_9=7.2, bb_per_9=3.2,
            stuff_plus=92, ip_last_30=12.0, era_last_3=4.30,
            spring_era=4.00, pitch_count_last_3d=0,
            vs_left_ba=0.262, vs_right_ba=0.255,
            high_leverage_era=4.80, fastball_velo=91.5, role="SP",
        ),
        "romano_pb": PitcherStats(
            name="Jordan Romano", team="ITA",
            era=2.90, fip=2.80, whip=1.00, k_per_9=11.5, bb_per_9=2.8,
            stuff_plus=125, ip_last_30=8.0, era_last_3=2.50,
            spring_era=2.40, pitch_count_last_3d=0,
            vs_left_ba=0.195, vs_right_ba=0.185,
            high_leverage_era=2.70, fastball_velo=97.5, role="PB",
        ),
    }
    return team, pitchers


def _team_gbr() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Great Britain — Dark horse with Jazz Chisholm. Elo 1250."""
    roster = RosterVolatility(
        roster_strength_index=55,
        confirmed_stars=["Jazz Chisholm Jr.", "Trayce Thompson", "Harry Ford"],
        uncertain_stars=[],
        absent_stars=[],
        team_chemistry=0.72,
        mlb_player_count=4,
    )
    team = TeamStats(
        name="Great Britain", code="GBR", elo=1250,
        runs_per_game=3.5, runs_allowed_per_game=4.8,
        batting_avg=0.240, team_obp=0.305, team_slg=0.365,
        team_woba=0.292, bullpen_era=4.80,
        bullpen_pitches_3d=0,
        defense_efficiency=0.688, sb_success_rate=0.68,
        lineup_wrc_plus=82, clutch_woba=0.282,
        roster_vol=roster,
    )
    pitchers = {
        "worley": PitcherStats(
            name="Vance Worley", team="GBR",
            era=4.80, fip=4.90, whip=1.42, k_per_9=6.0, bb_per_9=3.0,
            stuff_plus=82, ip_last_30=12.0, era_last_3=4.50,
            spring_era=4.30, pitch_count_last_3d=0,
            vs_left_ba=0.275, vs_right_ba=0.280,
            high_leverage_era=5.20, fastball_velo=89.5, role="SP",
        ),
        "beck": PitcherStats(
            name="Tristan Beck", team="GBR",
            era=4.50, fip=4.60, whip=1.38, k_per_9=6.5, bb_per_9=3.2,
            stuff_plus=85, ip_last_30=10.0, era_last_3=4.30,
            spring_era=4.10, pitch_count_last_3d=0,
            vs_left_ba=0.270, vs_right_ba=0.275,
            high_leverage_era=4.80, fastball_velo=90.5, role="SP",
        ),
        "fernander": PitcherStats(
            name="Chavez Fernander", team="GBR",
            era=5.20, fip=5.30, whip=1.50, k_per_9=5.8, bb_per_9=3.5,
            stuff_plus=80, ip_last_30=8.0, era_last_3=5.00,
            spring_era=4.80, pitch_count_last_3d=0,
            vs_left_ba=0.282, vs_right_ba=0.288,
            high_leverage_era=5.50, fastball_velo=89.0, role="SP",
        ),
        "petersen_pb": PitcherStats(
            name="Michael Petersen", team="GBR",
            era=5.00, fip=5.10, whip=1.48, k_per_9=5.5, bb_per_9=3.8,
            stuff_plus=78, ip_last_30=6.0, era_last_3=4.80,
            spring_era=4.60, pitch_count_last_3d=0,
            vs_left_ba=0.285, vs_right_ba=0.290,
            high_leverage_era=5.30, fastball_velo=88.5, role="PB",
        ),
    }
    return team, pitchers


def _team_bra() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Brazil — Weakest Pool B team, developing program. Elo 1180."""
    roster = RosterVolatility(
        roster_strength_index=40,
        confirmed_stars=["Eric Pardinho", "Thyago Vieira"],
        uncertain_stars=[],
        absent_stars=[],
        team_chemistry=0.75,
        mlb_player_count=1,
    )
    team = TeamStats(
        name="Brazil", code="BRA", elo=1180,
        runs_per_game=3.0, runs_allowed_per_game=5.8,
        batting_avg=0.228, team_obp=0.290, team_slg=0.330,
        team_woba=0.272, bullpen_era=5.50,
        bullpen_pitches_3d=0,
        defense_efficiency=0.675, sb_success_rate=0.65,
        lineup_wrc_plus=65, clutch_woba=0.262,
        roster_vol=roster,
    )
    pitchers = {
        "pardinho": PitcherStats(
            name="Eric Pardinho", team="BRA",
            era=4.30, fip=4.20, whip=1.32, k_per_9=8.5, bb_per_9=3.5,
            stuff_plus=100, ip_last_30=14.0, era_last_3=4.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.250, vs_right_ba=0.245,
            high_leverage_era=4.50, fastball_velo=94.5, role="SP",
        ),
        "takahashi_b": PitcherStats(
            name="Bo Takahashi", team="BRA",
            era=5.20, fip=5.40, whip=1.50, k_per_9=6.0, bb_per_9=3.8,
            stuff_plus=82, ip_last_30=10.0, era_last_3=5.00,
            spring_era=4.80, pitch_count_last_3d=0,
            vs_left_ba=0.278, vs_right_ba=0.282,
            high_leverage_era=5.50, fastball_velo=89.0, role="SP",
        ),
        "misaki": PitcherStats(
            name="Daniel Misaki", team="BRA",
            era=5.50, fip=5.60, whip=1.55, k_per_9=5.5, bb_per_9=4.0,
            stuff_plus=78, ip_last_30=8.0, era_last_3=5.30,
            spring_era=5.00, pitch_count_last_3d=0,
            vs_left_ba=0.285, vs_right_ba=0.290,
            high_leverage_era=5.80, fastball_velo=88.0, role="SP",
        ),
        "vieira_pb": PitcherStats(
            name="Thyago Vieira", team="BRA",
            era=4.00, fip=4.10, whip=1.28, k_per_9=9.0, bb_per_9=4.0,
            stuff_plus=108, ip_last_30=6.0, era_last_3=3.80,
            spring_era=3.60, pitch_count_last_3d=0,
            vs_left_ba=0.238, vs_right_ba=0.232,
            high_leverage_era=4.20, fastball_velo=98.0, role="PB",
        ),
    }
    return team, pitchers


_TEAM_FACTORIES_B = {
    "USA": _team_usa,
    "MEX": _team_mex,
    "ITA": _team_ita,
    "GBR": _team_gbr,
    "BRA": _team_bra,
}

# ═══════════════════════════════════════════════════════════════════════════════
# POOL B GAME SCHEDULE (10 games)
# Venue: Minute Maid Park, Houston (CST UTC-6, CDT UTC-5 after Mar 8 DST)
# ═══════════════════════════════════════════════════════════════════════════════

_POOL_B_SCHEDULE = [
    # ─── Day 1: March 7 (TW) / March 6 (Local) ──────────
    {
        "game_id": "B01",
        "date": "2026-03-07",
        "game_time": "2026-03-06T12:00:00-06:00",
        "tw_time": "03/07 02:00",
        "away_code": "MEX",
        "home_code": "GBR",
        "away_sp": "assad",
        "home_sp": "worley",
        "away_pb": "munoz_pb",
        "home_pb": "petersen_pb",
        "away_bp_pitches_3d": 0,
        "home_bp_pitches_3d": 0,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.38, "ml_home": 3.20,
            "rl_spread": 2.5, "rl_fav": "MEX", "rl_fav_odds": 1.90, "rl_dog_odds": 1.90,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 1.42, "f5_home": 3.00,
            "tt_away_line": 4.5, "tt_home_line": 2.5,
        },
    },
    {
        "game_id": "B02",
        "date": "2026-03-07",
        "game_time": "2026-03-06T19:00:00-06:00",
        "tw_time": "03/07 09:00",
        "away_code": "USA",
        "home_code": "BRA",
        "away_sp": "skubal",
        "home_sp": "pardinho",
        "away_pb": "miller_pb",
        "home_pb": "vieira_pb",
        "away_bp_pitches_3d": 0,
        "home_bp_pitches_3d": 0,
        "neutral_site": False,  # USA as home at Minute Maid
        "odds_params": {
            "ml_away": 1.08, "ml_home": 8.50,
            "rl_spread": 3.5, "rl_fav": "USA", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 8.5, "ou_over": 1.90, "ou_under": 1.90,
            "f5_away": 1.10, "f5_home": 7.00,
            "tt_away_line": 5.5, "tt_home_line": 2.5,
        },
    },
    # ─── Day 2: March 8 (TW) / March 7 (Local) ──────────
    {
        "game_id": "B03",
        "date": "2026-03-08",
        "game_time": "2026-03-07T12:00:00-06:00",
        "tw_time": "03/08 02:00",
        "away_code": "BRA",
        "home_code": "ITA",
        "away_sp": "takahashi_b",
        "home_sp": "pallante",
        "away_pb": "vieira_pb",
        "home_pb": "romano_pb",
        "away_bp_pitches_3d": 65,
        "home_bp_pitches_3d": 0,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 3.50, "ml_home": 1.35,
            "rl_spread": 2.5, "rl_fav": "ITA", "rl_fav_odds": 1.90, "rl_dog_odds": 1.90,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 3.20, "f5_home": 1.38,
            "tt_away_line": 2.5, "tt_home_line": 4.5,
        },
    },
    {
        "game_id": "B04",
        "date": "2026-03-08",
        "game_time": "2026-03-07T18:00:00-06:00",
        "tw_time": "03/08 08:00",
        "away_code": "GBR",
        "home_code": "USA",
        "away_sp": "beck",
        "home_sp": "burnes",
        "away_pb": "petersen_pb",
        "home_pb": "holmes_pb",
        "away_bp_pitches_3d": 65,
        "home_bp_pitches_3d": 65,
        "neutral_site": False,  # USA home
        "odds_params": {
            "ml_away": 6.50, "ml_home": 1.12,
            "rl_spread": 3.5, "rl_fav": "USA", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 5.50, "f5_home": 1.15,
            "tt_away_line": 2.5, "tt_home_line": 5.5,
        },
    },
    # ─── Day 3: March 9 (TW) / March 8 (Local — DST starts) ─────
    {
        "game_id": "B05",
        "date": "2026-03-09",
        "game_time": "2026-03-08T12:00:00-05:00",
        "tw_time": "03/09 01:00",
        "away_code": "GBR",
        "home_code": "ITA",
        "away_sp": "fernander",
        "home_sp": "biagini",
        "away_pb": "petersen_pb",
        "home_pb": "romano_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 65,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.50, "ml_home": 1.58,
            "rl_spread": 1.5, "rl_fav": "ITA", "rl_fav_odds": 2.00, "rl_dog_odds": 1.80,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.40, "f5_home": 1.62,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
    {
        "game_id": "B06",
        "date": "2026-03-09",
        "game_time": "2026-03-08T19:00:00-05:00",
        "tw_time": "03/09 08:00",
        "away_code": "BRA",
        "home_code": "MEX",
        "away_sp": "misaki",
        "home_sp": "bradley",
        "away_pb": "vieira_pb",
        "home_pb": "munoz_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 65,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 5.50, "ml_home": 1.18,
            "rl_spread": 3.5, "rl_fav": "MEX", "rl_fav_odds": 1.90, "rl_dog_odds": 1.90,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 4.80, "f5_home": 1.20,
            "tt_away_line": 2.5, "tt_home_line": 5.5,
        },
    },
    # ─── Day 4: March 10 (TW) / March 9 (Local CDT) ─────
    {
        "game_id": "B07",
        "date": "2026-03-10",
        "game_time": "2026-03-09T12:00:00-05:00",
        "tw_time": "03/10 01:00",
        "away_code": "BRA",
        "home_code": "GBR",
        "away_sp": "pardinho",
        "home_sp": "worley",
        "away_pb": "vieira_pb",
        "home_pb": "petersen_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.20, "ml_home": 1.72,
            "rl_spread": 1.5, "rl_fav": "GBR", "rl_fav_odds": 2.15, "rl_dog_odds": 1.72,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.15, "f5_home": 1.75,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
    {
        "game_id": "B08",
        "date": "2026-03-10",
        "game_time": "2026-03-09T19:00:00-05:00",
        "tw_time": "03/10 08:00",
        "away_code": "MEX",
        "home_code": "USA",
        "away_sp": "walker",
        "home_sp": "webb",
        "away_pb": "munoz_pb",
        "home_pb": "miller_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": False,  # USA home
        "odds_params": {
            "ml_away": 2.60, "ml_home": 1.55,
            "rl_spread": 1.5, "rl_fav": "USA", "rl_fav_odds": 1.95, "rl_dog_odds": 1.85,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.50, "f5_home": 1.58,
            "tt_away_line": 3.5, "tt_home_line": 4.5,
        },
    },
    # ─── Day 5: March 11 (TW) / March 10 (Local CDT) ────
    {
        "game_id": "B09",
        "date": "2026-03-11",
        "game_time": "2026-03-10T20:00:00-05:00",
        "tw_time": "03/11 09:00",
        "away_code": "ITA",
        "home_code": "USA",
        "away_sp": "aldegheri",
        "home_sp": "skubal",
        "away_pb": "romano_pb",
        "home_pb": "holmes_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": False,  # USA home
        "odds_params": {
            "ml_away": 4.20, "ml_home": 1.25,
            "rl_spread": 2.5, "rl_fav": "USA", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 3.60, "f5_home": 1.30,
            "tt_away_line": 2.5, "tt_home_line": 4.5,
        },
    },
    # ─── Day 6: March 12 (TW) / March 11 (Local CDT) ────
    {
        "game_id": "B10",
        "date": "2026-03-12",
        "game_time": "2026-03-11T18:00:00-05:00",
        "tw_time": "03/12 07:00",
        "away_code": "ITA",
        "home_code": "MEX",
        "away_sp": "pallante",
        "home_sp": "assad",
        "away_pb": "romano_pb",
        "home_pb": "munoz_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.30, "ml_home": 1.65,
            "rl_spread": 1.5, "rl_fav": "MEX", "rl_fav_odds": 2.10, "rl_dog_odds": 1.75,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.25, "f5_home": 1.68,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def list_wbc_matches_b() -> List[dict]:
    return [
        {"game_id": g["game_id"], "date": g["date"], "tw_time": g["tw_time"],
         "away": g["away_code"], "home": g["home_code"], "game_time": g["game_time"]}
        for g in _POOL_B_SCHEDULE
    ]


def fetch_wbc_match_b(game_id: str, live: bool = False,
                      use_mock: bool = False) -> MatchData:
    game = None
    for g in _POOL_B_SCHEDULE:
        if g["game_id"] == game_id.upper():
            game = g
            break
    if game is None:
        available = [g["game_id"] for g in _POOL_B_SCHEDULE]
        raise ValueError(f"Unknown game_id '{game_id}'. Available: {available}")

    away_code, home_code = game["away_code"], game["home_code"]
    away_team, away_pitchers = _TEAM_FACTORIES_B[away_code]()
    home_team, home_pitchers = _TEAM_FACTORIES_B[home_code]()
    away_team.bullpen_pitches_3d = game["away_bp_pitches_3d"]
    home_team.bullpen_pitches_3d = game["home_bp_pitches_3d"]

    pc_rule = PitchCountRule(round_name="Pool B", max_pitches=65,
                             rest_after_30=1, rest_after_50=4,
                             expected_sp_innings=3.5)

    ts = game["game_time"]
    p = game["odds_params"]
    odds = _std_odds(away_code, home_code, ts, **p)

    away_sp = away_pitchers[game["away_sp"]]
    home_sp = home_pitchers[game["home_sp"]]
    away_pb = away_pitchers.get(game.get("away_pb"))
    home_pb = home_pitchers.get(game.get("home_pb"))

    stuff = {"USA": 125, "MEX": 112, "ITA": 100, "GBR": 80, "BRA": 82}

    return MatchData(
        home=home_team, away=away_team,
        home_sp=home_sp, away_sp=away_sp,
        home_piggyback=home_pb, away_piggyback=away_pb,
        home_bullpen=_build_bullpen(home_code, home_team.bullpen_era,
                                    game["home_bp_pitches_3d"],
                                    avg_stuff=stuff.get(home_code, 90)),
        away_bullpen=_build_bullpen(away_code, away_team.bullpen_era,
                                    game["away_bp_pitches_3d"],
                                    avg_stuff=stuff.get(away_code, 90)),
        home_lineup=_build_lineup(home_code, home_team.batting_avg,
                                  home_team.team_obp, home_team.team_slg,
                                  woba=home_team.team_woba,
                                  wrc_plus=home_team.lineup_wrc_plus),
        away_lineup=_build_lineup(away_code, away_team.batting_avg,
                                  away_team.team_obp, away_team.team_slg,
                                  woba=away_team.team_woba,
                                  wrc_plus=away_team.lineup_wrc_plus),
        odds=odds, pitch_count_rule=pc_rule,
        game_time=game["game_time"],
        venue="Minute Maid Park, Houston",
        round_name="Pool B",
        neutral_site=game["neutral_site"],
    )
