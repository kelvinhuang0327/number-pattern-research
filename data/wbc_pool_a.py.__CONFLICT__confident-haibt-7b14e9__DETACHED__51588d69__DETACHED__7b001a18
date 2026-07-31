"""
WBC 2026 Pool A — 10-game schedule (San Juan, Puerto Rico).

Teams: PUR, CUB, PAN, COL, CAN
Venue: Estadio Hiram Bithorn, San Juan
Round: Pool A (pitch-count limit: 65 pitches)

Usage:
    from data.wbc_pool_a import fetch_wbc_match_a, list_wbc_matches_a
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


# ═══════════════════════════════════════════════════════════════════════════════
# ODDS HELPER (shared pattern)
# ═══════════════════════════════════════════════════════════════════════════════

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
# TEAM DEFINITIONS — POOL A
# ═══════════════════════════════════════════════════════════════════════════════

def _team_pur() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Puerto Rico — Host, strong MLB core. Elo 1500."""
    roster = RosterVolatility(
        roster_strength_index=88,
        confirmed_stars=["Francisco Lindor", "Carlos Correa", "Edwin Díaz",
                         "Marcus Stroman", "Seth Lugo"],
        uncertain_stars=["Nolan Arenado"],
        absent_stars=[],
        team_chemistry=0.85,
        mlb_player_count=14,
    )
    team = TeamStats(
        name="Puerto Rico", code="PUR", elo=1500,
        runs_per_game=5.2, runs_allowed_per_game=3.5,
        batting_avg=0.272, team_obp=0.345, team_slg=0.435,
        team_woba=0.345, bullpen_era=3.10,
        bullpen_pitches_3d=0,
        defense_efficiency=0.718, sb_success_rate=0.76,
        lineup_wrc_plus=122, clutch_woba=0.340,
        roster_vol=roster,
    )
    pitchers = {
        "stroman": PitcherStats(
            name="Marcus Stroman", team="PUR",
            era=3.55, fip=3.70, whip=1.22, k_per_9=7.8, bb_per_9=2.5,
            stuff_plus=108, ip_last_30=24.0, era_last_3=3.30,
            spring_era=3.20, pitch_count_last_3d=0,
            vs_left_ba=0.245, vs_right_ba=0.235,
            high_leverage_era=3.60, fastball_velo=93.0, role="SP",
        ),
        "lugo": PitcherStats(
            name="Seth Lugo", team="PUR",
            era=3.00, fip=3.20, whip=1.10, k_per_9=8.5, bb_per_9=2.0,
            stuff_plus=112, ip_last_30=26.0, era_last_3=2.80,
            spring_era=2.90, pitch_count_last_3d=0,
            vs_left_ba=0.235, vs_right_ba=0.220,
            high_leverage_era=3.20, fastball_velo=94.5, role="SP",
        ),
        "de_leon": PitcherStats(
            name="Jose De León", team="PUR",
            era=3.80, fip=3.90, whip=1.28, k_per_9=9.0, bb_per_9=3.2,
            stuff_plus=105, ip_last_30=20.0, era_last_3=3.50,
            spring_era=3.40, pitch_count_last_3d=0,
            vs_left_ba=0.250, vs_right_ba=0.240,
            high_leverage_era=4.00, fastball_velo=95.0, role="SP",
        ),
        "lopez_pb": PitcherStats(
            name="Jorge López", team="PUR",
            era=3.60, fip=3.50, whip=1.20, k_per_9=8.8, bb_per_9=3.0,
            stuff_plus=110, ip_last_30=12.0, era_last_3=3.30,
            spring_era=3.20, pitch_count_last_3d=0,
            vs_left_ba=0.240, vs_right_ba=0.228,
            high_leverage_era=3.50, fastball_velo=97.0, role="PB",
        ),
        "diaz_pb": PitcherStats(
            name="Edwin Díaz", team="PUR",
            era=2.80, fip=2.60, whip=0.92, k_per_9=13.5, bb_per_9=3.0,
            stuff_plus=135, ip_last_30=8.0, era_last_3=2.20,
            spring_era=2.00, pitch_count_last_3d=0,
            vs_left_ba=0.180, vs_right_ba=0.170,
            high_leverage_era=2.50, fastball_velo=99.5, role="PB",
        ),
    }
    return team, pitchers


