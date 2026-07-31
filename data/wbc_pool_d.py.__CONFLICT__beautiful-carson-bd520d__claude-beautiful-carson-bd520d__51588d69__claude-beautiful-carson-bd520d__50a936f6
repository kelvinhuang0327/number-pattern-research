"""
WBC 2026 Pool D — 10-game schedule (Miami, Florida).

Teams: DOM, VEN, NED, ISR, NIC
Venue: LoanDepot Park, Miami
Round: Pool D (pitch-count limit: 65 pitches)

Usage:
    from data.wbc_pool_d import fetch_wbc_match_d, list_wbc_matches_d
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
# TEAM DEFINITIONS — POOL D
# ═══════════════════════════════════════════════════════════════════════════════

def _team_dom() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Dominican Republic — MLB superstar lineup, perennial contender. Elo 1560."""
    roster = RosterVolatility(
        roster_strength_index=94,
        confirmed_stars=["Juan Soto", "Vladimir Guerrero Jr.", "Rafael Devers",
                         "Manny Machado", "Fernando Tatis Jr.", "Framber Valdez"],
        uncertain_stars=["Sandy Alcantara"],
        absent_stars=[],
        team_chemistry=0.88,
        mlb_player_count=26,
    )
    team = TeamStats(
        name="Dominican Republic", code="DOM", elo=1560,
        runs_per_game=5.3, runs_allowed_per_game=3.2,
        batting_avg=0.275, team_obp=0.350, team_slg=0.455,
        team_woba=0.355, bullpen_era=2.80,
        bullpen_pitches_3d=0,
        defense_efficiency=0.718, sb_success_rate=0.80,
        lineup_wrc_plus=132, clutch_woba=0.350,
        roster_vol=roster,
    )
    pitchers = {
        "valdez": PitcherStats(
            name="Framber Valdez", team="DOM",
            era=3.00, fip=3.20, whip=1.10, k_per_9=8.5, bb_per_9=2.5,
            stuff_plus=115, ip_last_30=26.0, era_last_3=2.80,
            spring_era=2.60, pitch_count_last_3d=0,
            vs_left_ba=0.215, vs_right_ba=0.220,
            high_leverage_era=2.90, fastball_velo=94.5, role="SP",
        ),
        "soriano": PitcherStats(
            name="Gregory Soto", team="DOM",
            era=3.60, fip=3.50, whip=1.20, k_per_9=9.0, bb_per_9=3.5,
            stuff_plus=118, ip_last_30=8.0, era_last_3=3.30,
            spring_era=3.20, pitch_count_last_3d=0,
            vs_left_ba=0.210, vs_right_ba=0.220,
            high_leverage_era=3.40, fastball_velo=99.0, role="SP",
        ),
        "peralta": PitcherStats(
            name="Wandy Peralta", team="DOM",
            era=3.20, fip=3.40, whip=1.15, k_per_9=9.5, bb_per_9=3.0,
            stuff_plus=112, ip_last_30=10.0, era_last_3=3.00,
            spring_era=2.90, pitch_count_last_3d=0,
            vs_left_ba=0.200, vs_right_ba=0.225,
            high_leverage_era=3.10, fastball_velo=97.5, role="SP",
        ),
        "clase_pb": PitcherStats(
            name="Emmanuel Clase", team="DOM",
            era=2.00, fip=2.10, whip=0.82, k_per_9=10.5, bb_per_9=1.5,
            stuff_plus=135, ip_last_30=8.0, era_last_3=1.70,
            spring_era=1.60, pitch_count_last_3d=0,
            vs_left_ba=0.170, vs_right_ba=0.160,
            high_leverage_era=1.80, fastball_velo=100.5, role="PB",
        ),
        "diaz_pb": PitcherStats(
            name="Jhoan Duran", team="DOM",
            era=2.50, fip=2.40, whip=0.95, k_per_9=12.0, bb_per_9=3.0,
            stuff_plus=132, ip_last_30=8.0, era_last_3=2.20,
            spring_era=2.10, pitch_count_last_3d=0,
            vs_left_ba=0.175, vs_right_ba=0.170,
            high_leverage_era=2.30, fastball_velo=101.0, role="PB",
        ),
    }
    return team, pitchers


def _team_ven() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Venezuela — Elite talent pool (Acuña, Altuve, Arraez). Elo 1540."""
    roster = RosterVolatility(
        roster_strength_index=92,
        confirmed_stars=["Ronald Acuña Jr.", "José Altuve", "Luis Arraez",
                         "Andrés Giménez", "José Ramírez", "Miguel Cabrera"],
        uncertain_stars=["Luis Castillo"],
        absent_stars=[],
        team_chemistry=0.86,
        mlb_player_count=24,
    )
    team = TeamStats(
        name="Venezuela", code="VEN", elo=1540,
        runs_per_game=5.2, runs_allowed_per_game=3.4,
        batting_avg=0.273, team_obp=0.347, team_slg=0.450,
        team_woba=0.352, bullpen_era=3.00,
        bullpen_pitches_3d=0,
        defense_efficiency=0.715, sb_success_rate=0.78,
        lineup_wrc_plus=128, clutch_woba=0.345,
        roster_vol=roster,
    )
    pitchers = {
        "castillo": PitcherStats(
            name="Luis Castillo", team="VEN",
            era=3.10, fip=3.30, whip=1.10, k_per_9=9.0, bb_per_9=2.5,
            stuff_plus=120, ip_last_30=24.0, era_last_3=2.90,
            spring_era=2.80, pitch_count_last_3d=0,
            vs_left_ba=0.220, vs_right_ba=0.215,
            high_leverage_era=3.00, fastball_velo=97.0, role="SP",
        ),
        "suarez_r": PitcherStats(
            name="Ranger Suárez", team="VEN",
            era=3.30, fip=3.50, whip=1.15, k_per_9=7.5, bb_per_9=2.2,
            stuff_plus=108, ip_last_30=22.0, era_last_3=3.10,
            spring_era=3.00, pitch_count_last_3d=0,
            vs_left_ba=0.210, vs_right_ba=0.230,
            high_leverage_era=3.20, fastball_velo=93.0, role="SP",
        ),
        "carrasco": PitcherStats(
            name="Carlos Carrasco", team="VEN",
            era=4.20, fip=4.30, whip=1.28, k_per_9=7.5, bb_per_9=2.5,
            stuff_plus=95, ip_last_30=18.0, era_last_3=4.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.248, vs_right_ba=0.240,
            high_leverage_era=4.40, fastball_velo=92.0, role="SP",
        ),
        "pressly_pb": PitcherStats(
            name="Ryan Pressly", team="VEN",
            era=2.80, fip=2.70, whip=0.98, k_per_9=10.0, bb_per_9=2.5,
            stuff_plus=120, ip_last_30=8.0, era_last_3=2.50,
            spring_era=2.40, pitch_count_last_3d=0,
            vs_left_ba=0.190, vs_right_ba=0.185,
            high_leverage_era=2.60, fastball_velo=96.5, role="PB",
        ),
    }
    return team, pitchers


def _team_ned() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Netherlands — Solid Curaçao/Aruba pipeline. Elo 1400."""
    roster = RosterVolatility(
        roster_strength_index=72,
        confirmed_stars=["Xander Bogaerts", "Ozzie Albies", "Didi Gregorius",
                         "Kenley Jansen", "Jonathan Schoop"],
        uncertain_stars=[],
        absent_stars=[],
        team_chemistry=0.80,
        mlb_player_count=10,
    )
    team = TeamStats(
        name="Netherlands", code="NED", elo=1400,
        runs_per_game=4.3, runs_allowed_per_game=3.8,
        batting_avg=0.260, team_obp=0.330, team_slg=0.405,
        team_woba=0.322, bullpen_era=3.50,
        bullpen_pitches_3d=0,
        defense_efficiency=0.705, sb_success_rate=0.72,
        lineup_wrc_plus=105, clutch_woba=0.315,
        roster_vol=roster,
    )
    pitchers = {
        "jansen": PitcherStats(
            name="Kenley Jansen", team="NED",
            era=3.30, fip=3.20, whip=1.08, k_per_9=10.0, bb_per_9=2.5,
            stuff_plus=118, ip_last_30=10.0, era_last_3=3.00,
            spring_era=2.90, pitch_count_last_3d=0,
            vs_left_ba=0.215, vs_right_ba=0.200,
            high_leverage_era=3.10, fastball_velo=93.0, role="SP",
        ),
        "leyer": PitcherStats(
            name="Robinson Leyer", team="NED",
            era=4.50, fip=4.60, whip=1.35, k_per_9=6.5, bb_per_9=3.0,
            stuff_plus=88, ip_last_30=14.0, era_last_3=4.20,
            spring_era=4.00, pitch_count_last_3d=0,
            vs_left_ba=0.260, vs_right_ba=0.265,
            high_leverage_era=4.80, fastball_velo=91.0, role="SP",
        ),
        "lowensteyn": PitcherStats(
            name="Mike Lowensteyn", team="NED",
            era=4.80, fip=4.90, whip=1.40, k_per_9=6.0, bb_per_9=3.5,
            stuff_plus=85, ip_last_30=12.0, era_last_3=4.50,
            spring_era=4.30, pitch_count_last_3d=0,
            vs_left_ba=0.268, vs_right_ba=0.275,
            high_leverage_era=5.10, fastball_velo=90.0, role="SP",
        ),
        "wainwright_pb": PitcherStats(
            name="Shairon Martis", team="NED",
            era=4.20, fip=4.30, whip=1.30, k_per_9=7.0, bb_per_9=3.0,
            stuff_plus=90, ip_last_30=8.0, era_last_3=4.00,
            spring_era=3.80, pitch_count_last_3d=0,
            vs_left_ba=0.252, vs_right_ba=0.258,
            high_leverage_era=4.50, fastball_velo=91.5, role="PB",
        ),
        "huijer": PitcherStats(
            name="Lars Huijer", team="NED",
            era=4.15, fip=4.30, whip=1.35, k_per_9=7.2, bb_per_9=3.0,
            stuff_plus=88, ip_last_30=18.0, era_last_3=3.90,
            spring_era=3.60, pitch_count_last_3d=0,
            vs_left_ba=0.262, vs_right_ba=0.268,
            high_leverage_era=4.80, fastball_velo=90.5, role="SP",
        ),
    }
    return team, pitchers