def _team_cub() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Cuba — Traditional powerhouse, mostly domestic league. Elo 1400."""
    roster = RosterVolatility(
        roster_strength_index=72,
        confirmed_stars=["Yoán Moncada", "Luis Robert", "Raidel Martinez"],
        uncertain_stars=["Livan Moinelo"],
        absent_stars=[],
        team_chemistry=0.80,
        mlb_player_count=3,
    )
    team = TeamStats(
        name="Cuba", code="CUB", elo=1400,
        runs_per_game=4.5, runs_allowed_per_game=4.0,
        batting_avg=0.265, team_obp=0.325, team_slg=0.400,
        team_woba=0.318, bullpen_era=3.80,
        bullpen_pitches_3d=0,
        defense_efficiency=0.705, sb_success_rate=0.74,
        lineup_wrc_plus=105, clutch_woba=0.310,
        roster_vol=roster,
    )
    pitchers = {
        "martinez_r": PitcherStats(
            name="Raidel Martinez", team="CUB",
            era=3.20, fip=3.40, whip=1.15, k_per_9=9.5, bb_per_9=2.5,
            stuff_plus=115, ip_last_30=20.0, era_last_3=2.90,
            spring_era=3.00, pitch_count_last_3d=0,
            vs_left_ba=0.228, vs_right_ba=0.215,
            high_leverage_era=3.30, fastball_velo=96.0, role="SP",
        ),
        "moinelo": PitcherStats(
            name="Livan Moinelo", team="CUB",
            era=2.50, fip=2.80, whip=1.05, k_per_9=10.0, bb_per_9=2.8,
            stuff_plus=118, ip_last_30=14.0, era_last_3=2.20,
            spring_era=2.40, pitch_count_last_3d=0,
            vs_left_ba=0.200, vs_right_ba=0.210,
            high_leverage_era=2.60, fastball_velo=93.5, role="SP",
        ),
        "rodriguez_y": PitcherStats(
            name="Yariel Rodríguez", team="CUB",
            era=4.20, fip=4.10, whip=1.32, k_per_9=8.2, bb_per_9=3.5,
            stuff_plus=102, ip_last_30=18.0, era_last_3=4.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.255, vs_right_ba=0.248,
            high_leverage_era=4.50, fastball_velo=95.0, role="SP",
        ),
        "lopez_y_pb": PitcherStats(
            name="Yoan López", team="CUB",
            era=4.50, fip=4.30, whip=1.35, k_per_9=7.8, bb_per_9=3.2,
            stuff_plus=98, ip_last_30=10.0, era_last_3=4.20,
            spring_era=4.00, pitch_count_last_3d=0,
            vs_left_ba=0.260, vs_right_ba=0.250,
            high_leverage_era=4.80, fastball_velo=94.0, role="PB",
        ),
    }
    return team, pitchers


def _team_pan() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Panama — Elo 1320. Solid infield defense, limited pitching depth."""
    roster = RosterVolatility(
        roster_strength_index=60,
        confirmed_stars=["Javy Guerra", "Christian Bethancourt"],
        uncertain_stars=["Edmundo Sosa"],
        absent_stars=[],
        team_chemistry=0.78,
        mlb_player_count=3,
    )
    team = TeamStats(
        name="Panama", code="PAN", elo=1320,
        runs_per_game=3.8, runs_allowed_per_game=4.5,
        batting_avg=0.250, team_obp=0.310, team_slg=0.370,
        team_woba=0.298, bullpen_era=4.50,
        bullpen_pitches_3d=0,
        defense_efficiency=0.698, sb_success_rate=0.70,
        lineup_wrc_plus=85, clutch_woba=0.288,
        roster_vol=roster,
    )
    pitchers = {
        "guerra": PitcherStats(
            name="Javy Guerra", team="PAN",
            era=3.90, fip=4.10, whip=1.30, k_per_9=8.0, bb_per_9=3.0,
            stuff_plus=100, ip_last_30=16.0, era_last_3=3.60,
            spring_era=3.50, pitch_count_last_3d=0,
            vs_left_ba=0.252, vs_right_ba=0.245,
            high_leverage_era=4.20, fastball_velo=93.5, role="SP",
        ),
        "jurado": PitcherStats(
            name="Ariel Jurado", team="PAN",
            era=4.40, fip=4.50, whip=1.38, k_per_9=6.5, bb_per_9=2.8,
            stuff_plus=90, ip_last_30=14.0, era_last_3=4.20,
            spring_era=4.00, pitch_count_last_3d=0,
            vs_left_ba=0.265, vs_right_ba=0.258,
            high_leverage_era=4.80, fastball_velo=91.0, role="SP",
        ),
        "barria": PitcherStats(
            name="Jaime Barria", team="PAN",
            era=4.60, fip=4.70, whip=1.40, k_per_9=6.8, bb_per_9=3.0,
            stuff_plus=88, ip_last_30=12.0, era_last_3=4.40,
            spring_era=4.20, pitch_count_last_3d=0,
            vs_left_ba=0.268, vs_right_ba=0.260,
            high_leverage_era=5.00, fastball_velo=90.5, role="SP",
        ),
        "espino_pb": PitcherStats(
            name="Paolo Espino", team="PAN",
            era=4.80, fip=4.90, whip=1.42, k_per_9=6.2, bb_per_9=2.5,
            stuff_plus=85, ip_last_30=10.0, era_last_3=4.60,
            spring_era=4.30, pitch_count_last_3d=0,
            vs_left_ba=0.270, vs_right_ba=0.265,
            high_leverage_era=5.20, fastball_velo=89.0, role="PB",
        ),
        "allen_l": PitcherStats(
            name="Logan Allen", team="PAN",
            era=4.45, fip=4.30, whip=1.40, k_per_9=8.5, bb_per_9=3.2,
            stuff_plus=98, ip_last_30=20.0, era_last_3=4.20,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.255, vs_right_ba=0.262,
            high_leverage_era=4.50, fastball_velo=92.5, role="SP",
        ),
    }
    return team, pitchers


def _team_col() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Colombia — Elo 1280. Emerging talent but thin roster."""
    roster = RosterVolatility(
        roster_strength_index=58,
        confirmed_stars=["Jose Quintana", "Gio Urshela"],
        uncertain_stars=["Julio Teheran"],
        absent_stars=[],
        team_chemistry=0.75,
        mlb_player_count=3,
    )
    team = TeamStats(
        name="Colombia", code="COL", elo=1280,
        runs_per_game=3.5, runs_allowed_per_game=4.8,
        batting_avg=0.242, team_obp=0.305, team_slg=0.360,
        team_woba=0.290, bullpen_era=4.80,
        bullpen_pitches_3d=0,
        defense_efficiency=0.690, sb_success_rate=0.68,
        lineup_wrc_plus=80, clutch_woba=0.280,
        roster_vol=roster,
    )
    pitchers = {
        "quintana": PitcherStats(
            name="Jose Quintana", team="COL",
            era=3.75, fip=3.90, whip=1.25, k_per_9=7.5, bb_per_9=2.8,
            stuff_plus=100, ip_last_30=20.0, era_last_3=3.50,
            spring_era=3.40, pitch_count_last_3d=0,
            vs_left_ba=0.240, vs_right_ba=0.248,
            high_leverage_era=3.90, fastball_velo=91.5, role="SP",
        ),
        "teheran": PitcherStats(
            name="Julio Teheran", team="COL",
            era=4.50, fip=4.60, whip=1.35, k_per_9=6.8, bb_per_9=3.0,
            stuff_plus=92, ip_last_30=14.0, era_last_3=4.30,
            spring_era=4.10, pitch_count_last_3d=0,
            vs_left_ba=0.260, vs_right_ba=0.255,
            high_leverage_era=4.80, fastball_velo=90.0, role="SP",
        ),
        "crismatt": PitcherStats(
            name="Nabil Crismatt", team="COL",
            era=3.90, fip=4.00, whip=1.28, k_per_9=7.2, bb_per_9=2.5,
            stuff_plus=95, ip_last_30=16.0, era_last_3=3.70,
            spring_era=3.60, pitch_count_last_3d=0,
            vs_left_ba=0.250, vs_right_ba=0.242,
            high_leverage_era=4.10, fastball_velo=91.0, role="SP",
        ),
        "patino_pb": PitcherStats(
            name="Luis Patiño", team="COL",
            era=4.20, fip=4.10, whip=1.30, k_per_9=9.0, bb_per_9=3.5,
            stuff_plus=108, ip_last_30=10.0, era_last_3=4.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.245, vs_right_ba=0.238,
            high_leverage_era=4.40, fastball_velo=96.0, role="PB",
        ),
    }
    return team, pitchers


def _team_can() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Canada — Elo 1420. Strong MLB hitters, decent rotation."""
    roster = RosterVolatility(
        roster_strength_index=80,
        confirmed_stars=["Freddie Freeman", "Tyler O'Neill", "Cal Quantrill",
                         "James Paxton"],
        uncertain_stars=["Joey Votto"],
        absent_stars=[],
        team_chemistry=0.82,
        mlb_player_count=10,
    )
    team = TeamStats(
        name="Canada", code="CAN", elo=1420,
        runs_per_game=4.8, runs_allowed_per_game=3.8,
        batting_avg=0.268, team_obp=0.340, team_slg=0.420,
        team_woba=0.335, bullpen_era=3.60,
        bullpen_pitches_3d=0,
        defense_efficiency=0.710, sb_success_rate=0.72,
        lineup_wrc_plus=115, clutch_woba=0.325,
        roster_vol=roster,
    )
    pitchers = {
        "quantrill": PitcherStats(
            name="Cal Quantrill", team="CAN",
            era=3.40, fip=3.60, whip=1.18, k_per_9=7.5, bb_per_9=2.2,
            stuff_plus=105, ip_last_30=24.0, era_last_3=3.20,
            spring_era=3.10, pitch_count_last_3d=0,
            vs_left_ba=0.240, vs_right_ba=0.232,
            high_leverage_era=3.50, fastball_velo=93.5, role="SP",
        ),
        "paxton": PitcherStats(
            name="James Paxton", team="CAN",
            era=3.80, fip=3.70, whip=1.22, k_per_9=9.0, bb_per_9=2.8,
            stuff_plus=110, ip_last_30=18.0, era_last_3=3.50,
            spring_era=3.40, pitch_count_last_3d=0,
            vs_left_ba=0.230, vs_right_ba=0.238,
            high_leverage_era=3.90, fastball_velo=95.0, role="SP",
        ),
        "soroka": PitcherStats(
            name="Michael Soroka", team="CAN",
            era=4.10, fip=4.20, whip=1.28, k_per_9=7.0, bb_per_9=2.5,
            stuff_plus=98, ip_last_30=16.0, era_last_3=3.90,
            spring_era=3.70, pitch_count_last_3d=0,
            vs_left_ba=0.248, vs_right_ba=0.242,
            high_leverage_era=4.30, fastball_velo=92.5, role="SP",
        ),
        "taillon_pb": PitcherStats(
            name="Jameson Taillon", team="CAN",
            era=4.00, fip=4.10, whip=1.25, k_per_9=7.2, bb_per_9=2.3,
            stuff_plus=100, ip_last_30=14.0, era_last_3=3.80,
            spring_era=3.60, pitch_count_last_3d=0,
            vs_left_ba=0.245, vs_right_ba=0.238,
            high_leverage_era=4.20, fastball_velo=93.0, role="PB",
        ),
    }
    return team, pitchers