def _team_isr() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Israel — Surprise 2023 success, MLB-heritage roster. Elo 1280."""
    roster = RosterVolatility(
        roster_strength_index=55,
        confirmed_stars=["Dean Kremer", "Rowdy Tellez", "Joc Pederson"],
        uncertain_stars=["Alex Bregman"],
        absent_stars=[],
        team_chemistry=0.76,
        mlb_player_count=6,
    )
    team = TeamStats(
        name="Israel", code="ISR", elo=1280,
        runs_per_game=3.6, runs_allowed_per_game=4.5,
        batting_avg=0.245, team_obp=0.312, team_slg=0.380,
        team_woba=0.298, bullpen_era=4.30,
        bullpen_pitches_3d=0,
        defense_efficiency=0.692, sb_success_rate=0.70,
        lineup_wrc_plus=88, clutch_woba=0.290,
        roster_vol=roster,
    )
    pitchers = {
        "kremer": PitcherStats(
            name="Dean Kremer", team="ISR",
            era=3.80, fip=3.90, whip=1.22, k_per_9=8.0, bb_per_9=2.5,
            stuff_plus=105, ip_last_30=20.0, era_last_3=3.50,
            spring_era=3.40, pitch_count_last_3d=0,
            vs_left_ba=0.240, vs_right_ba=0.235,
            high_leverage_era=3.90, fastball_velo=92.5, role="SP",
        ),
        "goldberg": PitcherStats(
            name="Zack Goldberg", team="ISR",
            era=5.00, fip=5.10, whip=1.45, k_per_9=6.0, bb_per_9=3.5,
            stuff_plus=82, ip_last_30=10.0, era_last_3=4.80,
            spring_era=4.60, pitch_count_last_3d=0,
            vs_left_ba=0.270, vs_right_ba=0.278,
            high_leverage_era=5.30, fastball_velo=89.0, role="SP",
        ),
        "wolf": PitcherStats(
            name="Jake Wolf", team="ISR",
            era=5.20, fip=5.30, whip=1.48, k_per_9=5.5, bb_per_9=3.8,
            stuff_plus=80, ip_last_30=8.0, era_last_3=5.00,
            spring_era=4.80, pitch_count_last_3d=0,
            vs_left_ba=0.275, vs_right_ba=0.282,
            high_leverage_era=5.50, fastball_velo=88.5, role="SP",
        ),
        "kingham_pb": PitcherStats(
            name="Nick Kingham", team="ISR",
            era=4.50, fip=4.60, whip=1.38, k_per_9=7.0, bb_per_9=3.2,
            stuff_plus=88, ip_last_30=6.0, era_last_3=4.20,
            spring_era=4.00, pitch_count_last_3d=0,
            vs_left_ba=0.262, vs_right_ba=0.268,
            high_leverage_era=4.80, fastball_velo=92.0, role="PB",
        ),
    }
    return team, pitchers


def _team_nic() -> Tuple[TeamStats, Dict[str, PitcherStats]]:
    """Nicaragua — First WBC appearance, limited MLB pipeline. Elo 1260."""
    roster = RosterVolatility(
        roster_strength_index=42,
        confirmed_stars=["Erasmo Ramírez", "Jonathan Loáisiga"],
        uncertain_stars=[],
        absent_stars=[],
        team_chemistry=0.82,
        mlb_player_count=2,
    )
    team = TeamStats(
        name="Nicaragua", code="NIC", elo=1260,
        runs_per_game=3.2, runs_allowed_per_game=5.2,
        batting_avg=0.235, team_obp=0.295, team_slg=0.345,
        team_woba=0.278, bullpen_era=5.00,
        bullpen_pitches_3d=0,
        defense_efficiency=0.680, sb_success_rate=0.67,
        lineup_wrc_plus=70, clutch_woba=0.268,
        roster_vol=roster,
    )
    pitchers = {
        "loaisiga": PitcherStats(
            name="Jonathan Loáisiga", team="NIC",
            era=3.50, fip=3.40, whip=1.15, k_per_9=9.0, bb_per_9=3.5,
            stuff_plus=115, ip_last_30=10.0, era_last_3=3.20,
            spring_era=3.00, pitch_count_last_3d=0,
            vs_left_ba=0.220, vs_right_ba=0.215,
            high_leverage_era=3.30, fastball_velo=97.5, role="SP",
        ),
        "ramirez_e": PitcherStats(
            name="Erasmo Ramírez", team="NIC",
            era=4.80, fip=4.90, whip=1.38, k_per_9=6.0, bb_per_9=2.5,
            stuff_plus=82, ip_last_30=12.0, era_last_3=4.50,
            spring_era=4.30, pitch_count_last_3d=0,
            vs_left_ba=0.265, vs_right_ba=0.270,
            high_leverage_era=5.10, fastball_velo=90.0, role="SP",
        ),
        "pastora": PitcherStats(
            name="Oscar Pastora", team="NIC",
            era=5.50, fip=5.60, whip=1.52, k_per_9=5.5, bb_per_9=4.0,
            stuff_plus=78, ip_last_30=8.0, era_last_3=5.20,
            spring_era=5.00, pitch_count_last_3d=0,
            vs_left_ba=0.282, vs_right_ba=0.288,
            high_leverage_era=5.80, fastball_velo=88.0, role="SP",
        ),
        "delgado_pb": PitcherStats(
            name="Sandor De La Cruz", team="NIC",
            era=5.20, fip=5.30, whip=1.48, k_per_9=6.0, bb_per_9=3.8,
            stuff_plus=80, ip_last_30=6.0, era_last_3=5.00,
            spring_era=4.80, pitch_count_last_3d=0,
            vs_left_ba=0.278, vs_right_ba=0.285,
            high_leverage_era=5.50, fastball_velo=89.0, role="PB",
        ),
    }
    return team, pitchers


_TEAM_FACTORIES_D = {
    "DOM": _team_dom,
    "VEN": _team_ven,
    "NED": _team_ned,
    "ISR": _team_isr,
    "NIC": _team_nic,
}

# ═══════════════════════════════════════════════════════════════════════════════
# POOL D GAME SCHEDULE (10 games)
# Venue: LoanDepot Park, Miami (EST UTC-5, EDT UTC-4 after Mar 8 DST)
# ═══════════════════════════════════════════════════════════════════════════════

_POOL_D_SCHEDULE = [
    # ─── Day 1: March 7 (TW) / March 6 (Local EST) ──────
    {
        "game_id": "D01",
        "date": "2026-03-07",
        "game_time": "2026-03-06T12:00:00-05:00",
        "tw_time": "03/07 01:00",
        "away_code": "NED",
        "home_code": "VEN",
        "away_sp": "huijer",
        "home_sp": "castillo",
        "away_pb": "wainwright_pb",
        "home_pb": "pressly_pb",
        "away_bp_pitches_3d": 0,
        "home_bp_pitches_3d": 0,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 4.60, "ml_home": 1.22,
            "rl_spread": 3.5, "rl_fav": "VEN", "rl_fav_odds": 2.05, "rl_dog_odds": 1.70,
            "ou_line": 9.5, "ou_over": 1.90, "ou_under": 1.90,
            "f5_away": 3.80, "f5_home": 1.28,
            "tt_away_line": 2.5, "tt_home_line": 6.5,
        },
    },
    {
        "game_id": "D02",
        "date": "2026-03-07",
        "game_time": "2026-03-06T19:00:00-05:00",
        "tw_time": "03/07 08:00",
        "away_code": "NIC",
        "home_code": "DOM",
        "away_sp": "loaisiga",
        "home_sp": "valdez",
        "away_pb": "delgado_pb",
        "home_pb": "clase_pb",
        "away_bp_pitches_3d": 0,
        "home_bp_pitches_3d": 0,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 7.00, "ml_home": 1.10,
            "rl_spread": 4.5, "rl_fav": "DOM", "rl_fav_odds": 1.95, "rl_dog_odds": 1.85,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 6.50, "f5_home": 1.12,
            "tt_away_line": 2.5, "tt_home_line": 5.5,
        },
    },
    # ─── Day 2: March 8 (TW) / March 7 (Local EST) ──────
    {
        "game_id": "D03",
        "date": "2026-03-08",
        "game_time": "2026-03-07T12:00:00-05:00",
        "tw_time": "03/08 01:00",
        "away_code": "NIC",
        "home_code": "NED",
        "away_sp": "ramirez_e",
        "home_sp": "leyer",
        "away_pb": "delgado_pb",
        "home_pb": "wainwright_pb",
        "away_bp_pitches_3d": 65,
        "home_bp_pitches_3d": 65,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.80, "ml_home": 1.48,
            "rl_spread": 1.5, "rl_fav": "NED", "rl_fav_odds": 1.90, "rl_dog_odds": 1.90,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.60, "f5_home": 1.52,
            "tt_away_line": 3.5, "tt_home_line": 4.5,
        },
    },
    {
        "game_id": "D04",
        "date": "2026-03-08",
        "game_time": "2026-03-07T18:00:00-05:00",
        "tw_time": "03/08 07:00",
        "away_code": "ISR",
        "home_code": "VEN",
        "away_sp": "kremer",
        "home_sp": "suarez_r",
        "away_pb": "kingham_pb",
        "home_pb": "pressly_pb",
        "away_bp_pitches_3d": 0,
        "home_bp_pitches_3d": 65,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 3.80, "ml_home": 1.30,
            "rl_spread": 2.5, "rl_fav": "VEN", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 3.50, "f5_home": 1.32,
            "tt_away_line": 2.5, "tt_home_line": 4.5,
        },
    },
    # ─── Day 3: March 9 (TW) / March 8 (Local — DST starts) ─
    {
        "game_id": "D05",
        "date": "2026-03-09",
        "game_time": "2026-03-08T12:00:00-04:00",
        "tw_time": "03/09 00:00",
        "away_code": "NED",
        "home_code": "DOM",
        "away_sp": "lowensteyn",
        "home_sp": "soriano",
        "away_pb": "wainwright_pb",
        "home_pb": "diaz_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 65,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 4.50, "ml_home": 1.22,
            "rl_spread": 2.5, "rl_fav": "DOM", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 4.00, "f5_home": 1.25,
            "tt_away_line": 2.5, "tt_home_line": 5.5,
        },
    },
    {
        "game_id": "D06",
        "date": "2026-03-09",
        "game_time": "2026-03-08T19:00:00-04:00",
        "tw_time": "03/09 07:00",
        "away_code": "NIC",
        "home_code": "ISR",
        "away_sp": "pastora",
        "home_sp": "goldberg",
        "away_pb": "delgado_pb",
        "home_pb": "kingham_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 65,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.50, "ml_home": 1.58,
            "rl_spread": 1.5, "rl_fav": "ISR", "rl_fav_odds": 2.00, "rl_dog_odds": 1.80,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.40, "f5_home": 1.62,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
    # ─── Day 4: March 10 (TW) / March 9 (Local EDT) ─────
    {
        "game_id": "D07",
        "date": "2026-03-10",
        "game_time": "2026-03-09T12:00:00-04:00",
        "tw_time": "03/10 00:00",
        "away_code": "DOM",
        "home_code": "ISR",
        "away_sp": "peralta",
        "home_sp": "wolf",
        "away_pb": "clase_pb",
        "home_pb": "kingham_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.12, "ml_home": 6.50,
            "rl_spread": 3.5, "rl_fav": "DOM", "rl_fav_odds": 1.85, "rl_dog_odds": 1.95,
            "ou_line": 8.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 1.15, "f5_home": 5.50,
            "tt_away_line": 5.5, "tt_home_line": 2.5,
        },
    },
    {
        "game_id": "D08",
        "date": "2026-03-10",
        "game_time": "2026-03-09T19:00:00-04:00",
        "tw_time": "03/10 07:00",
        "away_code": "VEN",
        "home_code": "NIC",
        "away_sp": "carrasco",
        "home_sp": "loaisiga",
        "away_pb": "pressly_pb",
        "home_pb": "delgado_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.25, "ml_home": 4.20,
            "rl_spread": 2.5, "rl_fav": "VEN", "rl_fav_odds": 1.90, "rl_dog_odds": 1.90,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 1.30, "f5_home": 3.80,
            "tt_away_line": 4.5, "tt_home_line": 2.5,
        },
    },
    # ─── Day 5: March 11 (TW) / March 10 (Local EDT) ────
    {
        "game_id": "D09",
        "date": "2026-03-11",
        "game_time": "2026-03-10T12:00:00-04:00",
        "tw_time": "03/11 00:00",
        "away_code": "ISR",
        "home_code": "NED",
        "away_sp": "kremer",
        "home_sp": "jansen",
        "away_pb": "kingham_pb",
        "home_pb": "wainwright_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 2.80, "ml_home": 1.48,
            "rl_spread": 1.5, "rl_fav": "NED", "rl_fav_odds": 2.00, "rl_dog_odds": 1.80,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 2.60, "f5_home": 1.52,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
    {
        "game_id": "D10",
        "date": "2026-03-11",
        "game_time": "2026-03-10T19:00:00-04:00",
        "tw_time": "03/11 07:00",
        "away_code": "VEN",
        "home_code": "DOM",
        "away_sp": "castillo",
        "home_sp": "valdez",
        "away_pb": "pressly_pb",
        "home_pb": "clase_pb",
        "away_bp_pitches_3d": 130,
        "home_bp_pitches_3d": 130,
        "neutral_site": True,
        "odds_params": {
            "ml_away": 1.95, "ml_home": 1.90,
            "rl_spread": 1.5, "rl_fav": "DOM", "rl_fav_odds": 2.15, "rl_dog_odds": 1.72,
            "ou_line": 7.5, "ou_over": 1.85, "ou_under": 1.95,
            "f5_away": 1.90, "f5_home": 1.92,
            "tt_away_line": 3.5, "tt_home_line": 3.5,
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def list_wbc_matches_d() -> List[dict]:
    return [
        {"game_id": g["game_id"], "date": g["date"], "tw_time": g["tw_time"],
         "away": g["away_code"], "home": g["home_code"], "game_time": g["game_time"]}
        for g in _POOL_D_SCHEDULE
    ]


def fetch_wbc_match_d(game_id: str, live: bool = False,
                      use_mock: bool = False) -> MatchData:
    game = None
    for g in _POOL_D_SCHEDULE:
        if g["game_id"] == game_id.upper():
            game = g
            break
    if game is None:
        available = [g["game_id"] for g in _POOL_D_SCHEDULE]
        raise ValueError(f"Unknown game_id '{game_id}'. Available: {available}")

    away_code, home_code = game["away_code"], game["home_code"]
    away_team, away_pitchers = _TEAM_FACTORIES_D[away_code]()
    home_team, home_pitchers = _TEAM_FACTORIES_D[home_code]()
    away_team.bullpen_pitches_3d = game["away_bp_pitches_3d"]
    home_team.bullpen_pitches_3d = game["home_bp_pitches_3d"]

    pc_rule = PitchCountRule(round_name="Pool D", max_pitches=65,
                             rest_after_30=1, rest_after_50=4,
                             expected_sp_innings=3.5)

    ts = game["game_time"]
    p = game["odds_params"]
    odds = _std_odds(away_code, home_code, ts, **p)

    away_sp = away_pitchers[game["away_sp"]]
    home_sp = home_pitchers[game["home_sp"]]
    away_pb = away_pitchers.get(game.get("away_pb"))
    home_pb = home_pitchers.get(game.get("home_pb"))

    stuff = {"DOM": 128, "VEN": 118, "NED": 95, "ISR": 88, "NIC": 80}

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
        venue="LoanDepot Park, Miami",
        round_name="Pool D",
        neutral_site=game["neutral_site"],
    )