_TEAM_FACTORIES_A = {
    "PUR": _team_pur,
    "CUB": _team_cub,
    "PAN": _team_pan,
    "COL": _team_col,
    "CAN": _team_can,
}

# ═══════════════════════════════════════════════════════════════════════════════
# POOL A GAME SCHEDULE (10 games)
# Venue: Estadio Hiram Bithorn, San Juan, Puerto Rico (AST = UTC-4)
# ═══════════════════════════════════════════════════════════════════════════════

_POOL_A_SCHEDULE = [
    # ─── Day 1: March 7 (TW) / March 6 (Local) ──────────
    {
        "game_id": "A01",
        "date": "2026-03-07",
        "game_time": "2026-03-06T12:00:00-04:00",
        "tw_time": "03/07 00:00",
        "away_code": "CUB",
        "home_code": "PAN",
        "away_sp": "martinez_r",
        "home_sp": "allen_l",
        "away_pb": "lopez_y_pb",
        "home_pb": "espino_pb",
        "away_bp_pitches_3d": 0,
        "home_bp_pitches_3d": 0,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.58, "ml_home": 2.45,
            "rl_spread": 1.5, "rl_fav": "CUB", "rl_fav_odds": 2.05, "rl_dog_odds": 1.82,
            "ou_line": 8.5, "ou_over": 1.95, "ou_under": 1.88,
            "f5_away": 1.62, "f5_home": 2.35,
            "tt_away_line": 4.5, "tt_home_line": 3.5,
        },
    },
    {
        "game_id": "A02",
        "date": "2026-03-07",
        "game_time": "2026-03-06T19:00:00-04:00",
        "tw_time": "03/07 07:00",
        "away_code": "PUR",
        "home_code": "COL",
        "away_sp": "stroman",
        "home_sp": "quintana",
        "away_pb": "lopez_pb",
        "home_pb": "patino_pb",
        "away_bp_pitches_3d": 0,
        "home_bp_pitches_3d": 0,
        "neutral_site": False,  # PUR home
        "odds_params": {
            "ml_away": 1.35, "ml_home": 3.40,
            "rl_spread": 2.5, "rl_fav": "PUR", "rl_fav_odds": 1.90, "rl_dog_odds": 1.90,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 1.40, "f5_home": 3.10,
            "tt_away_line": 4.5, "tt_home_line": 2.5,
        },
    },
    # ─── Day 2: March 8 (TW) / March 7 (Local) ──────────
    {
        "game_id": "A03",
        "date": "2026-03-08",
        "game_time": "2026-03-07T12:00:00-04:00",
        "tw_time": "03/08 00:00",
        "away_code": "COL",
        "home_code": "CAN",
        "away_sp": "teheran",
        "home_sp": "quantrill",
        "away_pb": "patino_pb",
        "home_pb": "taillon_pb",
        "away_bp_pitches_3d": 65,
        "home_bp_pitches_3d": 0,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.90, "ml_home": 1.45,
            "rl_spread": 1.5, "rl_fav": "CAN", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.70, "f5_home": 1.50,
            "tt_away_line": 2.5, "tt_home_line": 4.5,
        },
    },
    {
        "game_id": "A04",
        "date": "2026-03-08",
        "game_time": "2026-03-07T19:00:00-04:00",
        "tw_time": "03/08 07:00",
        "away_code": "PAN",
        "home_code": "PUR",
        "away_sp": "jurado",
        "home_sp": "lugo",
        "away_pb": "espino_pb",
        "home_pb": "diaz_pb",
        "away_bp_pitches_3d": 65,
        "home_bp_pitches_3d": 65,
        "neutral_site": False,  # PUR home
        "odds_params": {
            "ml_away": 3.80, "ml_home": 1.28,
            "rl_spread": 2.5, "rl_fav": "PUR", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 7.5, "ou_over": 1.90, "ou_under": 1.90,
            "f5_away": 3.30, "f5_home": 1.35,
            "tt_away_line": 2.5, "tt_home_line": 4.5,
        },
    },
    # ─── Day 3: March 9 (TW) / March 8 (Local) ──────────
    {
        "game_id": "A05",
        "date": "2026-03-09",
        "game_time": "2026-03-08T12:00:00-04:00",
        "tw_time": "03/09 00:00",
        "away_code": "COL",
        "home_code": "CUB",
        "away_sp": "crismatt",
        "home_sp": "moinelo",
        "away_pb": "patino_pb",
        "home_pb": "lopez_y_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 65,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.60, "ml_home": 1.55,
            "rl_spread": 1.5, "rl_fav": "CUB", "rl_fav_odds": 2.00, "rl_dog_odds": 1.80,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.45, "f5_home": 1.60,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
    {
        "game_id": "A06",
        "date": "2026-03-09",
        "game_time": "2026-03-08T19:00:00-04:00",
        "tw_time": "03/09 07:00",
        "away_code": "PAN",
        "home_code": "CAN",
        "away_sp": "barria",
        "home_sp": "paxton",
        "away_pb": "espino_pb",
        "home_pb": "taillon_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 65,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.80, "ml_home": 1.48,
            "rl_spread": 1.5, "rl_fav": "CAN", "rl_fav_odds": 1.90, "rl_dog_odds": 1.90,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.65, "f5_home": 1.52,
            "tt_away_line": 2.5, "tt_home_line": 4.5,
        },
    },
    # ─── Day 4: March 10 (TW) / March 9 (Local) ─────────
    {
        "game_id": "A07",
        "date": "2026-03-10",
        "game_time": "2026-03-09T12:00:00-04:00",
        "tw_time": "03/10 00:00",
        "away_code": "COL",
        "home_code": "PAN",
        "away_sp": "quintana",
        "home_sp": "guerra",
        "away_pb": "patino_pb",
        "home_pb": "espino_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.10, "ml_home": 1.78,
            "rl_spread": 1.5, "rl_fav": "COL", "rl_fav_odds": 2.20, "rl_dog_odds": 1.68,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.05, "f5_home": 1.80,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
    {
        "game_id": "A08",
        "date": "2026-03-10",
        "game_time": "2026-03-09T19:00:00-04:00",
        "tw_time": "03/10 07:00",
        "away_code": "CUB",
        "home_code": "PUR",
        "away_sp": "rodriguez_y",
        "home_sp": "de_leon",
        "away_pb": "lopez_y_pb",
        "home_pb": "diaz_pb",
        "away_bp_pitches_3d": 65,
        "home_bp_pitches_3d": 130,
        "neutral_site": False,  # PUR home
        "odds_params": {
            "ml_away": 2.30, "ml_home": 1.65,
            "rl_spread": 1.5, "rl_fav": "PUR", "rl_fav_odds": 2.10, "rl_dog_odds": 1.75,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.25, "f5_home": 1.68,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
    # ─── Day 5: March 11 (TW) / March 10 (Local) ────────
    {
        "game_id": "A09",
        "date": "2026-03-11",
        "game_time": "2026-03-10T19:00:00-04:00",
        "tw_time": "03/11 07:00",
        "away_code": "CAN",
        "home_code": "PUR",
        "away_sp": "soroka",
        "home_sp": "stroman",
        "away_pb": "taillon_pb",
        "home_pb": "lopez_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": False,  # PUR home
        "odds_params": {
            "ml_away": 2.15, "ml_home": 1.75,
            "rl_spread": 1.5, "rl_fav": "PUR", "rl_fav_odds": 2.15, "rl_dog_odds": 1.72,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.10, "f5_home": 1.78,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
    # ─── Day 6: March 12 (TW) / March 11 (Local) ────────
    {
        "game_id": "A10",
        "date": "2026-03-12",
        "game_time": "2026-03-11T15:00:00-04:00",
        "tw_time": "03/12 03:00",
        "away_code": "CAN",
        "home_code": "CUB",
        "away_sp": "quantrill",
        "home_sp": "martinez_r",
        "away_pb": "taillon_pb",
        "home_pb": "lopez_y_pb",
        "away_bp_pitches_3d": 65,
        "home_bp_pitches_3d": 130,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.72, "ml_home": 2.20,
            "rl_spread": 1.5, "rl_fav": "CAN", "rl_fav_odds": 2.10, "rl_dog_odds": 1.75,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 1.75, "f5_home": 2.15,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def list_wbc_matches_a() -> List[dict]:
    return [
        {"game_id": g["game_id"], "date": g["date"], "tw_time": g["tw_time"],
         "away": g["away_code"], "home": g["home_code"], "game_time": g["game_time"]}
        for g in _POOL_A_SCHEDULE
    ]


def fetch_wbc_match_a(game_id: str, live: bool = False,
                      use_mock: bool = False) -> MatchData:
    game = None
    for g in _POOL_A_SCHEDULE:
        if g["game_id"] == game_id.upper():
            game = g
            break
    if game is None:
        available = [g["game_id"] for g in _POOL_A_SCHEDULE]
        raise ValueError(f"Unknown game_id '{game_id}'. Available: {available}")

    away_code, home_code = game["away_code"], game["home_code"]
    away_team, away_pitchers = _TEAM_FACTORIES_A[away_code]()
    home_team, home_pitchers = _TEAM_FACTORIES_A[home_code]()
    away_team.bullpen_pitches_3d = game["away_bp_pitches_3d"]
    home_team.bullpen_pitches_3d = game["home_bp_pitches_3d"]

    pc_rule = PitchCountRule(round_name="Pool A", max_pitches=65,
                             rest_after_30=1, rest_after_50=4,
                             expected_sp_innings=3.5)

    ts = game["game_time"]
    p = game["odds_params"]
    odds = _std_odds(away_code, home_code, ts, **p)

    away_sp = away_pitchers[game["away_sp"]]
    home_sp = home_pitchers[game["home_sp"]]
    away_pb = away_pitchers.get(game.get("away_pb"))
    home_pb = home_pitchers.get(game.get("home_pb"))

    stuff = {"PUR": 115, "CAN": 100, "CUB": 105, "PAN": 85, "COL": 88}

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
        venue="Estadio Hiram Bithorn, San Juan",
        round_name="Pool A",
        neutral_site=game["neutral_site"],
    )
